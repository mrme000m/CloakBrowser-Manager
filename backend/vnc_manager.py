"""KasmVNC display allocation and lifecycle management."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import socket
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger("cloakbrowser.manager.vnc")


@dataclass
class VNCInstance:
    display: int
    ws_port: int
    process: subprocess.Popen | None = None


class VNCManager:
    BASE_DISPLAY = 100
    BASE_WS_PORT = 6100
    # Cap on concurrent displays (matches CDP's 100-port range; bounded by
    # MAX_RUNNING_PROFILES in practice). Configurable via env.
    MAX_DISPLAYS = int(os.environ.get("VNC_MAX_DISPLAYS", "100") or 100)
    _MAX_WS_SCAN = 200  # attempts to find a free ws_port at/after the base

    def __init__(self):
        self._allocated: dict[int, VNCInstance] = {}
        self._lock = asyncio.Lock()

    async def allocate(self) -> tuple[int, int]:
        """Returns (display_number, ws_port) for a new profile.

        Picks the lowest free display in [BASE_DISPLAY, BASE_DISPLAY+MAX_DISPLAYS)
        and bind-checks the corresponding ws_port (scanning forward if taken)
        so a non-free port no longer silently collides (Section 3e).
        """
        async with self._lock:
            display = self.BASE_DISPLAY
            while display in self._allocated:
                display += 1
            if display >= self.BASE_DISPLAY + self.MAX_DISPLAYS:
                raise RuntimeError(
                    f"No free VNC display in range "
                    f"{self.BASE_DISPLAY}-{self.BASE_DISPLAY + self.MAX_DISPLAYS - 1}"
                )
            base_ws = self.BASE_WS_PORT + (display - self.BASE_DISPLAY)
            ws_port = self._find_free_ws_port(base_ws)
            self._allocated[display] = VNCInstance(display=display, ws_port=ws_port)
            return display, ws_port

    @staticmethod
    def _find_free_ws_port(start: int) -> int:
        """Return a free TCP port at or after `start` (bind-checked on 127.0.0.1)."""
        for port in range(start, start + VNCManager._MAX_WS_SCAN):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f"No free WebSocket port found at or after {start}")

    async def start_vnc(
        self,
        display: int,
        ws_port: int,
        width: int = 1920,
        height: int = 1080,
    ) -> subprocess.Popen:
        """Start Xvnc (KasmVNC) on the given display."""
        xvnc_bin = shutil.which("Xvnc") or "Xvnc"

        # KasmVNC requires -httpd to enable the WebSocket handler on the websocket port.
        # Without it, the port accepts TCP but won't do WebSocket upgrade.
        httpd_dir = "/usr/share/kasmvnc/www"

        cmd = [
            xvnc_bin,
            f":{display}",
            "-websocketPort", str(ws_port),
            "-rfbport", "-1",  # disable raw VNC TCP port — WebSocket only
            "-geometry", f"{width}x{height}",
            "-depth", "24",
            "-SecurityTypes", "None",
            "-DisableBasicAuth",
            "-interface", "127.0.0.1",  # internal only, proxied by FastAPI
            "-AlwaysShared",
            "-httpd", httpd_dir,
        ]

        log_path = f"/tmp/xvnc-{display}.log"
        logger.info("Starting Xvnc on :%d (ws_port=%d) log=%s", display, ws_port, log_path)

        log_file = open(log_path, "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
        )
        log_file.close()  # Popen inherited the fd, parent doesn't need it

        # Wait a moment for Xvnc to initialize
        await asyncio.sleep(0.5)

        if proc.poll() is not None:
            try:
                with open(log_path) as f:
                    err = f.read()
            except Exception as exc:
                logger.debug("Failed to read Xvnc log %s: %s", log_path, exc)
                err = ""
            raise RuntimeError(f"Xvnc failed to start on :{display}: {err}")

        async with self._lock:
            if display in self._allocated:
                self._allocated[display].process = proc

        return proc

    async def stop_vnc(self, display: int):
        """Kill Xvnc for given display and release allocation."""
        async with self._lock:
            instance = self._allocated.pop(display, None)

        if instance and instance.process:
            logger.info("Stopping Xvnc on :%d", display)
            instance.process.terminate()
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, instance.process.wait, 5,
                )
            except subprocess.TimeoutExpired:
                instance.process.kill()

    async def cleanup_all(self):
        """Kill all managed Xvnc processes. Called on shutdown."""
        async with self._lock:
            displays = list(self._allocated.keys())

        for display in displays:
            await self.stop_vnc(display)

    async def cleanup_stale(self):
        """Kill orphan Xvnc processes from previous runs."""
        try:
            result = subprocess.run(
                ["pkill", "-f", r"Xvnc :[0-9]"],
                capture_output=True,
            )
            if result.returncode == 0:
                logger.info("Cleaned up stale Xvnc processes")
        except FileNotFoundError:
            logger.debug("pkill not found, skipping stale Xvnc cleanup")

    def get_ws_port(self, display: int) -> int | None:
        """Get WebSocket port for a display."""
        instance = self._allocated.get(display)
        return instance.ws_port if instance else None

    @property
    def active_displays(self) -> list[int]:
        return list(self._allocated.keys())

"""Launch/stop/track CloakBrowser instances per profile."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cloakbrowser import launch_persistent_context_async

from . import database as db
from . import proxy_health
from .vnc_manager import VNCManager

logger = logging.getLogger("cloakbrowser.manager.browser")

# Section 3d: hard cap on concurrent running browsers (0 = unlimited).
MAX_RUNNING_PROFILES = int(os.environ.get("MAX_RUNNING_PROFILES", "0") or 0)


def _normalize_proxy(raw: str) -> str:
    """Convert common proxy formats to http://user:pass@host:port.

    Accepts:
      - http://user:pass@host:port  (already valid)
      - host:port:user:pass
      - host:port
    """
    if raw.startswith(("http://", "https://", "socks5://")):
        return raw
    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, passwd = parts
        return f"http://{user}:{passwd}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{raw}"
    return raw


def _resolve_proxy_url(profile: dict[str, Any]) -> str | None:
    """Resolve the proxy URL for a profile.

    Priority:
      1. Explicit proxy field from the profile
      2. proxy_group_id → pick a member per the group's rotation mode
      3. proxy_credential_id → lookup credential and build URL
    """
    raw_proxy = profile.get("proxy") or None
    if raw_proxy:
        return _normalize_proxy(raw_proxy)

    group_id = profile.get("proxy_group_id")
    if group_id:
        url = _resolve_group_proxy(profile, group_id)
        if url:
            return url

    cred_id = profile.get("proxy_credential_id")
    if cred_id:
        cred = db.get_proxy_credential(cred_id)
        if cred:
            return proxy_health.build_proxy_url(cred)

    return None


def _resolve_group_proxy(profile: dict[str, Any], group_id: str) -> str | None:
    """Pick a member credential of a proxy group per its rotation mode and build its URL."""
    group = db.get_proxy_group(group_id)
    if not group:
        return None
    member_ids = db.list_group_member_ids(group_id)
    if not member_ids:
        return None
    mode = group.get("rotation_mode", "round_robin")
    chosen_id: str | None = None
    if mode == "round_robin":
        idx, _n = db.next_round_robin_index(group_id)
        if idx < 0:
            return None
        chosen_id = member_ids[idx]
    elif mode == "random":
        import random
        chosen_id = random.choice(member_ids)
    else:  # sticky_session
        assigned = profile.get("proxy_assignment")
        if assigned and assigned in member_ids:
            chosen_id = assigned
        else:
            pos = int(hashlib.md5(profile["id"].encode()).hexdigest(), 16) % len(member_ids)
            chosen_id = member_ids[pos]
            db.update_profile(profile["id"], proxy_assignment=chosen_id)
    cred = db.get_proxy_credential(chosen_id)
    if not cred:
        return None
    return proxy_health.build_proxy_url(cred)


def _validate_proxy(url: str) -> None:
    """Validate that a normalized proxy URL has scheme, host, and port."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", "socks5"):
        raise ValueError(
            f"Invalid proxy scheme '{parsed.scheme}'. Must be http, https, or socks5."
        )
    if not parsed.hostname:
        raise ValueError(f"Proxy URL missing hostname: {url}")
    if not parsed.port:
        raise ValueError(f"Proxy URL missing port: {url}")


def _init_profile_defaults(user_data_dir: Path) -> None:
    """Set up bookmarks and DuckDuckGo search on first launch."""
    default_dir = user_data_dir / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)

    # --- Bookmarks (only on first launch) ---
    bookmarks_path = default_dir / "Bookmarks"
    if not bookmarks_path.exists():
        ts = str(int(time.time() * 1_000_000))  # Chrome timestamp format
        _id = 1

        def bm(name: str, url: str) -> dict:
            nonlocal _id
            _id += 1
            return {"type": "url", "id": str(_id), "name": name, "url": url, "date_added": ts}

        def folder(name: str, children: list) -> dict:
            nonlocal _id
            _id += 1
            return {"type": "folder", "id": str(_id), "name": name, "children": children, "date_added": ts, "date_modified": ts}

        bookmarks = {
            "checksum": "",
            "roots": {
                "bookmark_bar": {
                    "type": "folder", "id": "1", "name": "Bookmarks bar",
                    "date_added": ts, "date_modified": ts,
                    "children": [
                        folder("Detection Tests", [
                            bm("Rebrowser Bot Detector", "https://bot-detector.rebrowser.net/"),
                            bm("Incolumitas", "https://bot.incolumitas.com/"),
                            bm("SannySort", "https://bot.sannysoft.com/"),
                            bm("BrowserScan Bot", "https://www.browserscan.net/bot-detection"),
                            bm("FingerprintJS Demo", "https://demo.fingerprint.com/web-scraping"),
                            bm("Pixelscan", "https://pixelscan.net/fingerprint-check"),
                            bm("CreepJS", "https://abrahamjuliot.github.io/creepjs/"),
                            bm("fingerprint-scan", "https://fingerprint-scan.com/"),
                            bm("DeviceInfo Bot", "https://deviceandbrowserinfo.com/are_you_a_bot"),
                        ]),
                        folder("Fingerprint", [
                            bm("BrowserLeaks Canvas", "https://browserleaks.com/canvas"),
                            bm("BrowserLeaks WebGL", "https://browserleaks.com/webgl"),
                            bm("BrowserLeaks Fonts", "https://browserleaks.com/fonts"),
                            bm("BrowserLeaks JS", "https://browserleaks.com/javascript"),
                            bm("FingerprintJS OSS", "https://fingerprintjs.github.io/fingerprintjs/"),
                            bm("Audio FP", "https://audiofingerprint.openwpm.com/"),
                            bm("DeviceInfo", "https://deviceandbrowserinfo.com/info_device"),
                        ]),
                        folder("Headers & TLS", [
                            bm("httpbin headers", "https://httpbin.org/headers"),
                            bm("httpbin IP", "https://httpbin.org/ip"),
                            bm("TLS Fingerprint", "https://tls.browserleaks.com/"),
                        ]),
                        folder("reCAPTCHA", [
                            bm("Google v3 Demo", "https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php"),
                            bm("2captcha v3", "https://2captcha.com/demo/recaptcha-v3"),
                            bm("Turnstile", "https://peet.ws/turnstile-test/non-interactive.html"),
                        ]),
                    ],
                },
                "other": {"type": "folder", "id": "2", "name": "Other bookmarks", "children": []},
                "synced": {"type": "folder", "id": "3", "name": "Mobile bookmarks", "children": []},
            },
            "version": 1,
        }
        bookmarks_path.write_text(json.dumps(bookmarks, indent=2))
        logger.info("Created default bookmarks for %s", user_data_dir.name)

    # --- DuckDuckGo as default search engine ---
    prefs_path = default_dir / "Preferences"
    if not prefs_path.exists():
        prefs = {
            "default_search_provider_data": {
                "template_url_data": {
                    "keyword": "duckduckgo.com",
                    "short_name": "DuckDuckGo",
                    "url": "https://duckduckgo.com/?q={searchTerms}",
                    "suggestions_url": "https://duckduckgo.com/ac/?q={searchTerms}&type=list",
                    "favicon_url": "https://duckduckgo.com/favicon.ico",
                }
            },
            "default_search_provider": {
                "enabled": True,
            },
        }
        prefs_path.write_text(json.dumps(prefs, indent=2))
        logger.info("Set DuckDuckGo as default search for %s", user_data_dir.name)


BASE_CDP_PORT = 5100
CDP_PORT_RANGE = 100  # cycle through 5100-5199 to avoid TIME_WAIT collisions


@dataclass
class RunningProfile:
    profile_id: str
    context: Any  # Playwright BrowserContext
    display: int
    ws_port: int
    cdp_port: int
    # GeoIP resolved from the (proxied) browser after launch (best-effort)
    exit_ip: str | None = None
    effective_timezone: str | None = None
    effective_locale: str | None = None


class BrowserManager:
    def __init__(self):
        self.running: dict[str, RunningProfile] = {}
        self._launching: set[str] = set()  # profile IDs currently being launched
        self.vnc = VNCManager()
        self._lock = asyncio.Lock()
        self._next_cdp_port = BASE_CDP_PORT
        self._auto_launch_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None
        # Crash auto-restart bookkeeping (Section 3c)
        self._restart_tasks: dict[str, asyncio.Task] = {}
        self._restart_counts: dict[str, int] = {}

    async def launch(self, profile: dict[str, Any], is_restart: bool = False) -> RunningProfile:
        """Launch a browser instance for the given profile."""
        profile_id = profile["id"]

        async with self._lock:
            if profile_id in self.running or profile_id in self._launching:
                raise RuntimeError(f"Profile {profile_id} is already running")
            if MAX_RUNNING_PROFILES > 0 and len(self.running) + len(self._launching) >= MAX_RUNNING_PROFILES:
                raise ValueError(f"Max running profiles ({MAX_RUNNING_PROFILES}) reached")
            self._launching.add(profile_id)

        # Manual (non-restart) launch resets the crash-restart counter and
        # cancels any pending auto-restart for this profile.
        if not is_restart:
            self._restart_counts.pop(profile_id, None)
            task = self._restart_tasks.pop(profile_id, None)
            if task and not task.done():
                task.cancel()

        display, ws_port = await self.vnc.allocate()

        try:
            cdp_port = self._allocate_cdp_port()
        except ValueError:
            async with self._lock:
                self._launching.discard(profile_id)
            await self.vnc.stop_vnc(display)
            raise

        # Clean stale Chromium lock files (left by previous container crashes)
        user_data_dir = Path(profile["user_data_dir"])
        for lock_file in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            lock_path = user_data_dir / lock_file
            lock_path.unlink(missing_ok=True)

        # Set up bookmarks and search engine on first launch
        _init_profile_defaults(user_data_dir)

        try:
            # Start KasmVNC on the allocated display
            await self.vnc.start_vnc(
                display,
                ws_port,
                width=profile.get("screen_width", 1920),
                height=profile.get("screen_height", 1080),
            )

            # Build fingerprint args from profile settings
            extra_args = self._build_fingerprint_args(profile)
            extra_args += profile.get("launch_args") or []
            extra_args.append(f"--remote-debugging-port={cdp_port}")

            # Resolve proxy (explicit field takes priority, then credential)
            proxy = _resolve_proxy_url(profile)
            if proxy:
                _validate_proxy(proxy)

            # Launch CloakBrowser on that display
            # DISPLAY is passed via env kwarg to avoid process-wide os.environ mutation
            context = await launch_persistent_context_async(
                user_data_dir=profile["user_data_dir"],
                headless=bool(profile.get("headless", False)),
                proxy=proxy,
                args=extra_args,
                timezone=profile.get("timezone") or None,
                locale=profile.get("locale") or None,
                humanize=bool(profile.get("humanize", False)),
                human_preset=profile.get("human_preset", "default"),
                geoip=bool(profile.get("geoip", False)),
                color_scheme=profile.get("color_scheme") or None,
                user_agent=profile.get("user_agent") or None,
                viewport={
                    "width": profile.get("screen_width", 1920),
                    "height": profile.get("screen_height", 1080) - 133,
                },
                env={**os.environ, "DISPLAY": f":{display}"},
            )

            # Inject clipboard listener: captures copied text on every page
            # so the GET /clipboard endpoint can read it via page.evaluate()
            _clipboard_init_js = """
                window.__clipboardText = '';
                document.addEventListener('copy', () => {
                    const sel = window.getSelection();
                    if (sel) window.__clipboardText = sel.toString();
                });
                document.addEventListener('keydown', (e) => {
                    if ((e.ctrlKey || e.metaKey) && e.key === 'c' && !e.altKey && !e.shiftKey) {
                        const sel = window.getSelection();
                        if (sel && sel.toString()) window.__clipboardText = sel.toString();
                    }
                });
            """
            await context.add_init_script(_clipboard_init_js)
            # Also inject into already-open pages (about:blank created before init_script)
            for p in context.pages:
                try:
                    await p.evaluate(_clipboard_init_js)
                except Exception as exc:
                    logger.debug("Clipboard init failed on existing page: %s", exc)

            running = RunningProfile(
                profile_id=profile_id,
                context=context,
                display=display,
                ws_port=ws_port,
                cdp_port=cdp_port,
            )

            # Auto-cleanup if browser crashes or user closes Chrome via VNC
            context.on("close", lambda: asyncio.ensure_future(
                self._on_browser_closed(profile_id)
            ))

            async with self._lock:
                self.running[profile_id] = running
                self._launching.discard(profile_id)

            logger.info(
                "Launched profile %s on display :%d (ws_port=%d, cdp_port=%d)",
                profile_id, display, ws_port, cdp_port,
            )

            # Best-effort GeoIP detection from the (proxied) browser — non-blocking.
            asyncio.create_task(self._detect_geoip(profile_id, running))

            return running

        except BaseException:
            async with self._lock:
                self._launching.discard(profile_id)
            await self.vnc.stop_vnc(display)
            raise

    async def _on_browser_closed(self, profile_id: str):
        """Called when browser exits (crash, user closed via VNC).

        Not triggered by stop() — stop() pops `running` first, so this finds
        nothing and returns early. That's what lets an explicit stop avoid
        auto-restart while an unexpected close triggers it (Section 3c).
        """
        async with self._lock:
            running = self.running.pop(profile_id, None)

        if running:
            logger.info("Browser closed for profile %s, cleaning up", profile_id)
            await self.vnc.stop_vnc(running.display)

        await self._maybe_schedule_restart(profile_id)

    async def stop(self, profile_id: str):
        """Stop a running browser instance and cancel any pending auto-restart."""
        # Pop before close so _on_browser_closed() finds nothing to clean up
        async with self._lock:
            running = self.running.pop(profile_id, None)

        # Cancel any pending crash auto-restart for this profile
        self._restart_counts.pop(profile_id, None)
        task = self._restart_tasks.pop(profile_id, None)
        if task and not task.done():
            task.cancel()

        if not running:
            return

        logger.info("Stopping profile %s", profile_id)

        try:
            await running.context.close()
        except Exception as exc:
            logger.warning("Error closing context for %s: %s", profile_id, exc)

        await self.vnc.stop_vnc(running.display)

    def get_status(self, profile_id: str) -> dict[str, Any]:
        """Get running status for a profile."""
        running = self.running.get(profile_id)
        if running:
            return {
                "status": "running",
                "vnc_ws_port": running.ws_port,
                "display": f":{running.display}",
                "cdp_url": f"/api/profiles/{profile_id}/cdp",
                "exit_ip": running.exit_ip,
                "effective_timezone": running.effective_timezone,
                "effective_locale": running.effective_locale,
            }
        return {
            "status": "stopped",
            "vnc_ws_port": None,
            "display": None,
            "cdp_url": None,
            "exit_ip": None,
            "effective_timezone": None,
            "effective_locale": None,
        }

    async def _maybe_schedule_restart(self, profile_id: str) -> None:
        """Schedule an auto-restart for a crashed profile (Section 3c)."""
        profile = db.get_profile(profile_id)
        if not profile or not profile.get("restart_on_crash"):
            return
        if profile_id in self.running or profile_id in self._launching:
            return  # already running/launching again
        max_restarts = int(profile.get("max_restarts", 5) or 0)
        count = self._restart_counts.get(profile_id, 0)
        if max_restarts <= 0 or count >= max_restarts:
            logger.warning(
                "Not auto-restarting %s: max_restarts reached (%d/%d)",
                profile_id, count, max_restarts,
            )
            self._restart_counts.pop(profile_id, None)
            return
        backoff = min(2 ** count, 60)
        self._restart_counts[profile_id] = count + 1
        logger.info(
            "Scheduling auto-restart for %s in %ds (attempt %d/%d)",
            profile_id, backoff, count + 1, max_restarts,
        )
        task = asyncio.create_task(self._restart_after(profile_id, backoff))
        self._restart_tasks[profile_id] = task

    async def _restart_after(self, profile_id: str, delay: int) -> None:
        try:
            await asyncio.sleep(delay)
            profile = db.get_profile(profile_id)
            if not profile:
                return
            if profile_id in self.running or profile_id in self._launching:
                return
            if profile.get("is_template"):
                return
            logger.info("Auto-restarting profile %s", profile_id)
            await self.launch(profile, is_restart=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Auto-restart failed for %s: %s", profile_id, exc)
        finally:
            self._restart_tasks.pop(profile_id, None)

    async def _detect_geoip(self, profile_id: str, running: RunningProfile) -> None:
        """Best-effort: read exit IP / timezone / locale from the proxied browser."""
        try:
            pages = running.context.pages
            page = pages[0] if pages else None
            if page is None:
                return
            try:
                ip = await page.evaluate(
                    "await fetch('https://api.ipify.org?format=json')"
                    ".then(r=>r.json()).then(d=>d.ip).catch(()=>null)"
                )
                running.exit_ip = ip
            except Exception as exc:
                logger.debug("geoip exit ip failed for %s: %s", profile_id, exc)
            try:
                tz = await page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
                running.effective_timezone = tz
            except Exception as exc:
                logger.debug("geoip tz failed for %s: %s", profile_id, exc)
            try:
                loc = await page.evaluate("navigator.language")
                running.effective_locale = loc
            except Exception as exc:
                logger.debug("geoip locale failed for %s: %s", profile_id, exc)
        except Exception as exc:
            logger.debug("geoip detection failed for %s: %s", profile_id, exc)

    async def cleanup_all(self):
        """Stop all running profiles. Called on shutdown."""
        async with self._lock:
            profile_ids = list(self.running.keys())

        for pid in profile_ids:
            await self.stop(pid)

        await self.vnc.cleanup_all()

    async def cleanup_stale(self):
        """Kill orphan processes from previous container runs."""
        await self.vnc.cleanup_stale()

    async def auto_launch_all(self):
        """Launch all profiles with auto_launch=True. Called on startup."""
        from . import database as db

        profiles = db.list_profiles()
        auto_profiles = [p for p in profiles if p.get("auto_launch")]
        if not auto_profiles:
            logger.info("No profiles configured for auto-launch")
            return

        logger.info("Auto-launching %d profile(s)...", len(auto_profiles))
        for profile in auto_profiles:
            try:
                await asyncio.wait_for(self.launch(profile), timeout=60)
                logger.info("Auto-launched profile %s (%s)", profile["name"], profile["id"])
            except Exception as exc:
                logger.error(
                    "Auto-launch failed for profile %s (%s): %s",
                    profile["name"], profile["id"], exc,
                )
        logger.info("Auto-launch complete: %d running", len(self.running))

    def _allocate_cdp_port(self) -> int:
        """Find a free CDP port using a rotating counter to avoid TIME_WAIT collisions."""
        for _ in range(CDP_PORT_RANGE):
            port = self._next_cdp_port
            self._next_cdp_port = BASE_CDP_PORT + (
                (self._next_cdp_port + 1 - BASE_CDP_PORT) % CDP_PORT_RANGE
            )
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise ValueError("No free CDP ports available in range %d-%d" % (BASE_CDP_PORT, BASE_CDP_PORT + CDP_PORT_RANGE - 1))

    def _build_fingerprint_args(self, profile: dict[str, Any]) -> list[str]:
        """Build extra Chromium args from profile fingerprint settings."""
        args: list[str] = [
            "--disable-infobars",
            "--test-type",  # suppress "unsupported flag: --no-sandbox" bad flags warning
            "--use-angle=swiftshader",  # software GL for VNC (no GPU in container)
        ]

        seed = profile.get("fingerprint_seed")
        if seed is not None:
            args.append(f"--fingerprint={seed}")

        p = profile.get("platform")
        if p:
            # Map our "macos" to binary's "macos"
            args.append(f"--fingerprint-platform={p}")

        vendor = profile.get("gpu_vendor")
        if vendor:
            args.append(f"--fingerprint-gpu-vendor={vendor}")

        renderer = profile.get("gpu_renderer")
        if renderer:
            args.append(f"--fingerprint-gpu-renderer={renderer}")

        hw = profile.get("hardware_concurrency")
        if hw is not None:
            args.append(f"--fingerprint-hardware-concurrency={hw}")

        sw = profile.get("screen_width")
        sh = profile.get("screen_height")
        if sw:
            args.append(f"--fingerprint-screen-width={sw}")
        if sh:
            args.append(f"--fingerprint-screen-height={sh}")

        return args

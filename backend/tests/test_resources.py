"""Tests for per-profile resource usage (psutil-backed)."""

from __future__ import annotations

import sys
import time
import types
from unittest.mock import MagicMock

import pytest


# ── BrowserManager.get_resources (unit) ─────────────────────────────────────


def test_get_resources_stopped():
    from backend.browser_manager import BrowserManager

    mgr = BrowserManager()
    assert mgr.get_resources("nonexistent") is None


def test_get_resources_psutil_missing(monkeypatch):
    """When psutil can't be imported, get_resources returns None (graceful)."""
    from backend.browser_manager import BrowserManager, RunningProfile

    mgr = BrowserManager()
    rp = RunningProfile(
        profile_id="abc", context=MagicMock(), display=100, ws_port=6100, cdp_port=5100
    )
    monkeypatch.setitem(mgr.running, "abc", rp)
    # `import psutil` inside get_resources raises ImportError when the slot is None.
    monkeypatch.setitem(sys.modules, "psutil", None)
    assert mgr.get_resources("abc") is None


def test_get_resources_running(monkeypatch):
    """Sum CPU/RSS over the browser process + recursive children."""
    from backend.browser_manager import BrowserManager, RunningProfile

    mgr = BrowserManager()
    rp = RunningProfile(
        profile_id="abc",
        context=MagicMock(),
        display=100,
        ws_port=6100,
        cdp_port=5100,
        chrome_pid=1234,
        started_at=time.time() - 10,
    )
    monkeypatch.setitem(mgr.running, "abc", rp)

    class FakeProc:
        def __init__(self, pid, cpu, rss, children=None):
            self._pid = pid
            self._cpu = cpu
            self._rss = rss
            self._children = children or []

        def cpu_percent(self, interval=None):
            return self._cpu

        def memory_info(self):
            return types.SimpleNamespace(rss=self._rss)

        def children(self, recursive=False):
            return self._children

        def is_running(self):
            return True

    child = FakeProc(1235, 10.0, 50 * 1024 * 1024)
    parent = FakeProc(1234, 5.0, 100 * 1024 * 1024, children=[child])
    fake = types.SimpleNamespace(
        pid_exists=lambda _p: True,
        Process=lambda _pid: parent,
        process_iter=lambda attrs=None: [],
    )
    monkeypatch.setitem(sys.modules, "psutil", fake)

    r = mgr.get_resources("abc")
    assert r is not None
    assert r["cpu_percent"] == 15.0  # 5 + 10
    assert r["mem_mb"] == 150.0  # (100 + 50) MiB
    assert r["proc_count"] == 2  # parent + child
    assert r["uptime_s"] >= 10


def test_get_resources_pid_rediscover(monkeypatch):
    """A dead cached pid triggers rediscovery via _discover_chrome_pid."""
    from backend.browser_manager import BrowserManager, RunningProfile

    mgr = BrowserManager()
    rp = RunningProfile(
        profile_id="abc",
        context=MagicMock(),
        display=100,
        ws_port=6100,
        cdp_port=5100,
        chrome_pid=9999,  # stale: pid_exists returns False
        started_at=time.time() - 5,
    )
    monkeypatch.setitem(mgr.running, "abc", rp)

    class FakeProc:
        def __init__(self, cpu, rss, children=None):
            self._cpu = cpu
            self._rss = rss
            self._children = children or []

        def cpu_percent(self, interval=None):
            return self._cpu

        def memory_info(self):
            return types.SimpleNamespace(rss=self._rss)

        def children(self, recursive=False):
            return self._children

        def is_running(self):
            return True

    parent = FakeProc(7.0, 64 * 1024 * 1024)
    # rediscovery returns 1234; Process(1234) -> parent; pid_exists False only for 9999.
    fake = types.SimpleNamespace(
        pid_exists=lambda p: p != 9999,
        Process=lambda _pid: parent,
        process_iter=lambda attrs=None: [],
    )
    monkeypatch.setitem(sys.modules, "psutil", fake)
    # Patch the module-level discoverer so we don't scan real host processes.
    import backend.browser_manager as bm

    monkeypatch.setattr(bm, "_discover_chrome_pid", lambda cdp_port: 1234)

    r = mgr.get_resources("abc")
    assert r is not None
    assert r["cpu_percent"] == 7.0
    assert rp.chrome_pid == 1234  # rediscovered pid cached


# ── API surface (resources + aggregates) ────────────────────────────────────


def test_status_resources_endpoint(app_client, monkeypatch):
    from backend import database as db
    from backend import main
    from backend.browser_manager import RunningProfile

    # Isolate from singleton state leaked by other launch tests: swap in a
    # fresh `running` dict for this test (monkeypatch restores it on teardown).
    monkeypatch.setattr(main.browser_mgr, "running", {})

    pid = db.create_profile(name="P")["id"]
    rp = RunningProfile(
        profile_id=pid,
        context=MagicMock(),
        display=100,
        ws_port=6100,
        cdp_port=5100,
    )
    main.browser_mgr.running[pid] = rp
    monkeypatch.setattr(
        main.browser_mgr,
        "get_resources",
        lambda _i: {"cpu_percent": 42.0, "mem_mb": 512.0, "uptime_s": 99.0, "proc_count": 3},
    )

    # GET /api/profiles/{id}/status
    r = app_client.get(f"/api/profiles/{pid}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["resources"] == {
        "cpu_percent": 42.0,
        "mem_mb": 512.0,
        "uptime_s": 99.0,
        "proc_count": 3,
    }

    # GET /api/profiles (list enrichment)
    r2 = app_client.get("/api/profiles")
    prof = next(p for p in r2.json() if p["id"] == pid)
    assert prof["status"] == "running"
    assert prof["resources"]["cpu_percent"] == 42.0
    assert prof["resources"]["mem_mb"] == 512.0

    # GET /api/status (aggregates)
    s = app_client.get("/api/status").json()
    assert s["total_cpu_percent"] == 42.0
    assert s["total_mem_mb"] == 512.0
    assert s["total_proc_count"] == 3


def test_status_resources_none_when_stopped(app_client, monkeypatch):
    from backend import database as db
    from backend import main

    monkeypatch.setattr(main.browser_mgr, "running", {})
    pid = db.create_profile(name="P")["id"]

    r = app_client.get(f"/api/profiles/{pid}/status").json()
    assert r["status"] == "stopped"
    assert r["resources"] is None

    prof = next(p for p in app_client.get("/api/profiles").json() if p["id"] == pid)
    assert prof["resources"] is None

    s = app_client.get("/api/status").json()
    assert s["total_cpu_percent"] is None
    assert s["total_mem_mb"] is None
    assert s["total_proc_count"] is None

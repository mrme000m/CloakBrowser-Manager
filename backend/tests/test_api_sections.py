"""API tests for sections 2/3/4: clone, bulk, templates, resource limit,
proxy test, locations, providers, groups, and local-CDP exemption."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient

from backend import main
from backend.browser_manager import RunningProfile


# ── Clone (3a) ───────────────────────────────────────────────────────────────


def test_clone_profile(app_client: TestClient):
    pid = app_client.post("/api/profiles", json={"name": "Original", "fingerprint_seed": 42}).json()["id"]
    resp = app_client.post(f"/api/profiles/{pid}/clone", json={"name": "Copy"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] != pid
    assert data["name"] == "Copy (copy)"
    assert data["is_template"] is False
    assert data["fingerprint_seed"] != 42


# ── Templates (3a) ─────────────────────────────────────────────────────────────


def test_template_cannot_be_launched(app_client: TestClient):
    pid = app_client.post("/api/profiles", json={"name": "T", "is_template": True}).json()["id"]
    resp = app_client.post(f"/api/profiles/{pid}/launch")
    assert resp.status_code == 409
    assert "Template" in resp.json()["detail"]


# ── Bulk actions (3b) ──────────────────────────────────────────────────────────


def test_bulk_launch(app_client: TestClient, monkeypatch):
    a = app_client.post("/api/profiles", json={"name": "A"}).json()["id"]
    b = app_client.post("/api/profiles", json={"name": "B"}).json()["id"]
    monkeypatch.setattr(main.browser_mgr, "launch", AsyncMock())
    resp = app_client.post("/api/profiles/bulk/launch", json={"ids": [a, b]})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert {r["id"] for r in results} == {a, b}
    assert all(r["ok"] for r in results)


def test_bulk_launch_by_tag(app_client: TestClient, monkeypatch):
    a = app_client.post("/api/profiles", json={"name": "A", "tags": [{"tag": "grp"}]}).json()["id"]
    app_client.post("/api/profiles", json={"name": "B", "tags": [{"tag": "other"}]})
    monkeypatch.setattr(main.browser_mgr, "launch", AsyncMock())
    resp = app_client.post("/api/profiles/bulk/launch", json={"tag": "grp"})
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()["results"]] == [a]


def test_bulk_stop(app_client: TestClient, monkeypatch):
    pid = app_client.post("/api/profiles", json={"name": "A"}).json()["id"]
    mock_running = MagicMock(spec=RunningProfile, display=100, ws_port=6100, cdp_port=5100)
    main.browser_mgr.running[pid] = mock_running
    monkeypatch.setattr(main.browser_mgr, "stop", AsyncMock())
    resp = app_client.post("/api/profiles/bulk/stop", json={"ids": [pid]})
    assert resp.status_code == 200
    assert resp.json()["results"][0]["ok"] is True


def test_bulk_delete(app_client: TestClient, monkeypatch):
    pid = app_client.post("/api/profiles", json={"name": "A"}).json()["id"]
    resp = app_client.post("/api/profiles/bulk/delete", json={"ids": [pid]})
    assert resp.status_code == 200
    assert resp.json()["results"][0]["ok"] is True
    assert app_client.get(f"/api/profiles/{pid}").status_code == 404


# ── Resource limit (3d) ───────────────────────────────────────────────────────


def test_launch_resource_limit_429(app_client: TestClient, monkeypatch):
    monkeypatch.setattr("backend.browser_manager.MAX_RUNNING_PROFILES", 1)
    # occupy the one slot with a fake running profile
    blocker = app_client.post("/api/profiles", json={"name": "blocker"}).json()["id"]
    main.browser_mgr.running[blocker] = MagicMock(spec=RunningProfile, display=100,
                                                   ws_port=6100, cdp_port=5100)
    try:
        other = app_client.post("/api/profiles", json={"name": "other"}).json()["id"]
        resp = app_client.post(f"/api/profiles/{other}/launch")
        assert resp.status_code == 429
        assert "Max running" in resp.json()["detail"]
    finally:
        main.browser_mgr.running.pop(blocker, None)


def test_status_reports_max_running(app_client: TestClient):
    resp = app_client.get("/api/status")
    assert resp.status_code == 200
    assert "max_running" in resp.json()


# ── Proxy test + locations (2a/2b) ────────────────────────────────────────────


def test_proxy_locations(app_client: TestClient):
    resp = app_client.get("/api/proxy-locations")
    assert resp.status_code == 200
    assert "ipvanish" in resp.json()


def test_proxy_credential_test(app_client: TestClient, monkeypatch):
    cred_id = app_client.post("/api/proxy-credentials", json={
        "name": "c", "scheme": "socks5", "host": "h.example", "port": 1080,
        "username": "u", "password": "p",
    }).json()["id"]
    fake = {"ok": True, "exit_ip": "1.2.3.4", "country": "US",
            "timezone": "America/New_York", "latency_ms": 10, "error": None}
    monkeypatch.setattr(main.proxy_health, "test_proxy", AsyncMock(return_value=fake))
    resp = app_client.post(f"/api/proxy-credentials/{cred_id}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["exit_ip"] == "1.2.3.4"
    # last_status persisted
    cred = app_client.get(f"/api/proxy-credentials/{cred_id}").json()
    assert cred["last_status"] == "ok"
    assert cred["last_exit_ip"] == "1.2.3.4"


# ── Providers (2b) ─────────────────────────────────────────────────────────────


def test_provider_crud(app_client: TestClient):
    pid = app_client.post("/api/proxy-providers", json={
        "name": "ipvanish", "type": "ipvanish", "scheme": "socks5", "port": 1080,
        "username": "u", "password": "p",
    }).json()["id"]
    assert app_client.get("/api/proxy-locations").status_code == 200
    assert app_client.get(f"/api/proxy-providers/{pid}").status_code == 200
    resp = app_client.put(f"/api/proxy-providers/{pid}", json={"name": "IPV"})
    assert resp.json()["name"] == "IPV"
    # credential referencing provider blocks delete
    app_client.post("/api/proxy-credentials", json={
        "name": "nyc", "provider_id": pid, "provider_location": "us-nyc",
    })
    del_resp = app_client.delete(f"/api/proxy-providers/{pid}")
    assert del_resp.status_code == 409


# ── Groups (2d) ───────────────────────────────────────────────────────────────


def test_group_members(app_client: TestClient):
    gid = app_client.post("/api/proxy-groups", json={"name": "g", "rotation_mode": "round_robin"}).json()["id"]
    cred_id = app_client.post("/api/proxy-credentials", json={
        "name": "c", "host": "h.example", "port": 1080, "username": "u", "password": "p",
    }).json()["id"]
    # add member
    resp = app_client.post(f"/api/proxy-groups/{gid}/members/{cred_id}")
    assert resp.status_code == 200
    assert resp.json()["member_count"] == 1
    # replace members (empty)
    resp = app_client.put(f"/api/proxy-groups/{gid}/members", json={"credential_ids": []})
    assert resp.json()["member_count"] == 0
    assert app_client.delete(f"/api/proxy-groups/{gid}").status_code == 200


# ── Local CDP exemption (4c) ──────────────────────────────────────────────────


def test_local_cdp_exempt_when_enabled_and_loopback(app_client: TestClient, monkeypatch):
    # Create while auth is still disabled, then turn it on.
    pid = app_client.post("/api/profiles", json={"name": "P"}).json()["id"]
    monkeypatch.setattr(main, "AUTH_TOKEN", "secret")
    monkeypatch.setattr(main, "ALLOW_LOCAL_CDP", True)
    monkeypatch.setattr(main, "_scope_is_loopback", lambda scope: True)
    # loopback + ALLOW_LOCAL_CDP -> auth bypassed; not running -> 404 from the route
    resp = app_client.get(f"/api/profiles/{pid}/cdp/local/json/version")
    assert resp.status_code == 404  # reached the route, profile not running
    assert resp.json()["detail"] == "Profile not running"


def test_local_cdp_blocked_when_disabled(app_client: TestClient, monkeypatch):
    pid = app_client.post("/api/profiles", json={"name": "P"}).json()["id"]
    monkeypatch.setattr(main, "AUTH_TOKEN", "secret")
    monkeypatch.setattr(main, "ALLOW_LOCAL_CDP", False)
    # ALLOW_LOCAL_CDP off -> exemption never considered -> auth applies -> 401
    resp = app_client.get(f"/api/profiles/{pid}/cdp/local/json/version")
    assert resp.status_code == 401


# ── Loopback detection (4c, unit-level) ───────────────────────────────────────


def test_host_is_loopback():
    assert main._host_is_loopback("127.0.0.1:8080") is True
    assert main._host_is_loopback("localhost") is True
    assert main._host_is_loopback("[::1]:8080") is True
    assert main._host_is_loopback("clk.mrme.tech") is False


def test_scope_is_loopback_client_ip():
    assert main._scope_is_loopback({"client": ("127.0.0.1", 0), "headers": []}) is True
    assert main._scope_is_loopback({"client": ("203.0.113.5", 0), "headers": []}) is False


def test_scope_is_loopback_host_header():
    # No client IP, but loopback Host header -> still loopback
    assert main._scope_is_loopback({
        "client": None,
        "headers": [(b"host", b"127.0.0.1:8080")],
    }) is True
    # Public host (e.g. CF tunnel) -> not loopback
    assert main._scope_is_loopback({
        "client": None,
        "headers": [(b"host", b"clk.mrme.tech")],
    }) is False


def test_is_local_cdp_path():
    assert main._is_local_cdp_path("/api/profiles/x/cdp/local/json/version") is True
    assert main._is_local_cdp_path("/api/profiles/x/cdp/local") is True
    assert main._is_local_cdp_path("/api/profiles/x/cdp/json/version") is False
    assert main._is_local_cdp_path("/api/profiles/x/launch") is False

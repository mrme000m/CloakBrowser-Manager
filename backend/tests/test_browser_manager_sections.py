"""Tests for browser_manager proxy-group resolution and VNC port allocation."""

from __future__ import annotations

import asyncio
import socket

from backend import database as db
from backend.browser_manager import _resolve_proxy_url
from backend.vnc_manager import VNCManager


def _cred(name: str) -> str:
    return db.create_proxy_credential(name=name, scheme="socks5", host=f"{name}.example",
                                      port=1080, username="u", password="p")["id"]


def _profile_with_group(group_id: str) -> dict:
    pid = db.create_profile(name="p", proxy_group_id=group_id)["id"]
    return db.get_profile(pid)


# ── _resolve_proxy_url: explicit + credential (unchanged behavior) ───────────


def test_resolve_explicit_proxy(tmp_db):
    p = {"proxy": "socks5://h:1080"}
    assert _resolve_proxy_url(p) == "socks5://h:1080"


def test_resolve_credential(tmp_db):
    cred_id = db.create_proxy_credential(name="c", scheme="socks5", host="h.example",
                                         port=1080, username="u", password="p")["id"]
    p = db.get_profile(db.create_profile(name="p", proxy_credential_id=cred_id)["id"])
    assert _resolve_proxy_url(p) == "socks5://u:p@h.example:1080"


# ── group resolution modes ───────────────────────────────────────────────────


def test_resolve_group_round_robin_cycles(tmp_db):
    g = db.create_proxy_group(name="g", rotation_mode="round_robin")
    a, b = _cred("a"), _cred("b")
    db.set_group_members(g["id"], [a, b])
    p = _profile_with_group(g["id"])
    url1 = _resolve_proxy_url(p)
    url2 = _resolve_proxy_url(p)
    url3 = _resolve_proxy_url(p)
    assert "a.example" in url1
    assert "b.example" in url2
    assert "a.example" in url3  # wraps around


def test_resolve_group_sticky_persists_assignment(tmp_db):
    g = db.create_proxy_group(name="g", rotation_mode="sticky_session")
    a, b = _cred("a"), _cred("b")
    db.set_group_members(g["id"], [a, b])
    pid = db.create_profile(name="p", proxy_group_id=g["id"])["id"]
    p = db.get_profile(pid)
    url1 = _resolve_proxy_url(p)
    url2 = _resolve_proxy_url(p)
    assert url1 == url2  # same member both times
    assignment = db.get_profile(pid)["proxy_assignment"]
    assert assignment in (a, b)
    assert (assignment_host := assignment) and (assignment_host in (a, b))


def test_resolve_group_random_returns_member(tmp_db):
    g = db.create_proxy_group(name="g", rotation_mode="random")
    a, b = _cred("a"), _cred("b")
    db.set_group_members(g["id"], [a, b])
    p = _profile_with_group(g["id"])
    url = _resolve_proxy_url(p)
    assert "a.example" in url or "b.example" in url


def test_resolve_group_empty_returns_none(tmp_db):
    g = db.create_proxy_group(name="g", rotation_mode="round_robin")
    p = _profile_with_group(g["id"])
    assert _resolve_proxy_url(p) is None


# ── VNC port allocation (Section 3e) ─────────────────────────────────────────


def test_vnc_allocate_returns_free_port():
    mgr = VNCManager()
    display, ws_port = asyncio.run(mgr.allocate())
    assert display == 100
    # returned port is currently free (bind-check released it)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", ws_port))  # should not raise


def test_vnc_allocate_skips_occupied_ws_port():
    mgr = VNCManager()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("127.0.0.1", 6100))  # BASE_WS_PORT
        blocker.listen(1)
        display, ws_port = asyncio.run(mgr.allocate())
    assert display == 100
    assert ws_port == 6101  # skipped the occupied 6100


def test_vnc_allocate_advances_display():
    mgr = VNCManager()
    d1, _ = asyncio.run(mgr.allocate())
    d2, _ = asyncio.run(mgr.allocate())
    assert d1 == 100
    assert d2 == 101

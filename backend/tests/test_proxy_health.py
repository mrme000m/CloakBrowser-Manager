"""Tests for proxy_health: location catalog, provider resolution, materialize, test_proxy."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend import proxy_health


# ── Location catalog ─────────────────────────────────────────────────────────


def test_ipvanish_locations_has_entries():
    assert "us-nyc" in proxy_health.IPVANISH_LOCATIONS
    assert proxy_health.IPVANISH_LOCATIONS["us-nyc"]["host"] == "nyc.socks.ipvanish.com"
    assert proxy_health.PROXY_LOCATIONS["ipvanish"] is proxy_health.IPVANISH_LOCATIONS


# ── resolve_provider_endpoint ────────────────────────────────────────────────


def test_resolve_ipvanish_valid():
    provider = {"type": "ipvanish", "scheme": "socks5", "port": 1080,
                "username": "u", "password": "p"}
    ep = proxy_health.resolve_provider_endpoint(provider, "us-nyc")
    assert ep is not None
    assert ep["host"] == "nyc.socks.ipvanish.com"
    assert ep["scheme"] == "socks5"
    assert ep["port"] == 1080
    assert ep["username"] == "u"
    assert ep["password"] == "p"


def test_resolve_ipvanish_unknown_location():
    provider = {"type": "ipvanish", "scheme": "socks5", "port": 1080}
    assert proxy_health.resolve_provider_endpoint(provider, "zzz") is None


def test_resolve_custom_host_template_with_port():
    provider = {"type": "custom", "scheme": "http", "port": 1080,
                "host_template": "brd.superproxy.io:22225"}
    ep = proxy_health.resolve_provider_endpoint(provider, None)
    assert ep is not None
    assert ep["host"] == "brd.superproxy.io"
    assert ep["port"] == 22225


def test_resolve_custom_no_host():
    provider = {"type": "custom", "scheme": "socks5", "port": 1080, "host_template": ""}
    assert proxy_health.resolve_provider_endpoint(provider, None) is None


# ── materialize_credential ───────────────────────────────────────────────────


def test_materialize_standalone_credential(tmp_db):
    from backend import database as db
    cred = db.create_proxy_credential(name="c", scheme="socks5", host="h.example", port=1080,
                                      username="u", password="p")
    out = proxy_health.materialize_credential(cred)
    assert out["host"] == "h.example"
    assert out["username"] == "u"
    assert proxy_health.build_proxy_url(cred) == "socks5://u:p@h.example:1080"


def test_materialize_provider_linked_credential(tmp_db):
    from backend import database as db
    provider = db.create_proxy_provider(name="ipvanish", type="ipvanish", scheme="socks5",
                                        port=1080, username="u", password="p")
    cred = db.create_proxy_credential(name="nyc", scheme="socks5", host="", port=1080,
                                      username="", password="",
                                      provider_id=provider["id"], provider_location="us-nyc")
    out = proxy_health.materialize_credential(cred)
    assert out["host"] == "nyc.socks.ipvanish.com"
    assert out["username"] == "u"
    assert out["password"] == "p"
    assert proxy_health.build_proxy_url(cred) == "socks5://u:p@nyc.socks.ipvanish.com:1080"
    # Raw build (without materialize) would be broken — empty host
    assert db.build_proxy_url_from_credential(cred) == "socks5://:1080"


# ── test_proxy (httpx mocked) ────────────────────────────────────────────────


class _Resp:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")


class _Client:
    def __init__(self, gets):
        self._gets = list(gets)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        r = self._gets.pop(0)
        if isinstance(r, Exception):
            raise r
        return _Resp(*r)


def _run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_test_proxy_ok(tmp_db):
    cred = {"scheme": "socks5", "host": "h", "port": 1080, "username": "u", "password": "p"}
    client = _Client([(200, {"ip": "1.2.3.4"}), (200, {"country_name": "US", "timezone": "America/New_York"})])
    with patch.object(proxy_health.httpx, "AsyncClient", return_value=client):
        result = _run(proxy_health.test_proxy(cred))
    assert result["ok"] is True
    assert result["exit_ip"] == "1.2.3.4"
    assert result["country"] == "US"
    assert result["timezone"] == "America/New_York"
    assert isinstance(result["latency_ms"], int)
    assert result["error"] is None


def test_test_proxy_fail(tmp_db):
    cred = {"scheme": "socks5", "host": "h", "port": 1080, "username": "u", "password": "p"}
    client = _Client([RuntimeError("boom")])
    with patch.object(proxy_health.httpx, "AsyncClient", return_value=client):
        result = _run(proxy_health.test_proxy(cred))
    assert result["ok"] is False
    assert result["exit_ip"] is None
    assert "boom" in (result["error"] or "")


def test_test_proxy_no_host():
    cred = {"scheme": "socks5", "host": "", "port": 1080}
    result = _run(proxy_health.test_proxy(cred))
    assert result["ok"] is False
    assert "no host" in (result["error"] or "")

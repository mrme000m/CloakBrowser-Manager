"""Proxy health checking and provider/location resolution.

Hosts the IPVanish location catalog (and a provider abstraction designed so
Bright Data / Smartproxy can plug in later), credential materialization for
provider-linked credentials, and the async `test_proxy` that connects through
a proxy to an IP-echo service and reports exit IP / country / timezone / latency.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from . import database as db

logger = logging.getLogger("cloakbrowser.manager.proxy_health")


# IPVanish SOCKS5 location codes → {host, city, country}.
# Ported from cloak-ob2-lab/create-cloak-profile-for-bdg.py and enriched with
# city/country display names.
IPVANISH_LOCATIONS: dict[str, dict[str, str]] = {
    "au":     {"host": "mel.socks.ipvanish.com", "city": "Melbourne", "country": "Australia"},
    "ca":     {"host": "tor.socks.ipvanish.com", "city": "Toronto", "country": "Canada"},
    "fr":     {"host": "par.socks.ipvanish.com", "city": "Paris", "country": "France"},
    "de":     {"host": "fra.socks.ipvanish.com", "city": "Frankfurt", "country": "Germany"},
    "it":     {"host": "lin.socks.ipvanish.com", "city": "Lin", "country": "Italy"},
    "nl":     {"host": "ams.socks.ipvanish.com", "city": "Amsterdam", "country": "Netherlands"},
    "pl":     {"host": "waw.socks.ipvanish.com", "city": "Warsaw", "country": "Poland"},
    "es":     {"host": "mad.socks.ipvanish.com", "city": "Madrid", "country": "Spain"},
    "uk":     {"host": "lon.socks.ipvanish.com", "city": "London", "country": "United Kingdom"},
    "gb":     {"host": "lon.socks.ipvanish.com", "city": "London", "country": "United Kingdom"},
    "us":     {"host": "atl.socks.ipvanish.com", "city": "Atlanta", "country": "United States"},
    "us-atl": {"host": "atl.socks.ipvanish.com", "city": "Atlanta", "country": "United States"},
    "us-chi": {"host": "chi.socks.ipvanish.com", "city": "Chicago", "country": "United States"},
    "us-cvg": {"host": "cvg.socks.ipvanish.com", "city": "Covington", "country": "United States"},
    "us-dal": {"host": "dal.socks.ipvanish.com", "city": "Dallas", "country": "United States"},
    "us-iad": {"host": "iad.socks.ipvanish.com", "city": "Washington", "country": "United States"},
    "us-lax": {"host": "lax.socks.ipvanish.com", "city": "Los Angeles", "country": "United States"},
    "us-mia": {"host": "mia.socks.ipvanish.com", "city": "Miami", "country": "United States"},
    "us-nyc": {"host": "nyc.socks.ipvanish.com", "city": "New York", "country": "United States"},
    "us-phx": {"host": "phx.socks.ipvanish.com", "city": "Phoenix", "country": "United States"},
    "us-sjc": {"host": "sjc.socks.ipvanish.com", "city": "San Jose", "country": "United States"},
}

# Structured for the frontend location picker. New providers plug in here.
PROXY_LOCATIONS: dict[str, dict[str, dict[str, str]]] = {
    "ipvanish": IPVANISH_LOCATIONS,
}


def get_location_meta(provider_type: str, location: str | None) -> dict[str, str] | None:
    catalog = PROXY_LOCATIONS.get(provider_type)
    if not catalog or not location:
        return None
    return catalog.get((location or "").lower().strip())


def resolve_provider_endpoint(provider: dict[str, Any], location: str | None) -> dict[str, Any] | None:
    """Return {scheme, host, port, username, password} for a provider+location.

    Returns None if the location is unknown or no host can be derived.
    """
    ptype = provider.get("type", "custom")
    base = {
        "scheme": provider.get("scheme", "socks5"),
        "port": int(provider.get("port", 1080)),
        "username": provider.get("username", ""),
        "password": provider.get("password", ""),
    }
    if ptype == "ipvanish":
        meta = get_location_meta("ipvanish", location)
        if not meta:
            return None
        return {**base, "host": meta["host"]}
    # brightdata / smartproxy / custom: host_template may be "host:port" or "host"
    host_template = provider.get("host_template", "") or ""
    host = host_template
    port = base["port"]
    if ":" in host_template:
        h, _, p = host_template.rpartition(":")
        if h:
            host = h
        if p.isdigit():
            port = int(p)
    if not host:
        return None
    return {**base, "host": host, "port": port}


def materialize_credential(cred: dict[str, Any]) -> dict[str, Any]:
    """Return a credential dict with host/user/pass/scheme/port filled in.

    For provider-linked credentials (provider_id set), resolve the endpoint
    from the provider account + location so the proxy URL can be built. For
    standalone credentials, return a shallow copy unchanged.
    """
    provider_id = cred.get("provider_id")
    if not provider_id:
        return dict(cred)
    provider = db.get_proxy_provider(provider_id)
    if not provider:
        return dict(cred)
    endpoint = resolve_provider_endpoint(provider, cred.get("provider_location"))
    if not endpoint:
        return dict(cred)
    out = dict(cred)
    out["scheme"] = endpoint.get("scheme", cred.get("scheme", "socks5"))
    out["host"] = endpoint.get("host", cred.get("host", ""))
    out["port"] = int(endpoint.get("port", cred.get("port", 1080)))
    out["username"] = endpoint.get("username", cred.get("username", ""))
    out["password"] = endpoint.get("password", cred.get("password", ""))
    return out


def build_proxy_url(cred: dict[str, Any]) -> str:
    """Materialize (if provider-linked) then build the proxy URL."""
    return db.build_proxy_url_from_credential(materialize_credential(cred))


def _empty_result(error: str) -> dict[str, Any]:
    return {"ok": False, "exit_ip": None, "country": None,
            "timezone": None, "latency_ms": None, "error": error}


async def test_proxy(cred: dict[str, Any]) -> dict[str, Any]:
    """Connect through a proxy to an IP-echo service and report diagnostics.

    Returns {ok, exit_ip, country, timezone, latency_ms, error}. All failures
    are caught and reported as ok=False so callers can persist last_status.
    """
    try:
        materialized = materialize_credential(cred)
    except Exception as exc:  # pragma: no cover - defensive
        return _empty_result(f"resolve: {exc}")
    if not materialized.get("host"):
        return _empty_result("no host configured")
    try:
        proxy_url = db.build_proxy_url_from_credential(materialized)
    except Exception as exc:
        return _empty_result(f"build url: {exc}")

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=15.0) as client:
            resp = await client.get("https://api.ipify.org?format=json")
            resp.raise_for_status()
            exit_ip = (resp.json() or {}).get("ip")
    except Exception as exc:
        return _empty_result(f"{type(exc).__name__}: {exc}")
    latency_ms = int((time.perf_counter() - start) * 1000)

    country: str | None = None
    timezone: str | None = None
    if exit_ip:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                geo = await client.get(f"https://ipapi.co/{exit_ip}/json/")
                if geo.status_code == 200:
                    g = geo.json() or {}
                    country = g.get("country_name") or g.get("country")
                    timezone = g.get("timezone")
        except Exception as exc:
            logger.debug("geo lookup failed for %s: %s", exit_ip, exc)

    return {"ok": True, "exit_ip": exit_ip, "country": country,
            "timezone": timezone, "latency_ms": latency_ms, "error": None}

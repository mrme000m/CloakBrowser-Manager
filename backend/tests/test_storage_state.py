"""Tests for storage_state application at launch.

Covers the pure/async helpers added to browser_manager:
``_storage_state_origin_seeds`` (extracts a per-origin localStorage mapping),
``_seed_local_storage`` (seeds localStorage via a route-fulfilled page so it
persists to disk across sessions), and ``_apply_storage_state`` (cookies via
``add_cookies`` + localStorage via the route-fulfilled page). The launch
integration is a thin call between the clipboard-init block and the
RunningProfile construction; these tests pin the helper contract.
"""

from __future__ import annotations

import pytest

from backend.browser_manager import (
    _apply_storage_state,
    _seed_local_storage,
    _storage_state_origin_seeds,
)


# ── _storage_state_origin_seeds ───────────────────────────────────────────────


def test_origin_seeds_empty():
    assert _storage_state_origin_seeds([]) == {}
    assert _storage_state_origin_seeds(None) == {}


def test_origin_seeds_includes_origin_and_items():
    origins = [
        {"origin": "https://example.com", "localStorage": [{"name": "token", "value": "abc"}]},
    ]
    seeds = _storage_state_origin_seeds(origins)
    assert seeds == {"https://example.com": [{"name": "token", "value": "abc"}]}


def test_origin_seeds_skips_malformed():
    origins = [
        "not-a-dict",
        {"missing_origin": True},
        {"origin": "https://ok.com", "localStorage": "not-a-list"},
        {"origin": 123, "localStorage": []},
        {"origin": "https://empty.com", "localStorage": []},
        {"origin": "https://good.com", "localStorage": [{"name": "k", "value": "v"}]},
    ]
    seeds = _storage_state_origin_seeds(origins)
    assert list(seeds.keys()) == ["https://good.com"]


def test_origin_seeds_coerces_non_string_values():
    origins = [{"origin": "https://n.com", "localStorage": [{"name": "n", "value": 7}]}]
    seeds = _storage_state_origin_seeds(origins)
    assert seeds == {"https://n.com": [{"name": "n", "value": "7"}]}


# ── fakes ─────────────────────────────────────────────────────────────────────


class FakePage:
    """Minimal stand-in for a Playwright Page (route/goto/evaluate/unroute/close)."""

    def __init__(self, *, goto_raises: bool = False):
        self.routes: list[str] = []
        self.gotos: list[str] = []
        self.evals: list = []  # list of (script, arg)
        self.unroutes: list[str] = []
        self.closed = False
        self._goto_raises = goto_raises

    async def route(self, pattern, handler):
        self.routes.append(pattern)
        self._handler = handler

    async def goto(self, url, **kwargs):
        if self._goto_raises:
            raise RuntimeError("goto boom")
        self.gotos.append(url)

    async def evaluate(self, script, arg=None):
        self.evals.append((script, arg))

    async def unroute(self, pattern):
        self.unroutes.append(pattern)

    async def close(self):
        self.closed = True


class FakeContext:
    """Minimal stand-in for a Playwright BrowserContext."""

    def __init__(self, *, add_cookies_raises: bool = False, page: FakePage | None = None):
        self.add_cookies_calls: list = []
        self.new_page_calls = 0
        self._add_cookies_raises = add_cookies_raises
        self._page = page

    async def add_cookies(self, cookies):
        if self._add_cookies_raises:
            raise RuntimeError("boom")
        self.add_cookies_calls.append(cookies)

    async def new_page(self):
        self.new_page_calls += 1
        if self._page is None:
            self._page = FakePage()
        return self._page


# ── _seed_local_storage ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_local_storage_navigates_each_origin():
    page = FakePage()
    ctx = FakeContext(page=page)
    seeds = {
        "https://a.com": [{"name": "k", "value": "v"}],
        "https://b.com": [{"name": "x", "value": "y"}],
    }
    await _seed_local_storage(ctx, seeds)
    assert ctx.new_page_calls == 1
    assert page.routes == ["**/*"]
    assert page.gotos == ["https://a.com", "https://b.com"]
    assert len(page.evals) == 2
    assert page.evals[0][1] == [{"name": "k", "value": "v"}]
    assert page.evals[1][1] == [{"name": "x", "value": "y"}]
    assert page.unroutes == ["**/*"]
    assert page.closed is True


@pytest.mark.asyncio
async def test_seed_local_storage_per_origin_failure_keeps_going():
    page = FakePage(goto_raises=True)
    ctx = FakeContext(page=page)
    seeds = {
        "https://bad.com": [{"name": "k", "value": "v"}],
        "https://good.com": [{"name": "x", "value": "y"}],
    }
    # goto raises for every origin — seed logs a warning per origin but must not
    # raise, and must still unroute + close the page.
    await _seed_local_storage(ctx, seeds)
    assert page.unroutes == ["**/*"]
    assert page.closed is True


# ── _apply_storage_state ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_storage_state_adds_cookies_and_seeds_local_storage():
    ctx = FakeContext()
    state = {
        "cookies": [{"name": "s", "value": "v", "domain": "example.com", "path": "/"}],
        "origins": [{"origin": "https://example.com", "localStorage": [{"name": "k", "value": "v"}]}],
    }
    warnings = await _apply_storage_state(ctx, state)
    assert warnings == []
    assert ctx.add_cookies_calls == [state["cookies"]]
    assert ctx.new_page_calls == 1
    page = ctx._page
    assert page.gotos == ["https://example.com"]
    assert page.evals[0][1] == [{"name": "k", "value": "v"}]
    assert page.closed is True


@pytest.mark.asyncio
async def test_apply_storage_state_noop_on_non_dict():
    ctx = FakeContext()
    assert await _apply_storage_state(ctx, None) == []
    assert await _apply_storage_state(ctx, "not-a-dict") == []
    assert ctx.add_cookies_calls == []
    assert ctx.new_page_calls == 0


@pytest.mark.asyncio
async def test_apply_storage_state_only_cookies():
    ctx = FakeContext()
    warnings = await _apply_storage_state(ctx, {"cookies": [{"name": "s", "value": "v"}]})
    assert warnings == []
    assert len(ctx.add_cookies_calls) == 1
    assert ctx.new_page_calls == 0  # no origins -> no page


@pytest.mark.asyncio
async def test_apply_storage_state_only_origins():
    ctx = FakeContext()
    warnings = await _apply_storage_state(
        ctx, {"origins": [{"origin": "https://x.com", "localStorage": [{"name": "k", "value": "v"}]}]}
    )
    assert warnings == []
    assert ctx.add_cookies_calls == []  # no cookies -> no add_cookies
    assert ctx.new_page_calls == 1
    assert ctx._page.gotos == ["https://x.com"]


@pytest.mark.asyncio
async def test_apply_storage_state_warns_on_failure():
    ctx = FakeContext(add_cookies_raises=True)
    warnings = await _apply_storage_state(
        ctx, {"cookies": [{"name": "s", "value": "v"}], "origins": []}
    )
    assert len(warnings) == 1
    assert "could not be applied" in warnings[0]

"""CloakBrowser Manager — FastAPI application.

Serves the React dashboard (static files) and provides a REST API
for browser profile management with live VNC viewing.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
import random
import shutil
import struct
from contextlib import asynccontextmanager
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import starlette.requests
from starlette.types import ASGIApp, Receive, Scope, Send

from . import database as db
from . import proxy_health
from .browser_manager import BrowserManager
from .models import (
    BulkIdsRequest,
    BulkResultItem,
    BulkResultResponse,
    ClipboardRequest,
    CloneRequest,
    GroupMembersUpdate,
    LaunchResponse,
    LoginRequest,
    ProfileCreate,
    ProfileResponse,
    ProfileStatusResponse,
    ProfileUpdate,
    ProxyCredentialCreate,
    ProxyCredentialResponse,
    ProxyCredentialUpdate,
    ProxyGroupCreate,
    ProxyGroupMemberResponse,
    ProxyGroupResponse,
    ProxyGroupUpdate,
    ProxyProviderCreate,
    ProxyProviderResponse,
    ProxyProviderUpdate,
    ProxyTestResult,
    StatusResponse,
    TagResponse,
)

logger = logging.getLogger("cloakbrowser.manager")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# Optional authentication via AUTH_TOKEN env var.
# If not set, all routes are open (local dev). If set, all /api/* routes
# (except /api/auth/* and /api/status) require Bearer token or cookie.
AUTH_TOKEN: str | None = os.environ.get("AUTH_TOKEN") or None

# Section 4c: allow an unauthenticated, localhost-only page-level CDP path so
# local tools (e.g. bdg) can connect without an auth-injecting bridge. Only
# requests from loopback (client IP or Host header) are exempt, so it stays
# safe behind a CF tunnel (the tunnel's Host is the public hostname).
ALLOW_LOCAL_CDP: bool = os.environ.get("ALLOW_LOCAL_CDP", "").lower() in ("1", "true", "yes", "on")

# Section 3d: hard cap on concurrent running browsers (0 = unlimited).
MAX_RUNNING_PROFILES: int = int(os.environ.get("MAX_RUNNING_PROFILES", "0") or 0)

# Section 2c: background proxy health-check interval in seconds (0 = off).
PROXY_HEALTH_CHECK_INTERVAL: int = int(os.environ.get("PROXY_HEALTH_CHECK_INTERVAL", "0") or 0)

# Section 4b: track active CDP WebSocket clients per profile (browser + page).
cdp_clients: dict[str, int] = {}


def _cdp_clients_inc(profile_id: str) -> None:
    cdp_clients[profile_id] = cdp_clients.get(profile_id, 0) + 1


def _cdp_clients_dec(profile_id: str) -> None:
    cdp_clients[profile_id] = max(0, cdp_clients.get(profile_id, 0) - 1)


# Loopback hostnames for the local-CDP exemption.
_LOOPBACK_HOSTS = {"127.0.0.1", "[::1]", "::1", "localhost", "ip6-localhost", "ip6-loopback"}


def _host_is_loopback(host_header: str) -> bool:
    h = host_header.strip().lower()
    if h.startswith("["):
        h = h.split("]", 1)[0] + "]"
    else:
        h = h.split(":", 1)[0]
    return h in _LOOPBACK_HOSTS


def _scope_is_loopback(scope: Scope) -> bool:
    """True if the request originated from loopback (client IP or Host header)."""
    client = scope.get("client")
    if client and client[0] in ("127.0.0.1", "::1"):
        return True
    for key, val in scope.get("headers", []):
        if key == b"host" and _host_is_loopback(val.decode("latin-1")):
            return True
    return False


def _is_local_cdp_path(path: str) -> bool:
    return path.startswith("/api/profiles/") and "/cdp/local" in path

# Paths that bypass authentication even when AUTH_TOKEN is set
_AUTH_EXEMPT = frozenset({"/api/auth/status", "/api/auth/login", "/api/status"})


def _check_auth(scope: Scope) -> bool:
    """Check if the request has a valid auth token (header or cookie)."""
    # Check Authorization: Bearer <token> header
    for key, val in scope.get("headers", []):
        if key == b"authorization":
            auth_value = val.decode()
            if auth_value.startswith("Bearer "):
                token = auth_value[7:]
                if token and hmac.compare_digest(token, AUTH_TOKEN):
                    return True
            break

    # Check auth_token cookie
    for key, val in scope.get("headers", []):
        if key == b"cookie":
            cookies = SimpleCookie()
            cookies.load(val.decode())
            if "auth_token" in cookies:
                cookie_val = cookies["auth_token"].value
                if cookie_val and hmac.compare_digest(cookie_val, AUTH_TOKEN):
                    return True
            break

    return False


def _is_https(request: Request) -> bool:
    """Check if the original client connection was HTTPS (via reverse proxy header)."""
    proto = request.headers.get("x-forwarded-proto", "")
    return "https" in proto


async def _check_websocket_origin(websocket: WebSocket) -> bool:
    """Reject cross-origin WebSocket connections (CSWSH protection).

    Browsers always send an Origin header on WebSocket upgrades.
    Non-browser clients (Playwright, curl) typically don't — those are allowed.
    If Origin is present, its host must match the request Host header.
    """
    origin = None
    host = None
    for key, val in websocket.scope.get("headers", []):
        if key == b"origin":
            origin = val.decode("latin-1")
        elif key == b"host":
            host = val.decode("latin-1")

    # No Origin header → non-browser client (Playwright, Puppeteer) → allow
    if not origin:
        return True

    # Parse origin to extract host:port
    try:
        parsed = urlparse(origin)
        origin_host = parsed.hostname or ""
        origin_port = parsed.port
    except ValueError:
        logger.warning("WebSocket origin malformed: %s", origin)
        await websocket.close(code=4403, reason="Origin not allowed")
        return False
    # Build origin netloc (host:port or just host if default port)
    if origin_port and origin_port not in (80, 443):
        origin_netloc = f"{origin_host}:{origin_port}"
    else:
        origin_netloc = origin_host

    if not host:
        return True  # no Host header to compare against

    # Strip default port from Host too (some proxies send "example.com:443")
    host_normalized = host
    if host.endswith(":80") or host.endswith(":443"):
        host_normalized = host.rsplit(":", 1)[0]

    if origin_netloc == host_normalized:
        return True

    logger.warning("WebSocket origin mismatch: origin=%s host=%s", origin, host)
    await websocket.close(code=4403, reason="Origin not allowed")
    return False


class AuthMiddleware:
    """Raw ASGI middleware for optional token auth.

    Uses raw ASGI instead of BaseHTTPMiddleware because the latter
    breaks WebSocket routes (wraps request body, preventing WS upgrade).
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Pass through if auth disabled, or non-HTTP/WS scope (e.g. lifespan)
        if not AUTH_TOKEN or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope["path"]

        # Skip auth for exempt endpoints and non-API paths (static frontend)
        if path in _AUTH_EXEMPT or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Section 4c: loopback-only, opt-in local CDP bypass (for bdg etc.)
        if ALLOW_LOCAL_CDP and _is_local_cdp_path(path) and _scope_is_loopback(scope):
            await self.app(scope, receive, send)
            return

        if _check_auth(scope):
            await self.app(scope, receive, send)
            return

        # Reject — unauthenticated
        if scope["type"] == "websocket":
            # ASGI requires receiving websocket.connect before sending close
            await receive()
            await send({"type": "websocket.close", "code": 4401, "reason": "Unauthorized"})
        else:
            response = JSONResponse({"detail": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _cred_to_response(cred: dict) -> ProxyCredentialResponse:
    """Build a ProxyCredentialResponse, materializing provider-linked creds."""
    materialized = proxy_health.materialize_credential(cred)
    return ProxyCredentialResponse(
        id=cred["id"],
        name=cred["name"],
        scheme=materialized.get("scheme", cred.get("scheme", "socks5")),
        host=materialized.get("host", cred.get("host", "")),
        port=materialized.get("port", cred.get("port", 1080)),
        username=materialized.get("username", cred.get("username", "")),
        has_password=bool(materialized.get("password")),
        proxy_url=db.build_proxy_url_from_credential(materialized),
        provider_id=cred.get("provider_id"),
        provider_location=cred.get("provider_location"),
        last_status=cred.get("last_status"),
        last_exit_ip=cred.get("last_exit_ip"),
        last_country=cred.get("last_country"),
        last_checked_at=cred.get("last_checked_at"),
        created_at=cred["created_at"],
        updated_at=cred["updated_at"],
    )


def _resolve_proxy_credential(profile: dict) -> ProxyCredentialResponse | None:
    """Resolve proxy_credential_id on a profile dict into a response model."""
    cred_id = profile.get("proxy_credential_id")
    if not cred_id:
        return None
    cred = db.get_proxy_credential(cred_id)
    if not cred:
        return None
    return _cred_to_response(cred)


def _resolve_proxy_group(profile: dict) -> ProxyGroupResponse | None:
    """Resolve proxy_group_id on a profile dict into a response model with members."""
    group_id = profile.get("proxy_group_id")
    if not group_id:
        return None
    group = db.get_proxy_group(group_id)
    if not group:
        return None
    members = db.list_group_members(group_id)
    return ProxyGroupResponse(
        id=group["id"],
        name=group["name"],
        rotation_mode=group.get("rotation_mode", "round_robin"),
        member_count=len(members),
        members=[ProxyGroupMemberResponse(**m) for m in members],
        created_at=group["created_at"],
        updated_at=group["updated_at"],
    )


def _provider_to_response(p: dict) -> ProxyProviderResponse:
    return ProxyProviderResponse(
        id=p["id"],
        name=p["name"],
        type=p.get("type", "custom"),
        scheme=p.get("scheme", "socks5"),
        host_template=p.get("host_template", "") or "",
        port=p.get("port", 1080),
        username=p.get("username", ""),
        has_password=bool(p.get("password")),
        options=p.get("options") or {},
        created_at=p["created_at"],
        updated_at=p["updated_at"],
    )


def _group_to_response(group_id: str) -> ProxyGroupResponse | None:
    group = db.get_proxy_group(group_id)
    if not group:
        return None
    members = db.list_group_members(group_id)
    return ProxyGroupResponse(
        id=group["id"],
        name=group["name"],
        rotation_mode=group.get("rotation_mode", "round_robin"),
        member_count=len(members),
        members=[ProxyGroupMemberResponse(**m) for m in members],
        created_at=group["created_at"],
        updated_at=group["updated_at"],
    )


def _cdp_endpoint(profile_id: str, scope: Scope) -> str:
    """Build the full WS CDP endpoint URL from the request's Host header."""
    host = "localhost:8080"
    for key, val in scope.get("headers", []):
        if key == b"host":
            host = val.decode("latin-1")
            break
    ws_scheme = "ws"
    for key, val in scope.get("headers", []):
        if key == b"x-forwarded-proto" and b"https" in val.lower():
            ws_scheme = "wss"
            break
    return f"{ws_scheme}://{host}/api/profiles/{profile_id}/cdp"


def _enrich_profile(profile: dict, scope: Scope) -> ProfileResponse:
    """Add runtime fields (status, proxy_credential, proxy_group, cdp_endpoint)."""
    profile_id = profile["id"]
    status = browser_mgr.get_status(profile_id)
    proxy_cred = _resolve_proxy_credential(profile)
    proxy_group = _resolve_proxy_group(profile)
    profile_tags = profile.get("tags", [])
    # Filter dict-only/internal keys to avoid duplicate/unexpected kwargs.
    profile_fields = {
        k: v for k, v in profile.items()
        if k not in ("tags", "proxy_assignment")
    }
    return ProfileResponse(
        **profile_fields,
        status=status["status"],
        vnc_ws_port=status["vnc_ws_port"],
        cdp_url=status["cdp_url"],
        cdp_endpoint=_cdp_endpoint(profile_id, scope),
        proxy_credential=proxy_cred.model_dump() if proxy_cred else None,
        proxy_group=proxy_group.model_dump() if proxy_group else None,
        tags=[TagResponse(**t) for t in profile_tags],
        resources=status.get("resources"),
    )


# Singleton browser manager
browser_mgr = BrowserManager()

# Frontend build directory (React production build)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


# ---------------------------------------------------------------------------
# RFB server message translator — KasmVNC BinaryClipboard → standard RFB
# ---------------------------------------------------------------------------


def _parse_kasmvnc_clipboard(data: bytes) -> str | None:
    """Extract text/plain from KasmVNC BinaryClipboard (type 180).

    Format: type(1) + action(1) + flags(4) + entries...
    Each entry: mime_len(u8) + mime(N) + data_len(u32 BE) + data(M)
    """
    if len(data) < 7:
        return None
    offset = 6  # skip type(1) + action(1) + flags(4)
    while offset < len(data):
        if offset + 1 > len(data):
            break
        mime_len = data[offset]
        offset += 1
        if offset + mime_len > len(data):
            break
        mime_type = data[offset:offset + mime_len]
        offset += mime_len
        if offset + 4 > len(data):
            break
        data_len = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        if mime_type == b"text/plain":
            end = min(offset + data_len, len(data))
            return data[offset:end].decode("utf-8", errors="replace")
        offset += data_len
    return None


def _build_server_cut_text(text: str) -> bytes:
    """Build standard RFB ServerCutText (type 3) message.

    RFB spec mandates Latin-1 encoding for ServerCutText.
    Characters outside Latin-1 (CJK, emoji, etc.) are replaced with '?'.
    """
    text_bytes = text.encode("latin-1", errors="replace")
    return struct.pack(">BxxxI", 3, len(text_bytes)) + text_bytes


# ---------------------------------------------------------------------------
# RFB client message filter — strip extension types KasmVNC doesn't support
# ---------------------------------------------------------------------------
# noVNC v1.4 batches multiple RFB messages into one WebSocket frame.
# KasmVNC 1.3.3 crashes on unsupported types (150, 248, etc.).
# We parse message boundaries using known sizes and keep only standard types.

# Client→server message sizes (fixed, except 2 and 6 which encode length)
_RFB_MSG_SIZE: dict[int, int | None] = {
    0: 20,    # SetPixelFormat
    2: None,  # SetEncodings — 4 + numEncodings*4 (rewritten to strip bad pseudo-encodings)
    3: 10,    # FramebufferUpdateRequest
    4: 8,     # KeyEvent
    5: 6,     # PointerEvent
    6: None,  # ClientCutText — 8 + length
}

# Extension types that noVNC sends — known sizes so we can skip past them
# instead of breaking and dropping all trailing data in the frame.
_RFB_EXTENSION_SIZE: dict[int, int] = {
    150: 10,  # EnableContinuousUpdates (1+1+2+2+2+2)
    248: 10,  # QEMU-like key event (observed from noVNC 1.4.0)
    252: 4,   # xvp (1+1+1+1)
    255: 4,   # QEMU audio control (1+1+2) — noVNC QEMUExtendedKeyEvent is actually 12
}

# Whitelist of encodings safe to send to KasmVNC.
# Instead of trying to blocklist problematic pseudo-encodings (error-prone —
# we had wrong numbers), we ONLY keep known-good encodings.
# Anything not on this list is stripped from SetEncodings.
_ALLOWED_ENCODINGS: set[int] = {
    # Framebuffer encodings (standard RFB)
    0,    # Raw
    1,    # CopyRect
    2,    # RRE
    5,    # Hextile
    7,    # Tight
    16,   # ZRLE
    # Safe pseudo-encodings
    -239,  # Cursor (0xFFFFFF11) — cursor shape
    -224,  # LastRect (0xFFFFFF20) — performance optimization
    # Tight quality/compress levels (these are just hints)
    *range(-32, -22),   # quality levels 0-9
    *range(-256, -246),  # compress levels 0-9
}


def _rfb_msg_length(data: bytes, offset: int) -> int | None:
    """Return total length of the RFB message at offset, or None if unrecognized."""
    if offset >= len(data):
        return None
    msg_type = data[offset]
    fixed = _RFB_MSG_SIZE.get(msg_type)
    if fixed is not None:
        return fixed
    remaining = len(data) - offset
    if msg_type == 2 and remaining >= 4:  # SetEncodings
        num_enc = struct.unpack_from(">H", data, offset + 2)[0]
        return 4 + num_enc * 4
    if msg_type == 6 and remaining >= 8:  # ClientCutText
        length = struct.unpack_from(">I", data, offset + 4)[0]
        return 8 + length
    # Known extension types — skip past them instead of giving up
    ext_size = _RFB_EXTENSION_SIZE.get(msg_type)
    if ext_size is not None:
        return ext_size
    return None  # truly unknown type


def _rewrite_set_encodings(data: bytes, offset: int, msg_len: int) -> bytes:
    """Keep only whitelisted encodings in a SetEncodings message."""
    _log = logging.getLogger("cloakbrowser.manager")
    num_enc = struct.unpack_from(">H", data, offset + 2)[0]
    kept = []
    stripped = []
    for i in range(num_enc):
        enc = struct.unpack_from(">i", data, offset + 4 + i * 4)[0]  # signed
        if enc in _ALLOWED_ENCODINGS:
            kept.append(enc)
        else:
            stripped.append(enc)
    if not stripped:
        return data[offset:offset + msg_len]
    _log.info("RFB filter: SetEncodings keeping %d: %s, stripped %d: %s", len(kept), kept, len(stripped), stripped)
    result = struct.pack(">BxH", 2, len(kept))
    for enc in kept:
        result += struct.pack(">i", enc)
    return result


def _rewrite_pointer_event(data: bytes, offset: int) -> bytes:
    """Convert standard 6-byte PointerEvent to KasmVNC's 11-byte format.

    Standard RFB:  [5:u8][mask:u8][x:u16][y:u16]          = 6 bytes
    KasmVNC:       [5:u8][mask:u16][x:u16][y:u16][sx:s16][sy:s16] = 11 bytes
    """
    mask = data[offset + 1]
    x = struct.unpack_from(">H", data, offset + 2)[0]
    y = struct.unpack_from(">H", data, offset + 4)[0]
    # Expand mask from u8 to u16.  Scroll deltas (sx, sy) are zero because
    # noVNC encodes scroll as button-mask bits (3=up, 4=down, 5=left, 6=right)
    # which pass through in the mask.  KasmVNC accepts mask-bit scroll on its
    # extended 11-byte format, so explicit deltas are unnecessary.
    return struct.pack(">BHHHhh", 5, mask, x, y, 0, 0)


def _filter_rfb_client_messages(data: bytes) -> bytes:
    """Parse concatenated RFB messages, keep only standard types (0-6).

    Rewrites PointerEvents from 6-byte standard to 11-byte KasmVNC format
    and strips unsupported pseudo-encodings from SetEncodings.
    """
    _log = logging.getLogger("cloakbrowser.manager")
    result = bytearray()
    offset = 0
    msg_idx = 0
    while offset < len(data):
        msg_type = data[offset]
        msg_len = _rfb_msg_length(data, offset)
        if msg_len is None:
            _log.info("RFB filter: DROPPING unknown type=%d at offset=%d/%d, skipping %d trailing bytes, hex=%s",
                       msg_type, offset, len(data), len(data) - offset, data[offset:offset+20].hex())
            break
        if offset + msg_len > len(data):
            # Incomplete message — DO NOT forward partial data, it desynchronizes
            # the RFB stream (KasmVNC buffers partial reads across frames).
            _log.warning("RFB filter: DROPPING incomplete type=%d need=%d have=%d — would desync stream",
                         msg_type, msg_len, len(data) - offset)
            break
        msg_idx += 1
        if msg_type in _RFB_MSG_SIZE:
            # Standard RFB type — keep (with rewrites for KasmVNC compatibility)
            _log.debug("RFB filter: KEEP type=%d len=%d at offset=%d (msg #%d in frame)", msg_type, msg_len, offset, msg_idx)
            if msg_type == 2:  # SetEncodings — whitelist safe encodings
                result.extend(_rewrite_set_encodings(data, offset, msg_len))
            elif msg_type == 5:  # PointerEvent — expand to KasmVNC's 11-byte format
                result.extend(_rewrite_pointer_event(data, offset))
            else:
                result.extend(data[offset:offset + msg_len])
        else:
            # Extension type (150, 248, etc.) — skip but continue parsing
            _log.debug("RFB filter: SKIP extension type=%d len=%d at offset=%d (msg #%d in frame)", msg_type, msg_len, offset, msg_idx)
        offset += msg_len
    if len(result) != len(data):
        _log.info("RFB filter: input=%d output=%d (delta %+d bytes)", len(data), len(result), len(result) - len(data))
    return bytes(result)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    await browser_mgr.cleanup_stale()
    browser_mgr._auto_launch_task = asyncio.create_task(browser_mgr.auto_launch_all())
    if PROXY_HEALTH_CHECK_INTERVAL > 0:
        browser_mgr._health_task = asyncio.create_task(_proxy_health_loop(PROXY_HEALTH_CHECK_INTERVAL))
    logger.info("CloakBrowser Manager started")
    yield
    logger.info("Shutting down — stopping all browsers...")
    if browser_mgr._auto_launch_task and not browser_mgr._auto_launch_task.done():
        browser_mgr._auto_launch_task.cancel()
        await asyncio.gather(browser_mgr._auto_launch_task, return_exceptions=True)
    if getattr(browser_mgr, "_health_task", None) and not browser_mgr._health_task.done():
        browser_mgr._health_task.cancel()
        await asyncio.gather(browser_mgr._health_task, return_exceptions=True)
    await browser_mgr.cleanup_all()


async def _proxy_health_loop(interval: int) -> None:
    """Periodically test every stored proxy credential and persist results."""
    from . import proxy_health
    logger.info("Proxy health check enabled (every %ds)", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            for c in db.list_proxy_credentials():
                try:
                    result = await proxy_health.test_proxy(c)
                    db.update_proxy_credential(
                        c["id"],
                        last_status="ok" if result["ok"] else "failed",
                        last_exit_ip=result.get("exit_ip"),
                        last_country=result.get("country"),
                        last_checked_at=db._now(),
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("health check failed for %s: %s", c.get("id"), exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("proxy health loop iteration error: %s", exc)


app = FastAPI(title="CloakBrowser Manager", lifespan=lifespan)
app.add_middleware(AuthMiddleware)


# ── Authentication ────────────────────────────────────────────────────────────


@app.get("/api/auth/status")
async def auth_status(request: starlette.requests.Request):
    """Check if auth is enabled and if the current request is authenticated.

    Exempt from auth middleware so the frontend can always call it.
    """
    authenticated = False
    if AUTH_TOKEN:
        authenticated = _check_auth(request.scope)
    return {"auth_required": AUTH_TOKEN is not None, "authenticated": authenticated}


@app.post("/api/auth/login")
async def auth_login(body: LoginRequest, request: Request, response: Response):
    if not AUTH_TOKEN:
        return {"ok": True}
    if not body.token or not hmac.compare_digest(body.token, AUTH_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")
    is_https = _is_https(request)
    response.set_cookie(
        key="auth_token",
        value=AUTH_TOKEN,
        httponly=True,
        samesite="strict",
        secure=is_https,
        path="/",
    )
    return {"ok": True}


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response):
    is_https = _is_https(request)
    response.delete_cookie(
        key="auth_token", path="/", secure=is_https, samesite="strict",
    )
    return {"ok": True}


# ── Profile CRUD ──────────────────────────────────────────────────────────────


@app.get("/api/profiles", response_model=list[ProfileResponse])
async def list_profiles(request: Request):
    profiles = db.list_profiles()
    return [_enrich_profile(p, request.scope) for p in profiles]


@app.post("/api/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(req: ProfileCreate, request: Request):
    data = req.model_dump()
    tags = data.pop("tags", None)
    if tags:
        data["tags"] = [t.model_dump() if hasattr(t, "model_dump") else t for t in tags]
    else:
        data["tags"] = []
    profile = db.create_profile(**data)
    return _enrich_profile(profile, request.scope)


@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str, request: Request):
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _enrich_profile(profile, request.scope)


@app.put("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: str, req: ProfileUpdate, request: Request):
    # Only pass fields that were explicitly set
    data = req.model_dump(exclude_unset=True)
    tags = data.pop("tags", None)
    if tags is not None:
        data["tags"] = [t.model_dump() if hasattr(t, "model_dump") else t for t in tags]
    profile = db.update_profile(profile_id, **data)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _enrich_profile(profile, request.scope)


@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    # Stop browser if running
    if profile_id in browser_mgr.running:
        await browser_mgr.stop(profile_id)

    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    user_data_dir = Path(profile["user_data_dir"])

    # DB first — if this fails, filesystem is untouched
    db.delete_profile(profile_id)

    # Then clean up disk
    if user_data_dir.exists():
        shutil.rmtree(user_data_dir, ignore_errors=True)

    return {"ok": True}


# ── Launch / Stop ─────────────────────────────────────────────────────────────


def _resolve_bulk_ids(body: BulkIdsRequest) -> list[str]:
    if body.ids:
        return list(body.ids)
    if body.tag:
        profiles = db.list_profiles()
        return [p["id"] for p in profiles if any(t["tag"] == body.tag for t in p.get("tags", []))]
    return []


# NB: bulk/clone endpoints are registered BEFORE the {profile_id} parameterized
# routes below, otherwise /api/profiles/bulk/... would be captured by
# /api/profiles/{profile_id}/... with profile_id == "bulk".


@app.post("/api/profiles/bulk/launch", response_model=BulkResultResponse)
async def bulk_launch(body: BulkIdsRequest):
    ids = _resolve_bulk_ids(body)
    results = []
    for pid in ids:
        try:
            profile = db.get_profile(pid)
            if not profile:
                raise ValueError("Profile not found")
            if profile.get("is_template"):
                raise ValueError("Templates cannot be launched")
            if pid in browser_mgr.running:
                raise ValueError("Already running")
            await browser_mgr.launch(profile)
            results.append(BulkResultItem(id=pid, ok=True))
        except Exception as exc:
            results.append(BulkResultItem(id=pid, ok=False, error=str(exc)))
    return BulkResultResponse(results=results)


@app.post("/api/profiles/bulk/stop", response_model=BulkResultResponse)
async def bulk_stop(body: BulkIdsRequest):
    ids = _resolve_bulk_ids(body)
    results = []
    for pid in ids:
        try:
            if pid not in browser_mgr.running:
                raise ValueError("Not running")
            await browser_mgr.stop(pid)
            results.append(BulkResultItem(id=pid, ok=True))
        except Exception as exc:
            results.append(BulkResultItem(id=pid, ok=False, error=str(exc)))
    return BulkResultResponse(results=results)


@app.post("/api/profiles/bulk/delete", response_model=BulkResultResponse)
async def bulk_delete(body: BulkIdsRequest):
    ids = _resolve_bulk_ids(body)
    results = []
    for pid in ids:
        try:
            if pid in browser_mgr.running:
                await browser_mgr.stop(pid)
            profile = db.get_profile(pid)
            if not profile:
                raise ValueError("Profile not found")
            user_data_dir = Path(profile["user_data_dir"])
            db.delete_profile(pid)
            if user_data_dir.exists():
                shutil.rmtree(user_data_dir, ignore_errors=True)
            results.append(BulkResultItem(id=pid, ok=True))
        except Exception as exc:
            results.append(BulkResultItem(id=pid, ok=False, error=str(exc)))
    return BulkResultResponse(results=results)


@app.post("/api/profiles/{profile_id}/launch", response_model=LaunchResponse)
async def launch_profile(profile_id: str, request: Request):
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.get("is_template"):
        raise HTTPException(status_code=409, detail="Templates cannot be launched")
    if profile_id in browser_mgr.running:
        raise HTTPException(status_code=409, detail="Profile is already running")

    try:
        running = await browser_mgr.launch(profile)
    except ValueError as exc:
        msg = str(exc)
        status_code = 429 if msg.startswith("Max running") else 400
        raise HTTPException(status_code=status_code, detail=msg)
    except Exception as exc:
        logger.error("Failed to launch profile %s: %s", profile_id, exc)
        raise HTTPException(status_code=500, detail="Failed to launch browser")

    return LaunchResponse(
        profile_id=profile_id,
        status="running",
        vnc_ws_port=running.ws_port,
        display=f":{running.display}",
        cdp_url=f"/api/profiles/{profile_id}/cdp",
        cdp_endpoint=_cdp_endpoint(profile_id, request.scope),
    )


@app.post("/api/profiles/{profile_id}/clone", response_model=ProfileResponse)
async def clone_profile(profile_id: str, body: CloneRequest, request: Request):
    cloned = db.clone_profile(profile_id, new_name=body.name)
    if not cloned:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _enrich_profile(cloned, request.scope)


@app.post("/api/profiles/{profile_id}/reseed", response_model=ProfileResponse)
async def reseed_profile(profile_id: str, request: Request):
    """Generate a new random fingerprint seed for a profile.

    The new seed takes effect the next time the profile is launched; the
    running browser (if any) is left untouched.
    """
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    old_seed = profile.get("fingerprint_seed")
    new_seed = random.randint(10000, 99999)
    while new_seed == old_seed:
        new_seed = random.randint(10000, 99999)
    updated = db.update_profile(profile_id, fingerprint_seed=new_seed)
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _enrich_profile(updated, request.scope)


@app.post("/api/profiles/{profile_id}/reset-ua", response_model=ProfileResponse)
async def reset_profile_user_agent(profile_id: str, request: Request):
    """Clear the explicit User-Agent override so it is regenerated on launch."""
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    updated = db.update_profile(profile_id, user_agent=None)
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _enrich_profile(updated, request.scope)


@app.post("/api/profiles/{profile_id}/stop")
async def stop_profile(profile_id: str):
    if profile_id not in browser_mgr.running:
        raise HTTPException(status_code=404, detail="Profile is not running")
    await browser_mgr.stop(profile_id)
    return {"ok": True}


@app.get("/api/profiles/{profile_id}/status", response_model=ProfileStatusResponse)
async def get_profile_status(profile_id: str, request: Request):
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    status = browser_mgr.get_status(profile_id)
    return ProfileStatusResponse(
        **status,
        cdp_endpoint=_cdp_endpoint(profile_id, request.scope),
        cdp_clients=cdp_clients.get(profile_id, 0),
    )


# ── System Status ─────────────────────────────────────────────────────────────


@app.get("/api/status", response_model=StatusResponse)
async def get_system_status():
    from cloakbrowser.config import CHROMIUM_VERSION

    profiles = db.list_profiles()
    agg = browser_mgr.aggregate_resources() if browser_mgr.running else None
    return StatusResponse(
        running_count=len(browser_mgr.running),
        binary_version=CHROMIUM_VERSION,
        profiles_total=len(profiles),
        max_running=MAX_RUNNING_PROFILES or None,
        total_cpu_percent=agg["cpu_percent"] if agg else None,
        total_mem_mb=agg["mem_mb"] if agg else None,
        total_proc_count=agg["proc_count"] if agg else None,
    )


# ── Proxy Credentials ──────────────────────────────────────────────────────────


_TEST_FIELDS = ("ok", "exit_ip", "country", "timezone", "latency_ms", "error")


@app.get("/api/proxy-credentials", response_model=list[ProxyCredentialResponse])
async def list_proxy_credentials():
    return [_cred_to_response(c) for c in db.list_proxy_credentials()]


@app.post("/api/proxy-credentials", response_model=ProxyCredentialResponse, status_code=201)
async def create_proxy_credential(req: ProxyCredentialCreate):
    cred = db.create_proxy_credential(**req.model_dump())
    return _cred_to_response(cred)  # type: ignore[arg-type]


@app.get("/api/proxy-credentials/{cred_id}", response_model=ProxyCredentialResponse)
async def get_proxy_credential(cred_id: str):
    cred = db.get_proxy_credential(cred_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Proxy credential not found")
    return _cred_to_response(cred)


@app.put("/api/proxy-credentials/{cred_id}", response_model=ProxyCredentialResponse)
async def update_proxy_credential(cred_id: str, req: ProxyCredentialUpdate):
    data = req.model_dump(exclude_unset=True)
    cred = db.update_proxy_credential(cred_id, **data)
    if not cred:
        raise HTTPException(status_code=404, detail="Proxy credential not found")
    return _cred_to_response(cred)


@app.delete("/api/proxy-credentials/{cred_id}")
async def delete_proxy_credential(cred_id: str):
    # Check if any profiles are using this credential
    count = db.count_profiles_using_credential(cred_id)
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {count} profile(s) are using this credential",
        )
    db.remove_credential_from_groups(cred_id)
    if not db.delete_proxy_credential(cred_id):
        raise HTTPException(status_code=404, detail="Proxy credential not found")
    return {"ok": True}


@app.post("/api/proxy-credentials/{cred_id}/test", response_model=ProxyTestResult)
async def test_proxy_credential(cred_id: str):
    cred = db.get_proxy_credential(cred_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Proxy credential not found")
    result = await proxy_health.test_proxy(cred)
    db.update_proxy_credential(
        cred_id,
        last_status="ok" if result["ok"] else "failed",
        last_exit_ip=result.get("exit_ip"),
        last_country=result.get("country"),
        last_checked_at=db._now(),
    )
    return ProxyTestResult(id=cred_id, **{k: result[k] for k in _TEST_FIELDS})


@app.post("/api/proxy-credentials/test-all", response_model=list[ProxyTestResult])
async def test_all_proxy_credentials():
    out: list[ProxyTestResult] = []
    for c in db.list_proxy_credentials():
        result = await proxy_health.test_proxy(c)
        db.update_proxy_credential(
            c["id"],
            last_status="ok" if result["ok"] else "failed",
            last_exit_ip=result.get("exit_ip"),
            last_country=result.get("country"),
            last_checked_at=db._now(),
        )
        out.append(ProxyTestResult(id=c["id"], **{k: result[k] for k in _TEST_FIELDS}))
    return out


# ── Proxy Providers & Locations ───────────────────────────────────────────────


@app.get("/api/proxy-locations")
async def get_proxy_locations():
    return proxy_health.PROXY_LOCATIONS


@app.get("/api/proxy-providers", response_model=list[ProxyProviderResponse])
async def list_proxy_providers():
    return [_provider_to_response(p) for p in db.list_proxy_providers()]


@app.post("/api/proxy-providers", response_model=ProxyProviderResponse, status_code=201)
async def create_proxy_provider(req: ProxyProviderCreate):
    provider = db.create_proxy_provider(**req.model_dump())
    return _provider_to_response(provider)  # type: ignore[arg-type]


@app.get("/api/proxy-providers/{provider_id}", response_model=ProxyProviderResponse)
async def get_proxy_provider(provider_id: str):
    p = db.get_proxy_provider(provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proxy provider not found")
    return _provider_to_response(p)


@app.put("/api/proxy-providers/{provider_id}", response_model=ProxyProviderResponse)
async def update_proxy_provider(provider_id: str, req: ProxyProviderUpdate):
    data = req.model_dump(exclude_unset=True)
    p = db.update_proxy_provider(provider_id, **data)
    if not p:
        raise HTTPException(status_code=404, detail="Proxy provider not found")
    return _provider_to_response(p)


@app.delete("/api/proxy-providers/{provider_id}")
async def delete_proxy_provider(provider_id: str):
    count = db.count_credentials_using_provider(provider_id)
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {count} credential(s) reference this provider",
        )
    if not db.delete_proxy_provider(provider_id):
        raise HTTPException(status_code=404, detail="Proxy provider not found")
    return {"ok": True}


# ── Proxy Groups ──────────────────────────────────────────────────────────────


@app.get("/api/proxy-groups", response_model=list[ProxyGroupResponse])
async def list_proxy_groups():
    groups = db.list_proxy_groups()
    out: list[ProxyGroupResponse] = []
    for g in groups:
        resp = _group_to_response(g["id"])
        if resp:
            out.append(resp)
    return out


@app.post("/api/proxy-groups", response_model=ProxyGroupResponse, status_code=201)
async def create_proxy_group(req: ProxyGroupCreate):
    g = db.create_proxy_group(**req.model_dump())
    return _group_to_response(g["id"])  # type: ignore[return-value]


@app.get("/api/proxy-groups/{group_id}", response_model=ProxyGroupResponse)
async def get_proxy_group_endpoint(group_id: str):
    resp = _group_to_response(group_id)
    if not resp:
        raise HTTPException(status_code=404, detail="Proxy group not found")
    return resp


@app.put("/api/proxy-groups/{group_id}", response_model=ProxyGroupResponse)
async def update_proxy_group(group_id: str, req: ProxyGroupUpdate):
    g = db.update_proxy_group(group_id, **req.model_dump(exclude_unset=True))
    if not g:
        raise HTTPException(status_code=404, detail="Proxy group not found")
    return _group_to_response(group_id)  # type: ignore[return-value]


@app.delete("/api/proxy-groups/{group_id}")
async def delete_proxy_group(group_id: str):
    count = db.count_profiles_using_group(group_id)
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {count} profile(s) are using this group",
        )
    if not db.delete_proxy_group(group_id):
        raise HTTPException(status_code=404, detail="Proxy group not found")
    return {"ok": True}


@app.put("/api/proxy-groups/{group_id}/members", response_model=ProxyGroupResponse)
async def set_proxy_group_members(group_id: str, body: GroupMembersUpdate):
    if not db.get_proxy_group(group_id):
        raise HTTPException(status_code=404, detail="Proxy group not found")
    db.set_group_members(group_id, body.credential_ids)
    return _group_to_response(group_id)  # type: ignore[return-value]


@app.post("/api/proxy-groups/{group_id}/members/{cred_id}", response_model=ProxyGroupResponse)
async def add_proxy_group_member(group_id: str, cred_id: str):
    if not db.get_proxy_group(group_id):
        raise HTTPException(status_code=404, detail="Proxy group not found")
    if not db.get_proxy_credential(cred_id):
        raise HTTPException(status_code=404, detail="Proxy credential not found")
    db.add_group_member(group_id, cred_id)
    return _group_to_response(group_id)  # type: ignore[return-value]


@app.delete("/api/proxy-groups/{group_id}/members/{cred_id}", response_model=ProxyGroupResponse)
async def remove_proxy_group_member(group_id: str, cred_id: str):
    db.remove_group_member(group_id, cred_id)
    return _group_to_response(group_id)  # type: ignore[return-value]


# ── Clipboard Relay ──────────────────────────────────────────────────────────

_CLIPBOARD_MAX_READ = 1_048_576  # 1MB cap on GET response

# Track xclip processes per display so we can kill the old one before spawning new
_xclip_procs: dict[int, asyncio.subprocess.Process] = {}


@app.post("/api/profiles/{profile_id}/clipboard")
async def set_clipboard(profile_id: str, body: ClipboardRequest):
    """Push text into the VNC session's X clipboard via xclip."""
    running = browser_mgr.running.get(profile_id)
    if not running:
        raise HTTPException(status_code=404, detail="Profile not running")

    import os

    # Kill previous xclip for this display (it stays alive to serve paste)
    old = _xclip_procs.pop(running.display, None)
    if old and old.returncode is None:
        old.kill()
        await old.wait()

    env = {**os.environ, "DISPLAY": f":{running.display}"}
    proc = await asyncio.create_subprocess_exec(
        "xclip", "-selection", "clipboard",
        stdin=asyncio.subprocess.PIPE,
        env=env,
    )
    # xclip reads stdin then stays alive to serve paste requests.
    proc.stdin.write(body.text.encode())  # type: ignore[union-attr]
    await proc.stdin.drain()  # type: ignore[union-attr]
    proc.stdin.close()  # type: ignore[union-attr]

    _xclip_procs[running.display] = proc

    return {"ok": True}


@app.get("/api/profiles/{profile_id}/clipboard")
async def get_clipboard(profile_id: str):
    """Read the VNC session's clipboard.

    Chrome doesn't write to X11 clipboard under KasmVNC, so xclip can't read it.
    Instead, read via Playwright's CDP connection to Chrome (navigator.clipboard.readText).
    Falls back to xclip for non-Chrome clipboard owners.
    """
    running = browser_mgr.running.get(profile_id)
    if not running:
        raise HTTPException(status_code=404, detail="Profile not running")

    # Read Chrome's current text selection via Playwright.
    # Chrome's native copy (via VNC Ctrl+C) doesn't write to X11 clipboard
    # and doesn't fire DOM events, so we read the visible selection instead.
    # The init script also captures copy events when they do fire.
    # Check all pages — user may have copied in any tab
    try:
        for page in running.context.pages:
            try:
                text = await page.evaluate("window.__clipboardText || ''")
                if text:
                    return {"text": text[:_CLIPBOARD_MAX_READ]}
            except Exception as exc:
                logger.debug("Clipboard read failed on page: %s", exc)
                continue
    except Exception as exc:
        logger.debug("Playwright clipboard read failed: %s", exc)

    # Fallback: xclip for non-Chrome clipboard owners
    import os

    env = {**os.environ, "DISPLAY": f":{running.display}"}
    proc = await asyncio.create_subprocess_exec(
        "xclip", "-selection", "clipboard", "-o",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"text": ""}

    if proc.returncode != 0:
        return {"text": ""}

    text = stdout[:_CLIPBOARD_MAX_READ].decode("utf-8", errors="replace")
    return {"text": text}


# ── VNC WebSocket Proxy ──────────────────────────────────────────────────────


@app.websocket("/api/profiles/{profile_id}/vnc")
async def vnc_proxy(websocket: WebSocket, profile_id: str):
    """Proxy WebSocket frames between the frontend and a profile's KasmVNC."""
    if not await _check_websocket_origin(websocket):
        return

    running = browser_mgr.running.get(profile_id)
    if not running:
        await websocket.close(code=4004, reason="Profile not running")
        return

    # Accept with client's requested subprotocol (if any) — RFC 6455 requires
    # the server must not respond with a subprotocol the client didn't request.
    requested = websocket.scope.get("subprotocols", [])
    subprotocol = "binary" if "binary" in requested else None
    await websocket.accept(subprotocol=subprotocol)

    import websockets

    vnc_url = f"ws://127.0.0.1:{running.ws_port}/websockify"

    try:
        async with websockets.connect(
            vnc_url,
            subprotocols=["binary"],
            origin=f"http://127.0.0.1:{running.ws_port}",
            max_size=None,  # VNC frames can be large (1920x1080 framebuffer)
            ping_interval=None,  # KasmVNC doesn't respond to WS pings
            ping_timeout=None,
            compression=None,  # KasmVNC can't handle permessage-deflate
        ) as vnc_ws:
            logger.info(
                "VNC proxy: connected to KasmVNC for %s (subprotocol=%s)",
                profile_id, vnc_ws.subprotocol,
            )

            # noVNC v1.4 sends extension message types (150=ContinuousUpdates,
            # 248=QEMUKey, etc.) that KasmVNC 1.3.3 doesn't support, causing
            # "unknown message type" → disconnect.
            #
            # noVNC batches multiple RFB messages into a single WebSocket frame,
            # so we must parse the RFB stream to find message boundaries and strip
            # unsupported types before forwarding. Standard client→server types
            # have known fixed sizes (except SetEncodings and ClientCutText which
            # encode their length).

            async def client_to_vnc():
                count = 0
                handshake = 0  # first 3 messages are RFB handshake
                dropped = 0
                try:
                    while True:
                        msg = await websocket.receive()
                        msg_type = msg.get("type", "")
                        if msg_type == "websocket.disconnect":
                            logger.info("VNC proxy [c->v]: client disconnect (code=%s) after %d msgs (%d dropped)", msg.get("code"), count, dropped)
                            break
                        if "bytes" in msg and msg["bytes"]:
                            count += 1
                            data = msg["bytes"]
                            handshake += 1

                            # First 3 messages are RFB handshake — forward as-is
                            if handshake <= 3:
                                logger.debug("VNC handshake #%d: %d bytes hex=%s", handshake, len(data), data[:20].hex())
                                await vnc_ws.send(data)
                                continue

                            # Parse RFB messages and strip unsupported types
                            filtered = _filter_rfb_client_messages(data)
                            if filtered:
                                # Safety: verify first byte is a valid RFB client type
                                if filtered[0] not in _RFB_MSG_SIZE:
                                    logger.error("RFB SAFETY: refusing to send data with invalid first byte=%d hex=%s",
                                                 filtered[0], filtered[:20].hex())
                                    dropped += 1
                                    continue
                                logger.debug("VNC send: %d bytes first_type=%d hex=%s", len(filtered), filtered[0], filtered[:100].hex())
                                await vnc_ws.send(filtered)
                            else:
                                dropped += 1

                        elif "text" in msg and msg["text"]:
                            # noVNC only sends binary frames — text frames are unexpected
                            # and would bypass the RFB filter, so drop them.
                            count += 1
                            logger.warning("VNC proxy [c->v]: DROPPING text frame len=%d (noVNC should only send binary)", len(msg["text"]))
                            dropped += 1
                        else:
                            logger.warning("VNC proxy [c->v]: unhandled msg keys=%s type=%s", list(msg.keys()), msg_type)
                except WebSocketDisconnect as exc:
                    logger.info("VNC proxy [c->v]: WebSocketDisconnect code=%s after %d msgs (%d dropped)", exc.code, count, dropped)
                except Exception as exc:
                    logger.warning("VNC proxy [c->v]: %s: %s (after %d msgs)", type(exc).__name__, exc, count)

            async def vnc_to_client():
                count = 0
                try:
                    async for msg in vnc_ws:
                        count += 1
                        if isinstance(msg, bytes) and len(msg) > 0:
                            msg_type = msg[0]
                            if msg_type == 180:
                                # KasmVNC BinaryClipboard → convert to standard
                                # ServerCutText (type 3) so noVNC can handle it
                                text = _parse_kasmvnc_clipboard(msg)
                                if text:
                                    logger.info("VNC proxy [v->c]: clipboard %d chars", len(text))
                                    await websocket.send_bytes(_build_server_cut_text(text))
                                else:
                                    logger.info("VNC proxy [v->c]: dropped type 180 (no text/plain)")
                                continue
                            await websocket.send_bytes(msg)
                        elif isinstance(msg, bytes):
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(msg)
                    logger.info("VNC proxy [v->c]: KasmVNC stream ended after %d msgs (close_code=%s)", count, vnc_ws.close_code)
                except WebSocketDisconnect as exc:
                    logger.info("VNC proxy [v->c]: client disconnect code=%s after %d msgs", exc.code, count)
                except Exception as exc:
                    logger.warning("VNC proxy [v->c]: %s: %s (after %d msgs)", type(exc).__name__, exc, count)

            c2v = asyncio.create_task(client_to_vnc(), name="c2v")
            v2c = asyncio.create_task(vnc_to_client(), name="v2c")

            done, pending = await asyncio.wait(
                [c2v, v2c],
                return_when=asyncio.FIRST_COMPLETED,
            )
            finished = [t.get_name() for t in done]
            still_running = [t.get_name() for t in pending]

            # Check if Xvnc is still alive
            vnc_instance = browser_mgr.vnc._allocated.get(running.display)
            xvnc_alive = vnc_instance and vnc_instance.process and vnc_instance.process.poll() is None
            logger.info(
                "VNC proxy: finished=%s pending=%s xvnc_alive=%s display=:%d for %s",
                finished, still_running, xvnc_alive, running.display, profile_id,
            )

            # Dump Xvnc log on disconnect
            import os
            xvnc_log = f"/tmp/xvnc-{running.display}.log"
            if os.path.exists(xvnc_log):
                with open(xvnc_log) as f:
                    log_content = f.read()
                if log_content.strip():
                    for line in log_content.strip().split("\n")[-20:]:
                        logger.info("Xvnc[:%d] %s", running.display, line)

            for task in pending:
                task.cancel()

    except Exception as exc:
        logger.error("VNC proxy connect error for %s: %s: %s", profile_id, type(exc).__name__, exc)
    finally:
        try:
            await websocket.close()
        except Exception as exc:
            logger.debug("VNC proxy: websocket.close() failed: %s", exc)


# ── CDP WebSocket Proxy ──────────────────────────────────────────────────────
# Simple bidirectional passthrough — CDP is standard JSON over WebSocket,
# no protocol translation needed (unlike VNC which requires RFB filtering).


@app.get("/api/profiles/{profile_id}/cdp")
async def cdp_info(profile_id: str):
    """Return CDP connection info. Prevents SPA catch-all from serving index.html."""
    running = browser_mgr.running.get(profile_id)
    if not running:
        raise HTTPException(status_code=404, detail="Profile not running")
    return {
        "cdp_url": f"/api/profiles/{profile_id}/cdp",
        "usage": "playwright.chromium.connect_over_cdp('http://<host>/api/profiles/"
        + profile_id + "/cdp')",
    }


async def _fetch_cdp_json(profile_id: str, chrome_path: str) -> dict:
    running = browser_mgr.running.get(profile_id)
    if not running:
        raise HTTPException(status_code=404, detail="Profile not running")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://127.0.0.1:{running.cdp_port}{chrome_path}", timeout=5
            )
            return resp.json()
    except Exception as exc:
        logger.error("CDP proxy: failed to reach Chrome CDP for %s: %s", profile_id, exc)
        raise HTTPException(status_code=502, detail="CDP endpoint unreachable")


@app.get("/api/profiles/{profile_id}/cdp/json/version/")
@app.get("/api/profiles/{profile_id}/cdp/json/version")
async def cdp_json_version(profile_id: str, request: Request):
    """Proxy Chrome's /json/version, rewriting WS URLs to go through our proxy."""
    data = await _fetch_cdp_json(profile_id, "/json/version")
    host = request.headers.get("host", "localhost:8080")
    ws_scheme = "wss" if _is_https(request) else "ws"
    data["webSocketDebuggerUrl"] = f"{ws_scheme}://{host}/api/profiles/{profile_id}/cdp"
    return data


@app.get("/api/profiles/{profile_id}/cdp/json/list/")
@app.get("/api/profiles/{profile_id}/cdp/json/list")
@app.get("/api/profiles/{profile_id}/cdp/json/")
@app.get("/api/profiles/{profile_id}/cdp/json")
async def cdp_json_list(profile_id: str, request: Request):
    """Proxy Chrome's /json/list, rewriting WS URLs."""
    data = await _fetch_cdp_json(profile_id, "/json/list")
    host = request.headers.get("host", "localhost:8080")
    ws_scheme = "wss" if _is_https(request) else "ws"
    for entry in data:
        if "webSocketDebuggerUrl" in entry:
            ws_path = entry["webSocketDebuggerUrl"].split("/devtools/")[-1]
            entry["webSocketDebuggerUrl"] = (
                f"{ws_scheme}://{host}/api/profiles/{profile_id}/cdp/devtools/{ws_path}"
            )
    return data


# ── Local CDP (loopback-only, opt-in via ALLOW_LOCAL_CDP) ─────────────────────
# Lets local tools like bdg connect to page-level CDP without an auth-injecting
# bridge. The AuthMiddleware exempts these paths only when the request is from
# loopback (client IP or Host header) and ALLOW_LOCAL_CDP is set.


@app.get("/api/profiles/{profile_id}/cdp/local/json/version/")
@app.get("/api/profiles/{profile_id}/cdp/local/json/version")
async def cdp_local_json_version(profile_id: str, request: Request):
    data = await _fetch_cdp_json(profile_id, "/json/version")
    host = request.headers.get("host", "localhost:8080")
    data["webSocketDebuggerUrl"] = f"ws://{host}/api/profiles/{profile_id}/cdp/local"
    return data


@app.get("/api/profiles/{profile_id}/cdp/local/json/list/")
@app.get("/api/profiles/{profile_id}/cdp/local/json/list")
@app.get("/api/profiles/{profile_id}/cdp/local/json/")
@app.get("/api/profiles/{profile_id}/cdp/local/json")
async def cdp_local_json_list(profile_id: str, request: Request):
    data = await _fetch_cdp_json(profile_id, "/json/list")
    host = request.headers.get("host", "localhost:8080")
    for entry in data:
        if "webSocketDebuggerUrl" in entry:
            ws_path = entry["webSocketDebuggerUrl"].split("/devtools/")[-1]
            entry["webSocketDebuggerUrl"] = (
                f"ws://{host}/api/profiles/{profile_id}/cdp/local/devtools/{ws_path}"
            )
    return data


async def _proxy_cdp_websocket(
    websocket: WebSocket, target_url: str, label: str,
    profile_id: str | None = None,
) -> None:
    """Bidirectional WebSocket proxy between a FastAPI client and a CDP target.

    Used by both browser-level and page-level CDP proxy endpoints. If
    profile_id is given, the active-CDP-client counter is maintained for it.
    """
    import websockets

    if profile_id:
        _cdp_clients_inc(profile_id)
    try:
        async with websockets.connect(
            target_url, max_size=None, ping_interval=None, ping_timeout=None
        ) as cdp_ws:
            logger.info("%s: connected to %s", label, target_url)

            async def client_to_cdp():
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        if "text" in msg and msg["text"]:
                            await cdp_ws.send(msg["text"])
                        elif "bytes" in msg and msg["bytes"]:
                            await cdp_ws.send(msg["bytes"])
                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    logger.warning("%s [c->cdp]: %s: %s", label, type(exc).__name__, exc)

            async def cdp_to_client():
                try:
                    async for msg in cdp_ws:
                        if isinstance(msg, str):
                            await websocket.send_text(msg)
                        else:
                            await websocket.send_bytes(msg)
                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    logger.warning("%s [cdp->c]: %s: %s", label, type(exc).__name__, exc)

            c2d = asyncio.create_task(client_to_cdp(), name="c2d")
            d2c = asyncio.create_task(cdp_to_client(), name="d2c")
            done, pending = await asyncio.wait(
                [c2d, d2c], return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            logger.info("%s: disconnected", label)

    except Exception as exc:
        logger.error("%s error: %s", label, exc)
    finally:
        if profile_id:
            _cdp_clients_dec(profile_id)
        try:
            await websocket.close()
        except Exception as exc:
            logger.debug("%s: websocket.close() failed: %s", label, exc)


@app.websocket("/api/profiles/{profile_id}/cdp")
async def cdp_proxy(websocket: WebSocket, profile_id: str):
    """Proxy WebSocket frames between external tools and Chrome's CDP."""
    if not await _check_websocket_origin(websocket):
        return

    running = browser_mgr.running.get(profile_id)
    if not running:
        await websocket.close(code=4004, reason="Profile not running")
        return

    await websocket.accept()

    # Get browser-level CDP WebSocket URL from Chrome
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://127.0.0.1:{running.cdp_port}/json/version", timeout=5
            )
            ws_url = resp.json()["webSocketDebuggerUrl"]
    except Exception as exc:
        logger.error("CDP proxy: failed to get WS URL for %s: %s", profile_id, exc)
        await websocket.close(code=4005, reason="CDP not available")
        return

    await _proxy_cdp_websocket(websocket, ws_url, f"CDP proxy [{profile_id}]", profile_id)


@app.websocket("/api/profiles/{profile_id}/cdp/devtools/{path:path}")
async def cdp_page_proxy(websocket: WebSocket, profile_id: str, path: str):
    """Proxy page-specific CDP WebSocket connections (e.g. /devtools/page/GUID)."""
    if not await _check_websocket_origin(websocket):
        return

    running = browser_mgr.running.get(profile_id)
    if not running:
        await websocket.close(code=4004, reason="Profile not running")
        return

    await websocket.accept()

    target_url = f"ws://127.0.0.1:{running.cdp_port}/devtools/{path}"
    await _proxy_cdp_websocket(websocket, target_url, f"CDP page proxy [{profile_id}]", profile_id)


# ── Local CDP WebSocket routes (loopback-only, opt-in) ────────────────────────


@app.websocket("/api/profiles/{profile_id}/cdp/local")
async def cdp_local_proxy(websocket: WebSocket, profile_id: str):
    """Browser-level CDP over the auth-free local path."""
    if not await _check_websocket_origin(websocket):
        return

    running = browser_mgr.running.get(profile_id)
    if not running:
        await websocket.close(code=4004, reason="Profile not running")
        return

    await websocket.accept()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://127.0.0.1:{running.cdp_port}/json/version", timeout=5
            )
            ws_url = resp.json()["webSocketDebuggerUrl"]
    except Exception as exc:
        logger.error("local CDP: failed to get WS URL for %s: %s", profile_id, exc)
        await websocket.close(code=4005, reason="CDP not available")
        return

    await _proxy_cdp_websocket(websocket, ws_url, f"CDP local [{profile_id}]", profile_id)


@app.websocket("/api/profiles/{profile_id}/cdp/local/devtools/{path:path}")
async def cdp_local_page_proxy(websocket: WebSocket, profile_id: str, path: str):
    """Page-level CDP over the auth-free local path (for bdg etc.)."""
    if not await _check_websocket_origin(websocket):
        return

    running = browser_mgr.running.get(profile_id)
    if not running:
        await websocket.close(code=4004, reason="Profile not running")
        return

    await websocket.accept()
    target_url = f"ws://127.0.0.1:{running.cdp_port}/devtools/{path}"
    await _proxy_cdp_websocket(websocket, target_url, f"CDP local page [{profile_id}]", profile_id)


# ── Static Frontend ───────────────────────────────────────────────────────────

# Serve React build. Must be AFTER API routes so /api/* isn't caught by the SPA.
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — all non-API routes return index.html."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = FRONTEND_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")

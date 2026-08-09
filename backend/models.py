"""Pydantic models for profile CRUD operations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Proxy Credentials ───────────────────────────────────────────────────────


class ProxyCredentialCreate(BaseModel):
    name: str
    scheme: Literal["http", "https", "socks5"] = "socks5"
    host: str = ""
    port: int = 1080
    username: str = ""
    password: str = ""
    provider_id: str | None = None
    provider_location: str | None = None


class ProxyCredentialUpdate(BaseModel):
    name: str | None = None
    scheme: Literal["http", "https", "socks5"] | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    provider_id: str | None = None
    provider_location: str | None = None


class ProxyCredentialResponse(BaseModel):
    id: str
    name: str
    scheme: str = "socks5"
    host: str
    port: int = 1080
    username: str = ""
    has_password: bool = False
    proxy_url: str = ""
    provider_id: str | None = None
    provider_location: str | None = None
    last_status: str | None = None  # "ok" | "failed" | None
    last_exit_ip: str | None = None
    last_country: str | None = None
    last_checked_at: str | None = None
    created_at: str
    updated_at: str


# ── Proxy Providers ────────────────────────────────────────────────────────


class ProxyProviderCreate(BaseModel):
    name: str
    type: Literal["ipvanish", "brightdata", "smartproxy", "custom"] = "custom"
    scheme: Literal["http", "https", "socks5"] = "socks5"
    host_template: str = ""
    port: int = 1080
    username: str = ""
    password: str = ""
    options: dict = Field(default_factory=dict)


class ProxyProviderUpdate(BaseModel):
    name: str | None = None
    type: Literal["ipvanish", "brightdata", "smartproxy", "custom"] | None = None
    scheme: Literal["http", "https", "socks5"] | None = None
    host_template: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    options: dict | None = None


class ProxyProviderResponse(BaseModel):
    id: str
    name: str
    type: str = "custom"
    scheme: str = "socks5"
    host_template: str = ""
    port: int = 1080
    username: str = ""
    has_password: bool = False
    options: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str


# ── Proxy Groups ───────────────────────────────────────────────────────────


class ProxyGroupCreate(BaseModel):
    name: str
    rotation_mode: Literal["round_robin", "sticky_session", "random"] = "round_robin"


class ProxyGroupUpdate(BaseModel):
    name: str | None = None
    rotation_mode: Literal["round_robin", "sticky_session", "random"] | None = None


class ProxyGroupMemberResponse(BaseModel):
    credential_id: str
    position: int
    name: str
    scheme: str = "socks5"
    host: str = ""
    port: int = 1080
    username: str = ""
    provider_id: str | None = None
    provider_location: str | None = None
    last_status: str | None = None
    last_exit_ip: str | None = None
    last_country: str | None = None


class ProxyGroupResponse(BaseModel):
    id: str
    name: str
    rotation_mode: str = "round_robin"
    member_count: int = 0
    members: list[ProxyGroupMemberResponse] = []
    created_at: str
    updated_at: str


class GroupMembersUpdate(BaseModel):
    credential_ids: list[str]


# ── Proxy Test ─────────────────────────────────────────────────────────────


class ProxyTestResult(BaseModel):
    id: str | None = None
    ok: bool
    exit_ip: str | None = None
    country: str | None = None
    timezone: str | None = None
    latency_ms: int | None = None
    error: str | None = None


# ── Tags ───────────────────────────────────────────────────────────────────


class TagCreate(BaseModel):
    tag: str
    color: str | None = None  # hex color


class TagResponse(BaseModel):
    tag: str
    color: str | None = None


# ── Profiles ──────────────────────────────────────────────────────────────


class ProfileCreate(BaseModel):
    name: str
    fingerprint_seed: int | None = None  # random if not set
    proxy: str | None = None  # "http://user:pass@host:port" or null
    proxy_credential_id: str | None = None  # reference to saved proxy credential
    proxy_group_id: str | None = None  # reference to a proxy rotation group
    timezone: str | None = None  # "America/New_York"
    locale: str | None = None  # "en-US"
    platform: Literal["windows", "macos", "linux"] = "windows"
    user_agent: str | None = None
    screen_width: int = 1920
    screen_height: int = 1080
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = None
    device_memory: float | None = None  # GB; real Chrome only reports 0.25/0.5/1/2/4/8 (capped at 8)
    brand: Literal["chrome", "edge", "opera", "vivaldi"] | None = None  # Sec-CH-UA brand
    brand_version: str | None = None  # leave unset → derived from binary Chromium version
    platform_version: str | None = None  # e.g. "10.0.19045" (Windows) or "13_5_1" (macOS)
    fonts_dir: str | None = None  # directory with target-platform fonts for font fingerprinting
    storage_quota_mb: int | None = None  # overrides storage quota reported via Storage APIs
    taskbar_height: int | None = None  # px, subtracted from availHeight
    geolocation_lat: float | None = None
    geolocation_lon: float | None = None
    webrtc_ip: str | None = None  # "auto" or explicit IP for WebRTC ICE candidates
    noise_enabled: bool = True  # canvas/WebGL/audio/client-rect noise (set False for stable returning-user identity)
    humanize: bool = False
    human_preset: Literal["default", "careful"] = "default"
    human_config: dict | None = None  # custom override mapping for typing/mouse/scroll params
    headless: bool = False
    geoip: bool = False
    clipboard_sync: bool = True
    auto_launch: bool = False
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    launch_args: list[str] = Field(default_factory=list)
    notes: str | None = None
    is_template: bool = False
    restart_on_crash: bool = False
    max_restarts: int = 5
    clear_on_launch: bool = False  # wipe cookies/cache/storage before each launch
    storage_state: dict | None = None  # pre-seeded cookies/localStorage state
    permissions: list[str] | None = None  # e.g. ["geolocation", "notifications"]
    device_scale_factor: float | None = None
    is_mobile: bool = False
    has_touch: bool = False
    extension_paths: list[str] | None = None  # Chrome extension paths to load
    persona: str | None = None  # coherent real-world device persona name (applied at creation)
    tags: list[TagCreate] | None = None

    @field_validator("device_memory")
    @classmethod
    def validate_device_memory(cls, v: object) -> object:
        """Reject deviceMemory values real Chrome cannot report.

        navigator.deviceMemory is a privacy-threshold value capped at 8 GB;
        stock Chrome only ever reports 0.25/0.5/1/2/4/8. Reporting 16/32/64 is
        impossible and a strong bot signal, so we block it at the write path.
        """
        if v is None:
            return v
        if v not in (0.25, 0.5, 1, 2, 4, 8):
            raise ValueError(
                "device_memory must be one of 0.25, 0.5, 1, 2, 4, 8 "
                "(navigator.deviceMemory is capped at 8 in real Chrome)"
            )
        return v


class ProfileUpdate(BaseModel):
    name: str | None = None
    fingerprint_seed: int | None = None
    proxy: str | None = Field(default=None)
    proxy_credential_id: str | None = Field(default=None)
    proxy_group_id: str | None = Field(default=None)
    timezone: str | None = Field(default=None)
    locale: str | None = Field(default=None)
    platform: Literal["windows", "macos", "linux"] | None = None
    user_agent: str | None = Field(default=None)
    screen_width: int | None = None
    screen_height: int | None = None
    gpu_vendor: str | None = Field(default=None)
    gpu_renderer: str | None = Field(default=None)
    hardware_concurrency: int | None = Field(default=None)
    device_memory: float | None = Field(default=None)
    brand: Literal["chrome", "edge", "opera", "vivaldi"] | None = Field(default=None)
    brand_version: str | None = Field(default=None)
    platform_version: str | None = Field(default=None)
    fonts_dir: str | None = Field(default=None)
    storage_quota_mb: int | None = Field(default=None)
    taskbar_height: int | None = Field(default=None)
    geolocation_lat: float | None = Field(default=None)
    geolocation_lon: float | None = Field(default=None)
    webrtc_ip: str | None = Field(default=None)
    noise_enabled: bool | None = None
    humanize: bool | None = None
    human_preset: Literal["default", "careful"] | None = None
    human_config: dict | None = Field(default=None)
    headless: bool | None = None
    geoip: bool | None = None
    clipboard_sync: bool | None = None
    auto_launch: bool | None = None
    color_scheme: Literal["light", "dark", "no-preference"] | None = Field(default=None)
    launch_args: list[str] | None = None
    notes: str | None = Field(default=None)
    is_template: bool | None = None
    restart_on_crash: bool | None = None
    max_restarts: int | None = None
    clear_on_launch: bool | None = None
    storage_state: dict | None = Field(default=None)
    permissions: list[str] | None = Field(default=None)
    device_scale_factor: float | None = Field(default=None)
    is_mobile: bool | None = None
    has_touch: bool | None = None
    extension_paths: list[str] | None = Field(default=None)
    persona: str | None = Field(default=None)
    tags: list[TagCreate] | None = None

    @field_validator("device_memory")
    @classmethod
    def validate_device_memory(cls, v: object) -> object:
        if v is None:
            return v
        if v not in (0.25, 0.5, 1, 2, 4, 8):
            raise ValueError(
                "device_memory must be one of 0.25, 0.5, 1, 2, 4, 8 "
                "(navigator.deviceMemory is capped at 8 in real Chrome)"
            )
        return v


class ProfileResponse(BaseModel):
    id: str
    name: str
    fingerprint_seed: int
    proxy: str | None = None
    proxy_credential_id: str | None = None
    proxy_credential: ProxyCredentialResponse | None = None
    proxy_group_id: str | None = None
    proxy_group: ProxyGroupResponse | None = None
    timezone: str | None = None
    locale: str | None = None
    platform: str = "windows"
    user_agent: str | None = None
    screen_width: int = 1920
    screen_height: int = 1080
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = None
    device_memory: float | None = None
    brand: str | None = None
    brand_version: str | None = None
    platform_version: str | None = None
    fonts_dir: str | None = None
    storage_quota_mb: int | None = None
    taskbar_height: int | None = None
    geolocation_lat: float | None = None
    geolocation_lon: float | None = None
    webrtc_ip: str | None = None
    noise_enabled: bool = True
    humanize: bool = False
    human_preset: str = "default"
    human_config: dict | None = None
    headless: bool = False
    geoip: bool = False
    clipboard_sync: bool = True
    auto_launch: bool = False
    clear_on_launch: bool = False
    storage_state: dict | None = None
    permissions: list[str] | None = None
    device_scale_factor: float | None = None
    is_mobile: bool = False
    has_touch: bool = False
    extension_paths: list[str] | None = None
    persona: str | None = None
    coherence_warnings: list[str] = []

    @field_validator("clipboard_sync", mode="before")
    @classmethod
    def coerce_clipboard_sync(cls, v: object) -> bool:
        return v if v is not None else True

    color_scheme: str | None = None
    launch_args: list[str] = []
    notes: str | None = None
    is_template: bool = False
    restart_on_crash: bool = False
    max_restarts: int = 5
    user_data_dir: str
    created_at: str
    updated_at: str
    tags: list[TagResponse] = []
    status: str = "stopped"  # "running" | "stopped"
    vnc_ws_port: int | None = None
    cdp_url: str | None = None
    cdp_endpoint: str | None = None  # full ws://host:port/api/profiles/{id}/cdp
    resources: ProfileResources | None = None


class LaunchResponse(BaseModel):
    profile_id: str
    status: str = "running"
    vnc_ws_port: int
    display: str
    cdp_url: str | None = None
    cdp_endpoint: str | None = None  # full ws:// URL


class StatusResponse(BaseModel):
    running_count: int
    binary_version: str
    profiles_total: int
    max_running: int | None = None
    # Aggregate resource usage across running profiles (None when none running)
    total_cpu_percent: float | None = None
    total_mem_mb: float | None = None
    total_proc_count: int | None = None


# ── Resources ───────────────────────────────────────────────────────────────


class ProfileResources(BaseModel):
    """Per-profile resource usage for a running browser (best-effort, via psutil)."""
    cpu_percent: float | None = None
    mem_mb: float | None = None
    uptime_s: float | None = None
    proc_count: int | None = None


class ProfileStatusResponse(BaseModel):
    status: str  # "running" | "stopped"
    vnc_ws_port: int | None = None
    display: str | None = None
    cdp_url: str | None = None
    cdp_endpoint: str | None = None
    cdp_clients: int = 0
    exit_ip: str | None = None
    effective_timezone: str | None = None
    effective_locale: str | None = None
    resources: ProfileResources | None = None
    coherence_warnings: list[str] = []


# ── Clone / Bulk ────────────────────────────────────────────────────────────


class CloneRequest(BaseModel):
    name: str | None = None


class BulkIdsRequest(BaseModel):
    ids: list[str] | None = None
    tag: str | None = None  # if set, resolve to all profiles with this tag


class BulkResultItem(BaseModel):
    id: str
    ok: bool
    error: str | None = None


class BulkResultResponse(BaseModel):
    results: list[BulkResultItem]


# ── Misc ────────────────────────────────────────────────────────────────────


class ClipboardRequest(BaseModel):
    text: str = Field(max_length=1_048_576)  # 1MB max


class LoginRequest(BaseModel):
    token: str

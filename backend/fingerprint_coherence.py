"""Cross-field consistency helpers for CloakBrowser profiles.

Anti-bot systems correlate many signals. This module detects contradictions
between platform, GPU, user agent, timezone, locale, screen size, etc., and
produces warnings / suggested corrections that the manager can surface in the
UI or auto-apply when safe.

The single most important principle: **every signal must agree**. A real
browser is internally consistent — the User-Agent Chrome major equals the
Sec-CH-UA brand version equals the binary's Chromium version; the WebGL
renderer matches the platform; the timezone country matches the locale
country matches the proxy exit country; the screen / availScreen / outer /
inner / devicePixelRatio chain is self-consistent. The validators below encode
those invariants.
"""

from __future__ import annotations

import platform as _platform
import re
from typing import Any


# ── Known GPU renderer patterns per platform ─────────────────────────────────

_PLATFORM_RENDERERS = {
    "windows": ("ANGLE (", "Direct3D11"),
    "macos": ("ANGLE (Apple,", "Metal"),
    "linux": ("ANGLE (", "Vulkan", "OpenGL"),
}

# Common UA platform fragments for sanity checks.
_UA_PLATFORM_FRAGMENTS = {
    "windows": ("Windows NT", "Win64", "WOW64"),
    "macos": ("Macintosh", "Mac OS X", "MacOS"),
    "linux": ("Linux", "X11"),
}

# Approximate Chrome UI heights that anti-bot scripts compare against
# `window.outerHeight - window.innerHeight`.
_PLATFORM_CHROME_UI_HEIGHT = {
    "windows": 133,
    "macos": 91,
    "linux": 80,
}

# Default taskbar/dock offsets subtracted from screen.availHeight per platform.
_PLATFORM_TASKBAR_HEIGHT = {
    "windows": 40,
    "macos": 23,
    "linux": 0,
}

# navigator.deviceMemory is a privacy-threshold value: real Chrome only ever
# reports one of these, capped at 8 GB — even on 64 GB machines. Reporting 16+
# is impossible in stock Chrome and a strong bot signal.
STANDARD_DEVICE_MEMORY: tuple[float, ...] = (0.25, 0.5, 1, 2, 4, 8)

# Logical-core counts real consumer CPUs ship with. Odd or huge values are
# suspicious (Chrome reports logical cores, so big.LITTLE hybrids do produce
# values like 10/12/14/20, but 7/13/99 are not real SKUs).
COMMON_CORE_COUNTS = {2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32}

# Common locale region (ISO-3166) -> country name mapping, used to detect
# timezone/locale/proxy country disagreements at country granularity.
_COUNTRY_LOCALE_HINTS = {
    "United States": "en-US",
    "Canada": "en-CA",
    "United Kingdom": "en-GB",
    "Germany": "de-DE",
    "France": "fr-FR",
    "Netherlands": "nl-NL",
    "Australia": "en-AU",
    "Japan": "ja-JP",
    "Poland": "pl-PL",
    "Spain": "es-ES",
    "Italy": "it-IT",
}

# Country name -> ISO-3166 alpha-2 code (for cross-checking proxy country vs.
# timezone/locale region).
_COUNTRY_ISO: dict[str, str] = {
    "United States": "US",
    "Canada": "CA",
    "United Kingdom": "GB",
    "Germany": "DE",
    "France": "FR",
    "Netherlands": "NL",
    "Australia": "AU",
    "Japan": "JP",
    "Poland": "PL",
    "Spain": "ES",
    "Italy": "IT",
}

# IANA timezone -> ISO country code. Keep this focused on common exit locations;
# unmapped timezones are skipped (no false positives).
_TZ_COUNTRY: dict[str, str] = {
    "America/New_York": "US", "America/Chicago": "US", "America/Denver": "US",
    "America/Los_Angeles": "US", "America/Toronto": "CA", "America/Vancouver": "CA",
    "America/Mexico_City": "MX", "America/Sao_Paulo": "BR", "America/Argentina/Buenos_Aires": "AR",
    "America/Bogota": "CO", "America/Lima": "PE", "America/Santiago": "CL",
    "Europe/London": "GB", "Europe/Dublin": "IE", "Europe/Berlin": "DE",
    "Europe/Paris": "FR", "Europe/Amsterdam": "NL", "Europe/Brussels": "BE",
    "Europe/Madrid": "ES", "Europe/Rome": "IT", "Europe/Lisbon": "PT",
    "Europe/Warsaw": "PL", "Europe/Stockholm": "SE", "Europe/Oslo": "NO",
    "Europe/Copenhagen": "DK", "Europe/Helsinki": "FI", "Europe/Zurich": "CH",
    "Europe/Vienna": "AT", "Europe/Prague": "CZ", "Europe/Athens": "GR",
    "Asia/Tokyo": "JP", "Asia/Seoul": "KR", "Asia/Shanghai": "CN",
    "Asia/Hong_Kong": "HK", "Asia/Singapore": "SG", "Asia/Bangkok": "TH",
    "Asia/Jakarta": "ID", "Asia/Manila": "PH", "Asia/Kolkata": "IN",
    "Asia/Dubai": "AE", "Asia/Tel_Aviv": "IL",
    "Australia/Sydney": "AU", "Australia/Melbourne": "AU", "Australia/Perth": "AU",
    "Pacific/Auckland": "NZ",
    "Africa/Johannesburg": "ZA", "Africa/Lagos": "NG", "Africa/Nairobi": "KE",
    "Africa/Cairo": "EG", "Africa/Casablanca": "MA",
}

_Platform = str  # keep type readable


def chrome_ui_height(platform: _Platform | None) -> int:
    """Return the recommended Chrome UI offset for the spoofed platform."""
    return _PLATFORM_CHROME_UI_HEIGHT.get((platform or "").lower(), 133)


def _default_taskbar(platform: _Platform | None) -> int:
    return _PLATFORM_TASKBAR_HEIGHT.get((platform or "").lower(), 40)


def _chrome_major_from_ua(ua: str | None) -> int | None:
    """Extract the Chrome/<major> token from a User-Agent string."""
    m = re.search(r"Chrome/(\d+)", ua or "")
    return int(m.group(1)) if m else None


def _major_from_version(v: Any) -> int | None:
    """Extract the leading integer from a dotted version string."""
    if v is None:
        return None
    try:
        return int(str(v).split(".")[0])
    except (ValueError, TypeError):
        return None


def get_binary_chromium_version() -> str | None:
    """Best-effort lookup of the installed CloakBrowser binary's Chromium version.

    Cached after first successful read. Returns None if the package or its
    version constant is unavailable (e.g. running outside the container).
    """
    global _cached_binary_version
    if _cached_binary_version is not None:
        return _cached_binary_version
    try:
        from cloakbrowser.config import CHROMIUM_VERSION  # type: ignore

        _cached_binary_version = str(CHROMIUM_VERSION)
        return _cached_binary_version
    except Exception:
        pass
    try:
        import cloakbrowser  # type: ignore

        v = getattr(cloakbrowser, "__version__", None) or getattr(
            cloakbrowser, "CHROMIUM_VERSION", None
        )
        if v:
            _cached_binary_version = str(v)
            return _cached_binary_version
    except Exception:
        pass
    return None


_cached_binary_version: str | None = None


def detect_host_platform() -> str:
    """Map the host OS to one of windows/macos/linux."""
    sysname = _platform.system().lower()
    if sysname == "windows":
        return "windows"
    if sysname == "darwin":
        return "macos"
    return "linux"


def validate_gpu_renderer(platform: _Platform | None, renderer: str | None) -> list[str]:
    """Return warnings if the GPU renderer contradicts the chosen platform."""
    warnings: list[str] = []
    if not platform or not renderer:
        return warnings

    p = platform.lower()
    expected = _PLATFORM_RENDERERS.get(p)
    if not expected:
        return warnings

    renderer_lower = renderer.lower()
    if p == "windows":
        if "direct3d11" not in renderer_lower and "d3d11" not in renderer_lower:
            warnings.append(
                f"GPU renderer '{renderer}' does not look like Windows (expected Direct3D11)."
            )
    elif p == "macos":
        if "metal" not in renderer_lower:
            warnings.append(
                f"GPU renderer '{renderer}' does not look like macOS (expected ANGLE Metal)."
            )
    elif p == "linux":
        if "vulkan" not in renderer_lower and "opengl" not in renderer_lower:
            warnings.append(
                f"GPU renderer '{renderer}' does not look like Linux (expected Vulkan/OpenGL)."
            )
    return warnings


def validate_user_agent(platform: _Platform | None, user_agent: str | None) -> list[str]:
    """Return warnings if the UA platform fragment contradicts the profile."""
    warnings: list[str] = []
    if not platform or not user_agent:
        return warnings

    p = platform.lower()
    expected = _UA_PLATFORM_FRAGMENTS.get(p, ())
    ua = user_agent

    # Also need to ensure it doesn't contain the *wrong* platform fragment.
    wrong_fragments: tuple[str, ...] = ()
    if p == "windows":
        wrong_fragments = ("Macintosh", "Mac OS X", "Linux")
    elif p == "macos":
        wrong_fragments = ("Windows NT", "Linux")
    elif p == "linux":
        wrong_fragments = ("Windows NT", "Macintosh", "Mac OS X")

    if expected and not any(fragment in ua for fragment in expected):
        warnings.append(
            f"User-Agent '{ua[:40]}...' is missing a {platform.title()} platform fragment."
        )

    for wrong in wrong_fragments:
        if wrong in ua:
            warnings.append(
                f"User-Agent '{ua[:40]}...' contains a contradictory platform fragment '{wrong}'."
            )
            break

    return warnings


def validate_hardware_concurrency(
    platform: _Platform | None,
    concurrency: int | None,
    device_memory: float | int | None = None,
) -> list[str]:
    """Return warnings if hardwareConcurrency/deviceMemory look implausible."""
    warnings: list[str] = []

    if concurrency is not None and (concurrency < 1 or concurrency > 64):
        warnings.append(
            f"hardwareConcurrency={concurrency} is outside the typical 1-64 range."
        )

    if device_memory is not None and device_memory not in STANDARD_DEVICE_MEMORY:
        warnings.append(
            f"deviceMemory={device_memory} GB is not a value real Chrome reports "
            f"(navigator.deviceMemory is capped at 8; use one of "
            f"{', '.join(str(x) for x in STANDARD_DEVICE_MEMORY)})."
        )

    if platform == "macos" and concurrency is not None and concurrency < 8:
        # Apple Silicon Macs overwhelmingly report 8+ cores.
        warnings.append(
            f"hardwareConcurrency={concurrency} is unusual for a modern macOS profile."
        )

    return warnings


def validate_screen_viewport(
    platform: _Platform | None,
    screen_width: int | None,
    screen_height: int | None,
    taskbar_height: int | None = None,
) -> list[str]:
    """Return warnings for implausible screen/viewport combinations."""
    warnings: list[str] = []
    sw = screen_width or 0
    sh = screen_height or 0

    if sw and sh:
        ratio = sw / sh
        common_ratios = [16 / 9, 16 / 10, 4 / 3, 21 / 9, 32 / 9]
        if not any(abs(ratio - r) < 0.05 for r in common_ratios):
            warnings.append(
                f"Screen ratio {sw}x{sh} ({ratio:.2f}) does not match common desktop ratios."
            )
        if sw < 800 or sh < 600:
            warnings.append(
                f"Screen resolution {sw}x{sh} is very small for a desktop browser."
            )

    tb = taskbar_height
    if tb is not None and tb < 0:
        warnings.append(f"taskbarHeight={tb} cannot be negative.")

    return warnings


def suggest_dpr_for(
    platform: _Platform | None, screen_width: int | None, screen_height: int | None
) -> float:
    """Suggest a plausible devicePixelRatio for a platform + screen.

    Returns 1.0 by default. macOS Retina panels and common HiDPI Windows
    resolutions get a 2.0 / 1.25 / 1.5 hint respectively.
    """
    p = (platform or "").lower()
    sw = screen_width or 0
    sh = screen_height or 0
    # Retina-class macOS panels report 2x.
    macos_retina = {(1440, 900), (1512, 982), (1728, 1117), (2560, 1600), (3024, 1964)}
    if p == "macos":
        return 2.0 if (sw, sh) in macos_retina else 1.0
    if p == "windows":
        if (sw, sh) == (3840, 2160):
            return 1.5
        if (sw, sh) in {(2560, 1440), (2560, 1080)}:
            return 1.25
        return 1.0
    # linux
    return 1.0


def validate_screen_chain(
    platform: _Platform | None,
    screen_width: int | None,
    screen_height: int | None,
    taskbar_height: int | None = None,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    device_pixel_ratio: float | None = None,
) -> list[str]:
    """Validate the screen / availScreen / outer / inner / DPR chain.

    Anti-bot scripts compare ``screen.availHeight`` (= screen − taskbar) with
    ``window.outerHeight`` and ``window.innerHeight``, and check that
    ``devicePixelRatio`` is plausible for the screen + platform. A single
    broken link (e.g. innerWidth > screen.width) is an instant fail.
    """
    warnings: list[str] = []
    sw = screen_width or 0
    sh = screen_height or 0
    if not sw or not sh:
        return warnings

    p = (platform or "").lower()
    tb = taskbar_height if taskbar_height is not None else _default_taskbar(platform)
    avail_h = sh - tb
    avail_w = sw  # taskbar rarely reduces availWidth on Win/Mac dock-edge cases
    if avail_h <= 0:
        warnings.append(
            f"taskbarHeight={tb} leaves no availHeight for screen {sw}x{sh}."
        )

    # viewport (inner) must fit inside availScreen, and outer ≈ availScreen.
    vw = viewport_width or 0
    vh = viewport_height or 0
    if vh and avail_h > 0 and vh > avail_h:
        warnings.append(
            f"viewport innerHeight={vh} exceeds availHeight={avail_h} "
            f"(screen {sh} − taskbar {tb}); a maximized window cannot exceed availHeight."
        )
    if vw and sw and vw > sw:
        warnings.append(
            f"viewport innerWidth={vw} exceeds screen.width={sw}; "
            "innerWidth must be ≤ screen.width or the page looks virtualized."
        )

    # outer − inner should approximate the platform chrome UI.
    chrome_ui = chrome_ui_height(platform)
    if vh and sh:
        outer_h_est = vh + chrome_ui
        if outer_h_est > sh:
            warnings.append(
                f"implied window outerHeight (~inner {vh} + chrome {chrome_ui} = {outer_h_est}) "
                f"exceeds screen.height={sh}; the window would be larger than the screen."
            )

    # devicePixelRatio plausibility per platform.
    if device_pixel_ratio is not None:
        dpr = float(device_pixel_ratio)
        if p == "macos" and dpr not in (1.0, 2.0, 3.0):
            warnings.append(
                f"devicePixelRatio={dpr} is unusual for macOS (expect 1.0 or 2.0, rarely 3.0)."
            )
        elif p == "windows" and dpr not in (1.0, 1.25, 1.5, 1.75, 2.0):
            warnings.append(
                f"devicePixelRatio={dpr} is unusual for Windows "
                "(expect 1.0/1.25/1.5/1.75/2.0)."
            )
        elif p == "linux" and dpr not in (1.0, 1.25, 1.5, 2.0):
            warnings.append(
                f"devicePixelRatio={dpr} is unusual for Linux (expect 1.0/1.25/1.5/2.0)."
            )

    return warnings


def validate_timezone_locale(
    timezone: str | None,
    locale: str | None,
    proxy_country: str | None = None,
    proxy_timezone: str | None = None,
) -> list[str]:
    """Return warnings when timezone/locale/proxy signals disagree at country level."""
    warnings: list[str] = []

    tz_country = _TZ_COUNTRY.get((timezone or "").strip()) if timezone else None
    locale_region = (locale.split("-")[-1] or "").upper() if locale else None

    if tz_country and locale_region and tz_country != locale_region:
        warnings.append(
            f"Timezone '{timezone}' is {tz_country} but locale region is "
            f"'{locale_region}'; they should be the same country."
        )

    if proxy_country:
        proxy_iso = _COUNTRY_ISO.get(proxy_country)
        if proxy_iso and locale_region and proxy_iso != locale_region:
            expected_locale = _COUNTRY_LOCALE_HINTS.get(proxy_country)
            warnings.append(
                f"Proxy country '{proxy_country}' ({proxy_iso}) usually pairs with "
                f"locale '{expected_locale}', not '{locale}'."
            )
        if proxy_iso and tz_country and proxy_iso != tz_country:
            warnings.append(
                f"Proxy country '{proxy_country}' ({proxy_iso}) does not match "
                f"timezone '{timezone}' ({tz_country})."
            )

    if proxy_timezone and timezone and proxy_timezone != timezone:
        warnings.append(
            f"Profile timezone '{timezone}' differs from proxy-detected timezone '{proxy_timezone}'."
        )

    return warnings


def validate_client_hints(
    platform: _Platform | None,
    brand: str | None,
    brand_version: str | None,
    platform_version: str | None,
) -> list[str]:
    """Return warnings for implausible Sec-CH-UA / platform version values."""
    warnings: list[str] = []

    if brand and brand.lower() not in {"chrome", "edge", "opera", "vivaldi", "firefox", "safari"}:
        warnings.append(f"Unknown browser brand '{brand}'.")

    if brand_version:
        try:
            major = int(brand_version.split(".")[0])
            if major < 80 or major > 200:
                warnings.append(f"brandVersion={brand_version} is outside typical stable Chrome range.")
        except ValueError:
            warnings.append(f"brandVersion='{brand_version}' is not a valid version string.")

    if platform == "windows" and platform_version:
        if not re.match(r"^\d+\.0\.\d+$", platform_version):
            warnings.append(
                f"platformVersion='{platform_version}' does not look like a Windows NT version (e.g. 10.0.19045)."
            )
    elif platform == "macos" and platform_version:
        if not re.match(r"^\d+_\d+(_\d+)?$", platform_version):
            warnings.append(
                f"platformVersion='{platform_version}' does not look like a macOS version (e.g. 13_5_1)."
            )

    return warnings


def validate_ua_brand_coherence(
    user_agent: str | None,
    brand_version: str | None,
    binary_version: str | None = None,
) -> list[str]:
    """Warn if the UA Chrome major, the Sec-CH-UA brand version, and the
    CloakBrowser binary Chromium version disagree.

    These three must report the *same* major version. A mismatch (e.g.
    UA says Chrome/146 but Sec-CH-UA says v="120") is one of the most reliable
    automated-browser tells, because stock Chrome never disagrees with itself.
    """
    warnings: list[str] = []
    ua_major = _chrome_major_from_ua(user_agent)
    brand_major = _major_from_version(brand_version)
    bin_major = _major_from_version(binary_version)

    if ua_major is not None and brand_major is not None and ua_major != brand_major:
        warnings.append(
            f"User-Agent reports Chrome/{ua_major} but Sec-CH-UA brand version is "
            f"{brand_major}; they must match (anti-bot systems cross-check these)."
        )

    # Only cross-check against the binary when it looks like a real Chrome
    # version (major >= 80), so test sentinel values like "0.0.0-test" don't
    # produce false positives.
    if bin_major is not None and bin_major >= 80:
        if brand_major is not None and brand_major != bin_major:
            warnings.append(
                f"Sec-CH-UA brand version {brand_major} differs from the CloakBrowser "
                f"binary Chromium {bin_major}; leave brand_version unset so it is "
                f"derived from the binary."
            )
        elif ua_major is not None and ua_major != bin_major:
            warnings.append(
                f"User-Agent reports Chrome/{ua_major} but the CloakBrowser binary is "
                f"Chromium {bin_major}; leave user_agent unset so it matches the binary."
            )

    return warnings


def validate_hardware_bundle(
    platform: _Platform | None,
    gpu_renderer: str | None,
    hardware_concurrency: int | None,
    device_memory: float | int | None,
    screen_width: int | None,
    screen_height: int | None,
) -> list[str]:
    """Warn when the GPU / cores / memory / screen combination is implausible
    as a single real machine (e.g. a flagship GPU with 2 cores, or 4K with a
    low-end integrated GPU and 4 GB)."""
    warnings: list[str] = []
    p = (platform or "").lower()
    r = (gpu_renderer or "").lower()

    high_end_gpu = any(
        tok in r
        for tok in ("rtx 4090", "rtx 4080", "rtx 3090", "rtx 3080", "rx 7900", "rx 6900")
    )
    if high_end_gpu and hardware_concurrency is not None and hardware_concurrency < 8:
        warnings.append(
            f"A high-end GPU ('{gpu_renderer}') with hardwareConcurrency="
            f"{hardware_concurrency} is implausible; such cards ship in 8+ core machines."
        )

    # A 4K screen with an entry-level integrated GPU is unusual.
    sw = screen_width or 0
    sh = screen_height or 0
    is_4k = sw >= 3840 and sh >= 2160
    low_end_gpu = any(tok in r for tok in ("iris", "uhd", "hd graphics"))
    if is_4k and low_end_gpu:
        warnings.append(
            f"A 4K screen ({sw}x{sh}) with an entry-level GPU ('{gpu_renderer}') "
            "is an unusual combination."
        )

    if p == "macos" and hardware_concurrency is not None and hardware_concurrency < 8:
        warnings.append(
            f"hardwareConcurrency={hardware_concurrency} is unusual for Apple Silicon "
            "(M-series Macs report 8+ cores)."
        )

    return warnings


def validate_fonts_for_spoofed_platform(
    platform: _Platform | None,
    fonts_dir: str | None,
    host_platform: _Platform | None,
) -> list[str]:
    """Warn when spoofing a non-host platform without the matching font pack.

    CloakBrowser checks the real font table (via ``fc-list`` on Linux) when
    spoofing Windows/macOS; without Segoe UI / SF fonts the canvas and font
    fingerprint leak the host's font set, which is an instant detection on
    Windows/macOS-spoofed profiles.
    """
    warnings: list[str] = []
    if not platform or not host_platform:
        return warnings
    p = platform.lower()
    h = host_platform.lower()
    if p == h:
        return warnings
    if p in ("windows", "macos") and not fonts_dir:
        flag = "--fingerprint-windows-font-metrics" if p == "windows" else ""
        extra = f" and consider {flag}" if flag else ""
        warnings.append(
            f"Spoofing {p} on a {h} host without --fonts-dir: the host font table "
            f"({h}) will leak through canvas/font fingerprinting. Set --fonts-dir to a "
            f"real {p} font directory{extra}."
        )
    return warnings


def validate_angle_backend(
    platform: _Platform | None,
    gpu_renderer: str | None,
    actual_backend: str | None,
) -> list[str]:
    """Warn when the actual ANGLE backend contradicts the spoofed GPU renderer.

    The manager runs software GL (SwiftShader) in the GPU-less VNC container
    while reporting a hardware renderer (D3D11/Metal/Vulkan). The reported
    string is spoofed correctly, but the *rendering path* is software, which
    can be revealed by WebGL performance timing and extension probing.
    """
    warnings: list[str] = []
    if not actual_backend or not gpu_renderer or not platform:
        return warnings
    backend = actual_backend.lower()
    renderer = gpu_renderer.lower()
    if "swiftshader" not in backend and "software" not in backend:
        return warnings
    # Only warn when the spoofed renderer claims a hardware backend.
    hw_claim = (
        "direct3d" in renderer or "metal" in renderer or "vulkan" in renderer or "opengl" in renderer
    )
    if hw_claim:
        warnings.append(
            f"The browser renders with {actual_backend} (software GL) but reports "
            f"'{gpu_renderer}'; performance/extension probing can reveal the mismatch. "
            "Acceptable inside the GPU-less container, but a real GPU would be more organic."
        )
    return warnings


# ── Device personas ──────────────────────────────────────────────────────────
#
# A persona is a fully-coherent, real-world machine: its screen, DPR, GPU,
# core count, memory, and platform version are the values that actual hardware
# reports. Building a fleet from different personas yields *diverse but
# individually coherent* profiles, instead of N copies of 1920×1080 + RTX 3070
# which anti-bot systems cluster on.

PERSONAS: list[dict[str, Any]] = [
    {
        "name": "win10-thinkpad-t14",
        "label": "ThinkPad T14 (Windows 10, Intel Iris Xe, 1920×1080@125%)",
        "platform": "windows",
        "fields": {
            "screen_width": 1920, "screen_height": 1080,
            "device_scale_factor": 1.25,
            "taskbar_height": 40,
            "gpu_vendor": "Google Inc. (Intel)",
            "gpu_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x00009A49) Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "hardware_concurrency": 8,
            "device_memory": 8,
            "brand": "chrome",
            "platform_version": "10.0.19045",
        },
    },
    {
        "name": "win11-rtx3070-desktop",
        "label": "Desktop (Windows 11, RTX 3070, 2560×1440)",
        "platform": "windows",
        "fields": {
            "screen_width": 2560, "screen_height": 1440,
            "device_scale_factor": 1.0,
            "taskbar_height": 48,
            "gpu_vendor": "Google Inc. (NVIDIA)",
            "gpu_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 (0x00002484) Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "hardware_concurrency": 16,
            "device_memory": 8,
            "brand": "chrome",
            "platform_version": "10.0.22631",
        },
    },
    {
        "name": "win10-amd-4k",
        "label": "Desktop (Windows 10, RX 7900, 4K@150%)",
        "platform": "windows",
        "fields": {
            "screen_width": 3840, "screen_height": 2160,
            "device_scale_factor": 1.5,
            "taskbar_height": 40,
            "gpu_vendor": "Google Inc. (AMD)",
            "gpu_renderer": "ANGLE (AMD, AMD Radeon RX 7900 XT (0x000073BF) Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "hardware_concurrency": 12,
            "device_memory": 8,
            "brand": "chrome",
            "platform_version": "10.0.19045",
        },
    },
    {
        "name": "mac-mbp-m2-14",
        "label": "MacBook Pro 14\" (M2, 1512×982 Retina, macOS 14)",
        "platform": "macos",
        "fields": {
            "screen_width": 1512, "screen_height": 982,
            "device_scale_factor": 2.0,
            "taskbar_height": 23,
            "gpu_vendor": "Google Inc. (Apple)",
            "gpu_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)",
            "hardware_concurrency": 10,
            "device_memory": 8,
            "brand": "chrome",
            "platform_version": "14_3",
        },
    },
    {
        "name": "mac-mba-m1",
        "label": "MacBook Air (M1, 1440×900 Retina, macOS 13)",
        "platform": "macos",
        "fields": {
            "screen_width": 1440, "screen_height": 900,
            "device_scale_factor": 2.0,
            "taskbar_height": 23,
            "gpu_vendor": "Google Inc. (Apple)",
            "gpu_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)",
            "hardware_concurrency": 8,
            "device_memory": 8,
            "brand": "chrome",
            "platform_version": "13_5_1",
        },
    },
    {
        "name": "linux-amd-desktop",
        "label": "Desktop (Linux, RX 6700, 1920×1080)",
        "platform": "linux",
        "fields": {
            "screen_width": 1920, "screen_height": 1080,
            "device_scale_factor": 1.0,
            "taskbar_height": 0,
            "gpu_vendor": "Google Inc. (AMD)",
            "gpu_renderer": "ANGLE (AMD, AMD Radeon RX 6700 XT (0x000073BF) Vulkan 1.3.268, Vulkan)",
            "hardware_concurrency": 12,
            "device_memory": 8,
            "brand": "chrome",
        },
    },
]


def list_personas() -> list[dict[str, Any]]:
    """Return persona summaries (name + label) for UI/CLI discovery."""
    return [{"name": p["name"], "label": p["label"], "platform": p["platform"]} for p in PERSONAS]


def list_persona_names() -> list[str]:
    return [p["name"] for p in PERSONAS]


def get_persona(name: str | None) -> dict[str, Any] | None:
    """Return the full persona dict for ``name`` (fields + platform), or None."""
    if not name:
        return None
    for p in PERSONAS:
        if p["name"] == name:
            return p
    return None


def suggest_persona(seed: int | None = None) -> dict[str, Any]:
    """Pick a deterministic persona from a fingerprint seed (stable per seed)."""
    import random as _r

    rng = _r.Random(seed if seed is not None else 0)
    return rng.choice(PERSONAS)


def analyze_profile(
    profile: dict[str, Any],
    *,
    binary_version: str | None = None,
    host_platform: str | None = None,
    actual_angle_backend: str | None = None,
) -> list[str]:
    """Run all coherence checks on a profile dict and return warnings.

    Environment-dependent checks (font-pack mismatch vs host OS, software-GL
    backend vs spoofed GPU) only fire when ``host_platform`` /
    ``actual_angle_backend`` are supplied — i.e. from the launch path — so the
    static editor view stays focused on profile-internal consistency.
    """
    warnings: list[str] = []
    platform = profile.get("platform") or "windows"
    screen_w = profile.get("screen_width")
    screen_h = profile.get("screen_height")
    taskbar = profile.get("taskbar_height")

    warnings.extend(validate_gpu_renderer(platform, profile.get("gpu_renderer")))
    warnings.extend(validate_user_agent(platform, profile.get("user_agent")))
    warnings.extend(
        validate_hardware_concurrency(
            platform,
            profile.get("hardware_concurrency"),
            profile.get("device_memory"),
        )
    )
    warnings.extend(validate_screen_viewport(platform, screen_w, screen_h, taskbar))

    # Screen chain (avail / outer / inner / DPR). The manager sizes the viewport
    # as screen_h − chrome UI (maximized window); validate that relationship.
    chrome_ui = chrome_ui_height(platform)
    viewport_h = (screen_h - chrome_ui) if screen_h else None
    viewport_w = screen_w
    warnings.extend(
        validate_screen_chain(
            platform,
            screen_w,
            screen_h,
            taskbar,
            viewport_w,
            viewport_h,
            profile.get("device_scale_factor"),
        )
    )

    warnings.extend(
        validate_timezone_locale(
            profile.get("timezone"),
            profile.get("locale"),
            profile.get("proxy_country"),
            profile.get("proxy_timezone"),
        )
    )
    warnings.extend(
        validate_client_hints(
            platform,
            profile.get("brand"),
            profile.get("brand_version"),
            profile.get("platform_version"),
        )
    )

    bin_ver = binary_version if binary_version is not None else get_binary_chromium_version()
    warnings.extend(
        validate_ua_brand_coherence(
            profile.get("user_agent"), profile.get("brand_version"), bin_ver
        )
    )

    warnings.extend(
        validate_hardware_bundle(
            platform,
            profile.get("gpu_renderer"),
            profile.get("hardware_concurrency"),
            profile.get("device_memory"),
            screen_w,
            screen_h,
        )
    )

    if host_platform:
        warnings.extend(
            validate_fonts_for_spoofed_platform(
                platform, profile.get("fonts_dir"), host_platform
            )
        )

    if actual_angle_backend:
        warnings.extend(
            validate_angle_backend(
                platform, profile.get("gpu_renderer"), actual_angle_backend
            )
        )

    return warnings


def suggest_viewport_height(screen_height: int, platform: _Platform | None) -> int:
    """Suggest an innerHeight matching platform chrome UI."""
    return max(600, screen_height - chrome_ui_height(platform))


def suggest_gpu_for_platform(platform: _Platform | None) -> dict[str, str] | None:
    """Return a sensible default GPU preset for the chosen platform.

    Linux no longer falls back to SwiftShader (a software-rendering tell); a
    real Vulkan desktop GPU is used instead.
    """
    defaults = {
        "windows": {
            "vendor": "Google Inc. (NVIDIA)",
            "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 (0x00002484) Direct3D11 vs_5_0 ps_5_0, D3D11)",
        },
        "macos": {
            "vendor": "Google Inc. (Apple)",
            "renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)",
        },
        "linux": {
            "vendor": "Google Inc. (AMD)",
            "renderer": "ANGLE (AMD, AMD Radeon RX 6700 XT (0x000073BF) Vulkan 1.3.268, Vulkan)",
        },
    }
    return defaults.get((platform or "").lower())

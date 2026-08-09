"""Cross-field consistency helpers for CloakBrowser profiles.

Anti-bot systems correlate many signals. This module detects contradictions
between platform, GPU, user agent, timezone, locale, screen size, etc., and
produces warnings / suggested corrections that the manager can surface in the
UI or auto-apply when safe.
"""

from __future__ import annotations

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

# Common timezone/locale mismatches that look synthetic.
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

_Platform = str  # keep type readable


def chrome_ui_height(platform: _Platform | None) -> int:
    """Return the recommended Chrome UI offset for the spoofed platform."""
    return _PLATFORM_CHROME_UI_HEIGHT.get((platform or "").lower(), 133)


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
    device_memory: int | None = None,
) -> list[str]:
    """Return warnings if hardwareConcurrency/deviceMemory look implausible."""
    warnings: list[str] = []
    if concurrency is not None and (concurrency < 1 or concurrency > 64):
        warnings.append(
            f"hardwareConcurrency={concurrency} is outside the typical 1-64 range."
        )

    if device_memory is not None and device_memory not in (0.25, 0.5, 1, 2, 4, 8, 16, 32, 64):
        warnings.append(
            f"deviceMemory={device_memory} GB is not one of the standard Chrome values."
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


def validate_timezone_locale(
    timezone: str | None,
    locale: str | None,
    proxy_country: str | None = None,
    proxy_timezone: str | None = None,
) -> list[str]:
    """Return warnings when timezone/locale/proxy signals disagree."""
    warnings: list[str] = []

    if timezone and locale:
        # Very rough heuristic: the locale region should not strongly clash with
        # the timezone region. e.g. America/* with ja-JP is suspicious.
        tz_region = timezone.split("/")[0].lower()
        locale_region = (locale.split("-")[-1] or "").lower()

        region_locale_map: dict[str, tuple[str, ...]] = {
            "america": ("us", "ca", "mx", "br", "ar", "cl", "co", "pe"),
            "europe": ("de", "fr", "gb", "uk", "nl", "it", "es", "pl", "ie", "se", "no", "dk", "fi"),
            "asia": ("jp", "kr", "cn", "in", "sg", "th", "vn", "id", "ph"),
            "africa": ("za", "ng", "ke", "eg", "ma"),
            "australia": ("au", "nz"),
            "pacific": ("au", "nz", "fj"),
        }
        allowed = region_locale_map.get(tz_region, ())
        if allowed and locale_region not in allowed:
            warnings.append(
                f"Timezone region '{tz_region}' and locale region '{locale_region}' look mismatched."
            )

    if proxy_country and locale:
        expected_locale = _COUNTRY_LOCALE_HINTS.get(proxy_country)
        if expected_locale and not locale.lower().startswith(
            expected_locale.split("-")[0].lower()
        ):
            warnings.append(
                f"Proxy country '{proxy_country}' usually pairs with locale '{expected_locale}', not '{locale}'."
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


def analyze_profile(profile: dict[str, Any]) -> list[str]:
    """Run all coherence checks on a profile dict and return warnings."""
    warnings: list[str] = []
    platform = profile.get("platform") or "windows"

    warnings.extend(
        validate_gpu_renderer(platform, profile.get("gpu_renderer"))
    )
    warnings.extend(
        validate_user_agent(platform, profile.get("user_agent"))
    )
    warnings.extend(
        validate_hardware_concurrency(
            platform,
            profile.get("hardware_concurrency"),
            profile.get("device_memory"),
        )
    )
    warnings.extend(
        validate_screen_viewport(
            platform,
            profile.get("screen_width"),
            profile.get("screen_height"),
            profile.get("taskbar_height"),
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

    return warnings


def suggest_viewport_height(screen_height: int, platform: _Platform | None) -> int:
    """Suggest an innerHeight matching platform chrome UI."""
    return max(600, screen_height - chrome_ui_height(platform))


def suggest_gpu_for_platform(platform: _Platform | None) -> dict[str, str] | None:
    """Return a sensible default GPU preset for the chosen platform."""
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
            "vendor": "Google Inc. (NVIDIA)",
            "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 (0x00001B80) Vulkan 1.3.204, SwiftShader)",
        },
    }
    return defaults.get((platform or "").lower())

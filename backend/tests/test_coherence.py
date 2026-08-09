"""Tests for fingerprint coherence engine."""

import pytest
from ..fingerprint_coherence import (
    STANDARD_DEVICE_MEMORY,
    analyze_profile,
    detect_host_platform,
    get_binary_chromium_version,
    get_persona,
    list_persona_names,
    list_personas,
    suggest_dpr_for,
    suggest_persona,
    validate_angle_backend,
    validate_fonts_for_spoofed_platform,
    validate_gpu_renderer,
    validate_hardware_bundle,
    validate_hardware_concurrency,
    validate_screen_chain,
    validate_screen_viewport,
    validate_timezone_locale,
    validate_ua_brand_coherence,
    validate_user_agent,
    validate_client_hints,
    chrome_ui_height,
    suggest_viewport_height,
    suggest_gpu_for_platform,
)


class TestGpuRenderer:
    def test_windows_d3d11_valid(self):
        w = validate_gpu_renderer("windows", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)")
        assert len(w) == 0

    def test_windows_no_d3d_fails(self):
        w = validate_gpu_renderer("windows", "ANGLE (Apple, ANGLE Metal Renderer: Apple M3)")
        assert len(w) == 1
        assert "Direct3D11" in w[0]

    def test_macos_metal_valid(self):
        w = validate_gpu_renderer("macos", "ANGLE (Apple, ANGLE Metal Renderer: Apple M3)")
        assert len(w) == 0

    def test_macos_no_metal_fails(self):
        w = validate_gpu_renderer("macos", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11)")
        assert len(w) == 1
        assert "Metal" in w[0]

    def test_linux_vulkan_or_opengl_valid(self):
        w = validate_gpu_renderer("linux", "ANGLE (NVIDIA, Vulkan 1.3)")
        assert len(w) == 0

    def test_no_renderer_skips(self):
        w = validate_gpu_renderer("windows", None)
        assert len(w) == 0

    def test_no_platform_skips(self):
        w = validate_gpu_renderer(None, "anything")
        assert len(w) == 0


class TestUserAgent:
    def test_windows_ua_ok(self):
        w = validate_user_agent("windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        assert len(w) == 0

    def test_windows_ua_missing(self):
        w = validate_user_agent("windows", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
        assert len(w) >= 1

    def test_macos_ua_wrong_platform(self):
        w = validate_user_agent("macos", "Mozilla/5.0 (X11; Linux x86_64)")
        assert len(w) >= 1


class TestHardwareConcurrency:
    def test_out_of_range(self):
        w = validate_hardware_concurrency(None, 128, 8)
        assert any("outside" in x for x in w)

    def test_non_standard_device_memory(self):
        w = validate_hardware_concurrency(None, 8, 3)
        assert any("real Chrome" in x for x in w)

    def test_valid(self):
        w = validate_hardware_concurrency(None, 8, 8)
        assert len(w) == 0

    def test_macos_low_cores(self):
        w = validate_hardware_concurrency("macos", 2, 8)
        assert any("macOS" in x for x in w)

    def test_device_memory_capped_at_eight(self):
        # Values > 8 are impossible in real Chrome and must warn.
        for bad in (12, 16, 32, 64):
            w = validate_hardware_concurrency(None, 8, bad)
            assert any("real Chrome" in x for x in w), f"deviceMemory={bad} should warn"

    def test_device_memory_standard_values_ok(self):
        for ok in STANDARD_DEVICE_MEMORY:
            assert validate_hardware_concurrency(None, 8, ok) == [] or all(
                "real Chrome" not in x for x in validate_hardware_concurrency(None, 8, ok)
            )


class TestScreenViewport:
    def test_unusual_ratio(self):
        w = validate_screen_viewport(None, 1920, 500, None)
        assert any("ratio" in x for x in w)

    def test_valid_ratio(self):
        w = validate_screen_viewport(None, 1920, 1080, None)
        assert len(w) == 0

    def test_negative_taskbar(self):
        w = validate_screen_viewport(None, 1920, 1080, -1)
        assert any("negative" in x for x in w)


class TestTimezoneLocale:
    def test_america_asia_locale_mismatch(self):
        w = validate_timezone_locale("America/New_York", "ja-JP", None, None)
        assert len(w) >= 1

    def test_europe_europe_locale_match(self):
        w = validate_timezone_locale("Europe/Berlin", "de-DE", None, None)
        assert len(w) == 0

    def test_proxy_country_mismatch(self):
        w = validate_timezone_locale(None, "ja-JP", "United States", None)
        assert any("locale" in x.lower() for x in w)

    def test_proxy_timezone_mismatch(self):
        w = validate_timezone_locale("America/New_York", "en-US", None, "Europe/London")
        assert any("differs" in x for x in w)


class TestClientHints:
    def test_unknown_brand(self):
        w = validate_client_hints(None, "brave", None, None)
        assert any("Unknown" in x for x in w)

    def test_platform_version_windows(self):
        w = validate_client_hints("windows", "chrome", "120.0.6099.109", "14.0")
        assert any("Windows NT" in x for x in w)

    def test_platform_version_macos(self):
        w = validate_client_hints("macos", "chrome", "120.0.6099.109", "13_5_1")
        assert len(w) == 0


class TestChromeUiHeight:
    def test_windows(self):
        assert chrome_ui_height("windows") == 133

    def test_macos(self):
        assert chrome_ui_height("macos") == 91

    def test_linux(self):
        assert chrome_ui_height("linux") == 80

    def test_unknown_falls_back_to_windows(self):
        assert chrome_ui_height(None) == 133
        assert chrome_ui_height("unknown") == 133


class TestSuggestions:
    def test_viewport_height(self):
        assert suggest_viewport_height(1080, "windows") == 947
        assert suggest_viewport_height(1080, "macos") == 989

    def test_gpu_for_platform(self):
        gpu = suggest_gpu_for_platform("macos")
        assert gpu is not None
        assert "Metal" in gpu["renderer"]

        gpu = suggest_gpu_for_platform("windows")
        assert gpu is not None
        assert "Direct3D11" in gpu["renderer"]


class TestAnalyzeProfile:
    def test_coherent_profile_no_warnings(self):
        profile = {
            "platform": "windows",
            "gpu_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "gpu_vendor": "Google Inc. (NVIDIA)",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "screen_width": 1920,
            "screen_height": 1080,
            "hardware_concurrency": 8,
            "device_memory": 8,
            "timezone": "America/New_York",
            "locale": "en-US",
            "brand": "chrome",
            "brand_version": "120.0.6099.109",
            "platform_version": "10.0.19045",
        }
        w = analyze_profile(profile)
        assert len(w) == 0, f"Expected no warnings, got: {w}"

    def test_incoherent_profile_has_warnings(self):
        profile = {
            "platform": "macos",
            "gpu_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "gpu_vendor": "Google Inc. (NVIDIA)",
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "screen_width": 1920,
            "screen_height": 1080,
            "hardware_concurrency": 2,
            "device_memory": 8,
            "timezone": "Asia/Tokyo",
            "locale": "de-DE",
        }
        w = analyze_profile(profile)
        assert len(w) > 0, "Expected warnings for incoherent profile"

    def test_empty_profile_has_no_warnings(self):
        w = analyze_profile({})
        assert len(w) == 0


# ── UA ↔ brand ↔ binary coherence ────────────────────────────────────────────


class TestUaBrandCoherence:
    def test_ua_brand_mismatch_warns(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        w = validate_ua_brand_coherence(ua, "120.0.6099.109")
        assert any("120" in x and "146" in x for x in w)

    def test_ua_brand_match_ok(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36"
        assert validate_ua_brand_coherence(ua, "146.0.7680.177.5") == []

    def test_binary_mismatch_warns(self):
        # UA 146 + brand 146 (consistent) but binary is 144 → drift.
        ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36"
        w = validate_ua_brand_coherence(ua, "146.0.0.0", binary_version="144.0.0.0")
        assert any("144" in x for x in w)

    def test_test_sentinel_binary_skipped(self):
        # The test mock sets CHROMIUM_VERSION="0.0.0-test" (major 0); the binary
        # cross-check must NOT fire on that sentinel.
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36"
        assert validate_ua_brand_coherence(ua, "146.0.0.0", binary_version="0.0.0-test") == []

    def test_no_chrome_in_ua_skips(self):
        assert validate_ua_brand_coherence("Mozilla/5.0 (Macintosh)", "120.0.0.0") == []
        assert validate_ua_brand_coherence(None, None) == []


# ── Screen chain / DPR ───────────────────────────────────────────────────────


class TestScreenChain:
    def test_viewport_exceeds_avail_warns(self):
        w = validate_screen_chain("windows", 1920, 1080, 40, 1920, 1080)
        # innerHeight 1080 > availHeight (1080-40=1040) → warn
        assert any("availHeight" in x for x in w)

    def test_consistent_maximized_ok(self):
        w = validate_screen_chain("windows", 1920, 1080, 40, 1920, 947)
        assert w == []

    def test_inner_exceeds_screen_warns(self):
        w = validate_screen_chain("windows", 1366, 768, 0, 1920, 700)
        assert any("innerWidth" in x for x in w)

    def test_macos_retina_dpr_ok(self):
        assert validate_screen_chain("macos", 1512, 982, 23, 1512, 891, 2.0) == []

    def test_macos_bad_dpr_warns(self):
        w = validate_screen_chain("macos", 1512, 982, 23, 1512, 891, 1.25)
        assert any("devicePixelRatio" in x for x in w)


class TestSuggestDpr:
    def test_macos_retina(self):
        assert suggest_dpr_for("macos", 1512, 982) == 2.0
        assert suggest_dpr_for("macos", 1440, 900) == 2.0

    def test_windows_4k(self):
        assert suggest_dpr_for("windows", 3840, 2160) == 1.5
        assert suggest_dpr_for("windows", 2560, 1440) == 1.25
        assert suggest_dpr_for("windows", 1920, 1080) == 1.0


# ── Hardware bundle ──────────────────────────────────────────────────────────


class TestHardwareBundle:
    def test_high_end_gpu_low_cores_warns(self):
        w = validate_hardware_bundle(
            "windows",
            "ANGLE (NVIDIA, NVIDIA GeForce RTX 3090 Direct3D11, D3D11)",
            4, 8, 2560, 1440,
        )
        assert any("high-end GPU" in x for x in w)

    def test_balanced_bundle_ok(self):
        w = validate_hardware_bundle(
            "windows",
            "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11, D3D11)",
            8, 8, 1920, 1080,
        )
        assert w == []

    def test_macos_low_cores_warns(self):
        w = validate_hardware_bundle("macos", "ANGLE (Apple, Metal Renderer: Apple M2)", 4, 8, 1512, 982)
        assert any("Apple Silicon" in x for x in w)


# ── Fonts / angle backend ─────────────────────────────────────────────────────


class TestFontsForSpoofedPlatform:
    def test_windows_on_linux_without_fonts_warns(self):
        w = validate_fonts_for_spoofed_platform("windows", None, "linux")
        assert any("font" in x for x in w)

    def test_windows_on_linux_with_fonts_ok(self):
        assert validate_fonts_for_spoofed_platform("windows", "/fonts/win10", "linux") == []

    def test_same_host_skips(self):
        assert validate_fonts_for_spoofed_platform("linux", None, "linux") == []


class TestAngleBackend:
    def test_swiftshader_vs_d3d11_warns(self):
        w = validate_angle_backend(
            "windows",
            "ANGLE (NVIDIA, GeForce RTX 3070 Direct3D11, D3D11)",
            "swiftshader",
        )
        assert any("SwiftShader" in x or "swiftshader" in x or "software" in x for x in w)

    def test_no_backend_skips(self):
        assert validate_angle_backend("windows", "ANGLE (NVIDIA, RTX 3070 D3D11)", None) == []


# ── Personas ──────────────────────────────────────────────────────────────────


class TestPersonas:
    def test_list_nonempty(self):
        names = list_persona_names()
        assert len(names) >= 5
        assert "win11-rtx3070-desktop" in names

    def test_get_persona_fields(self):
        p = get_persona("mac-mbp-m2-14")
        assert p is not None
        assert p["platform"] == "macos"
        assert p["fields"]["device_memory"] == 8
        assert p["fields"]["device_scale_factor"] == 2.0

    def test_unknown_persona_none(self):
        assert get_persona("nope") is None

    def test_suggest_persona_deterministic(self):
        assert suggest_persona(42)["name"] == suggest_persona(42)["name"]

    def test_list_personas_summaries(self):
        for s in list_personas():
            assert {"name", "label", "platform"} <= set(s.keys())


# ── analyze_profile with env signals ──────────────────────────────────────────


class TestAnalyzeWithEnv:
    def test_host_font_warning_when_spoofing_offhost(self):
        profile = {"platform": "windows"}  # no fonts_dir
        w = analyze_profile(profile, host_platform="linux")
        assert any("font" in x for x in w)

    def test_angle_backend_warning_at_launch(self):
        profile = {
            "platform": "windows",
            "gpu_renderer": "ANGLE (NVIDIA, RTX 3070 Direct3D11, D3D11)",
        }
        w = analyze_profile(profile, actual_angle_backend="swiftshader")
        assert any("software" in x or "SwiftShader" in x for x in w)

    def test_static_analyze_no_env_warnings(self):
        # Without env signals, fonts/angle checks must not fire.
        profile = {
            "platform": "windows",
            "gpu_renderer": "ANGLE (NVIDIA, RTX 3070 Direct3D11, D3D11)",
        }
        w = analyze_profile(profile)
        assert not any("font" in x for x in w)
        assert not any("software" in x for x in w)


# ── Country-level timezone/locale ─────────────────────────────────────────────


class TestTimezoneLocaleCountry:
    def test_london_german_locale_mismatch(self):
        w = validate_timezone_locale("Europe/London", "de-DE", None, None)
        assert any("United Kingdom" in x or "GB" in x or "Germany" in x or "DE" in x for x in w)

    def test_newyork_us_locale_ok(self):
        assert validate_timezone_locale("America/New_York", "en-US", None, None) == []

    def test_proxy_country_timezone_mismatch(self):
        w = validate_timezone_locale("America/New_York", "en-US", "United Kingdom", None)
        assert any("United Kingdom" in x for x in w)


# ── Binary version lookup ─────────────────────────────────────────────────────


class TestBinaryVersion:
    def test_returns_test_sentinel(self):
        # conftest mocks cloakbrowser.config.CHROMIUM_VERSION = "0.0.0-test"
        assert get_binary_chromium_version() == "0.0.0-test"

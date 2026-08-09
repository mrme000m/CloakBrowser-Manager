"""Tests for fingerprint coherence engine."""

import pytest
from ..fingerprint_coherence import (
    analyze_profile,
    validate_gpu_renderer,
    validate_user_agent,
    validate_hardware_concurrency,
    validate_screen_viewport,
    validate_timezone_locale,
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
        assert any("standard" in x for x in w)

    def test_valid(self):
        w = validate_hardware_concurrency(None, 8, 8)
        assert len(w) == 0

    def test_macos_low_cores(self):
        w = validate_hardware_concurrency("macos", 2, 8)
        assert any("macOS" in x for x in w)


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

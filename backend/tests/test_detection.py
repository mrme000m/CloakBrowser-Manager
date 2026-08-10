"""Tests for the live detection-report comparison (evaluate_detection_report).

These exercise the pure comparison logic without launching a browser. The
in-page JS probe (DETECTION_PROBE_JS) can't run without a real CloakBrowser
launch, but the comparison function that turns its output into pass/fail
checks is fully unit-testable with crafted `actual` dicts.
"""

from __future__ import annotations

from backend.main import _is_private_ip, evaluate_detection_report


def _ua(major: int) -> str:
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
    )


def test_ua_sec_ch_ua_match_passes():
    actual = {"userAgent": _ua(146), "uaDataBrands": [{"brand": "Google Chrome", "version": "146"}]}
    r = evaluate_detection_report(actual, {})
    check = next(c for c in r["checks"] if c["test"] == "UA ↔ Sec-CH-UA version")
    assert check["status"] == "pass"


def test_ua_sec_ch_ua_mismatch_fails():
    actual = {"userAgent": _ua(146), "uaDataBrands": [{"brand": "Google Chrome", "version": "120"}]}
    r = evaluate_detection_report(actual, {})
    check = next(c for c in r["checks"] if c["test"] == "UA ↔ Sec-CH-UA version")
    assert check["status"] == "fail"
    assert check["actual"] == 120 and check["expected"] == 146


def test_device_memory_over_eight_fails():
    actual = {"userAgent": _ua(146), "deviceMemory": 16}
    r = evaluate_detection_report(actual, {"device_memory": 8})
    cap = next(c for c in r["checks"] if c["test"] == "deviceMemory cap")
    assert cap["status"] == "fail"
    assert r["failed"] >= 1


def test_device_memory_matches_expected_passes():
    actual = {"userAgent": _ua(146), "deviceMemory": 8}
    r = evaluate_detection_report(actual, {"device_memory": 8})
    mem = next(c for c in r["checks"] if c["test"] == "deviceMemory")
    assert mem["status"] == "pass"


def test_webgl_renderer_mismatch_fails():
    actual = {
        "userAgent": _ua(146),
        "webgl": {"vendor": "Google Inc.", "renderer": "ANGLE (SwiftShader)"},
    }
    expected = {"gpu_renderer": "ANGLE (NVIDIA, RTX 3070 Direct3D11, D3D11)"}
    r = evaluate_detection_report(actual, expected)
    rnd = next(c for c in r["checks"] if c["test"] == "WebGL renderer")
    assert rnd["status"] == "fail"


def test_webgl_renderer_platform_mismatch_fails():
    # macos platform but a Windows D3D11 renderer → platform-consistency fail.
    actual = {
        "userAgent": _ua(146),
        "webgl": {"renderer": "ANGLE (NVIDIA, RTX 3070 Direct3D11, D3D11)"},
    }
    r = evaluate_detection_report(actual, {"platform": "macos"})
    plat = next(c for c in r["checks"] if c["test"] == "WebGL renderer matches platform")
    assert plat["status"] == "fail"


def test_timezone_locale_match_passes():
    actual = {"userAgent": _ua(146), "timeZone": "America/New_York", "languages": ["en-US"]}
    r = evaluate_detection_report(actual, {"timezone": "America/New_York", "locale": "en-US"})
    tz = next(c for c in r["checks"] if c["test"] == "timezone")
    loc = next(c for c in r["checks"] if c["test"].startswith("locale"))
    assert tz["status"] == "pass" and loc["status"] == "pass"


def test_screen_and_dpr_match_passes():
    actual = {
        "userAgent": _ua(146),
        "screen": {"width": 1512, "height": 982, "availWidth": 1512, "availHeight": 959},
        "window": {"innerWidth": 1512, "innerHeight": 891, "outerWidth": 1512, "outerHeight": 982, "devicePixelRatio": 2},
        "devicePixelRatio": 2,
    }
    expected = {
        "platform": "macos",
        "screen_width": 1512,
        "screen_height": 982,
        "device_scale_factor": 2.0,
        "taskbar_height": 23,
    }
    r = evaluate_detection_report(actual, expected)
    assert all(c["status"] == "pass" for c in r["checks"] if "screen" in c["test"] or "devicePixelRatio" in c["test"] or "chrome UI" in c["test"])


def test_webrtc_leak_fails_against_exit_ip():
    actual = {"userAgent": _ua(146), "webrtc": {"checked": True, "ips": ["203.0.113.5", "8.8.8.8"]}}
    # exit IP is 203.0.113.5; the 8.8.8.8 candidate is a non-proxy public IP → leak.
    r = evaluate_detection_report(actual, {"exit_ip": "203.0.113.5"})
    webrtc = next(c for c in r["checks"] if c["test"] == "WebRTC IP leak")
    assert webrtc["status"] == "fail"


def test_webrtc_no_leak_passes():
    actual = {"userAgent": _ua(146), "webrtc": {"checked": True, "ips": ["203.0.113.5"]}}
    r = evaluate_detection_report(actual, {"exit_ip": "203.0.113.5"})
    webrtc = next(c for c in r["checks"] if c["test"] == "WebRTC IP leak")
    assert webrtc["status"] == "pass"


def test_platform_font_missing_warns():
    actual = {"userAgent": _ua(146), "fonts": {"detected": ["Liberation Sans"]}}
    r = evaluate_detection_report(actual, {"platform": "windows"})
    font = next(c for c in r["checks"] if "Segoe UI" in c["test"])
    assert font["status"] == "warn"


def test_coherence_warnings_propagated():
    r = evaluate_detection_report({"userAgent": _ua(146)}, {}, coherence_warnings=["x", "y"])
    assert r["coherence_warnings"] == ["x", "y"]


# ── Automation / identity tells (H1/H2/H6/H7) ──────────────────────────────────


def test_webdriver_truthy_fails():
    actual = {"userAgent": _ua(146), "webdriver": True}
    r = evaluate_detection_report(actual, {"platform": "windows"})
    wd = next(c for c in r["checks"] if c["test"] == "navigator.webdriver")
    assert wd["status"] == "fail" and wd["actual"] is True


def test_webdriver_false_passes():
    actual = {"userAgent": _ua(146), "webdriver": False}
    r = evaluate_detection_report(actual, {"platform": "windows"})
    wd = next(c for c in r["checks"] if c["test"] == "navigator.webdriver")
    assert wd["status"] == "pass"


def test_navigator_platform_match_passes():
    actual = {"userAgent": _ua(146), "platform": "Win32"}
    r = evaluate_detection_report(actual, {"platform": "windows"})
    np = next(c for c in r["checks"] if c["test"] == "navigator.platform")
    assert np["status"] == "pass" and np["expected"] == "Win32"


def test_navigator_platform_mismatch_fails():
    actual = {"userAgent": _ua(146), "platform": "Linux x86_64"}
    r = evaluate_detection_report(actual, {"platform": "windows"})
    np = next(c for c in r["checks"] if c["test"] == "navigator.platform")
    assert np["status"] == "fail"


def test_ua_data_platform_match_passes():
    actual = {"userAgent": _ua(146), "uaDataPlatform": "Windows"}
    r = evaluate_detection_report(actual, {"platform": "windows"})
    ch = next(c for c in r["checks"] if c["test"] == "Sec-CH-UA-Platform")
    assert ch["status"] == "pass" and ch["expected"] == "Windows"


def test_ua_data_platform_mismatch_fails():
    actual = {"userAgent": _ua(146), "uaDataPlatform": "Linux"}
    r = evaluate_detection_report(actual, {"platform": "windows"})
    ch = next(c for c in r["checks"] if c["test"] == "Sec-CH-UA-Platform")
    assert ch["status"] == "fail"


def test_ua_data_platform_absent_warns():
    actual = {"userAgent": _ua(146)}  # no uaDataPlatform key
    r = evaluate_detection_report(actual, {"platform": "windows"})
    ch = next(c for c in r["checks"] if c["test"] == "Sec-CH-UA-Platform")
    assert ch["status"] == "warn"


def test_webgl_vendor_match_passes():
    actual = {"userAgent": _ua(146), "webgl": {"vendor": "Google Inc. (NVIDIA)", "renderer": "x"}}
    r = evaluate_detection_report(actual, {"gpu_vendor": "Google Inc. (NVIDIA)"})
    v = next(c for c in r["checks"] if c["test"] == "WebGL vendor")
    assert v["status"] == "pass"


def test_webgl_vendor_mismatch_fails():
    actual = {"userAgent": _ua(146), "webgl": {"vendor": "Google Inc.", "renderer": "x"}}
    r = evaluate_detection_report(actual, {"gpu_vendor": "Google Inc. (NVIDIA)"})
    v = next(c for c in r["checks"] if c["test"] == "WebGL vendor")
    assert v["status"] == "fail"


def test_plugins_five_passes():
    actual = {"userAgent": _ua(146), "automation": {"plugins": 5}}
    r = evaluate_detection_report(actual, {})
    p = next(c for c in r["checks"] if c["test"] == "navigator.plugins")
    assert p["status"] == "pass"


def test_plugins_not_five_warns():
    actual = {"userAgent": _ua(146), "automation": {"plugins": 0}}
    r = evaluate_detection_report(actual, {})
    p = next(c for c in r["checks"] if c["test"] == "navigator.plugins")
    assert p["status"] == "warn"


def test_window_chrome_absent_fails():
    actual = {"userAgent": _ua(146), "automation": {"hasChrome": False, "chromeRuntime": False}}
    r = evaluate_detection_report(actual, {})
    c = next(c for c in r["checks"] if c["test"] == "window.chrome")
    assert c["status"] == "fail"


def test_chrome_runtime_present_warns():
    actual = {"userAgent": _ua(146), "automation": {"hasChrome": True, "chromeRuntime": True}}
    r = evaluate_detection_report(actual, {})
    c = next(c for c in r["checks"] if c["test"] == "chrome.runtime")
    assert c["status"] == "warn"


def test_window_chrome_present_no_runtime_passes():
    actual = {"userAgent": _ua(146), "automation": {"hasChrome": True, "chromeRuntime": False}}
    r = evaluate_detection_report(actual, {})
    c = next(c for c in r["checks"] if c["test"] == "window.chrome")
    assert c["status"] == "pass"


def test_max_touch_points_desktop_passes():
    actual = {"userAgent": _ua(146), "automation": {"maxTouchPoints": 0}}
    r = evaluate_detection_report(actual, {"has_touch": False})
    m = next(c for c in r["checks"] if c["test"] == "navigator.maxTouchPoints")
    assert m["status"] == "pass"


def test_max_touch_points_touch_mismatch_warns():
    actual = {"userAgent": _ua(146), "automation": {"maxTouchPoints": 0}}
    r = evaluate_detection_report(actual, {"has_touch": True})
    m = next(c for c in r["checks"] if c["test"] == "navigator.maxTouchPoints")
    assert m["status"] == "warn"


def test_notification_permission_default_passes():
    actual = {"userAgent": _ua(146), "automation": {"notificationPermission": "default"}}
    r = evaluate_detection_report(actual, {})
    n = next(c for c in r["checks"] if c["test"] == "Notification.permission")
    assert n["status"] == "pass"


def test_notification_permission_granted_warns():
    actual = {"userAgent": _ua(146), "automation": {"notificationPermission": "granted"}}
    r = evaluate_detection_report(actual, {})
    n = next(c for c in r["checks"] if c["test"] == "Notification.permission")
    assert n["status"] == "warn"


def test_color_depth_non_standard_warns():
    actual = {"userAgent": _ua(146), "screen": {"colorDepth": 16, "width": 1920, "height": 1080}}
    r = evaluate_detection_report(actual, {})
    cd = next(c for c in r["checks"] if c["test"] == "screen.colorDepth")
    assert cd["status"] == "warn"


def test_color_depth_24_passes():
    actual = {"userAgent": _ua(146), "screen": {"colorDepth": 24, "width": 1920, "height": 1080}}
    r = evaluate_detection_report(actual, {})
    cd = next(c for c in r["checks"] if c["test"] == "screen.colorDepth")
    assert cd["status"] == "pass"


def test_is_private_ip():
    assert _is_private_ip("127.0.0.1")
    assert _is_private_ip("192.168.1.1")
    assert _is_private_ip("10.0.0.1")
    assert _is_private_ip("172.16.0.1")
    assert _is_private_ip("fe80::1")
    assert not _is_private_ip("203.0.113.5")
    assert not _is_private_ip("8.8.8.8")

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


def test_is_private_ip():
    assert _is_private_ip("127.0.0.1")
    assert _is_private_ip("192.168.1.1")
    assert _is_private_ip("10.0.0.1")
    assert _is_private_ip("172.16.0.1")
    assert _is_private_ip("fe80::1")
    assert not _is_private_ip("203.0.113.5")
    assert not _is_private_ip("8.8.8.8")

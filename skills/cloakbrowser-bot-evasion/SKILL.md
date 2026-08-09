---
name: CloakBrowser Manager — Organic Fingerprint & Bot Detection Evasion
description: >
  Create organic, detection-resistant browser profiles in CloakBrowser-Manager.
  Apply when the user wants to configure a profile to evade bot detection,
  understand fingerprint fields, align proxy/timezone/locale/GPU for coherence,
  run automated detection tests, or interpret coherence warnings.
---

# CloakBrowser-Manager Organic Fingerprint & Bot Detection Evasion Guide

Use this skill when working in a CloakBrowser-Manager codebase or container to
create profiles that exhibit coherent, organic device fingerprints resistant to
popular bot-detection suites.

## Quick Check

```bash
# Is CloakBrowser-Manager running?
curl http://localhost:8080/api/status
# List profiles
curl http://localhost:8080/api/profiles | jq '.[] | {id, name, platform, coherence_warnings}'
```

## Creating an Organic Profile

The most important principle: **every signal must agree**. Anti-bot scripts
correlate screen size, GPU, platform, UA, timezone, locale, WebRTC, and hardware
signals. A single mismatch will flag you.

### CLI template

```bash
cbpm profiles create \
  --name "organic-windows-us" \
  --platform windows \
  --gpu-vendor "Google Inc. (NVIDIA)" \
  --gpu-renderer "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 (0x00002484) Direct3D11 vs_5_0 ps_5_0, D3D11)" \
  --hardware-concurrency 8 \
  --device-memory 8 \
  --timezone America/New_York \
  --locale en-US \
  --geoip true \
  --webrtc-ip auto \
  --geolocation-lat 40.7128 \
  --geolocation-lon -74.0060 \
  --brand chrome \
  --brand-version 120.0.6099.109 \
  --platform-version 10.0.19045 \
  --noise-enabled true \
  --humanize true \
  --human-preset careful \
  --clear-on-launch false
```

### macOS variant

```bash
cbpm profiles create \
  --name "organic-macos" \
  --platform macos \
  --gpu-vendor "Google Inc. (Apple)" \
  --gpu-renderer "ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)" \
  --hardware-concurrency 10 \
  --device-memory 16 \
  --timezone America/Los_Angeles \
  --locale en-US \
  --geoip true \
  --webrtc-ip auto \
  --brand chrome \
  --platform-version 13_5_1
```

## Field Reference

### Platform coherence groups

| Field | Windows | macOS | Linux |
|-------|---------|-------|-------|
| GPU renderer | ANGLE + D3D11 | ANGLE Metal | Vulkan/OpenGL |
| UA fragment | Windows NT | Macintosh/Mac OS X | Linux/X11 |
| platformVersion | 10.0.19045 | 13_5_1, 14_3 | — |
| Chrome UI height | 133px | 91px | 80px |
| Taskbar default | 40px | 23px | 0 |

### Network consistency

- **proxy** — Always use with a real proxy. Websites check if IP matches timezone/locale.
- **geoip=true** — Automatically sets timezone/locale from proxy exit IP. Backed by MaxMind GeoLite2.
- **webrtc_ip=auto** — Ensures WebRTC ICE candidates carry the proxy IP, not the container's real IP. This is automatically injected when a proxy is configured.

### Hardware signals

- **hardware_concurrency** — `navigator.hardwareConcurrency`. Windows: 4–16, macOS: 8–20, Linux: 2–16.
- **device_memory** — `navigator.deviceMemory`. Must be a standard Chrome value (0.25, 0.5, 1, 2, 4, 8). Use 8 for modern desktops.
- **screen_width/height** — Must match common desktop ratios (16:9, 16:10). 1920×1080 is the safest default.
- **taskbar_height** — Subtracted from availHeight. 40 (Windows), 23 (macOS).
- **device_scale_factor** — Pixel ratio. 1.0 for standard desktops, 2.0 for Retina/HiDPI.

### Client Hints (Sec-CH-UA)

- **brand** — Browser brand in Client Hints headers. Chrome, Edge, Opera, Vivaldi.
- **brand_version** — Should match the Chromium version.
- **platform_version** — OS version string.

### Session Hygiene

- **clear_on_launch=true** — Deletes Cookies, Local Storage, Cache, History, Service Workers, IndexedDB, and GPU cache before every launch. Use for fresh-session profiles.
- **clear_on_launch=false** (default) — Keeps state across launches. Use for returning-user profiles (accounts stay logged in).
- **storage_state** — Upload a pre-warmed Playwright storage_state JSON via `POST /api/profiles/{id}/storage-state`. Cleared and re-applied on launch when clear_on_launch is true.

### Noise Control

- **noise_enabled=true** (default) — Canvas/WebGL/audio/client-rect noise varies per seed. Good for unique identities.
- **noise_enabled=false** — Seed still determines identity but noise is disabled. Reduces detectable tampering patterns for returning-user profiles (Chromium 148+).

### Humanization

- **humanize=true** — Plugs into CloakBrowser's Bezier-curve mouse movement, per-character typing delays, mistypes, overshoots, scroll acceleration/deceleration, and idle micro-movements.
- **human_preset=careful** — Slower typing, longer pauses, enabled idle-between-actions — harder to detect but slower execution.
- **human_config** — Raw JSON override for individual parameters (typing_delay, mouse_wobble_max, scroll_overshoot_chance, etc.).

## Verifying Your Profile

### Manual detection testing

The profile includes a bookmark folder named "Detection Tests" with these links:

1. **Rebrowser Bot Detector** — Comprehensive detection panel
2. **CreepJS** — Deep fingerprint analysis by @abrahamjuliot
3. **Pixelscan** — IP/fingerprint integrity check
4. **FingerprintJS Demo** — Real-world fingerprinting library
5. **BrowserScan Bot** — Multi-signal bot classification
6. **BrowserLeaks Canvas/WebGL/Fonts** — Individual signal validation

Visit each and ensure no red flags.

### Automated analysis

```bash
# Run automated detection test (headless, non-persistent)
curl -X POST http://localhost:8080/api/profiles/<profile-id>/analyze
```

Returns pass/fail per test with coherence warnings.

### Coherence Warnings

The manager runs consistency checks at profile creation, update, and launch. Warnings appear in:
- **Profile editor UI** — amber alert box below Session Hygiene
- **API response** — `coherence_warnings` array on GET /api/profiles/{id}
- **CLI** — `cbpm profiles get <id>` shows warnings

Common warnings and fixes:

| Warning | Fix |
|---------|-----|
| GPU renderer doesn't match platform | Switch GPU preset or platform |
| User-Agent missing platform fragment | Reset UA (POST /reseed) or set explicitly |
| Timezone/locale region mismatch | Enable geoip or manually align |
| Proxy country != locale | Enable geoip or set locale manually |
| Device memory not standard Chrome value | Use 0.25, 0.5, 1, 2, 4, 8, 16, or 32 |
| Platform version format wrong | Use `10.0.19045` for Windows, `13_5_1` for macOS |

## Common Issues

### "I'm being detected as a bot even with geoip=true"

1. Verify your proxy is healthy: `curl http://localhost:8080/api/proxy-credentials/<id>/test`
2. Check WebRTC is spoofed: `webrtc_ip=auto` (should auto-inject with proxy, but verify in launch args)
3. Enable humanize: `--humanize true --human-preset careful`
4. Clear cached fingerprint: delete profile and recreate with clear_on_launch

### "My Linux profile shows as Windows fonts missing"

On Linux hosts, install Windows fonts:
```bash
apt-get install ttf-mscorefonts-installer
```
Then set `fonts_dir` to the font directory or mount fonts into the container.

### "My canvas fingerprint changes between launches"

This is intentional with `noise_enabled=true`. For stable fingerprints across sessions, set `noise_enabled=false` and use a fixed `fingerprint_seed`.

### "reCAPTCHA v3 gives me a low score"

reCAPTCHA v3 scores reflect behavioral trust over time. To improve:
1. Use the same profile seed across launches (stable identity).
2. Set `noise_enabled=false`.
3. Enable `humanize=true` with `human_preset=careful`.
4. Browse naturally for 10–15 minutes before navigating to reCAPTCHA-protected pages.
5. Do NOT clear cookies/localStorage between sessions.

## API Reference

| Endpoint | Purpose |
|----------|---------|
| `GET /api/profiles/{id}` | View profile with coherence_warnings |
| `POST /api/profiles/{id}/reseed` | Generate new random fingerprint seed |
| `POST /api/profiles/{id}/reset-ua` | Clear explicit User-Agent |
| `POST /api/profiles/{id}/storage-state` | Upload Playwright storage_state |
| `POST /api/profiles/{id}/analyze` | Run automated detection test |
| `GET /api/proxy-credentials/{id}/test` | Test proxy health (exit IP, country, timezone) |

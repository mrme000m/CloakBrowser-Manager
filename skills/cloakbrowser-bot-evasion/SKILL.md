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

The recommended approach is a **device persona** — a coherent real-world
machine — plus GeoIP. Leave `brand_version` and `user_agent` unset so they are
derived from the CloakBrowser binary's Chromium version and never disagree.

```bash
# List coherent personas
cbpm profiles personas

cbpm profiles create \
  --name "organic-windows-us" \
  --persona win11-rtx3070-desktop \
  --timezone America/New_York \
  --locale en-US \
  --geoip true \
  --webrtc-ip auto \
  --geolocation-lat 40.7128 \
  --geolocation-lon -74.0060 \
  --noise-enabled true \
  --humanize true \
  --human-preset careful \
  --clear-on-launch false
```

### macOS variant

```bash
cbpm profiles create \
  --name "organic-macos" \
  --persona mac-mbp-m2-14 \
  --timezone America/Los_Angeles \
  --locale en-US \
  --geoip true \
  --webrtc-ip auto
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

- **hardware_concurrency** — `navigator.hardwareConcurrency`. Common real values: 4, 6, 8, 10, 12, 16, 20, 24. Odd/huge values are suspicious. Set by the persona.
- **device_memory** — `navigator.deviceMemory`. Real Chrome only reports **0.25, 0.5, 1, 2, 4, 8** and is capped at 8 (even on 64 GB machines). Values > 8 are impossible and a bot signal; the manager rejects them on create/update.
- **screen_width/height** — Must match common desktop ratios (16:9, 16:10). Set by the persona so a fleet is diverse, not all 1920×1080.
- **taskbar_height** — Subtracted from availHeight. 40 (Windows), 23 (macOS). Set by the persona.
- **device_scale_factor** — Pixel ratio. macOS Retina = 2.0; Windows 4K = 1.5; standard = 1.0. Set by the persona.

### Client Hints (Sec-CH-UA)

- **brand** — Browser brand in Client Hints headers. `chrome` on all platforms.
- **brand_version** — **Leave unset** so it is derived from the CloakBrowser binary's Chromium version. A UA reporting `Chrome/146` while Sec-CH-UA says `v="120"` is a guaranteed fail.
- **platform_version** — OS version string. Set by the persona (Win `10.0.19045`, macOS `14_3`).

### Device personas

Use `--persona <name>` to apply a coherent bundle (screen + GPU + cores + memory + DPR + platform version + taskbar) in one step. A fleet built from *different* personas is diverse but each profile is internally consistent; building everything as `1920×1080 + RTX 3070` lets anti-bot systems cluster your profiles. Any field you pass explicitly overrides the persona for that one field. Run `cbpm profiles personas` for the list.

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
# Launch a one-shot headless run and verify the LIVE fingerprint against the
# profile — reads the actual navigator/WebGL/screen/timezone/voices/WebRTC
# values from the page and compares them to the profile (not a scraper).
curl -X POST http://localhost:8080/api/profiles/<profile-id>/analyze
# CLI:
cbpm profiles analyze <profile-id>
```

Returns per-signal pass/fail/warn: UA↔Sec-CH-UA version, UA↔CloakBrowser binary,
WebGL renderer↔platform, `deviceMemory ≤ 8`, timezone↔locale, screen chain,
devicePixelRatio, speechSynthesis voices, platform fonts, WebRTC IP leak —
plus coherence warnings.

### Coherence Warnings

The manager runs consistency checks at profile creation, update, and launch. Warnings appear in:
- **Profile editor UI** — amber alert box below Session Hygiene
- **API response** — `coherence_warnings` array on GET /api/profiles/{id}
- **CLI** — `cbpm profiles get <id>` shows warnings

Common warnings and fixes:

| Warning | Fix |
|---------|-----|
| UA Chrome/major ≠ Sec-CH-UA brand version | Leave `brand_version` unset (derived from binary) |
| UA ≠ CloakBrowser binary version | Leave `user_agent` unset |
| GPU renderer doesn't match platform | Use a matching persona or GPU preset |
| User-Agent missing platform fragment | Reset UA (POST /reset-ua) or set explicitly |
| Timezone/locale region mismatch (country-level) | Enable geoip or manually align |
| Proxy country != timezone/locale | Enable geoip or set locale manually |
| Device memory not a real Chrome value | Use 0.25/0.5/1/2/4/8 (capped at 8) |
| Platform version format wrong | Win `10.0.19045`, macOS `14_3` — or use a persona |
| Spoofing Windows/macOS on Linux without fonts_dir | Set `--fonts-dir` to a real platform font pack |
| Software GL (SwiftShader) ≠ spoofed GPU | Expected in the GPU-less container; note the tradeoff |

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
| `GET /api/personas` | List coherent device personas |
| `POST /api/profiles/{id}/reseed` | Generate a new full-entropy fingerprint seed |
| `POST /api/profiles/{id}/rotate-identity` | New seed + re-apply the persona's hardware bundle |
| `POST /api/profiles/{id}/reset-ua` | Clear explicit User-Agent (regenerate from binary) |
| `POST /api/profiles/{id}/storage-state` | Upload Playwright storage_state |
| `POST /api/profiles/{id}/analyze` | Live in-page fingerprint verification |
| `GET /api/proxy-credentials/{id}/test` | Test proxy health (exit IP, country, timezone) |

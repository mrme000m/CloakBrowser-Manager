<p align="center">
<img src="https://i.imgur.com/cqkp6fG.png" width="500" alt="CloakBrowser">
</p>

<h3 align="center">Browser Profile Manager for CloakBrowser</h3>

<p align="center">
Create, manage, and launch isolated browser profiles with unique fingerprints.<br>
Free, self-hosted alternative to Multilogin, GoLogin, and AdsPower.
</p>

<p align="center">
<a href="https://github.com/CloakHQ/CloakBrowser"><img src="https://img.shields.io/github/stars/cloakhq/cloakbrowser?label=CloakBrowser" alt="Stars"></a>
<a href="https://hub.docker.com/r/cloakhq/cloakbrowser-manager"><img src="https://img.shields.io/docker/pulls/cloakhq/cloakbrowser-manager?label=docker&logo=docker&logoColor=white" alt="Docker Pulls"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
</p>

---

<p align="center">
<img src="https://i.imgur.com/twdX81Q.png" width="800" alt="CloakBrowser Manager — Browser View">
<br>
<img src="https://i.imgur.com/XFYn1qY.png" width="800" alt="CloakBrowser Manager — Profile Settings">
</p>

Each profile is an isolated CloakBrowser instance with its own fingerprint, proxy, cookies, and session data. Profiles persist across restarts. Everything runs in one Docker container.

```bash
docker run -p 8080:8080 -v cloakprofiles:/data cloakhq/cloakbrowser-manager
```

Or build from source:

```bash
git clone https://github.com/CloakHQ/CloakBrowser-Manager.git
cd CloakBrowser-Manager
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080) in your browser. Create a profile. Click Launch. Done.

> **Early alpha** — this project is under active development. Expect bugs. If you find one, please [open an issue](https://github.com/CloakHQ/CloakBrowser-Manager/issues).

## Why Not Just Use a VPN?

A VPN only changes your IP. Incognito only clears cookies. Chrome profiles share the same hardware fingerprint underneath. Platforms use 50+ signals to link your accounts — canvas, WebGL, audio, GPU, fonts, screen size, timezone.

Each CloakBrowser profile generates a completely different device identity. To the website, each profile looks like a different computer.

| Solution | What it changes | Accounts linked? |
|----------|----------------|-----------------|
| VPN | IP address only | Yes — same fingerprint |
| Incognito | Clears cookies | Yes — same fingerprint |
| Chrome profiles | Separate bookmarks/cookies | Yes — same hardware fingerprint |
| **CloakBrowser** | **Everything — full device identity per profile** | **No** |

## Features

- **Profile management** — create, edit, delete browser profiles with unique fingerprints
- **Per-profile settings** — fingerprint seed, proxy, timezone, locale, user agent, screen size, platform
- **Identity rotation API** — reseed fingerprint, reset User-Agent, and swap proxy/timezone via REST endpoints
- **One-click launch/stop** — each profile runs as an isolated CloakBrowser instance
- **Session persistence** — cookies, localStorage, and cache survive browser restarts
- **In-browser viewing** — interact with launched browsers via noVNC, directly in the web GUI
- **Playwright/Puppeteer API** — connect to any running profile programmatically via CDP, while still watching it live in the browser
- **Optional authentication** — protect the web UI and API with a single token, or run wide open locally
- **Powered by CloakBrowser** — 32 source-level C++ patches, passes Cloudflare Turnstile, 0.9 reCAPTCHA v3 score

## Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Tailwind CSS
- **Browser viewer**: noVNC (WebSocket-based VNC client)
- **Database**: SQLite
- **Browser engine**: [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) (stealth Chromium binary)

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up --build
```

## Requirements

- Docker (20.10+)
- ~2 GB disk (image + binary)
- ~512 MB RAM per running profile

## Organic Profiles (Anti-Detection)

Each profile can be tuned for **maximum coherence** — every fingerprint signal is internally consistent so anti-bot systems (FingerprintJS, CreepJS, BrowserScan, Pixelscan, reCAPTCHA v3, Cloudflare Turnstile) cannot flag it as automated.

### Quick Start: Create a clean Windows profile

The recommended way to get a coherent, organic fingerprint is to build from a
**device persona** — a curated, internally-consistent real-world machine (screen,
GPU, cores, memory, DPR, platform version all set together). Leave
`brand_version` / `user_agent` unset so they are derived from the CloakBrowser
binary's Chromium version and never disagree (a UA↔Sec-CH-UA version mismatch is
a classic bot tell).

```bash
# List available personas
cbpm profiles personas

# CLI
cbpm profiles create \
  --name "shop-us" \
  --persona win11-rtx3070-desktop \
  --geoip true \
  --humanize true \
  --webrtc-ip auto
```

Then launch and visit the bookmarked detection sites to verify.

### Key organic-fingerprint fields

| Field | Purpose | Recommended |
|---|---|---|
| `--persona` | Apply a coherent real-world device bundle | Use this instead of setting each field by hand |
| `--geoip` | Auto-match timezone + locale to proxy IP | Always enable with a proxy |
| `--webrtc-ip auto` | Spoof WebRTC ICE candidates to proxy IP | Always when using a proxy (auto-injected) |
| `--brand` | Sec-CH-UA browser brand | `chrome` on all platforms |
| `--brand-version` | Sec-CH-UA version | **Leave unset** → derived from the binary (a mismatch with the UA is a bot tell) |
| `--user-agent` | Override User-Agent | **Leave unset** → matches the binary's Chromium version |
| `--platform-version` | Sec-CH-UA-Platform-Version | Set by the persona (Win: `10.0.19045`, Mac: `14_3`) |
| `--noise-enabled false` | Disable canvas/WebGL noise (stable identity) | For returning-user profiles |
| `--device-memory` | `navigator.deviceMemory` | `8`; real Chrome only reports 0.25/0.5/1/2/4/8 (capped at 8) |
| `--fonts-dir` | Custom font directory | Required when spoofing Windows/macOS on a Linux host |
| `--clear-on-launch` | Wipe cookies/cache each launch | For fresh-session profiles |
| `--geolocation-lat/lon` | Consistent geolocation | Match IP location |
| `--storage-quota` | Override storage quota | Match device class |
| `--taskbar-height` | Adjust availHeight | Set by the persona (Win: 40, macOS: 23) |
| `--device-scale-factor` | Pixel ratio | Set by the persona (macOS Retina: 2.0) |

### Device personas

A persona is a fully-coherent, real-world machine. Creating a fleet from
*different* personas gives diverse-but-individually-consistent profiles, instead
of N copies of `1920×1080 + RTX 3070` which anti-bot systems cluster on.

```bash
cbpm profiles personas
#   win10-thinkpad-t14      windows  ThinkPad T14 (Intel Iris Xe, 1920×1080@125%)
#   win11-rtx3070-desktop  windows  Desktop (RTX 3070, 2560×1440)
#   win10-amd-4k           windows  Desktop (RX 7900, 4K@150%)
#   mac-mbp-m2-14          macos    MacBook Pro 14" (M2, 1512×982 Retina)
#   mac-mba-m1             macos    MacBook Air (M1, 1440×900 Retina)
#   linux-amd-desktop      linux    Desktop (RX 6700, 1920×1080)
```

`--persona win11-rtx3070-desktop` sets the screen, GPU, cores, memory, DPR,
platform version, and taskbar together. Any field you also pass explicitly
overrides the persona for that one field (and the coherence engine will flag the
resulting mismatch).

### Platform consistency guide

**Windows profile:**
- GPU: ANGLE with Direct3D11 (NVIDIA RTX / AMD RX)
- UA: contains `Windows NT`
- platformVersion: `10.0.19045`
- Chrome UI offset: 133px

**macOS profile:**
- GPU: ANGLE Metal (Apple M-series)
- UA: contains `Macintosh`
- platformVersion: `13_5_1`
- Chrome UI offset: 91px

**Linux profile:**
- GPU: ANGLE Vulkan/OpenGL
- UA: contains `Linux`
- Chrome UI offset: 80px

The coherence engine validates these automatically and surfaces warnings in the UI.

### Detection-Test Workflow

1. Create a profile with recommended settings.
2. Launch the browser.
3. Open the "Detection Tests" bookmark folder (auto-created) and visit:
   - [Rebrowser Bot Detector](https://bot-detector.rebrowser.net/)
   - [Incolumitas](https://bot.incolumitas.com/)
   - [BrowserScan Bot](https://www.browserscan.net/bot-detection)
   - [Pixelscan](https://pixelscan.net/fingerprint-check)
   - [CreepJS](https://abrahamjuliot.github.io/creepjs/)
4. If any test flags your profile, check the Coherence Warnings section in the profile editor for mismatches.
5. Adjust fields and re-test.

### Automated Analysis API

```bash
# Launch a one-shot headless run and verify the live fingerprint against the
# profile (reads the actual navigator/WebGL/screen/timezone/WebRTC values
# from the page and compares them to the profile — not a third-party scraper).
curl -X POST http://localhost:8080/api/profiles/<id>/analyze
```

Returns a per-signal pass/fail/warn report (UA↔Sec-CH-UA version, UA↔binary,
WebGL renderer↔platform, `deviceMemory ≤ 8`, timezone↔locale, screen chain,
devicePixelRatio, speechSynthesis voices, platform fonts, WebRTC IP leak) plus
the coherence warnings.

### Identity rotation

```bash
# New full-entropy fingerprint seed (new canvas/audio/etc, same hardware).
curl -X POST http://localhost:8080/api/profiles/<id>/reseed

# Stronger: new seed AND re-apply the persona's coherent hardware bundle.
curl -X POST http://localhost:8080/api/profiles/<id>/rotate-identity

# Clear an explicit User-Agent so it is regenerated from the binary.
curl -X POST http://localhost:8080/api/profiles/<id>/reset-ua
```

Both take effect on the next launch; a running browser is left untouched.



Pull the latest image and restart:

```bash
docker pull cloakhq/cloakbrowser-manager
docker stop <container-id>
docker run -p 8080:8080 -v cloakprofiles:/data cloakhq/cloakbrowser-manager
```

Your profiles and session data are stored in the `cloakprofiles` volume and persist across updates.

## Automation API

Every running profile exposes a CDP (Chrome DevTools Protocol) endpoint. Connect Playwright or Puppeteer to automate a profile while watching it live in the browser.

```python
from playwright.async_api import async_playwright

async with async_playwright() as pw:
    browser = await pw.chromium.connect_over_cdp(
        "http://localhost:8080/api/profiles/<profile-id>/cdp"
    )
    page = browser.contexts[0].pages[0]
    await page.goto("https://example.com")
```

```javascript
const { chromium } = require("playwright");

const browser = await chromium.connectOverCDP(
  "http://localhost:8080/api/profiles/<profile-id>/cdp"
);
const page = browser.contexts()[0].pages()[0];
await page.goto("https://example.com");
```

The CDP URL is available in the toolbar (code icon) when a profile is running. The same browser session is accessible both visually through VNC and programmatically through the API.

## Remote Access

The container binds to localhost only. To access from a remote server:

```bash
ssh -L 8080:localhost:8080 your-server
```

Then open `http://localhost:8080`.

## Authentication

By default, there is no authentication (ideal for local use). To protect the web UI and API when hosting on a network, set the `AUTH_TOKEN` environment variable:

```bash
docker run -p 8080:8080 -v cloakprofiles:/data -e AUTH_TOKEN=your-secret-token cloakhq/cloakbrowser-manager
```

Or in `docker-compose.yml`:

```yaml
environment:
  - AUTH_TOKEN=your-secret-token
```

When `AUTH_TOKEN` is set:

- The web UI shows a login page. Enter the token to unlock.
- API consumers pass the token via `Authorization: Bearer <token>` header.
- VNC WebSocket connections are authenticated via the login cookie.
- The `/api/status` endpoint remains unauthenticated (for Docker healthcheck).

> **Note**: The auth token is transmitted in cleartext over HTTP. If you expose the Manager to the internet, put it behind a reverse proxy with HTTPS (Caddy, nginx, Traefik).

## License

- **This application** (GUI source code) — MIT. See [LICENSE](LICENSE).
- **CloakBrowser binary** (compiled Chromium) — free to use, no redistribution. See [BINARY-LICENSE.md](BINARY-LICENSE.md).

The GUI application requires the CloakBrowser Chromium binary to function. The binary is automatically downloaded on first launch and is governed by its own license terms. If you fork or redistribute this application, your users must comply with the [CloakBrowser Binary License](BINARY-LICENSE.md).

## Contributing

Contributions are welcome. Please [open an issue](https://github.com/CloakHQ/CloakBrowser-Manager/issues) first to discuss what you'd like to change.

## Links

- **CloakBrowser** — [github.com/CloakHQ/CloakBrowser](https://github.com/CloakHQ/CloakBrowser)
- **Website** — [cloakbrowser.dev](https://cloakbrowser.dev)
- **Bug reports** — [GitHub Issues](https://github.com/CloakHQ/CloakBrowser-Manager/issues)
- **Contact** — cloakhq@pm.me

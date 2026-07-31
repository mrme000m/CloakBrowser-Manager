# cbpm — CloakBrowser Profile Manager CLI

A self-explaining command-line client for the CloakBrowser-Manager REST API. Built
in the spirit of [browser-debugger-cli](https://github.com/.../browser-debugger-cli):
**the tool teaches itself** — discover every command and option without leaving the
terminal.

## Install

```bash
cd cli
npm install
npm run build          # emits dist/index.js
npm link               # optional: exposes the `cbpm` command on PATH
```

Or run directly: `node dist/index.js <command>`.

## Configure

```bash
cbpm config set api_url https://clk.mrme.tech   # or http://127.0.0.1:8080
cbpm auth login <AUTH_TOKEN>                    # validates + stores the Bearer token
cbpm status
```

Env overrides: `CBPM_API_URL`, `CBPM_API_TOKEN`.

## Self-explaining surfaces

```bash
cbpm --help --json                 # machine-readable schema of the whole CLI
cbpm profiles create --list-fields # every create field with type/default
cbpm profiles create --describe fingerprint-seed
cbpm proxy-locations --list        # the provider location catalog
cbpm proxy-locations --describe atl     # full details + a create example
cbpm proxy-locations --search "new york"
```

## Common tasks

```bash
cbpm profiles create --name shop-us --proxy-group <group-id> --geoip --humanize
cbpm profiles launch <id>
cbpm profiles status <id>          # CDP clients · geoip · CPU/mem/uptime
cbpm profiles connect <id>         # Playwright/Puppeteer/curl/bdg snippets
cbpm profiles bulk launch --tag shop
cbpm proxy-credentials test-all
```

## Design

- **stdout = data, stderr = logs/errors/hints.** Structured output via `--json`.
- **Versioned JSON envelope**: `{version, success, data}` / `{version, success:false, error, exitCode, suggestion}`.
- **Semantic exit codes** (Square ranges): `0` ok, `80` bad input, `81` auth, `90` not-found, `91` conflict, `92` rate-limited, `100` external, `110` software. All listed in `cbpm --help --json`.
- Single runtime dependency: `commander`. HTTP via the global `fetch`.

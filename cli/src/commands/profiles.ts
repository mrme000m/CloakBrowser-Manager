/** `cbpm profiles ...` — profile lifecycle & operations. */

import { spawn } from "node:child_process";

import { Command, Option } from "commander";

import { api, tag } from "../client.js";
import { effectiveConfig } from "../config.js";
import { CommandError } from "../errors.js";
import {
  formatBulk,
  formatLaunch,
  formatProfile,
  formatProfileList,
  formatProfileStatus,
  pad,
  truncate,
} from "../format.js";
import { runCommand, parseIds } from "../runner.js";
import { PROFILE_FIELDS, listFields, findField, suggestFields } from "../schema.js";
import type { Profile } from "../types.js";

function camel(s: string): string {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function collect(v: string, p: string[]): string[] {
  p.push(v);
  return p;
}

/** Add a Commander option per field in PROFILE_FIELDS (keeps create/`--list-fields` in sync). */
function applyProfileOptions(cmd: Command): void {
  for (const f of PROFILE_FIELDS) {
    if (f.name === "clipboard_sync") {
      cmd.option("--no-clipboard-sync", "Disable clipboard sync (default: enabled)");
      continue;
    }
    if (f.type === "bool") {
      cmd.option(f.flag, f.description);
    } else if (f.type === "int") {
      cmd.option(`${f.flag} <n>`, f.description, (v: string) => parseInt(v, 10));
    } else if (f.type === "list[string]") {
      cmd.option(`${f.flag} <v>`, `${f.description} (repeatable)`, collect, [] as string[]);
    } else if (f.type.startsWith("enum:")) {
      const choices = f.type.slice(5).split("|");
      cmd.addOption(new Option(`${f.flag} <v>`, f.description).choices(choices));
    } else {
      cmd.option(`${f.flag} <v>`, f.description);
    }
  }
}

/** Build the create/update body from the parsed options (only includes provided fields). */
function bodyFromOptions(opts: Record<string, unknown>): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const f of PROFILE_FIELDS) {
    const key = camel(f.name);
    const val = opts[key];
    if (val === undefined) continue;
    if (f.name === "tags") {
      const arr = val as string[];
      body.tags = arr.map((t) => {
        const i = t.indexOf(":");
        return i > 0 ? tag(t.slice(0, i), t.slice(i + 1)) : tag(t);
      });
      continue;
    }
    if (f.name === "clipboard_sync") {
      // --no-clipboard-sync → false; otherwise omit (server default true)
      if (val === false) body.clipboard_sync = false;
      continue;
    }
    if (f.type === "list[string]") {
      if ((val as string[]).length) body[f.name] = val;
      continue;
    }
    body[f.name] = val;
  }
  return body;
}

function fieldsTable(): string {
  const rows = listFields().map((f) => ({
    flag: f.flag,
    type: truncate(f.type.replace("enum:", ""), 16),
    required: f.required ? "yes" : "",
    default: f.default,
    desc: truncate(f.description, 48),
  }));
  const head = `${pad("flag", 22)} ${pad("type", 16)} ${pad("req", 4)} ${pad("default", 8)} description`;
  return [head, ...rows.map((r) => `${pad(r.flag, 22)} ${pad(r.type, 16)} ${pad(r.required, 4)} ${pad(r.default, 8)} ${r.desc}`)].join("\n");
}

function describeField(name: string): string {
  const f = findField(name);
  if (!f) {
    const sugg = suggestFields(name).map((s) => s.flag);
    return [
      `Unknown field: --${name.replace(/^--/, "")}`,
      sugg.length ? `Did you mean: ${sugg.join(", ")}?` : "",
      "Run `cbpm profiles create --list-fields` to see all fields.",
    ]
      .filter(Boolean)
      .join("\n");
  }
  return [
    `${f.flag}  (${f.type})`,
    `  ${f.description}`,
    `  required: ${f.required ? "yes" : "no"}   default: ${f.default}`,
    f.example ? `  example: ${f.example}` : "",
    "",
    "Example:",
    `  cbpm profiles create --name <n> ${f.flag} ${f.example ?? "<value>"}`,
  ]
    .filter(Boolean)
    .join("\n");
}

function localCdpWs(apiUrl: string, id: string): string {
  const ws = apiUrl.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://").replace(/\/+$/, "");
  return `${ws}/api/profiles/${id}/cdp/local`;
}

function localCdpHttp(apiUrl: string, id: string): string {
  return `${apiUrl.replace(/\/+$/, "")}/api/profiles/${id}/cdp/local`;
}

function connectSnippets(p: Profile, localWs: string, localHttp: string, authRequired: boolean) {
  const authUrl = p.cdp_endpoint || null;
  const headersArg = authRequired ? `, headers: {"Authorization": "Bearer <YOUR_TOKEN>"}` : "";
  const curlHeader = authRequired ? ` -H "Authorization: Bearer <YOUR_TOKEN>"` : "";
  return {
    auth_url: authUrl,
    local_url: localWs,
    playwright_python: `from playwright.async_api import async_playwright\nasync with async_playwright() as pw:\n    browser = await pw.chromium.connect_over_cdp("${authUrl ?? localWs}"${headersArg})`,
    playwright_js: `import { chromium } from "playwright";\nconst browser = await chromium.connectOverCDP("${authUrl ?? localWs}"${headersArg.replace(", headers:", ", { headers:")});\n// note: pass headers as the 2nd arg object in JS`,
    puppeteer: `const browser = await puppeteer.connect({ browserWSEndpoint: "${authUrl ?? localWs}"${authRequired ? `, headers: { Authorization: "Bearer <YOUR_TOKEN>" }` : ""} });`,
    curl_json_list: `curl${curlHeader} ${localHttp}/json/list`,
    bdg: `bdg <url> --chrome-ws-url=${localWs}`,
  };
}

export function registerProfilesCommand(program: Command): void {
  const profiles = program
    .command("profiles")
    .description("Create and manage browser profiles");

  // ── list ────────────────────────────────────────────────────────────────
  profiles
    .command("list")
    .description("List profiles (optionally filtered by tag/status/template)")
    .option("--tag <tag>", "Filter to profiles with this tag")
    .option("--status <status>", "Filter: running | stopped")
    .option("--template", "Show only templates")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { tag?: string; status?: string; template?: boolean; json?: boolean }) => {
      await runCommand(
        async () => {
          let list = await api.listProfiles();
          if (options.tag) list = list.filter((p) => p.tags.some((t) => t.tag === options.tag));
          if (options.status) list = list.filter((p) => p.status === options.status);
          if (options.template) list = list.filter((p) => p.is_template);
          return { success: true, data: list };
        },
        options,
        formatProfileList,
      );
    });

  // ── create (self-explaining: --list-fields / --describe) ────────────────
  const create = profiles
    .command("create")
    .description("Create a profile. Use --list-fields to discover every option.")
    .option("-j, --json", "Output as JSON", false)
    .option("--list-fields", "List every create field with type/default (no API call)")
    .option("--describe <field>", "Describe one field (no API call)");
  applyProfileOptions(create);
  create.action(async (options: Record<string, unknown> & { json?: boolean; listFields?: boolean; describe?: string }) => {
    if (options.listFields) {
      console.log(fieldsTable());
      process.exit(0);
    }
    if (options.describe) {
      const out = describeField(String(options.describe));
      const found = findField(String(options.describe));
      console.log(out);
      process.exit(found ? 0 : 80);
    }
    if (!options.name) {
      process.stderr.write("Error: --name is required. Run `cbpm profiles create --list-fields` to see all options.\n");
      process.exit(80);
    }
    const body = bodyFromOptions(options);
    await runCommand(
      async () => {
        const p = await api.createProfile(body);
        return { success: true, data: p };
      },
      { json: options.json },
      formatProfile,
    );
  });

  // ── get ────────────────────────────────────────────────────────────────
  profiles
    .command("get <id>")
    .description("Show a profile's full details")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.getProfile(id) }),
        options,
        formatProfile,
      );
    });

  // ── update ────────────────────────────────────────────────────────────
  const update = profiles
    .command("update <id>")
    .description("Update profile fields (only provided ones change)")
    .option("-j, --json", "Output as JSON", false);
  applyProfileOptions(update);
  update.action(async (id: string, options: Record<string, unknown> & { json?: boolean }) => {
    const body = bodyFromOptions(options);
    if (Object.keys(body).length === 0) {
      process.stderr.write("Error: no fields provided to update. Run `cbpm profiles create --list-fields` for available flags.\n");
      process.exit(80);
    }
    await runCommand(
      async () => ({ success: true, data: await api.updateProfile(id, body) }),
      { json: options.json },
      formatProfile,
    );
  });

  // ── delete ────────────────────────────────────────────────────────────
  profiles
    .command("delete <id>")
    .description("Delete a profile and its browser data (stops first if running)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.deleteProfile(id) }),
        options,
        () => `Deleted ${id}`,
      );
    });

  // ── launch / stop ──────────────────────────────────────────────────────
  profiles
    .command("launch <id>")
    .description("Launch the profile's browser")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.launchProfile(id) }), options, formatLaunch);
    });

  profiles
    .command("stop <id>")
    .description("Stop a running profile")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.stopProfile(id) }),
        options,
        () => `Stopped ${id}`,
      );
    });

  // ── clone ──────────────────────────────────────────────────────────────
  profiles
    .command("clone <id>")
    .description("Clone a profile (new random fingerprint seed)")
    .option("--name <name>", "Name for the clone")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { name?: string; json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.cloneProfile(id, options.name) }),
        options,
        (p: Profile) => `${formatProfile(p)}\n\nCloned from ${id}`,
      );
    });

  // ── status ────────────────────────────────────────────────────────────
  profiles
    .command("status <id>")
    .description("Show a running profile's runtime status (CDP clients, geoip, resources)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.profileStatus(id) }),
        options,
        formatProfileStatus,
      );
    });

  // ── connect ────────────────────────────────────────────────────────────
  profiles
    .command("connect <id>")
    .description("Print CDP connection snippets (Playwright/Puppeteer/curl/bdg); --exec-bdg runs bdg")
    .option("--exec-bdg", "Run `bdg` against the local CDP endpoint instead of printing")
    .option("--url <url>", "URL to pass to bdg (with --exec-bdg)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { execBdg?: boolean; url?: string; json?: boolean }) => {
      const { api_url, token } = effectiveConfig();
      const localWs = localCdpWs(api_url, id);
      const localHttp = localCdpHttp(api_url, id);

      if (options.execBdg) {
        try {
          const child = spawn("bdg", [options.url ?? "about:blank", `--chrome-ws-url=${localWs}`], {
            stdio: "inherit",
          });
          child.on("error", () => {
            process.stderr.write("Error: `bdg` not found on PATH. Install browser-debugger-cli or drop --exec-bdg to print the command.\n");
            process.exit(100);
          });
          child.on("exit", (code) => process.exit(code ?? 1));
        } catch (err) {
          throw new CommandError(`Failed to launch bdg: ${(err as Error).message}`, {
            suggestion: "Install browser-debugger-cli, or drop --exec-bdg to print the command.",
          }, 100);
        }
        return;
      }

      await runCommand(
        async () => {
          const p = await api.getProfile(id);
          const authRequired = Boolean(token);
          return { success: true, data: connectSnippets(p, localWs, localHttp, authRequired) };
        },
        options,
        (s) => [
          `Connection snippets for profile ${id}`,
          `  Auth URL (Bearer):   ${s.auth_url ?? "—"}`,
          `  Local URL (no auth, requires ALLOW_LOCAL_CDP=true + loopback): ${s.local_url}`,
          ``,
          `Playwright (Python):`,
          s.playwright_python,
          ``,
          `Playwright (JS):`,
          s.playwright_js,
          ``,
          `Puppeteer (Node):`,
          s.puppeteer,
          ``,
          `curl /json/list:`,
          s.curl_json_list,
          ``,
          `browser-debugger-cli (bdg):`,
          s.bdg,
        ].join("\n"),
      );
    });

  // ── bulk ────────────────────────────────────────────────────────────────
  profiles
    .command("bulk <action>")
    .description("Act on many profiles at once (launch | stop | delete)")
    .option("--ids <ids>", "Comma-separated profile ids")
    .option("--tag <tag>", "Resolve to all profiles with this tag")
    .option("-j, --json", "Output as JSON", false)
    .action(async (action: string, options: { ids?: string; tag?: string; json?: boolean }) => {
      if (!["launch", "stop", "delete"].includes(action)) {
        process.stderr.write(`Error: bulk action must be launch|stop|delete (got '${action}')\n`);
        process.exit(80);
      }
      const body: { ids?: string[]; tag?: string } = {};
      if (options.ids) body.ids = parseIds(options.ids);
      if (options.tag) body.tag = options.tag;
      if (!body.ids && !body.tag) {
        process.stderr.write("Error: provide --ids <csv> or --tag <tag>\n");
        process.exit(80);
      }
      await runCommand(
        async () => {
          const data =
            action === "launch"
              ? await api.bulkLaunch(body)
              : action === "stop"
                ? await api.bulkStop(body)
                : await api.bulkDelete(body);
          return { success: true, data };
        },
        options,
        formatBulk,
      );
    });
}

/** Human-readable formatters for stdout (non-JSON) output. */

import type {
  AuthStatus,
  BulkResultResponse,
  LaunchResult,
  Profile,
  ProfileStatus,
  ProxyCredential,
  ProxyGroup,
  ProxyLocation,
  ProxyProvider,
  ProxyTestResult,
  SystemStatus,
} from "./types.js";

export function pad(s: string, n: number): string {
  return s.length >= n ? s : s + " ".repeat(n - s.length);
}

export function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

export function fmtUptime(s: number | null | undefined): string {
  if (s == null) return "—";
  const sec = Math.floor(s);
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return `${d}d${h}h`;
  if (h > 0) return `${h}h${m}m`;
  if (m > 0) return `${m}m`;
  return `${sec}s`;
}

function resources(p: Profile | ProfileStatus): string {
  const r = (p as Profile).resources ?? null;
  if (!r || (r.cpu_percent == null && r.mem_mb == null)) return "";
  return `CPU ${r.cpu_percent ?? "—"}% ${r.mem_mb != null ? `${r.mem_mb.toFixed(0)}MB` : ""} up ${fmtUptime(r.uptime_s)}`;
}

export function formatSystemStatus(s: SystemStatus): string {
  const cap = s.max_running != null ? ` / ${s.max_running}` : "";
  const agg =
    s.total_cpu_percent != null && s.total_mem_mb != null
      ? `   CPU ${s.total_cpu_percent.toFixed(0)}% · ${(s.total_mem_mb ?? 0).toFixed(0)}MB${s.total_proc_count != null ? ` · ${s.total_proc_count} proc` : ""}`
      : "";
  return [
    `CloakBrowser Manager`,
    `  version:    ${s.binary_version}`,
    `  running:    ${s.running_count}${cap}`,
    `  profiles:   ${s.profiles_total}${agg}`,
  ].join("\n");
}

export function formatProfileList(profiles: Profile[]): string {
  if (profiles.length === 0) return "No profiles. Create one with `cbpm profiles create --name <n>`.";
  const rows = profiles.map((p) => {
    const st = p.status === "running" ? "●run" : " stop";
    const tpl = p.is_template ? " [TPL]" : "";
    const proxy =
      p.proxy_group?.name
        ? `group:${p.proxy_group.name}`
        : p.proxy_credential?.name
          ? `cred:${p.proxy_credential.name}`
          : p.proxy
            ? "custom"
            : "—";
    const r = resources(p);
    const line2 = [`${truncate(proxy, 18)}`, r].filter(Boolean).join("  ");
    return `${st}  ${pad(truncate(p.name, 22), 22)}${tpl}  ${p.id}${line2 ? `\n        ${line2}` : ""}`;
  });
  return rows.join("\n");
}

export function formatProfile(p: Profile): string {
  const tags = p.tags.map((t) => t.tag).join(", ") || "—";
  const proxy =
    p.proxy_group?.name
      ? `group: ${p.proxy_group.name} (${p.proxy_group.rotation_mode})`
      : p.proxy_credential?.name
        ? `cred: ${p.proxy_credential.name}`
        : p.proxy ?? "—";
  const r = resources(p);
  return [
    `${p.name}  ${p.is_template ? "[TEMPLATE]" : ""}  (${p.status})`,
    `  id:              ${p.id}`,
    `  platform:        ${p.platform}`,
    `  fingerprint_seed: ${p.fingerprint_seed}`,
    `  proxy:            ${proxy}`,
    `  timezone/locale:  ${p.timezone ?? "—"} / ${p.locale ?? "—"}`,
    `  screen:           ${p.screen_width}x${p.screen_height}`,
    `  humanize:         ${p.humanize ? `yes (${p.human_preset})` : "no"}  geoip: ${p.geoip}  headless: ${p.headless}`,
    `  auto_launch:      ${p.auto_launch}  restart_on_crash: ${p.restart_on_crash} (max ${p.max_restarts})`,
    `  tags:             ${tags}`,
    `  cdp_endpoint:     ${p.cdp_endpoint ?? "—"}`,
    r ? `  resources:       ${r}` : "",
    p.notes ? `  notes:           ${p.notes}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export function formatProfileStatus(s: ProfileStatus): string {
  const geo = [s.exit_ip, s.effective_timezone, s.effective_locale].filter(Boolean).join(" · ");
  const r = s.resources ? resources(s) : "";
  return [
    `status:       ${s.status}`,
    `cdp:          ${s.cdp_endpoint ?? "—"}`,
    `cdp_clients:  ${s.cdp_clients}`,
    geo ? `geoip:        ${geo}` : "",
    r ? `resources:    ${r}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export function formatLaunch(l: LaunchResult): string {
  return `Launched ${l.profile_id} — display ${l.display}, vnc ws_port ${l.vnc_ws_port}\nCDP: ${l.cdp_endpoint ?? "—"}`;
}

export function formatProxyCredentialList(creds: ProxyCredential[]): string {
  if (creds.length === 0) return "No proxy credentials. Create one with `cbpm proxy-credentials create --name <n>`.";
  return creds
    .map((c) => {
      const health =
        c.last_status === "ok"
          ? `✓ ${c.last_exit_ip ?? ""}${c.last_country ? ` ${c.last_country}` : ""}`.trim()
          : c.last_status === "failed"
            ? "✗ failed"
            : "—";
      const prov = c.provider_id ? `prov:${c.provider_location ?? c.provider_id}` : "—";
      return `${pad(truncate(c.name, 20), 20)}  ${c.scheme}://${c.host}:${c.port}  ${prov}  ${health}  ${c.id}`;
    })
    .join("\n");
}

export function formatProxyProviderList(providers: ProxyProvider[]): string {
  if (providers.length === 0) return "No proxy providers.";
  return providers
    .map((p) => `${pad(truncate(p.name, 20), 20)}  ${p.type}  ${p.scheme} ${p.host_template || "(catalog)"}:${p.port}  ${p.id}`)
    .join("\n");
}

export function formatProxyGroup(g: ProxyGroup): string {
  const members = g.members
    .map((m) => `  - [${m.position}] ${m.name} (${m.credential_id})`)
    .join("\n");
  return `${g.name} (${g.id})\n  rotation: ${g.rotation_mode}\n  members (${g.member_count}):\n${members || "  (none)"}`;
}

export function formatProxyGroupList(groups: ProxyGroup[]): string {
  if (groups.length === 0) return "No proxy groups. Create one with `cbpm proxy-groups create --name <n>`.";
  return groups.map((g) => `${pad(truncate(g.name, 20), 20)}  ${g.rotation_mode}  ${g.member_count} members  ${g.id}`).join("\n");
}

export function formatProxyTest(t: ProxyTestResult): string {
  if (!t.ok) return `${t.id ?? ""} ✗ ${t.error ?? "failed"}`.trim();
  const extra = [t.exit_ip, t.country, t.timezone, t.latency_ms != null ? `${t.latency_ms}ms` : null]
    .filter(Boolean)
    .join(" · ");
  return `${t.id ?? ""} ✓ ${extra}`.trim();
}

export function formatBulk(b: BulkResultResponse): string {
  const ok = b.results.filter((r) => r.ok).length;
  const fail = b.results.length - ok;
  const lines = b.results.map((r) =>
    r.ok ? `  ✓ ${r.id}` : `  ✗ ${r.id} — ${r.error ?? "failed"}`,
  );
  return `${ok} ok, ${fail} failed\n${lines.join("\n")}`;
}

export function formatAuth(a: AuthStatus): string {
  return `auth_required: ${a.auth_required}\nauthenticated: ${a.authenticated}`;
}

export function formatLocationList(locations: Record<string, ProxyLocation>): string {
  const rows = Object.entries(locations).map(([code, loc]) => ({
    code,
    city: loc.city,
    country: loc.country,
    host: loc.host,
  }));
  if (rows.length === 0) return "No locations.";
  return rows
    .map((r) => `${pad(r.code, 8)} ${pad(truncate(r.city, 18), 18)} ${pad(r.country, 14)} ${r.host}`)
    .join("\n");
}

export function formatLocation(code: string, loc: ProxyLocation): string {
  return [
    `${code} — ${loc.city}, ${loc.country}`,
    `  host:   ${loc.host}`,
    `  city:   ${loc.city}`,
    `  country: ${loc.country}`,
    "",
    "Create a credential from this location:",
    `  cbpm proxy-credentials create --name "${loc.city}" --provider-id <ipvanish-provider-id> --provider-location ${code}`,
  ].join("\n");
}

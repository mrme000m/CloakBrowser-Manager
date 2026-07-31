/**
 * API client for CloakBrowser Manager backend.
 */

export interface ProxyCredential {
  id: string;
  name: string;
  scheme: string;
  host: string;
  port: number;
  username: string;
  has_password: boolean;
  proxy_url: string;
  provider_id: string | null;
  provider_location: string | null;
  last_status: string | null; // "ok" | "failed" | null
  last_exit_ip: string | null;
  last_country: string | null;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProxyProvider {
  id: string;
  name: string;
  type: string; // ipvanish | brightdata | smartproxy | custom
  scheme: string;
  host_template: string;
  port: number;
  username: string;
  has_password: boolean;
  options: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProxyGroupMember {
  credential_id: string;
  position: number;
  name: string;
  scheme: string;
  host: string;
  port: number;
  username: string;
  provider_id: string | null;
  provider_location: string | null;
  last_status: string | null;
  last_exit_ip: string | null;
  last_country: string | null;
}

export interface ProxyGroup {
  id: string;
  name: string;
  rotation_mode: string; // round_robin | sticky_session | random
  member_count: number;
  members: ProxyGroupMember[];
  created_at: string;
  updated_at: string;
}

export interface ProxyLocationMeta {
  host: string;
  city: string;
  country: string;
}

/** GET /api/proxy-locations → { ipvanish: { "us-nyc": {host,city,country}, ... } } */
export type ProxyLocations = Record<string, Record<string, ProxyLocationMeta>>;

export interface ProxyTestResult {
  id: string | null;
  ok: boolean;
  exit_ip: string | null;
  country: string | null;
  timezone: string | null;
  latency_ms: number | null;
  error: string | null;
}

export interface Profile {
  id: string;
  name: string;
  fingerprint_seed: number;
  proxy: string | null;
  proxy_credential_id: string | null;
  proxy_credential: ProxyCredential | null;
  proxy_group_id: string | null;
  proxy_group: ProxyGroup | null;
  timezone: string | null;
  locale: string | null;
  platform: string;
  user_agent: string | null;
  screen_width: number;
  screen_height: number;
  gpu_vendor: string | null;
  gpu_renderer: string | null;
  hardware_concurrency: number | null;
  humanize: boolean;
  human_preset: string;
  headless: boolean;
  geoip: boolean;
  clipboard_sync: boolean;
  auto_launch: boolean;
  color_scheme: string | null;
  launch_args: string[];
  notes: string | null;
  is_template: boolean;
  restart_on_crash: boolean;
  max_restarts: number;
  user_data_dir: string;
  created_at: string;
  updated_at: string;
  tags: { tag: string; color: string | null }[];
  status: "running" | "stopped";
  vnc_ws_port: number | null;
  cdp_url: string | null;
  cdp_endpoint: string | null;
}

export interface ProfileCreateData {
  name: string;
  fingerprint_seed?: number | null;
  proxy?: string | null;
  proxy_credential_id?: string | null;
  proxy_group_id?: string | null;
  timezone?: string | null;
  locale?: string | null;
  platform?: string;
  user_agent?: string | null;
  screen_width?: number;
  screen_height?: number;
  gpu_vendor?: string | null;
  gpu_renderer?: string | null;
  hardware_concurrency?: number | null;
  humanize?: boolean;
  human_preset?: string;
  headless?: boolean;
  geoip?: boolean;
  clipboard_sync?: boolean;
  auto_launch?: boolean;
  color_scheme?: string | null;
  launch_args?: string[];
  notes?: string | null;
  is_template?: boolean;
  restart_on_crash?: boolean;
  max_restarts?: number;
  tags?: { tag: string; color: string | null }[];
}

export interface ProxyCredentialData {
  name: string;
  scheme?: string;
  host: string;
  port?: number;
  username?: string;
  password?: string;
  provider_id?: string | null;
  provider_location?: string | null;
}

export interface ProxyProviderData {
  name: string;
  type?: string;
  scheme?: string;
  host_template?: string;
  port?: number;
  username?: string;
  password?: string;
  options?: Record<string, unknown>;
}

export interface ProxyGroupData {
  name: string;
  rotation_mode?: string;
}

export interface LaunchResult {
  profile_id: string;
  status: string;
  vnc_ws_port: number;
  display: string;
  cdp_url: string | null;
  cdp_endpoint: string | null;
}

/** GET /api/profiles/{id}/status — per-profile runtime info (geoip, cdp clients). */
export interface ProfileStatus {
  status: string;
  vnc_ws_port: number | null;
  display: string | null;
  cdp_url: string | null;
  cdp_endpoint: string | null;
  cdp_clients: number;
  exit_ip: string | null;
  effective_timezone: string | null;
  effective_locale: string | null;
}

export interface SystemStatus {
  running_count: number;
  binary_version: string;
  profiles_total: number;
  max_running: number | null;
}

export interface BulkResultItem {
  id: string;
  ok: boolean;
  error: string | null;
}

export interface BulkResultResponse {
  results: BulkResultItem[];
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Global 401 callback — set by App to trigger login page on auth failure
let _onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(cb: (() => void) | null) {
  _onUnauthorized = cb;
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    if (res.status === 401 && _onUnauthorized) {
      _onUnauthorized();
      throw new ApiError(401, "Unauthorized");
    }
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  authStatus: () =>
    request<{ auth_required: boolean; authenticated: boolean }>("/api/auth/status"),

  login: (token: string) =>
    request<{ ok: boolean }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  logout: () =>
    request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  listProfiles: () => request<Profile[]>("/api/profiles"),

  getProfile: (id: string) => request<Profile>(`/api/profiles/${id}`),

  createProfile: (data: ProfileCreateData) =>
    request<Profile>("/api/profiles", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateProfile: (id: string, data: Partial<ProfileCreateData>) =>
    request<Profile>(`/api/profiles/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProfile: (id: string) =>
    request<{ ok: boolean }>(`/api/profiles/${id}`, { method: "DELETE" }),

  launchProfile: (id: string) =>
    request<LaunchResult>(`/api/profiles/${id}/launch`, { method: "POST" }),

  stopProfile: (id: string) =>
    request<{ ok: boolean }>(`/api/profiles/${id}/stop`, { method: "POST" }),

  /** Per-profile runtime status: geoip (exit IP / TZ / locale) + CDP client count. */
  getProfileStatus: (id: string) =>
    request<ProfileStatus>(`/api/profiles/${id}/status`),

  /** Clone a profile (new random fingerprint seed, is_template forced false). */
  cloneProfile: (id: string, name?: string) =>
    request<Profile>(`/api/profiles/${id}/clone`, {
      method: "POST",
      body: JSON.stringify(name ? { name } : {}),
    }),

  bulkLaunch: (body: { ids?: string[]; tag?: string }) =>
    request<BulkResultResponse>("/api/profiles/bulk/launch", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  bulkStop: (body: { ids?: string[]; tag?: string }) =>
    request<BulkResultResponse>("/api/profiles/bulk/stop", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  bulkDelete: (body: { ids?: string[]; tag?: string }) =>
    request<BulkResultResponse>("/api/profiles/bulk/delete", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getStatus: () => request<SystemStatus>("/api/status"),

  setClipboard: (id: string, text: string) =>
    request<{ ok: boolean }>(`/api/profiles/${id}/clipboard`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  getClipboard: (id: string) =>
    request<{ text: string }>(`/api/profiles/${id}/clipboard`),

  // ── Proxy Credentials ──────────────────────────────────────────

  listProxyCredentials: () =>
    request<ProxyCredential[]>("/api/proxy-credentials"),

  createProxyCredential: (data: ProxyCredentialData) =>
    request<ProxyCredential>("/api/proxy-credentials", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateProxyCredential: (id: string, data: Partial<ProxyCredentialData>) =>
    request<ProxyCredential>(`/api/proxy-credentials/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProxyCredential: (id: string) =>
    request<{ ok: boolean }>(`/api/proxy-credentials/${id}`, { method: "DELETE" }),

  /** Test a single credential through its proxy; persists last_status/exit_ip/... */
  testProxyCredential: (id: string) =>
    request<ProxyTestResult>(`/api/proxy-credentials/${id}/test`, { method: "POST" }),

  /** Test every credential; returns per-credential results. */
  testAllProxyCredentials: () =>
    request<ProxyTestResult[]>("/api/proxy-credentials/test-all", { method: "POST" }),

  /** Provider location catalog (IPVanish city codes, etc.) for the picker. */
  getProxyLocations: () => request<ProxyLocations>("/api/proxy-locations"),

  // ── Proxy Providers ─────────────────────────────────────────────

  listProxyProviders: () =>
    request<ProxyProvider[]>("/api/proxy-providers"),

  createProxyProvider: (data: ProxyProviderData) =>
    request<ProxyProvider>("/api/proxy-providers", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateProxyProvider: (id: string, data: Partial<ProxyProviderData>) =>
    request<ProxyProvider>(`/api/proxy-providers/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProxyProvider: (id: string) =>
    request<{ ok: boolean }>(`/api/proxy-providers/${id}`, { method: "DELETE" }),

  // ── Proxy Groups (rotation pools) ───────────────────────────────

  listProxyGroups: () =>
    request<ProxyGroup[]>("/api/proxy-groups"),

  createProxyGroup: (data: ProxyGroupData) =>
    request<ProxyGroup>("/api/proxy-groups", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateProxyGroup: (id: string, data: Partial<ProxyGroupData>) =>
    request<ProxyGroup>(`/api/proxy-groups/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProxyGroup: (id: string) =>
    request<{ ok: boolean }>(`/api/proxy-groups/${id}`, { method: "DELETE" }),

  /** Replace all members of a group. */
  setProxyGroupMembers: (id: string, credential_ids: string[]) =>
    request<ProxyGroup>(`/api/proxy-groups/${id}/members`, {
      method: "PUT",
      body: JSON.stringify({ credential_ids }),
    }),

  addProxyGroupMember: (groupId: string, credentialId: string) =>
    request<ProxyGroup>(`/api/proxy-groups/${groupId}/members/${credentialId}`, {
      method: "POST",
    }),

  removeProxyGroupMember: (groupId: string, credentialId: string) =>
    request<ProxyGroup>(`/api/proxy-groups/${groupId}/members/${credentialId}`, {
      method: "DELETE",
    }),
};

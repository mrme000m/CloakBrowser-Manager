/** Typed REST client for the CloakBrowser-Manager API (fetch + AbortController). */

import { effectiveConfig } from "./config.js";
import { REQUEST_TIMEOUT_MS } from "./constants.js";
import { CommandError, exitCodeForStatus, hintForStatus } from "./errors.js";
import type {
  AuthStatus,
  BulkResultResponse,
  LaunchResult,
  OkResponse,
  Profile,
  ProfileStatus,
  ProxyCredential,
  ProxyGroup,
  ProxyLocations,
  ProxyProvider,
  ProxyTestResult,
  SystemStatus,
  Tag,
} from "./types.js";

/** Effective base URL + token at call time (env may override file). */
function endpoint(): { base: string; token: string } {
  const cfg = effectiveConfig();
  return { base: cfg.api_url.replace(/\/+$/, ""), token: cfg.token };
}

/** Resolve the JSON `detail` from an error response, if any. */
async function errorDetail(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: string; message?: string };
    return body.detail ?? body.message;
  } catch {
    return undefined;
  }
}

/** Core request helper: throws CommandError on HTTP failure. */
async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const { base, token } = endpoint();
  const url = `${base}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (token) headers.Authorization = `Bearer ${token}`;
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof Error && err.name === "AbortError") {
      throw new CommandError(`Request timed out after ${REQUEST_TIMEOUT_MS}ms: ${method} ${path}`, {
        suggestion: "Is the manager reachable? Run `cbpm status` or `cbpm config set api_url <url>`.",
      }, exitCodeForStatus(0) /* EXTERNAL via network */);
    }
    throw new CommandError(`Network error reaching ${url}: ${(err as Error).message}`, {
      suggestion: "Check the API URL (`cbpm config show`) and that the manager is running.",
    }, 100 /* EXTERNAL */);
  }
  clearTimeout(timer);

  if (!res.ok) {
    const detail = await errorDetail(res);
    const code = exitCodeForStatus(res.status);
    throw new CommandError(
      `HTTP ${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`,
      { suggestion: hintForStatus(res.status, detail), detail },
      code,
    );
  }

  // 204 No Content or empty body
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new CommandError(`Invalid JSON response from ${method} ${path}`, {
      suggestion: "The manager returned a non-JSON body — check server logs.",
    }, 110 /* SOFTWARE */);
  }
}

// ── Auth ────────────────────────────────────────────────────────────────────
export const api = {
  authStatus: () => request<AuthStatus>("GET", "/api/auth/status"),
  authLogin: (token: string) => request<{ ok: boolean }>("POST", "/api/auth/login", { token }),
  authLogout: () => request<OkResponse>("POST", "/api/auth/logout"),

  // ── System ────────────────────────────────────────────────────────────────
  systemStatus: () => request<SystemStatus>("GET", "/api/status"),

  // ── Profiles ──────────────────────────────────────────────────────────────
  listProfiles: () => request<Profile[]>("GET", "/api/profiles"),
  getProfile: (id: string) => request<Profile>("GET", `/api/profiles/${id}`),
  createProfile: (data: Record<string, unknown>) =>
    request<Profile>("POST", "/api/profiles", data),
  updateProfile: (id: string, data: Record<string, unknown>) =>
    request<Profile>("PUT", `/api/profiles/${id}`, data),
  deleteProfile: (id: string) => request<OkResponse>("DELETE", `/api/profiles/${id}`),
  launchProfile: (id: string) => request<LaunchResult>("POST", `/api/profiles/${id}/launch`),
  stopProfile: (id: string) => request<OkResponse>("POST", `/api/profiles/${id}/stop`),
  cloneProfile: (id: string, name?: string) =>
    request<Profile>("POST", `/api/profiles/${id}/clone`, name ? { name } : {}),
  profileStatus: (id: string) => request<ProfileStatus>("GET", `/api/profiles/${id}/status`),
  bulkLaunch: (body: { ids?: string[]; tag?: string }) =>
    request<BulkResultResponse>("POST", "/api/profiles/bulk/launch", body),
  bulkStop: (body: { ids?: string[]; tag?: string }) =>
    request<BulkResultResponse>("POST", "/api/profiles/bulk/stop", body),
  bulkDelete: (body: { ids?: string[]; tag?: string }) =>
    request<BulkResultResponse>("POST", "/api/profiles/bulk/delete", body),

  // ── Proxy credentials ─────────────────────────────────────────────────────
  listProxyCredentials: () => request<ProxyCredential[]>("GET", "/api/proxy-credentials"),
  getProxyCredential: (id: string) =>
    request<ProxyCredential>("GET", `/api/proxy-credentials/${id}`),
  createProxyCredential: (data: Record<string, unknown>) =>
    request<ProxyCredential>("POST", "/api/proxy-credentials", data),
  updateProxyCredential: (id: string, data: Record<string, unknown>) =>
    request<ProxyCredential>("PUT", `/api/proxy-credentials/${id}`, data),
  deleteProxyCredential: (id: string) =>
    request<OkResponse>("DELETE", `/api/proxy-credentials/${id}`),
  testProxyCredential: (id: string) =>
    request<ProxyTestResult>("POST", `/api/proxy-credentials/${id}/test`),
  testAllProxyCredentials: () =>
    request<ProxyTestResult[]>("POST", "/api/proxy-credentials/test-all"),

  // ── Proxy providers ───────────────────────────────────────────────────────
  listProxyProviders: () => request<ProxyProvider[]>("GET", "/api/proxy-providers"),
  getProxyProvider: (id: string) => request<ProxyProvider>("GET", `/api/proxy-providers/${id}`),
  createProxyProvider: (data: Record<string, unknown>) =>
    request<ProxyProvider>("POST", "/api/proxy-providers", data),
  updateProxyProvider: (id: string, data: Record<string, unknown>) =>
    request<ProxyProvider>("PUT", `/api/proxy-providers/${id}`, data),
  deleteProxyProvider: (id: string) =>
    request<OkResponse>("DELETE", `/api/proxy-providers/${id}`),

  // ── Proxy groups ──────────────────────────────────────────────────────────
  listProxyGroups: () => request<ProxyGroup[]>("GET", "/api/proxy-groups"),
  getProxyGroup: (id: string) => request<ProxyGroup>("GET", `/api/proxy-groups/${id}`),
  createProxyGroup: (data: Record<string, unknown>) =>
    request<ProxyGroup>("POST", "/api/proxy-groups", data),
  updateProxyGroup: (id: string, data: Record<string, unknown>) =>
    request<ProxyGroup>("PUT", `/api/proxy-groups/${id}`, data),
  deleteProxyGroup: (id: string) =>
    request<OkResponse>("DELETE", `/api/proxy-groups/${id}`),
  setGroupMembers: (id: string, credentialIds: string[]) =>
    request<ProxyGroup>("PUT", `/api/proxy-groups/${id}/members`, { credential_ids: credentialIds }),
  addGroupMember: (groupId: string, credId: string) =>
    request<ProxyGroup>("POST", `/api/proxy-groups/${groupId}/members/${credId}`),
  removeGroupMember: (groupId: string, credId: string) =>
    request<ProxyGroup>("DELETE", `/api/proxy-groups/${groupId}/members/${credId}`),

  // ── Proxy locations ───────────────────────────────────────────────────────
  proxyLocations: () => request<ProxyLocations>("GET", "/api/proxy-locations"),
};

/** A {tag, color} pair as accepted by the profile create/update endpoints. */
export function tag(t: string, color?: string): Tag {
  return color ? { tag: t, color } : { tag: t, color: null };
}

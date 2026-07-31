import { afterEach, beforeEach, describe, test } from "node:test";
import assert from "node:assert/strict";

import { api } from "../src/client.js";
import { EXIT_CODES } from "../src/constants.js";
import { CommandError } from "../src/errors.js";

const origFetch = globalThis.fetch;
function mockFetch(impl: (url: string, init: RequestInit) => Response | Promise<Response>): void {
  globalThis.fetch = impl as typeof fetch;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("client", () => {
  beforeEach(() => {
    process.env.CBPM_API_URL = "http://mgr:8080";
    process.env.CBPM_API_TOKEN = "sekret";
  });
  afterEach(() => {
    globalThis.fetch = origFetch;
    delete process.env.CBPM_API_URL;
    delete process.env.CBPM_API_TOKEN;
  });

  test("systemStatus sends Bearer + parses JSON", async () => {
    let seenUrl = "";
    let seenAuth = "";
    mockFetch((url, init) => {
      seenUrl = String(url);
      const h = (init?.headers ?? {}) as Record<string, string>;
      seenAuth = h.Authorization ?? "";
      return jsonResponse({
        running_count: 2,
        binary_version: "v",
        profiles_total: 5,
        max_running: null,
        total_cpu_percent: null,
        total_mem_mb: null,
        total_proc_count: null,
      });
    });
    const s = await api.systemStatus();
    assert.equal(s.running_count, 2);
    assert.equal(seenUrl, "http://mgr:8080/api/status");
    assert.equal(seenAuth, "Bearer sekret");
  });

  test("createProfile sends POST + JSON body", async () => {
    let method = "";
    let body = "";
    mockFetch((_url, init) => {
      method = init?.method ?? "";
      body = String(init?.body ?? "");
      return jsonResponse({ id: "p1", name: "x" }, 201);
    });
    const p = await api.createProfile({ name: "x" });
    assert.equal(method, "POST");
    assert.equal(JSON.parse(body).name, "x");
    assert.equal(p.id, "p1");
  });

  test("404 -> CommandError NOT_FOUND with detail", async () => {
    mockFetch(() => jsonResponse({ detail: "Profile not found" }, 404));
    await assert.rejects(
      () => api.getProfile("x"),
      (e: unknown) => e instanceof CommandError && (e as CommandError).exitCode === EXIT_CODES.NOT_FOUND && /Profile not found/.test((e as Error).message),
    );
  });

  test("401 -> AUTH", async () => {
    mockFetch(() => jsonResponse({ detail: "Unauthorized" }, 401));
    await assert.rejects(
      () => api.listProfiles(),
      (e: unknown) => (e as CommandError).exitCode === EXIT_CODES.AUTH,
    );
  });

  test("409 -> CONFLICT", async () => {
    mockFetch(() => jsonResponse({ detail: "already running" }, 409));
    await assert.rejects(
      () => api.launchProfile("x"),
      (e: unknown) => (e as CommandError).exitCode === EXIT_CODES.CONFLICT,
    );
  });

  test("429 -> RATE_LIMIT", async () => {
    mockFetch(() => jsonResponse({ detail: "Max running profiles (5) reached" }, 429));
    await assert.rejects(
      () => api.launchProfile("x"),
      (e: unknown) => (e as CommandError).exitCode === EXIT_CODES.RATE_LIMIT,
    );
  });

  test("no token -> no Authorization header", async () => {
    delete process.env.CBPM_API_TOKEN;
    let seenAuth = "unset";
    mockFetch((_url, init) => {
      const h = (init?.headers ?? {}) as Record<string, string>;
      seenAuth = h.Authorization ?? "unset";
      return jsonResponse({ auth_required: false, authenticated: true });
    });
    await api.authStatus();
    assert.equal(seenAuth, "unset");
  });
});

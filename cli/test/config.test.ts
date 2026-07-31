import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { effectiveConfig, readConfig, setConfigKey, unsetConfigKey } from "../src/config.js";
import { DEFAULT_API_URL } from "../src/constants.js";

let dir: string;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "cbpm-"));
  process.env.HOME = dir;
  delete process.env.CBPM_API_URL;
  delete process.env.CBPM_API_TOKEN;
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

test("readConfig returns defaults when no file", () => {
  const c = readConfig();
  assert.equal(c.api_url, DEFAULT_API_URL);
  assert.equal(c.token, "");
});

test("setConfigKey persists and is read back", () => {
  setConfigKey("api_url", "https://mgr.example");
  setConfigKey("token", "tok-123");
  const c = readConfig();
  assert.equal(c.api_url, "https://mgr.example");
  assert.equal(c.token, "tok-123");
});

test("unsetConfigKey reverts api_url to default", () => {
  setConfigKey("api_url", "https://mgr.example");
  unsetConfigKey("api_url");
  assert.equal(readConfig().api_url, DEFAULT_API_URL);
});

test("effectiveConfig env overrides the file", () => {
  setConfigKey("api_url", "https://file.example");
  setConfigKey("token", "file-tok");
  process.env.CBPM_API_URL = "https://env.example";
  process.env.CBPM_API_TOKEN = "env-tok";
  const c = effectiveConfig();
  assert.equal(c.api_url, "https://env.example");
  assert.equal(c.token, "env-tok");
});

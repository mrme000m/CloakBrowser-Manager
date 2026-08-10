import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { bodyFromOptions } from "../src/commands/profiles.js";
import { CommandError } from "../src/errors.js";
import { EXIT_CODES } from "../src/constants.js";
import { PROFILE_FIELDS, parseJsonObject } from "../src/schema.js";

test("PROFILE_FIELDS includes storage_state and human_config", () => {
  assert.ok(PROFILE_FIELDS.find((f) => f.name === "storage_state"), "storage_state present");
  assert.ok(PROFILE_FIELDS.find((f) => f.name === "human_config"), "human_config present");
});

test("parseJsonObject parses inline JSON", () => {
  const r = parseJsonObject('{"cookies":[]}', "storage_state");
  assert.equal(r.ok, true);
  if (r.ok) assert.deepEqual(r.value, { cookies: [] });
});

test("parseJsonObject reads a file path", () => {
  const tmp = mkdtempSync(join(tmpdir(), "cbpm-jsonfield-"));
  try {
    const p = join(tmp, "state.json");
    writeFileSync(p, '{"cookies":[{"name":"s"}]}', "utf-8");
    const r = parseJsonObject(p, "storage_state");
    assert.equal(r.ok, true);
    if (r.ok) assert.deepEqual(r.value, { cookies: [{ name: "s" }] });
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("parseJsonObject rejects an array", () => {
  const r = parseJsonObject("[1,2]", "storage_state");
  assert.equal(r.ok, false);
  if (!r.ok) assert.match(r.error, /got array/);
});

test("parseJsonObject rejects malformed JSON", () => {
  const r = parseJsonObject("{bad", "human_config");
  assert.equal(r.ok, false);
  if (!r.ok) assert.match(r.error, /--human-config is not valid JSON/);
});

test("parseJsonObject rejects empty string", () => {
  const r = parseJsonObject("", "human_config");
  assert.equal(r.ok, false);
  if (!r.ok) assert.match(r.error, /is empty/);
});

test("bodyFromOptions omits dict fields when not provided", () => {
  const body = bodyFromOptions({ name: "shop" });
  assert.equal("storage_state" in body, false);
  assert.equal("human_config" in body, false);
  assert.equal(body.name, "shop");
});

test("bodyFromOptions parses storage_state inline", () => {
  // bodyFromOptions keys opts by camel(f.name) -> storageState (Commander shape)
  const body = bodyFromOptions({ storageState: '{"cookies":[],"origins":[]}' });
  assert.deepEqual(body.storage_state, { cookies: [], origins: [] });
});

test("bodyFromOptions parses human_config inline", () => {
  const body = bodyFromOptions({ humanConfig: '{"typing_delay":120}' });
  assert.deepEqual(body.human_config, { typing_delay: 120 });
});

test("bodyFromOptions parses storage_state from a file path", () => {
  const tmp = mkdtempSync(join(tmpdir(), "cbpm-bodyfromopts-"));
  try {
    const p = join(tmp, "state.json");
    writeFileSync(p, '{"cookies":[]}', "utf-8");
    const body = bodyFromOptions({ storageState: p });
    assert.deepEqual(body.storage_state, { cookies: [] });
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("bodyFromOptions throws CommandError (exit 80) on malformed storage_state", () => {
  assert.throws(
    () => bodyFromOptions({ storageState: "{bad" }),
    (e: unknown) => e instanceof CommandError && (e as CommandError).exitCode === EXIT_CODES.INVALID_ARGS
  );
});

test("bodyFromOptions still forwards scalar fields", () => {
  const body = bodyFromOptions({ name: "shop", timezone: "America/New_York" });
  assert.equal(body.name, "shop");
  assert.equal(body.timezone, "America/New_York");
});

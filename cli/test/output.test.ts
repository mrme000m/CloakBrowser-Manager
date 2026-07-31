import { test } from "node:test";
import assert from "node:assert/strict";

import { VERSION } from "../src/constants.js";
import { buildJsonError, buildSuccessResponse } from "../src/output.js";

test("success envelope is versioned + carries data", () => {
  const env = buildSuccessResponse({ a: 1 });
  assert.equal(env.version, VERSION);
  assert.equal(env.success, true);
  assert.deepEqual(env.data, { a: 1 });
});

test("error envelope carries exitCode + suggestion", () => {
  const env = buildJsonError("boom", { exitCode: 90, suggestion: "try cbpm profiles list" });
  assert.equal(env.version, VERSION);
  assert.equal(env.success, false);
  assert.equal(env.error, "boom");
  assert.equal(env.exitCode, 90);
  assert.equal(env.suggestion, "try cbpm profiles list");
});

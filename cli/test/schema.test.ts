import { test } from "node:test";
import assert from "node:assert/strict";

import { PROFILE_FIELDS, findField, suggestFields } from "../src/schema.js";

test("has a required name field", () => {
  const f = PROFILE_FIELDS.find((x) => x.name === "name");
  assert.ok(f, "name field present");
  assert.equal(f?.required, true);
  assert.equal(f?.flag, "--name");
});

test("findField by snake name", () => {
  assert.equal(findField("platform")?.name, "platform");
});

test("findField by --flag form", () => {
  assert.equal(findField("--fingerprint-seed")?.name, "fingerprint_seed");
  assert.equal(findField("fingerprint-seed")?.name, "fingerprint_seed");
});

test("suggestFields returns near-miss candidates", () => {
  const s = suggestFields("platfrm");
  assert.ok(s.some((f) => f.name === "platform"), "suggests platform for 'platfrm'");
});

test("all fields have a flag and a description", () => {
  for (const f of PROFILE_FIELDS) {
    assert.ok(f.flag.startsWith("--"), `${f.name} flag`);
    assert.ok(f.description.length > 0, `${f.name} description`);
  }
});

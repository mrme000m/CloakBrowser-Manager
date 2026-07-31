import { test } from "node:test";
import assert from "node:assert/strict";
import { Command } from "commander";

import { generateMachineReadableHelp, generateSubcommandHelp } from "../src/helpJson.js";

test("machine help shape", () => {
  const p = new Command().name("cbpm").description("d").version("0.1.0");
  p.command("status").description("s").option("-j, --json", "json", false);
  const h = generateMachineReadableHelp(p);
  assert.equal(h.name, "cbpm");
  assert.equal(h.version, "0.1.0");
  assert.equal(h.description, "d");
  assert.ok(h.command.subcommands.some((c) => c.name === "status"));
  assert.ok(h.exitCodes.length > 0);
  assert.ok(h.taskMappings.length > 0);
  assert.equal(typeof h.runtimeState.api_url, "string");
});

test("subcommand help resolves a path", () => {
  const p = new Command().name("cbpm");
  const profiles = p.command("profiles").description("profiles");
  profiles.command("list").description("list").option("--tag <t>", "tag");
  const h = generateSubcommandHelp(p, ["profiles", "list"]);
  assert.equal(h.path.join("."), "profiles.list");
  assert.equal(h.command.name, "list");
  assert.ok(h.command.options.some((o) => o.flags.includes("--tag")));
});

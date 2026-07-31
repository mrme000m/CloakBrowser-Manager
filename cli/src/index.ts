#!/usr/bin/env node
/** cbpm — CloakBrowser Profile Manager CLI (self-explaining). */

import { Command } from "commander";

import { CLI_DESCRIPTION, CLI_NAME, VERSION } from "./constants.js";
import { commandRegistry } from "./commands.js";
import { generateMachineReadableHelp, generateSubcommandHelp } from "./helpJson.js";

/** Extract the subcommand path (leading non-flag tokens) from argv. */
function extractCommandPath(argv: string[]): string[] {
  const path: string[] = [];
  for (const a of argv.slice(2)) {
    if (a === "--help" || a === "--json") continue;
    if (a.startsWith("-")) break;
    path.push(a);
  }
  return path;
}

async function main(): Promise<void> {
  const program = new Command()
    .name(CLI_NAME)
    .description(CLI_DESCRIPTION)
    .version(VERSION);

  // Register all commands (builds the introspection tree before --help --json).
  commandRegistry.forEach((register) => register(program));

  const argv = process.argv;

  // Self-explaining machine-readable help: `cbpm [--help --json]` or `cbpm <path> --help --json`.
  if (argv.includes("--help") && argv.includes("--json")) {
    const path = extractCommandPath(argv);
    const help = path.length > 0 ? generateSubcommandHelp(program, path) : generateMachineReadableHelp(program);
    console.log(JSON.stringify(help, null, 2));
    process.exit(0);
  }

  // No arguments → show help (Commander otherwise errors with no root action).
  if (argv.slice(2).length === 0) {
    program.outputHelp();
    process.exit(0);
  }

  await program.parseAsync();
}

main().catch((err) => {
  process.stderr.write(`cbpm: ${err instanceof Error ? err.message : String(err)}\n`);
  process.exit(1);
});

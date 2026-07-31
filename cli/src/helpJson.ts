/** Machine-readable `--help --json` engine (bdg-style self-description). */

import type { Command, Option } from "commander";
import { effectiveConfig } from "./config.js";
import { CLI_DESCRIPTION, CLI_NAME, EXIT_CODE_DOCS, VERSION } from "./constants.js";

export interface HelpOption {
  flags: string;
  description: string;
  required: boolean;
  default?: unknown;
}

export interface HelpCommand {
  name: string;
  description: string;
  usage?: string;
  args: { name: string; required: boolean; variadic: boolean }[];
  options: HelpOption[];
  subcommands: HelpCommand[];
}

export interface TaskMapping {
  intent: string;
  commands: string[];
  description: string;
}

export interface RuntimeState {
  api_url: string;
  token_set: boolean;
}

export interface MachineReadableHelp {
  name: string;
  version: string;
  description: string;
  command: HelpCommand;
  exitCodes: typeof EXIT_CODE_DOCS;
  taskMappings: TaskMapping[];
  runtimeState: RuntimeState;
}

const TASK_MAPPINGS: TaskMapping[] = [
  { intent: "create_profile", commands: ["cbpm profiles create --name <n>"], description: "Create a new browser profile. Use --list-fields to discover all options." },
  { intent: "list_profiles", commands: ["cbpm profiles list"], description: "List all profiles with status/resources." },
  { intent: "launch_profile", commands: ["cbpm profiles launch <id>"], description: "Launch a profile's browser." },
  { intent: "stop_profile", commands: ["cbpm profiles stop <id>"], description: "Stop a running profile." },
  { intent: "clone_profile", commands: ["cbpm profiles clone <id> [--name <n>]"], description: "Clone a profile (new identity seed)." },
  { intent: "delete_profile", commands: ["cbpm profiles delete <id>"], description: "Delete a profile and its data." },
  { intent: "connect_cdp", commands: ["cbpm profiles connect <id>"], description: "Show CDP connection snippets (Playwright/Puppeteer/curl/bdg)." },
  { intent: "bulk_launch_tagged", commands: ["cbpm profiles bulk launch --tag <t>"], description: "Launch all profiles with a tag." },
  { intent: "test_proxy", commands: ["cbpm proxy-credentials test <id>", "cbpm proxy-credentials test-all"], description: "Verify a proxy's exit IP/country/latency." },
  { intent: "list_proxy_locations", commands: ["cbpm proxy-locations --list"], description: "List the provider location catalog (self-explaining)." },
  { intent: "manage_proxy_rotation", commands: ["cbpm proxy-groups create", "cbpm proxy-groups members <id> --ids ..."], description: "Create a rotation group and assign member credentials." },
  { intent: "manager_status", commands: ["cbpm status"], description: "Show running/profile counts + aggregate resources." },
];

function convertOption(opt: Option): HelpOption {
  return {
    flags: opt.flags,
    description: opt.description,
    required: opt.required,
    ...(opt.defaultValue !== undefined ? { default: opt.defaultValue } : {}),
  };
}

function convertCommand(cmd: Command): HelpCommand {
  const args = (cmd.registeredArguments || []).map((a) => ({
    name: a.name(),
    required: !a.variadic,
    variadic: Boolean(a.variadic),
  }));
  return {
    name: cmd.name(),
    description: cmd.description() || "",
    usage: cmd.usage?.(),
    args,
    options: (cmd.options || []).map(convertOption),
    subcommands: (cmd.commands || []).map(convertCommand),
  };
}

function runtimeState(): RuntimeState {
  const cfg = effectiveConfig();
  return { api_url: cfg.api_url, token_set: Boolean(cfg.token) };
}

/** Top-level machine-readable help for the whole program. */
export function generateMachineReadableHelp(program: Command): MachineReadableHelp {
  return {
    name: program.name() || CLI_NAME,
    version: program.version() || VERSION,
    description: program.description() || CLI_DESCRIPTION,
    command: convertCommand(program),
    exitCodes: EXIT_CODE_DOCS,
    taskMappings: TASK_MAPPINGS,
    runtimeState: runtimeState(),
  };
}

/** Find a subcommand by a path of names (e.g. ["profiles","list"]). */
function findSubcommand(cmd: Command, path: string[]): Command | undefined {
  let cur: Command | undefined = cmd;
  for (const name of path) {
    cur = (cur.commands || []).find((c) => c.name() === name);
    if (!cur) return undefined;
  }
  return cur;
}

/** Machine-readable help scoped to a subcommand path. */
export function generateSubcommandHelp(program: Command, path: string[]): { path: string[]; command: HelpCommand; runtimeState: RuntimeState } {
  const sub = findSubcommand(program, path);
  const command = sub ? convertCommand(sub) : convertCommand(program);
  return { path, command, runtimeState: runtimeState() };
}

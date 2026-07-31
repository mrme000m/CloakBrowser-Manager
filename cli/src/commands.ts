/** Ordered command registry with help-output groups (bdg-style). */

import type { Command } from "commander";

import { registerAuthCommand } from "./commands/auth.js";
import { registerConfigCommand } from "./commands/config.js";
import { registerProfilesCommand } from "./commands/profiles.js";
import { registerProxyCredentialsCommand } from "./commands/proxyCredentials.js";
import { registerProxyGroupsCommand } from "./commands/proxyGroups.js";
import { registerProxyLocationsCommand } from "./commands/proxyLocations.js";
import { registerProxyProvidersCommand } from "./commands/proxyProviders.js";
import { registerStatusCommand } from "./commands/status.js";

export type CommandRegistrar = (program: Command) => void;

/** A sentinel registrar that emits a section header in the human help output. */
function addGroup(_name: string): CommandRegistrar {
  // Commander has no first-class group concept; we rely on registration order
  // and the built-in grouped help. This placeholder keeps the registry readable.
  return () => undefined;
}

export const commandRegistry: CommandRegistrar[] = [
  registerStatusCommand,
  addGroup("Configuration & Auth:"),
  registerConfigCommand,
  registerAuthCommand,
  addGroup("Profiles:"),
  registerProfilesCommand,
  addGroup("Proxy Management:"),
  registerProxyCredentialsCommand,
  registerProxyProvidersCommand,
  registerProxyGroupsCommand,
  registerProxyLocationsCommand,
];

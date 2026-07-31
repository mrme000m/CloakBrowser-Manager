/** `cbpm config get|set|unset|show` — manage ~/.cbpm/config.json. */

import { Command } from "commander";

import { effectiveConfig, readConfig, setConfigKey, unsetConfigKey } from "../config.js";
import { configPath } from "../constants.js";
import { runCommand } from "../runner.js";

type Key = "api_url" | "token";

function isKey(v: string): v is Key {
  return v === "api_url" || v === "token";
}

export function registerConfigCommand(program: Command): void {
  const cfg = program
    .command("config")
    .description("Manage CLI configuration (~/.cbpm/config.json): api_url + token");

  cfg
    .command("get <key>")
    .description("Print a single config value (api_url | token)")
    .action((key: string) => {
      if (!isKey(key)) {
        process.stderr.write(`Error: unknown key '${key}'. Valid: api_url | token\n`);
        process.exit(80);
      }
      const c = effectiveConfig();
      console.log(key === "token" ? c.token : c.api_url);
      process.exit(0);
    });

  cfg
    .command("set <key> <value>")
    .description("Set a config value (api_url | token). Token is stored with 0600 perms.")
    .action((key: string, value: string) => {
      if (!isKey(key)) {
        process.stderr.write(`Error: unknown key '${key}'. Valid: api_url | token\n`);
        process.exit(80);
      }
      const c = setConfigKey(key, value);
      process.stderr.write(`Set ${key} in ${configPath()}\n`);
      // Never print the token to stdout; print api_url only.
      console.log(key === "token" ? "token: ******" : `${key}: ${c.api_url}`);
      process.exit(0);
    });

  cfg
    .command("unset <key>")
    .description("Unset a config value (revert api_url to default, clear token)")
    .action((key: string) => {
      if (!isKey(key)) {
        process.stderr.write(`Error: unknown key '${key}'. Valid: api_url | token\n`);
        process.exit(80);
      }
      unsetConfigKey(key);
      process.stderr.write(`Unset ${key}\n`);
      process.exit(0);
    });

  cfg
    .command("show")
    .description("Show the effective config (token masked) + file path")
    .option("-j, --json", "Output as JSON", false)
    .action((options: { json?: boolean }) => {
      void runCommand(
        () => {
          const c = effectiveConfig();
          const masked = { api_url: c.api_url, token_set: Boolean(c.token) };
          return {
            success: true,
            data: { ...masked, config_path: configPath() } as { api_url: string; token_set: boolean; config_path: string },
          };
        },
        options,
        (d) => `api_url:   ${d.api_url}\ntoken_set: ${d.token_set}\nconfig:   ${d.config_path}`,
      );
    });

  // Plain `cbpm config` (no subcommand) prints the file contents read-only.
  cfg.action(() => {
    const c = readConfig();
    console.log(`api_url: ${c.api_url}\ntoken:  ${c.token ? "******" : "(unset)"}\nfile:   ${configPath()}`);
    process.exit(0);
  });
}

/** `cbpm auth status|login|logout` — token-based auth against the manager. */

import { Command } from "commander";

import { api } from "../client.js";
import { setConfigKey, unsetConfigKey } from "../config.js";
import { CommandError } from "../errors.js";
import { formatAuth } from "../format.js";
import { runCommand } from "../runner.js";

export function registerAuthCommand(program: Command): void {
  const auth = program
    .command("auth")
    .description("Authentication (the manager's AUTH_TOKEN)");

  auth
    .command("status")
    .description("Show whether the manager requires auth and whether the configured token is valid")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { json?: boolean }) => {
      await runCommand(
        async () => {
          const data = await api.authStatus();
          return { success: true, data };
        },
        options,
        formatAuth,
      );
    });

  auth
    .command("login <token>")
    .description("Validate a token against the manager and store it for future commands")
    .option("-j, --json", "Output as JSON", false)
    .action(async (token: string, options: { json?: boolean }) => {
      await runCommand(
        async () => {
          // Validate by hitting the login endpoint (constant-time check server-side).
          const res = await api.authLogin(token);
          if (!res.ok) {
            throw new CommandError("Token rejected by the manager", {
              suggestion: "Check the token matches the manager's AUTH_TOKEN.",
            }, 81);
          }
          setConfigKey("token", token);
          return { success: true, data: { ok: true, token_stored: true } };
        },
        options,
        () => "Login OK — token stored in ~/.cbpm/config.json",
      );
    });

  auth
    .command("logout")
    .description("Clear the stored token (the manager uses Bearer auth, not a session)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { json?: boolean }) => {
      await runCommand(
        async () => {
          try {
            await api.authLogout();
          } catch {
            // Best-effort: clearing the stored token is what matters for the CLI.
          }
          unsetConfigKey("token");
          return { success: true, data: { ok: true, token_cleared: true } };
        },
        options,
        () => "Logged out — stored token cleared",
      );
    });
}

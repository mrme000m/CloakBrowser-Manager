/** `cbpm status` — manager system status. */

import { Command } from "commander";

import { api } from "../client.js";
import { formatSystemStatus } from "../format.js";
import { runCommand } from "../runner.js";

export function registerStatusCommand(program: Command): void {
  program
    .command("status")
    .description("Show manager status: running/profile counts + aggregate resource usage")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { json?: boolean }) => {
      await runCommand(
        async () => {
          const data = await api.systemStatus();
          return { success: true, data };
        },
        options,
        formatSystemStatus,
      );
    });
}

/** `cbpm proxy-groups ...` — proxy rotation groups + members. */

import { Command, Option } from "commander";

import { api } from "../client.js";
import { formatProxyGroup, formatProxyGroupList } from "../format.js";
import { runCommand, parseIds } from "../runner.js";

export function registerProxyGroupsCommand(program: Command): void {
  const groups = program
    .command("proxy-groups")
    .description("Manage proxy rotation groups (round_robin / sticky_session / random)");

  groups
    .command("list")
    .description("List proxy groups")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.listProxyGroups() }), options, formatProxyGroupList);
    });

  groups
    .command("create")
    .description("Create a proxy rotation group")
    .option("-j, --json", "Output as JSON", false)
    .option("--name <name>", "Group name", "group")
    .addOption(
      new Option("--rotation-mode <mode>", "How members are chosen on each launch")
        .choices(["round_robin", "sticky_session", "random"])
        .default("round_robin"),
    )
    .action(async (options: Record<string, unknown> & { json?: boolean }) => {
      const body: Record<string, unknown> = {
        name: options.name,
        rotation_mode: options.rotationMode,
      };
      await runCommand(
        async () => ({ success: true, data: await api.createProxyGroup(body) }),
        { json: options.json },
        (g) => `Created group ${g.id} (${g.name}, ${g.rotation_mode})`,
      );
    });

  groups
    .command("get <id>")
    .description("Show a group with its members")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.getProxyGroup(id) }), options, formatProxyGroup);
    });

  groups
    .command("update <id>")
    .description("Update a group's name/rotation mode")
    .option("-j, --json", "Output as JSON", false)
    .option("--name <name>", "Group name")
    .addOption(
      new Option("--rotation-mode <mode>", "Rotation mode").choices(["round_robin", "sticky_session", "random"]),
    )
    .action(async (id: string, options: Record<string, unknown> & { json?: boolean }) => {
      const body: Record<string, unknown> = {};
      if (options.name !== undefined) body.name = options.name;
      if (options.rotationMode !== undefined) body.rotation_mode = options.rotationMode;
      if (Object.keys(body).length === 0) {
        process.stderr.write("Error: no fields provided to update.\n");
        process.exit(80);
      }
      await runCommand(
        async () => ({ success: true, data: await api.updateProxyGroup(id, body) }),
        { json: options.json },
        (g) => `Updated ${g.id}`,
      );
    });

  groups
    .command("delete <id>")
    .description("Delete a group (fails if profiles reference it)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.deleteProxyGroup(id) }), options, () =>
        `Deleted ${id}`,
      );
    });

  groups
    .command("members <id>")
    .description("Replace the group's member credentials (ordered list)")
    .option("--ids <ids>", "Comma-separated credential ids")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { ids?: string; json?: boolean }) => {
      if (!options.ids) {
        process.stderr.write("Error: --ids <csv> is required.\n");
        process.exit(80);
      }
      const ids = parseIds(options.ids);
      await runCommand(
        async () => ({ success: true, data: await api.setGroupMembers(id, ids) }),
        options,
        (g) => `${g.name} now has ${g.member_count} member(s)`,
      );
    });

  groups
    .command("add <id> <credId>")
    .description("Append a credential to a group")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, credId: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.addGroupMember(id, credId) }), options, (g) =>
        `${g.name}: added ${credId}`,
      );
    });

  groups
    .command("remove <id> <credId>")
    .description("Remove a credential from a group")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, credId: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.removeGroupMember(id, credId) }), options, (g) =>
        `${g.name}: removed ${credId}`,
      );
    });
}

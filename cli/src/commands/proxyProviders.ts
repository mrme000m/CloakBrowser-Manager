/** `cbpm proxy-providers ...` — proxy provider accounts. */

import { Command, Option } from "commander";

import { api } from "../client.js";
import { formatProxyProviderList } from "../format.js";
import { runCommand } from "../runner.js";

export function registerProxyProvidersCommand(program: Command): void {
  const prov = program
    .command("proxy-providers")
    .description("Manage proxy provider accounts (e.g. one IPVanish account)");

  prov
    .command("list")
    .description("List proxy providers")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.listProxyProviders() }), options, formatProxyProviderList);
    });

  prov
    .command("create")
    .description("Create a provider account")
    .option("-j, --json", "Output as JSON", false)
    .option("--name <name>", "Provider name", "provider")
    .addOption(
      new Option("--type <type>", "Provider type").choices(["ipvanish", "brightdata", "smartproxy", "custom"]).default("custom"),
    )
    .addOption(new Option("--scheme <scheme>", "Proxy scheme").choices(["http", "https", "socks5"]).default("socks5"))
    .option("--host-template <tpl>", "Host template for custom providers (e.g. {location}.proxy.example)")
    .option("--port <port>", "Proxy port", (v: string) => parseInt(v, 10), 1080)
    .option("--username <user>", "Username")
    .option("--password <pass>", "Password")
    .action(async (options: Record<string, unknown> & { json?: boolean }) => {
      const body: Record<string, unknown> = {
        name: options.name,
        type: options.type,
        scheme: options.scheme,
        host_template: options.hostTemplate ?? "",
        port: options.port,
        username: options.username ?? "",
        password: options.password ?? "",
        options: {},
      };
      await runCommand(
        async () => ({ success: true, data: await api.createProxyProvider(body) }),
        { json: options.json },
        (p) => `Created provider ${p.id} (${p.name}, ${p.type})`,
      );
    });

  prov
    .command("get <id>")
    .description("Show a provider")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.getProxyProvider(id) }), options, (p) =>
        JSON.stringify(p, null, 2),
      );
    });

  prov
    .command("update <id>")
    .description("Update a provider (only provided fields change)")
    .option("-j, --json", "Output as JSON", false)
    .option("--name <name>", "Provider name")
    .addOption(new Option("--type <type>", "Provider type").choices(["ipvanish", "brightdata", "smartproxy", "custom"]))
    .addOption(new Option("--scheme <scheme>", "Proxy scheme").choices(["http", "https", "socks5"]))
    .option("--host-template <tpl>", "Host template")
    .option("--port <port>", "Proxy port", (v: string) => parseInt(v, 10))
    .option("--username <user>", "Username")
    .option("--password <pass>", "Password")
    .action(async (id: string, options: Record<string, unknown> & { json?: boolean }) => {
      const body: Record<string, unknown> = {};
      for (const [from, to] of [
        ["name", "name"], ["type", "type"], ["scheme", "scheme"], ["hostTemplate", "host_template"],
        ["port", "port"], ["username", "username"], ["password", "password"],
      ] as [string, string][]) {
        if (options[from] !== undefined) body[to] = options[from];
      }
      if (Object.keys(body).length === 0) {
        process.stderr.write("Error: no fields provided to update.\n");
        process.exit(80);
      }
      await runCommand(
        async () => ({ success: true, data: await api.updateProxyProvider(id, body) }),
        { json: options.json },
        (p) => `Updated ${p.id}`,
      );
    });

  prov
    .command("delete <id>")
    .description("Delete a provider (fails if credentials are linked to it)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.deleteProxyProvider(id) }), options, () =>
        `Deleted ${id}`,
      );
    });
}

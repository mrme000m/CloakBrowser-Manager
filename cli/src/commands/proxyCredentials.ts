/** `cbpm proxy-credentials ...` — saved proxy credentials. */

import { Command, Option } from "commander";

import { api } from "../client.js";
import { formatProxyCredentialList, formatProxyTest } from "../format.js";
import { runCommand } from "../runner.js";

export function registerProxyCredentialsCommand(program: Command): void {
  const creds = program
    .command("proxy-credentials")
    .description("Manage saved proxy credentials (test exit IP / country / latency)");

  creds
    .command("list")
    .description("List proxy credentials with last health status")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.listProxyCredentials() }),
        options,
        formatProxyCredentialList,
      );
    });

  creds
    .command("create")
    .description("Create a proxy credential. Use --provider-id + --provider-location for a provider account.")
    .option("-j, --json", "Output as JSON", false)
    .option("--name <name>", "Credential name", "proxy")
    .addOption(new Option("--scheme <scheme>", "Proxy scheme").choices(["http", "https", "socks5"]).default("socks5"))
    .option("--host <host>", "Proxy host")
    .option("--port <port>", "Proxy port", (v: string) => parseInt(v, 10), 1080)
    .option("--username <user>", "Username")
    .option("--password <pass>", "Password")
    .option("--provider-id <id>", "Link to a proxy provider account")
    .option("--provider-location <code>", "Location code from the provider catalog (see `cbpm proxy-locations`)")
    .action(
      async (options: Record<string, unknown> & { json?: boolean }) => {
        const body: Record<string, unknown> = { name: options.name };
        for (const k of ["scheme", "host", "port", "username", "password", "providerId", "providerLocation"]) {
          if (options[k] !== undefined) {
            body[k === "providerId" ? "provider_id" : k === "providerLocation" ? "provider_location" : k] = options[k];
          }
        }
        await runCommand(
          async () => ({ success: true, data: await api.createProxyCredential(body) }),
          { json: options.json },
          (c) => `Created ${c.id} (${c.name})`,
        );
      },
    );

  creds
    .command("get <id>")
    .description("Show a proxy credential")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.getProxyCredential(id) }), options, (c) =>
        JSON.stringify(c, null, 2),
      );
    });

  creds
    .command("update <id>")
    .description("Update a proxy credential (only provided fields change)")
    .option("-j, --json", "Output as JSON", false)
    .addOption(new Option("--scheme <scheme>", "Proxy scheme").choices(["http", "https", "socks5"]))
    .option("--name <name>", "Credential name")
    .option("--host <host>", "Proxy host")
    .option("--port <port>", "Proxy port", (v: string) => parseInt(v, 10))
    .option("--username <user>", "Username")
    .option("--password <pass>", "Password")
    .option("--provider-id <id>", "Link to a proxy provider account")
    .option("--provider-location <code>", "Location code")
    .action(async (id: string, options: Record<string, unknown> & { json?: boolean }) => {
      const body: Record<string, unknown> = {};
      for (const k of ["scheme", "name", "host", "port", "username", "password", "providerId", "providerLocation"]) {
        if (options[k] !== undefined) {
          body[k === "providerId" ? "provider_id" : k === "providerLocation" ? "provider_location" : k] = options[k];
        }
      }
      if (Object.keys(body).length === 0) {
        process.stderr.write("Error: no fields provided to update.\n");
        process.exit(80);
      }
      await runCommand(
        async () => ({ success: true, data: await api.updateProxyCredential(id, body) }),
        { json: options.json },
        (c) => `Updated ${c.id}`,
      );
    });

  creds
    .command("delete <id>")
    .description("Delete a proxy credential (fails if in use by a profile/group)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.deleteProxyCredential(id) }),
        options,
        () => `Deleted ${id}`,
      );
    });

  creds
    .command("test <id>")
    .description("Test a proxy credential (exit IP / country / timezone / latency)")
    .option("-j, --json", "Output as JSON", false)
    .action(async (id: string, options: { json?: boolean }) => {
      await runCommand(async () => ({ success: true, data: await api.testProxyCredential(id) }), options, formatProxyTest);
    });

  creds
    .command("test-all")
    .description("Test every proxy credential")
    .option("-j, --json", "Output as JSON", false)
    .action(async (options: { json?: boolean }) => {
      await runCommand(
        async () => ({ success: true, data: await api.testAllProxyCredentials() }),
        options,
        (results) => results.map((r) => formatProxyTest(r)).join("\n"),
      );
    });
}

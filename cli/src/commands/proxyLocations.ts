/** `cbpm proxy-locations` — self-explaining introspection over the provider location catalog.

 * Mirrors `bdg cdp --list/--describe/--search`: the catalog is fetched from the
 * manager and explored client-side, so the user discovers locations without docs.
 */

import { Command } from "commander";

import { api } from "../client.js";
import { CommandError } from "../errors.js";
import { formatLocationList, pad, truncate } from "../format.js";
import { runCommand } from "../runner.js";
import type { ProxyLocation, ProxyLocations } from "../types.js";

interface CatalogEntry {
  provider: string;
  code: string;
  loc: ProxyLocation;
}

type LocationsData =
  | CatalogEntry
  | { query: string; results: CatalogEntry[] }
  | { entries: CatalogEntry[] };

function flatten(catalog: ProxyLocations): CatalogEntry[] {
  const out: CatalogEntry[] = [];
  for (const [provider, codes] of Object.entries(catalog)) {
    for (const [code, loc] of Object.entries(codes)) {
      out.push({ provider, code, loc });
    }
  }
  return out;
}

function describeEntry(entry: CatalogEntry): string {
  return [
    `${entry.provider}/${entry.code} — ${entry.loc.city}, ${entry.loc.country}`,
    `  provider: ${entry.provider}`,
    `  code:     ${entry.code}`,
    `  host:     ${entry.loc.host}`,
    `  city:     ${entry.loc.city}`,
    `  country:  ${entry.loc.country}`,
    ``,
    `Create a credential from this location:`,
    `  cbpm proxy-credentials create --name "${entry.loc.city}" --provider-id <${entry.provider}-provider-id> --provider-location ${entry.code}`,
  ].join("\n");
}

function searchEntries(entries: CatalogEntry[], q: string): CatalogEntry[] {
  const needle = q.toLowerCase();
  return entries.filter(
    (e) =>
      e.code.toLowerCase().includes(needle) ||
      e.loc.city.toLowerCase().includes(needle) ||
      e.loc.country.toLowerCase().includes(needle) ||
      e.provider.toLowerCase().includes(needle),
  );
}

export function registerProxyLocationsCommand(program: Command): void {
  program
    .command("proxy-locations")
    .description(
      "Provider location catalog (self-explaining): --list, --describe <code>, --search <query>",
    )
    .option("--list", "List all locations (provider, code, city, country, host)")
    .option("--describe <code>", "Show full details + a create-credential example for a code")
    .option("--search <query>", "Search codes/cities/countries/providers")
    .option("--provider <type>", "Filter --list to one provider type")
    .option("-j, --json", "Output as JSON", false)
    .action(
      async (options: { list?: boolean; describe?: string; search?: string; provider?: string; json?: boolean }) => {
        // Default to --list when no mode flag is given; the handler's else
        // branch produces the full catalog, so --list is the implicit default.
        await runCommand<LocationsData>(
          async () => {
            const catalog = await api.proxyLocations();
            let entries = flatten(catalog);
            if (options.provider) entries = entries.filter((e) => e.provider === options.provider);

            let data: LocationsData;
            if (options.describe) {
              const found = entries.find((e) => e.code === options.describe);
              if (!found) {
                throw new CommandError(
                  `Unknown location code: ${options.describe}`,
                  {
                    suggestion: `Run \`cbpm proxy-locations --list${options.provider ? ` --provider ${options.provider}` : ""}\` to see available codes.`,
                  },
                  90,
                );
              }
              data = found;
            } else if (options.search) {
              data = { query: options.search, results: searchEntries(entries, options.search) };
            } else {
              data = { entries };
            }
            return { success: true, data };
          },
          options,
          (data: LocationsData) => {
            if ("loc" in data && "provider" in data) {
              return describeEntry(data);
            }
            if ("query" in data) {
              const d = data;
              if (d.results.length === 0) return `No locations matched '${d.query}'.`;
              return formatLocationList(Object.fromEntries(d.results.map((r) => [r.code, r.loc])));
            }
            const d = data;
            if (d.entries.length === 0) return "No locations in the catalog.";
            return d.entries
              .map((e) => `${pad(e.provider, 10)} ${pad(e.code, 8)} ${pad(truncate(e.loc.city, 18), 18)} ${pad(e.loc.country, 14)} ${e.loc.host}`)
              .join("\n");
          },
        );
      },
    );
}

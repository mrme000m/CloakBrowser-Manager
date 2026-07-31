/** Config management: ~/.cbpm/config.json with env-var overrides. */

import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import { configPath, DEFAULT_API_URL, ENV_API_TOKEN, ENV_API_URL } from "./constants.js";

export interface CbpmConfig {
  api_url: string;
  token: string;
}

function emptyConfig(): CbpmConfig {
  return { api_url: DEFAULT_API_URL, token: "" };
}

/** Read the persisted config file (defaults if missing/corrupt). */
export function readConfig(): CbpmConfig {
  try {
    const path = configPath();
    if (!existsSync(path)) return emptyConfig();
    const raw = JSON.parse(readFileSync(path, "utf-8")) as Partial<CbpmConfig>;
    return {
      api_url: raw.api_url || DEFAULT_API_URL,
      token: raw.token || "",
    };
  } catch {
    return emptyConfig();
  }
}

/** Persist the config to disk (creates ~/.cbpm/). */
export function writeConfig(cfg: CbpmConfig): void {
  const path = configPath();
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(cfg, null, 2) + "\n", "utf-8");
  // Tighten permissions (token is sensitive).
  try {
    chmodSync(path, 0o600);
  } catch {
    // best-effort
  }
}

/** Effective config: env vars override the file. */
export function effectiveConfig(): CbpmConfig {
  const cfg = readConfig();
  return {
    api_url: process.env[ENV_API_URL] || cfg.api_url,
    token: process.env[ENV_API_TOKEN] || cfg.token,
  };
}

/** Set a single key in the persisted config. */
export function setConfigKey(key: "api_url" | "token", value: string): CbpmConfig {
  const cfg = readConfig();
  cfg[key] = value;
  writeConfig(cfg);
  return cfg;
}

/** Unset a single key (revert to default for api_url, empty for token). */
export function unsetConfigKey(key: "api_url" | "token"): CbpmConfig {
  const cfg = readConfig();
  if (key === "api_url") cfg.api_url = DEFAULT_API_URL;
  else cfg.token = "";
  writeConfig(cfg);
  return cfg;
}

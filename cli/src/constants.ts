/** Static constants and semantic exit codes for the cbpm CLI. */

export const CLI_NAME = "cbpm";
export const CLI_DESCRIPTION =
  "CloakBrowser Profile Manager — self-explaining CLI for profile creation and management.";
export const VERSION = "0.1.0";

/** Default API base URL (loopback CBM server). */
export const DEFAULT_API_URL = "http://127.0.0.1:8080";

/** Request timeout (ms) for the REST client. */
export const REQUEST_TIMEOUT_MS = 30_000;

/** Env-var overrides. */
export const ENV_API_URL = "CBPM_API_URL";
export const ENV_API_TOKEN = "CBPM_API_TOKEN";

/** Config file path: ~/.cbpm/config.json */
export function configPath(): string {
  const home = process.env.HOME || process.env.USERPROFILE || "";
  return `${home}/.cbpm/config.json`;
}

/**
 * Semantic exit codes (Square ranges), also emitted in `--help --json`.
 * 0         success
 * 1         generic/unhandled
 * 80-89     user input / validation (do not retry — fix input)
 * 90-99     resource / state (not found, conflict, rate-limited)
 * 100-109   external / integration (retry with backoff)
 * 110-119   internal software (report bug, do not retry)
 */
export const EXIT_CODES = {
  SUCCESS: 0,
  GENERIC: 1,
  INVALID_ARGS: 80,
  AUTH: 81,
  NOT_FOUND: 90,
  CONFLICT: 91,
  RATE_LIMIT: 92,
  EXTERNAL: 100,
  SOFTWARE: 110,
} as const;

export type ExitCode = (typeof EXIT_CODES)[keyof typeof EXIT_CODES];

export interface ExitCodeDoc {
  name: string;
  code: number;
  meaning: string;
  retry: boolean;
}

export const EXIT_CODE_DOCS: ExitCodeDoc[] = [
  { name: "SUCCESS", code: 0, meaning: "Operation completed successfully", retry: false },
  { name: "GENERIC", code: 1, meaning: "Unhandled / generic error", retry: false },
  { name: "INVALID_ARGS", code: 80, meaning: "Invalid arguments or validation error — fix the input", retry: false },
  { name: "AUTH", code: 81, meaning: "Authentication required or invalid token — run `cbpm auth login`", retry: false },
  { name: "NOT_FOUND", code: 90, meaning: "Requested resource was not found", retry: false },
  { name: "CONFLICT", code: 91, meaning: "State conflict (already running, in use, etc.)", retry: false },
  { name: "RATE_LIMIT", code: 92, meaning: "Resource limit reached (e.g. MAX_RUNNING_PROFILES)", retry: true },
  { name: "EXTERNAL", code: 100, meaning: "External/remote error (API 5xx, network) — retry with backoff", retry: true },
  { name: "SOFTWARE", code: 110, meaning: "Internal software error — report a bug", retry: false },
];

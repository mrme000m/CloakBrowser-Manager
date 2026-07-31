/** Structured command error carrying a suggestion + exit code (bdg-style). */

import { EXIT_CODES, type ExitCode } from "./constants.js";

export interface ErrorContext {
  suggestion?: string;
  detail?: string;
  [k: string]: unknown;
}

export class CommandError extends Error {
  readonly exitCode: ExitCode;
  readonly context: ErrorContext;

  constructor(message: string, context: ErrorContext = {}, exitCode: ExitCode = EXIT_CODES.GENERIC) {
    super(message);
    this.name = "CommandError";
    this.exitCode = context.suggestion ? exitCode : exitCode;
    this.context = context;
  }
}

/** Map an HTTP status code to a semantic exit code. */
export function exitCodeForStatus(status: number): ExitCode {
  if (status === 401 || status === 403) return EXIT_CODES.AUTH;
  if (status === 404) return EXIT_CODES.NOT_FOUND;
  if (status === 409) return EXIT_CODES.CONFLICT;
  if (status === 429) return EXIT_CODES.RATE_LIMIT;
  if (status >= 500) return EXIT_CODES.EXTERNAL;
  if (status >= 400) return EXIT_CODES.INVALID_ARGS;
  return EXIT_CODES.EXTERNAL;
}

/** Human-readable hint for an HTTP status. */
export function hintForStatus(status: number, detail?: string): string {
  switch (status) {
    case 401:
      return "Auth required — run `cbpm auth login <token>` (or set CBPM_API_TOKEN).";
    case 403:
      return "Forbidden — the configured token lacks access.";
    case 404:
      return "Not found — check the id, or run `cbpm profiles list`.";
    case 409:
      return detail ? `Conflict — ${detail}` : "Conflict — the resource is in an incompatible state.";
    case 429:
      return "Rate/resource limit reached — stop a profile or raise MAX_RUNNING_PROFILES.";
    default:
      return status >= 500
        ? "Server error — retry shortly. Run `cbpm status` to check the manager."
        : "Request rejected by the server — check the input.";
  }
}

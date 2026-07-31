/** Central command runner: try/catch + output + exit (bdg-style). */

import { EXIT_CODES, type ExitCode } from "./constants.js";
import { CommandError } from "./errors.js";
import { buildJsonError, buildSuccessResponse } from "./output.js";

export interface CommandResult<T> {
  success: boolean;
  data?: T;
  error?: string;
  exitCode?: ExitCode;
  suggestion?: string;
  detail?: string;
  hint?: string; // informational, printed to stderr (not an error)
}

export interface BaseOptions {
  json?: boolean;
}

type Formatter<T> = (data: T) => string;

/** Run a handler, render output (JSON envelope or human formatter), and exit. */
export async function runCommand<T>(
  handler: () => Promise<CommandResult<T>> | CommandResult<T>,
  options: BaseOptions,
  formatter?: Formatter<T>,
): Promise<void> {
  let result: CommandResult<T>;
  try {
    result = await handler();
  } catch (err) {
    if (err instanceof CommandError) {
      result = {
        success: false,
        error: err.message,
        exitCode: err.exitCode,
        suggestion: err.context.suggestion,
        detail: err.context.detail,
      };
    } else {
      result = {
        success: false,
        error: err instanceof Error ? err.message : String(err),
        exitCode: EXIT_CODES.SOFTWARE,
      };
    }
  }

  if (!result.success) {
    if (options.json) {
      console.log(
        JSON.stringify(
          buildJsonError(result.error || "Unknown error", {
            exitCode: result.exitCode,
            suggestion: result.suggestion,
            detail: result.detail,
          }),
          null,
          2,
        ),
      );
    } else {
      process.stderr.write(`Error: ${result.error}\n`);
      if (result.suggestion) process.stderr.write(`Suggestion: ${result.suggestion}\n`);
      if (result.detail) process.stderr.write(`Detail: ${result.detail}\n`);
    }
    process.exit(result.exitCode ?? EXIT_CODES.GENERIC);
  }

  // Success path
  const data = result.data as T;
  if (result.hint) process.stderr.write(`${result.hint}\n`);
  if (options.json) {
    console.log(JSON.stringify(buildSuccessResponse(data), null, 2));
  } else if (formatter) {
    console.log(formatter(data));
  } else {
    // No formatter: fall back to JSON on stdout.
    console.log(JSON.stringify(data, null, 2));
  }
  process.exit(EXIT_CODES.SUCCESS);
}

/** Parse a comma-separated --ids value into a string[] (no empty entries). */
export function parseIds(raw: string): string[] {
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

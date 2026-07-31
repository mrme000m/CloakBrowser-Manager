/** Versioned output envelope: {version, success, data|error...} (bdg-style). */

import { VERSION } from "./constants.js";

export interface SuccessEnvelope<T> {
  version: string;
  success: true;
  data: T;
}

export interface ErrorEnvelope {
  version: string;
  success: false;
  error: string;
  exitCode: number;
  suggestion?: string;
  detail?: string;
}

export function buildSuccessResponse<T>(data: T): SuccessEnvelope<T> {
  return { version: VERSION, success: true, data };
}

export function buildJsonError(
  error: string,
  opts: { exitCode?: number; suggestion?: string; detail?: string } = {},
): ErrorEnvelope {
  const env: ErrorEnvelope = {
    version: VERSION,
    success: false,
    error,
    exitCode: opts.exitCode ?? 1,
  };
  if (opts.suggestion) env.suggestion = opts.suggestion;
  if (opts.detail) env.detail = opts.detail;
  return env;
}

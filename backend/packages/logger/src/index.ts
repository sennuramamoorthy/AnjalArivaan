import { JsonLogger } from './logger.js';
import type { ILogger, LogLevel } from './types.js';

export { JsonLogger } from './logger.js';
export type { ILogger, LogEntry, LogLevel } from './types.js';

/**
 * Factory function to create a new structured JSON logger.
 *
 * @param service   Service name included on every log entry.
 * @param traceId   Distributed trace ID. Auto-generated UUID when omitted.
 * @param minLevel  Minimum level to emit. Defaults to 'debug'.
 */
export function createLogger(
  service: string,
  traceId?: string,
  minLevel: LogLevel = 'debug',
): ILogger {
  return new JsonLogger(service, traceId, minLevel);
}

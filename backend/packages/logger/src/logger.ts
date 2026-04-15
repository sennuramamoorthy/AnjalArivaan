import { randomUUID } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import type { ILogger, LogEntry, LogLevel } from './types.js';

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

/**
 * Production-grade structured JSON logger.
 *
 * - Each log call writes one JSON line to process.stdout.
 * - In test environments (NODE_ENV === 'test'), output is suppressed unless
 *   LOG_IN_TESTS=true is set.
 * - child() returns a new JsonLogger with merged base context.
 * - timed() times an async operation and logs duration_ms on completion.
 */
export class JsonLogger implements ILogger {
  private readonly service: string;
  private readonly traceId: string;
  private readonly minLevel: LogLevel;
  private readonly baseContext: Record<string, unknown>;

  constructor(
    service: string,
    traceId?: string,
    minLevel: LogLevel = 'debug',
    baseContext: Record<string, unknown> = {},
  ) {
    this.service = service;
    this.traceId = traceId ?? randomUUID();
    this.minLevel = minLevel;
    this.baseContext = baseContext;
  }

  private shouldSuppress(): boolean {
    return (
      process.env['NODE_ENV'] === 'test' && process.env['LOG_IN_TESTS'] !== 'true'
    );
  }

  private write(entry: LogEntry): void {
    if (this.shouldSuppress()) return;
    process.stdout.write(JSON.stringify(entry) + '\n');
  }

  private buildEntry(
    level: LogLevel,
    message: string,
    context: Record<string, unknown> = {},
  ): LogEntry | null {
    if (LEVEL_ORDER[level] < LEVEL_ORDER[this.minLevel]) return null;

    // Extract and serialize error if present
    let errorFields: Partial<LogEntry> = {};
    if (context['error'] instanceof Error) {
      const err = context['error'] as Error;
      errorFields = {
        error_name: err.name,
        error_message: err.message,
        ...(err.stack !== undefined ? { error_stack: err.stack } : {}),
      };
      // Remove the raw Error object from context before spreading
      const { error: _removed, ...rest } = context;
      context = rest;
    }

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      service: this.service,
      trace_id: this.traceId,
      message,
      ...this.baseContext,
      ...context,
      ...errorFields,
    };

    return entry;
  }

  debug(message: string, context?: Record<string, unknown>): void {
    const entry = this.buildEntry('debug', message, context);
    if (entry) this.write(entry);
  }

  info(message: string, context?: Record<string, unknown>): void {
    const entry = this.buildEntry('info', message, context);
    if (entry) this.write(entry);
  }

  warn(message: string, context?: Record<string, unknown>): void {
    const entry = this.buildEntry('warn', message, context);
    if (entry) this.write(entry);
  }

  error(message: string, context?: Record<string, unknown> & { error?: Error }): void {
    const entry = this.buildEntry('error', message, context);
    if (entry) this.write(entry);
  }

  child(context: Record<string, unknown>): ILogger {
    return new JsonLogger(this.service, this.traceId, this.minLevel, {
      ...this.baseContext,
      ...context,
    });
  }

  async timed<T>(
    operationName: string,
    fn: () => Promise<T>,
    meta?: Record<string, unknown>,
  ): Promise<T> {
    const start = performance.now();
    try {
      const result = await fn();
      const duration_ms = Math.round((performance.now() - start) * 100) / 100;
      this.info(`${operationName} completed`, {
        duration_ms,
        operation: operationName,
        ...meta,
      });
      return result;
    } catch (err: unknown) {
      const duration_ms = Math.round((performance.now() - start) * 100) / 100;
      this.error(`${operationName} failed`, {
        duration_ms,
        operation: operationName,
        error: err instanceof Error ? err : new Error(String(err)),
        ...meta,
      });
      throw err;
    }
  }
}

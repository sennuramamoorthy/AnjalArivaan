/**
 * Minimal JSON structured logger that mirrors the @anjal/logger ILogger interface.
 * This local implementation lets the service run without the workspace dep installed.
 * Wire up the workspace dep in Phase 2.
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEntry {
  timestamp: string; // ISO 8601
  level: LogLevel;
  service: string;
  trace_id: string;
  message: string;
  duration_ms?: number;
  model_id?: string;
  prompt_template_id?: string;
  retrieved_chunk_count?: number;
  user_feedback?: string;
  error_name?: string;
  error_message?: string;
  error_stack?: string;
  [key: string]: unknown;
}

export interface ILogger {
  debug(message: string, context?: Record<string, unknown>): void;
  info(message: string, context?: Record<string, unknown>): void;
  warn(message: string, context?: Record<string, unknown>): void;
  error(message: string, context?: Record<string, unknown> & { error?: Error }): void;
  child(context: Record<string, unknown>): ILogger;
  timed<T>(
    operationName: string,
    fn: () => Promise<T>,
    meta?: Record<string, unknown>,
  ): Promise<T>;
}

export function createLogger(service: string, baseContext: Record<string, unknown> = {}): ILogger {
  const write = (level: LogLevel, message: string, context: Record<string, unknown> = {}): void => {
    const { error, ...rest } = context as Record<string, unknown> & { error?: Error };
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      service,
      trace_id: (baseContext['trace_id'] as string | undefined) ?? 'unknown',
      message,
      ...baseContext,
      ...rest,
    };

    if (error instanceof Error) {
      entry['error_name'] = error.name;
      entry['error_message'] = error.message;
      if (error.stack !== undefined) {
        entry['error_stack'] = error.stack;
      }
    }

    process.stdout.write(JSON.stringify(entry) + '\n');
  };

  const logger: ILogger = {
    debug: (message, context) => write('debug', message, context),
    info: (message, context) => write('info', message, context),
    warn: (message, context) => write('warn', message, context),
    error: (message, context) => write('error', message, context),

    child: (context) => createLogger(service, { ...baseContext, ...context }),

    timed: async <T>(
      operationName: string,
      fn: () => Promise<T>,
      meta: Record<string, unknown> = {},
    ): Promise<T> => {
      const start = Date.now();
      try {
        const result = await fn();
        write('info', operationName, { ...meta, duration_ms: Date.now() - start });
        return result;
      } catch (err) {
        write('error', operationName, {
          ...meta,
          duration_ms: Date.now() - start,
          error: err instanceof Error ? err : new Error(String(err)),
        });
        throw err;
      }
    },
  };

  return logger;
}

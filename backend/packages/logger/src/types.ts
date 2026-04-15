export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEntry {
  timestamp: string; // ISO 8601
  level: LogLevel;
  service: string;
  trace_id: string;
  message: string;
  duration_ms?: number; // REQUIRED when closing any outbound API call
  // AI-specific fields (optional)
  model_id?: string;
  prompt_template_id?: string;
  retrieved_chunk_count?: number;
  user_feedback?: string;
  // Error fields
  error_name?: string;
  error_message?: string;
  error_stack?: string;
  // Arbitrary extra context
  [key: string]: unknown;
}

export interface ILogger {
  debug(message: string, context?: Record<string, unknown>): void;
  info(message: string, context?: Record<string, unknown>): void;
  warn(message: string, context?: Record<string, unknown>): void;
  error(message: string, context?: Record<string, unknown> & { error?: Error }): void;
  /** Create a child logger that inherits context and merges new context into every entry */
  child(context: Record<string, unknown>): ILogger;
  /**
   * Wraps an async operation:
   * - starts a timer
   * - on success: logs at INFO with duration_ms
   * - on error: logs at ERROR with duration_ms + error details, then re-throws
   */
  timed<T>(
    operationName: string,
    fn: () => Promise<T>,
    meta?: Record<string, unknown>,
  ): Promise<T>;
}

/**
 * Logger unit tests — written FIRST per TDD.
 *
 * Captures process.stdout writes, parses as JSON, and asserts structure/values.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createLogger } from '../../../../backend/packages/logger/src/index.js';
import type { ILogger, LogEntry } from '../../../../backend/packages/logger/src/types.js';

// ── stdout capture helper ────────────────────────────────────────────────────

function captureStdout(): { lines: () => string[]; restore: () => void } {
  const captured: string[] = [];
  const originalWrite = process.stdout.write.bind(process.stdout);

  const spy = vi
    .spyOn(process.stdout, 'write')
    .mockImplementation((chunk: unknown): boolean => {
      if (typeof chunk === 'string') {
        captured.push(chunk);
      }
      return true;
    });

  return {
    lines: () =>
      captured
        .join('')
        .split('\n')
        .filter((l) => l.trim() !== ''),
    restore: () => {
      spy.mockRestore();
      void originalWrite; // keep reference
    },
  };
}

function parseLastEntry(lines: string[]): LogEntry {
  const last = lines[lines.length - 1];
  if (!last) throw new Error('No log output captured');
  return JSON.parse(last) as LogEntry;
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('JsonLogger', () => {
  let capture: ReturnType<typeof captureStdout>;

  beforeEach(() => {
    // Enable output during tests by setting LOG_IN_TESTS
    process.env['LOG_IN_TESTS'] = 'true';
    capture = captureStdout();
  });

  afterEach(() => {
    capture.restore();
    delete process.env['LOG_IN_TESTS'];
  });

  // 1
  it('should output valid JSON on each log call', () => {
    const logger = createLogger('test-service');
    logger.info('hello');

    const lines = capture.lines();
    expect(lines.length).toBeGreaterThanOrEqual(1);
    expect(() => JSON.parse(lines[lines.length - 1]!)).not.toThrow();
  });

  // 2
  it('should include timestamp in ISO 8601 format', () => {
    const logger = createLogger('test-service');
    logger.info('ts test');

    const entry = parseLastEntry(capture.lines());
    expect(entry.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$/);
  });

  // 3
  it('should include the service name', () => {
    const logger = createLogger('mail-sync');
    logger.info('service test');

    const entry = parseLastEntry(capture.lines());
    expect(entry.service).toBe('mail-sync');
  });

  // 4
  it('should include trace_id', () => {
    const logger = createLogger('test-service', 'trace-abc-123');
    logger.info('trace test');

    const entry = parseLastEntry(capture.lines());
    expect(entry.trace_id).toBe('trace-abc-123');
  });

  // 4b — auto-generates trace_id when not provided
  it('should auto-generate a trace_id when not provided', () => {
    const logger = createLogger('test-service');
    logger.info('auto trace');

    const entry = parseLastEntry(capture.lines());
    expect(typeof entry.trace_id).toBe('string');
    expect(entry.trace_id.length).toBeGreaterThan(0);
  });

  // 5
  it('should include the message', () => {
    const logger = createLogger('test-service');
    logger.warn('important warning');

    const entry = parseLastEntry(capture.lines());
    expect(entry.message).toBe('important warning');
  });

  // 6
  it('should log at correct level', () => {
    const logger = createLogger('test-service');

    logger.debug('d');
    const debug = parseLastEntry(capture.lines());
    expect(debug.level).toBe('debug');

    logger.info('i');
    const info = parseLastEntry(capture.lines());
    expect(info.level).toBe('info');

    logger.warn('w');
    const warn = parseLastEntry(capture.lines());
    expect(warn.level).toBe('warn');

    logger.error('e');
    const error = parseLastEntry(capture.lines());
    expect(error.level).toBe('error');
  });

  // 7
  it('should not log below minLevel', () => {
    const logger = createLogger('test-service', undefined, 'warn');
    logger.debug('silent debug');
    logger.info('silent info');

    const lines = capture.lines();
    // nothing should have been written for debug/info
    expect(lines.length).toBe(0);

    logger.warn('audible warn');
    const entry = parseLastEntry(capture.lines());
    expect(entry.level).toBe('warn');
  });

  // 8
  it('should include extra context fields', () => {
    const logger = createLogger('test-service');
    logger.info('with context', { requestId: 'req-999', userId: 'u-1' });

    const entry = parseLastEntry(capture.lines());
    expect(entry['requestId']).toBe('req-999');
    expect(entry['userId']).toBe('u-1');
  });

  // 9
  it('should serialize Error fields on error log', () => {
    const logger = createLogger('test-service');
    const err = new TypeError('something broke');
    logger.error('failure', { error: err });

    const entry = parseLastEntry(capture.lines());
    expect(entry.error_name).toBe('TypeError');
    expect(entry.error_message).toBe('something broke');
    expect(typeof entry.error_stack).toBe('string');
    expect(entry.error_stack).toContain('TypeError');
  });

  // 10
  it('child() should merge parent context into every entry', () => {
    const parent = createLogger('test-service', 'parent-trace');
    const child = parent.child({ component: 'mail-indexer', accountId: 'acct-42' });

    child.info('child message');
    const entry = parseLastEntry(capture.lines());

    expect(entry.service).toBe('test-service');
    expect(entry.trace_id).toBe('parent-trace');
    expect(entry['component']).toBe('mail-indexer');
    expect(entry['accountId']).toBe('acct-42');
    expect(entry.message).toBe('child message');
  });

  // 11
  it('timed() should log duration_ms on success', async () => {
    const logger = createLogger('test-service');
    const result = await logger.timed('gmail.fetch', async () => {
      return 'ok';
    });

    expect(result).toBe('ok');
    const entry = parseLastEntry(capture.lines());
    expect(entry.level).toBe('info');
    expect(typeof entry.duration_ms).toBe('number');
    expect(entry.duration_ms).toBeGreaterThanOrEqual(0);
  });

  // 12
  it('timed() should log duration_ms on error and re-throw', async () => {
    const logger = createLogger('test-service');
    const boom = new Error('network timeout');

    await expect(
      logger.timed('qdrant.search', async () => {
        throw boom;
      }),
    ).rejects.toThrow('network timeout');

    const entry = parseLastEntry(capture.lines());
    expect(entry.level).toBe('error');
    expect(typeof entry.duration_ms).toBe('number');
    expect(entry.duration_ms).toBeGreaterThanOrEqual(0);
  });

  // 13
  it('timed() should log at info level on success, error level on failure', async () => {
    const logger = createLogger('test-service');

    await logger.timed('success-op', async () => 'done');
    const successEntry = parseLastEntry(capture.lines());
    expect(successEntry.level).toBe('info');

    await expect(
      logger.timed('fail-op', async () => {
        throw new Error('fail');
      }),
    ).rejects.toThrow();

    const failEntry = parseLastEntry(capture.lines());
    expect(failEntry.level).toBe('error');
  });
});

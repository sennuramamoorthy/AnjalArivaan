import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import type { AuthService } from '../services/AuthService.js';
import type { RbacService } from '../services/RbacService.js';
import type { ILogger } from '../logger.js';
import { createAuthenticateHook } from '../middleware/authenticate.js';
import { authorize } from '../middleware/authorize.js';
import {
  UserAlreadyExistsError,
  InvalidCredentialsError,
  MfaRequiredError,
  InvalidMfaCodeError,
  MfaDisabledError,
  TokenInvalidError,
  ValidationError,
} from '../domain/errors.js';

const RegisterBodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(1),
  role: z
    .enum(['SUPER_ADMIN', 'DEPT_ADMIN', 'VC', 'REGISTRAR', 'DEAN', 'HOD', 'STAFF'])
    .optional(),
});

const LoginBodySchema = z.object({
  email: z.string().email(),
  password: z.string(),
  mfaCode: z.string().optional(),
});

const RefreshBodySchema = z.object({
  refreshToken: z.string().uuid(),
});

const LogoutBodySchema = z.object({
  refreshToken: z.string().uuid(),
});

const MfaVerifySetupBodySchema = z.object({
  token: z.string().length(6),
});

function errorResponse(code: string, message: string, traceId: string) {
  return { success: false, error: { code, message }, meta: { traceId } };
}

export function registerAuthRoutes(
  app: FastifyInstance,
  authService: AuthService,
  rbacService: RbacService,
  logger: ILogger,
): void {
  const authenticate = createAuthenticateHook(authService, logger);

  app.post('/auth/register', async (request, reply) => {
    const traceId = (request.headers['x-trace-id'] as string | undefined) ?? 'unknown';
    const childLogger = logger.child({ trace_id: traceId });
    const start = Date.now();

    childLogger.debug('POST /auth/register', { method: 'POST', url: '/auth/register' });

    const parsed = RegisterBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const message = parsed.error.errors.map((e) => e.message).join(', ');
      childLogger.warn('Validation failed', { duration_ms: Date.now() - start });
      return reply.status(400).send(errorResponse('VALIDATION_ERROR', message, traceId));
    }

    try {
      const { email, password, name, role } = parsed.data;
      const registerInput = role !== undefined
        ? { email, password, name, role }
        : { email, password, name };
      const user = await authService.register(registerInput);
      childLogger.info('User registered', { userId: user.id, duration_ms: Date.now() - start });
      return reply.status(201).send({ success: true, data: user, meta: { traceId } });
    } catch (err) {
      const duration_ms = Date.now() - start;
      if (err instanceof UserAlreadyExistsError) {
        childLogger.warn('Registration conflict', { duration_ms });
        return reply.status(409).send(errorResponse(err.code, err.message, traceId));
      }
      if (err instanceof ValidationError) {
        childLogger.warn('Validation error', { duration_ms });
        return reply.status(400).send(errorResponse(err.code, err.message, traceId));
      }
      childLogger.error('Registration failed', { duration_ms, error: err as Error });
      return reply.status(500).send(errorResponse('INTERNAL_ERROR', 'Internal server error', traceId));
    }
  });

  app.post('/auth/login', async (request, reply) => {
    const traceId = (request.headers['x-trace-id'] as string | undefined) ?? 'unknown';
    const childLogger = logger.child({ trace_id: traceId });
    const start = Date.now();

    childLogger.debug('POST /auth/login', { method: 'POST', url: '/auth/login' });

    const parsed = LoginBodySchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.status(400).send(
        errorResponse('VALIDATION_ERROR', parsed.error.errors.map((e) => e.message).join(', '), traceId),
      );
    }

    try {
      const { email, password, mfaCode } = parsed.data;
      const loginInput = mfaCode !== undefined
        ? { email, password, mfaCode }
        : { email, password };
      const tokens = await authService.login(loginInput);
      childLogger.info('User logged in', { duration_ms: Date.now() - start });
      return reply.status(200).send({ success: true, data: tokens, meta: { traceId } });
    } catch (err) {
      const duration_ms = Date.now() - start;
      if (err instanceof MfaRequiredError) {
        return reply.status(200).send({
          success: false,
          error: { code: err.code, message: err.message },
          meta: { traceId },
        });
      }
      if (err instanceof InvalidCredentialsError || err instanceof InvalidMfaCodeError) {
        childLogger.warn('Login failed', { duration_ms });
        return reply.status(401).send(errorResponse(err.code, err.message, traceId));
      }
      childLogger.error('Login error', { duration_ms, error: err as Error });
      return reply.status(500).send(errorResponse('INTERNAL_ERROR', 'Internal server error', traceId));
    }
  });

  app.post('/auth/refresh', async (request, reply) => {
    const traceId = (request.headers['x-trace-id'] as string | undefined) ?? 'unknown';
    const start = Date.now();
    const childLogger = logger.child({ trace_id: traceId });

    const parsed = RefreshBodySchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.status(400).send(
        errorResponse('VALIDATION_ERROR', parsed.error.errors.map((e) => e.message).join(', '), traceId),
      );
    }

    try {
      const tokens = await authService.refreshToken(parsed.data.refreshToken);
      childLogger.info('Token refreshed', { duration_ms: Date.now() - start });
      return reply.status(200).send({ success: true, data: tokens, meta: { traceId } });
    } catch (err) {
      const duration_ms = Date.now() - start;
      if (err instanceof TokenInvalidError) {
        childLogger.warn('Invalid refresh token', { duration_ms });
        return reply.status(401).send(errorResponse(err.code, err.message, traceId));
      }
      childLogger.error('Refresh error', { duration_ms, error: err as Error });
      return reply.status(500).send(errorResponse('INTERNAL_ERROR', 'Internal server error', traceId));
    }
  });

  app.post(
    '/auth/logout',
    { preHandler: [authenticate] },
    async (request, reply) => {
      const traceId = (request.headers['x-trace-id'] as string | undefined) ?? 'unknown';
      const start = Date.now();
      const childLogger = logger.child({ trace_id: traceId });

      const parsed = LogoutBodySchema.safeParse(request.body);
      if (!parsed.success) {
        return reply.status(400).send(
          errorResponse('VALIDATION_ERROR', parsed.error.errors.map((e) => e.message).join(', '), traceId),
        );
      }

      await authService.logout(parsed.data.refreshToken);
      childLogger.info('User logged out', { duration_ms: Date.now() - start });
      return reply.status(200).send({ success: true, data: null, meta: { traceId } });
    },
  );

  app.post(
    '/auth/mfa/setup',
    { preHandler: [authenticate] },
    async (request, reply) => {
      const traceId = (request.headers['x-trace-id'] as string | undefined) ?? 'unknown';
      const start = Date.now();
      const childLogger = logger.child({ trace_id: traceId });

      try {
        const result = await authService.setupMfa(request.user!.id);
        childLogger.info('MFA setup', { duration_ms: Date.now() - start });
        return reply.status(200).send({ success: true, data: result, meta: { traceId } });
      } catch (err) {
        const duration_ms = Date.now() - start;
        if (err instanceof MfaDisabledError) {
          childLogger.warn('MFA setup rejected — MFA globally disabled', { duration_ms });
          return reply.status(403).send(errorResponse(err.code, err.message, traceId));
        }
        childLogger.error('MFA setup error', { duration_ms, error: err as Error });
        return reply.status(500).send(errorResponse('INTERNAL_ERROR', 'Internal server error', traceId));
      }
    },
  );

  app.post(
    '/auth/mfa/verify-setup',
    { preHandler: [authenticate] },
    async (request, reply) => {
      const traceId = (request.headers['x-trace-id'] as string | undefined) ?? 'unknown';
      const start = Date.now();
      const childLogger = logger.child({ trace_id: traceId });

      const parsed = MfaVerifySetupBodySchema.safeParse(request.body);
      if (!parsed.success) {
        return reply.status(400).send(
          errorResponse('VALIDATION_ERROR', parsed.error.errors.map((e) => e.message).join(', '), traceId),
        );
      }

      try {
        const result = await authService.verifyMfaSetup(request.user!.id, parsed.data.token);
        childLogger.info('MFA verified and enabled', { duration_ms: Date.now() - start });
        return reply.status(200).send({ success: true, data: result, meta: { traceId } });
      } catch (err) {
        const duration_ms = Date.now() - start;
        if (err instanceof MfaDisabledError) {
          childLogger.warn('MFA verify rejected — MFA globally disabled', { duration_ms });
          return reply.status(403).send(errorResponse(err.code, err.message, traceId));
        }
        if (err instanceof InvalidMfaCodeError) {
          childLogger.warn('Invalid MFA setup code', { duration_ms });
          return reply.status(400).send(errorResponse(err.code, err.message, traceId));
        }
        childLogger.error('MFA verify setup error', { duration_ms, error: err as Error });
        return reply.status(500).send(errorResponse('INTERNAL_ERROR', 'Internal server error', traceId));
      }
    },
  );
}

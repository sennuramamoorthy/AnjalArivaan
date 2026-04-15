import type { FastifyRequest, FastifyReply } from 'fastify';
import type { AuthService } from '../services/AuthService.js';
import type { ILogger } from '../logger.js';
import {
  TokenExpiredError,
  TokenInvalidError,
  UnauthorizedError,
} from '../domain/errors.js';
import type { UserRole } from '../domain/User.js';

export interface AuthenticatedUser {
  id: string;
  email: string;
  role: UserRole;
}

// Augment Fastify's Request type
declare module 'fastify' {
  interface FastifyRequest {
    user?: AuthenticatedUser;
    traceId?: string;
  }
}

export function createAuthenticateHook(authService: AuthService, logger: ILogger) {
  return async function authenticate(
    request: FastifyRequest,
    reply: FastifyReply,
  ): Promise<void> {
    const start = Date.now();
    const traceId = (request.headers['x-trace-id'] as string | undefined) ?? request.traceId ?? 'unknown';
    const childLogger = logger.child({ trace_id: traceId });

    const authHeader = request.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      childLogger.warn('Missing or malformed Authorization header', {
        duration_ms: Date.now() - start,
      });
      await reply.status(401).send({
        success: false,
        error: { code: 'UNAUTHORIZED', message: 'Missing or malformed Authorization header' },
        meta: { traceId },
      });
      return;
    }

    const token = authHeader.slice(7);

    try {
      const payload = authService.verifyAccessToken(token);
      request.user = {
        id: payload.sub,
        email: payload.email,
        role: payload.role as UserRole,
      };

      childLogger.debug('JWT verified', {
        userId: payload.sub,
        duration_ms: Date.now() - start,
      });
    } catch (err) {
      const duration_ms = Date.now() - start;

      if (err instanceof TokenExpiredError) {
        childLogger.warn('JWT expired', { duration_ms });
        await reply.status(401).send({
          success: false,
          error: { code: 'TOKEN_EXPIRED', message: 'Token has expired' },
          meta: { traceId },
        });
        return;
      }

      if (err instanceof TokenInvalidError || err instanceof UnauthorizedError) {
        childLogger.warn('Invalid JWT', { duration_ms });
        await reply.status(401).send({
          success: false,
          error: { code: 'TOKEN_INVALID', message: 'Invalid token' },
          meta: { traceId },
        });
        return;
      }

      childLogger.error('Unexpected error during authentication', {
        duration_ms,
        error: err instanceof Error ? err : new Error(String(err)),
      });
      await reply.status(401).send({
        success: false,
        error: { code: 'UNAUTHORIZED', message: 'Authentication failed' },
        meta: { traceId },
      });
    }
  };
}

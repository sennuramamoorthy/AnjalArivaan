import Fastify, { type FastifyInstance } from 'fastify';
import helmet from '@fastify/helmet';
import cors from '@fastify/cors';
import { v4 as uuidv4 } from 'uuid';
import type { AuthService } from './services/AuthService.js';
import type { RbacService } from './services/RbacService.js';
import type { IUserRepository } from './repositories/IUserRepository.js';
import type { ILogger } from './logger.js';
import { registerAuthRoutes } from './routes/auth.routes.js';
import { registerUserRoutes } from './routes/user.routes.js';
import {
  UserAlreadyExistsError,
  InvalidCredentialsError,
  MfaRequiredError,
  InvalidMfaCodeError,
  MfaDisabledError,
  TokenExpiredError,
  TokenInvalidError,
  UnauthorizedError,
  ForbiddenError,
  ValidationError,
} from './domain/errors.js';

export interface AppDependencies {
  authService: AuthService;
  rbacService: RbacService;
  userRepo: IUserRepository;
  logger: ILogger;
}

const ERROR_STATUS_MAP: Array<[new (...args: never[]) => Error, number]> = [
  [UserAlreadyExistsError, 409],
  [InvalidCredentialsError, 401],
  [MfaRequiredError, 200],
  [InvalidMfaCodeError, 400],
  [MfaDisabledError, 403],
  [TokenExpiredError, 401],
  [TokenInvalidError, 401],
  [UnauthorizedError, 401],
  [ForbiddenError, 403],
  [ValidationError, 400],
];

export function buildApp(deps: AppDependencies): FastifyInstance {
  const { authService, rbacService, userRepo, logger } = deps;

  const app = Fastify({ logger: false });

  // X-Trace-ID middleware
  app.addHook('onRequest', async (request) => {
    const incoming = request.headers['x-trace-id'] as string | undefined;
    request.traceId = incoming ?? uuidv4();
    // Echo trace ID back in responses
    void request; // used below in onSend
  });

  app.addHook('onSend', async (request, reply) => {
    void reply.header('x-trace-id', request.traceId ?? 'unknown');
  });

  // Security headers
  void app.register(helmet);
  void app.register(cors, { origin: true });

  // Health check
  app.get('/health', async (_request, reply) => {
    return reply.status(200).send({ status: 'ok', service: 'identity' });
  });

  // Routes under /api/v1
  void app.register(
    async (v1) => {
      registerAuthRoutes(v1, authService, rbacService, logger);
      registerUserRoutes(v1, authService, userRepo, logger);
    },
    { prefix: '/api/v1' },
  );

  // Global error handler
  app.setErrorHandler(async (error, request, reply) => {
    const traceId = request.traceId ?? 'unknown';
    const duration_ms = 0;

    logger.child({ trace_id: traceId }).error('Unhandled error', {
      duration_ms,
      error,
    });

    for (const [ErrorClass, statusCode] of ERROR_STATUS_MAP) {
      if (error instanceof ErrorClass) {
        const domainErr = error as { code: string; message: string };
        return reply.status(statusCode).send({
          success: false,
          error: { code: domainErr.code, message: domainErr.message },
          meta: { traceId },
        });
      }
    }

    return reply.status(500).send({
      success: false,
      error: { code: 'INTERNAL_ERROR', message: 'Internal server error' },
      meta: { traceId },
    });
  });

  return app;
}

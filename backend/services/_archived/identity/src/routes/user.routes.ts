import type { FastifyInstance } from 'fastify';
import type { AuthService } from '../services/AuthService.js';
import type { ILogger } from '../logger.js';
import type { IUserRepository } from '../repositories/IUserRepository.js';
import { createAuthenticateHook } from '../middleware/authenticate.js';

export function registerUserRoutes(
  app: FastifyInstance,
  authService: AuthService,
  userRepo: IUserRepository,
  logger: ILogger,
): void {
  const authenticate = createAuthenticateHook(authService, logger);

  app.get(
    '/users/me',
    { preHandler: [authenticate] },
    async (request, reply) => {
      const traceId = (request.headers['x-trace-id'] as string | undefined) ?? 'unknown';
      const start = Date.now();
      const childLogger = logger.child({ trace_id: traceId });

      childLogger.debug('GET /users/me', { method: 'GET', url: '/users/me' });

      const user = await userRepo.findById(request.user!.id);
      if (!user) {
        childLogger.warn('User not found for /me', { duration_ms: Date.now() - start });
        return reply.status(404).send({
          success: false,
          error: { code: 'NOT_FOUND', message: 'User not found' },
          meta: { traceId },
        });
      }

      const { passwordHash: _ph, mfaSecret: _ms, backupCodes: _bc, ...publicUser } = user;

      childLogger.info('GET /users/me success', { userId: user.id, duration_ms: Date.now() - start });
      return reply.status(200).send({ success: true, data: publicUser, meta: { traceId } });
    },
  );
}

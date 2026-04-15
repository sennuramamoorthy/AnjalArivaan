import type { FastifyRequest, FastifyReply } from 'fastify';
import type { UserRole } from '../domain/User.js';
import type { RbacService } from '../services/RbacService.js';

export type AuthorizeHandler = (
  request: FastifyRequest,
  reply: FastifyReply,
  done: () => void,
) => Promise<void>;

export function authorize(rbacService: RbacService, ...roles: UserRole[]): AuthorizeHandler {
  return async function (request: FastifyRequest, reply: FastifyReply): Promise<void> {
    const traceId =
      (request.headers['x-trace-id'] as string | undefined) ?? request.traceId ?? 'unknown';

    if (!request.user) {
      await reply.status(401).send({
        success: false,
        error: { code: 'UNAUTHORIZED', message: 'Not authenticated' },
        meta: { traceId },
      });
      return;
    }

    const hasAccess = rbacService.canAccess(request.user.role, roles);
    if (!hasAccess) {
      await reply.status(403).send({
        success: false,
        error: {
          code: 'FORBIDDEN',
          message: `Role ${request.user.role} is not permitted to access this resource`,
        },
        meta: { traceId },
      });
      return;
    }
  };
}

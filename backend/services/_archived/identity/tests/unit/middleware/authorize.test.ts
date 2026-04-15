import { describe, it, expect, vi, beforeEach } from 'vitest';
import { authorize } from '../../../src/middleware/authorize.js';
import { RbacService } from '../../../src/services/RbacService.js';
import type { FastifyRequest, FastifyReply } from 'fastify';
import type { UserRole } from '../../../src/domain/User.js';

function makeMockReply(): FastifyReply {
  const reply = {
    status: vi.fn().mockReturnThis(),
    send: vi.fn().mockReturnThis(),
  } as unknown as FastifyReply;
  return reply;
}

function makeMockRequest(role?: UserRole): FastifyRequest {
  return {
    headers: {},
    traceId: 'test-trace-id',
    user: role ? { id: 'user-1', email: 'test@example.com', role } : undefined,
  } as unknown as FastifyRequest;
}

describe('authorize middleware', () => {
  let rbacService: RbacService;

  beforeEach(() => {
    rbacService = new RbacService();
  });

  it('should pass through when user has required role', async () => {
    const handler = authorize(rbacService, 'STAFF');
    const request = makeMockRequest('STAFF');
    const reply = makeMockReply();

    await handler(request, reply, () => {});

    expect(reply.status).not.toHaveBeenCalled();
    expect(reply.send).not.toHaveBeenCalled();
  });

  it('should return 403 when user lacks required role', async () => {
    const handler = authorize(rbacService, 'SUPER_ADMIN');
    const request = makeMockRequest('STAFF');
    const reply = makeMockReply();

    await handler(request, reply, () => {});

    expect(reply.status).toHaveBeenCalledWith(403);
    expect(reply.send).toHaveBeenCalledWith(
      expect.objectContaining({ success: false }),
    );
  });

  it('should support multiple allowed roles', async () => {
    const handler = authorize(rbacService, 'DEAN', 'VC', 'REGISTRAR');

    // VC should pass (exact match)
    const vcRequest = makeMockRequest('VC');
    const vcReply = makeMockReply();
    await handler(vcRequest, vcReply, () => {});
    expect(vcReply.status).not.toHaveBeenCalled();

    // REGISTRAR should pass (exact match)
    const registrarRequest = makeMockRequest('REGISTRAR');
    const registrarReply = makeMockReply();
    await handler(registrarRequest, registrarReply, () => {});
    expect(registrarReply.status).not.toHaveBeenCalled();

    // HOD (50) cannot access VC (70) / REGISTRAR (70) — insufficient level
    const hodRequest = makeMockRequest('HOD');
    const hodReply = makeMockReply();
    await handler(hodRequest, hodReply, () => {});
    expect(hodReply.status).toHaveBeenCalledWith(403);
  });

  it('should return 401 when user is not authenticated', async () => {
    const handler = authorize(rbacService, 'STAFF');
    const request = makeMockRequest(); // no user
    const reply = makeMockReply();

    await handler(request, reply, () => {});

    expect(reply.status).toHaveBeenCalledWith(401);
  });
});

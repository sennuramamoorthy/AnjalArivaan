import { describe, it, expect, vi, beforeEach } from 'vitest';
import { generateKeyPairSync } from 'crypto';
import jwt from 'jsonwebtoken';
import { createAuthenticateHook } from '../../../src/middleware/authenticate.js';
import { AuthService } from '../../../src/services/AuthService.js';
import { InMemoryUserRepository } from '../../../src/repositories/InMemoryUserRepository.js';
import { MockPasswordHasher } from '../../../src/adapters/MockPasswordHasher.js';
import { MockTokenStore } from '../../../src/adapters/MockTokenStore.js';
import { MockTotpService } from '../../../src/adapters/MockTotpService.js';
import { createLogger } from '../../../src/logger.js';
import type { FastifyRequest, FastifyReply } from 'fastify';

const { privateKey, publicKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

const { privateKey: wrongPrivateKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

const FIELD_ENC_KEY = 'b'.repeat(64);

function makeAuthService(): AuthService {
  return new AuthService(
    new InMemoryUserRepository(),
    new MockPasswordHasher(),
    new MockTokenStore(),
    new MockTotpService(),
    createLogger('identity-test'),
    privateKey,
    publicKey,
    FIELD_ENC_KEY,
  );
}

function makeValidToken(overrides: Partial<{ key: string }> = {}): string {
  return jwt.sign(
    { sub: 'user-1', role: 'STAFF', email: 'test@example.com', jti: 'jti-1' },
    overrides.key ?? privateKey,
    { algorithm: 'RS256', expiresIn: '15m' },
  );
}

function makeMockReply(): FastifyReply {
  const sent: unknown[] = [];
  const reply = {
    status: vi.fn().mockReturnThis(),
    send: vi.fn().mockImplementation((body) => {
      sent.push(body);
      return reply;
    }),
    _sent: sent,
  } as unknown as FastifyReply;
  return reply;
}

function makeMockRequest(authHeader?: string): FastifyRequest {
  return {
    headers: authHeader ? { authorization: authHeader } : {},
    traceId: 'test-trace-id',
    user: undefined,
  } as unknown as FastifyRequest;
}

describe('authenticate middleware', () => {
  let authService: AuthService;
  let authenticate: ReturnType<typeof createAuthenticateHook>;

  beforeEach(() => {
    authService = makeAuthService();
    authenticate = createAuthenticateHook(authService, createLogger('test'));
  });

  it('should attach decoded user to request on valid JWT', async () => {
    const token = makeValidToken();
    const request = makeMockRequest(`Bearer ${token}`);
    const reply = makeMockReply();

    await authenticate(request, reply);

    expect(reply.status).not.toHaveBeenCalled();
    expect(request.user).toBeDefined();
    expect(request.user!.id).toBe('user-1');
    expect(request.user!.role).toBe('STAFF');
    expect(request.user!.email).toBe('test@example.com');
  });

  it('should return 401 for missing Authorization header', async () => {
    const request = makeMockRequest(); // no auth header
    const reply = makeMockReply();

    await authenticate(request, reply);

    expect(reply.status).toHaveBeenCalledWith(401);
    expect(reply.send).toHaveBeenCalledWith(
      expect.objectContaining({ success: false }),
    );
  });

  it('should return 401 for malformed token', async () => {
    const request = makeMockRequest('Bearer not.a.valid.jwt');
    const reply = makeMockReply();

    await authenticate(request, reply);

    expect(reply.status).toHaveBeenCalledWith(401);
    expect(reply.send).toHaveBeenCalledWith(
      expect.objectContaining({ success: false }),
    );
  });

  it('should return 401 for expired token', async () => {
    // Create token that expired 1 second ago using past nbf/exp
    const now = Math.floor(Date.now() / 1000);
    const token = jwt.sign(
      { sub: 'user-1', role: 'STAFF', email: 'test@example.com', jti: 'jti-2', iat: now - 120, exp: now - 60 },
      privateKey,
      { algorithm: 'RS256' },
    );

    const request = makeMockRequest(`Bearer ${token}`);
    const reply = makeMockReply();

    await authenticate(request, reply);

    expect(reply.status).toHaveBeenCalledWith(401);
    const body = (reply.send as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as { error?: { code: string } };
    expect(body?.error?.code).toBe('TOKEN_EXPIRED');
  });

  it('should return 401 for wrong signing key', async () => {
    const token = makeValidToken({ key: wrongPrivateKey });
    const request = makeMockRequest(`Bearer ${token}`);
    const reply = makeMockReply();

    await authenticate(request, reply);

    expect(reply.status).toHaveBeenCalledWith(401);
    expect(reply.send).toHaveBeenCalledWith(
      expect.objectContaining({ success: false }),
    );
  });
});

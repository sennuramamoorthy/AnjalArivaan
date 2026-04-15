import { describe, it, expect, beforeEach } from 'vitest';
import { AuthService } from '../../../src/services/AuthService.js';
import { InMemoryUserRepository } from '../../../src/repositories/InMemoryUserRepository.js';
import { MockPasswordHasher } from '../../../src/adapters/MockPasswordHasher.js';
import { MockTokenStore } from '../../../src/adapters/MockTokenStore.js';
import { MockTotpService } from '../../../src/adapters/MockTotpService.js';
import { createLogger } from '../../../src/logger.js';
import {
  UserAlreadyExistsError,
  InvalidCredentialsError,
  MfaRequiredError,
  InvalidMfaCodeError,
  TokenInvalidError,
  ValidationError,
} from '../../../src/domain/errors.js';
import { generateKeyPairSync } from 'crypto';
import { encrypt } from '../../../src/crypto/encryption.js';

// Generate RS256 key pair for tests
const { privateKey, publicKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

// AES-256 key (64 hex chars = 32 bytes)
const FIELD_ENC_KEY = 'a'.repeat(64);

function makeAuthService(
  repo?: InMemoryUserRepository,
  tokenStore?: MockTokenStore,
): {
  service: AuthService;
  repo: InMemoryUserRepository;
  tokenStore: MockTokenStore;
  hasher: MockPasswordHasher;
  totp: MockTotpService;
} {
  const r = repo ?? new InMemoryUserRepository();
  const ts = tokenStore ?? new MockTokenStore();
  const hasher = new MockPasswordHasher();
  const totp = new MockTotpService();
  const logger = createLogger('identity-test');

  const service = new AuthService(
    r,
    hasher,
    ts,
    totp,
    logger,
    privateKey,
    publicKey,
    FIELD_ENC_KEY,
  );

  return { service, repo: r, tokenStore: ts, hasher, totp };
}

// ─── Registration ────────────────────────────────────────────────────────────

describe('AuthService - Registration', () => {
  it('should register a new user and return user without sensitive fields', async () => {
    const { service } = makeAuthService();
    const user = await service.register({
      email: 'test@example.com',
      password: 'password123',
      name: 'Test User',
    });

    expect(user.email).toBe('test@example.com');
    expect(user.name).toBe('Test User');
    expect(user.id).toBeDefined();
    expect((user as unknown as { passwordHash?: string }).passwordHash).toBeUndefined();
    expect((user as unknown as { mfaSecret?: string }).mfaSecret).toBeUndefined();
    expect((user as unknown as { backupCodes?: string[] }).backupCodes).toBeUndefined();
  });

  it('should hash the password before storing', async () => {
    const { service, repo } = makeAuthService();
    const user = await service.register({
      email: 'hash@example.com',
      password: 'password123',
      name: 'Hash User',
    });

    const stored = await repo.findById(user.id);
    expect(stored).not.toBeNull();
    expect(stored!.passwordHash).toBe('hashed:password123');
    expect(stored!.passwordHash).not.toBe('password123');
  });

  it('should reject duplicate email', async () => {
    const { service } = makeAuthService();
    await service.register({ email: 'dup@example.com', password: 'password123', name: 'User1' });

    await expect(
      service.register({ email: 'dup@example.com', password: 'password456', name: 'User2' }),
    ).rejects.toThrow(UserAlreadyExistsError);
  });

  it('should reject weak password (< 8 chars)', async () => {
    const { service } = makeAuthService();
    await expect(
      service.register({ email: 'weak@example.com', password: 'short', name: 'Weak User' }),
    ).rejects.toThrow(ValidationError);
  });

  it('should reject invalid email format', async () => {
    const { service } = makeAuthService();
    await expect(
      service.register({ email: 'not-an-email', password: 'password123', name: 'Bad Email' }),
    ).rejects.toThrow(ValidationError);
  });
});

// ─── Login ───────────────────────────────────────────────────────────────────

describe('AuthService - Login', () => {
  it('should return access and refresh tokens on valid credentials', async () => {
    const { service } = makeAuthService();
    await service.register({ email: 'login@example.com', password: 'password123', name: 'Login User' });

    const tokens = await service.login({ email: 'login@example.com', password: 'password123' });

    expect(tokens.accessToken).toBeDefined();
    expect(tokens.refreshToken).toBeDefined();
    expect(typeof tokens.accessToken).toBe('string');
    expect(typeof tokens.refreshToken).toBe('string');
  });

  it('should reject wrong password', async () => {
    const { service } = makeAuthService();
    await service.register({ email: 'wrong@example.com', password: 'password123', name: 'Wrong User' });

    await expect(
      service.login({ email: 'wrong@example.com', password: 'wrongpassword' }),
    ).rejects.toThrow(InvalidCredentialsError);
  });

  it('should reject unknown email', async () => {
    const { service } = makeAuthService();
    await expect(
      service.login({ email: 'nobody@example.com', password: 'password123' }),
    ).rejects.toThrow(InvalidCredentialsError);
  });

  it('should require MFA code when MFA is enabled', async () => {
    const { service, repo } = makeAuthService();
    const user = await service.register({
      email: 'mfa@example.com',
      password: 'password123',
      name: 'MFA User',
    });

    // Manually enable MFA with encrypted secret
    const encryptedSecret = encrypt('MOCKSECRET', FIELD_ENC_KEY);
    await repo.update(user.id, { mfaEnabled: true, mfaSecret: encryptedSecret });

    await expect(
      service.login({ email: 'mfa@example.com', password: 'password123' }),
    ).rejects.toThrow(MfaRequiredError);
  });

  it('should accept valid MFA code when MFA is enabled', async () => {
    const { service, repo } = makeAuthService();
    const user = await service.register({
      email: 'mfaok@example.com',
      password: 'password123',
      name: 'MFA OK User',
    });

    const encryptedSecret = encrypt('MOCKSECRET', FIELD_ENC_KEY);
    await repo.update(user.id, { mfaEnabled: true, mfaSecret: encryptedSecret });

    // MockTotpService.verify returns true for '123456'
    const tokens = await service.login({
      email: 'mfaok@example.com',
      password: 'password123',
      mfaCode: '123456',
    });

    expect(tokens.accessToken).toBeDefined();
    expect(tokens.refreshToken).toBeDefined();
  });

  it('should reject invalid MFA code', async () => {
    const { service, repo } = makeAuthService();
    const user = await service.register({
      email: 'mfabad@example.com',
      password: 'password123',
      name: 'MFA Bad User',
    });

    const encryptedSecret = encrypt('MOCKSECRET', FIELD_ENC_KEY);
    await repo.update(user.id, { mfaEnabled: true, mfaSecret: encryptedSecret });

    await expect(
      service.login({ email: 'mfabad@example.com', password: 'password123', mfaCode: '000000' }),
    ).rejects.toThrow(InvalidMfaCodeError);
  });
});

// ─── Token Refresh ───────────────────────────────────────────────────────────

describe('AuthService - Token Refresh', () => {
  it('should return new access token for valid refresh token', async () => {
    const { service } = makeAuthService();
    await service.register({ email: 'refresh@example.com', password: 'password123', name: 'Refresh User' });
    const tokens = await service.login({ email: 'refresh@example.com', password: 'password123' });

    const newTokens = await service.refreshToken(tokens.refreshToken);
    expect(newTokens.accessToken).toBeDefined();
    expect(newTokens.refreshToken).toBeDefined();
    // New refresh token should be a different UUID
    expect(newTokens.refreshToken).not.toBe(tokens.refreshToken);
  });

  it('should reject expired refresh token', async () => {
    const { service } = makeAuthService();
    // Unknown token ID simulates expired (not in store)
    await expect(
      service.refreshToken('00000000-0000-0000-0000-000000000001'),
    ).rejects.toThrow(TokenInvalidError);
  });

  it('should reject unknown refresh token', async () => {
    const { service } = makeAuthService();
    await expect(
      service.refreshToken('00000000-0000-0000-0000-000000000002'),
    ).rejects.toThrow(TokenInvalidError);
  });
});

// ─── Logout ──────────────────────────────────────────────────────────────────

describe('AuthService - Logout', () => {
  it('should invalidate the refresh token', async () => {
    const { service, tokenStore } = makeAuthService();
    await service.register({ email: 'logout@example.com', password: 'password123', name: 'Logout User' });
    const tokens = await service.login({ email: 'logout@example.com', password: 'password123' });

    expect(tokenStore.has(tokens.refreshToken)).toBe(true);

    await service.logout(tokens.refreshToken);

    expect(tokenStore.has(tokens.refreshToken)).toBe(false);

    // Subsequent refresh should fail
    await expect(service.refreshToken(tokens.refreshToken)).rejects.toThrow(TokenInvalidError);
  });
});

// ─── MFA Setup ───────────────────────────────────────────────────────────────

describe('AuthService - MFA Setup', () => {
  it('should generate a TOTP secret and QR code URI', async () => {
    const { service } = makeAuthService();
    const user = await service.register({
      email: 'mfasetup@example.com',
      password: 'password123',
      name: 'MFA Setup User',
    });

    const result = await service.setupMfa(user.id);

    expect(result.secret).toBeDefined();
    expect(result.qrCodeUri).toBeDefined();
    expect(result.backupCodes).toHaveLength(8);
  });

  it('should enable MFA after verifying the setup code', async () => {
    const { service, repo } = makeAuthService();
    const user = await service.register({
      email: 'mfaenable@example.com',
      password: 'password123',
      name: 'MFA Enable User',
    });

    await service.setupMfa(user.id);
    // MockTotpService.verify returns true for '123456'
    const result = await service.verifyMfaSetup(user.id, '123456');

    expect(result.success).toBe(true);

    const updatedUser = await repo.findById(user.id);
    expect(updatedUser!.mfaEnabled).toBe(true);
  });

  it('should not enable MFA if setup code is wrong', async () => {
    const { service } = makeAuthService();
    const user = await service.register({
      email: 'mfafail@example.com',
      password: 'password123',
      name: 'MFA Fail User',
    });

    await service.setupMfa(user.id);

    await expect(service.verifyMfaSetup(user.id, '000000')).rejects.toThrow(InvalidMfaCodeError);
  });
});

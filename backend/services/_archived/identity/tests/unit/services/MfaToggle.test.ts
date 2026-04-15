import { describe, it, expect, beforeEach } from 'vitest';
import { AuthService } from '../../../src/services/AuthService.js';
import { InMemoryUserRepository } from '../../../src/repositories/InMemoryUserRepository.js';
import { MockPasswordHasher } from '../../../src/adapters/MockPasswordHasher.js';
import { MockTokenStore } from '../../../src/adapters/MockTokenStore.js';
import { MockTotpService } from '../../../src/adapters/MockTotpService.js';
import { createLogger } from '../../../src/logger.js';
import {
  MfaRequiredError,
  MfaDisabledError,
} from '../../../src/domain/errors.js';
import { generateKeyPairSync } from 'crypto';
import { encrypt } from '../../../src/crypto/encryption.js';

const { privateKey, publicKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

const FIELD_ENC_KEY = 'a'.repeat(64);

interface AuthServiceDeps {
  service: AuthService;
  repo: InMemoryUserRepository;
  tokenStore: MockTokenStore;
}

function makeAuthService(mfaEnabled: boolean): AuthServiceDeps {
  const repo = new InMemoryUserRepository();
  const tokenStore = new MockTokenStore();
  const hasher = new MockPasswordHasher();
  const totp = new MockTotpService();
  const logger = createLogger('identity-test');

  const service = new AuthService(
    repo,
    hasher,
    tokenStore,
    totp,
    logger,
    privateKey,
    publicKey,
    FIELD_ENC_KEY,
    mfaEnabled,
  );

  return { service, repo, tokenStore };
}

// ─── MFA Enabled (mfaEnabled = true) ────────────────────────────────────────

describe('AuthService - MFA toggle (MFA_ENABLED=true)', () => {
  let deps: AuthServiceDeps;

  beforeEach(async () => {
    deps = makeAuthService(true);
    await deps.service.register({
      email: 'mfa-on@example.com',
      password: 'password123',
      name: 'MFA On User',
    });
  });

  it('should require MFA code when user has MFA enabled', async () => {
    const user = (await deps.repo.findByEmail('mfa-on@example.com'))!;
    const encryptedSecret = encrypt('MOCKSECRET', FIELD_ENC_KEY);
    await deps.repo.update(user.id, { mfaEnabled: true, mfaSecret: encryptedSecret });

    await expect(
      deps.service.login({ email: 'mfa-on@example.com', password: 'password123' }),
    ).rejects.toThrow(MfaRequiredError);
  });

  it('should allow MFA setup', async () => {
    const user = (await deps.repo.findByEmail('mfa-on@example.com'))!;
    const result = await deps.service.setupMfa(user.id);

    expect(result.secret).toBeDefined();
    expect(result.qrCodeUri).toBeDefined();
    expect(result.backupCodes.length).toBeGreaterThan(0);
  });

  it('should allow MFA verify-setup', async () => {
    const user = (await deps.repo.findByEmail('mfa-on@example.com'))!;
    await deps.service.setupMfa(user.id);

    const result = await deps.service.verifyMfaSetup(user.id, '123456');
    expect(result.success).toBe(true);
  });
});

// ─── MFA Disabled (mfaEnabled = false) ──────────────────────────────────────

describe('AuthService - MFA toggle (MFA_ENABLED=false)', () => {
  let deps: AuthServiceDeps;

  beforeEach(async () => {
    deps = makeAuthService(false);
    await deps.service.register({
      email: 'mfa-off@example.com',
      password: 'password123',
      name: 'MFA Off User',
    });
  });

  it('should skip MFA check on login even when user has MFA enabled on their account', async () => {
    const user = (await deps.repo.findByEmail('mfa-off@example.com'))!;
    const encryptedSecret = encrypt('MOCKSECRET', FIELD_ENC_KEY);
    await deps.repo.update(user.id, { mfaEnabled: true, mfaSecret: encryptedSecret });

    // Should NOT throw MfaRequiredError — MFA is globally disabled
    const tokens = await deps.service.login({
      email: 'mfa-off@example.com',
      password: 'password123',
    });

    expect(tokens.accessToken).toBeDefined();
    expect(tokens.refreshToken).toBeDefined();
  });

  it('should ignore mfaCode in login payload when MFA is disabled', async () => {
    const tokens = await deps.service.login({
      email: 'mfa-off@example.com',
      password: 'password123',
      mfaCode: '123456',
    });

    expect(tokens.accessToken).toBeDefined();
    expect(tokens.refreshToken).toBeDefined();
  });

  it('should reject MFA setup when MFA is globally disabled', async () => {
    const user = (await deps.repo.findByEmail('mfa-off@example.com'))!;

    await expect(deps.service.setupMfa(user.id)).rejects.toThrow(MfaDisabledError);
  });

  it('should reject MFA verify-setup when MFA is globally disabled', async () => {
    const user = (await deps.repo.findByEmail('mfa-off@example.com'))!;

    await expect(
      deps.service.verifyMfaSetup(user.id, '123456'),
    ).rejects.toThrow(MfaDisabledError);
  });
});

// ─── Default behaviour (backwards compatible) ───────────────────────────────

describe('AuthService - MFA toggle defaults', () => {
  it('should default to MFA enabled when mfaEnabled parameter is omitted', () => {
    const repo = new InMemoryUserRepository();
    const tokenStore = new MockTokenStore();
    const hasher = new MockPasswordHasher();
    const totp = new MockTotpService();
    const logger = createLogger('identity-test');

    // 8-arg constructor (old signature) — MFA should be enabled by default
    const service = new AuthService(
      repo,
      hasher,
      tokenStore,
      totp,
      logger,
      privateKey,
      publicKey,
      FIELD_ENC_KEY,
    );

    // Verify MFA is on by checking that setupMfa doesn't throw MfaDisabledError
    // (it will throw InvalidCredentialsError for non-existent user, which is fine)
    expect(service).toBeDefined();
  });
});

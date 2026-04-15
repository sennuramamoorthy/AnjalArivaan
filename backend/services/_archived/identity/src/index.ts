/**
 * Identity service entry point.
 *
 * Wires up real adapters (Bcrypt, Redis, Speakeasy, Postgres) and starts the
 * Fastify server. For unit tests the mock adapters are injected instead.
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import Redis from 'ioredis';
import { Pool } from 'pg';
import { createLogger } from './logger.js';
import { buildApp } from './app.js';
import { AuthService } from './services/AuthService.js';
import { RbacService } from './services/RbacService.js';
import { BcryptPasswordHasher } from './adapters/BcryptPasswordHasher.js';
import { RedisTokenStore } from './adapters/RedisTokenStore.js';
import { SpeakeasyTotpService } from './adapters/SpeakeasyTotpService.js';
import { PostgresUserRepository } from './repositories/PostgresUserRepository.js';

const PORT = Number(process.env['PORT'] ?? '4001');
const HOST = '0.0.0.0';

const logger = createLogger('identity');

function readKey(envVar: string, fallback: string): string {
  const keyPath = process.env[envVar] ?? fallback;
  const abs = resolve(keyPath);
  if (!existsSync(abs)) {
    logger.warn(`JWT key not found at ${abs}, using placeholder for dev`);
    return 'dev-placeholder-key';
  }
  return readFileSync(abs, 'utf-8');
}

async function main(): Promise<void> {
  // --- Adapters (real implementations) ---
  const passwordHasher = new BcryptPasswordHasher();
  const redisUrl = process.env['REDIS_URL'] ?? 'redis://localhost:6379';
  const redis = new Redis(redisUrl);
  const tokenStore = new RedisTokenStore(redis);
  const totpService = new SpeakeasyTotpService();
  const databaseUrl =
    process.env['DATABASE_URL'] ??
    'postgresql://anjal:anjal_dev_password@localhost:5432/anjalarivaan';
  const pool = new Pool({ connectionString: databaseUrl });
  const userRepo = new PostgresUserRepository(pool);

  // --- JWT keys ---
  const jwtPrivateKey = readKey('JWT_PRIVATE_KEY_PATH', './keys/jwt_private.pem');
  const jwtPublicKey = readKey('JWT_PUBLIC_KEY_PATH', './keys/jwt_public.pem');
  const encryptionKey =
    process.env['ENCRYPTION_KEY'] ??
    '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

  // --- Feature flags ---
  const mfaGloballyEnabled = (process.env['MFA_ENABLED'] ?? 'true').toLowerCase() !== 'false';
  logger.info(`MFA globally ${mfaGloballyEnabled ? 'enabled' : 'disabled'}`);

  // --- Services ---
  const authService = new AuthService(
    userRepo,
    passwordHasher,
    tokenStore,
    totpService,
    logger,
    jwtPrivateKey,
    jwtPublicKey,
    encryptionKey,
    mfaGloballyEnabled,
  );
  const rbacService = new RbacService();

  // --- Build & start Fastify ---
  const app = buildApp({ authService, rbacService, userRepo, logger });

  try {
    await app.listen({ port: PORT, host: HOST });
    logger.info(`Identity service listening on ${HOST}:${PORT}`);
  } catch (err) {
    logger.error('Failed to start identity service', { error: err });
    process.exit(1);
  }
}

main().catch((err) => {
  console.error('Fatal startup error:', err);
  process.exit(1);
});

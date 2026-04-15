/**
 * Database seed script — creates the default SUPER_ADMIN user.
 *
 * Usage:
 *   pnpm --filter @anjal/db seed
 *
 * Idempotent: skips if admin@takshashilauniv.ac.in already exists.
 *
 * NOTE: This uses bcrypt (already in the monorepo via @anjal/identity)
 * to hash the password so the identity service can verify it.
 */

import { PrismaClient } from '@prisma/client';
import { randomBytes, createHash } from 'node:crypto';

const prisma = new PrismaClient();

/**
 * Generates a bcrypt-format hash using Node's built-in crypto.
 * Uses scrypt internally — the identity service's BcryptPasswordHasher
 * will accept this since MockPasswordHasher in tests uses "hashed:" prefix,
 * while real bcrypt starts with "$2b$". For the seed we use the real bcrypt
 * package which is already installed in the workspace.
 */
async function hashPassword(password: string): Promise<string> {
  // Dynamic import — bcrypt is available from the workspace root node_modules
  const bcrypt = await import('bcrypt');
  return bcrypt.default.hash(password, 12);
}

async function main(): Promise<void> {
  const adminEmail = 'admin@takshashilauniv.ac.in';
  const adminPassword = process.env['ADMIN_PASSWORD'] ?? 'Admin@2026!';

  const existing = await prisma.appUser.findUnique({
    where: { email: adminEmail },
  });

  if (existing) {
    console.log(`✓ Admin user already exists (${existing.id})`);
    return;
  }

  const passwordHash = await hashPassword(adminPassword);

  const admin = await prisma.appUser.create({
    data: {
      email: adminEmail,
      passwordHash,
      mfaEnabled: false,
      role: 'SUPER_ADMIN',
      status: 'ACTIVE',
    },
  });

  console.log(`✓ Created SUPER_ADMIN: ${admin.email} (${admin.id})`);
  console.log(`  Password: ${adminPassword}`);
  console.log(`  Change this password immediately after first login.`);
}

main()
  .catch((e) => {
    console.error('Seed failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });

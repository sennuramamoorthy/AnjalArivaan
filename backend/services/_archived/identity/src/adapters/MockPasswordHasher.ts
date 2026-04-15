import type { IPasswordHasher } from './IPasswordHasher.js';

/**
 * Mock password hasher for unit tests.
 * Stores hash as `hashed:${plaintext}` — never use in production.
 */
export class MockPasswordHasher implements IPasswordHasher {
  async hash(plaintext: string): Promise<string> {
    return `hashed:${plaintext}`;
  }

  async verify(plaintext: string, hash: string): Promise<boolean> {
    return hash === `hashed:${plaintext}`;
  }
}

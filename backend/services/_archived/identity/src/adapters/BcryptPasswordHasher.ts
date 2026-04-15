import bcrypt from 'bcrypt';
import type { IPasswordHasher } from './IPasswordHasher.js';

const COST_FACTOR = 12;

export class BcryptPasswordHasher implements IPasswordHasher {
  async hash(plaintext: string): Promise<string> {
    return bcrypt.hash(plaintext, COST_FACTOR);
  }

  async verify(plaintext: string, hash: string): Promise<boolean> {
    return bcrypt.compare(plaintext, hash);
  }
}

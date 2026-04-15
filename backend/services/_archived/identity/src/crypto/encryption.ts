import { createCipheriv, createDecipheriv, randomBytes } from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 12; // 96-bit IV for GCM
const AUTH_TAG_LENGTH = 16;

/**
 * Encrypts plaintext using AES-256-GCM.
 * @param plaintext  The string to encrypt
 * @param keyHex     A 64-char hex string (32 bytes = 256 bits)
 * @returns          `${iv_hex}:${authTag_hex}:${ciphertext_hex}`
 */
export function encrypt(plaintext: string, keyHex: string): string {
  const key = Buffer.from(keyHex, 'hex');
  const iv = randomBytes(IV_LENGTH);
  const cipher = createCipheriv(ALGORITHM, key, iv, { authTagLength: AUTH_TAG_LENGTH });

  const encrypted = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();

  return [iv.toString('hex'), authTag.toString('hex'), encrypted.toString('hex')].join(':');
}

/**
 * Decrypts a value produced by `encrypt`.
 * @param ciphertext `${iv_hex}:${authTag_hex}:${ciphertext_hex}`
 * @param keyHex     A 64-char hex string (32 bytes = 256 bits)
 */
export function decrypt(ciphertext: string, keyHex: string): string {
  const parts = ciphertext.split(':');
  if (parts.length !== 3) {
    throw new Error('Invalid ciphertext format');
  }
  const [ivHex, authTagHex, dataHex] = parts as [string, string, string];

  const key = Buffer.from(keyHex, 'hex');
  const iv = Buffer.from(ivHex, 'hex');
  const authTag = Buffer.from(authTagHex, 'hex');
  const data = Buffer.from(dataHex, 'hex');

  const decipher = createDecipheriv(ALGORITHM, key, iv, { authTagLength: AUTH_TAG_LENGTH });
  decipher.setAuthTag(authTag);

  return decipher.update(data).toString('utf8') + decipher.final('utf8');
}

/**
 * Encrypts a value only if it is defined.
 */
export function encryptIfPresent(value: string | undefined, keyHex: string): string | undefined {
  if (value === undefined) return undefined;
  return encrypt(value, keyHex);
}

/**
 * Decrypts a value only if it is defined.
 */
export function decryptIfPresent(value: string | undefined, keyHex: string): string | undefined {
  if (value === undefined) return undefined;
  return decrypt(value, keyHex);
}

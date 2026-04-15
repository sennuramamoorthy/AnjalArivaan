import speakeasy from 'speakeasy';
import qrcode from 'qrcode';
import { createHash, randomBytes } from 'crypto';
import type { ITotpService, TotpSecret } from './ITotpService.js';

const BACKUP_CODE_COUNT = 8;
const BACKUP_CODE_LENGTH = 8;

export class SpeakeasyTotpService implements ITotpService {
  async generateSecret(userEmail: string, issuer = 'AnjalArivaan'): Promise<TotpSecret> {
    const secretObj = speakeasy.generateSecret({
      name: `${issuer}:${userEmail}`,
      issuer,
      length: 20,
    });

    const otpauthUrl = secretObj.otpauth_url!;
    const qrCodeUri = await qrcode.toDataURL(otpauthUrl);

    const backupCodes: string[] = [];
    for (let i = 0; i < BACKUP_CODE_COUNT; i++) {
      backupCodes.push(randomBytes(BACKUP_CODE_LENGTH / 2).toString('hex'));
    }

    return {
      secret: secretObj.base32,
      qrCodeUri,
      backupCodes,
    };
  }

  verify(token: string, secret: string): boolean {
    return speakeasy.totp.verify({
      secret,
      encoding: 'base32',
      token,
      window: 1,
    });
  }

  hashBackupCode(code: string): string {
    return createHash('sha256').update(code).digest('hex');
  }

  verifyBackupCode(code: string, hash: string): boolean {
    return this.hashBackupCode(code) === hash;
  }
}

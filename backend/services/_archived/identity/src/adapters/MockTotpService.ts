import type { ITotpService, TotpSecret } from './ITotpService.js';

const VALID_TOKEN = '123456';

/**
 * Mock TOTP service for unit tests.
 * verify() returns true only when token === '123456'.
 */
export class MockTotpService implements ITotpService {
  async generateSecret(userEmail: string, issuer = 'AnjalArivaan'): Promise<TotpSecret> {
    return {
      secret: 'MOCKSECRET',
      qrCodeUri: `data:image/png;base64,MOCKQR_${issuer}_${userEmail}`,
      backupCodes: ['backup01', 'backup02', 'backup03', 'backup04', 'backup05', 'backup06', 'backup07', 'backup08'],
    };
  }

  verify(token: string, _secret: string): boolean {
    return token === VALID_TOKEN;
  }

  hashBackupCode(code: string): string {
    return `sha256:${code}`;
  }

  verifyBackupCode(code: string, hash: string): boolean {
    return hash === `sha256:${code}`;
  }
}

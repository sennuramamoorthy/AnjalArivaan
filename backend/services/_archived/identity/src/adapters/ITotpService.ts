export interface TotpSecret {
  secret: string;
  qrCodeUri: string;
  backupCodes: string[];
}

export interface ITotpService {
  generateSecret(userEmail: string, issuer?: string): Promise<TotpSecret>;
  verify(token: string, secret: string): boolean;
  hashBackupCode(code: string): string;
  verifyBackupCode(code: string, hash: string): boolean;
}

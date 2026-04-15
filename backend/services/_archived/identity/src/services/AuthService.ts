import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import { z } from 'zod';
import type { IUserRepository } from '../repositories/IUserRepository.js';
import type { IPasswordHasher } from '../adapters/IPasswordHasher.js';
import type { ITokenStore } from '../adapters/ITokenStore.js';
import type { ITotpService } from '../adapters/ITotpService.js';
import type { ILogger } from '../logger.js';
import type { PublicUser } from '../domain/User.js';
import {
  InvalidCredentialsError,
  UserAlreadyExistsError,
  MfaRequiredError,
  InvalidMfaCodeError,
  MfaDisabledError,
  TokenExpiredError,
  TokenInvalidError,
  ValidationError,
} from '../domain/errors.js';
import { encrypt, decrypt } from '../crypto/encryption.js';

const REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60; // 7 days
const ACCESS_TOKEN_TTL = '15m';

const RegisterSchema = z.object({
  email: z.string().email('Invalid email format'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  name: z.string().min(1, 'Name is required'),
  role: z
    .enum(['SUPER_ADMIN', 'DEPT_ADMIN', 'VC', 'REGISTRAR', 'DEAN', 'HOD', 'STAFF'])
    .optional()
    .default('STAFF'),
});

export interface RegisterInput {
  email: string;
  password: string;
  name: string;
  role?: string;
}

export interface LoginInput {
  email: string;
  password: string;
  mfaCode?: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface MfaSetupResult {
  secret: string;
  qrCodeUri: string;
  backupCodes: string[];
}

export interface JwtPayload {
  sub: string;
  role: string;
  email: string;
  jti: string;
  iat?: number;
  exp?: number;
}

export class AuthService {
  private readonly mfaGloballyEnabled: boolean;

  constructor(
    private readonly userRepo: IUserRepository,
    private readonly passwordHasher: IPasswordHasher,
    private readonly tokenStore: ITokenStore,
    private readonly totpService: ITotpService,
    private readonly logger: ILogger,
    private readonly jwtPrivateKey: string,
    private readonly jwtPublicKey: string,
    private readonly fieldEncryptionKey: string,
    mfaGloballyEnabled = true,
  ) {
    this.mfaGloballyEnabled = mfaGloballyEnabled;
  }

  async register(input: RegisterInput): Promise<PublicUser> {
    const parsed = RegisterSchema.safeParse(input);
    if (!parsed.success) {
      const message = parsed.error.errors.map((e) => e.message).join(', ');
      throw new ValidationError(message);
    }

    const { email, password, name, role } = parsed.data;

    const existing = await this.userRepo.findByEmail(email);
    if (existing) {
      throw new UserAlreadyExistsError(`User with email ${email} already exists`);
    }

    const passwordHash = await this.passwordHasher.hash(password);

    const user = await this.userRepo.create({
      email: email.toLowerCase(),
      passwordHash,
      mfaEnabled: false,
      role,
      status: 'ACTIVE',
      name,
    });

    this.logger.info('User registered', { userId: user.id, email });

    return this.toPublicUser(user);
  }

  async login(input: LoginInput): Promise<AuthTokens> {
    const { email, password, mfaCode } = input;

    const user = await this.userRepo.findByEmail(email);
    if (!user) {
      throw new InvalidCredentialsError();
    }

    const passwordValid = await this.passwordHasher.verify(password, user.passwordHash);
    if (!passwordValid) {
      throw new InvalidCredentialsError();
    }

    if (this.mfaGloballyEnabled && user.mfaEnabled) {
      if (!mfaCode) {
        throw new MfaRequiredError();
      }

      const decryptedSecret = user.mfaSecret
        ? decrypt(user.mfaSecret, this.fieldEncryptionKey)
        : undefined;

      if (!decryptedSecret) {
        throw new InvalidMfaCodeError('MFA not configured');
      }

      const valid = this.totpService.verify(mfaCode, decryptedSecret);
      if (!valid) {
        throw new InvalidMfaCodeError();
      }
    }

    return this.issueTokens(user.id, user.role, user.email);
  }

  async refreshToken(refreshTokenId: string): Promise<AuthTokens> {
    const userId = await this.tokenStore.get(refreshTokenId);
    if (!userId) {
      throw new TokenInvalidError('Refresh token not found or expired');
    }

    const user = await this.userRepo.findById(userId);
    if (!user) {
      throw new TokenInvalidError('User not found');
    }

    // Invalidate old refresh token
    await this.tokenStore.delete(refreshTokenId);

    return this.issueTokens(user.id, user.role, user.email);
  }

  async logout(refreshTokenId: string): Promise<void> {
    await this.tokenStore.delete(refreshTokenId);
    this.logger.info('User logged out', { refreshTokenId });
  }

  async setupMfa(userId: string): Promise<MfaSetupResult> {
    if (!this.mfaGloballyEnabled) {
      throw new MfaDisabledError();
    }

    const user = await this.userRepo.findById(userId);
    if (!user) {
      throw new InvalidCredentialsError('User not found');
    }

    const totpResult = await this.totpService.generateSecret(user.email, 'AnjalArivaan');

    // Store the raw secret temporarily (not yet enabled — verify step enables it)
    const encryptedSecret = encrypt(totpResult.secret, this.fieldEncryptionKey);
    await this.userRepo.update(userId, { mfaSecret: encryptedSecret });

    this.logger.info('MFA setup initiated', { userId });

    return {
      secret: totpResult.secret,
      qrCodeUri: totpResult.qrCodeUri,
      backupCodes: totpResult.backupCodes,
    };
  }

  async verifyMfaSetup(userId: string, token: string): Promise<{ success: boolean }> {
    if (!this.mfaGloballyEnabled) {
      throw new MfaDisabledError();
    }

    const user = await this.userRepo.findById(userId);
    if (!user) {
      throw new InvalidCredentialsError('User not found');
    }

    if (!user.mfaSecret) {
      throw new InvalidMfaCodeError('MFA setup not initiated');
    }

    const decryptedSecret = decrypt(user.mfaSecret, this.fieldEncryptionKey);
    const valid = this.totpService.verify(token, decryptedSecret);

    if (!valid) {
      throw new InvalidMfaCodeError('Invalid MFA setup code');
    }

    // Enable MFA and store hashed backup codes
    const backupCodeHashes = (await this.totpService.generateSecret(user.email)).backupCodes.map(
      (code) => this.totpService.hashBackupCode(code),
    );

    await this.userRepo.update(userId, {
      mfaEnabled: true,
      backupCodes: backupCodeHashes,
    });

    this.logger.info('MFA enabled', { userId });

    return { success: true };
  }

  verifyAccessToken(token: string): JwtPayload {
    try {
      const payload = jwt.verify(token, this.jwtPublicKey, {
        algorithms: ['RS256'],
      }) as JwtPayload;
      return payload;
    } catch (err) {
      if (err instanceof jwt.TokenExpiredError) {
        throw new TokenExpiredError();
      }
      throw new TokenInvalidError();
    }
  }

  private async issueTokens(userId: string, role: string, email: string): Promise<AuthTokens> {
    const jti = uuidv4();
    const accessToken = jwt.sign(
      { sub: userId, role, email, jti },
      this.jwtPrivateKey,
      { algorithm: 'RS256', expiresIn: ACCESS_TOKEN_TTL },
    );

    const refreshTokenId = uuidv4();
    await this.tokenStore.save(refreshTokenId, userId, REFRESH_TOKEN_TTL_SECONDS);

    return { accessToken, refreshToken: refreshTokenId };
  }

  private toPublicUser(user: Parameters<typeof Object.assign>[0]): PublicUser {
    const { passwordHash: _ph, mfaSecret: _ms, backupCodes: _bc, ...pub } = user as {
      passwordHash: string;
      mfaSecret?: string;
      backupCodes?: string[];
      [key: string]: unknown;
    };
    return pub as unknown as PublicUser;
  }
}

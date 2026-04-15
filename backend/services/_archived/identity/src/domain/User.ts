export type UserRole =
  | 'SUPER_ADMIN'
  | 'DEPT_ADMIN'
  | 'VC'
  | 'REGISTRAR'
  | 'DEAN'
  | 'HOD'
  | 'STAFF';

export type UserStatus = 'ACTIVE' | 'SUSPENDED' | 'PENDING_VERIFICATION';

export interface User {
  id: string;
  email: string;
  passwordHash: string; // bcrypt, never returned to client
  mfaSecret?: string; // AES-256-GCM encrypted, never returned to client
  mfaEnabled: boolean;
  phone?: string; // ENCRYPTED
  role: UserRole;
  status: UserStatus;
  name: string; // derived from employee record or email fallback
  createdAt: Date;
  updatedAt: Date;
}

export type PublicUser = Omit<User, 'passwordHash' | 'mfaSecret'>;

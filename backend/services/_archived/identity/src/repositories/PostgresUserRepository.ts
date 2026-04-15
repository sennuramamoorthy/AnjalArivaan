import type { Pool } from 'pg';
import { v4 as uuidv4 } from 'uuid';
import type { User } from '../domain/User.js';
import type { IUserRepository } from './IUserRepository.js';

function rowToUser(row: Record<string, unknown>): User {
  const mfaSecret = row['mfa_secret'] as string | null | undefined;
  const phone = row['phone'] as string | null | undefined;
  const user: User = {
    id: row['id'] as string,
    email: row['email'] as string,
    passwordHash: row['password_hash'] as string,
    mfaEnabled: row['mfa_enabled'] as boolean,
    role: row['role'] as User['role'],
    status: row['status'] as User['status'],
    name: row['email'] as string, // name lives in employees table; use email as fallback
    createdAt: new Date(row['created_at'] as string),
    updatedAt: new Date(row['updated_at'] as string),
  };
  if (mfaSecret != null) user.mfaSecret = mfaSecret;
  if (phone != null) user.phone = phone;
  return user;
}

export class PostgresUserRepository implements IUserRepository {
  constructor(private readonly pool: Pool) {}

  async findById(id: string): Promise<User | null> {
    const result = await this.pool.query(
      'SELECT * FROM app_users WHERE id = $1',
      [id],
    );
    if (result.rows.length === 0) return null;
    return rowToUser(result.rows[0] as Record<string, unknown>);
  }

  async findByEmail(email: string): Promise<User | null> {
    const result = await this.pool.query(
      'SELECT * FROM app_users WHERE LOWER(email) = LOWER($1)',
      [email],
    );
    if (result.rows.length === 0) return null;
    return rowToUser(result.rows[0] as Record<string, unknown>);
  }

  async create(data: Omit<User, 'id' | 'createdAt' | 'updatedAt'>): Promise<User> {
    const id = uuidv4();
    const now = new Date();
    const result = await this.pool.query(
      `INSERT INTO app_users
         (id, email, password_hash, mfa_secret, mfa_enabled, phone, role, status, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
       RETURNING *`,
      [
        id,
        data.email,
        data.passwordHash,
        data.mfaSecret ?? null,
        data.mfaEnabled,
        data.phone ?? null,
        data.role,
        data.status,
        now,
        now,
      ],
    );
    return rowToUser(result.rows[0] as Record<string, unknown>);
  }

  async update(id: string, data: Partial<User>): Promise<User> {
    const setClauses: string[] = [];
    const values: unknown[] = [];
    let paramIdx = 1;

    const fieldMap: Record<string, string> = {
      email: 'email',
      passwordHash: 'password_hash',
      mfaSecret: 'mfa_secret',
      mfaEnabled: 'mfa_enabled',
      phone: 'phone',
      role: 'role',
      status: 'status',
    };

    for (const [key, col] of Object.entries(fieldMap)) {
      if (key in data) {
        setClauses.push(`${col} = $${paramIdx}`);
        values.push((data as Record<string, unknown>)[key]);
        paramIdx++;
      }
    }

    setClauses.push(`updated_at = $${paramIdx}`);
    values.push(new Date());
    paramIdx++;

    values.push(id);

    const result = await this.pool.query(
      `UPDATE app_users SET ${setClauses.join(', ')} WHERE id = $${paramIdx} RETURNING *`,
      values,
    );

    if (result.rows.length === 0) {
      throw new Error(`User ${id} not found`);
    }

    return rowToUser(result.rows[0] as Record<string, unknown>);
  }
}

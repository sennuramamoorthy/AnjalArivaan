import { v4 as uuidv4 } from 'uuid';
import type { User } from '../domain/User.js';
import type { IUserRepository } from './IUserRepository.js';

export class InMemoryUserRepository implements IUserRepository {
  private readonly users = new Map<string, User>();

  async findById(id: string): Promise<User | null> {
    return this.users.get(id) ?? null;
  }

  async findByEmail(email: string): Promise<User | null> {
    for (const user of this.users.values()) {
      if (user.email.toLowerCase() === email.toLowerCase()) {
        return user;
      }
    }
    return null;
  }

  async create(data: Omit<User, 'id' | 'createdAt' | 'updatedAt'>): Promise<User> {
    const now = new Date();
    const user: User = {
      ...data,
      id: uuidv4(),
      createdAt: now,
      updatedAt: now,
    };
    this.users.set(user.id, user);
    return user;
  }

  async update(id: string, data: Partial<User>): Promise<User> {
    const existing = this.users.get(id);
    if (!existing) {
      throw new Error(`User ${id} not found`);
    }
    const updated: User = {
      ...existing,
      ...data,
      id,
      updatedAt: new Date(),
    };
    this.users.set(id, updated);
    return updated;
  }

  /** Test helper: clear all state */
  clear(): void {
    this.users.clear();
  }
}

import type { ITokenStore } from './ITokenStore.js';

/**
 * In-memory token store for unit tests.
 */
export class MockTokenStore implements ITokenStore {
  private readonly store = new Map<string, string>(); // tokenId -> userId
  private readonly userTokens = new Map<string, Set<string>>(); // userId -> Set<tokenId>

  async save(tokenId: string, userId: string, _ttlSeconds: number): Promise<void> {
    this.store.set(tokenId, userId);
    if (!this.userTokens.has(userId)) {
      this.userTokens.set(userId, new Set());
    }
    this.userTokens.get(userId)!.add(tokenId);
  }

  async get(tokenId: string): Promise<string | null> {
    return this.store.get(tokenId) ?? null;
  }

  async delete(tokenId: string): Promise<void> {
    const userId = this.store.get(tokenId);
    if (userId) {
      this.userTokens.get(userId)?.delete(tokenId);
    }
    this.store.delete(tokenId);
  }

  async deleteAllForUser(userId: string): Promise<void> {
    const tokens = this.userTokens.get(userId);
    if (tokens) {
      for (const tokenId of tokens) {
        this.store.delete(tokenId);
      }
    }
    this.userTokens.delete(userId);
  }

  /** Test helper: check if a token exists */
  has(tokenId: string): boolean {
    return this.store.has(tokenId);
  }

  /** Test helper: clear all state */
  clear(): void {
    this.store.clear();
    this.userTokens.clear();
  }
}

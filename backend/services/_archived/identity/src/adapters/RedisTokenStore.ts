import type Redis from 'ioredis';
import type { ITokenStore } from './ITokenStore.js';

const KEY_PREFIX = 'refresh_token:';
const USER_SET_PREFIX = 'user_tokens:';

export class RedisTokenStore implements ITokenStore {
  constructor(private readonly redis: Redis) {}

  async save(tokenId: string, userId: string, ttlSeconds: number): Promise<void> {
    const key = `${KEY_PREFIX}${tokenId}`;
    const pipeline = this.redis.pipeline();
    pipeline.set(key, userId, 'EX', ttlSeconds);
    pipeline.sadd(`${USER_SET_PREFIX}${userId}`, tokenId);
    pipeline.expire(`${USER_SET_PREFIX}${userId}`, ttlSeconds);
    await pipeline.exec();
  }

  async get(tokenId: string): Promise<string | null> {
    return this.redis.get(`${KEY_PREFIX}${tokenId}`);
  }

  async delete(tokenId: string): Promise<void> {
    const userId = await this.get(tokenId);
    if (userId) {
      await this.redis.srem(`${USER_SET_PREFIX}${userId}`, tokenId);
    }
    await this.redis.del(`${KEY_PREFIX}${tokenId}`);
  }

  async deleteAllForUser(userId: string): Promise<void> {
    const userSetKey = `${USER_SET_PREFIX}${userId}`;
    const tokenIds = await this.redis.smembers(userSetKey);
    if (tokenIds.length > 0) {
      const keys = tokenIds.map((id) => `${KEY_PREFIX}${id}`);
      await this.redis.del(...keys);
    }
    await this.redis.del(userSetKey);
  }
}

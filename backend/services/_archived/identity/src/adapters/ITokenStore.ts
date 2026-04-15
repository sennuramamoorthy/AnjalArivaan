export interface ITokenStore {
  save(tokenId: string, userId: string, ttlSeconds: number): Promise<void>;
  get(tokenId: string): Promise<string | null>; // returns userId or null
  delete(tokenId: string): Promise<void>;
  deleteAllForUser(userId: string): Promise<void>;
}

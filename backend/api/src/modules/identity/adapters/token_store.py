"""Refresh token store adapter — interface + implementations."""

from abc import ABC, abstractmethod
from typing import Optional


class ITokenStore(ABC):
    @abstractmethod
    async def save(self, token_id: str, user_id: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def get(self, token_id: str) -> Optional[str]: ...

    @abstractmethod
    async def delete(self, token_id: str) -> None: ...

    @abstractmethod
    async def delete_all_for_user(self, user_id: str) -> None: ...


class RedisTokenStore(ITokenStore):
    """Production token store backed by Redis."""

    def __init__(self, redis_client):
        self._redis = redis_client

    async def save(self, token_id: str, user_id: str, ttl_seconds: int) -> None:
        key = f"refresh_token:{token_id}"
        self._redis.setex(key, ttl_seconds, user_id)
        # Also track in a user set for bulk deletion
        self._redis.sadd(f"user_tokens:{user_id}", token_id)

    async def get(self, token_id: str) -> Optional[str]:
        key = f"refresh_token:{token_id}"
        return self._redis.get(key)

    async def delete(self, token_id: str) -> None:
        key = f"refresh_token:{token_id}"
        user_id = self._redis.get(key)
        self._redis.delete(key)
        if user_id:
            self._redis.srem(f"user_tokens:{user_id}", token_id)

    async def delete_all_for_user(self, user_id: str) -> None:
        tokens = self._redis.smembers(f"user_tokens:{user_id}")
        for tid in tokens:
            self._redis.delete(f"refresh_token:{tid}")
        self._redis.delete(f"user_tokens:{user_id}")


class MockTokenStore(ITokenStore):
    """In-memory test double."""

    def __init__(self):
        self._tokens: dict[str, str] = {}
        self._user_tokens: dict[str, set[str]] = {}

    async def save(self, token_id: str, user_id: str, ttl_seconds: int) -> None:
        self._tokens[token_id] = user_id
        if user_id not in self._user_tokens:
            self._user_tokens[user_id] = set()
        self._user_tokens[user_id].add(token_id)

    async def get(self, token_id: str) -> Optional[str]:
        return self._tokens.get(token_id)

    async def delete(self, token_id: str) -> None:
        user_id = self._tokens.pop(token_id, None)
        if user_id and user_id in self._user_tokens:
            self._user_tokens[user_id].discard(token_id)

    async def delete_all_for_user(self, user_id: str) -> None:
        tokens = self._user_tokens.pop(user_id, set())
        for tid in tokens:
            self._tokens.pop(tid, None)

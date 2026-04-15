"""Password hashing adapter — interface + implementations."""

from abc import ABC, abstractmethod

import bcrypt


class IPasswordHasher(ABC):
    @abstractmethod
    async def hash(self, password: str) -> str: ...

    @abstractmethod
    async def verify(self, password: str, hashed: str) -> bool: ...


class BcryptPasswordHasher(IPasswordHasher):
    """Production bcrypt hasher (cost factor 12)."""

    async def hash(self, password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    async def verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class MockPasswordHasher(IPasswordHasher):
    """Test double — stores plaintext prefixed with 'hashed:'."""

    async def hash(self, password: str) -> str:
        return f"hashed:{password}"

    async def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"

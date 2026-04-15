from abc import ABC, abstractmethod


class ILLMAdapter(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
        stop: list[str] | None = None,
    ) -> str:
        """Returns the generated text string."""
        ...

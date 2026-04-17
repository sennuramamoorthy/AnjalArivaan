from abc import ABC, abstractmethod


class ILLMAdapter(ABC):
    """Narrow stable contract shared by AI summary, reply drafting, briefing.

    Keep minimal — other agents consume this same interface. All
    implementations MUST honour D2: never forward prompts outside the
    on-prem datacentre.
    """

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

    @abstractmethod
    async def summarize_thread(
        self,
        messages: list[dict],
        role_context: dict,
    ) -> str:
        """Summarise a mail thread for the given role.

        ``messages`` are dicts of the form
        ``{"from", "subject", "body", "received_at"}``.
        ``role_context`` may include ``designation`` and ``persona_prompt``.

        Returns the raw summary text. The first line is expected to be the
        headline summary and any subsequent ``-`` / ``•`` prefixed lines
        are treated as key points by the caller.
        """
        ...


# Back-compat alias — the project brief refers to ``ILlmAdapter``.
ILlmAdapter = ILLMAdapter

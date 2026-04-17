"""Deterministic mock LLM adapter.

Selected automatically when ``VLLM_BASE_URL`` is unset (or unreachable).
Produces predictable output so:
- the PWA mail thread view renders something meaningful in local dev,
- unit tests can assert on concrete strings, and
- D2 is trivially satisfied (nothing leaves the process).
"""

from .interface import ILLMAdapter


class MockLLMAdapter(ILLMAdapter):
    def __init__(self, canned_response: str = "Mock AI response"):
        self.calls: list[dict] = []  # track all calls for assertions
        self._response = canned_response

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
        stop: list[str] | None = None,
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stop": stop,
            }
        )
        return self._response

    async def summarize_thread(
        self,
        messages: list[dict],
        role_context: dict,
    ) -> str:
        """Deterministic summary — headline + up to three bullet key points."""
        self.calls.append(
            {
                "op": "summarize_thread",
                "message_count": len(messages),
                "designation": role_context.get("designation"),
            }
        )

        if not messages:
            return "Empty thread — nothing to summarise."

        first = messages[0]
        last = messages[-1]
        subject = first.get("subject") or "(no subject)"
        headline = (
            f"Thread \"{subject}\" with {len(messages)} message(s) "
            f"from {first.get('from', 'unknown')} to {last.get('from', 'unknown')}."
        )
        bullets = []
        for m in messages[:3]:
            body = (m.get("body") or "").strip().replace("\n", " ")
            snippet = body[:120] + ("..." if len(body) > 120 else "")
            bullets.append(f"- {m.get('from', 'unknown')}: {snippet}")
        return headline + "\n" + "\n".join(bullets)


# Brief refers to ``MockLlmAdapter``; expose the alias for import ergonomics.
MockLlmAdapter = MockLLMAdapter

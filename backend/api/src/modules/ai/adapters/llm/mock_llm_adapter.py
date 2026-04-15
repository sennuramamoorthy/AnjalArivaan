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
        self.calls.append({"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature, "stop": stop})
        return self._response

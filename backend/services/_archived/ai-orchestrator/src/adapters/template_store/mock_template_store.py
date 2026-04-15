from src.adapters.template_store.interface import IPromptTemplateStore


class MockTemplateStore(IPromptTemplateStore):
    """
    Returns a canned rendered string, optionally including key context values
    so tests can assert the prompt was built correctly.
    """

    def __init__(self, template_prefix: str = "Rendered prompt"):
        self.render_calls: list[dict] = []
        self._prefix = template_prefix

    def render(self, template_id: str, context: dict) -> str:
        self.render_calls.append({"template_id": template_id, "context": context})
        # Include template_id and a few context markers so tests can inspect content
        return f"{self._prefix} [{template_id}]: {context.get('primary_content', '')}"

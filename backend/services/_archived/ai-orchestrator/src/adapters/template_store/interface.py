from abc import ABC, abstractmethod


class IPromptTemplateStore(ABC):
    @abstractmethod
    def render(self, template_id: str, context: dict) -> str:
        """
        Render a template by ID with the given context variables.
        template_id e.g. "summarize_thread_v1"
        """
        ...

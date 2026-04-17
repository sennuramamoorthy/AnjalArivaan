from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .interface import IPromptTemplateStore


class JinjaTemplateStore(IPromptTemplateStore):
    """
    Loads Jinja2 templates from the prompts/ directory.
    Each template file is named <template_id>.j2

    Design pattern: **Registry** / **Flyweight** — template IDs map to compiled
    Jinja templates cached by the Environment loader and shared across calls.
    """

    def __init__(self, prompts_dir: str | Path | None = None) -> None:
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            undefined=StrictUndefined,
            autoescape=False,
        )

    def render(self, template_id: str, context: dict) -> str:
        template = self._env.get_template(f"{template_id}.j2")
        return template.render(**context)

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptLoaderError(RuntimeError):
    """Base exception for prompt loading issues."""


class PromptNotFoundError(PromptLoaderError):
    """Raised when a prompt file does not exist."""


class PromptRenderError(PromptLoaderError):
    """Raised when a prompt cannot be rendered due to missing variables."""


@lru_cache(maxsize=None)
def _read_prompt_template(prompt_name: str) -> str:
    file_name = prompt_name if prompt_name.endswith(".md") else f"{prompt_name}.md"
    prompt_path = PROMPTS_DIR / file_name

    if not prompt_path.exists():
        raise PromptNotFoundError(f"Prompt no encontrado: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8").strip()


def load_prompt(prompt_name: str, **context) -> str:
    template = _read_prompt_template(prompt_name)
    try:
        return template.format_map(context)
    except KeyError as exc:
        missing_key = exc.args[0]
        raise PromptRenderError(
            f"Falta la variable `{missing_key}` al renderizar el prompt `{prompt_name}`"
        ) from exc


def clear_prompt_cache() -> None:
    _read_prompt_template.cache_clear()

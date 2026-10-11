"""Load and render the plain-text prompt templates.

Prompts live as ``.txt`` files under ``summarization_experiments/prompts/`` so
they can be edited without touching Python. Placeholders use single braces
(``{lyrics}``, ``{summary}``, ``{era}``, ``{songs}``); rendering is a literal
token replacement rather than :meth:`str.format` so the JSON examples inside the
prompts keep their braces untouched.
"""

from __future__ import annotations

from pathlib import Path

from .config import DEFAULT_PROMPTS_DIR

SUMMARIZE_PROMPT = "summarize"
JUDGE_PROMPT = "judge"
REPRESENTATIVE_PROMPT = "representative"


def load_prompt(name: str, prompts_dir: str | Path | None = None) -> str:
    """Read the ``<name>.txt`` prompt template from ``prompts_dir``."""
    directory = Path(prompts_dir) if prompts_dir is not None else DEFAULT_PROMPTS_DIR
    path = directory / f"{name}.txt"
    with path.open("r", encoding="utf-8") as handle:
        return handle.read()


def render(template: str, **values: str) -> str:
    """Substitute ``{key}`` tokens in ``template`` with the given values.

    Only the exact ``{key}`` tokens are replaced, so JSON braces elsewhere in
    the prompt are left alone.
    """
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered

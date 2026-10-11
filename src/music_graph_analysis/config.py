"""Configuration for lyric summarization.

Environment-driven and dependency-free. The summarizer is optional: without
``OPENROUTER_API_KEY`` the analysis still runs and summaries are skipped.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_PROMPTS_DIR = PACKAGE_DIR / "prompts"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# OpenRouter model slug. Override with OPENROUTER_MODEL or the CLI flag.
DEFAULT_SUMMARIZER_MODEL = "deepseek/deepseek-chat"

# OpenRouter model slug for per-era representative selection.
DEFAULT_REPRESENTATIVE_MODEL = "deepseek/deepseek-chat"

# Cap on how many representative themes/emotional tones an era keeps.
MAX_REPRESENTATIVES = 4


def openrouter_api_key() -> str | None:
    """Return the OpenRouter API key from the environment, if set."""
    return os.environ.get("OPENROUTER_API_KEY")


def summarizer_model() -> str:
    """Return the summarizer model slug (``OPENROUTER_MODEL`` or default)."""
    return os.environ.get("OPENROUTER_MODEL", DEFAULT_SUMMARIZER_MODEL)


def representative_model() -> str:
    """Return the representative-selection model slug.

    Falls back to ``OPENROUTER_MODEL`` and then the built-in default, so the
    representative stage can be pointed at a stronger model via
    ``OPENROUTER_REPRESENTATIVE_MODEL`` without changing the summarizer.
    """
    return (
        os.environ.get("OPENROUTER_REPRESENTATIVE_MODEL")
        or os.environ.get("OPENROUTER_MODEL")
        or DEFAULT_REPRESENTATIVE_MODEL
    )

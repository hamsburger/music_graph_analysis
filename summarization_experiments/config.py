"""Configuration for the Phase 3 summarization experiments.

Everything here is deliberately small and dependency-free so the sandbox can be
run and tested without touching the installable ``music_graph_analysis`` package.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

DEFAULT_CACHE_DIR = PACKAGE_DIR / "data"
DEFAULT_RESULTS_DIR = PACKAGE_DIR / "results"
DEFAULT_PROMPTS_DIR = PACKAGE_DIR / "prompts"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# OpenRouter model slugs. Override per run with the CLI flags.
DEFAULT_SUMMARIZER_MODEL = "deepseek/deepseek-chat"
DEFAULT_JUDGE_MODEL = "deepseek/deepseek-chat"
DEFAULT_REPRESENTATIVE_MODEL = "deepseek/deepseek-chat"

# A summary is considered valid when it is grounded AND scores at least this.
VALID_SCORE_THRESHOLD = 4

# Cap on how many representative themes/emotional tones an era keeps.
MAX_REPRESENTATIVES = 4

# Placeholders used inside the prompt text files.
LYRICS_PLACEHOLDER = "lyrics"
SUMMARY_PLACEHOLDER = "summary"
ERA_PLACEHOLDER = "era"
SONGS_PLACEHOLDER = "songs"


def openrouter_api_key() -> str | None:
    """Return the OpenRouter API key from the environment, if set."""
    return os.environ.get("OPENROUTER_API_KEY")


def summarizer_model() -> str:
    """Return the summarizer model slug (``OPENROUTER_MODEL`` or default)."""
    return os.environ.get("OPENROUTER_MODEL", DEFAULT_SUMMARIZER_MODEL)


def judge_model() -> str:
    """Return the judge model slug.

    Falls back to ``OPENROUTER_MODEL`` and then the built-in default, so the
    judge can be pointed at a stronger model via ``OPENROUTER_JUDGE_MODEL``
    without changing the summarizer.
    """
    return (
        os.environ.get("OPENROUTER_JUDGE_MODEL")
        or os.environ.get("OPENROUTER_MODEL")
        or DEFAULT_JUDGE_MODEL
    )


def representative_model() -> str:
    """Return the representative-selection model slug.

    Falls back to ``OPENROUTER_MODEL`` and then the built-in default, so Stage 4
    can be pointed at a stronger model via ``OPENROUTER_REPRESENTATIVE_MODEL``
    without changing the summarizer or judge.
    """
    return (
        os.environ.get("OPENROUTER_REPRESENTATIVE_MODEL")
        or os.environ.get("OPENROUTER_MODEL")
        or DEFAULT_REPRESENTATIVE_MODEL
    )

"""Phase 3 lyric summarization experiments (sandbox, not part of the package)."""

from .config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_REPRESENTATIVE_MODEL,
    DEFAULT_SUMMARIZER_MODEL,
    VALID_SCORE_THRESHOLD,
    judge_model,
    openrouter_api_key,
    representative_model,
    summarizer_model,
)
from .llm_client import LLMError, OpenRouterClient
from .lyrics_source import LyricsError, LyricsSource
from .pipeline import (
    SummarizationPipeline,
    aggregate,
    clean_lyrics,
    era_label,
    extract_json,
    format_summary,
)

__all__ = [
    "DEFAULT_JUDGE_MODEL",
    "DEFAULT_REPRESENTATIVE_MODEL",
    "DEFAULT_SUMMARIZER_MODEL",
    "LLMError",
    "LyricsError",
    "LyricsSource",
    "OpenRouterClient",
    "SummarizationPipeline",
    "VALID_SCORE_THRESHOLD",
    "aggregate",
    "clean_lyrics",
    "era_label",
    "extract_json",
    "format_summary",
    "judge_model",
    "openrouter_api_key",
    "representative_model",
    "summarizer_model",
]

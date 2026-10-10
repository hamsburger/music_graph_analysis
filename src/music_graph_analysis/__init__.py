"""Music graph analysis package."""

from .analysis import ArtistAnalyzer, format_report
from .cache import JsonCache
from .config import DEFAULT_SUMMARIZER_MODEL, openrouter_api_key, summarizer_model
from .eras import (
    UNKNOWN_ERA,
    EraBounds,
    compute_era_bounds,
    parse_release_date,
    select_top_songs_per_era,
    song_pageviews,
)
from .genius import GeniusAPIError, GeniusClient
from .llm import LLMError, OpenRouterClient
from .lyrics import LyricsError, LyricsSource
from .summarize import (
    SongSummarizer,
    attach_summaries,
    clean_lyrics,
    extract_json,
)

__all__ = [
    "ArtistAnalyzer",
    "DEFAULT_SUMMARIZER_MODEL",
    "EraBounds",
    "GeniusAPIError",
    "GeniusClient",
    "JsonCache",
    "LLMError",
    "LyricsError",
    "LyricsSource",
    "OpenRouterClient",
    "SongSummarizer",
    "UNKNOWN_ERA",
    "attach_summaries",
    "clean_lyrics",
    "compute_era_bounds",
    "extract_json",
    "format_report",
    "openrouter_api_key",
    "parse_release_date",
    "select_top_songs_per_era",
    "song_pageviews",
    "summarizer_model",
]

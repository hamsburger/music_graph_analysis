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
from .images import ImageFetcher
from .llm import LLMError, OpenRouterClient
from .lyrics import LyricsError, LyricsSource
from .render import (
    DIMENSIONS,
    build_chart_svg,
    era_tag_counts,
    normalize_tags,
    render_html,
)
from .summarize import (
    SongSummarizer,
    attach_summaries,
    clean_lyrics,
    extract_json,
)

__all__ = [
    "ArtistAnalyzer",
    "DEFAULT_SUMMARIZER_MODEL",
    "DIMENSIONS",
    "EraBounds",
    "GeniusAPIError",
    "GeniusClient",
    "ImageFetcher",
    "JsonCache",
    "LLMError",
    "LyricsError",
    "LyricsSource",
    "OpenRouterClient",
    "SongSummarizer",
    "UNKNOWN_ERA",
    "attach_summaries",
    "build_chart_svg",
    "clean_lyrics",
    "compute_era_bounds",
    "era_tag_counts",
    "extract_json",
    "format_report",
    "normalize_tags",
    "openrouter_api_key",
    "parse_release_date",
    "render_html",
    "select_top_songs_per_era",
    "song_pageviews",
    "summarizer_model",
]

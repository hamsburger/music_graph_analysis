"""Music graph analysis package."""

from .analysis import ArtistAnalyzer, format_report
from .cache import JsonCache
from .eras import (
    UNKNOWN_ERA,
    EraBounds,
    compute_era_bounds,
    parse_release_date,
    select_top_songs_per_era,
    song_pageviews,
)
from .genius import GeniusAPIError, GeniusClient

__all__ = [
    "ArtistAnalyzer",
    "EraBounds",
    "GeniusAPIError",
    "GeniusClient",
    "JsonCache",
    "UNKNOWN_ERA",
    "compute_era_bounds",
    "format_report",
    "parse_release_date",
    "select_top_songs_per_era",
    "song_pageviews",
]

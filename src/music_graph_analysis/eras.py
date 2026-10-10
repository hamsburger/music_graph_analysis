"""Era bucketing logic for artist discographies.

Songs are grouped into a fixed number of equal time-length "era" buckets
spanning the artist's first and last release. Songs without a usable release
date are collected into an ``unknown`` bucket so they are never silently lost.

This module is pure: it operates on Genius song dictionaries but performs no
network or file I/O, which keeps it easy to unit test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

UNKNOWN_ERA = "unknown"

MIN_YEAR = 1900


@dataclass(frozen=True)
class EraBounds:
    """Equal-length era boundaries across ``[start, end]``."""

    start: datetime
    end: datetime
    n: int

    @property
    def width(self) -> timedelta:
        if self.n <= 0:
            return timedelta(0)
        return (self.end - self.start) / self.n

    def interval(self, index: int) -> tuple[datetime, datetime]:
        """Return the ``(start, end)`` datetimes for era ``index``."""
        start = self.start + self.width * index
        if index == self.n - 1:
            end = self.end
        else:
            end = self.start + self.width * (index + 1)
        return start, end

    def assign(self, when: datetime | None) -> int | str:
        """Return the era index for ``when``, or ``UNKNOWN_ERA`` if undated."""
        if when is None:
            return UNKNOWN_ERA
        if self.n <= 0 or self.end <= self.start:
            return 0
        offset = (when - self.start).total_seconds()
        span = (self.end - self.start).total_seconds()
        index = int(offset / span * self.n)
        return max(0, min(index, self.n - 1))


def parse_release_date(song: dict[str, Any]) -> datetime | None:
    """Extract a ``datetime`` from a Genius song's release metadata.

    Reads ``release_date_components`` (preferred) or falls back to the
    ``release_date`` string. Returns ``None`` when no usable date exists.
    """
    components = song.get("release_date_components")
    if isinstance(components, dict):
        year = components.get("year")
        if year:
            month = components.get("month") or 1
            day = components.get("day") or 1
            try:
                return datetime(int(year), int(month), int(day))
            except (TypeError, ValueError):
                return None

    raw = song.get("release_date")
    if isinstance(raw, str) and raw.strip():
        candidate = raw.strip()
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            try:
                return datetime.strptime(candidate[:4], "%Y")
            except ValueError:
                return None
    return None


def song_pageviews(song: dict[str, Any]) -> int:
    """Return the song's pageview count, defaulting to ``0``."""
    stats = song.get("stats") or {}
    value = stats.get("pageviews")
    return int(value) if isinstance(value, (int, float)) else 0


def compute_era_bounds(
    dates: Iterable[datetime | None], n: int = 5
) -> EraBounds | None:
    """Compute equal-length era bounds from a collection of release dates.

    Returns ``None`` when there are no usable dates at all.
    """
    usable = [d for d in dates if d is not None]
    if not usable:
        return None
    return EraBounds(start=min(usable), end=max(usable), n=n)


def select_top_songs_per_era(
    songs: Iterable[dict[str, Any]],
    bounds: EraBounds | None,
    top_k: int = 5,
) -> dict[int | str, list[dict[str, Any]]]:
    """Group songs into eras and keep the ``top_k`` most popular in each.

    Popularity is measured by ``stats.pageviews`` (descending), with the song
    title as a tie-breaker so results are deterministic. The returned mapping
    always contains the ``unknown`` key (possibly empty) so callers can rely
    on its presence.
    """
    grouped: dict[int | str, list[dict[str, Any]]] = {UNKNOWN_ERA: []}
    if bounds is not None:
        for index in range(bounds.n):
            grouped[index] = []

    for song in songs:
        when = parse_release_date(song) if bounds is not None else None
        era = bounds.assign(when) if bounds is not None else UNKNOWN_ERA
        grouped.setdefault(era, []).append(song)

    for era, era_songs in grouped.items():
        era_songs.sort(
            key=lambda s: (-song_pageviews(s), (s.get("title") or "").casefold())
        )
        grouped[era] = era_songs[:top_k]

    return grouped

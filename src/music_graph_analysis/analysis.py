"""Orchestrate artist era analysis on top of the Genius client.

Workflow for a given artist:

1. Resolve the artist by exact name match.
2. Pull their full discography (primary-artist songs only).
3. Split the release-date range into equal-length era buckets.
4. Keep the most popular songs in each era (plus an ``unknown`` bucket).
5. For each selected song, fetch who sampled it and aggregate the results.

Network access is funnelled through :class:`ArtistAnalyzer`, which optionally
caches responses via :class:`~music_graph_analysis.cache.JsonCache`.
"""

from __future__ import annotations

from typing import Any, Callable

from .cache import JsonCache
from .eras import (
    UNKNOWN_ERA,
    compute_era_bounds,
    parse_release_date,
    select_top_songs_per_era,
    song_pageviews,
)
from .genius import (
    RELATIONSHIP_INTERPOLATED_BY,
    RELATIONSHIP_INTERPOLATES,
    RELATIONSHIP_SAMPLES,
    RELATIONSHIP_SAMPLED_IN,
    GeniusClient,
    GeniusAPIError,
)
from .naming import artist_folder


def _primary_artist_id(song: dict[str, Any]) -> int | None:
    artist = song.get("primary_artist") or {}
    return artist.get("id")


def _artist_folder(artist_name: str | None, artist_id: int) -> str:
    return artist_folder(artist_name, artist_id)


def _date_label(song: dict[str, Any]) -> str | None:
    values = song.get("release_date_components") or {}
    year = values.get("year")
    if not year:
        return song.get("release_date_for_display")
    month = values.get("month")
    day = values.get("day")
    if month and day:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{year:04d}"


def _related_song(song: dict[str, Any]) -> dict[str, Any]:
    """Normalise a related song into the fields used across the report."""
    return {
        "id": song.get("id"),
        "title": song.get("title"),
        "artist": song.get("artist_names")
        or (song.get("primary_artist") or {}).get("name"),
        "release_date": _date_label(song),
    }


class ArtistAnalyzer:
    """Analyse how often an artist's era-defining songs were sampled."""

    def __init__(
        self,
        client: GeniusClient,
        *,
        cache: JsonCache | None = None,
    ) -> None:
        self.client = client
        self.cache = cache

    def _cached(self, key: str, fetch: Callable[[], Any]) -> Any:
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        value = fetch()
        if self.cache is not None:
            self.cache.set(key, value)
        return value

    def discography(
        self, artist_id: int, artist_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Return (and cache) every song for ``artist_id``."""
        return self._cached(
            f"{_artist_folder(artist_name, artist_id)}/discography",
            lambda: list(self.client.iter_artist_songs(artist_id)),
        )

    def relationships(
        self,
        song_id: int,
        *,
        artist_id: int | None = None,
        artist_name: str | None = None,
        song_title: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return (and cache) all sample/interpolation relationships for a song.

        Fetches a single ``GET /songs/{id}`` and groups the result by
        relationship type (``samples``, ``sampled_in``, ``interpolates`` and
        ``interpolated_by``). When artist context is supplied the response is
        nested under a per-artist folder, otherwise it falls back to a shared
        ``songs`` folder.
        """
        folder = _artist_folder(artist_name, artist_id) if artist_id else "songs"
        label = f"{song_title}-{song_id}" if song_title else f"song-{song_id}"
        return self._cached(
            f"{folder}/relationships/{label}",
            lambda: self.client.get_all_relationships(song_id),
        )

    def sampled_in(
        self,
        song_id: int,
        *,
        artist_id: int | None = None,
        artist_name: str | None = None,
        song_title: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return (and cache) the songs that sampled ``song_id``."""
        relations = self.relationships(
            song_id,
            artist_id=artist_id,
            artist_name=artist_name,
            song_title=song_title,
        )
        return relations.get(RELATIONSHIP_SAMPLED_IN, [])

    def analyze(
        self,
        name: str,
        *,
        n_eras: int = 5,
        top_k: int = 5,
        include_unknown: bool = True,
    ) -> dict[str, Any]:
        """Run the full era analysis for the artist called ``name``."""
        artist = self.client.find_artist(name)
        if artist is None:
            raise GeniusAPIError(f"No Genius artist directly matching {name!r}")
        artist_id = artist["id"]

        discography = self.discography(artist_id, artist.get("name"))
        own_songs = [s for s in discography if _primary_artist_id(s) == artist_id]

        bounds = compute_era_bounds(
            (parse_release_date(s) for s in own_songs), n=n_eras
        )
        grouped = select_top_songs_per_era(own_songs, bounds, top_k)

        result: dict[str, Any] = {
            "artist": {
                "id": artist_id,
                "name": artist.get("name"),
                "url": artist.get("url"),
            },
            "span": None,
            "eras": [],
        }
        if bounds is not None:
            result["span"] = {
                "start": bounds.start.date().isoformat(),
                "end": bounds.end.date().isoformat(),
                "n_eras": bounds.n,
            }

        ordered_eras: list[int | str] = []
        if bounds is not None:
            ordered_eras.extend(range(bounds.n))
        if include_unknown and grouped.get(UNKNOWN_ERA):
            ordered_eras.append(UNKNOWN_ERA)

        for era in ordered_eras:
            result["eras"].append(
                self._build_era(era, grouped.get(era, []), bounds, artist)
            )

        return result

    def _build_era(
        self,
        era: int | str,
        songs: list[dict[str, Any]],
        bounds: Any,
        artist: dict[str, Any],
    ) -> dict[str, Any]:
        if era == UNKNOWN_ERA or bounds is None:
            label = "Unknown era (no release date)"
            start = end = None
        else:
            interval_start, interval_end = bounds.interval(era)
            start = interval_start.date().isoformat()
            end = interval_end.date().isoformat()
            label = f"Era {era + 1} ({start} to {end})"

        era_songs = []
        for song in songs:
            relations = self.relationships(
                song["id"],
                artist_id=artist.get("id"),
                artist_name=artist.get("name"),
                song_title=song.get("title"),
            )
            sampled_in = relations.get(RELATIONSHIP_SAMPLED_IN, [])
            era_songs.append(
                {
                    "id": song["id"],
                    "title": song.get("title"),
                    "artist_names": song.get("artist_names"),
                    "release_date": _date_label(song),
                    "pageviews": song_pageviews(song),
                    "sample_count": len(sampled_in),
                    "sampled_by": [_related_song(s) for s in sampled_in],
                    "samples": [
                        _related_song(s)
                        for s in relations.get(RELATIONSHIP_SAMPLES, [])
                    ],
                    "interpolates": [
                        _related_song(s)
                        for s in relations.get(RELATIONSHIP_INTERPOLATES, [])
                    ],
                    "interpolated_by": [
                        _related_song(s)
                        for s in relations.get(RELATIONSHIP_INTERPOLATED_BY, [])
                    ],
                    "inspired_by": [
                        _related_song(s)
                        for s in relations.get(RELATIONSHIP_SAMPLES, [])
                    ]
                    + [
                        _related_song(s)
                        for s in relations.get(RELATIONSHIP_INTERPOLATES, [])
                    ],
                }
            )

        totals = {
            RELATIONSHIP_SAMPLES: sum(len(s["samples"]) for s in era_songs),
            RELATIONSHIP_SAMPLED_IN: sum(len(s["sampled_by"]) for s in era_songs),
            RELATIONSHIP_INTERPOLATES: sum(
                len(s["interpolates"]) for s in era_songs
            ),
            RELATIONSHIP_INTERPOLATED_BY: sum(
                len(s["interpolated_by"]) for s in era_songs
            ),
        }

        return {
            "era": era,
            "label": label,
            "start": start,
            "end": end,
            "total_samples": totals[RELATIONSHIP_SAMPLED_IN],
            "totals": totals,
            "songs": era_songs,
        }


def format_report(result: dict[str, Any]) -> str:
    """Render an analysis result as a readable console summary."""
    artist = result["artist"]
    lines = [f"Artist: {artist.get('name')} (id {artist.get('id')})"]
    span = result.get("span")
    if span:
        lines.append(
            f"Career span: {span['start']} to {span['end']} "
            f"across {span['n_eras']} eras"
        )
    lines.append("")

    for era in result["eras"]:
        lines.append(f"{era['label']}  [total samples: {era['total_samples']}]")
        if not era["songs"]:
            lines.append("  (no songs)")
        for song in era["songs"]:
            parts = [f"sampled {song['sample_count']}x"]
            if song["interpolated_by"]:
                parts.append(f"interpolated {len(song['interpolated_by'])}x")
            if song["samples"]:
                parts.append(f"sampled from {len(song['samples'])}")
            if song["interpolates"]:
                parts.append(f"interpolates {len(song['interpolates'])}")
            lines.append(
                f"  - {song['title']} "
                f"({song['release_date']}, {song['pageviews']:,} views) "
                + ", ".join(parts)
            )
            for source in song["inspired_by"][:5]:
                lines.append(
                    f"      < inspired by {source['title']} "
                    f"({source['artist']}, {source['release_date']})"
                )
            artists: dict[str, int] = {}
            for sampler in song["sampled_by"]:
                key = sampler.get("artist") or "Unknown"
                artists[key] = artists.get(key, 0) + 1
            for sampler_artist, count in sorted(
                artists.items(), key=lambda kv: (-kv[1], kv[0].casefold())
            )[:5]:
                lines.append(f"      • {sampler_artist} ({count})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"

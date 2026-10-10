"""Fetch song lyrics via ``lyricsgenius`` and cache them per artist.

The Genius API does not return lyrics, so this wraps the unofficial
``lyricsgenius`` scraper (which itself uses the Genius API to resolve a song URL
and then scrapes the page). ``lyricsgenius`` is imported lazily so importing
this module never triggers network access.
"""

from __future__ import annotations

import os
from typing import Any

from music_graph_analysis.cache import JsonCache

from .naming import artist_folder, song_label


class LyricsError(RuntimeError):
    """Raised when lyrics cannot be fetched."""


class LyricsSource:
    """Fetch lyrics by song ID, caching the raw result under the artist folder."""

    def __init__(
        self,
        access_token: str | None = None,
        *,
        cache: JsonCache | None = None,
        sleep_time: float = 0.5,
        remove_section_headers: bool = False,
    ) -> None:
        self.access_token = access_token or os.environ.get("GENIUS_ACCESS_TOKEN")
        self.cache = cache
        self.sleep_time = sleep_time
        self.remove_section_headers = remove_section_headers
        self._genius: Any = None

    @property
    def genius(self) -> Any:
        """Lazily construct the ``lyricsgenius.Genius`` client."""
        if self._genius is None:
            if not self.access_token:
                raise LyricsError(
                    "No Genius access token provided. Set GENIUS_ACCESS_TOKEN "
                    "or pass access_token=..."
                )
            from lyricsgenius import Genius

            self._genius = Genius(
                self.access_token,
                sleep_time=self.sleep_time,
                verbose=False,
                remove_section_headers=self.remove_section_headers,
            )
        return self._genius

    def get_lyrics(
        self,
        song_id: int,
        *,
        artist_id: int | None = None,
        artist_name: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Return ``{song_id, title, lyrics}`` for ``song_id`` (cached).

        ``lyrics`` is an empty string when the scraper finds nothing.
        """
        folder = artist_folder(artist_name, artist_id)
        key = f"{folder}/lyrics/{song_label(title, song_id)}"

        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return hit

        raw = self.genius.lyrics(song_id=song_id)
        record = {
            "song_id": song_id,
            "title": title,
            "artist": artist_name,
            "lyrics": raw or "",
        }
        if self.cache is not None:
            self.cache.set(key, record)
        return record

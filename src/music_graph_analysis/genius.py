"""Minimal client for the Genius API (https://api.genius.com).

Only the endpoints needed for graph analysis are implemented so far:
``GET /songs/{id}``, ``GET /search`` and ``GET /artists/{id}/songs``.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterator

import requests

GENIUS_API_BASE_URL = "https://api.genius.com"

# ``GET /artists/{id}/songs`` rejects ``per_page`` values above 50.
MAX_PER_PAGE = 50

# Relationship types exposed by ``song.song_relationships``.
# ``samples``/``interpolates`` describe what a song drew from; the
# ``*_in``/``*_by`` variants describe the songs that drew from it.
RELATIONSHIP_SAMPLES = "samples"
RELATIONSHIP_SAMPLED_IN = "sampled_in"
RELATIONSHIP_INTERPOLATES = "interpolates"
RELATIONSHIP_INTERPOLATED_BY = "interpolated_by"
RELATIONSHIP_TYPES = (
    RELATIONSHIP_SAMPLES,
    RELATIONSHIP_SAMPLED_IN,
    RELATIONSHIP_INTERPOLATES,
    RELATIONSHIP_INTERPOLATED_BY,
)


class GeniusAPIError(RuntimeError):
    """Raised when the Genius API returns a non-success response."""


class GeniusClient:
    """Thin wrapper around the Genius REST API.

    Parameters
    ----------
    access_token:
        A Genius API access token. If omitted, it is read from the
        ``GENIUS_ACCESS_TOKEN`` environment variable.
    base_url:
        Base URL of the API. Override mainly for testing.
    timeout:
        Request timeout in seconds.
    max_retries:
        Number of attempts for transient failures (timeouts, 429, 5xx).
    backoff:
        Base seconds for exponential backoff between retries.
    min_interval:
        Minimum seconds between consecutive requests (client-side throttle).
        Defaults to ``0`` so tests and callers can opt in explicitly.
    """

    def __init__(
        self,
        access_token: str | None = None,
        base_url: str = GENIUS_API_BASE_URL,
        timeout: float = 10.0,
        *,
        max_retries: int = 3,
        backoff: float = 1.0,
        min_interval: float = 0.0,
    ) -> None:
        token = access_token or os.environ.get("GENIUS_ACCESS_TOKEN")
        if not token:
            raise GeniusAPIError(
                "No Genius access token provided. Set GENIUS_ACCESS_TOKEN "
                "or pass access_token=..."
            )
        self.access_token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.backoff = backoff
        self.min_interval = min_interval
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self.min_interval <= 0 or self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            self._throttle()
            try:
                response = requests.get(
                    url, headers=headers, params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_error = exc
            else:
                self._last_request_at = time.monotonic()

                try:
                    payload = response.json()
                except ValueError as exc:  # pragma: no cover - defensive
                    raise GeniusAPIError(
                        "Genius API returned non-JSON response "
                        f"({response.status_code})"
                    ) from exc

                if response.status_code == 200 and "response" in payload:
                    return payload["response"]

                # Retry transient server/rate-limit errors, fail fast otherwise.
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = GeniusAPIError(
                        f"Genius API error {response.status_code} for {path}"
                    )
                else:
                    message = payload.get("meta", {}).get("message", response.text)
                    raise GeniusAPIError(
                        f"Genius API error {response.status_code} for {path}: {message}"
                    )

            if attempt < self.max_retries - 1:
                time.sleep(self.backoff * (2**attempt))

        raise GeniusAPIError(
            f"Genius API request failed for {path} after "
            f"{self.max_retries} attempts: {last_error}"
        ) from last_error

    def get_song(self, song_id: int) -> dict[str, Any]:
        """Call ``GET /songs/{song_id}`` and return the ``response`` body."""
        return self._get(f"/songs/{song_id}")

    def get_song_detail(self, song_id: int) -> dict[str, Any]:
        """Return the ``song`` object from ``GET /songs/{song_id}``."""
        body = self.get_song(song_id)
        return body.get("song", body)

    def get_relationships(
        self, song_id: int, relationship_type: str = RELATIONSHIP_SAMPLED_IN
    ) -> list[dict[str, Any]]:
        """Return related songs of ``relationship_type`` for ``song_id``.

        Uses ``GET /songs/{id}`` and reads the ``song_relationships`` list. The
        default returns the songs that **sampled** the given song
        (``sampled_in``). Returns an empty list when there are none.
        """
        song = self.get_song_detail(song_id)
        for relationship in song.get("song_relationships", []):
            if (
                relationship.get("type") == relationship_type
                or relationship.get("relationship_type") == relationship_type
            ):
                return relationship.get("songs", [])
        return []

    def get_all_relationships(
        self,
        song_id: int,
        relationship_types: tuple[str, ...] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return every requested relationship type for ``song_id``.

        Fetches ``GET /songs/{id}`` once and groups the ``song_relationships``
        entries by type. The result maps each requested type to its list of
        songs, defaulting to an empty list when the relationship is absent.
        """
        types = relationship_types or RELATIONSHIP_TYPES
        result: dict[str, list[dict[str, Any]]] = {t: [] for t in types}
        song = self.get_song_detail(song_id)
        for relationship in song.get("song_relationships", []):
            rtype = relationship.get("type") or relationship.get("relationship_type")
            if rtype in result:
                result[rtype].extend(relationship.get("songs") or [])
        return result

    def get_sampled_in(self, song_id: int) -> list[dict[str, Any]]:
        """Return the songs that sampled the song with ``song_id``."""
        return self.get_relationships(song_id, RELATIONSHIP_SAMPLED_IN)

    def get_samples(self, song_id: int) -> list[dict[str, Any]]:
        """Return the songs that the song with ``song_id`` sampled."""
        return self.get_relationships(song_id, RELATIONSHIP_SAMPLES)

    def get_interpolates(self, song_id: int) -> list[dict[str, Any]]:
        """Return the songs that the song with ``song_id`` interpolated."""
        return self.get_relationships(song_id, RELATIONSHIP_INTERPOLATES)

    def get_interpolated_by(self, song_id: int) -> list[dict[str, Any]]:
        """Return the songs that interpolated the song with ``song_id``."""
        return self.get_relationships(song_id, RELATIONSHIP_INTERPOLATED_BY)

    def search(self, query: str) -> dict[str, Any]:
        """Call ``GET /search`` and return the ``response`` body."""
        return self._get("/search", params={"q": query})

    def find_artist(
        self, name: str, *, case_sensitive: bool = False
    ) -> dict[str, Any] | None:
        """Find the artist whose name directly matches ``name``.

        Uses ``GET /search`` and scans the returned hits for a
        ``primary_artist`` whose name matches the input exactly (after
        stripping surrounding whitespace). Returns the matching artist
        object, or ``None`` when no direct match is found.
        """
        response = self.search(name)
        target = name.strip()
        if not case_sensitive:
            target = target.casefold()

        for hit in response.get("hits", []):
            artist = hit.get("result", {}).get("primary_artist", {})
            artist_name = artist.get("name", "").strip()
            if not artist_name:
                continue
            candidate = artist_name if case_sensitive else artist_name.casefold()
            if candidate == target:
                return artist
        return None

    def get_artist_songs(
        self,
        artist_id: int,
        *,
        sort: str = "popularity",
        per_page: int = 20,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Call ``GET /artists/{id}/songs`` and return the songs list.

        Defaults retrieve the artist's most popular songs.
        """
        response = self._get(
            f"/artists/{artist_id}/songs",
            params={"sort": sort, "per_page": per_page, "page": page},
        )
        return response.get("songs", [])

    def iter_artist_songs(
        self,
        artist_id: int,
        *,
        sort: str = "popularity",
        per_page: int = MAX_PER_PAGE,
    ) -> Iterator[dict[str, Any]]:
        """Yield every song for an artist, paging until the API runs out.

        ``per_page`` is clamped to :data:`MAX_PER_PAGE`. Paging stops when a
        page is empty or returns fewer than ``per_page`` songs.
        """
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        page = 1
        while True:
            songs = self.get_artist_songs(
                artist_id, sort=sort, per_page=per_page, page=page
            )
            if not songs:
                return
            yield from songs
            if len(songs) < per_page:
                return
            page += 1

    def get_artist_top_songs(
        self, name: str, *, limit: int = 20, case_sensitive: bool = False
    ) -> list[dict[str, Any]]:
        """Return the most popular songs for the artist called ``name``.

        Looks the artist up via :meth:`find_artist` (requiring a direct
        name match) and then fetches their top songs via
        :meth:`get_artist_songs`.
        """
        artist = self.find_artist(name, case_sensitive=case_sensitive)
        if artist is None:
            raise GeniusAPIError(f"No Genius artist directly matching {name!r}")
        return self.get_artist_songs(artist["id"], per_page=limit)

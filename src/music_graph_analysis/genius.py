"""Minimal client for the Genius API (https://api.genius.com).

Only the endpoints needed for graph analysis are implemented so far:
``GET /songs/{id}``, ``GET /search`` and ``GET /artists/{id}/songs``.
"""

from __future__ import annotations

import os
from typing import Any

import requests

GENIUS_API_BASE_URL = "https://api.genius.com"


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
    """

    def __init__(
        self,
        access_token: str | None = None,
        base_url: str = GENIUS_API_BASE_URL,
        timeout: float = 10.0,
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

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.get(
            url, headers=headers, params=params, timeout=self.timeout
        )
        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            raise GeniusAPIError(
                f"Genius API returned non-JSON response ({response.status_code})"
            ) from exc

        if response.status_code != 200 or "response" not in payload:
            message = payload.get("meta", {}).get("message", response.text)
            raise GeniusAPIError(
                f"Genius API error {response.status_code} for {path}: {message}"
            )
        return payload["response"]

    def get_song(self, song_id: int) -> dict[str, Any]:
        """Call ``GET /songs/{song_id}`` and return the ``response`` body."""
        return self._get(f"/songs/{song_id}")

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

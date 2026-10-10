"""Fetch album art and inline it as base64 ``data:`` URIs.

This is the only render-related module that touches the network. It downloads
the small (300x300) Genius thumbnail for a song and base64-encodes it so the
generated HTML stays self-contained. Results are cached via
:class:`~music_graph_analysis.cache.JsonCache`, so repeated renders do not
re-hit ``images.genius.com``.
"""

from __future__ import annotations

import base64
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from .cache import JsonCache
from .naming import artist_folder, song_label

DEFAULT_TIMEOUT = 20.0

_EXTENSION_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}


def _guess_content_type(url: str) -> str:
    extension = urlparse(url).path.rsplit(".", 1)[-1].lower()
    return _EXTENSION_TYPES.get(extension, "image/png")


class ImageFetcher:
    """Download images and return them as ``data:`` URIs (optionally cached)."""

    def __init__(
        self,
        *,
        cache: JsonCache | None = None,
        fetch: Callable[..., Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.cache = cache
        self._fetch = fetch or requests.get
        self.timeout = timeout

    def data_uri(
        self,
        url: str,
        *,
        artist_id: int | None = None,
        artist_name: str | None = None,
        song_id: int | None = None,
        title: str | None = None,
    ) -> str:
        """Return ``url`` as a base64 data URI, caching by song when possible."""
        key = None
        if song_id is not None:
            folder = artist_folder(artist_name, artist_id)
            key = f"{folder}/images/{song_label(title, song_id)}"
            if self.cache is not None:
                hit = self.cache.get(key)
                if hit and hit.get("data_uri"):
                    return hit["data_uri"]

        response = self._fetch(url, timeout=self.timeout)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()

        content_type = ""
        headers = getattr(response, "headers", None) or {}
        content_type = (headers.get("Content-Type") or "").split(";")[0].strip()
        if not content_type.startswith("image/"):
            content_type = _guess_content_type(url)

        encoded = base64.b64encode(response.content).decode("ascii")
        data_uri = f"data:{content_type};base64,{encoded}"

        if key is not None and self.cache is not None:
            self.cache.set(key, {"url": url, "data_uri": data_uri})
        return data_uri

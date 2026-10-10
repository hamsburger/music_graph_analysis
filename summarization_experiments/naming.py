"""Shared helpers for building cache keys and result paths.

Kept dependency-free so both the lyrics source and the pipeline can use them
without importing each other.
"""

from __future__ import annotations

import hashlib


def content_hash(text: str, *, length: int = 12) -> str:
    """Return a short, stable hex digest of ``text`` for use in cache keys."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def artist_folder(artist_name: str | None, artist_id: int | None) -> str:
    """Return the per-artist folder label used across caches and results."""
    if artist_id:
        return f"{artist_name}-{artist_id}" if artist_name else f"artist-{artist_id}"
    return "songs"


def song_label(title: str | None, song_id: int) -> str:
    """Return a human-readable, cache-key-safe label for a song."""
    return f"{title}-{song_id}" if title else f"song-{song_id}"


def model_slug(model: str) -> str:
    """Turn a model slug (e.g. ``deepseek/deepseek-chat``) into one path segment."""
    return model.replace("/", "-")

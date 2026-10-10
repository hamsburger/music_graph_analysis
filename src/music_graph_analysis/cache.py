"""A tiny JSON file cache for API responses.

Keeps re-runs fast and avoids hammering the Genius API during development.

Keys are treated as human-readable, slash-separated paths so the cache is easy
to browse. Each segment is slugified into a filesystem-safe name, e.g.::

    "kanye-west-123/discography"
    "kanye-west-123/sampled-in/stronger-456"

maps to::

    data/cache/kanye-west-123/discography.json
    data/cache/kanye-west-123/sampled-in/stronger-456.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_CACHE_DIR = Path("data") / "cache"

_SLUG_SEPARATORS = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Turn arbitrary text into a lowercase, filesystem-safe slug.

    Falls back to ``"unnamed"`` when the input contains no usable characters.
    """
    slug = _SLUG_SEPARATORS.sub("-", str(value).casefold()).strip("-")
    return slug or "unnamed"


class JsonCache:
    """Persist JSON-serialisable values under ``root`` keyed by a path string."""

    def __init__(self, root: str | Path = DEFAULT_CACHE_DIR) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        segments = [slugify(part) for part in key.split("/") if part.strip()]
        if not segments:
            segments = ["unnamed"]
        return self.root.joinpath(*segments[:-1], f"{segments[-1]}.json")

    def get(self, key: str) -> Any | None:
        """Return the cached value for ``key`` or ``None`` on a miss."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` for ``key``, creating parent directories if needed."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        tmp.replace(path)

    def clear(self) -> None:
        """Delete every cached file and the directories that held them."""
        if not self.root.exists():
            return
        for path in self.root.glob("**/*.json"):
            path.unlink()
        for directory in sorted(
            (p for p in self.root.glob("**/*") if p.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass

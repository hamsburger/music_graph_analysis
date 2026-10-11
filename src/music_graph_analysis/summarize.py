"""Summarize a song's lyrics with an LLM and attach the result to the report.

This is the productionised slice of the Phase 3 sandbox: lyrics are fetched via
:class:`~music_graph_analysis.lyrics.LyricsSource`, cleaned, sent through
:class:`~music_graph_analysis.llm.OpenRouterClient` using the ``summarize``
prompt, and the parsed summary dict is attached to each song. It also hosts the
per-era representative selection stage: the era's song tags are read at once and
an LLM picks the most representative ``themes`` and ``emotional_tone``. The judge
stage stays in the sandbox.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from .config import (
    DEFAULT_PROMPTS_DIR,
    DEFAULT_REPRESENTATIVE_MODEL,
    DEFAULT_SUMMARIZER_MODEL,
    MAX_REPRESENTATIVES,
)
from .llm import LLMError
from .lyrics import LyricsError
from .naming import artist_folder, content_hash, model_slug, song_label
from .render import normalize_tags
from . import prompts

# Lyrics states that carry no usable content.
_EMPTY_LYRICS_MARKERS = ("[editing]",)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def clean_lyrics(raw: str | None) -> str | None:
    """Return usable lyrics text, or ``None`` when there is nothing to summarise.

    Strips ``[editing]`` markers and rejects empty, editing-only, and
    snippet-only lyrics.
    """
    text = (raw or "").strip()
    if not text:
        return None
    for marker in _EMPTY_LYRICS_MARKERS:
        text = text.replace(marker, "")
    text = text.strip()
    if not text:
        return None
    if text.startswith("[Snippet]"):
        return None
    return text


def extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object found in ``text``.

    Tolerates markdown code fences and surrounding prose by falling back to the
    span between the first ``{`` and the last ``}``.
    """
    candidate = text.strip()
    fence = _FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()

    try:
        parsed = json.loads(candidate)
    except ValueError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")
        parsed = json.loads(candidate[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON is not an object")
    return parsed


def _era_songs_payload(songs: list[dict[str, Any]]) -> str:
    """Render each song's cleaned themes/tone labels as prompt input lines."""
    lines: list[str] = []
    for song in songs:
        summary = song.get("summary") or {}
        themes = normalize_tags(summary, "themes")
        tones = normalize_tags(summary, "emotional_tone")
        title = song.get("title") or "Untitled"
        lines.append(
            f"- {title}: themes=[{'; '.join(themes) or '—'}]; "
            f"tone=[{'; '.join(tones) or '—'}]"
        )
    return "\n".join(lines) if lines else "(no songs with usable tags)"


def _normalize_labels(value: Any) -> list[str]:
    """Coerce a raw LLM label field to a trimmed, de-duplicated, capped list."""
    if value is None:
        return []
    if isinstance(value, str):
        parts: list[str] = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = [str(part) for part in value]
    else:
        parts = [str(value)]

    labels: list[str] = []
    seen: set[str] = set()
    for part in parts:
        label = part.strip().strip("\"'").strip()
        if label and label.casefold() not in seen:
            seen.add(label.casefold())
            labels.append(label)
        if len(labels) >= MAX_REPRESENTATIVES:
            break
    return labels


def _normalize_representative(parsed: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw representative-selection response into a stable shape."""
    return {
        "themes": _normalize_labels(parsed.get("themes")),
        "emotional_tone": _normalize_labels(parsed.get("emotional_tone")),
        "reasoning": str(parsed.get("reasoning", "")).strip(),
    }


class SongSummarizer:
    """Summarize individual songs, with optional per-model/input caching."""

    def __init__(
        self,
        llm: Any,
        lyrics_source: Any,
        *,
        cache: Any = None,
        prompts_dir: Any = None,
        summarizer_model: str = DEFAULT_SUMMARIZER_MODEL,
        representative_model: str = DEFAULT_REPRESENTATIVE_MODEL,
    ) -> None:
        self.llm = llm
        self.lyrics_source = lyrics_source
        self.cache = cache
        self.prompts_dir = (
            prompts_dir if prompts_dir is not None else DEFAULT_PROMPTS_DIR
        )
        self.summarizer_model = summarizer_model
        self.representative_model = representative_model

    def _cached(self, key: str, fetch: Callable[[], Any]) -> Any:
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        value = fetch()
        if self.cache is not None:
            self.cache.set(key, value)
        return value

    def summarize(
        self,
        song_id: int,
        lyrics: str,
        *,
        artist_id: int | None = None,
        artist_name: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Produce a structured summary of ``lyrics`` (cached per model + input)."""
        folder = artist_folder(artist_name, artist_id)
        label = song_label(title, song_id)
        template = prompts.load_prompt(prompts.SUMMARIZE_PROMPT, self.prompts_dir)
        prompt = prompts.render(template, lyrics=lyrics)
        key = (
            f"{folder}/summaries/{label}-{model_slug(self.summarizer_model)}"
            f"-{content_hash(prompt)}"
        )

        def fetch() -> dict[str, Any]:
            response = self.llm.complete(prompt, model=self.summarizer_model)
            return extract_json(response)

        return self._cached(key, fetch)

    def summarize_song(
        self,
        song: dict[str, Any],
        *,
        artist_id: int | None = None,
        artist_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch lyrics for ``song`` and return its summary, or ``None`` if unusable."""
        song_id = song["id"]
        title = song.get("title")
        resolved_name = artist_name or song.get("artist") or song.get("artist_names")

        lyrics_record = self.lyrics_source.get_lyrics(
            song_id,
            artist_id=artist_id,
            artist_name=resolved_name,
            title=title,
        )
        lyrics = clean_lyrics(lyrics_record.get("lyrics"))
        if lyrics is None:
            return None

        return self.summarize(
            song_id,
            lyrics,
            artist_id=artist_id,
            artist_name=resolved_name,
            title=title,
        )

    def select_representative(
        self,
        songs: list[dict[str, Any]],
        *,
        era_label: str,
        era_index: int | None = None,
        artist_id: int | None = None,
        artist_name: str | None = None,
    ) -> dict[str, Any]:
        """Pick the era's most representative themes/tone (cached per model + input).

        ``songs`` are era song dicts that each carry a ``summary``. Only ``themes``
        and ``emotional_tone`` are considered; ``key_imagery`` is left to the
        renderer's frequency-based selection.
        """
        folder = artist_folder(artist_name, artist_id)
        template = prompts.load_prompt(
            prompts.REPRESENTATIVE_PROMPT, self.prompts_dir
        )
        prompt = prompts.render(
            template, era=era_label, songs=_era_songs_payload(songs)
        )
        index = era_index if era_index is not None else "x"
        key = (
            f"{folder}/representative/era-{index}"
            f"-{model_slug(self.representative_model)}-{content_hash(prompt)}"
        )

        def fetch() -> dict[str, Any]:
            response = self.llm.complete(prompt, model=self.representative_model)
            return _normalize_representative(extract_json(response))

        return self._cached(key, fetch)


def attach_summaries(
    result: dict[str, Any],
    summarizer: SongSummarizer,
    *,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Attach a ``summary`` dict to every song in an analysis ``result``.

    Songs with no usable lyrics (or that fail summarization) get
    ``summary: None`` so the shape is uniform. Errors never abort the run.
    """
    artist = result.get("artist", {})
    artist_id = artist.get("id")
    artist_name = artist.get("name")

    for era in result.get("eras", []):
        for song in era.get("songs", []):
            if log:
                log(f"Summarizing {song.get('title')} ({song.get('id')})...")
            try:
                song["summary"] = summarizer.summarize_song(
                    song, artist_id=artist_id, artist_name=artist_name
                )
            except (LLMError, LyricsError, ValueError) as exc:
                song["summary"] = None
                if log:
                    log(f"  skipped: {exc}")

    return result


def attach_representatives(
    result: dict[str, Any],
    summarizer: SongSummarizer,
    *,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Attach ``era["representative"]`` for every era with usable summaries.

    Best-effort: an era whose representative selection fails stores an
    ``{"error": "..."}`` dict instead of aborting the run. Eras with no usable
    song summaries are left untouched.
    """
    artist = result.get("artist", {})
    artist_id = artist.get("id")
    artist_name = artist.get("name")

    for index, era in enumerate(result.get("eras", [])):
        songs = [song for song in era.get("songs", []) if song.get("summary")]
        if not songs:
            continue
        label = era.get("label") or f"Era {index + 1}"
        if log:
            log(f"Selecting representative labels for {label}...")
        try:
            era["representative"] = summarizer.select_representative(
                songs,
                era_label=label,
                era_index=index,
                artist_id=artist_id,
                artist_name=artist_name,
            )
        except (LLMError, ValueError) as exc:
            era["representative"] = {"error": str(exc)}
            if log:
                log(f"  skipped: {exc}")

    return result

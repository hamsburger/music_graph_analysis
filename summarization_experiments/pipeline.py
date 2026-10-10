"""The summarization pipeline: lyrics -> LLM summary -> LLM judge.

The logic here is intentionally testable: all LLM and lyrics access is injected
via the ``llm`` and ``lyrics_source`` collaborators, so tests can pass fakes and
never touch the network.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

from music_graph_analysis.cache import JsonCache

from . import prompts
from .config import (
    DEFAULT_PROMPTS_DIR,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_SUMMARIZER_MODEL,
    VALID_SCORE_THRESHOLD,
)
from .naming import artist_folder, content_hash, model_slug, song_label

# Lyrics states that carry no usable content.
_EMPTY_LYRICS_MARKERS = ("[editing]",)


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


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


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


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


class SummarizationPipeline:
    """Run the summarize + judge loop for individual songs, with caching."""

    def __init__(
        self,
        llm: Any,
        lyrics_source: Any,
        *,
        cache: JsonCache | None = None,
        prompts_dir: Any = None, # TODO: This project needs better typing
        summarizer_model: str = DEFAULT_SUMMARIZER_MODEL,
        judge_model: str = DEFAULT_JUDGE_MODEL,
        valid_threshold: int = VALID_SCORE_THRESHOLD,
    ) -> None:
        self.llm = llm
        self.lyrics_source = lyrics_source
        self.cache = cache
        self.prompts_dir = prompts_dir if prompts_dir is not None else DEFAULT_PROMPTS_DIR
        self.summarizer_model = summarizer_model
        self.judge_model = judge_model
        self.valid_threshold = valid_threshold

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

    def judge(
        self,
        song_id: int,
        lyrics: str,
        summary: dict[str, Any],
        *,
        artist_id: int | None = None,
        artist_name: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Score ``summary`` against the original ``lyrics`` (cached per model + input)."""
        folder = artist_folder(artist_name, artist_id)
        label = song_label(title, song_id)
        template = prompts.load_prompt(prompts.JUDGE_PROMPT, self.prompts_dir)
        prompt = prompts.render(
            template,
            lyrics=lyrics,
            summary=json.dumps(summary, ensure_ascii=False, indent=2),
        )
        key = (
            f"{folder}/judge/{label}-{model_slug(self.judge_model)}"
            f"-{content_hash(prompt)}"
        )

        def fetch() -> dict[str, Any]:
            response = self.llm.complete(prompt, model=self.judge_model)
            parsed = extract_json(response)

            score = max(1, min(5, _as_int(parsed.get("score"), default=0)))
            grounded = _as_bool(parsed.get("grounded"))
            missing = parsed.get("missing_points") or []
            if not isinstance(missing, list):
                missing = [str(missing)]
            valid = grounded and score >= self.valid_threshold
            return {
                "score": score,
                "grounded": grounded,
                "missing_points": [str(point) for point in missing],
                "reasoning": str(parsed.get("reasoning", "")),
                "verdict": "valid" if valid else "invalid",
            }

        return self._cached(key, fetch)

    def process_song(self, song: dict[str, Any]) -> dict[str, Any]:
        """Run the full pipeline for a single song dict from a report."""
        song_id = song["id"]
        title = song.get("title")
        artist_name = song.get("artist") or song.get("artist_names")
        artist_id = song.get("artist_id")

        context = {
            "artist_id": artist_id,
            "artist_name": artist_name,
            "title": title,
        }

        lyrics_record = self.lyrics_source.get_lyrics(song_id, **context)
        lyrics = clean_lyrics(lyrics_record.get("lyrics"))

        base = {
            "song_id": song_id,
            "title": title,
            "artist": artist_name,
        }
        if lyrics is None:
            return {**base, "skipped": True, "reason": "no usable lyrics"}

        summary = self.summarize(song_id, lyrics, **context)
        judged = self.judge(song_id, lyrics, summary, **context)

        return {
            **base,
            "skipped": False,
            "lyrics_chars": len(lyrics),
            "summary": summary,
            "judge": judged,
            "meta": {
                "summarizer_model": self.summarizer_model,
                "judge_model": self.judge_model,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }


def aggregate(
    records: list[dict[str, Any]],
    *,
    valid_threshold: int = VALID_SCORE_THRESHOLD,
) -> dict[str, Any]:
    """Summarise a list of per-song records into run-level metrics."""
    processed = [r for r in records if not r.get("skipped") and "judge" in r]
    skipped = [r for r in records if r.get("skipped")]
    scores = [r["judge"]["score"] for r in processed]

    distribution = {str(n): 0 for n in range(1, 6)}
    for score in scores:
        distribution[str(score)] = distribution.get(str(score), 0) + 1

    valid = sum(1 for r in processed if r["judge"]["verdict"] == "valid")
    grounded = sum(1 for r in processed if r["judge"]["grounded"])

    return {
        "songs_total": len(records),
        "songs_processed": len(processed),
        "songs_skipped": len(skipped),
        "mean_score": round(sum(scores) / len(scores), 2) if scores else None,
        "pass_rate": round(valid / len(processed), 2) if processed else None,
        "grounded_rate": round(grounded / len(processed), 2) if processed else None,
        "score_distribution": distribution,
        "valid_threshold": valid_threshold,
    }


def format_summary(report: dict[str, Any]) -> str:
    """Render an aggregate report as a short console summary."""
    lines = [
        f"Songs: {report['songs_processed']} processed, "
        f"{report['songs_skipped']} skipped (of {report['songs_total']})",
    ]
    if report.get("mean_score") is not None:
        lines.append(
            f"Mean judge score: {report['mean_score']}/5 | "
            f"pass rate: {report['pass_rate']} | "
            f"grounded: {report['grounded_rate']}"
        )
        dist = ", ".join(
            f"{score}:{count}"
            for score, count in sorted(report["score_distribution"].items())
        )
        lines.append(f"Score distribution: {dist}")
    return "\n".join(lines)

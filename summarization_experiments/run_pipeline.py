"""CLI: run the lyric summarization + judge pipeline over an artist report.

Usage
-----
    python summarization_experiments/run_pipeline.py data/report/millkzy.json
        [--limit N] [--song-ids IDS] [--seed S]
        [--summarizer-model M] [--judge-model M]
        [--no-cache] [--cache-dir DIR] [--out DIR] [--min-interval SECONDS]

Reads a Phase 2 report, fetches each song's lyrics, summarizes them with an LLM,
scores the summary with a second LLM, and writes the combined per-song records to
a single ``results.json`` plus an aggregate report. Credentials come from
``.env`` (loaded automatically): ``GENIUS_ACCESS_TOKEN`` and
``OPENROUTER_API_KEY``.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

# Allow both ``python summarization_experiments/run_pipeline.py`` and
# ``python -m summarization_experiments.run_pipeline`` without requiring an
# editable install of either package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from dotenv import load_dotenv

from summarization_experiments import (
    LLMError,
    LyricsError,
    LyricsSource,
    OpenRouterClient,
    SummarizationPipeline,
    aggregate,
    format_summary,
)
from summarization_experiments.config import (
    DEFAULT_CACHE_DIR,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_RESULTS_DIR,
    DEFAULT_SUMMARIZER_MODEL,
    judge_model,
    openrouter_api_key,
    summarizer_model,
)
from summarization_experiments.naming import artist_folder
from music_graph_analysis.cache import JsonCache


def parse_song_ids(value: str) -> list[int]:
    """Parse a comma-separated list of song IDs (e.g. ``"1,2,3"``)."""
    try:
        return [int(part) for part in value.split(",") if part.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid comma-separated song IDs: {value!r}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Path to a Phase 2 report JSON")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Randomly sample at most this many songs",
    )
    parser.add_argument(
        "--song-ids",
        type=parse_song_ids,
        default=None,
        help="Process specific song IDs, comma-separated (e.g. 1,2,3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for the --limit random sample (default: nondeterministic)",
    )
    parser.add_argument(
        "--summarizer-model", default=None, help=f"Model (default: {DEFAULT_SUMMARIZER_MODEL})"
    )
    parser.add_argument(
        "--judge-model", default=None, help=f"Model (default: {DEFAULT_JUDGE_MODEL})"
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument(
        "--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Cache directory"
    )
    parser.add_argument(
        "--out", default=str(DEFAULT_RESULTS_DIR), help="Results directory"
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=0.0,
        help="Minimum seconds between LLM requests (default: 0)",
    )
    return parser


def load_songs(report: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Flatten a report into an artist dict and a de-duplicated song list."""
    artist = report.get("artist", {})
    songs: list[dict[str, Any]] = []
    seen: set[int] = set()
    for era in report.get("eras", []):
        for song in era.get("songs", []):
            song_id = song.get("id")
            if song_id is None or song_id in seen:
                continue
            seen.add(song_id)
            songs.append(
                {
                    "id": song_id,
                    "title": song.get("title"),
                    "artist_names": song.get("artist_names"),
                    "artist_id": artist.get("id"),
                    "artist": artist.get("name"),
                }
            )
    return artist, songs


def select_songs(
    songs: list[dict[str, Any]],
    *,
    song_ids: list[int] | None = None,
    limit: int | None = None,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Filter ``songs`` to explicit ``song_ids`` and/or a random sample of ``limit``.

    Sampling keeps the original report order and is reproducible when ``seed`` is
    given.
    """
    if song_ids:
        wanted = set(song_ids)
        songs = [s for s in songs if s["id"] in wanted]
    if limit is not None and 0 <= limit < len(songs):
        rng = random.Random(seed)
        indices = sorted(rng.sample(range(len(songs)), limit))
        songs = [songs[i] for i in indices]
    return songs


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    load_dotenv()

    if not openrouter_api_key():
        print(
            "Configuration error: OPENROUTER_API_KEY is not set (see .env.example)",
            file=sys.stderr,
        )
        return 2

    with open(args.report, "r", encoding="utf-8") as handle:
        report = json.load(handle)

    artist, songs = load_songs(report)
    songs = select_songs(
        songs, song_ids=args.song_ids, limit=args.limit, seed=args.seed
    )

    if not songs:
        print("No songs to process.", file=sys.stderr)
        return 1

    cache = None if args.no_cache else JsonCache(args.cache_dir)
    lyrics_source = LyricsSource(cache=cache)
    try:
        llm = OpenRouterClient(min_interval=args.min_interval)
    except LLMError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    pipeline = SummarizationPipeline(
        llm,
        lyrics_source,
        cache=cache,
        summarizer_model=args.summarizer_model or summarizer_model(),
        judge_model=args.judge_model or judge_model(),
    )

    out_dir = Path(args.out) / artist_folder(artist.get("name"), artist.get("id"))
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for song in songs:
        print(f"Processing {song['title']} ({song['id']})...", file=sys.stderr)
        try:
            record = pipeline.process_song(song)
        except (LLMError, LyricsError, ValueError) as exc:
            record = {
                "song_id": song["id"],
                "title": song["title"],
                "artist": song["artist"],
                "error": str(exc),
            }
        records.append(record)

    with (out_dir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump({"songs": records}, handle, ensure_ascii=False, indent=2)

    report_out = aggregate(records, valid_threshold=pipeline.valid_threshold)
    report_out["artist"] = {
        "id": artist.get("id"),
        "name": artist.get("name"),
    }
    with (out_dir / "report.json").open("w", encoding="utf-8") as handle:
        json.dump(report_out, handle, ensure_ascii=False, indent=2)

    print(format_summary(report_out))
    print(f"Wrote results to {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

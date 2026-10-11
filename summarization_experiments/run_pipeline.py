"""CLI: run the lyric summarization + judge pipeline over an artist report.

Usage
-----
    python summarization_experiments/run_pipeline.py data/report/millkzy.json
        [--limit N] [--song-ids IDS] [--seed S]
        [--summarizer-model M] [--judge-model M] [--representative-model M]
        [--skip-representatives]
        [--no-cache] [--cache-dir DIR] [--out DIR] [--min-interval SECONDS]

Reads a Phase 2 report, fetches each song's lyrics, summarizes them with an LLM,
scores the summary with a second LLM, then selects the most representative
themes and emotional tone for each era with a third LLM call. Writes the combined
per-song records to a single ``results.json`` plus an aggregate report, and an
augmented ``report_enriched.json`` (input schema + song summaries + per-era
``representative``) for the renderer. Credentials come from ``.env`` (loaded
automatically): ``GENIUS_ACCESS_TOKEN`` and ``OPENROUTER_API_KEY``.
"""

from __future__ import annotations

import argparse
import copy
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
    DEFAULT_REPRESENTATIVE_MODEL,
    DEFAULT_RESULTS_DIR,
    DEFAULT_SUMMARIZER_MODEL,
    judge_model,
    openrouter_api_key,
    representative_model,
    summarizer_model,
)
from summarization_experiments.naming import artist_folder
from summarization_experiments.pipeline import era_label
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
    parser.add_argument(
        "--representative-model",
        default=None,
        help=f"Model for era representative selection "
        f"(default: {DEFAULT_REPRESENTATIVE_MODEL})",
    )
    parser.add_argument(
        "--skip-representatives",
        action="store_true",
        help="Skip the per-era representative-selection stage",
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


def attach_summaries_to_eras(
    report: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return a copy of ``report`` with each era song's ``summary`` attached.

    The input report keeps its Phase 2 schema (``artist`` + ``eras[].songs[]``),
    so the augmented copy can be fed straight to the renderer. Songs that were
    skipped or errored keep no ``summary`` key.
    """
    summaries = {
        record["song_id"]: record["summary"]
        for record in records
        if record.get("summary")
    }
    enriched = copy.deepcopy(report)
    for era in enriched.get("eras", []):
        for song in era.get("songs", []):
            summary = summaries.get(song.get("id"))
            if summary is not None:
                song["summary"] = summary
    return enriched


def add_representatives(
    report: dict[str, Any], pipeline: SummarizationPipeline
) -> dict[str, Any]:
    """Attach ``era["representative"]`` for every era with usable summaries.

    Best-effort: an era that fails to select representatives stores an ``error``
    instead of aborting the run.
    """
    artist = report.get("artist", {})
    for index, era in enumerate(report.get("eras", [])):
        songs = [song for song in era.get("songs", []) if song.get("summary")]
        if not songs:
            continue
        try:
            era["representative"] = pipeline.select_representative(
                songs,
                era_label=era_label(era, index),
                era_index=index,
                artist_id=artist.get("id"),
                artist_name=artist.get("name"),
            )
        except (LLMError, ValueError) as exc:
            era["representative"] = {"error": str(exc)}
    return report


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
        representative_model=args.representative_model or representative_model(),
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

    enriched = attach_summaries_to_eras(report, records)
    if not args.skip_representatives:
        print(
            "Selecting representative themes/emotions per era...",
            file=sys.stderr,
        )
        add_representatives(enriched, pipeline)
    with (out_dir / "report_enriched.json").open("w", encoding="utf-8") as handle:
        json.dump(enriched, handle, ensure_ascii=False, indent=2)

    print(format_summary(report_out))
    print(f"Wrote results to {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

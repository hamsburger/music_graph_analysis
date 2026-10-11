"""CLI: analyse how often an artist's era-defining songs were sampled.

Usage
-----
    python src/analyze_artist.py "Artist Name" [--eras 5] [--top 5]
                                       [--json] [--out DIR|FILE]
                                       [--no-cache] [--cache-dir DIR]
                                       [--no-summarize] [--summarizer-model M]
                                       [--representative-model M]
                                       [--skip-representatives]

The access token is read from ``GENIUS_ACCESS_TOKEN`` (loaded from ``.env``).
As a final step each song's lyrics are summarized via the OpenRouter API and the
summary is attached to the song, then each era's most representative themes and
emotional tone are selected; this needs ``OPENROUTER_API_KEY`` and is skipped
with a warning when the key is missing (or with ``--no-summarize``).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from music_graph_analysis import (
    ArtistAnalyzer,
    GeniusAPIError,
    GeniusClient,
    JsonCache,
    LLMError,
    LyricsSource,
    OpenRouterClient,
    SongSummarizer,
    attach_representatives,
    attach_summaries,
    openrouter_api_key,
    representative_model,
    summarizer_model,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artist", help="Artist name to look up (exact match)")
    parser.add_argument(
        "--eras", type=int, default=5, help="Number of era buckets (default: 5)"
    )
    parser.add_argument(
        "--top", type=int, default=5, help="Songs per era to analyse (default: 5), ranked by popularity (views on Genius)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the full result as JSON"
    )
    parser.add_argument(
        "--out",
        default="data/report",
        help=(
            "Write the full result as JSON to this path. If it is a directory "
            "(the default, data/report), a per-artist file is created inside it."
        ),
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable the on-disk response cache"
    )
    parser.add_argument(
        "--cache-dir",
        default="data/cache",
        help="Cache directory (default: data/cache)",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=0.34,
        help="Minimum seconds between Genius API requests (default: 0.34)",
    )
    parser.add_argument(
        "--no-summarize",
        action="store_true",
        help="Skip the LLM lyric summarization step",
    )
    parser.add_argument(
        "--summarizer-model",
        default=None,
        help="OpenRouter model for summaries (default: OPENROUTER_MODEL)",
    )
    parser.add_argument(
        "--representative-model",
        default=None,
        help=(
            "OpenRouter model for per-era representative selection "
            "(default: OPENROUTER_REPRESENTATIVE_MODEL or OPENROUTER_MODEL)"
        ),
    )
    parser.add_argument(
        "--skip-representatives",
        action="store_true",
        help="Skip the per-era representative-selection step",
    )
    parser.add_argument(
        "--llm-min-interval",
        type=float,
        default=0.0,
        help="Minimum seconds between OpenRouter requests (default: 0)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    load_dotenv()

    try:
        client = GeniusClient(min_interval=args.min_interval)
    except GeniusAPIError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    cache = None if args.no_cache else JsonCache(args.cache_dir)
    analyzer = ArtistAnalyzer(client, cache=cache)

    try:
        result = analyzer.analyze(args.artist, n_eras=args.eras, top_k=args.top)
    except GeniusAPIError as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        return 1

    if not args.no_summarize:
        _run_llm_stages(result, args, cache)

    from music_graph_analysis import format_report

    print(format_report(result))

    out_path = _report_path(args.out, args.artist)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}", file=sys.stderr)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


def _report_path(out: str, artist: str) -> Path:
    """Resolve ``--out`` to a file path, deriving a filename for directories."""
    path = Path(out)
    if path.suffix.lower() == ".json":
        return path
    slug = re.sub(r"[^a-z0-9]+", "_", artist.casefold()).strip("_")
    return path / f"{slug or 'unnamed'}.json"


def _run_llm_stages(
    result: dict, args: argparse.Namespace, cache: JsonCache | None
) -> None:
    """Summarize every song in ``result`` and select per-era representatives.

    Progress is logged to stderr. Both stages are best-effort and never abort
    the analysis; the representative stage only runs if summarization is
    enabled.
    """
    if not openrouter_api_key():
        print(
            "Summarization skipped: OPENROUTER_API_KEY is not set (see .env.example).",
            file=sys.stderr,
        )
        return

    try:
        llm = OpenRouterClient(min_interval=args.llm_min_interval)
    except LLMError as exc:
        print(f"Summarization skipped: {exc}", file=sys.stderr)
        return

    summarizer = SongSummarizer(
        llm,
        LyricsSource(cache=cache),
        cache=cache,
        summarizer_model=args.summarizer_model or summarizer_model(),
        representative_model=args.representative_model or representative_model(),
    )
    log = lambda message: print(message, file=sys.stderr)
    attach_summaries(result, summarizer, log=log)
    if not args.skip_representatives:
        attach_representatives(result, summarizer, log=log)


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI: analyse how often an artist's era-defining songs were sampled.

Usage
-----
    python src/analyze_artist.py "Artist Name" [--eras 5] [--top 5]
                                       [--json] [--out FILE]
                                       [--no-cache] [--cache-dir DIR]

The access token is read from ``GENIUS_ACCESS_TOKEN`` (loaded from ``.env``).
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from music_graph_analysis import ArtistAnalyzer, GeniusAPIError, GeniusClient, JsonCache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artist", help="Artist name to look up (exact match)")
    parser.add_argument(
        "--eras", type=int, default=5, help="Number of era buckets (default: 5)"
    )
    parser.add_argument(
        "--top", type=int, default=5, help="Songs per era to analyse (default: 5)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the full result as JSON"
    )
    parser.add_argument("--out", help="Write the full result as JSON to this path")
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
        help="Minimum seconds between API requests (default: 0.34)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

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

    from music_graph_analysis import format_report

    print(format_report(result))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
        print(f"Wrote {args.out}", file=sys.stderr)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

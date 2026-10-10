"""Example script: call the Genius ``/songs`` route and print the result.

Usage
-----
    python src/genius_api_example.py [SONG_ID]

The access token is read from ``GENIUS_ACCESS_TOKEN``. Create a ``.env`` file
in the project root (see ``.env`` / ``.env.example``) and this script will load
it automatically via python-dotenv.
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from music_graph_analysis import GeniusAPIError, GeniusClient

DEFAULT_SONG_ID = 378195


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "song_id",
        nargs="?",
        type=int,
        default=DEFAULT_SONG_ID,
        help=f"Genius song id to fetch (default: {DEFAULT_SONG_ID})",
    )
    args = parser.parse_args(argv)

    load_dotenv()

    try:
        client = GeniusClient()
    except GeniusAPIError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print(f"GET /songs/{args.song_id}")
    try:
        song = client.get_song(args.song_id)
    except GeniusAPIError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(song, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

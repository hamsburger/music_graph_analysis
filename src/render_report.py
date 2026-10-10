"""CLI: render era reports as a self-contained interactive HTML page.

Usage
-----
    python src/render_report.py --in data/report/daniel_caesar.json
    python src/render_report.py --in a.json b.json --out pages/index.html
    python src/render_report.py --in-dir data/report --out pages/index.html

Reads saved analysis reports (no Genius token needed), fetches each song's
album thumbnail and inlines it as a base64 data URI, then writes a single HTML
page with artist + dimension dropdowns. Pass ``--no-images`` to skip the
network fetch and draw plain shapes instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from music_graph_analysis import ImageFetcher, JsonCache, render_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--in",
        dest="inputs",
        nargs="+",
        default=[],
        help="One or more analysis report JSON files",
    )
    parser.add_argument(
        "--in-dir",
        dest="in_dir",
        help="Directory of *.json reports to combine",
    )
    parser.add_argument(
        "--out",
        default="pages/index.html",
        help="Output HTML path (default: pages/index.html)",
    )
    parser.add_argument("--title", default=None, help="Page title")
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip fetching album art (draw plain shapes)",
    )
    parser.add_argument(
        "--cache-dir",
        default="data/cache",
        help="Cache directory for fetched images (default: data/cache)",
    )
    return parser


def _report_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(path) for path in args.inputs]
    if args.in_dir:
        paths.extend(sorted(Path(args.in_dir).glob("*.json")))
    if not paths:
        raise SystemExit("No input reports: pass --in and/or --in-dir")
    return paths


def _load_reports(paths: list[Path]) -> list[dict]:
    reports = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            reports.append(json.load(handle))
    return reports


def _image_map(
    reports: list[dict], cache: JsonCache | None
) -> dict[int, str]:
    fetcher = ImageFetcher(cache=cache)
    images: dict[int, str] = {}
    for result in reports:
        artist = result.get("artist", {})
        artist_id = artist.get("id")
        artist_name = artist.get("name")
        for era in result.get("eras", []):
            for song in era.get("songs", []):
                url = song.get("song_art_image_thumbnail_url") or song.get(
                    "song_art_image_url"
                )
                if not url:
                    continue
                try:
                    images[song["id"]] = fetcher.data_uri(
                        url,
                        artist_id=artist_id,
                        artist_name=artist_name,
                        song_id=song.get("id"),
                        title=song.get("title"),
                    )
                except Exception as exc:  # best-effort: keep rendering
                    print(
                        f"  image skipped for {song.get('title')!r}: {exc}",
                        file=sys.stderr,
                    )
    return images


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    paths = _report_paths(args)
    reports = _load_reports(paths)
    if not reports:
        print("No reports loaded.", file=sys.stderr)
        return 1

    images: dict[int, str] = {}
    if not args.no_images:
        cache = JsonCache(args.cache_dir)
        images = _image_map(reports, cache)

    title = args.title or "Era visualizations"
    page = render_html(reports, images, title=title)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")

    artist_names = ", ".join(
        str(result.get("artist", {}).get("name")) for result in reports
    )
    print(f"Wrote {out_path} ({artist_names})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

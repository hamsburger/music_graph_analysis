# Phase 4 — Era visualization (rendering plan)

This document plans the Phase 4 work from [README.md](../README.md): render the
era analysis as something that displays on GitHub, with

- eras on a time x-axis,
- themes / imagery / emotional tone labeled per era, selectable from a dropdown,
- each song drawn as a shape with its album image embedded.

## Goal & scope

Produce a **self-contained interactive HTML page** (inline SVG + CSS + a small
amount of vanilla JS, album art inlined as base64) published with GitHub Pages.
A page can show **one or many artists** and lets the viewer switch:

- **Artist** — dropdown (shown when more than one report is combined),
- **Dimension** — dropdown over `themes`, `key_imagery`, `emotional_tone`.

The renderer is split so all layout logic is pure, testable Python that returns
SVG/HTML strings; only the CLI and the image fetcher touch the filesystem or
network.

**Out of scope:** CI beyond the Pages deploy workflow, and any LLM work
(Phase 3).

## Decisions

| Question | Choice |
| --- | --- |
| Render target | Self-contained HTML page for GitHub Pages |
| Chart tech | Python-generated SVG + tiny vanilla JS (no new deps, no CDN) |
| Y position + shape size | Songs spread evenly down each era (staggered between adjacent eras); shape size `r ∝ sqrt(pageviews)` |
| Album art | 300×300 thumbnails, fetched and embedded as base64 data URIs |
| Artist switching | Single combined page with an artist dropdown |
| Output folder | `pages/` (served by a GitHub Actions Pages workflow) |

## Architecture

- `src/music_graph_analysis/render.py` — pure functions, no I/O:
  - `DIMENSIONS = ("themes", "key_imagery", "emotional_tone")`.
  - `REPRESENTATIVE_DIMENSIONS = ("themes", "emotional_tone")` — dimensions whose
    era labels come from the LLM representative selection when available.
  - `normalize_tags(summary, dimension) -> list[str]` — lists used as-is; the
    comma-separated `emotional_tone` is split; trimmed, lowercased, deduped.
  - `era_tag_counts(era, dimension) -> Counter` — tag frequency across an era.
  - `era_representative(era, dimension) -> list[str]` — the cleaned
    `era["representative"]` labels (see
    [representative-selection.md](representative-selection.md)).
  - `era_dimension_tags(era, dimension, max_tags)` — uses the representative
    labels for `REPRESENTATIVE_DIMENSIONS` when present, falling back to
    frequency; `key_imagery` always uses frequency.
  - `build_chart_svg(result, images, *, width, height) -> str` — one SVG per
    artist: era bands, axes, and song shapes in a shared base layer, with album
    art (`images[song_id]`) embedded **once** per song, plus one toggleable
    `dim-tags` layer per dimension. Text is XML-escaped.
  - `render_html(artists, images, *, title) -> str` — full document: `<style>`,
    one SVG per artist, artist + dimension `<select>`s, toggle JS, and a shape
    fallback when an image is missing.
- `src/music_graph_analysis/images.py` — the only render-related module that
  touches the network:
  - `ImageFetcher(fetch=requests.get)` → `data_uri(url)` downloads the 300×300
    thumbnail and base64-encodes it, cached via `JsonCache` under
    `{artist}/images/{song}.json`.
- `src/render_report.py` — CLI, does file/network I/O; no Genius token needed
  (it reads saved reports only).

## Layout details

- **X axis** = time (release date), with a small deterministic horizontal
  jitter (derived from the song id) so overlapping songs separate slightly.
  Alternating era bands with era labels; undated songs go in a trailing
  `Unknown` band.
- **Y axis** = no longer encodes pageviews: each era's songs are spread evenly
  down the plot area (staggered between adjacent eras) so shapes do not overlap
  vertically. **Radius** `∝ sqrt(pageviews)`, clamped, so circle size still
  conveys popularity.
- **Labels per era** = for `themes` and `emotional_tone`, the LLM's
  representative labels when the report has `era["representative"]` (falling
  back to top tags by frequency otherwise); `key_imagery` always uses top tags by
  frequency. Counts are not shown. When an era has representative `reasoning`, it
  is emitted as a native SVG `<title>` on the era band so hovering the band shows
  the rationale.
- **Hover tooltip** — a JS-driven tooltip on each song shape shows the song
  title, its album name (when available), its `overview` summary text (when
  available), plus its tags for **all three** dimensions, with the currently
  selected dimension highlighted. The tooltip follows the cursor, clamping
  horizontally and flipping above the cursor when it would overflow the bottom
  edge; the page keeps generous bottom padding so tooltips near the bottom of
  the chart stay fully visible.
- **Dropdown** toggles visibility of the pre-rendered SVG layers, so no chart
  code runs in the browser. Album art is embedded once per song (in the shared
  base layer), keeping multi-artist pages small.

## CLI

```bash
# single artist
python src/render_report.py --in data/report/daniel_caesar.json \
    --out pages/index.html [--title T] [--no-images]

# combine several artists into one page
python src/render_report.py --in data/report/a.json data/report/b.json \
    --out pages/index.html
# or every report in a directory
python src/render_report.py --in-dir data/report --out pages/index.html
```

- `--no-images` falls back to colored circles (smaller, no network).
- The default output is `pages/index.html`.
- Generated HTML is **committed** (unlike the gitignored caches) so Pages can
  serve it.

## Publishing with GitHub Pages

GitHub's "deploy from a branch" source only serves the repo root or `/docs`, so
we use the **GitHub Actions** Pages source instead, which can publish an
arbitrary folder (`pages/`).

1. Generate and commit the page(s):

   ```bash
   python src/render_report.py --in-dir data/report --out pages/index.html
   git add pages && git commit -m "Add era visualizations" && git push
   ```

2. Enable Pages once: **Settings → Pages → Build and deployment → Source =
   "GitHub Actions"**. The committed `.github/workflows/pages.yml` uploads the
   `pages/` directory and deploys it on every push that touches it.

3. The site is served at:

   ```
   https://<your-username>.github.io/<repo>/
   ```

   (with `pages/index.html` as the entry point).

Notes:

- The first publish takes ~1 minute; later pushes to `pages/**` redeploy
  automatically (the workflow also supports manual `workflow_dispatch`).
- The page is fully self-contained, so it works from Pages, `file://`, or any
  static host.

## Changes to existing code

- `analysis.py:_build_era` — add `song_art_image_url`,
  `song_art_image_thumbnail_url`, and `album` to each era song.
- `__init__.py` — re-export the new render/image symbols.
- `AGENTS.md` — note that `images.py` is a third `requests` caller
  (images.genius.com, not the Genius API).
- `pyproject.toml` — no new runtime dependencies.

## Docs to update

- `README.md` — mark Phase 4 and add the render command under usage.
- `docs/repo-structure.md` — add `render.py`, `images.py`, `render_report.py`,
  and the `pages/` folder.
- `CHANGELOG.md` — entry for this change (via the changelog skill).

## Testing

`tests/test_render.py` (no network):

- `normalize_tags` handles list vs comma-separated string; dedupe/trim.
- `era_tag_counts` aggregation.
- `build_chart_svg`: circle/`<clipPath>` count, XML escaping, unknown-era band.
- `render_html`: three dimensions, artist + dimension selects, multi-artist
  grouping, missing-image fallback.
- Image embedding with a fake fetcher dict.

Also extend `tests/test_analysis.py` to assert era songs carry the art URL.

## Risks / open questions

- **Page size** — base64 art makes multi-artist pages large. Mitigations:
  300×300 thumbnails, `--no-images`, or lazy image loading.
- **Hotlinking / rate limits** — images are downloaded once and cached, so
  repeated renders do not re-hit `images.genius.com`.
- **Copyright** — album thumbnails are referenced for display only; not a new
  redistribution surface beyond what GitHub Pages already hosts.

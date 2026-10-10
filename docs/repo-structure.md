# Repository Structure

This document maps out the repository layout and explains what each part does.

## Directory tree

```
music_graph_analysis/
├── .env                     # Local secrets (gitignored). GENIUS_ACCESS_TOKEN.
├── .env.example             # Template for the environment file.
├── README.md                # Project goals, setup, and usage.
├── pyproject.toml           # Package metadata, dependencies, pytest config.
├── opencode.json            # opencode configuration (read/grep permissions).
├── data/
│   ├── cache/               # Generated JSON response cache (gitignored).
│   └── examples/            # Sample Genius API payloads for reference/tests.
├── docs/
│   ├── cache.md             # On-disk response cache design.
│   ├── phase-3-summarization.md  # LLM lyric summarization plan.
│   └── repo-structure.md    # This document.
├── notebook_experiments/    # Scratch space for exploratory notebooks.
├── summarization_experiments/  # Phase 3 sandbox: lyrics -> LLM summary -> judge.
├── src/
│   ├── analyze_artist.py            # CLI entry point for the era analysis.
│   ├── genius_api_example.py        # Minimal /songs/{id} example script.
│   └── music_graph_analysis/        # Installable package.
│       ├── __init__.py              # Public API re-exports.
│       ├── genius.py                # Genius REST API client.
│       ├── eras.py                  # Pure era-bucketing logic.
│       ├── cache.py                 # JSON disk cache.
│       └── analysis.py              # Orchestration + report formatting.
└── tests/
    ├── test_genius.py               # Client request/retry/paging tests.
    ├── test_eras.py                 # Bucketing and selection tests.
    └── test_analysis.py             # End-to-end analysis tests (fake client).
```

## Package modules

### `music_graph_analysis/genius.py`
Thin wrapper around the Genius REST API (`https://api.genius.com`). Holds all
network access.

- `GeniusClient` — auth via `GENIUS_ACCESS_TOKEN`, request timeout, retry with
  exponential backoff, and an optional client-side throttle (`min_interval`).
- `get_song` / `get_song_detail` — fetch a song and its detailed object.
- `get_relationships` / `get_all_relationships` — read `song_relationships`.
  `get_all_relationships` fetches a song once and groups its related songs by
  type (`samples`, `sampled_in`, `interpolates`, `interpolated_by`); the
  `get_samples` / `get_sampled_in` / `get_interpolates` / `get_interpolated_by`
  helpers return a single direction.
- `search` / `find_artist` — look up an artist by an exact name match.
- `get_artist_songs` — one page of an artist's songs.
- `iter_artist_songs` — generator that pages through the full discography
  (`per_page` is clamped to `MAX_PER_PAGE == 50`).
- `get_artist_top_songs` — convenience lookup of the most popular songs.
- `GeniusAPIError` — raised on configuration or API failures.

### `music_graph_analysis/eras.py`
Pure, side-effect-free logic (no network or file I/O) that is easy to unit test.

- `EraBounds` — dataclass describing `n` equal-time buckets across
  `[start, end]`, with `interval(i)` and `assign(datetime)`.
- `parse_release_date(song)` — extracts a `datetime` from
  `release_date_components` (falling back to the `release_date` string).
- `song_pageviews(song)` — popularity metric from `stats.pageviews`.
- `compute_era_bounds(dates, n)` — builds `EraBounds` from release dates.
- `select_top_songs_per_era(songs, bounds, top_k)` — groups songs into eras and
  keeps the `top_k` most popular in each, always including an `unknown` bucket
  (`UNKNOWN_ERA`) for undated songs.

### `music_graph_analysis/cache.py`
- `JsonCache` — JSON file cache under `data/cache/` (configurable). Keys are
  slash-separated, human-readable paths that are slugified per segment, so each
  artist gets its own folder (e.g. `data/cache/kanye-west-123/discography.json`).
  Used to avoid re-hitting the API on repeated runs.

### `music_graph_analysis/analysis.py`
Orchestration layer that ties the client, cache, and era logic together.

- `ArtistAnalyzer` — resolves the artist, pulls the full discography, keeps only
  songs where the artist is the `primary_artist`, computes era bounds, selects
  top songs per era, fetches each song's sample/interpolation relationships
  (both what it drew from and what drew from it), and aggregates results.
- `format_report(result)` — renders a readable console summary.

### `music_graph_analysis/__init__.py`
Re-exports the public surface (`GeniusClient`, `ArtistAnalyzer`, `JsonCache`,
era helpers, `format_report`, etc.) so callers can import from the package root.

## Entry points

- `src/analyze_artist.py` — CLI for the era analysis:
  ```bash
  python src/analyze_artist.py "SWV" [--eras N] [--top K] [--json] [--out FILE]
  ```
- `src/genius_api_example.py` — prints the raw `/songs/{id}` response.

## Data flow

```
artist name
   │  find_artist (search)
   ▼
artist id ──► iter_artist_songs (paged, cached)
   │              │
   │              ▼
   │        primary-artist filter
   │              │
   │              ▼
   │        compute_era_bounds ◄── parse_release_date
   │              │
   │              ▼
   │        select_top_songs_per_era (top-K + unknown bucket)
   │              │
   │              ▼
   └──────► get_all_relationships (per song, cached)
                  │
                  ▼
          aggregated JSON + console report
```

## Tests

Run the suite from the project root:

```bash
pytest
```

Tests never hit the network: the Genius client tests monkeypatch
`requests.get`, and the analysis tests use a `FakeClient` plus a temporary
`JsonCache`.

## Related concepts

- **Era buckets** — the artist's career span (`earliest` to `latest` release) is
  divided into `n` equal-length time intervals; the most popular songs in each
  are analysed.
- **Unknown bucket** — songs missing a usable release date are grouped under
  `unknown` rather than being dropped.
- **Sampled-in / interpolated-by** — the songs that sampled or interpolated a
  given track, read from `song.song_relationships` where `type == "sampled_in"`
  or `"interpolated_by"`. The reverse directions (`samples`, `interpolates`)
  capture what the song itself drew from.

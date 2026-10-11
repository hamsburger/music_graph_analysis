# Repository Structure

This document maps out the repository layout and explains what each part does.

## Directory tree

```
music_graph_analysis/
├── .env                     # Local secrets (gitignored). GENIUS_ACCESS_TOKEN.
├── .env.example             # Template for the environment file.
├── .github/
│   └── workflows/pages.yml  # Deploys the committed pages/ folder to Pages.
├── README.md                # Project goals, setup, and usage.
├── pyproject.toml           # Package metadata, dependencies, pytest config.
├── opencode.json            # opencode configuration (read/grep permissions).
├── data/
│   ├── cache/               # Generated JSON response cache (gitignored).
│   └── examples/            # Sample Genius API payloads for reference/tests.
├── docs/
│   ├── cache.md             # On-disk response cache design.
│   ├── phase-3-summarization.md  # LLM lyric summarization plan.
│   ├── phase-4-visualization.md  # Interactive HTML rendering plan.
│   ├── representative-selection.md  # Stage 4 era representative plan.
│   └── repo-structure.md    # This document.
├── notebook_experiments/    # Scratch space for exploratory notebooks.
├── pages/                   # Committed generated HTML for GitHub Pages.
├── summarization_experiments/  # Phase 3 sandbox: lyrics -> summary -> judge
│                               # -> per-era representative selection. The
│                               # summarizer used in production is in the package.
├── src/
│   ├── analyze_artist.py            # CLI entry point for the era analysis.
│   ├── render_report.py             # CLI entry point for HTML rendering.
│   ├── genius_api_example.py        # Minimal /songs/{id} example script.
│   └── music_graph_analysis/        # Installable package.
│       ├── __init__.py              # Public API re-exports.
│       ├── genius.py                # Genius REST API client.
│       ├── eras.py                  # Pure era-bucketing logic.
│       ├── cache.py                 # JSON disk cache.
│       ├── naming.py                # Cache-key / label helpers.
│       ├── config.py                # Summarizer env vars, model, prompts dir.
│       ├── llm.py                   # OpenRouter chat-completions client.
│       ├── lyrics.py                # LyricsSource (lazy lyricsgenius).
│       ├── images.py                # Album-art fetcher -> base64 data URIs.
│       ├── prompts.py               # Load/render prompt templates.
│       ├── prompts/
│       │   ├── summarize.txt        # Summarize prompt (package data).
│       │   └── representative.txt   # Era representative prompt (package data).
│       ├── render.py                # Pure SVG/HTML rendering for the charts.
│       ├── summarize.py             # SongSummarizer + summaries/representatives.
│       └── analysis.py              # Orchestration + report formatting.
└── tests/
    ├── test_genius.py               # Client request/retry/paging tests.
    ├── test_eras.py                 # Bucketing and selection tests.
    ├── test_analysis.py             # End-to-end analysis tests (fake client).
    ├── test_render.py               # SVG/HTML rendering + image fetcher tests.
    └── test_summarize.py            # Summarizer tests (fake LLM + lyrics).
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

### `music_graph_analysis/naming.py`
- Dependency-free helpers shared by the analyzer and summarizer:
  `content_hash` (short SHA-256 for cache keys), `artist_folder`,
  `song_label`, and `model_slug` (slash-safe path segment).

### `music_graph_analysis/config.py`
- Summarizer configuration: `DEFAULT_PROMPTS_DIR`, `OPENROUTER_BASE_URL`,
  `DEFAULT_SUMMARIZER_MODEL`, `DEFAULT_REPRESENTATIVE_MODEL`,
  `MAX_REPRESENTATIVES`, plus `openrouter_api_key()`, `summarizer_model()`
  (`OPENROUTER_API_KEY` / `OPENROUTER_MODEL`), and `representative_model()`
  (`OPENROUTER_REPRESENTATIVE_MODEL` -> `OPENROUTER_MODEL` -> default).

### `music_graph_analysis/llm.py`
- `OpenRouterClient` — OpenAI-compatible chat-completions client for
  `https://openrouter.ai/api/v1`; timeout, retries with exponential backoff,
  and an optional `min_interval` throttle. `LLMError` on failure.

### `music_graph_analysis/lyrics.py`
- `LyricsSource` — fetches lyrics by song ID via the unofficial `lyricsgenius`
  scraper (imported lazily) and caches the raw result per artist.
  `LyricsError` when the token is missing or a fetch fails.

### `music_graph_analysis/images.py`
- `ImageFetcher` — downloads a song's album thumbnail from `images.genius.com`
  and returns it as a base64 `data:` URI, caching the result via `JsonCache`
  (`{artist}/images/{song}.json`). The `fetch` callable is injectable so tests
  never hit the network. This is the only render-related module that uses
  `requests`.

### `music_graph_analysis/render.py`
Pure, side-effect-free rendering (no network or file I/O) that returns strings.

- `DIMENSIONS` — `("themes", "key_imagery", "emotional_tone")`.
- `normalize_tags(summary, dimension)` — clean/dedupe tags (splits the
  comma-separated `emotional_tone`).
- `era_tag_counts(era, dimension)` — tag frequency across an era.
- `build_chart_svg(result, images, ...)` — one SVG per artist: time x-axis with
  era bands, songs spread evenly down each era (staggered, with a deterministic
  x-jitter) and sized by `sqrt(pageviews)`, drawn as clipped circles filled
  with `images[song_id]` (embedded once), and one toggleable tag layer per
  dimension.
- `render_html(artists, images, *, title)` — a self-contained page with one SVG
  per artist plus artist/dimension dropdowns and toggle JS.

### `music_graph_analysis/prompts.py` + `prompts/`
- `load_prompt(name)` / `render(template, **values)` load and fill the
  plain-text templates. `prompts/summarize.txt` (Stage 2) and
  `prompts/representative.txt` (Stage 4) ship as package data; rendering is
  literal `{token}` replacement so the JSON examples inside the prompts keep
  their braces.

### `music_graph_analysis/summarize.py`
- `SongSummarizer` — fetches a song's lyrics, cleans them, calls the LLM with
  the summarize prompt, and parses the strict-JSON summary (cached per model +
  rendered prompt). `summarize_song(song)` returns the summary dict or `None`
  when there are no usable lyrics. `select_representative(songs, era_label=...)`
  reads an era's `themes`/`emotional_tone` labels at once and returns the most
  representative ones plus `reasoning` (cached per era + model + prompt).
- `attach_summaries(result, summarizer)` — walks an analysis result and sets a
  `summary` key on every song (or `None`); never aborts on a per-song error.
- `attach_representatives(result, summarizer)` — sets `era["representative"]` for
  every era that has usable summaries (best-effort, storing `{"error": ...}` on
  failure).
- `clean_lyrics` / `extract_json` — the pure helpers (snippet/`[editing]`
  rejection and tolerant JSON parsing).

### `music_graph_analysis/analysis.py`
Orchestration layer that ties the client, cache, and era logic together.

- `ArtistAnalyzer` — resolves the artist, pulls the full discography, keeps only
  songs where the artist is the `primary_artist`, computes era bounds, selects
  top songs per era, fetches each song's sample/interpolation relationships
  (both what it drew from and what drew from it), and aggregates results.
- `format_report(result)` — renders a readable console summary.

### `music_graph_analysis/__init__.py`
Re-exports the public surface (`GeniusClient`, `ArtistAnalyzer`, `JsonCache`,
era helpers, `SongSummarizer`, `attach_summaries`, `format_report`, etc.) so
callers can import from the package root.

## Entry points

- `src/analyze_artist.py` — CLI for the era analysis. As a final step it
  summarizes each song's lyrics and selects each era's representative themes /
  emotional tone; without `OPENROUTER_API_KEY` (or with `--no-summarize`) it
  warns and skips, and `--skip-representatives` skips just the era stage.
  ```bash
  python src/analyze_artist.py "SWV" [--eras N] [--top K] [--json] [--out DIR|FILE]
                                     [--no-summarize] [--summarizer-model M]
                                     [--representative-model M] [--skip-representatives]
  ```
- `src/genius_api_example.py` — prints the raw `/songs/{id}` response.
- `src/render_report.py` — reads one or more saved reports and writes a
  self-contained interactive HTML page (album thumbnails inlined as data URIs).
  ```bash
  python src/render_report.py --in data/report/a.json data/report/b.json \
                              --out pages/index.html [--title T] [--no-images]
  ```
  Commit the output under `pages/`; `.github/workflows/pages.yml` deploys that
  folder to GitHub Pages.

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
                  │
                  ▼ (final steps, best-effort)
          attach_summaries ◄── LyricsSource (lyricsgenius)
                  │              + OpenRouterClient (summarize.txt)
                  ▼
          each song gains a `summary` dict
                  │
                  ▼
          attach_representatives ◄── OpenRouterClient (representative.txt)
                  │
                  ▼
          each era gains a `representative` dict
```

## Tests

Run the suite from the project root:

```bash
pytest
```

Tests never hit the network: the Genius client tests monkeypatch
`requests.get`, the analysis tests use a `FakeClient` plus a temporary
`JsonCache`, and the summarizer tests use a `FakeLLM` and `FakeLyricsSource`.

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

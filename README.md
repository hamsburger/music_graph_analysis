# Project Goals

See [docs/repo-structure.md](docs/repo-structure.md) for a map of the codebase.

~~Look for a producer that produces many songs~~

~~or on average, a producer’s song is sampled by many artists~~

~~**High production, low sampled by**: Commercial Plumber, Black Hole in for love of the game~~

~~**High production, high sampled by** Legendary, Curatorial status~~

~~**Low production, low sampled_by** Niche~~

~~**Low production, high sampled_by** One hit wonder~~

**Update:** Seems like this is hard to achieve through the Genius API since we cannot search by producer name. So I think the better idea here is to understand how many times an artists' most popular songs in each era was "sampled_in". I'd say we find the artist's most recent and earliest song, using that range, divide into 5 equal time-length buckets, we'll call these era buckets. The top 5 most popular songs in each era are picked, and we find out how many times they've been sampled and which songs/artists sampled them.

# Project Phases

- **Phase 1 (Complete)**: Divide songs into eras and pick top 5 most popular songs in each era
- **Phase 2 (Complete)**: For each song, find out song relationships: samples, sampled_in, interpolates, interpolated_by
- **Phase 3 (In progress)**: LLM Summary of lyrics for each song is completed and integrated (see [docs/phase-3-summarization.md](docs/phase-3-summarization.md)); the LLM judge experiment and the song-lineage summary remain in the sandbox.
- **Phase 4 (Complete)**: an interactive, self-contained HTML page renders each artist's eras on a time x-axis, with themes / imagery / emotional tone selectable from a dropdown and each song drawn as a shape with its album thumbnail embedded. See [docs/phase-4-visualization.md](docs/phase-4-visualization.md).

## Improvements
- Add CLAUDE/AGENT.md so you can be more confident in the data your coding agent is using as context for making decisions
- Add skills for automations you're sure about, such as changelog generation on every commit
- How is DeepSeek Flash so good at figuring out where to get context? (e.g. use lyricsgenius to get lyrics, implement the Genius API perfectly as if it has been grounded in its endpoint)
- Batch Processing for LLM summarization? Right now we're just processing one song at a time.
- We should scrape more data outside of cache if we haven't scraped on the current date? Or maybe use a flag to look for new data.
- /song endpoint fetch should use {title}-{id} as cache key instead of just the id.

# Data Source

Genius API Key

# Setup

Create and activate a virtual environment, then install the project (this also
installs the runtime dependencies `requests`, `python-dotenv`, and
`lyricsgenius`, plus the dev extras such as `pytest`):

```bash
python -m venv .venv

# Windows (bash)
source .venv/Scripts/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Environment variables

Copy `.env.example` to `.env` and set your Genius access token:

```bash
cp .env.example .env
```

```
GENIUS_ACCESS_TOKEN=your_token_here
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=deepseek/deepseek-chat
```

`.env` is gitignored; never commit real credentials.

`OPENROUTER_API_KEY` enables the LLM lyric summaries (and per-era representative
selection) attached as the final analysis step; without it the analysis runs and
these steps are skipped with a warning. `OPENROUTER_MODEL` is the summarizer
model (default `deepseek/deepseek-chat`); `OPENROUTER_REPRESENTATIVE_MODEL`
optionally points the representative-selection step at a different model.

## Running the example

With the virtual environment active:

```bash
python src/genius_api_example.py
```

Optionally pass a Genius song id, e.g. `python src/genius_api_example.py 378195`.
The script prints the raw `/songs/{id}` response as JSON.

## Running the era analysis

Analyse how often an artist's most popular songs in each career "era" were
sampled. The artist's release dates are split into 5 equal time-length buckets
(songs with no date go into an `unknown` bucket), the top 5 songs per bucket are
selected by pageviews, and each song's relationships are collected: what it
`sampled`/`interpolated` (its inspirations) and the songs that `sampled_in`/
`interpolated_by` it (its influence).

As a final step, each song's lyrics are fetched and summarized with the LLM, and
the resulting `summary` dict (`overview`, `themes`, `emotional_tone`,
`key_imagery`) is attached to the song. Then, per era, the songs' `themes` and
`emotional_tone` labels are read at once and the most representative ones (with a
short rationale) are attached as `era["representative"]`. Both steps are
best-effort: without `OPENROUTER_API_KEY` they are skipped with a warning.

```bash
python src/analyze_artist.py "SWV"
```

Useful flags:

- `--eras N` / `--top K` — number of era buckets / songs per era.
- `--json` — print the full structured result as JSON.
- `--out DIR|FILE` — where to write the full result as JSON. Defaults to
  `data/report`, where a per-artist file (e.g. `data/report/daniel_caesar.json`)
  is created; pass a `.json` path to choose the exact file.
- `--no-cache` — disable the on-disk response cache (`data/cache/`).
- `--min-interval SECONDS` — client-side throttle between Genius API requests.
- `--no-summarize` — skip both LLM stages (summary + representative selection).
- `--summarizer-model M` — OpenRouter model for summaries (default `OPENROUTER_MODEL`).
- `--representative-model M` — OpenRouter model for per-era representative
  selection (default `OPENROUTER_REPRESENTATIVE_MODEL` or `OPENROUTER_MODEL`).
- `--skip-representatives` — keep the summaries but skip representative selection.

## Rendering the visualization

Turn one or more saved analysis reports (with their LLM summaries) into a
single self-contained interactive HTML page: eras on a time x-axis, songs
spread evenly down each era (with a small deterministic x-jitter) and sized by
popularity, each drawn as a shape with its album thumbnail embedded, and a
dropdown to switch between **themes**, **key imagery**, and **emotional tone**.
When more than one report is combined, an **artist** dropdown appears too.

Era labels for **themes** and **emotional tone** use each era's LLM-selected
`representative` labels when the report has them (hover an era band to see the
rationale); **key imagery** and reports without representatives fall back to the
top tags by frequency.

```bash
# one artist
python src/render_report.py --in data/report/daniel_caesar.json --out pages/index.html

# combine every report in a folder
python src/render_report.py --in-dir data/report --out pages/index.html
```

Useful flags:

- `--out FILE` — output path (default `pages/index.html`).
- `--no-images` — skip fetching album art (draw plain shapes; no network).
- `--title T` — page title.
- `--cache-dir DIR` — cache fetched thumbnails (default `data/cache`).

The generated HTML is committed (unlike the gitignored caches). To publish it,
push `pages/` and enable GitHub Pages with the **GitHub Actions** source; the
committed workflow uploads the `pages/` folder. See
[docs/phase-4-visualization.md](docs/phase-4-visualization.md) for details.

## Tests

```bash
pytest
```
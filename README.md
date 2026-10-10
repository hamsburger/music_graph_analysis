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
- **Phase 3 (In progress)**: LLM Summary of lyrics for each song, then another LLM to summarize the lineage of the song (how it was created, who sampled it). See [docs/phase-3-summarization.md](docs/phase-3-summarization.md) for the experimentation plan.

## Improvements
- Add CLAUDE/AGENT.md so you can be more confident in the data your coding agent is using as context for making decisions
- Add skills for automations you're sure about, such as changelog generation on every commit
- How is DeepSeek Flash so good at figuring out where to get context? (e.g. use lyricsgenius to get lyrics, implement the Genius API perfectly as if it has been grounded in its endpoint)
- Batch Processing for LLM summarization? Right now we're just processing one song at a time.

# Data Source

Genius API Key

# Setup

Create and activate a virtual environment, then install the project (this also
installs the runtime dependencies `requests` and `python-dotenv`, plus the dev
extras such as `pytest`):

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
```

`.env` is gitignored; never commit real credentials.

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

```bash
python src/analyze_artist.py "SWV"
```

Useful flags:

- `--eras N` / `--top K` — number of era buckets / songs per era.
- `--json` — print the full structured result as JSON.
- `--out FILE` — write the full result as JSON to a file.
- `--no-cache` — disable the on-disk response cache (`data/cache/`).
- `--min-interval SECONDS` — client-side throttle between API requests.

## Tests

```bash
pytest
```
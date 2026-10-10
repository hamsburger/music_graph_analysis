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
- **Phase 4**: Produce something that can render on github and show the following things:
  - Eras on a "time" x-axis.
  - Themes, imageries, or emotional tones labeled on a chart for each era. User should be able to select which one that want to see in a dropdown menu.
  - Render each song in the era as a shape of some sort? With the album image of the song being embedded in the shape.

## Improvements
- Add CLAUDE/AGENT.md so you can be more confident in the data your coding agent is using as context for making decisions
- Add skills for automations you're sure about, such as changelog generation on every commit
- How is DeepSeek Flash so good at figuring out where to get context? (e.g. use lyricsgenius to get lyrics, implement the Genius API perfectly as if it has been grounded in its endpoint)
- Batch Processing for LLM summarization? Right now we're just processing one song at a time.

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

`OPENROUTER_API_KEY` enables the LLM lyric summaries attached to each song as
the final analysis step; without it the analysis runs and summaries are skipped
with a warning. `OPENROUTER_MODEL` is the summarizer model (default
`deepseek/deepseek-chat`).

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
`key_imagery`) is attached to the song. This step is best-effort: without
`OPENROUTER_API_KEY` it is skipped with a warning.

```bash
python src/analyze_artist.py "SWV"
```

Useful flags:

- `--eras N` / `--top K` — number of era buckets / songs per era.
- `--json` — print the full structured result as JSON.
- `--out FILE` — write the full result as JSON to a file.
- `--no-cache` — disable the on-disk response cache (`data/cache/`).
- `--min-interval SECONDS` — client-side throttle between Genius API requests.
- `--no-summarize` — skip the LLM lyric summarization step.
- `--summarizer-model M` — OpenRouter model for summaries (default `OPENROUTER_MODEL`).

## Tests

```bash
pytest
```
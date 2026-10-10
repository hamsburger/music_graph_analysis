# Project Goals

Look for a producer that produces many songs

or on average, a producer’s song is sampled by many artists

**High production, low sampled by**: Commercial Plumber, Black Hole in for love of the game

**High production, high sampled by** Legendary, Curatorial status

**Low production, low sampled_by** Niche

**Low production, high sampled_by** One hit wonder

**Update:** Seems like this is hard to achieve through the Genius API since we cannot search by producer name. So I think the better idea here is to understand how many times an artists' most popular songs in each era was "sampled_in". I'd say we find the artist's most recent and earliest song, using that range, divide into 5 equal time-length buckets, we'll call these era buckets. The top 5 most popular songs in each era are picked, and we find out how many times they've been sampled and which songs/artists sampled them.

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

## Tests

```bash
pytest
```
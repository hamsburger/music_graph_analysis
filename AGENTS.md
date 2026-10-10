# AGENTS.md

Project-specific guidance for coding agents working in this repo.

## What this is

Python tool that analyses music sampling/interpolation graphs via the Genius API.
An artist's career is split into equal-length **eras**; the most popular songs per
era are selected and their `samples` / `sampled_in` / `interpolates` /
`interpolated_by` relationships are collected and reported. As a final step each
song's lyrics are summarized with an LLM and the summary is attached to the song.

See [docs/repo-structure.md](docs/repo-structure.md) for the full codebase map and
[docs/cache.md](docs/cache.md) for the on-disk cache design. Keep those docs in
sync when changing behavior.

## Commands

Run from the repo root with the venv active.

```bash
python -m pip install -e ".[dev]"      # install package + dev extras
pytest                                  # full test suite (no network)
pytest tests/test_eras.py              # single test file
python src/analyze_artist.py "SWV"     # run the era analysis
python src/genius_api_example.py       # raw /songs/{id} example
```

There is no configured linter, formatter, or type-checker — only `pytest`.
Do not invent or assume a lint command.

## Conventions

- Python >= 3.10; PEP 8; 4-space indent; module and public-function docstrings.
- Every module uses `from __future__ import annotations` and type hints.
- Prefer pure, side-effect-free functions for logic (see `eras.py`): no network
  or file I/O in that layer, so it stays easy to unit test.
- Genius network access is funnelled through `music_graph_analysis/genius.py`
  (`GeniusClient`); OpenRouter access through `music_graph_analysis/llm.py`
  (`OpenRouterClient`). These are the only modules that call `requests`, except
  `music_graph_analysis/images.py` (`ImageFetcher`), which downloads album
  thumbnails from `images.genius.com` for the Phase 4 renderer.
  Lyrics scraping lives in `lyrics.py` (`LyricsSource`, lazy `lyricsgenius`).
- `analysis.py` is the orchestration layer; `summarize.py` attaches the LLM
  summary dict to each song. `__init__.py` re-exports the public API, so add
  public symbols there too.
- Prompts are package data under `music_graph_analysis/prompts/` (`summarize.txt`);
  include new `.txt` files via `[tool.setuptools.package-data]` in `pyproject.toml`.
- `analyze_artist.py` runs summarization as its final step. It is best-effort:
  without `OPENROUTER_API_KEY` (or with `--no-summarize`) it warns and skips, so
  the base analysis never requires the OpenRouter key.

## Gotchas

- **Tests must never hit the network.** Client tests monkeypatch `requests.get`;
  analysis tests use `FakeClient` and a temporary `JsonCache`. Follow that pattern.
- **Never read or log `.env` or any credentials.** `GENIUS_ACCESS_TOKEN` is loaded
  via `python-dotenv`; `opencode.json` denies reads/greps of `.env*` files. Use
  `.env.example` as the template only.
- **`data/cache/` is generated and gitignored** — don't commit it, and treat
  cached JSON as disposable (writes are atomic, reads fall back to a fresh fetch).
- API responses are rate-limited: keep the retry/backoff and `min_interval`
  throttle behaviour in `GeniusClient` intact.

## Verification before finishing

1. `pytest` passes.
2. If you changed analysis output or CLI flags, update `README.md` and the
   relevant doc under `docs/`.

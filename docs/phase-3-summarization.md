# Phase 3 — LLM lyric summarization (experimentation plan)

This document plans the Phase 3 work from [README.md](../README.md): use an LLM to
summarize the lyrics of each era-defining song, then have a second LLM act as a
**judge** that checks the summary for grounding, completeness, and validity.

The first step is a throwaway sandbox under `summarization_experiments/` so we can
tune prompts on real songs *before* wiring anything into the production
`analysis.py` pipeline.

## Goal & scope

Validate a three-stage pipeline end to end:

1. **Ingest** — obtain the lyrics for a song.
2. **Summarize** — an LLM produces a structured summary of those lyrics.
3. **Judge** — a separate LLM call scores the summary (out of 5), checks whether
   the reasoning is grounded in the lyrics, and lists any important information
   that was left out.

**Out of scope for now:** the second half of Phase 3 (summarizing a song's
*lineage* — how it was created and who sampled it) and any integration into the
installable `music_graph_analysis` package. Those come after the summary/judge
loop is proven.

## Status & how to run

The sandbox is implemented. Set `OPENROUTER_API_KEY` (and keep
`GENIUS_ACCESS_TOKEN`) in `.env`, then:

```bash
python summarization_experiments/run_pipeline.py data/report/millkzy.json --limit 3
```

Per-song results land in `summarization_experiments/results/{artist}/` with an
aggregate `report.json`. Unit tests (no network) live in
`tests/test_summarization_experiments.py`.

## Background (verified)

- The Genius API `/songs/{id}` endpoint does **not** return lyrics. Confirmed by
  inspecting `data/examples/song_465899.json`, which has `lyrics_state` but no
  `lyrics` field.
- `data/examples/Lyrics_Millkzy.json` (committed in the initial push) contains
  scraped lyrics, so a scraping path already exists in spirit.
- `lyricsgenius` 3.2.0 (plus `beautifulsoup4` and `lxml`) is already installed in
  the dev environment.
- `lyricsgenius.Genius.song(song_id)` and `.lyrics(song_id=...)` fetch a song's
  lyrics **by ID**, and we already have song IDs in `data/report/*.json`.
- `notebook_experiments/` is currently empty. `data/report/*.json` holds stale
  Phase-1-era reports (they predate the Phase 2 relationship fields).

## Decisions

| Question | Choice |
| --- | --- |
| Lyrics source | `lyricsgenius`, fetched by song ID, cached per artist |
| LLM backend | OpenRouter, called over `requests` (no new SDK) |
| Artifact form | Python scripts (pytest-friendly), not notebooks |
| Location | Top-level `summarization_experiments/` (outside the package) |
| Prompts | Plain-text files under `summarization_experiments/prompts/` |
| Caching | Per-artist, reusing the package `JsonCache` layout |

## Folder structure

```
summarization_experiments/
├── prompts/
│   ├── summarize.txt          # Stage 2 prompt (plain text, {lyrics} placeholder)
│   └── judge.txt              # Stage 3 prompt (plain text, {lyrics}/{summary})
├── data/                      # gitignored; mirrors the JsonCache layout
│   └── {artist-name}-{artist-id}/
│       ├── lyrics/{song-title}-{song-id}.json
│       ├── summaries/{song-title}-{song-id}.json
│       └── judge/{song-title}-{song-id}.json
├── results/                   # gitignored; run outputs
│   └── {artist-name}-{artist-id}/
│       ├── results.json       # {"songs": [...]} — per-song summary + judge
│       └── report.json        # aggregate: mean score, pass rate, distribution
├── __init__.py
├── config.py                  # env vars, model ids, paths, constants
├── naming.py                  # shared cache-key / result-path helpers
├── lyrics_source.py           # lyricsgenius wrapper -> per-artist cache
├── llm_client.py              # OpenRouter chat-completions via requests
├── prompts.py                 # loads prompts/*.txt and renders placeholders
├── pipeline.py                # summarize/judge logic + aggregation
└── run_pipeline.py            # CLI entry point
```

## Pipeline stages

### Stage 1 — Ingest lyrics

- Input: an artist report (`data/report/*.json`) or an explicit `--song-id`.
- For each song, fetch lyrics with `lyricsgenius` by ID.
- Skip songs whose lyrics are empty, `[editing]`, or snippet-only
  (`[Snippet]` with no real content), recording a `skipped` reason.
- Store `{song_id, title, artist, lyrics, chars}` in the per-artist lyrics cache.

### Stage 2 — Summarize

- The LLM receives the raw lyrics plus `prompts/summarize.txt`.
- It must return **strict JSON** with:
  `overview`, `themes[]`, `emotional_tone`, `key_imagery[]`.
- A tolerant JSON extractor strips fenced code blocks / leading prose before
  parsing.

### Stage 3 — Judge

- A *separate* LLM call receives the **original lyrics** and the **candidate
  summary** plus `prompts/judge.txt`.
- It must return **strict JSON** with:
  `score` (integer 1–5), `grounded` (bool), `missing_points[]`, `reasoning`,
  and `verdict`.
- Default validity rule: `verdict == "valid"` when `grounded` is true **and**
  `score >= 4`. The threshold lives in `config.py` so it is easy to retune.

### Prompt templates

- `prompts.py` loads `prompts/summarize.txt` and `prompts/judge.txt`.
- Placeholders are `{lyrics}` and `{summary}`. They are replaced by a literal
  token substitution, **not** `str.format`, so the JSON examples inside the
  prompts keep their braces.

## LLM client

- `OpenRouterClient` is modelled on `GeniusClient` (`music_graph_analysis/genius.py`):
  `requests`, a request timeout, retries with exponential backoff, and an
  optional client-side `min_interval` throttle.
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`.
- Configuration comes from the environment:
  - `OPENROUTER_API_KEY` — required.
  - `OPENROUTER_MODEL` — default summarizer model (e.g. `deepseek/deepseek-chat`).
  - Optional per-stage overrides so the judge can use a stronger model than the
    summarizer.
- Errors mirror `GeniusAPIError` (a dedicated `LLMError`).

## Caching

- Reuse `music_graph_analysis.JsonCache` so the layout matches
  [docs/cache.md](cache.md): each artist gets a
  `{artist-name}-{artist-id}/` folder.
- Cache keys:
  - `{artist}/lyrics/{song}` — raw lyrics from `lyricsgenius`.
  - `{artist}/summaries/{song}-{model}-{digest}` — Stage 2 output.
  - `{artist}/judge/{song}-{model}-{digest}` — Stage 3 output.
- `{digest}` is a short SHA-256 of the **rendered prompt** — i.e. the exact LLM
  input. For summaries that is the lyrics plus `summarize.txt`; for verdicts it is
  the lyrics + candidate summary plus `judge.txt`. Editing a prompt template or
  the input data therefore produces a fresh cache entry instead of a stale hit,
  and the model slug is included so switching models never serves a stale result.
- Caching both lyrics and LLM responses means iterating on prompts never re-hits
  Genius, but changed prompts are re-billed (intentionally) rather than silently
  reusing the previous run's output.
- When only a `--song-id` is given (no artist report), fall back to a shared
  `songs/` folder, exactly like the existing relationship cache does.

## Output schema (per song)

```json
{
  "song_id": 10595643,
  "title": "RUSSIAN ROULETTE(I ADORE U)",
  "artist": "Millkzy",
  "summary": {
    "overview": "one-paragraph summary of the song",
    "themes": ["love", "betrayal", "denial"],
    "emotional_tone": "melancholic, conflicted",
    "key_imagery": ["russian roulette", "a bullet to my heart"]
  },
  "judge": {
    "score": 4,
    "grounded": true,
    "missing_points": ["does not mention the religious framing in the outro"],
    "reasoning": "the summary captures the central conflict but ...",
    "verdict": "valid"
  },
  "meta": {
    "summarizer_model": "deepseek/deepseek-chat",
    "judge_model": "deepseek/deepseek-chat",
    "created_at": "2026-10-10T12:00:00Z"
  }
}
```

The combined `report.json` adds aggregates: number of songs, mean judge score,
pass rate, `grounded` rate, and the score distribution.

## CLI

```
python summarization_experiments/run_pipeline.py <report.json>
    [--limit N] [--seed S] [--song-ids IDS]
    [--summarizer-model M] [--judge-model M]
    [--no-cache] [--out DIR]
```

- `<report.json>` is a Phase 2 report (`data/report/*.json`).
- `--limit` keeps early iterations cheap by randomly sampling at most `N` songs
  (rather than taking the first `N`); pass `--seed` for a reproducible sample.
- `--song-ids` processes specific songs, comma-separated
  (`--song-ids 1,2,3`); combined with `--limit` the sample is drawn from the
  selected IDs.
- `--no-cache` forces fresh lyrics + LLM calls; `--out` overrides the results dir.

## Evaluation

- **Primary metric:** judge score (mean out of 5) and pass rate.
- **Secondary:** `grounded` rate and average number of `missing_points`.
- Because the judge is itself an LLM, this is a *self-evaluation* loop. The doc
  records that caveat and suggests later spot-checking a hand-labelled subset to
  calibrate whether the judge's scores track human judgement.

## Testing

- `tests/test_summarization_experiments.py` follows the AGENTS.md pattern: no
  network. A `FakeLLMClient` returns canned JSON, and the lyrics fetcher is
  monkeypatched.
- Covered: tolerant JSON extraction, skip logic for `[editing]`/snippet lyrics,
  the judge validity threshold, and report aggregation.
- Tests live under `tests/` so the existing `pytest` config discovers them.

## Config / docs to update

- `.env.example` — add `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` (template
  only; `.env` stays gitignored and denied to agents).
- `.gitignore` — ignore `summarization_experiments/data/` and
  `summarization_experiments/results/`.
- `docs/repo-structure.md` and `README.md` — note the experiment folder and
  Phase 3 status.
- `CHANGELOG.md` — entry for this planning doc + scaffold.

## Open questions / risks

- **Genius ToS / rate limits** — `lyricsgenius` scrapes the web; mitigate with a
  conservative `sleep_time`, caching, and not committing lyrics.
- **Copyright** — raw lyrics are stored locally and sent to the LLM. Summaries
  are transformative, but this is worth flagging explicitly.
- **Model slug & cost** — the exact OpenRouter model name and budget per run
  still need to be pinned down in `config.py`.
- **Judge reliability** — the judge prompt is the crux of the experiment; expect
  two to three prompt iterations before the scores feel trustworthy.

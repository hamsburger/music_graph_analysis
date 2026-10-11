# Changelog

Brief, reverse-chronological notes on project changes. Each entry is keyed by
the commit's short hash and labels what was added, changed, or removed.

## d66ef1b — 2026-10-11

**Added** per-era representative selection to the production package:
`SongSummarizer.select_representative` and `attach_representatives` read each
era's song tags and attach an `era["representative"]` dict (themes, tone,
reasoning), backed by a new `representative` prompt, config
(`DEFAULT_REPRESENTATIVE_MODEL`, `MAX_REPRESENTATIVES`,
`representative_model()`), and network-free tests. **Changed** `analyze_artist.py`
to run the stage after summarization with `--representative-model` and
`--skip-representatives` flags, and updated the README and docs to describe the
productionised stage.

## cd303e5 — 2026-10-11

**Added** a fourth summarization sandbox stage that has an LLM pick each era's
most representative themes and emotional tones (with reasoning), writing them
into an augmented `report_enriched.json`; includes the representative prompt,
config/CLI flags, caching, and tests. `key_imagery` continues to use
frequency-based selection. **Added** `docs/representative-selection.md`
documenting the plan, with renderer integration left pending.

## eb7aa7e — 2026-10-10

**Changed** the committed `pages/index.html` to regenerate the Pages
visualization with the new chart layout (evenly spread songs, x-jitter, hover
overviews, and bottom spacing).

## 4df56d4 — 2026-10-10

**Changed** the report page to add extra bottom spacing and clamp the hover
tooltip within the viewport (flipping it above the cursor near the bottom edge)
so tooltips are no longer cut off.

## b0c894b — 2026-10-10

**Changed** the chart layout so songs spread evenly down each era (staggered
between adjacent eras) with a small deterministic x-jitter, dropping the
pageview y-axis; circle size still encodes popularity via `sqrt(pageviews)`.

## 4b40a15 — 2026-10-10

**Added** the song's `overview` summary text to the chart hover tooltip (shown
when a summary is present), alongside the title, album, and per-dimension tags.

## 2c7ecf2 — 2026-10-10

**Added** Phase 4: `render_report.py` and the `render`/`images` modules turn
saved reports into a self-contained interactive HTML page (eras on a time axis,
album thumbnails, theme/imagery/tone toggles), **changed** `analyze_artist.py` to
write per-artist files under `data/report/` by default, and **added** a GitHub
Pages workflow that deploys the committed `pages/index.html`.

## 8db6e5a — 2026-10-10

**Added** the production lyric summarization pipeline to the package
(`config`, `llm`, `lyrics`, `naming`, `prompts`, `summarize`) and **changed**
`analyze_artist.py` to attach an LLM `summary` to every song as its final,
best-effort step (skipped without `OPENROUTER_API_KEY` or with `--no-summarize`).

## d5746be — 2026-10-10

**Changed** the summarize prompt to require a detailed overview with each claim
backed by a short lyric quote and **removed** the `narrative` field; **changed**
run outputs to a single `results.json` (`{"songs": [...]}`) instead of one JSON
file per song.

## a296539 — 2026-10-10

**Changed** both changelog skills to record what was added, changed, or removed,
and **changed** existing CHANGELOG.md and PROMPT_CHANGELOG.md entries to use the
new **Added/Changed/Removed** labels.

## f7ae6ff — 2026-10-10

**Added** the Phase 3 summarization sandbox: a lyrics → LLM summary → LLM judge
pipeline under `summarization_experiments/`, with prompt files, caching, a CLI,
and network-free tests.

## 9a0f129 — 2026-10-10

**Changed** the update-changelog skill so entries are written after the change
commit and then folded back into that same commit.

## 03e0098 — 2026-10-10

**Added** Phase 2: each selected song's relationships are now collected in both
directions (what it sampled/interpolated, and what sampled/interpolated it).

## 5b18297 — 2026-10-10

**Added** AGENTS.md documenting the repo conventions, commands, and guardrails
for coding agents.

## acee454 — 2026-10-10

**Added** the update-changelog skill and the initial CHANGELOG.md.

## 81a6cf1 — 2026-10-10

**Added** Phase 1 era analysis: an artist's songs are split into equal-length
eras and the top songs per era are selected by pageviews.

## 733932d — 2026-10-09

**Added** the Genius API module with the package skeleton, example scripts, and
client tests.

## bc5fee5 — 2026-10-09

**Added** the project README and a sample Genius API payload.

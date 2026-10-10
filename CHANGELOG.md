# Changelog

Brief, reverse-chronological notes on project changes. Each entry is keyed by
the commit's short hash and labels what was added, changed, or removed.

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

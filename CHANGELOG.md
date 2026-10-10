# Changelog

Brief, reverse-chronological notes on project changes. Each entry is keyed by
the commit's short hash.

## 400ea5b — 2026-10-10

Added the Phase 3 summarization sandbox: a lyrics → LLM summary → LLM judge
pipeline under `summarization_experiments/`, with prompt files, caching, a CLI,
and network-free tests.

## 849295d — 2026-10-10

Updated the update-changelog skill so entries are written after the change
commit and then folded back into that same commit.

## 03e0098 — 2026-10-10

Completed Phase 2: each selected song's relationships are collected in both
directions (what it sampled/interpolated, and what sampled/interpolated it).

## 5b18297 — 2026-10-10

Added AGENTS.md documenting the repo conventions, commands, and guardrails for
coding agents.

## acee454 — 2026-10-10

Added the update-changelog skill and the initial CHANGELOG.md.

## 81a6cf1 — 2026-10-10

Added Phase 1 era analysis: an artist's songs are split into equal-length eras
and the top songs per era are selected by pageviews.

## 733932d — 2026-10-09

Initial implementation of the Genius API module, with the package skeleton,
example scripts, and client tests.

## bc5fee5 — 2026-10-09

Initial push containing the project README and a sample Genius API payload.

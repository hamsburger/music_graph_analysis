# Prompt Changelog

Brief, reverse-chronological notes on changes to the Phase 3 summarization
prompt templates (`summarization_experiments/prompts/`). Each entry records what
was added, changed, or removed, why, and how the results changed as a result.

## d5746be · 2026-10-10 — summarize.txt

**Changed** `summarize.txt` to ask for a detailed, multi-sentence overview in
which every claim is backed by a short lyric quote, and **removed** the
`narrative` field from the required JSON keys.

**Effect** On the 3-song Daniel Caesar run ("Get You", "Best Part", "CYANIDE"),
mean judge score was 4.0 with a 1.0 pass rate and grounding rate; every overview
now quotes the lyrics, and the judge's `missing_points` cite specific omitted
lines instead of generic gaps.

## f7ae6ff · 2026-10-10 — both

**Added** the initial `summarize.txt` and `judge.txt` prompts for the Phase 3
sandbox: the summarizer returns strict JSON (`overview`, `themes`, `narrative`,
`emotional_tone`, `key_imagery`), and a separate judge scores the summary out of
5, checks grounding, and lists missing points.

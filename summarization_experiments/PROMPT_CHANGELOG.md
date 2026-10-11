# Prompt Changelog

Brief, reverse-chronological notes on changes to the Phase 3 summarization
prompt templates (`summarization_experiments/prompts/`). Each entry records what
was added, changed, or removed, why, and how the results changed as a result.

## 3085315 · 2026-10-11 — representative

**Added** `representative.txt`, a new fourth-stage prompt that takes every song's
already-extracted theme and emotional-tone labels for one era and asks an LLM to
pick the most representative ones (aiming for 3–4 each), merge near-duplicate
labels, and return strict JSON (`themes`, `emotional_tone`, `reasoning`). It uses
the new `{era}` and `{songs}` placeholders and explicitly forbids inventing labels
no song supports.

**Effect** Observed on the Daniel Caesar run: all six era blocks (5 eras plus the
date-less "Unknown era") now carry a `representative` object that is grounded
entirely in the song-level labels. For example Era 1 returned themes
`love, time, transformation, acceptance` and tones `reflective, passionate,
resigned`, with the reasoning naming the labels it left out (`gratitude`,
`uplifting`); each block lists 3–4 themes and 3 tones. Because the stage appends
data rather than changing summarization or judging, the aggregate metrics are
unchanged (`mean_score` 4.04, `pass_rate` 0.96, `grounded_rate` 1.0).

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

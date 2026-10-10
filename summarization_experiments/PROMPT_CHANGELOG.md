# Prompt Changelog

Brief, reverse-chronological notes on changes to the Phase 3 summarization
prompt templates (`summarization_experiments/prompts/`). Each entry records what
was added, changed, or removed, and why.

## f7ae6ff · 2026-10-10 — both

**Added** the initial `summarize.txt` and `judge.txt` prompts for the Phase 3
sandbox: the summarizer returns strict JSON (`overview`, `themes`, `narrative`,
`emotional_tone`, `key_imagery`), and a separate judge scores the summary out of
5, checks grounding, and lists missing points.

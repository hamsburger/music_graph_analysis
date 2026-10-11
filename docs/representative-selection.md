# Era representative selection (Stage 4 plan)

This document plans an additional summarization stage: for each era, take the
`themes` and `emotional_tone` labels produced for every song in that era and have
an LLM pick the **most representative** labels, with a short explanation of why
they were chosen. The result is written into the report so the Phase 4
visualization can display it.

## Motivation

Phase 4 currently labels each era with the **top tags by frequency**
(`render.era_tag_counts`), for every dimension. Frequency is a decent proxy for
`key_imagery` (concrete repeated images), but it is a poor one for `themes` and
`emotional_tone`: the most frequent tag is not necessarily the most
representative, and near-duplicate labels fragment the counts.

Stage 4 asks an LLM to read the whole era's labels at once, merge near-duplicates
and surface what actually characterises the era, and to justify the choice.

## Decisions

| Question | Choice |
| --- | --- |
| Where it lives | `summarization_experiments/` sandbox (not the package yet) |
| Granularity | One LLM call **per era**, covering `themes` and `emotional_tone` |
| Output storage | `era["representative"]` in an augmented copy of the input report |
| Label freedom | May synthesize/merge labels, grounded only in the era's song tags |
| Reasoning display | Per-era tooltip/caption in the renderer (Phase 4) |
| `key_imagery` | **Unchanged** — still top tags by frequency |

## Status

- Stage 4 (sandbox prompt + pipeline + CLI + tests): **implemented**.
- Renderer integration (`src/music_graph_analysis/render.py`): **pending** until
  the summarization output has been manually inspected.

## Pipeline stage

### Stage 4 — Representative selection

- Input: every song in one era that has a summary, reduced to its cleaned
  `themes` and `emotional_tone` labels.
- Prompt: `summarization_experiments/prompts/representative.txt`, placeholders
  `{era}` (e.g. `Era 2 (2019–2021)`) and `{songs}`.
- Output: **strict JSON** with
  `themes[]`, `emotional_tone[]`, `reasoning`.
- Normalisation (`_normalize_representative`): coerce both label fields to
  trimmed, de-duplicated string lists (splitting comma-separated strings), cap
  at `MAX_REPRESENTATIVES`, and keep `reasoning` as a string. `key_imagery` is
  intentionally never produced here.

## Prompt

`summarization_experiments/prompts/representative.txt`:

- Use only the provided labels; do not invent themes/emotions no song supports.
- May merge near-duplicate labels (e.g. "heartbreak" + "grief" -> "heartbreak").
- Pick the most representative themes and emotional tones (aim for 3–4 each),
  preferring labels shared by or central to multiple songs.
- Explain why the chosen labels best represent the era and note notable
  omissions.

## Caching

Reuses the sandbox `JsonCache` layout (see [cache.md](cache.md)):

- `{artist}/representative/era-{index}-{model_slug}-{digest}`

`{digest}` is the short SHA-256 of the rendered prompt (the exact LLM input), so
editing the prompt template or the era's song labels produces a fresh entry, and
the model slug is included so switching models never serves a stale result.
`{model_slug}` comes from `representative_model()`
(`OPENROUTER_REPRESENTATIVE_MODEL` -> `OPENROUTER_MODEL` -> default).

## Output

Stage 4 does not alter `results.json` or the aggregate `report.json`. Instead
`run_pipeline.py` writes an **augmented copy of the input report** to
`results/{artist}/report_enriched.json`:

- every era song gains its `summary` dict (needed for `key_imagery` counts and
  song tooltips), and
- every era gains `representative`:

```json
{
  "era": 1,
  "start": "2019-01-01",
  "end": "2021-01-01",
  "songs": [{ "id": 1, "title": "...", "summary": { "...": "..." } }],
  "representative": {
    "themes": ["love", "devotion", "distance"],
    "emotional_tone": ["tender", "longing"],
    "reasoning": "These labels recur across the era's three songs and ..."
  }
}
```

The report keeps the Phase 2 schema (`artist`, `eras[].songs[]`), so
`render_report.py` can read it directly with no adapter. Failed eras are
best-effort and store `{"error": "..."}` instead. With `--limit`, representative
selection only sees the processed subset of each era (documented in the CLI
help).

## CLI

```
python summarization_experiments/run_pipeline.py <report.json>
    [--limit N] [--seed S] [--song-ids IDS]
    [--summarizer-model M] [--judge-model M] [--representative-model M]
    [--skip-representatives]
    [--no-cache] [--out DIR]
```

- `--representative-model M` picks the model for Stage 4 (default
  `OPENROUTER_REPRESENTATIVE_MODEL` or `OPENROUTER_MODEL`).
- `--skip-representatives` runs only the summarize + judge stages.

## Renderer integration (pending)

Planned changes to `src/music_graph_analysis/render.py`, held until the
summarization output has been checked by hand:

- `REPRESENTATIVE_DIMENSIONS = ("themes", "emotional_tone")`.
- `era_representative(era, dimension)` -> `normalize_tags(era["representative"], dimension)`.
- In `build_chart_svg`, for `themes`/`emotional_tone` use the era's
  representative labels when present and fall back to `counts.most_common`
  otherwise; `key_imagery` always uses frequency counts.
- Surface `era["representative"]["reasoning"]` as a native SVG `<title>` on the
  era band (per-era tooltip); song tooltips stay unchanged.

## Testing

No network (AGENTS.md pattern): `FakeLLM` returns canned JSON and the lyrics
source is faked. Covered: representative parsing/normalisation (string vs list
`emotional_tone`, dedupe, cap), caching (one call; key changes with input and
prompt), `attach_summaries_to_eras`, per-era `representative` wiring, and the new
CLI flags. Renderer tests are added with the pending renderer work.

## Docs to update

- `docs/phase-3-summarization.md` — link Stage 4 and its prompt.
- `docs/repo-structure.md` — note the new prompt and sandbox output.
- `README.md` — keep the sandbox out of the main usage flow until
  productionised; no CLI change there yet.
- `CHANGELOG.md` — via the update-changelog skill when this is committed.
- `summarization_experiments/PROMPT_CHANGELOG.md` — only when explicitly asked.

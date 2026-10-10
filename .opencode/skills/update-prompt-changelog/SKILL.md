---
name: update-prompt-changelog
description: >
  Use ONLY when the user explicitly asks to update the prompt changelog,
  typically after running a summarization experiment. Do NOT trigger this
  automatically when editing prompt templates. Appends an entry recording what
  was added, changed, or removed in the prompt and why to
  summarization_experiments/PROMPT_CHANGELOG.md.
---

# Update the summarization prompt changelog

Keep `summarization_experiments/PROMPT_CHANGELOG.md` in sync with the prompt
templates. It is a short, human-readable history of *prompt* changes for the
Phase 3 summarization experiments. Each entry must make clear **what was added,
what was changed, and what was removed** — use the change-type labels below so
the nature of the change is explicit. Prompt wording is the main experimental
variable, so the rationale matters more than a raw diff. Because these prompts
are tuned against real runs, each entry must also record the **observed effect
on the data**: how the outputs or aggregate metrics shifted as a result of the
prompt change.

## When to run

- **Only** when the user explicitly asks to update or backfill the prompt
  changelog — normally after running a summarization experiment.
- Never run this automatically as a side effect of editing a prompt template.
  Editing a prompt under `summarization_experiments/prompts/` is **not** a
  trigger on its own.

When asked, record the prompt change(s) that the experiment was run against.

## Location

`summarization_experiments/PROMPT_CHANGELOG.md` — create it with a
`# Prompt Changelog` heading if it does not exist.

## Format

Reverse-chronological: newest entry at the top, directly below the heading.
Each entry is:

```markdown
## <YYYY-MM-DD> — <summarize|judge|both>

**<Added|Changed|Removed>** <one or two sentences on what changed in the prompt and why.>

**Effect** <how the results changed as a result, with concrete evidence from a run.>
```

- Date — today's date; prefix the short commit hash if the change is already
  committed (`<short-hash> · <YYYY-MM-DD>`).
- Stage — which prompt(s) changed: `summarize`, `judge`, or `both`.
- Change type — start the summary with one of the bold labels **Added**,
  **Changed**, or **Removed**. If the entry covers more than one kind of change
  (e.g. a rule was removed and another added), repeat the label for each so both
  are explicit.
- Summary — plain prose, 1-2 sentences per label. State the intent (e.g.
  "tightened the grounding rule to forbid inferred names"), not every edited
  word. If the change was a response to a run, mention the observed problem
  briefly.
- Effect — one to two sentences on the change's impact on the data, not just
  the prompt. Report concrete signals where available: judge scores, pass/valid
  rate, grounding rate, the songs/artist the run covered, and any notable shift
  in output (e.g. "overviews now quote lyrics, so missing-point complaints
  became specific"). If the effect is not yet observed (prompt changed but not
  run), say so explicitly rather than guessing.

## Steps

1. Identify which prompt files changed. If you have not already, inspect them:

   ```bash
   git diff -- summarization_experiments/prompts/
   ```

2. Gather the data effect. If a run was done, read its `results.json` /
   `report.json` (under `summarization_experiments/results/<artist>-<id>/`) and
   pull the concrete numbers — judge scores, pass/valid rate, grounding rate,
   songs covered — plus any notable shift in the summaries or judge remarks. If
   no run has happened yet, note that the effect is unobserved instead of
   inventing one.

3. Read the current `summarization_experiments/PROMPT_CHANGELOG.md` (create it
   with a `# Prompt Changelog` heading if missing).

4. Write the new entry at the top, above any existing entries. Preserve all
   existing entries exactly.

5. If this prompt change was made as part of a commit, include the commit's
   short hash (`git rev-parse --short HEAD`) in the entry and stage the
   changelog into that commit. If the commit already exists, fold the entry in
   with `git add summarization_experiments/PROMPT_CHANGELOG.md && git commit
   --amend --no-edit` — the same amend-rewrites-the-hash caveat as the main
   `CHANGELOG.md` skill applies.

## Example

```markdown
# Prompt Changelog

## a1b2c3d · 2026-10-10 — both

**Changed** the grounding rule in `summarize.txt` to forbid inferred artist
names. **Added** an instruction to `judge.txt` telling it to penalize
unsupported claims after the first run invented artist context.

**Effect** On the 3-song Daniel Caesar run, pass rate stayed 1.0 and grounding
remained true, but judge `missing_points` shifted from generic notes to specific
omitted lyric lines now that overviews quote the source.
```

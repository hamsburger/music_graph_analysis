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
variable, so the rationale matters more than a raw diff.

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

## Steps

1. Identify which prompt files changed. If you have not already, inspect them:

   ```bash
   git diff -- summarization_experiments/prompts/
   ```

2. Read the current `summarization_experiments/PROMPT_CHANGELOG.md` (create it
   with a `# Prompt Changelog` heading if missing).

3. Write the new entry at the top, above any existing entries. Preserve all
   existing entries exactly.

4. If this prompt change was made as part of a commit, include the commit's
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
```

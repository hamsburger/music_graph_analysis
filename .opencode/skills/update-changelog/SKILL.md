---
name: update-changelog
description: >
  Use whenever you create a git commit in this repo, or when the user asks to
  update/append the changelog. Appends a brief entry, keyed by the commit's
  short hash, that records what was added, changed, or removed, to the top of
  CHANGELOG.md.
---

# Update CHANGELOG on commit

Keep `CHANGELOG.md` in sync with git history: every commit gets a short,
human-readable entry keyed by its hash. Each entry must make clear **what was
added, what was changed, and what was removed** — use the change-type labels in
the format below so the nature of each change is explicit, not just the effect.

## When to run

- **After** you create a commit (`git commit ...`) on the user's behalf. Add the
  new entry for that commit, then fold the changelog change back into that same
  commit with `git commit --amend`.
- When the user explicitly asks to update or backfill the changelog.

Do **not** run this for commits the user made outside the current session unless
they ask — you cannot observe those.

## Format

`CHANGELOG.md` is reverse-chronological: newest entry at the top, under the
`# Changelog` heading. Each entry is:

```markdown
## <short-hash> — <YYYY-MM-DD>

**<Added|Changed|Removed>** <one or two sentences describing what changed and why.>
```

- `<short-hash>` — from `git rev-parse --short HEAD`.
- `<YYYY-MM-DD>` — the commit date (`git log -1 --format=%cs`).
- Change type — start the summary with one of the bold labels **Added**,
  **Changed**, or **Removed**. If a commit does more than one, repeat the label
  on each point (e.g. `**Added** ...` then `**Changed** ...`) so each is
  explicit. Prefer the labels that actually apply; do not invent removals.
- Summary — plain prose, 1-2 sentences max per label. No bullet lists. Describe
  the user-visible effect, not every file touched.

## Steps

1. Create the change commit **first**; do not touch `CHANGELOG.md` yet.

2. Read the commit you just created:

   ```bash
   git rev-parse --short HEAD
   git log -1 --format='%cs%n%s%n%b'
   ```

   Inspect the diff stat for context if the subject is vague:

   ```bash
   git show --stat --oneline HEAD
   ```

3. Read the current `CHANGELOG.md` (create it with a `# Changelog` heading if
   it does not exist).

4. Insert the new entry for that commit directly below the `# Changelog`
   heading, above any existing entries. Preserve all existing entries exactly.

5. Fold the changelog update back into the commit it documents:

   ```bash
   git add CHANGELOG.md
   git commit --amend --no-edit
   ```

6. Because `--amend` rewrites the commit hash, the hash you recorded in step 4
   no longer matches HEAD. This is expected: while you are here, fix any earlier
   entry whose hash is now superseded, and on the next run correct the entry you
   just added.

## Example

```markdown
# Changelog

## 400ea5b — 2026-10-10

**Added** the Phase 3 summarization sandbox under
`summarization_experiments/`, with prompt files, caching, a CLI, and
network-free tests. **Changed** the README to document the new commands.

## 81a6cf1 — 2026-10-10

**Added** the Phase 1 era analysis: an artist's songs are split into
equal-length eras and the top songs per era are selected by pageviews.

## bc5fee5 — 2026-10-09

**Added** the initial Genius API client, example scripts, and a sample payload.
```

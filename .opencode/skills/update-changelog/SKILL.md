---
name: update-changelog
description: >
  Use whenever you create a git commit in this repo, or when the user asks to
  update/append the changelog. Appends a brief 1-2 sentence summary of the
  change, keyed by the commit's short hash, to the top of CHANGELOG.md.
---

# Update CHANGELOG on commit

Keep `CHANGELOG.md` in sync with git history: every commit gets a short,
human-readable entry keyed by its hash.

## When to run

- When you intend to and before you create a commit (`git commit ...`) on
  the user's behalf. Also fold this CHANGELOG into the same commit.
- When the user explicitly asks to update or backfill the changelog.

Do **not** run this for commits the user made outside the current session unless
they ask — you cannot observe those.

## Format

`CHANGELOG.md` is reverse-chronological: newest entry at the top, under the
`# Changelog` heading. Each entry is:

```markdown
## <short-hash> — <YYYY-MM-DD>

<One or two sentences describing what changed and why.>
```

- `<short-hash>` — from `git rev-parse --short HEAD`.
- `<YYYY-MM-DD>` — the commit date (`git log -1 --format=%cs`).
- Summary — plain prose, 1-2 sentences max. No bullet lists. Describe the
  user-visible effect, not every file touched.

## Steps

1. Read the commit you just created:

   ```bash
   git rev-parse --short HEAD
   git log -1 --format='%cs%n%s%n%b'
   ```

   Inspect the diff stat for context if the subject is vague:

   ```bash
   git show --stat --oneline HEAD
   ```

2. Read the current `CHANGELOG.md` (create it with a `# Changelog` heading if
   it does not exist).

3. Insert the new entry directly below the `# Changelog` heading, above any
   existing entries. Preserve all existing entries exactly.

4. Do not commit the changelog update unless the user asks; leave it as a
   working-tree change they can review, or amend it into the same commit only
   if the user explicitly requests an amend.

## Example

```markdown
# Changelog

## 81a6cf1 — 2026-10-10

Added the Phase 1 era analysis: artist songs are split into equal-length eras
and the top songs per era are selected by pageviews.

## bc5fee5 — 2026-10-09

Initial push with the Genius API client and example scripts.
```

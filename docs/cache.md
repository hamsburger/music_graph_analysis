# Response cache

The Genius API is rate-limited and slow, so every response used during an
analysis is cached on disk under `data/cache/`. Re-running an analysis reads the
cache instead of re-hitting the API, which keeps iterations fast and avoids
hammering Genius during development.

## Layout

Cache keys are **human-readable, slash-separated paths**. Each path segment is
slugified (lowercased, non-alphanumeric characters collapsed to `-`) and mapped
to a nested folder, with a `.json` extension on the final segment:

```
key:  "{artist-name}-{artist-id}/discography"
key:  "{artist-name}-{artist-id}/songs/{song-id}"
key:  "{artist-name}-{artist-id}/relationships/{song-title}-{song-id}"
key:  "{artist-name}-{artist-id}/summaries/{song-title}-{song-id}-{model}-{digest}"
```

which produces, for example:

```
data/cache/
└── kanye-west-123/
    ├── discography.json
    ├── songs/
    │   └── 456.json
    ├── relationships/
    │   ├── stronger-456.json
    │   └── power-789.json
    ├── lyrics/
    │   └── stronger-456.json
    └── summaries/
        └── stronger-456-deepseek-deepseek-chat-1a2b3c4d5e6f.json
```

Each artist therefore gets its own folder, and each cached response lives
beside the artist it belongs to. This makes the cache easy to browse and
inspect by hand instead of dealing with opaque hash filenames.

## What gets cached

| Key path | Source | Used for |
| --- | --- | --- |
| `{artist}/discography` | `GET /artists/{id}/songs` (paged) | The artist's full song list. |
| `{artist}/songs/{song}` | `GET /songs/{id}` | Per-song album name (the list endpoint omits it). |
| `{artist}/relationships/{song}` | `GET /songs/{id}` | A song's samples / sampled_in / interpolates / interpolated_by. |
| `{artist}/lyrics/{song}` | `lyricsgenius` scrape | Raw lyrics for a song. |
| `{artist}/summaries/{song}-{model}-{digest}` | OpenRouter chat completion | The LLM summary of a song's lyrics. |

When no artist context is available, relationship responses fall back to a
shared `songs/` folder (`songs/relationships/{song}.json`).

For summaries, `{digest}` is a short SHA-256 of the **rendered prompt**
(lyrics + `summarize.txt`) and `{model}` is the summarizer slug, so editing the
prompt or switching models produces a fresh entry rather than a stale hit.

## Behaviour

- **Reads** (`JsonCache.get`) return `None` on a miss or if the file is
  unreadable/corrupt, so a broken entry simply triggers a fresh fetch.
- **Writes** (`JsonCache.set`) are atomic: they write to a `.tmp` file and then
  rename it into place, so a crash mid-write can't leave a half-written JSON
  file.
- **Clearing** (`JsonCache.clear`) recursively deletes every cached `.json`
  file and the directories that held them.

The cache is enabled by default (`data/cache/`, configurable). Pass
`--no-cache` or `--cache-dir DIR` to `analyze_artist.py` to disable it or move
it. The directory is gitignored, so cached responses are never committed.

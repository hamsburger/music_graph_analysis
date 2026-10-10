import json

import pytest

from music_graph_analysis.cache import JsonCache
from music_graph_analysis.config import DEFAULT_PROMPTS_DIR
from music_graph_analysis.llm import LLMError
from music_graph_analysis.prompts import render
from music_graph_analysis.summarize import (
    SongSummarizer,
    attach_summaries,
    clean_lyrics,
    extract_json,
)


class FakeLLM:
    """Returns queued responses and records every call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, prompt, *, model, system=None, temperature=0.0, max_tokens=None):
        self.calls.append({"model": model, "prompt": prompt})
        if not self.responses:
            raise LLMError("no queued response")
        return self.responses.pop(0)


class FakeLyricsSource:
    def __init__(self, lyrics_by_id):
        self.lyrics_by_id = lyrics_by_id
        self.calls = 0

    def get_lyrics(self, song_id, *, artist_id=None, artist_name=None, title=None):
        self.calls += 1
        return {
            "song_id": song_id,
            "title": title,
            "artist": artist_name,
            "lyrics": self.lyrics_by_id.get(song_id, ""),
        }


SUMMARY_JSON = json.dumps(
    {
        "overview": "A song about a relationship.",
        "themes": ["love"],
        "emotional_tone": "melancholic",
        "key_imagery": ["rain"],
    }
)


def build_summarizer(llm, lyrics_source, cache=None, prompts_dir=DEFAULT_PROMPTS_DIR):
    return SongSummarizer(
        llm,
        lyrics_source,
        cache=cache,
        prompts_dir=prompts_dir,
        summarizer_model="test/summarizer",
    )


def test_clean_lyrics_rejects_empty_editing_and_snippet():
    assert clean_lyrics("") is None
    assert clean_lyrics(None) is None
    assert clean_lyrics("[editing]") is None
    assert clean_lyrics("[Snippet]\nAnd from a third person...") is None


def test_clean_lyrics_keeps_normal_lyrics():
    assert clean_lyrics("  [Verse]\nHello world  ") == "[Verse]\nHello world"


def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"score": 3}\n```') == {"score": 3}
    assert extract_json('Here:\n{"score": 5}\nDone') == {"score": 5}


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_render_leaves_json_braces_untouched():
    assert render('Return {"score": 1} using {lyrics}', lyrics="X") == (
        'Return {"score": 1} using X'
    )


def test_summarize_parses_llm_json():
    llm = FakeLLM([SUMMARY_JSON])
    summarizer = build_summarizer(llm, FakeLyricsSource({}))

    summary = summarizer.summarize(1, "some lyrics", title="Song")

    assert summary["themes"] == ["love"]
    assert llm.calls[0]["model"] == "test/summarizer"


def test_summarize_song_fetches_lyrics_and_returns_summary():
    llm = FakeLLM([SUMMARY_JSON])
    lyrics = FakeLyricsSource({1: "[Verse]\nreal lyrics"})
    summarizer = build_summarizer(llm, lyrics)

    summary = summarizer.summarize_song({"id": 1, "title": "Song"})

    assert summary["overview"] == "A song about a relationship."
    assert lyrics.calls == 1


def test_summarize_song_returns_none_without_lyrics():
    llm = FakeLLM([])
    summarizer = build_summarizer(llm, FakeLyricsSource({1: "[editing]"}))

    assert summarizer.summarize_song({"id": 1, "title": "Empty"}) is None
    assert llm.calls == []


def test_cache_prevents_duplicate_llm_calls(tmp_path):
    llm = FakeLLM([SUMMARY_JSON])
    summarizer = build_summarizer(llm, FakeLyricsSource({}), cache=JsonCache(tmp_path))

    summarizer.summarize(1, "lyrics", title="Song")
    summarizer.summarize(1, "lyrics", title="Song")

    assert len(llm.calls) == 1


def test_cache_key_changes_with_lyrics(tmp_path):
    llm = FakeLLM([SUMMARY_JSON, SUMMARY_JSON])
    summarizer = build_summarizer(llm, FakeLyricsSource({}), cache=JsonCache(tmp_path))

    summarizer.summarize(1, "lyrics one", title="Song")
    summarizer.summarize(1, "lyrics two", title="Song")

    assert len(llm.calls) == 2


def test_cache_key_changes_with_prompt(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "summarize.txt").write_text("v1 {lyrics}", encoding="utf-8")

    llm = FakeLLM([SUMMARY_JSON, SUMMARY_JSON])
    summarizer = build_summarizer(
        llm, FakeLyricsSource({}), cache=JsonCache(tmp_path / "cache"), prompts_dir=prompts_dir
    )

    summarizer.summarize(1, "lyrics", title="Song")
    (prompts_dir / "summarize.txt").write_text("v2 {lyrics}", encoding="utf-8")
    summarizer.summarize(1, "lyrics", title="Song")

    assert len(llm.calls) == 2


def make_result():
    return {
        "artist": {"id": 9, "name": "Artist"},
        "eras": [
            {
                "era": 0,
                "songs": [
                    {"id": 1, "title": "One"},
                    {"id": 2, "title": "Two"},
                ],
            }
        ],
    }


def test_attach_summaries_sets_summary_on_every_song():
    llm = FakeLLM([SUMMARY_JSON, SUMMARY_JSON])
    lyrics = FakeLyricsSource({1: "[Verse]\na", 2: "[Verse]\nb"})
    summarizer = build_summarizer(llm, lyrics)

    result = attach_summaries(make_result(), summarizer)

    summaries = [song["summary"] for era in result["eras"] for song in era["songs"]]
    assert all(s and s["themes"] == ["love"] for s in summaries)
    assert lyrics.calls == 2


def test_attach_summaries_sets_none_when_lyrics_missing():
    llm = FakeLLM([])
    summarizer = build_summarizer(llm, FakeLyricsSource({}))

    result = attach_summaries(make_result(), summarizer)

    assert all(
        song["summary"] is None for era in result["eras"] for song in era["songs"]
    )


def test_attach_summaries_does_not_abort_on_error():
    llm = FakeLLM([])  # raises LLMError when asked to summarize
    lyrics = FakeLyricsSource({1: "[Verse]\na", 2: "[Verse]\nb"})
    summarizer = build_summarizer(llm, lyrics)

    result = attach_summaries(make_result(), summarizer)

    songs = [song for era in result["eras"] for song in era["songs"]]
    assert [song["summary"] for song in songs] == [None, None]

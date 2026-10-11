import json

import pytest

from music_graph_analysis.cache import JsonCache
from summarization_experiments.config import DEFAULT_PROMPTS_DIR
from summarization_experiments.pipeline import (
    SummarizationPipeline,
    _normalize_representative,
    aggregate,
    clean_lyrics,
    extract_json,
)
from summarization_experiments.prompts import render
from summarization_experiments.run_pipeline import (
    add_representatives,
    attach_summaries_to_eras,
    build_parser,
    parse_song_ids,
    select_songs,
)


class FakeLLM:
    """Returns queued responses and records every call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, prompt, *, model, system=None, temperature=0.0, max_tokens=None):
        self.calls.append({"model": model, "prompt": prompt})
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

JUDGE_JSON = json.dumps(
    {
        "score": 4,
        "grounded": True,
        "missing_points": ["misses the second verse"],
        "reasoning": "mostly accurate",
        "verdict": "valid",
    }
)

REPRESENTATIVE_JSON = json.dumps(
    {
        "themes": ["love", "Devotion", "love"],
        "emotional_tone": ["tender", "longing"],
        "reasoning": "These recur across the era.",
    }
)

ERA_SONGS = [
    {
        "id": 1,
        "title": "A",
        "summary": {"themes": ["love", "loss"], "emotional_tone": "tender, sad"},
    },
    {"id": 2, "title": "B", "summary": {"themes": ["love"], "emotional_tone": "longing"}},
]


def build_pipeline(llm, lyrics_source, cache=None):
    return SummarizationPipeline(
        llm,
        lyrics_source,
        cache=cache,
        prompts_dir=DEFAULT_PROMPTS_DIR,
        summarizer_model="test/summarizer",
        judge_model="test/judge",
        representative_model="test/representative",
    )


def test_clean_lyrics_rejects_empty_and_editing():
    assert clean_lyrics("") is None
    assert clean_lyrics(None) is None
    assert clean_lyrics("[editing]") is None


def test_clean_lyrics_rejects_snippet_only():
    assert clean_lyrics("[Snippet]\nAnd from a third person...") is None


def test_clean_lyrics_keeps_normal_lyrics():
    assert clean_lyrics("  [Verse]\nHello world  ") == "[Verse]\nHello world"


def test_extract_json_handles_code_fences():
    text = "```json\n{\"score\": 3}\n```"
    assert extract_json(text) == {"score": 3}


def test_extract_json_handles_surrounding_prose():
    text = "Here is the result:\n{\"score\": 5}\nHope that helps."
    assert extract_json(text) == {"score": 5}


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_render_leaves_json_braces_untouched():
    template = 'Return {"score": 1} using {lyrics}'
    assert render(template, lyrics="HELLO") == 'Return {"score": 1} using HELLO'


def test_pipeline_summarizes_and_judges():
    llm = FakeLLM([SUMMARY_JSON, JUDGE_JSON])
    pipeline = build_pipeline(llm, FakeLyricsSource({}))

    summary = pipeline.summarize(1, "some lyrics", title="Song")
    judged = pipeline.judge(1, "some lyrics", summary, title="Song")

    assert summary["themes"] == ["love"]
    assert judged["score"] == 4
    assert judged["grounded"] is True
    assert judged["verdict"] == "valid"
    assert llm.calls[0]["model"] == "test/summarizer"
    assert llm.calls[1]["model"] == "test/judge"


def test_judge_enforces_threshold_over_model_verdict():
    response = json.dumps(
        {"score": 3, "grounded": True, "missing_points": [], "verdict": "valid"}
    )
    llm = FakeLLM([response])
    pipeline = build_pipeline(llm, FakeLyricsSource({}))

    judged = pipeline.judge(1, "lyrics", {"overview": "x"})

    assert judged["score"] == 3
    assert judged["verdict"] == "invalid"


def test_judge_invalid_when_not_grounded():
    response = json.dumps({"score": 5, "grounded": False, "missing_points": []})
    llm = FakeLLM([response])
    pipeline = build_pipeline(llm, FakeLyricsSource({}))

    assert pipeline.judge(1, "lyrics", {"overview": "x"})["verdict"] == "invalid"


def test_process_song_skips_when_no_lyrics():
    llm = FakeLLM([])
    pipeline = build_pipeline(llm, FakeLyricsSource({1: "[editing]"}))

    record = pipeline.process_song({"id": 1, "title": "Empty"})

    assert record["skipped"] is True
    assert record["reason"] == "no usable lyrics"
    assert llm.calls == []


def test_process_song_runs_full_pipeline():
    llm = FakeLLM([SUMMARY_JSON, JUDGE_JSON])
    lyrics = FakeLyricsSource({1: "[Verse]\nreal lyrics"})
    pipeline = build_pipeline(llm, lyrics)

    record = pipeline.process_song(
        {"id": 1, "title": "Song", "artist": "Artist", "artist_id": 9}
    )

    assert record["skipped"] is False
    assert record["summary"]["themes"] == ["love"]
    assert record["judge"]["verdict"] == "valid"
    assert record["meta"]["summarizer_model"] == "test/summarizer"
    assert lyrics.calls == 1


def test_cache_prevents_duplicate_llm_calls(tmp_path):
    llm = FakeLLM([SUMMARY_JSON])
    cache = JsonCache(tmp_path)
    pipeline = build_pipeline(llm, FakeLyricsSource({}), cache=cache)

    pipeline.summarize(1, "lyrics", title="Song")
    pipeline.summarize(1, "lyrics", title="Song")

    assert len(llm.calls) == 1


def test_cache_key_changes_with_lyrics(tmp_path):
    llm = FakeLLM([SUMMARY_JSON, SUMMARY_JSON])
    cache = JsonCache(tmp_path)
    pipeline = build_pipeline(llm, FakeLyricsSource({}), cache=cache)

    pipeline.summarize(1, "lyrics one", title="Song")
    pipeline.summarize(1, "lyrics two", title="Song")

    assert len(llm.calls) == 2


def test_cache_key_changes_with_prompt(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "summarize.txt").write_text("v1 {lyrics}", encoding="utf-8")
    (prompts_dir / "judge.txt").write_text("judge {lyrics} {summary}", encoding="utf-8")

    llm = FakeLLM([SUMMARY_JSON, SUMMARY_JSON])
    pipeline = SummarizationPipeline(
        llm,
        FakeLyricsSource({}),
        cache=JsonCache(tmp_path / "cache"),
        prompts_dir=prompts_dir,
        summarizer_model="test/summarizer",
        judge_model="test/judge",
    )

    pipeline.summarize(1, "lyrics", title="Song")
    (prompts_dir / "summarize.txt").write_text("v2 {lyrics}", encoding="utf-8")
    pipeline.summarize(1, "lyrics", title="Song")

    assert len(llm.calls) == 2


def test_judge_cache_key_changes_with_summary(tmp_path):
    llm = FakeLLM([JUDGE_JSON, JUDGE_JSON])
    cache = JsonCache(tmp_path)
    pipeline = build_pipeline(llm, FakeLyricsSource({}), cache=cache)

    pipeline.judge(1, "lyrics", {"overview": "a"}, title="Song")
    pipeline.judge(1, "lyrics", {"overview": "b"}, title="Song")

    assert len(llm.calls) == 2


SONGS = [{"id": n, "title": f"Song {n}"} for n in range(1, 6)]


def test_parse_song_ids_accepts_comma_separated():
    assert parse_song_ids("1,2,3") == [1, 2, 3]


def test_parse_song_ids_ignores_blanks_and_spaces():
    assert parse_song_ids(" 1, 2 ,3 ") == [1, 2, 3]


def test_parse_song_ids_rejects_non_numeric():
    with pytest.raises(Exception):
        parse_song_ids("1,two")


def test_build_parser_parses_song_ids():
    args = build_parser().parse_args(["report.json", "--song-ids", "4,5"])

    assert args.song_ids == [4, 5]


def test_select_songs_filters_multiple_ids():
    assert [s["id"] for s in select_songs(SONGS, song_ids=[1, 3])] == [1, 3]


def test_select_songs_ignores_unknown_ids():
    assert [s["id"] for s in select_songs(SONGS, song_ids=[99])] == []


def test_select_songs_limit_is_reproducible_and_ordered():
    first = select_songs(SONGS, limit=2, seed=42)
    second = select_songs(SONGS, limit=2, seed=42)

    assert first == second
    assert len(first) == 2
    assert [s["id"] for s in first] == sorted(s["id"] for s in first)


def test_select_songs_limit_larger_than_list_keeps_all():
    assert select_songs(SONGS, limit=10) == SONGS


def test_select_songs_applies_ids_before_limit():
    songs = select_songs(SONGS, song_ids=[2, 4], limit=1, seed=1)

    assert len(songs) == 1
    assert songs[0]["id"] in {2, 4}


def test_aggregate_metrics():
    records = [
        {"skipped": False, "judge": {"score": 5, "grounded": True, "verdict": "valid"}},
        {"skipped": False, "judge": {"score": 3, "grounded": True, "verdict": "invalid"}},
        {"skipped": True, "reason": "no usable lyrics"},
    ]
    report = aggregate(records)

    assert report["songs_total"] == 3
    assert report["songs_processed"] == 2
    assert report["songs_skipped"] == 1
    assert report["mean_score"] == 4.0
    assert report["pass_rate"] == 0.5
    assert report["grounded_rate"] == 1.0
    assert report["score_distribution"]["5"] == 1


def test_normalize_representative_coerces_string_tone():
    result = _normalize_representative(
        {
            "themes": "love, loss , love",
            "emotional_tone": "Tender",
            "reasoning": "  because  ",
        }
    )

    assert result["themes"] == ["love", "loss"]
    assert result["emotional_tone"] == ["Tender"]
    assert result["reasoning"] == "because"


def test_normalize_representative_caps_labels():
    result = _normalize_representative({"themes": ["a", "b", "c", "d", "e", "f"]})

    assert result["themes"] == ["a", "b", "c", "d"]
    assert result["emotional_tone"] == []


def test_select_representative_parses_and_normalizes():
    llm = FakeLLM([REPRESENTATIVE_JSON])
    pipeline = build_pipeline(llm, FakeLyricsSource({}))

    result = pipeline.select_representative(
        ERA_SONGS, era_label="Era 1 (2019–2021)", era_index=0
    )

    assert result["themes"] == ["love", "Devotion"]
    assert result["emotional_tone"] == ["tender", "longing"]
    assert result["reasoning"] == "These recur across the era."
    assert "key_imagery" not in result
    assert llm.calls[0]["model"] == "test/representative"
    assert "themes=[love; loss]" in llm.calls[0]["prompt"]


def test_select_representative_cache_prevents_duplicate_calls(tmp_path):
    llm = FakeLLM([REPRESENTATIVE_JSON])
    cache = JsonCache(tmp_path)
    pipeline = build_pipeline(llm, FakeLyricsSource({}), cache=cache)

    pipeline.select_representative(ERA_SONGS, era_label="Era 1", era_index=0)
    pipeline.select_representative(ERA_SONGS, era_label="Era 1", era_index=0)

    assert len(llm.calls) == 1


def test_attach_summaries_to_eras_does_not_mutate_input():
    report = {
        "artist": {"id": 9, "name": "Artist"},
        "eras": [
            {
                "era": 0,
                "start": "2019-01-01",
                "end": "2020-01-01",
                "songs": [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}],
            }
        ],
    }
    records = [
        {"song_id": 1, "summary": {"themes": ["love"]}},
        {"song_id": 2, "skipped": True, "reason": "no usable lyrics"},
    ]

    enriched = attach_summaries_to_eras(report, records)

    assert enriched["eras"][0]["songs"][0]["summary"] == {"themes": ["love"]}
    assert "summary" not in enriched["eras"][0]["songs"][1]
    assert "summary" not in report["eras"][0]["songs"][0]


def test_add_representatives_per_era():
    report = {
        "artist": {"id": 9, "name": "Artist"},
        "eras": [
            {
                "era": 0,
                "start": "2019-01-01",
                "end": "2020-01-01",
                "songs": [
                    {
                        "id": 1,
                        "title": "A",
                        "summary": {"themes": ["love"], "emotional_tone": "tender"},
                    }
                ],
            },
            {"era": 1, "start": "2020-01-01", "end": "2021-01-01", "songs": []},
        ],
    }
    llm = FakeLLM([REPRESENTATIVE_JSON])
    pipeline = build_pipeline(llm, FakeLyricsSource({}))

    add_representatives(report, pipeline)

    assert report["eras"][0]["representative"]["themes"] == ["love", "Devotion"]
    assert "representative" not in report["eras"][1]
    assert len(llm.calls) == 1


def test_add_representatives_records_errors():
    report = {
        "artist": {"id": 9, "name": "Artist"},
        "eras": [
            {
                "era": 0,
                "songs": [{"id": 1, "title": "A", "summary": {"themes": ["love"]}}],
            }
        ],
    }
    llm = FakeLLM(["not json at all"])
    pipeline = build_pipeline(llm, FakeLyricsSource({}))

    add_representatives(report, pipeline)

    assert "error" in report["eras"][0]["representative"]


def test_build_parser_parses_representative_flags():
    args = build_parser().parse_args(
        ["report.json", "--representative-model", "x/y", "--skip-representatives"]
    )

    assert args.representative_model == "x/y"
    assert args.skip_representatives is True

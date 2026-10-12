import base64
import re

from music_graph_analysis.cache import JsonCache
from music_graph_analysis.images import ImageFetcher
from music_graph_analysis.render import (
    JITTER_MAX,
    _jitter_for_song,
    _song_y,
    build_chart_svg,
    era_dimension_tags,
    era_representative,
    era_tag_counts,
    normalize_tags,
    render_html,
)


def make_summary(themes=None, imagery=None, tone=None, overview=None):
    return {
        "overview": overview,
        "themes": themes or [],
        "key_imagery": imagery or [],
        "emotional_tone": tone,
    }


def make_result(artist_id=42, name="Test Artist"):
    return {
        "artist": {"id": artist_id, "name": name, "url": "https://x"},
        "span": {"start": "2000-01-01", "end": "2004-01-01", "n_eras": 2},
        "eras": [
            {
                "era": 0,
                "label": "Era 1",
                "start": "2000-01-01",
                "end": "2002-01-01",
                "total_samples": 1,
                "songs": [
                    {
                        "id": 1,
                        "title": "Early Hit",
                        "release_date": "2000-06-01",
                        "pageviews": 100,
                        "album": "Debut",
                        "summary": make_summary(
                            ["Love", "loss"], ["rain"], "Melancholic, sad"
                        ),
                    },
                    {
                        "id": 2,
                        "title": "Early B",
                        "release_date": "2001-06-01",
                        "pageviews": 50,
                        "summary": make_summary(["love"], [], "hopeful"),
                    },
                ],
            },
            {
                "era": 1,
                "label": "Era 2",
                "start": "2002-01-01",
                "end": "2004-01-01",
                "total_samples": 0,
                "songs": [
                    {
                        "id": 3,
                        "title": "Late Hit",
                        "release_date": "2003-06-01",
                        "pageviews": 500,
                        "summary": make_summary(["loss"], ["fire"], "angry"),
                    }
                ],
            },
            {
                "era": "unknown",
                "label": "Unknown era",
                "start": None,
                "end": None,
                "total_samples": 0,
                "songs": [
                    {
                        "id": 4,
                        "title": "Undated",
                        "release_date": None,
                        "pageviews": 10,
                        "summary": None,
                    }
                ],
            },
        ],
    }


def test_normalize_tags_keeps_list_values():
    summary = make_summary(["love", "loss"])
    assert normalize_tags(summary, "themes") == ["love", "loss"]


def test_normalize_tags_splits_emotional_tone_string():
    summary = make_summary(tone="Melancholic, Conflicted, melancholic")
    assert normalize_tags(summary, "emotional_tone") == [
        "melancholic",
        "conflicted",
    ]


def test_normalize_tags_strips_quotes_and_whitespace():
    summary = make_summary(imagery=["'the coffee I need'", "  rain  "])
    assert normalize_tags(summary, "key_imagery") == [
        "the coffee i need",
        "rain",
    ]


def test_normalize_tags_handles_missing_summary():
    assert normalize_tags(None, "themes") == []
    assert normalize_tags({}, "themes") == []


def test_era_tag_counts_aggregates_across_songs():
    era = make_result()["eras"][0]
    counts = era_tag_counts(era, "themes")
    assert counts["love"] == 2
    assert counts["loss"] == 1


def test_era_representative_reads_and_cleans_labels():
    era = make_result()["eras"][0]
    era["representative"] = {
        "themes": ["Devotion", "love", "love"],
        "emotional_tone": ["Tender", "longing"],
        "reasoning": "why",
    }
    assert era_representative(era, "themes") == ["devotion", "love"]
    assert era_representative(era, "emotional_tone") == ["tender", "longing"]


def test_era_representative_empty_without_selection():
    era = make_result()["eras"][0]
    assert era_representative(era, "themes") == []
    era["representative"] = {"error": "boom"}
    assert era_representative(era, "themes") == []


def test_era_dimension_tags_prefers_representative():
    era = make_result()["eras"][0]
    era["representative"] = {"themes": ["yearning", "distance"]}
    assert era_dimension_tags(era, "themes") == ["yearning", "distance"]


def test_era_dimension_tags_caps_representative():
    era = make_result()["eras"][0]
    era["representative"] = {"themes": ["a", "b", "c", "d", "e"]}
    assert era_dimension_tags(era, "themes", max_tags=3) == ["a", "b", "c"]


def test_era_dimension_tags_falls_back_when_dimension_absent():
    era = make_result()["eras"][0]
    assert era_dimension_tags(era, "themes") == ["love", "loss"]
    era["representative"] = {"themes": ["yearning"]}
    assert era_dimension_tags(era, "key_imagery") == ["rain"]


def test_build_chart_svg_uses_representative_labels():
    result = make_result()
    result["eras"][0]["representative"] = {
        "themes": ["yearning"],
        "emotional_tone": ["wistful"],
        "reasoning": "These recur.",
    }
    svg = build_chart_svg(result, {})
    assert ">yearning</text>" in svg
    assert ">wistful</text>" in svg
    assert ">love</text>" not in svg


def test_build_chart_svg_falls_back_to_frequency_tags():
    svg = build_chart_svg(make_result(), {})
    assert ">love</text>" in svg


def test_build_chart_svg_key_imagery_ignores_representative():
    result = make_result()
    result["eras"][0]["representative"] = {
        "themes": ["yearning"],
        "key_imagery": ["a made up image"],
        "reasoning": "x",
    }
    svg = build_chart_svg(result, {})
    assert ">rain</text>" in svg
    assert "a made up image" not in svg


def test_build_chart_svg_era_band_shows_reasoning_title():
    result = make_result()
    result["eras"][0]["representative"] = {
        "themes": ["yearning"],
        "reasoning": "These labels recur across the era.",
    }
    svg = build_chart_svg(result, {})
    assert "<title>These labels recur across the era.</title>" in svg


def test_build_chart_svg_omits_reasoning_title_when_absent():
    svg = build_chart_svg(make_result(), {})
    assert "<title>" not in svg


def test_build_chart_svg_embeds_album_art():
    images = {1: "data:image/png;base64,AAAA"}
    svg = build_chart_svg(make_result(), images)
    assert svg.startswith("<svg")
    assert "<clipPath" in svg
    assert 'href="data:image/png;base64,AAAA"' in svg
    assert svg.count("<image") == 1


def test_build_chart_svg_marks_unknown_band():
    svg = build_chart_svg(make_result(), {})
    assert "Unknown" in svg
    assert "rain" in svg


def test_build_chart_svg_escapes_artist_name():
    result = make_result(name="Bad <script> & Co")
    svg = build_chart_svg(result, {})
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_render_html_single_artist_hides_artist_select():
    page = render_html([make_result()], {})
    assert page.startswith("<!DOCTYPE html>")
    assert 'id="dimension-select"' in page
    assert 'id="artist-select"' not in page
    assert page.count('class="chart"') == 1
    assert page.count('class="dim-tags"') == 3


def test_render_html_multi_artist_adds_artist_select():
    artists = [make_result(1, "One"), make_result(2, "Two")]
    page = render_html(artists, {})
    assert 'id="artist-select"' in page
    assert page.count('class="chart"') == 2
    assert page.count('class="dim-tags"') == 6
    assert 'data-artist="1"' in page
    assert 'data-artist="2"' in page


def test_build_chart_svg_adds_tooltip_attributes():
    svg = build_chart_svg(make_result(), {})
    assert 'data-song-title="Early Hit"' in svg
    assert 'data-album="Debut"' in svg
    assert 'data-themes="love, loss"' in svg
    assert 'data-key-imagery="rain"' in svg
    assert 'data-emotional-tone="melancholic, sad"' in svg


def test_build_chart_svg_omits_album_when_missing():
    svg = build_chart_svg(make_result(), {})
    assert svg.count("data-album=") == 1


def test_build_chart_svg_emits_overview_attribute():
    result = make_result()
    result["eras"][0]["songs"][0]["summary"] = make_summary(
        ["love"], ["rain"], "melancholic", overview="A song about yearning."
    )
    svg = build_chart_svg(result, {})
    assert 'data-overview="A song about yearning."' in svg


def test_build_chart_svg_omits_overview_when_missing():
    svg = build_chart_svg(make_result(), {})
    assert "data-overview=" not in svg


def test_build_chart_svg_tag_labels_omit_counts():
    svg = build_chart_svg(make_result(), {})
    assert ">love</text>" in svg
    assert " (2)" not in svg


def test_song_y_spreads_songs_evenly_within_era():
    count = 4
    ys = [
        _song_y(era_index=0, song_index=i, count=count, top=0.0, height=100.0)
        for i in range(count)
    ]
    assert len(set(ys)) == count
    gaps = [round(b - a, 6) for a, b in zip(ys, ys[1:])]
    assert len(set(gaps)) == 1


def test_song_y_staggers_adjacent_eras():
    even = _song_y(era_index=0, song_index=0, count=3, top=0.0, height=100.0)
    odd = _song_y(era_index=1, song_index=0, count=3, top=0.0, height=100.0)
    assert even != odd


def test_build_chart_svg_spreads_era_songs_vertically():
    svg = build_chart_svg(make_result(), {})
    cys = re.findall(r'cy="([0-9.]+)"', svg)
    assert len(cys) == 4
    assert cys[0] != cys[1]


def test_build_chart_svg_drops_pageview_y_axis():
    svg = build_chart_svg(make_result(), {})
    assert "Pageviews" not in svg


def test_build_chart_svg_x_jitter_is_deterministic():
    assert build_chart_svg(make_result(), {}) == build_chart_svg(make_result(), {})


def test_jitter_for_song_is_deterministic_and_bounded():
    song = {"id": 7}
    value = _jitter_for_song(song)
    assert value == _jitter_for_song(song)
    assert -JITTER_MAX <= value <= JITTER_MAX



def test_render_html_includes_tooltip_element():
    page = render_html([make_result()], {})
    assert 'id="tooltip"' in page
    assert 'class="song"' in page


def test_render_html_adds_bottom_space_for_tooltips():
    page = render_html([make_result()], {})
    assert "padding: 8px 20px 120px" in page


def test_render_html_clamps_tooltip_vertically():
    page = render_html([make_result()], {})
    assert "tooltip.offsetHeight" in page
    assert "window.innerHeight" in page


class FakeResponse:
    def __init__(self, content=b"abc", content_type="image/png"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        return None


def test_image_fetcher_returns_data_uri():
    calls = []

    def fake_fetch(url, timeout=None):
        calls.append(url)
        return FakeResponse()

    fetcher = ImageFetcher(fetch=fake_fetch)
    uri = fetcher.data_uri("https://images.genius.com/x.png")
    expected = base64.b64encode(b"abc").decode("ascii")
    assert uri == f"data:image/png;base64,{expected}"
    assert calls == ["https://images.genius.com/x.png"]


def test_image_fetcher_caches_by_song(tmp_path):
    calls = []

    def fake_fetch(url, timeout=None):
        calls.append(url)
        return FakeResponse()

    fetcher = ImageFetcher(cache=JsonCache(tmp_path), fetch=fake_fetch)
    first = fetcher.data_uri(
        "https://images.genius.com/x.png",
        artist_id=42,
        artist_name="Test Artist",
        song_id=1,
        title="Early Hit",
    )
    second = fetcher.data_uri(
        "https://images.genius.com/x.png",
        artist_id=42,
        artist_name="Test Artist",
        song_id=1,
        title="Early Hit",
    )
    assert first == second
    assert len(calls) == 1

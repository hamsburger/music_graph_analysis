from datetime import datetime

from music_graph_analysis.analysis import ArtistAnalyzer, format_report
from music_graph_analysis.cache import JsonCache


class FakeClient:
    def __init__(self, songs, samplers=None, artist_id=42, name="Test Artist"):
        self._songs = songs
        self._samplers = samplers or {}
        self.artist_id = artist_id
        self.name = name
        self.discography_calls = 0
        self.sampled_in_calls = 0

    def find_artist(self, name):
        if name != self.name:
            return None
        return {
            "id": self.artist_id,
            "name": self.name,
            "url": f"https://genius.com/artists/{self.artist_id}",
        }

    def iter_artist_songs(self, artist_id):
        self.discography_calls += 1
        return list(self._songs)

    def get_sampled_in(self, song_id):
        self.sampled_in_calls += 1
        return self._samplers.get(song_id, [])


def make_song(song_id, title, year, views, primary_id=42, month=1, day=1):
    components = (
        {"year": year, "month": month, "day": day} if year else None
    )
    return {
        "id": song_id,
        "title": title,
        "artist_names": "Test Artist",
        "primary_artist": {"id": primary_id, "name": "Test Artist"},
        "stats": {"pageviews": views},
        "release_date_components": components,
        "release_date_for_display": f"{year}" if year else None,
    }


def make_sampler(song_id, title, artist="Other"):
    return {
        "id": song_id,
        "title": title,
        "artist_names": artist,
        "primary_artist": {"name": artist},
        "release_date_components": {"year": 2010, "month": 1, "day": 1},
    }


def build_client():
    songs = [
        make_song(1, "Early Hit", 2000, views=100),
        make_song(2, "Early B-Side", 2000, views=10),
        make_song(3, "Late Hit", 2004, views=500),
        make_song(4, "Undated", None, views=50),
        make_song(5, "Not Ours", 2001, views=999, primary_id=7),
    ]
    samplers = {
        1: [make_sampler(101, "Sample One", "Artist A")],
        3: [
            make_sampler(102, "Sample Two", "Artist B"),
            make_sampler(103, "Sample Three", "Artist B"),
        ],
        4: [],
    }
    return FakeClient(songs, samplers)


def test_analyze_filters_to_primary_artist_songs():
    analyzer = ArtistAnalyzer(build_client())
    result = analyzer.analyze("Test Artist", n_eras=5, top_k=5)
    all_ids = [
        song["id"] for era in result["eras"] for song in era["songs"]
    ]
    assert 5 not in all_ids


def test_analyze_reports_sample_counts_and_samplers():
    analyzer = ArtistAnalyzer(build_client())
    result = analyzer.analyze("Test Artist", n_eras=5, top_k=5)
    songs = {s["id"]: s for era in result["eras"] for s in era["songs"]}

    assert songs[1]["sample_count"] == 1
    assert songs[1]["sampled_by"][0]["artist"] == "Artist A"
    assert songs[3]["sample_count"] == 2


def test_analyze_places_undated_song_in_unknown_era():
    analyzer = ArtistAnalyzer(build_client())
    result = analyzer.analyze("Test Artist", n_eras=5, top_k=5)
    unknown = [era for era in result["eras"] if era["era"] == "unknown"]
    assert len(unknown) == 1
    assert [s["id"] for s in unknown[0]["songs"]] == [4]


def test_analyze_span_and_top_k():
    analyzer = ArtistAnalyzer(build_client())
    result = analyzer.analyze("Test Artist", n_eras=5, top_k=1)
    assert result["span"]["start"] == "2000-01-01"
    assert result["span"]["end"] == "2004-01-01"
    for era in result["eras"]:
        assert len(era["songs"]) <= 1


def test_analyze_uses_cache_on_second_run(tmp_path):
    client = build_client()
    cache = JsonCache(tmp_path)
    analyzer = ArtistAnalyzer(client, cache=cache)

    analyzer.analyze("Test Artist")
    first_discography = client.discography_calls
    first_sampled = client.sampled_in_calls

    analyzer.analyze("Test Artist")
    assert client.discography_calls == first_discography
    assert client.sampled_in_calls == first_sampled


def test_analyze_raises_for_unknown_artist():
    import pytest

    from music_graph_analysis import GeniusAPIError

    analyzer = ArtistAnalyzer(build_client())
    with pytest.raises(GeniusAPIError):
        analyzer.analyze("Nobody")


def test_format_report_mentions_artist_and_songs():
    analyzer = ArtistAnalyzer(build_client())
    report = format_report(analyzer.analyze("Test Artist"))
    assert "Test Artist" in report
    assert "Early Hit" in report
    assert "sampled 1x" in report

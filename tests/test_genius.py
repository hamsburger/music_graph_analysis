import pytest

from music_graph_analysis import GeniusAPIError, GeniusClient


def test_client_requires_token(monkeypatch):
    monkeypatch.delenv("GENIUS_ACCESS_TOKEN", raising=False)
    with pytest.raises(GeniusAPIError):
        GeniusClient()


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


def test_get_song_builds_request(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured.update(url=url, headers=headers, params=params, timeout=timeout)
        return DummyResponse({"response": {"song": {"id": 123, "title": "Hey"}}})

    monkeypatch.setattr("music_graph_analysis.genius.requests.get", fake_get)

    client = GeniusClient(access_token="test-token")
    song = client.get_song(123)

    assert captured["url"] == "https://api.genius.com/songs/123"
    assert captured["headers"]["Authorization"] == "Bearer test-token"
    assert song["song"]["title"] == "Hey"


def test_api_error_raises(monkeypatch):
    monkeypatch.setattr(
        "music_graph_analysis.genius.requests.get",
        lambda *a, **k: DummyResponse(
            {"meta": {"message": "Not found"}}, status_code=404
        ),
    )

    client = GeniusClient(access_token="test-token")
    with pytest.raises(GeniusAPIError, match="Not found"):
        client.get_song(0)


def test_iter_artist_songs_pages_until_short_page():
    client = GeniusClient(access_token="test-token")

    def fake_songs(artist_id, *, sort="popularity", per_page=50, page=1):
        assert per_page == 50
        if page == 1:
            return [{"id": i} for i in range(50)]
        if page == 2:
            return [{"id": i} for i in range(10)]
        return []

    client.get_artist_songs = fake_songs
    songs = list(client.iter_artist_songs(1))
    assert len(songs) == 60


def test_iter_artist_songs_clamps_per_page():
    client = GeniusClient(access_token="test-token")
    seen = []

    def fake_songs(artist_id, *, sort="popularity", per_page=50, page=1):
        seen.append(per_page)
        return []

    client.get_artist_songs = fake_songs
    list(client.iter_artist_songs(1, per_page=500))
    assert seen == [50]


def test_iter_artist_songs_clamps_per_page_minimum():
    client = GeniusClient(access_token="test-token")
    seen = []

    def fake_songs(artist_id, *, sort="popularity", per_page=50, page=1):
        seen.append(per_page)
        return []

    client.get_artist_songs = fake_songs
    list(client.iter_artist_songs(1, per_page=0))
    assert seen == [1]


def test_get_sampled_in_extracts_relationship_songs():
    client = GeniusClient(access_token="test-token")
    client.get_song = lambda song_id: {
        "song": {
            "song_relationships": [
                {"type": "samples", "songs": [{"id": 1}]},
                {"type": "sampled_in", "songs": [{"id": 2}, {"id": 3}]},
            ]
        }
    }
    assert [s["id"] for s in client.get_sampled_in(9)] == [2, 3]


def test_get_sampled_in_returns_empty_when_absent():
    client = GeniusClient(access_token="test-token")
    client.get_song = lambda song_id: {"song": {"song_relationships": []}}
    assert client.get_sampled_in(9) == []


def test_get_cached_returns_none_on_miss(tmp_path):
    from music_graph_analysis.cache import JsonCache

    cache = JsonCache(tmp_path)
    assert cache.get("missing") is None
    cache.set("key", {"a": 1})
    assert cache.get("key") == {"a": 1}


def test_cache_uses_friendly_nested_paths(tmp_path):
    from music_graph_analysis.cache import JsonCache

    cache = JsonCache(tmp_path)
    cache.set("Kanye West-123/sampled-in/Stronger-456", {"b": 2})

    expected = tmp_path / "kanye-west-123" / "sampled-in" / "stronger-456.json"
    assert expected.exists()
    assert cache.get("Kanye West-123/sampled-in/Stronger-456") == {"b": 2}


def test_get_retries_transient_failure(monkeypatch):
    import requests

    attempts = {"n": 0}

    def flaky_get(url, headers=None, params=None, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise requests.exceptions.Timeout("boom")
        return DummyResponse({"response": {"song": {"id": 1}}})

    monkeypatch.setattr("music_graph_analysis.genius.requests.get", flaky_get)
    client = GeniusClient(access_token="test-token", max_retries=3, backoff=0)
    assert client.get_song(1)["song"]["id"] == 1
    assert attempts["n"] == 2

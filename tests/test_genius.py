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

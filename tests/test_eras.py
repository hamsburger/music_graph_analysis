from datetime import datetime

from music_graph_analysis.eras import (
    UNKNOWN_ERA,
    EraBounds,
    compute_era_bounds,
    parse_release_date,
    select_top_songs_per_era,
    song_pageviews,
)


def make_song(song_id, title, year, month=1, day=1, views=0):
    return {
        "id": song_id,
        "title": title,
        "artist_names": "Test",
        "stats": {"pageviews": views},
        "release_date_components": (
            {"year": year, "month": month, "day": day} if year else None
        ),
    }


def test_parse_release_date_from_components():
    song = make_song(1, "A", 1999, 6, 15)
    assert parse_release_date(song) == datetime(1999, 6, 15)


def test_parse_release_date_defaults_missing_month_day():
    song = {"release_date_components": {"year": 2001, "month": None, "day": None}}
    assert parse_release_date(song) == datetime(2001, 1, 1)


def test_parse_release_date_falls_back_to_string():
    assert parse_release_date({"release_date": "2014-03-17"}) == datetime(2014, 3, 17)
    assert parse_release_date({"release_date": "1987"}) == datetime(1987, 1, 1)


def test_parse_release_date_returns_none_when_missing_or_invalid():
    assert parse_release_date({}) is None
    assert parse_release_date({"release_date_components": None}) is None
    assert (
        parse_release_date(
            {"release_date_components": {"year": 2001, "month": 2, "day": 30}}
        )
        is None
    )


def test_song_pageviews_defaults_to_zero():
    assert song_pageviews({"stats": {"pageviews": 123}}) == 123
    assert song_pageviews({}) == 0


def test_compute_era_bounds_none_without_dates():
    assert compute_era_bounds([None, None]) is None


def test_compute_era_bounds_uses_min_and_max():
    bounds = compute_era_bounds(
        [datetime(2000, 1, 1), datetime(2004, 1, 1), datetime(2002, 6, 1)], n=5
    )
    assert isinstance(bounds, EraBounds)
    assert bounds.start == datetime(2000, 1, 1)
    assert bounds.end == datetime(2004, 1, 1)
    assert bounds.n == 5


def test_era_bounds_assign_boundaries():
    bounds = EraBounds(start=datetime(2000, 1, 1), end=datetime(2005, 1, 1), n=5)
    assert bounds.assign(None) == UNKNOWN_ERA
    assert bounds.assign(datetime(2000, 1, 1)) == 0
    assert bounds.assign(datetime(2004, 12, 31)) == 4
    assert bounds.assign(datetime(2001, 1, 1)) == 1


def test_era_bounds_zero_span_assigns_first():
    bounds = EraBounds(start=datetime(2000, 1, 1), end=datetime(2000, 1, 1), n=5)
    assert bounds.assign(datetime(2000, 1, 1)) == 0


def test_era_bounds_intervals_cover_span():
    bounds = EraBounds(start=datetime(2000, 1, 1), end=datetime(2005, 1, 1), n=5)
    start0, end0 = bounds.interval(0)
    assert start0 == bounds.start
    start_last, end_last = bounds.interval(4)
    assert end_last == bounds.end
    assert end0 == bounds.interval(1)[0]


def test_select_top_songs_per_era_picks_by_pageviews():
    bounds = EraBounds(start=datetime(2000, 1, 1), end=datetime(2005, 1, 1), n=5)
    songs = [
        make_song(1, "era0-low", 2000, 1, 2, views=10),
        make_song(2, "era0-high", 2000, 1, 3, views=100),
        make_song(3, "era0-mid", 2000, 1, 4, views=50),
        make_song(4, "era4", 2004, 12, 1, views=999),
    ]
    grouped = select_top_songs_per_era(songs, bounds, top_k=2)
    assert [s["id"] for s in grouped[0]] == [2, 3]
    assert [s["id"] for s in grouped[4]] == [4]
    assert UNKNOWN_ERA in grouped


def test_select_top_songs_puts_undated_in_unknown():
    bounds = EraBounds(start=datetime(2000, 1, 1), end=datetime(2005, 1, 1), n=5)
    songs = [make_song(1, "no-date", None, views=5)]
    grouped = select_top_songs_per_era(songs, bounds, top_k=5)
    assert [s["id"] for s in grouped[UNKNOWN_ERA]] == [1]


def test_select_top_songs_without_bounds_all_unknown():
    songs = [make_song(1, "a", 2000, views=1), make_song(2, "b", 2001, views=2)]
    grouped = select_top_songs_per_era(songs, None, top_k=5)
    assert set(grouped) == {UNKNOWN_ERA}
    assert [s["id"] for s in grouped[UNKNOWN_ERA]] == [2, 1]

"""Render an era analysis as a self-contained, interactive HTML page.

Everything here is pure: no network and no file I/O. Layout is produced as SVG
strings and the page as an HTML string, so the whole module is trivial to unit
test. Album art is supplied by the caller as a ``{song_id: data_uri}`` mapping
(see :mod:`music_graph_analysis.images`), which keeps this module network-free.

Each artist is drawn as a single SVG (so album art is embedded only once) with
the era bands, axes, and song shapes in a shared base layer. The dimension
labels live in one ``<g class="dim-tags" data-dimension="...">`` layer per
dimension, and a little vanilla JS toggles which layer is visible based on the
artist and dimension dropdowns.
"""

from __future__ import annotations

import html
import math
import zlib
from collections import Counter
from datetime import date
from typing import Any, Iterable

DIMENSIONS = ("themes", "key_imagery", "emotional_tone")

DIMENSION_LABELS = {
    "themes": "Themes",
    "key_imagery": "Key imagery",
    "emotional_tone": "Emotional tone",
}

DEFAULT_WIDTH = 1100
DEFAULT_HEIGHT = 620
MARGIN_TOP = 64
MARGIN_RIGHT = 40
MARGIN_BOTTOM = 72
MARGIN_LEFT = 76
MAX_TAGS_PER_ERA = 4
UNKNOWN_BAND_WIDTH = 96
RADIUS_MIN = 9.0
RADIUS_MAX = 26.0
JITTER_MAX = 6.0

_BAND_FILLS = ("#f4f6fb", "#e8ecf6")
_AXIS_COLOR = "#8a93a6"
_TEXT_COLOR = "#2b2f38"
_TAG_COLOR = "#5b6270"


def normalize_tags(
    summary: dict[str, Any] | None, dimension: str
) -> list[str]:
    """Return the cleaned, de-duplicated tags for ``dimension`` in ``summary``.

    ``themes`` and ``key_imagery`` are lists; ``emotional_tone`` is a
    comma-separated string. Values are trimmed, unquoted, lowercased, and
    de-duplicated while preserving order.
    """
    if not summary:
        return []
    value = summary.get(dimension)
    if value is None:
        return []

    if isinstance(value, str):
        parts: list[str] = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = [str(part) for part in value]
    else:
        parts = [str(value)]

    tags: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tag = part.strip().strip("\"'").strip().casefold()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def era_tag_counts(era: dict[str, Any], dimension: str) -> Counter[str]:
    """Count tag frequency for ``dimension`` across the songs in ``era``."""
    counts: Counter[str] = Counter()
    for song in era.get("songs", []):
        for tag in normalize_tags(song.get("summary"), dimension):
            counts[tag] += 1
    return counts


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _parse_iso(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _x_for_date(
    day: date | None, dmin: date | None, dmax: date | None, left: float, span: float
) -> float:
    if day is None or dmin is None or dmax is None or dmax <= dmin or span <= 0:
        return left + span / 2
    frac = (day - dmin).days / (dmax - dmin).days
    frac = min(1.0, max(0.0, frac))
    return left + frac * span


def _song_y(
    *,
    era_index: int,
    song_index: int,
    count: int,
    top: float,
    height: float,
) -> float:
    step = 1.0 / (max(1, count) + 1)
    frac = (song_index + 1) * step
    frac += (0.5 * step) if era_index % 2 else (-0.5 * step)
    return top + frac * height


def _jitter_for_song(song: dict[str, Any], amount: float = JITTER_MAX) -> float:
    song_id = song.get("id")
    if song_id is None:
        return 0.0
    seed = zlib.crc32(str(song_id).encode("utf-8"))
    return ((seed % 2001) / 2000.0 - 0.5) * 2.0 * amount


def _radius_for_pageviews(pageviews: float, values: list[float]) -> float:
    positive = [v for v in values if v > 0]
    if not positive:
        return (RADIUS_MIN + RADIUS_MAX) / 2
    low = math.sqrt(min(positive))
    high = math.sqrt(max(positive))
    if high <= low:
        return (RADIUS_MIN + RADIUS_MAX) / 2
    frac = (math.sqrt(max(pageviews, 0.0)) - low) / (high - low)
    frac = min(1.0, max(0.0, frac))
    return RADIUS_MIN + frac * (RADIUS_MAX - RADIUS_MIN)


def _short_era_label(era: dict[str, Any]) -> tuple[str, str]:
    value = era.get("era")
    if isinstance(value, int):
        start = (era.get("start") or "")[:4]
        end = (era.get("end") or "")[:4]
        return f"Era {value + 1}", f"{start}–{end}"
    return "Unknown", "no date"


def _song_x(
    song: dict[str, Any],
    *,
    is_dated: bool,
    index: int,
    count: int,
    x0: float,
    x1: float,
    dmin: date | None,
    dmax: date | None,
    left: float,
    dated_span: float,
) -> float:
    if not is_dated:
        return x0 + ((index + 0.5) / max(1, count)) * (x1 - x0)
    song_date = _parse_iso(song.get("release_date"))
    if song_date is None:
        return (x0 + x1) / 2
    return _x_for_date(song_date, dmin, dmax, left, dated_span)


def _song_tooltip_attrs(song: dict[str, Any]) -> str:
    summary = song.get("summary")
    attrs = [
        f'data-song-title="{_esc(song.get("title") or "Untitled")}"'
    ]
    album = song.get("album")
    if album:
        attrs.append(f'data-album="{_esc(album)}"')
    overview = (summary or {}).get("overview")
    if isinstance(overview, str) and overview.strip():
        attrs.append(f'data-overview="{_esc(overview.strip())}"')
    for dimension in DIMENSIONS:
        tags = ", ".join(normalize_tags(summary, dimension))
        attrs.append(f'data-{dimension.replace("_", "-")}="{_esc(tags)}"')
    return " ".join(attrs)


def build_chart_svg(
    result: dict[str, Any],
    images: dict[int, str] | None = None,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    id_prefix: str = "chart",
    dimensions: Iterable[str] = DIMENSIONS,
    max_tags: int = MAX_TAGS_PER_ERA,
) -> str:
    """Render ``result`` as a single SVG string.

    X is time (release date) with era bands; songs are spread evenly down each
    era's vertical band (staggered between adjacent eras) with a small
    deterministic x-jitter, while radius is pageviews. Album art is drawn
    inside clipped circles when ``images`` has the song id. Era tag labels are
    emitted once per dimension into toggleable ``dim-tags`` layers.
    """
    dimensions = tuple(dimensions)
    images = images or {}
    artist = result.get("artist", {})
    eras = result.get("eras", [])

    left = MARGIN_LEFT
    top = MARGIN_TOP
    plot_w = max(1, width - MARGIN_LEFT - MARGIN_RIGHT)
    plot_h = max(1, height - MARGIN_TOP - MARGIN_BOTTOM)

    all_songs = [song for era in eras for song in era.get("songs", [])]
    pageview_values = [float(song.get("pageviews") or 0) for song in all_songs]

    dated_eras = [e for e in eras if e.get("start") and e.get("end")]
    undated_eras = [e for e in eras if not (e.get("start") and e.get("end"))]

    date_values: list[date] = []
    for era in dated_eras:
        for key in ("start", "end"):
            parsed = _parse_iso(era.get(key))
            if parsed is not None:
                date_values.append(parsed)
    dmin = min(date_values) if date_values else None
    dmax = max(date_values) if date_values else None

    if dated_eras:
        unknown_w = UNKNOWN_BAND_WIDTH if undated_eras else 0
        dated_w = max(1, plot_w - unknown_w)
    else:
        unknown_w = plot_w
        dated_w = 0

    def era_x(era: dict[str, Any]) -> tuple[float, float]:
        if era.get("start") and era.get("end"):
            x0 = _x_for_date(_parse_iso(era["start"]), dmin, dmax, left, dated_w)
            x1 = _x_for_date(_parse_iso(era["end"]), dmin, dmax, left, dated_w)
        else:
            x0 = left + dated_w
            x1 = left + dated_w + unknown_w
        return x0, max(x1, x0 + 1)

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{_esc(artist.get("name") or "artist")} era chart">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{left}" y="30" font-size="20" font-weight="600" '
        f'fill="{_TEXT_COLOR}">{_esc(artist.get("name") or "Unknown artist")}'
        f"</text>",
        f'<text x="{left}" y="50" font-size="12" fill="{_AXIS_COLOR}">'
        f"Themes, imagery &amp; tone by era</text>",
    ]

    parts.append(f'<g class="base">')

    clip_paths: list[str] = []
    song_markup: list[str] = []
    for era_index, era in enumerate(eras):
        x0, x1 = era_x(era)
        band_fill = _BAND_FILLS[era_index % len(_BAND_FILLS)]
        parts.append(
            f'<rect x="{x0:.1f}" y="{top:.1f}" width="{x1 - x0:.1f}" '
            f'height="{plot_h:.1f}" fill="{band_fill}"/>'
        )

        title, subtitle = _short_era_label(era)
        center = (x0 + x1) / 2
        parts.append(
            f'<text x="{center:.1f}" y="{top + 16:.1f}" font-size="12" '
            f'font-weight="600" text-anchor="middle" fill="{_TEXT_COLOR}">'
            f"{_esc(title)}</text>"
        )
        parts.append(
            f'<text x="{center:.1f}" y="{top + 30:.1f}" font-size="10" '
            f'text-anchor="middle" fill="{_AXIS_COLOR}">{_esc(subtitle)}</text>'
        )

        songs = era.get("songs", [])
        for song_index, song in enumerate(songs):
            x = _song_x(
                song,
                is_dated=bool(era.get("start") and era.get("end")),
                index=song_index,
                count=len(songs),
                x0=x0,
                x1=x1,
                dmin=dmin,
                dmax=dmax,
                left=left,
                dated_span=dated_w,
            )
            x = min(x1, max(x0, x + _jitter_for_song(song)))
            y = _song_y(
                era_index=era_index,
                song_index=song_index,
                count=len(songs),
                top=top,
                height=plot_h,
            )
            radius = _radius_for_pageviews(
                float(song.get("pageviews") or 0), pageview_values
            )
            clip_id = f"{id_prefix}-clip-{song.get('id')}"
            markup, clip = _song_markup(
                song, images, x=x, y=y, radius=radius, clip_id=clip_id
            )
            song_markup.append(markup)
            if clip:
                clip_paths.append(clip)

    parts.extend(clip_paths)
    parts.extend(song_markup)
    parts.append("</g>")

    for layer_index, dimension in enumerate(dimensions):
        style = "" if layer_index == 0 else ' style="display:none"'
        parts.append(
            f'<g class="dim-tags" data-dimension="{_esc(dimension)}"{style}>'
        )
        for era in eras:
            x0, x1 = era_x(era)
            center = (x0 + x1) / 2
            counts = era_tag_counts(era, dimension)
            tags = [tag for tag, _ in counts.most_common(max_tags)]
            for row, tag in enumerate(tags):
                y = top + plot_h - 8 - (len(tags) - 1 - row) * 14
                parts.append(
                    f'<text x="{center:.1f}" y="{y:.1f}" font-size="10" '
                    f'text-anchor="middle" fill="{_TAG_COLOR}">'
                    f"{_esc(tag)}</text>"
                )
        parts.append("</g>")

    parts.append(
        f'<line x1="{left}" y1="{top + plot_h:.1f}" '
        f'x2="{left + plot_w:.1f}" y2="{top + plot_h:.1f}" '
        f'stroke="{_AXIS_COLOR}"/>'
    )

    parts.append("</svg>")
    return "".join(parts)


def _song_markup(
    song: dict[str, Any],
    images: dict[int, str],
    *,
    x: float,
    y: float,
    radius: float,
    clip_id: str,
) -> tuple[str, str | None]:
    song_id = song.get("id")
    data_uri = images.get(song_id) if song_id is not None else None
    body: list[str] = []
    clip: str | None = None

    if data_uri:
        clip = (
            f'<clipPath id="{_esc(clip_id)}"><circle cx="{x:.1f}" '
            f'cy="{y:.1f}" r="{radius:.1f}"/></clipPath>'
        )
        body.append(
            f'<image x="{x - radius:.1f}" y="{y - radius:.1f}" '
            f'width="{2 * radius:.1f}" height="{2 * radius:.1f}" '
            f'href="{_esc(data_uri)}" clip-path="url(#{_esc(clip_id)})" '
            f'preserveAspectRatio="xMidYMid slice"/>'
        )
        body.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="none" '
            f'stroke="#ffffff" stroke-width="2"/>'
        )
    else:
        body.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" '
            f'fill="#c3cad8" stroke="#ffffff" stroke-width="2"/>'
        )
        body.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="11" '
            f'text-anchor="middle" fill="{_TEXT_COLOR}">'
            f"{_esc((song.get('title') or '?')[:1].upper())}</text>"
        )

    markup = (
        f'<g class="song" {_song_tooltip_attrs(song)}>'
        + "".join(body)
        + "</g>"
    )
    return markup, clip


def _select(
    select_id: str, label: str, options: list[tuple[str, str]]
) -> str:
    option_markup = "".join(
        f'<option value="{_esc(value)}">{_esc(text)}</option>'
        for value, text in options
    )
    return (
        f'<label class="control">{_esc(label)} '
        f'<select id="{_esc(select_id)}">{option_markup}</select></label>'
    )


def render_html(
    artists: list[dict[str, Any]],
    images: dict[int, str] | None = None,
    *,
    title: str = "Era visualizations",
) -> str:
    """Render one or more artist results as a single interactive HTML page."""
    images = images or {}

    artist_options: list[tuple[str, str]] = []
    for result in artists:
        artist = result.get("artist", {})
        key = str(artist.get("id"))
        artist_options.append((key, str(artist.get("name") or key)))

    dimension_options = [
        (dimension, DIMENSION_LABELS[dimension]) for dimension in DIMENSIONS
    ]

    charts: list[str] = []
    for result in artists:
        artist = result.get("artist", {})
        artist_key = str(artist.get("id"))
        svg = build_chart_svg(result, images, id_prefix=f"a{artist_key}")
        charts.append(
            f'<div class="chart" data-artist="{_esc(artist_key)}">{svg}</div>'
        )

    controls = [_select("dimension-select", "Dimension", dimension_options)]
    if len(artist_options) > 1:
        controls.insert(0, _select("artist-select", "Artist", artist_options))

    return _HTML_TEMPLATE.format(
        title=_esc(title),
        controls="".join(controls),
        charts="".join(charts),
    )


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      Helvetica, Arial, sans-serif;
    color: #2b2f38;
    background: #ffffff;
  }}
  header {{ padding: 24px 28px 8px; }}
  h1 {{ margin: 0 0 12px; font-size: 24px; }}
  .controls {{ display: flex; flex-wrap: wrap; gap: 20px; }}
  .control {{ font-size: 13px; color: #5b6270; }}
  select {{ margin-left: 6px; padding: 4px 8px; font-size: 13px; }}
  main {{ padding: 8px 20px 120px; }}
  .chart {{ display: none; }}
  .song {{ cursor: pointer; }}
  .tooltip {{
    position: fixed;
    pointer-events: none;
    max-width: 280px;
    padding: 8px 10px;
    border-radius: 6px;
    background: rgba(20, 22, 28, 0.94);
    color: #ffffff;
    font-size: 12px;
    line-height: 1.4;
    z-index: 10;
  }}
  .tooltip[hidden] {{ display: none; }}
  .tooltip .t-title {{ font-weight: 600; }}
  .tooltip .t-album {{ color: #c3cad8; }}
  .tooltip .t-overview {{ margin-top: 4px; color: #c3cad8; }}
  .tooltip .t-dim {{ margin-top: 4px; color: #c3cad8; }}
  .tooltip .t-dim.active {{ color: #ffffff; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="controls">{controls}</div>
</header>
<main>{charts}</main>
<div id="tooltip" class="tooltip" hidden></div>
<script>
(function () {{
  var artistSelect = document.getElementById("artist-select");
  var dimensionSelect = document.getElementById("dimension-select");
  var tooltip = document.getElementById("tooltip");
  var charts = Array.prototype.slice.call(
    document.querySelectorAll(".chart")
  );
  var tagLayers = Array.prototype.slice.call(
    document.querySelectorAll(".dim-tags")
  );
  function update() {{
    var artist = artistSelect ? artistSelect.value : null;
    var dimension = dimensionSelect.value;
    charts.forEach(function (chart) {{
      var match = !artist || chart.dataset.artist === artist;
      chart.style.display = match ? "block" : "none";
    }});
    tagLayers.forEach(function (layer) {{
      layer.style.display = layer.dataset.dimension === dimension
        ? "" : "none";
    }});
  }}
  function moveTooltip(event) {{
    var margin = 14;
    var x = Math.min(event.clientX + margin, window.innerWidth - 300);
    var height = tooltip.offsetHeight;
    var y = event.clientY + margin;
    if (y + height > window.innerHeight - 8) {{
      y = event.clientY - height - margin;
    }}
    y = Math.max(8, y);
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  }}
  function showTooltip(event, song) {{
    var title = song.getAttribute("data-song-title") || "Untitled";
    tooltip.innerHTML = '<div class="t-title"></div>';
    tooltip.querySelector(".t-title").textContent = title;
    var album = song.getAttribute("data-album");
    if (album) {{
      var albumRow = document.createElement("div");
      albumRow.className = "t-album";
      albumRow.textContent = album;
      tooltip.appendChild(albumRow);
    }}
    var overview = song.getAttribute("data-overview");
    if (overview) {{
      var overviewRow = document.createElement("div");
      overviewRow.className = "t-overview";
      overviewRow.textContent = overview;
      tooltip.appendChild(overviewRow);
    }}
    Array.prototype.forEach.call(dimensionSelect.options, function (option) {{
      var tags = song.getAttribute(
        "data-" + option.value.replace(/_/g, "-")
      );
      var row = document.createElement("div");
      row.className = "t-dim"
        + (option.value === dimensionSelect.value ? " active" : "");
      row.textContent = option.text + ": " + (tags || "\\u2014");
      tooltip.appendChild(row);
    }});
    tooltip.hidden = false;
    moveTooltip(event);
  }}
  document.querySelectorAll(".song").forEach(function (song) {{
    song.addEventListener("mouseenter", function (event) {{
      showTooltip(event, song);
    }});
    song.addEventListener("mousemove", moveTooltip);
    song.addEventListener("mouseleave", function () {{
      tooltip.hidden = true;
    }});
  }});
  if (artistSelect) {{ artistSelect.addEventListener("change", update); }}
  dimensionSelect.addEventListener("change", update);
  update();
}})();
</script>
</body>
</html>
"""

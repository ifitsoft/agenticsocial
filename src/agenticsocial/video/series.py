"""Series configuration: scaffolding and loading `series.toml`."""
from __future__ import annotations

import tomllib

from ..workspace import Workspace, atomic_write
from .models import FORMATS, Series, SeriesError

SERIES_TEMPLATE = """\
[series]
name       = "{name}"
slug       = "{slug}"
byline     = ""
cadence    = "daily"              # daily | weekly | adhoc — advisory, nothing schedules
register   = "reported"           # reported | first-person

[runtime]
target_sec = 120                  # pace is derived: target_sec / sum(beat holds)
tolerance_sec = 8

[formats]
enabled = ["vertical", "wide"]    # vertical 1080x1920 · wide 1920x1080

[design]
surface     = "#F2F5F8"
ink         = "#0B1B2B"
ink_muted   = "#5A6B7C"
accent      = "#2E6BFF"
accent_alt  = "#00C2D7"
accent_warm = "#FF6B4A"           # reserved; see warm_acts
type_family = "SF Pro Display, Helvetica Neue, system-ui"
type_scale  = "default"           # default | compact | large

[structure]
warm_acts = []                    # acts permitted to use accent_warm

# [[structure.acts]]
# id = "01"
# label = "01 — The headline"
# beats = 6
"""

COVERAGE_TEMPLATE = """\
{{
  "series": "{name}",
  "conventions": {{
    "id": "Stable kebab-case slug for a story THREAD, not a single day's article. Reuse the same id when the story returns.",
    "angle": "launch | analysis | incident | deployment | research | culture — what the beat actually did with the story.",
    "update": "Set true when an entry revisits an id covered on an earlier date. Put the earlier date in updateOf and say what is new in note.",
    "rule": "Before writing a new episode, check coverage. A hit means either skip it or run it as an explicit update — never re-tell it as if it were new."
  }},
  "episodes": []
}}
"""


def scaffold_series(ws: Workspace, slug: str, name: str | None = None) -> Series:
    d = ws.series_dir / slug
    if d.exists():
        raise SeriesError(f"series already exists: {slug}")
    (d / "episodes").mkdir(parents=True)
    name = name or slug
    atomic_write(d / "series.toml", SERIES_TEMPLATE.format(name=name, slug=slug))
    atomic_write(d / "coverage.json", COVERAGE_TEMPLATE.format(name=name))
    return load_series(ws, slug)


def load_series(ws: Workspace, slug: str) -> Series:
    d = ws.series_dir / slug
    path = d / "series.toml"
    if not path.exists():
        raise SeriesError(f"no series '{slug}' — create it with `agsoc series new {slug}`")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SeriesError(f"{path}: malformed series.toml — {e}")

    meta = raw.get("series", {})
    runtime = raw.get("runtime", {})
    design = raw.get("design", {})
    structure = raw.get("structure", {})

    formats = raw.get("formats", {}).get("enabled", list(FORMATS))
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        raise SeriesError(
            f"{path}: unknown format(s) {', '.join(unknown)} — one of: {', '.join(FORMATS)}"
        )
    if not formats:
        raise SeriesError(f"{path}: [formats] enabled is empty — enable at least one")

    target_sec = runtime.get("target_sec", 120)
    if not isinstance(target_sec, int) or target_sec <= 0:
        raise SeriesError(f"{path}: [runtime] target_sec must be a positive integer")

    return Series(
        slug=slug,
        name=meta.get("name", slug),
        dir=d,
        byline=meta.get("byline", ""),
        cadence=meta.get("cadence", "daily"),
        register=meta.get("register", "reported"),
        target_sec=target_sec,
        tolerance_sec=runtime.get("tolerance_sec", 8),
        formats=formats,
        design=design,
        acts=structure.get("acts", []),
    )


def list_series(ws: Workspace) -> list[Series]:
    if not ws.series_dir.is_dir():
        return []
    slugs = sorted(
        d.name for d in ws.series_dir.iterdir() if (d / "series.toml").exists()
    )
    return [load_series(ws, s) for s in slugs]

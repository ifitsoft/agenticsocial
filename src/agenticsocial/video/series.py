"""Series configuration: scaffolding and loading `series.toml`."""
from __future__ import annotations

import json
import re
import shutil
import tomllib

from ..workspace import Workspace, atomic_write
from .models import FORMATS, Series, SeriesError

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

SERIES_TEMPLATE = """\
[series]
name       = {name}
slug       = {slug}
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

CONVENTIONS = {
    "id": "Stable kebab-case slug for a story THREAD, not a single day's article. Reuse the same id when the story returns.",
    "angle": "launch | analysis | incident | deployment | research | culture — what the beat actually did with the story.",
    "update": "Set true when an entry revisits an id covered on an earlier date. Put the earlier date in updateOf and say what is new in note.",
    "rule": "Before writing a new episode, check coverage. A hit means either skip it or run it as an explicit update — never re-tell it as if it were new.",
}


def _toml_str(value: str) -> str:
    """Render a TOML basic string.

    JSON's string escaping is a valid subset of TOML's basic-string escaping
    (both use \\", \\\\, \\n, \\t, \\uXXXX), so json.dumps produces a correct
    quoted TOML string. Interpolating raw operator input instead corrupts the
    file it is written into — see D-020.
    """
    return json.dumps(value)


def render_series_toml(name: str, slug: str) -> str:
    return SERIES_TEMPLATE.format(name=_toml_str(name), slug=_toml_str(slug))


def render_coverage_json(name: str) -> str:
    return (
        json.dumps(
            {"series": name, "conventions": CONVENTIONS, "episodes": []},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def _validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise SeriesError(
            f"invalid series slug {slug!r} — use lowercase letters, digits and "
            "hyphens, starting with a letter or digit (slugs become directory names)"
        )


def _table(raw: dict, key: str, path) -> dict:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise SeriesError(
            f"{path}: [{key}] must be a table, got {type(value).__name__}"
        )
    return value


def scaffold_series(ws: Workspace, slug: str, name: str | None = None) -> Series:
    _validate_slug(slug)
    d = ws.series_dir / slug
    if d.exists():
        raise SeriesError(f"series already exists: {slug}")
    name = name or slug
    (d / "episodes").mkdir(parents=True)
    try:
        atomic_write(d / "series.toml", render_series_toml(name, slug))
        atomic_write(d / "coverage.json", render_coverage_json(name))
        return load_series(ws, slug)
    except BaseException:
        # Leave nothing half-written: the operator's obvious next move is to
        # retry, and a partial directory would fail with "already exists".
        shutil.rmtree(d, ignore_errors=True)
        raise


def load_series(ws: Workspace, slug: str) -> Series:
    d = ws.series_dir / slug
    path = d / "series.toml"
    if not path.is_file():
        raise SeriesError(f"no series '{slug}' — create it with `agsoc series new {slug}`")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SeriesError(f"{path}: malformed series.toml — {e}")
    except OSError as e:
        raise SeriesError(f"{path}: cannot read series.toml — {e}")

    meta = _table(raw, "series", path)
    runtime = _table(raw, "runtime", path)
    design = _table(raw, "design", path)
    structure = _table(raw, "structure", path)

    formats = _table(raw, "formats", path).get("enabled", list(FORMATS))
    if not isinstance(formats, list) or not all(isinstance(f, str) for f in formats):
        raise SeriesError(f"{path}: [formats] enabled must be a list of strings")
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        raise SeriesError(
            f"{path}: unknown format(s) {', '.join(unknown)} — one of: {', '.join(FORMATS)}"
        )
    if not formats:
        raise SeriesError(f"{path}: [formats] enabled is empty — enable at least one")

    target_sec = runtime.get("target_sec", 120)
    if isinstance(target_sec, bool) or not isinstance(target_sec, int) or target_sec <= 0:
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
        warm_acts=structure.get("warm_acts", []),
    )


def series_slugs(ws: Workspace) -> list[str]:
    """Enumerate series slugs. Cannot fail on a malformed series — see D-018."""
    if not ws.series_dir.is_dir():
        return []
    return sorted(
        d.name for d in ws.series_dir.iterdir() if (d / "series.toml").is_file()
    )


def list_series(ws: Workspace) -> list[Series]:
    """Load every series. Strict: raises if ANY series is malformed.

    For partial results — which is what `agsoc series list` needs — iterate
    `series_slugs()` and load each inside a try/except. See D-018.
    """
    return [load_series(ws, s) for s in series_slugs(ws)]

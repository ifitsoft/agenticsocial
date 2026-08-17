"""Series configuration: scaffolding and loading `series.toml`."""
from __future__ import annotations

import json
import re
import shutil
import tomllib

from ..workspace import Workspace, atomic_write
from .models import FORMATS, Series, SeriesError

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_NAME_LEN = 64

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


_TOML_SHORT_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _toml_str(value: str) -> str:
    """Render a TOML v1.0.0 basic string.

    TOML files are UTF-8, so every printable character — including non-BMP ones
    like emoji — is written literally. Only what UTF-8 cannot carry safely
    inside a basic string gets escaped: the quote, the backslash, the C0
    controls, and U+007F.

    Do NOT substitute json.dumps here. With ensure_ascii=True it emits UTF-16
    surrogate pairs, which TOML rejects because \\uXXXX must name a Unicode
    scalar value; with ensure_ascii=False it emits raw U+007F, which TOML
    forbids in a basic string. Neither setting is correct. See D-022.
    """
    out = ['"']
    for ch in value:
        short = _TOML_SHORT_ESCAPES.get(ch)
        if short is not None:
            out.append(short)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


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


_UNSAFE_CHARS = ("/", "\\", "\x00")


def _assert_safe_name(name: str, kind: str, error: type[Exception]) -> None:
    """Reject anything that could address a path outside its parent directory.

    Deliberately separate from the naming rules. Naming governs what agsoc will
    CREATE; this governs what it will TOUCH. A directory a human named `My-Show`
    stays loadable; `../../outside` does not, whoever made it. See D-038.
    """
    if not name or name in {".", ".."} or any(c in name for c in _UNSAFE_CHARS):
        raise error(
            f"unsafe {kind} {name!r} — must be a single directory name, "
            "not a path"
        )


def _validate_slug(slug: str) -> None:
    if len(slug) > MAX_NAME_LEN:
        raise SeriesError(
            f"series slug is too long ({len(slug)} characters, limit {MAX_NAME_LEN})"
        )
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
    _assert_safe_name(slug, "series slug", SeriesError)
    _validate_slug(slug)
    d = ws.series_dir / slug
    if d.exists() or d.is_symlink():
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
    _assert_safe_name(slug, "series slug", SeriesError)
    d = ws.series_dir / slug
    path = d / "series.toml"
    if not path.is_file():
        raise SeriesError(f"no series '{slug}' — create it with `agsoc series new {slug}`")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SeriesError(f"{path}: malformed series.toml — {e}")
    except UnicodeDecodeError as e:
        raise SeriesError(
            f"{path}: series.toml is not valid UTF-8 — {e}. "
            "Re-save it as UTF-8; agsoc writes and expects UTF-8 everywhere."
        )
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

    acts = structure.get("acts", [])
    if not isinstance(acts, list) or not all(isinstance(a, dict) for a in acts):
        raise SeriesError(
            f"{path}: [[structure.acts]] must be a list of tables — "
            "write [[structure.acts]] blocks, not a bare acts = value"
        )

    warm_acts = structure.get("warm_acts", [])
    if not isinstance(warm_acts, list) or not all(
        isinstance(a, str) for a in warm_acts
    ):
        raise SeriesError(f"{path}: [structure] warm_acts must be a list of strings")

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
        acts=acts,
        warm_acts=warm_acts,
    )


def series_slugs(ws: Workspace) -> list[str]:
    """Enumerate series slugs. Cannot fail on a malformed series — see D-018.
    An unreadable series/ still surfaces as SeriesError, never OSError."""
    if not ws.series_dir.is_dir():
        return []
    try:
        return sorted(
            d.name for d in ws.series_dir.iterdir() if (d / "series.toml").is_file()
        )
    except OSError as e:
        raise SeriesError(f"{ws.series_dir}: cannot list series — {e}")


def list_series(ws: Workspace) -> list[Series]:
    """Load every series. Strict: raises if ANY series is malformed.

    For partial results — which is what `agsoc series list` needs — iterate
    `series_slugs()` and load each inside a try/except. See D-018.
    """
    return [load_series(ws, s) for s in series_slugs(ws)]

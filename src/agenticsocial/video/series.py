"""Series configuration: scaffolding and loading `series.toml`."""
from __future__ import annotations

import json
import re
import shutil
import tomllib
import warnings
from typing import Any

from ..workspace import Workspace, assert_safe_name, atomic_write
from .models import FORMATS, Series, SeriesError

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_NAME_LEN = 64

# The design tokens that become CSS custom properties in `engine/planbuild.js`
# (PLAN_TOKENS). Keep this list identical to that map: a token here that the
# engine does not set is a pointless rule, and a token the engine sets that is
# missing here is the whole bug this exists to prevent.
#
# `type_family` and `type_scale` are deliberately absent. They are typography,
# not colour, and a colour rule applied to the whole [design] table would reject
# the scaffold's own font stack.
COLOUR_TOKENS = (
    "surface",
    "ink",
    "ink_muted",
    "accent",
    "accent_alt",
    "accent_warm",
)

# `#RGB` and `#RRGGBB`, case-insensitive — the only two forms the scaffold and
# both committed episodes write. Named colours and `rgb()` are valid CSS and are
# still refused: see `_colour_reason`.
HEX_COLOUR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Phase 4 selects voice rules from `register`, so a typo must not silently pick
# a default. `cadence` is deliberately NOT validated: spec §6 marks it advisory
# and nothing branches on it, so a legitimate "fortnightly" must still load.
REGISTERS = ("reported", "first-person")

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


def validate_design(design: dict, where: Any) -> None:
    """Refuse any `[design]` value that becomes a CSS custom property and is not
    a colour we write.

    This is the single most important check in the video pipeline, and it is
    here — in Python, at load and again before `plan.json` is written — rather
    than in `planbuild.js`, because of how CSS fails. `--blue: 5` is an invalid
    declaration, and an invalid declaration is DISCARDED: no exception, no
    console message, no visual marker. The render completes, looks plausible,
    and is wrong. A crash would be better; the operator would at least know.

    Checking at render time is not equivalent even if it caught the same values:
    by then the operator has waited out a full frame-by-frame render.

    The types are checked, not the truthiness. `accent = 0`, `accent = false`,
    `accent = ""` and `accent = []` are all falsy, and a check written
    `if value and not HEX_COLOUR_RE.match(value)` accepts every one of them —
    then `str()`s them into the stylesheet. `isinstance(v, str)` also rejects
    `true` for free, which a bare `isinstance(v, (int, str))` would not.
    """
    for token in COLOUR_TOKENS:
        if token not in design:
            continue
        value = design[token]
        if isinstance(value, str) and HEX_COLOUR_RE.match(value):
            continue
        raise SeriesError(
            f"{where}: [design] {token} must be a hex colour — "
            f'"#RRGGBB" or "#RGB", either case — got {value!r}. '
            "Named colours, rgb() and other CSS forms are refused even though "
            "CSS accepts them: agsoc writes one format, and a second "
            "silently-accepted one is how a palette drifts. This value becomes "
            "a CSS custom property, and CSS discards an invalid declaration "
            "without an error — the render would come out wrong and say nothing."
        )


def check_warm_acts(acts: list, warm_acts: list, where: Any) -> None:
    """Warn — never refuse — when `warm_acts` names an act nobody declared.

    `warm_acts` entries are act IDs, the same key a beat's `act` uses. Joining
    on the label instead would mean that rewording an act's display text
    silently unwires every reference to it, which is the failure this whole
    task exists to eliminate.

    D-070 keeps the miss soft. Spec §6 marks act metadata advisory, and a series
    whose only fault is a renamed act must still load — refusing would turn a
    cosmetic problem into a hard stop on the wrong side. Silence is the other
    failure: nothing else in the pipeline will ever mention that `accent_warm`
    is wired to an act that does not exist, so the operator would simply never
    see the warm treatment and have no thread to pull.
    """
    declared = {
        a["id"] for a in acts if isinstance(a, dict) and isinstance(a.get("id"), str)
    }
    unknown = [w for w in warm_acts if w not in declared]
    if not unknown:
        return
    warnings.warn(
        f"{where}: [structure] warm_acts names "
        f"{', '.join(repr(u) for u in unknown)}, which no [[structure.acts]] "
        "declares. warm_acts entries are act ids (the `id` field), not labels. "
        "Loading anyway — those acts simply will not get the accent_warm "
        "treatment.",
        UserWarning,
        stacklevel=3,
    )


def scaffold_series(ws: Workspace, slug: str, name: str | None = None) -> Series:
    assert_safe_name(slug, "series slug", SeriesError)
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
    assert_safe_name(slug, "series slug", SeriesError)
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

    tolerance_sec = runtime.get("tolerance_sec", 8)
    if (
        isinstance(tolerance_sec, bool)
        or not isinstance(tolerance_sec, int)
        or tolerance_sec < 0
    ):
        raise SeriesError(
            f"{path}: [runtime] tolerance_sec must be a non-negative integer "
            "(0 means the runtime must match target_sec exactly)"
        )

    register = meta.get("register", "reported")
    if register not in REGISTERS:
        raise SeriesError(
            f"{path}: [series] register must be one of "
            f"{', '.join(REGISTERS)} — got {register!r}. "
            "Phase 4 selects voice rules from this value."
        )

    for field in ("name", "byline"):
        value = meta.get(field)
        if value is not None and not isinstance(value, str):
            raise SeriesError(
                f"{path}: [series] {field} must be a string, got "
                f"{type(value).__name__}"
            )

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

    validate_design(design, path)
    check_warm_acts(acts, warm_acts, path)

    return Series(
        slug=slug,
        name=meta.get("name", slug),
        dir=d,
        byline=meta.get("byline", ""),
        cadence=meta.get("cadence", "daily"),
        register=register,
        target_sec=target_sec,
        tolerance_sec=tolerance_sec,
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

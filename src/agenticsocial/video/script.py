"""The beat schema: what a beat IS, per type, independent of how it renders.

This module owns spec §7's catalogue and nothing else. It answers "is this a
well-formed beat?"; `plan.py` answers "when does it appear and can we draw it
yet?". The split is not tidiness — Phase 5 verifies claims, and a claim is
anchored to a beat's `src` and `quote`. The verifier has to walk beats as data
without knowing anything about frames, pace or JSON, and that is exactly what
`Script` gives it.

Two gates, deliberately separate:

  * **validity** — the type is in `BEAT_TYPES` and its fields check out. Every
    catalogue type is valid today, including the ones no renderer exists for.
  * **renderability** — `RENDERABLE` is the subset `plan.py` can currently
    emit. A `dumbbell` is a real beat that this phase cannot draw, and an
    operator must be able to tell that from a typo.

READ ONLY. Nothing here writes: `script.yaml`'s bytes are load-bearing for
`script_sha256` (spec §10, DECISIONS D-026), so not even normalisation is
allowed. `read_script` hands us document 2 verbatim; we parse a copy.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable

import yaml

from ..models import Status
from .episode import read_script
from .models import Episode

DEFAULT_HOLD = 3.0

# What plan.py can currently emit. Widening this is a rendering decision, not a
# schema one — see the module docstring.
#
# Phase 4 added a builder in engine/planbuild.js for each of the five text
# types alongside `statement`. The four that remain (`kpis`, `jumpChart`,
# `dumbbell`, `custom`) are valid beats with no builder: they draw numbers or
# arbitrary JS, and both need more than a text vocabulary. A name added here
# without a builder renders a blank card, so
# tests/test_video_planbuild.py::test_every_renderable_type_has_a_builder holds
# this set and `BUILDERS` to each other.
RENDERABLE = frozenset({"statement", "body", "list", "quote", "title", "signoff"})


class ScriptError(Exception):
    pass


# --- field checkers -------------------------------------------------------------
# A checker returns None when the value is acceptable, or a reason phrase that
# completes "`<field>` <reason>". They are written against the VALUE's type, never
# its truthiness: `sub: ""` is a title card without a subtitle, `hold: 0` is a
# beat that never appears, and a check written `if value:` cannot tell them apart.

Check = Callable[[Any], "str | None"]


def _is_number(v: Any) -> bool:
    # bool is a subclass of int; `hold: true` is not a duration.
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_str(v: Any) -> bool:
    return isinstance(v, str)


def _is_filled(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _type_name(v: Any) -> str:
    return "null" if v is None else type(v).__name__


def free_text(v: Any) -> str | None:
    """A string, empty allowed. For decorative or advisory fields."""
    return None if _is_str(v) else f"must be a string, got {_type_name(v)}"


def text(v: Any) -> str | None:
    """A string carrying content. Empty is a missing sentence, not a short one."""
    if not _is_str(v):
        return f"must be a string, got {_type_name(v)}"
    if not v.strip():
        return "must not be empty"
    return None


def number(v: Any) -> str | None:
    return None if _is_number(v) else f"must be a number, got {_type_name(v)}"


def positive_number(v: Any) -> str | None:
    if not _is_number(v):
        return f"must be a number, got {_type_name(v)}"
    return None if v > 0 else f"must be greater than zero, got {v!r}"


def text_list(v: Any) -> str | None:
    """A non-empty list of non-empty strings. A bare string is not a list — it
    is iterable, which is how it survives a weaker check and renders as N
    single-character rows."""
    if not isinstance(v, list):
        return f"must be a list, got {_type_name(v)}"
    if not v:
        return "must not be empty"
    for i, item in enumerate(v):
        if not _is_filled(item):
            return f"[{i}] must be a non-empty string, got {_type_name(item)}"
    return None


def rows(v: Any) -> str | None:
    """A non-empty list. The per-row shape is deliberately unconstrained — see
    the module note on `dumbbell` in the Phase 3 report; the committed episode
    builds its rows inline and the spec does not name their columns."""
    if not isinstance(v, list):
        return f"must be a list, got {_type_name(v)}"
    if not v:
        return "must not be empty"
    return None


def jump_rows(v: Any) -> str | None:
    """`rows[{label, before, after, shown}]` — spec §7.1 as corrected by D-068.

    A jumpChart is a LIST of bars. The engine's signature is
    `jumpChart(rows, max, d0, parent)` and the only episode that has ever drawn
    one passes four `[label, from, to, shown]` rows. The spec's original
    single-bar `before`/`after` could not express that chart at all.

    Rows are mappings here, not the engine's positional tuples: a script is
    written by hand, and `['GDP.pdf', 22.0, 34.0, '…']` gives an operator no
    way to notice they have swapped the two numbers. The positional form is
    `render.mjs`'s problem, at the other end of `plan.json`.

    `before`/`after` are checked as numbers, not as truthy: a benchmark that
    scored 0 before is a real bar. `shown` is a display override — the engine
    sets it as `html` — so an empty one deliberately blanks the value cell, the
    way `sub: ""` blanks a title card's subtitle.
    """
    if not isinstance(v, list):
        return f"must be a list, got {_type_name(v)}"
    if not v:
        return "must not be empty"
    for i, item in enumerate(v):
        if not isinstance(item, dict):
            return (
                f"[{i}] must be a mapping with `label`, `before` and `after`, "
                f"got {_type_name(item)}"
            )
        if "label" not in item:
            return f"[{i}] needs a `label`"
        if not _is_filled(item["label"]):
            return (
                f"[{i}] `label` must be a non-empty string, got "
                f"{_type_name(item['label'])}"
            )
        for name in ("before", "after"):
            if name not in item:
                return f"[{i}] needs a `{name}`"
            if not _is_number(item[name]):
                return (
                    f"[{i}] `{name}` must be a number, got {_type_name(item[name])}"
                )
        if "shown" in item and not _is_str(item["shown"]):
            return f"[{i}] `shown` must be a string, got {_type_name(item['shown'])}"
    return None


def series_pair(v: Any) -> str | None:
    """Exactly two named series — spec §7.1 writes it as `series[2]`."""
    if not isinstance(v, list):
        return f"must be a list, got {_type_name(v)}"
    if len(v) != 2:
        return f"must name exactly two series, got {len(v)}"
    for i, item in enumerate(v):
        if not _is_filled(item):
            return f"[{i}] must be a non-empty string, got {_type_name(item)}"
    return None


def kpi_items(v: Any) -> str | None:
    """`items[{value, unit, label, decimals}]` — spec §7.1.

    `value` may be a string: the engine's `kpis()` falls back to printing a
    non-numeric value rather than counting up to it. §7.2 constrains the numeric
    ones ("every numeric `value` must appear inside that `quote`"), which is
    Phase 5's check, not this one.
    """
    if not isinstance(v, list):
        return f"must be a list, got {_type_name(v)}"
    if not v:
        return "must not be empty"
    for i, item in enumerate(v):
        if not isinstance(item, dict):
            return f"[{i}] must be a mapping, got {_type_name(item)}"
        if "value" not in item:
            return f"[{i}] needs a `value`"
        val = item["value"]
        if not _is_number(val) and not _is_filled(val):
            return f"[{i}] `value` must be a number or a non-empty string, got {_type_name(val)}"
        if "label" not in item:
            return f"[{i}] needs a `label`"
        if not _is_filled(item["label"]):
            return f"[{i}] `label` must be a non-empty string, got {_type_name(item['label'])}"
        if "unit" in item and not _is_str(item["unit"]):
            return f"[{i}] `unit` must be a string, got {_type_name(item['unit'])}"
        if "decimals" in item:
            d = item["decimals"]
            if not _is_int(d) or d < 0:
                return f"[{i}] `decimals` must be a non-negative integer, got {d!r}"
    return None


# --- the catalogue --------------------------------------------------------------
# Data, not branches: adding a type in Phase 4 is a row here, never a new `if`.
#
# `cited` marks the types that spec §7.2 will not let render without a source:
# "there is no path to rendering a number that isn't in a source". `title` and
# `signoff` assert nothing about the world and require neither — demanding a
# source for a title card would turn the rule into noise operators route around.

BEAT_TYPES: dict[str, dict] = {
    "statement": {"required": {"text": text}, "optional": {}, "cited": False},
    "body": {"required": {"text": text}, "optional": {}, "cited": False},
    "list": {
        "required": {"items": text_list},
        "optional": {"lead": free_text},
        "cited": False,
    },
    "kpis": {"required": {"items": kpi_items}, "optional": {}, "cited": True},
    "jumpChart": {
        # D-068: `rows`, not a single `before`/`after` pair. See `jump_rows`.
        "required": {
            "rows": jump_rows,
            "scale": positive_number,
            "footnote": text,
        },
        "optional": {},
        "cited": True,
    },
    "dumbbell": {
        "required": {
            "rows": rows,
            "series": series_pair,
            "caption": text,
            "footnote": text,
        },
        "optional": {},
        "cited": False,
    },
    "quote": {
        "required": {"text": text, "attribution": text},
        "optional": {},
        "cited": False,
    },
    "title": {"required": {}, "optional": {"sub": free_text}, "cited": False},
    "signoff": {"required": {}, "optional": {"text": free_text}, "cited": False},
    "custom": {"required": {"js": text}, "optional": {}, "cited": False},
}

# Present on every type (spec §7.1, "shared optional fields on every type").
# `hold` is handled separately: it has a default and a positivity rule.
SHARED_TEXT = ("act", "kicker", "src", "quote", "claim_override")


@dataclass(frozen=True)
class Beat:
    """Frozen per D-062 — a snapshot that mutates lies about its file.

    `fields` is the type-specific payload, already validated: only the keys the
    operator actually wrote, so "absent" and "written empty" stay distinct.
    `claim_override` rides in `fields` because it is the one shared field the
    dataclass has no slot for and Phase 5 must not lose it.
    """

    index: int
    type: str
    hold: float
    act: str
    kicker: str
    src: str
    quote: str
    fields: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Script:
    episode: str
    series: str
    status: str
    pace: float
    beats: tuple[Beat, ...]


def _known_types() -> str:
    return ", ".join(sorted(BEAT_TYPES))


def _beat(raw: Any, index: int, where: Any) -> Beat:
    if not isinstance(raw, dict):
        raise ScriptError(
            f"{where}: beat {index} must be a mapping, got {_type_name(raw)}"
        )

    kind = raw.get("type")
    if kind is None:
        raise ScriptError(
            f"{where}: beat {index} has no `type` — one of: {_known_types()}"
        )
    if not _is_str(kind) or kind not in BEAT_TYPES:
        raise ScriptError(
            f"{where}: beat {index} has unknown type {kind!r} — "
            f"known types: {_known_types()}"
        )

    spec = BEAT_TYPES[kind]
    at = f"{where}: beat {index} ({kind}):"

    hold = raw.get("hold", DEFAULT_HOLD)
    if not _is_number(hold) or hold <= 0:
        raise ScriptError(
            f"{at} `hold` must be a positive number of seconds, got {hold!r}"
        )

    for name in SHARED_TEXT:
        if name in raw:
            reason = free_text(raw[name])
            if reason:
                raise ScriptError(f"{at} `{name}` {reason}")

    if spec["cited"]:
        # spec §7.2 — there is no path to rendering a number that isn't in a
        # source. Present-but-empty is not a citation.
        for name in ("src", "quote"):
            if not _is_filled(raw.get(name)):
                raise ScriptError(
                    f"{at} `{name}` is required and must not be empty — a "
                    f"{kind} beat renders numbers, and spec §7.2 allows no path "
                    "to rendering a number that isn't in a source"
                )

    payload: dict = {}
    for name, check in spec["required"].items():
        if name not in raw:
            raise ScriptError(f"{at} `{name}` is required")
        reason = check(raw[name])
        if reason:
            raise ScriptError(f"{at} `{name}` {reason}")
        payload[name] = raw[name]
    for name, check in spec["optional"].items():
        if name not in raw:
            continue
        reason = check(raw[name])
        if reason:
            raise ScriptError(f"{at} `{name}` {reason}")
        payload[name] = raw[name]
    if "claim_override" in raw:
        payload["claim_override"] = raw["claim_override"]

    return Beat(
        index=index,
        type=kind,
        hold=float(hold),
        act=raw.get("act", ""),
        kicker=raw.get("kicker", ""),
        src=raw.get("src", ""),
        quote=raw.get("quote", ""),
        fields=payload,
    )


def _meta_str(meta: dict, key: str, default: str, where: Any) -> str:
    value = meta.get(key, default)
    if not _is_str(value):
        raise ScriptError(
            f"{where}: `{key}` must be a string, got {_type_name(value)}"
        )
    return value


def load_script_with_digest(episode: Episode) -> tuple[Script, str]:
    """Parse and validate `script.yaml`, returning it with its sha256.

    The digest belongs here rather than in `plan.py` so that the bytes hashed
    and the beats validated are the same file contents — `script_sha256` binds
    approval to a script, and a hash of a different read is a hash of a
    different script.
    """
    where = episode.script_path
    try:
        digest = hashlib.sha256(where.read_bytes()).hexdigest()
    except OSError as e:
        raise ScriptError(f"{where}: cannot read script.yaml — {e}")

    # Raises EpisodeError if the file is not a script at all (unreadable, bad
    # metadata document). That is a lower-level failure than a schema one and
    # keeps its own type.
    meta, beats_text, _ = read_script(where)

    if beats_text is None:
        raise ScriptError(
            f"{where}: no beats document — script.yaml needs a `---` separator "
            "line, then `beats:`"
        )
    try:
        doc = yaml.safe_load(beats_text)
    except yaml.YAMLError as e:
        raise ScriptError(f"{where}: cannot parse beats — {e}")
    if doc is None:
        raise ScriptError(f"{where}: no beats to render")
    if not isinstance(doc, dict) or "beats" not in doc:
        raise ScriptError(
            f"{where}: the beats document must be a mapping with a `beats:` key"
        )
    raw_beats = doc["beats"]
    if not isinstance(raw_beats, list):
        raise ScriptError(f"{where}: `beats` must be a list")
    if not raw_beats:
        raise ScriptError(f"{where}: no beats to render")

    pace = meta.get("pace", 1.0)
    if not _is_number(pace) or pace <= 0:
        raise ScriptError(f"{where}: `pace` must be a positive number, got {pace!r}")

    script = Script(
        episode=_meta_str(meta, "episode", episode.id, where),
        series=_meta_str(meta, "series", episode.series_slug, where),
        status=_meta_str(meta, "status", Status.DRAFT.value, where),
        pace=float(pace),
        beats=tuple(_beat(raw, i, where) for i, raw in enumerate(raw_beats)),
    )
    return script, digest


def load_script(episode: Episode) -> Script:
    """Parse and validate `script.yaml`. Never writes."""
    return load_script_with_digest(episode)[0]


def validate_acts(acts: Any, where: Any) -> None:
    """Validate `[[structure.acts]]` from `series.toml` (spec §6).

    `beats` counts are advisory targets, but an advisory `-1` is still nonsense
    handed to the storyboard skill. `label` is free-form and is not checked:
    the spec's own cold-open row carries `label = ""`.
    """
    if not isinstance(acts, list):
        raise ScriptError(
            f"{where}: [[structure.acts]] must be a list of tables, got "
            f"{_type_name(acts)}"
        )
    for i, act in enumerate(acts):
        at = f"{where}: act {i}"
        if not isinstance(act, dict):
            raise ScriptError(
                f"{at} must be a table with an `id`, got {_type_name(act)} — "
                "write [[structure.acts]] blocks, not a bare acts = value"
            )
        if "id" not in act:
            raise ScriptError(f"{at} has no `id` — a beat names its act by id")
        if not _is_str(act["id"]):
            raise ScriptError(
                f"{at}: `id` must be a string, got {_type_name(act['id'])}"
            )
        if "beats" in act:
            count = act["beats"]
            if not _is_int(count) or count <= 0:
                raise ScriptError(
                    f"{at}: `beats` must be a positive integer, got {count!r}"
                )

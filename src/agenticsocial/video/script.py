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
    emit. Phase 4 Task 3 closed the gap, so the two coincide today; they are
    still separate questions, and the next type §7.1 grows will be valid before
    anything can draw it. An operator must be able to tell that from a typo.

READ ONLY. Nothing here writes: `script.yaml`'s bytes are load-bearing for
`script_sha256` (spec §10, DECISIONS D-026), so not even normalisation is
allowed. `read_script` hands us document 2 verbatim; we parse a copy.
"""
from __future__ import annotations

import decimal
import hashlib
import re
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
# Phase 4 Task 1 added a builder in engine/planbuild.js for each of the five
# text types alongside `statement`; Task 2 added the two chart types spec §7.2
# calls strictly verifiable; Task 3 adds `dumbbell`, whose two-tone merged
# marker the engine had CSS for and no function, and `custom`, which runs the
# author's own JS. That closes the catalogue: RENDERABLE == set(BEAT_TYPES).
#
# It stays a separate name rather than becoming `set(BEAT_TYPES)`. The two gates
# answer different questions — "is this a well-formed beat?" and "can plan.py
# emit it?" — and the next type added to §7.1 is valid before anyone has written
# its builder. Collapsing them would make that type render a blank card on the
# day it is described. A name added here without a builder renders a blank card,
# so
# tests/test_video_planbuild.py::test_every_renderable_type_has_a_builder holds
# this set and `BUILDERS` to each other.
RENDERABLE = frozenset(
    {
        "statement",
        "body",
        "list",
        "quote",
        "title",
        "signoff",
        "kpis",
        "jumpChart",
        "dumbbell",
        "custom",
    }
)


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


def dumbbell_rows(v: Any) -> str | None:
    """`rows[{label, values[2], shown?}]` — the AMIE chart, named.

    Phase 3 left this shape unconstrained on purpose: spec §7.1 writes only
    `rows[]`, and the one chart that had ever been drawn built its rows inline
    in `engine/content/2026-08-12.js`. Phase 4 Task 3 draws it, so the columns
    have to be named, and they are named after that episode — the only evidence
    there is.

    `values` is a PAIR aligned with `series[2]`, not two keys. The two numbers
    are the same measurement of two entities and `series` already says which is
    which; `a`/`b` would leave the operator holding that mapping in their head.

    They are FRACTIONS OF THE TRACK, in `[0, 1]`, checked by
    `dumbbell_within_track`. There is no `scale` field because there is no
    numeric axis: this type exists for sources that publish ratings rather than
    scores (spec §7.2), and it renders no numbers at all.

    The episode's row spec has a fifth column, a boolean `up` saying whether the
    two markers separate. It is deliberately NOT a field: it is exactly
    `a != b`, and a declared copy of something the numbers already state can
    disagree with them. `up: false` on a row whose values differ would draw one
    merged marker over two different ratings — the hidden-series failure spec
    §7.2 names, with the schema's blessing.

    `note` is the row's finding in words ("on par"). Optional, and free text:
    a row without one has an empty cell, which is not the same as a crash.
    """
    if not isinstance(v, list):
        return f"must be a list, got {_type_name(v)}"
    if not v:
        return "must not be empty"
    for i, item in enumerate(v):
        if not isinstance(item, dict):
            return (
                f"[{i}] must be a mapping with `label` and `values`, got "
                f"{_type_name(item)}"
            )
        if "label" not in item:
            return f"[{i}] needs a `label`"
        if not _is_filled(item["label"]):
            return (
                f"[{i}] `label` must be a non-empty string, got "
                f"{_type_name(item['label'])}"
            )
        if "values" not in item:
            return f"[{i}] needs `values`"
        values = item["values"]
        if not isinstance(values, list):
            return f"[{i}] `values` must be a list, got {_type_name(values)}"
        if len(values) != 2:
            return (
                f"[{i}] `values` must be one number per series, so exactly two, "
                f"got {len(values)}"
            )
        for k, value in enumerate(values):
            if not _is_number(value):
                return (
                    f"[{i}] `values[{k}]` must be a number, got {_type_name(value)}"
                )
        if "note" in item and not _is_str(item["note"]):
            return f"[{i}] `note` must be a string, got {_type_name(item['note'])}"
    return None


def dumbbell_within_track(payload: dict) -> str | None:
    """Every position is a fraction of the track, so `[0, 1]` inclusive.

    The same geometry rule as `jump_rows_within_scale`, and it needs no `scale`
    to state it: the engine positions each marker at `value * 100 + '%'`, so
    `1.4` is drawn 40% past the right edge and `-0.2` off the left. Inclusive at
    both ends — a marker at 0 or at 1 is at an end of the track, which is on the
    card — and `0` is a real position, so this may not be written `if not v`.
    """
    for i, row in enumerate(payload.get("rows", [])):
        if not isinstance(row, dict):
            continue  # dumbbell_rows has already refused it
        values = row.get("values")
        if not isinstance(values, list):
            continue
        for k, value in enumerate(values):
            if not _is_number(value):
                continue
            if not 0 <= value <= 1:
                return (
                    f"`rows[{i}]` `values[{k}]` is {value!r}, outside the track "
                    "— a dumbbell has no `scale` because it has no numeric "
                    "axis: a value is a fraction of the track, from 0 at the "
                    "left end to 1 at the right, and the engine draws each "
                    "marker at `value * 100%`"
                )
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


def jump_rows_within_scale(payload: dict) -> str | None:
    """R4 — a row value outside `[0, scale]` is refused, not clipped.

    A cross-field rule, so it cannot live in a per-field checker: `rows` and
    `scale` only mean anything together. The engine positions every dot as
    `value / max * 100 + '%'` and sizes the gain segment the same way, so a row
    above the scale is drawn past the end of its track — off the card, or
    clipped by whatever overflow the stage happens to have — and a negative one
    is drawn to the left of zero.

    Clipping to the scale would be worse than refusing: the bar would sit at
    100% and read as the maximum, which is a number the plan did not carry.
    That is R2's failure wearing a geometry costume, and it is silent.

    The bound is INCLUSIVE at both ends. `0` is a benchmark that scored nothing
    before — the most interesting bar on the chart — and a value equal to the
    scale is drawn at 100% of the track, which is on the card.
    """
    scale = payload.get("scale")
    if not _is_number(scale):
        return None  # positive_number has already refused it, with a better message
    for i, row in enumerate(payload.get("rows", [])):
        for name in ("before", "after"):
            value = row.get(name)
            if not _is_number(value):
                continue  # jump_rows has already refused it
            if not 0 <= value <= scale:
                return (
                    f"`rows[{i}]` `{name}` is {value!r}, outside the chart's "
                    f"`scale` of {scale} — the engine draws every dot at "
                    f"`{name} / scale`, so this bar lands off its track. Raise "
                    "`scale` or fix the value; it is not clipped, because a "
                    "clipped bar reads as the maximum and that is a number "
                    "nothing in the script says"
                )
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


def _as_displayed(value: float, decimals: int) -> str:
    """The glyphs `count()` would put on screen for this value.

    Message-only, but it has to be right or the error tells an operator to look
    for a number the frame never shows. `toFixed` and `Math.round` both round
    half AWAY from zero on the decimal the operator wrote; Python's `round` and
    `format` round half to EVEN, so `format(0.75, '.0f')` is `0` where the
    engine renders `1`. `repr` first, so the value quantised is the one they
    typed rather than its binary neighbour.
    """
    step = decimal.Decimal(1).scaleb(-decimals)
    return str(decimal.Decimal(repr(value)).quantize(step, decimal.ROUND_HALF_UP))


def kpi_items(v: Any) -> str | None:
    """`items[{value, unit, label, decimals}]` — spec §7.1, plus `prefix`.

    `value` may be a string: the engine's `kpis()` falls back to printing a
    non-numeric value rather than counting up to it. §7.2 constrains the numeric
    ones ("every numeric `value` must appear inside that `quote`"), which is
    Phase 5's check, not this one.

    **R2 — display rounding is refused.** `count()` formats with
    `decimals ? v.toFixed(decimals) : Math.round(v)`, so `value: 0.756,
    decimals: 1` puts `0.8` on the screen. `0.8` is in no source, in no quote
    and in no plan: Phase 5 would verify `0.756` against the quote, pass, and
    ship a video showing a number nobody checked. If an author wants `0.8` on
    screen the script says `0.8`, because the script is what gets verified.

    Note where the hole is widest: `decimals` is OPTIONAL, and its absence is
    not "print the value as written" — it is `Math.round(v)`. So absent is
    checked as 0, and `value: 0.75` with no `decimals` is refused for reaching
    the frame as `1`.

    `prefix` and `unit` are the opposite case and are deliberately free:
    `$0.75` and `0.75` are the same figure differently read, and so is `2,000`.
    A symbol changes how a number reads, not what it is.

    `prefix` is not in the spec's field list; `unit` alone cannot express the
    committed episode, which renders `$0.75` AND `50%` from the same engine
    call. `unit` is the SUFFIX and `prefix` the leading symbol — a fixed table
    of "symbols that lead" would be a global that retroactively changes what
    past episodes rendered, which is the class of failure this phase exists to
    close.
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
        for name in ("unit", "prefix"):
            if name in item and not _is_str(item[name]):
                return f"[{i}] `{name}` must be a string, got {_type_name(item[name])}"
        decimals = item.get("decimals", 0)
        if "decimals" in item and (not _is_int(decimals) or decimals < 0):
            return f"[{i}] `decimals` must be a non-negative integer, got {decimals!r}"
        # Only numbers are formatted; a string value is printed verbatim.
        if _is_number(val) and round(val, decimals) != val:
            return (
                f"[{i}] `value` {val!r} would reach the frame as "
                f"{_as_displayed(val, decimals)} at `decimals: {decimals}`"
                + ("" if "decimals" in item else " (the default)")
                + " — display rounding invents a figure that is in no source, "
                "no quote and no plan; write the number you want on screen"
            )
    return None


# --- `custom`: executed, and therefore attested ---------------------------------

# The three spellings a custom beat is most likely to reach for, written as
# calls rather than as bare words: `Math.round` and an identifier called
# `randomised` are not non-determinism, and a guard that refuses them teaches
# authors that the check is noise. `\s*` around the dot because `Math . random`
# is the same call.
NONDETERMINISTIC = (
    (re.compile(r"\bDate\s*\.\s*now\s*\("), "Date.now"),
    (re.compile(r"\bMath\s*\.\s*random\s*\("), "Math.random"),
    (re.compile(r"\bperformance\s*\.\s*now\s*\("), "performance.now"),
)


def custom_js(v: Any) -> str | None:
    """The one authored field that is EXECUTED, in the page, as written.

    `__seek(t)` positioning every element from `t` alone is the invariant that
    makes a render reproducible and any single frame re-creatable months later.
    Nothing else an operator writes can break it; this can, because everything
    else is data and this is code.

    **This is a lint, not a sandbox.** It is a regex over three spellings. It
    catches the accident — an author who reaches for `Math.random()` out of
    habit — and it does not catch anyone who does not want to be caught:
    `window['Ma'+'th'].random()` walks straight past it, and so does any value
    fetched, computed or read off the DOM. Same framing as D-062: the guard
    raises the floor, it is not a boundary. What the beat renders is covered by
    `attest`, which is a person's signature rather than a check.
    """
    reason = text(v)
    if reason:
        return reason
    for pattern, name in NONDETERMINISTIC:
        if pattern.search(v):
            return (
                f"calls {name}() — a custom beat is executed in the page, and "
                "`__seek(t)` must position every element from `t` alone or the "
                "render stops being reproducible. Derive the value from the "
                "animation's own progress instead. (This is a LINT, not a "
                "sandbox: it greps for three spellings and catches the "
                "accident, not the adversary — a computed call goes straight "
                "past it, so determinism here is still yours to keep.)"
            )
    return None


def attestation(v: Any) -> str | None:
    """R5 — spec §7.1 says `custom` needs "manual attestation" and names no field.

    This is that field. No mechanical check can verify what arbitrary rendering
    code puts on a screen; that is what "arbitrary" means. The honest substitute
    is not a weaker check dressed as a strong one — it is a sentence in which a
    person states what the beat displays and takes responsibility for it, shown
    to the operator in `agsoc video review` before they approve.

    Empty is refused for the same reason a blank `src` is not a citation: it
    satisfies every "is the key there" check and states nothing, which is the
    approval theatre the field exists to avoid.
    """
    if not _is_str(v):
        return (
            f"must be a string, got {_type_name(v)} — a `custom` beat renders "
            "whatever its `js` draws, and nothing can check that mechanically; "
            "`attest` is where a person says what it shows and signs for it"
        )
    if not v.strip():
        return (
            "must not be empty — an attestation nobody wrote is worse than "
            "none: it puts a record of a judgement in front of the approver "
            "that was never made"
        )
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
        # R4. Runs after every field has checked out, because it reads two of
        # them at once. See `jump_rows_within_scale`.
        "cross": jump_rows_within_scale,
    },
    "dumbbell": {
        "required": {
            "rows": dumbbell_rows,
            "series": series_pair,
            "caption": text,
            # Spec §7.2: a dumbbell "encodes direction only and must carry a
            # footnote saying so". It renders no numbers, so the footnote is the
            # only place the reader is told what the markers mean.
            "footnote": text,
        },
        "optional": {},
        "cited": False,
        "cross": dumbbell_within_track,
    },
    "quote": {
        "required": {"text": text, "attribution": text},
        "optional": {},
        "cited": False,
    },
    "title": {"required": {}, "optional": {"sub": free_text}, "cited": False},
    "signoff": {"required": {}, "optional": {"text": free_text}, "cited": False},
    # Executed, and therefore attested. `js` is linted for the three obvious
    # non-determinism sources (a lint, not a sandbox — see `custom_js`), and
    # `attest` is the manual attestation spec §7.1 requires and does not name.
    "custom": {
        "required": {"js": custom_js, "attest": attestation},
        "optional": {},
        "cited": False,
    },
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
    # Rules that read more than one field at once, once every field is known to
    # be well-formed on its own. Data, not a branch — `cross` is absent on the
    # types that have no such rule.
    cross = spec.get("cross")
    if cross is not None:
        reason = cross(payload)
        if reason:
            raise ScriptError(f"{at} {reason}")

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

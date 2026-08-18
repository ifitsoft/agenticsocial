"""`script.yaml` + `series.toml` -> `plan.json`, the Python->Node handoff.

The engine cannot read YAML: `scene.html` loads its script with `document.write`
because `fetch` and ES modules are both CORS-blocked over `file://`. Rather than
give Node a YAML dependency, Python parses and emits JSON, and `render.mjs`
consumes that. This keeps Node a pure renderer.

This module owns RESOLUTION, not schema: pace, absolute times, frame numbers and
the JSON shape Node reads. `script.py` decides what a beat is; everything here
consumes an already-valid `Script`.

Two failures that look alike and are not:

  * an **unknown** type — a typo, fixed in script.yaml (raised by script.py);
  * a **valid but unrenderable** type — a real beat this phase cannot draw yet,
    fixed by implementing it (raised here).

Emitting one message for both would tell an operator to go and fix a file that
is already correct.

It only ever READS the script — `script.yaml` bytes are load-bearing for
`script_file_sha256` (spec 10, DECISIONS D-026).
"""
from __future__ import annotations

import ast
import inspect
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

from ..workspace import atomic_write
from .models import Episode, Series, SeriesError
from .script import (
    BEAT_TYPES,
    DEFAULT_HOLD,
    RENDERABLE,
    Script,
    ScriptError,
    load_script_with_digest,
    validate_acts,
)
from .series import validate_design

FPS = 30
# The renderable gate, named for the callers that already import it. It is
# script.py's RENDERABLE, not a second list: two frozensets drift the first time
# either is widened, which is the D-036 pattern that has produced five defects.
SUPPORTED_BEATS = RENDERABLE
FORMATS = {"vertical": {"w": 1080, "h": 1920}}

__all__ = [
    "FPS",
    "DEFAULT_HOLD",
    "SUPPORTED_BEATS",
    "FORMATS",
    "PlanError",
    "act_labels",
    "RuntimeCheck",
    "build_plan",
    "check_runtime",
    "write_plan",
    "SERIES_ATTR_COVERAGE",
    "series_reads",
    "series_reads_of",
    "series_inputs",
]


class PlanError(Exception):
    pass


def act_labels(series: Series) -> dict[str, str]:
    """`act id -> display label`, resolved once so `planbuild.js` does no lookup.

    A beat names its act by ID; the label is display text. Resolving here means
    an operator can reword `label = "03 — Agents"` without silently unwiring
    every beat that points at act `03`.

    Falls back to the id when an act declares no usable `label`. `validate_acts`
    requires an `id` and deliberately does not constrain `label` — spec §6's own
    cold-open row carries `label = ""` — so `""` is a label an operator chose and
    is kept, while a missing or non-string one is not a label at all and would
    otherwise be interpolated into the chip as `None` or `5`.
    """
    labels: dict[str, str] = {}
    for act in series.acts:
        if not isinstance(act, dict):
            continue
        act_id = act.get("id")
        if not isinstance(act_id, str):
            continue
        label = act.get("label")
        # First declaration wins, so a duplicated id resolves deterministically.
        labels.setdefault(act_id, label if isinstance(label, str) else act_id)
    return labels


@dataclass(frozen=True)
class RuntimeCheck:
    """Is this episode the length the series asks for?

    Frozen per D-062. Phase 7's `approve` refuses on this object, and a verdict
    a caller can edit after the fact is not a verdict.

    `delta` is signed — `total - target`. An operator needs to know whether to
    cut or to add, and `abs()` here would make them work it out again.
    """

    total_sec: float
    target_sec: int
    tolerance_sec: int
    within: bool
    delta: float


def check_runtime(script: Script, series: Series) -> RuntimeCheck:
    """Total runtime against `[runtime]` in series.toml. Reads and writes no files.

    Total is `sum(hold) * pace` — the authored holds scaled once at the end,
    not per beat. That is deliberately NOT how `build_plan` computes
    `total_sec`: the plan rounds each beat to 3dp because frame numbers derive
    from it, so the two can disagree in the third decimal. This is the number
    the duration rule is written against, and it is the one Phase 7 must gate
    on.

    Both totals are rounded to 3dp before comparing, because R2's boundary is
    INCLUSIVE and binary floats make inclusivity accidental: eight 16.0s holds
    sum to 128.00000000000003 on some paths, and a `<=` against an unrounded
    sum would fail an episode that hits the documented bound exactly.

    D-063 — the freshness question. This function deliberately does NOT re-read
    series.toml. It is a computation over two values, not a gate: it decides
    nothing and writes nothing, so there is no moment for a stale read to be
    exploited. Re-reading from `series.dir` would also buy almost nothing —
    the path comes from the same object the value did, so a caller who can
    forge one can forge the other; it would only narrow staleness, not
    forgery, while making a pure function do IO.

    The guarantee therefore has to live at the gate, not here. When Phase 7
    builds `approve`, it must load series.toml and script.yaml ITSELF,
    immediately before the transition, in the same function that performs the
    write — the way `episode.set_status` re-reads the status it gates on. A
    gate that accepts a `Series` parameter from its caller is the fourth
    bypass, whatever this function does internally. See the Phase 3 Task 2
    report.
    """
    total = round(sum(beat.hold for beat in script.beats) * script.pace, 3)
    delta = round(total - series.target_sec, 3)
    return RuntimeCheck(
        total_sec=total,
        target_sec=series.target_sec,
        tolerance_sec=series.tolerance_sec,
        # `<=`, not `<`: the bound is inclusive. And `tolerance_sec: 0` is a
        # legitimate setting meaning "match target_sec exactly" — series.py
        # allows it on purpose, so it reaches here and must not be read as
        # "no limit".
        within=abs(delta) <= series.tolerance_sec,
        delta=delta,
    )


def build_plan(series: Series, episode: Episode, fmt: str = "vertical") -> dict:
    if fmt not in FORMATS:
        raise PlanError(
            f"unsupported format {fmt!r} — this phase renders: "
            f"{', '.join(sorted(FORMATS))}"
        )
    where = episode.script_path

    # A schema failure surfaces as PlanError because this is the entry point the
    # CLI wraps; the wording is script.py's and is passed through unchanged.
    try:
        script, digest = load_script_with_digest(episode)
        validate_acts(series.acts, series.dir / "series.toml")
    except ScriptError as e:
        raise PlanError(str(e)) from e

    # Again, having already run in load_series. Not redundant: this is the last
    # point before plan.json exists on disk and Node is started, and build_plan
    # takes a `Series` from its caller — the same reason check_runtime's docstring
    # gives for why a gate must re-verify rather than trust what it was handed.
    try:
        validate_design(series.design, series.dir / "series.toml")
    except SeriesError as e:
        raise PlanError(str(e)) from e

    labels = act_labels(series)
    pace = script.pace
    beats_out: list[dict] = []
    at = 0.0
    for beat in script.beats:
        if beat.type not in RENDERABLE:
            raise PlanError(
                f"{where}: beat {beat.index} ({beat.type}) is a valid beat type "
                f"but cannot be rendered yet — this phase renders: "
                f"{', '.join(sorted(RENDERABLE))}"
            )
        hold = round(beat.hold * pace, 3)
        if round(hold * FPS) < 1:
            raise PlanError(
                f"{where}: beat {beat.index} lasts {hold}s at pace {pace}, under "
                f"one frame at {FPS}fps — it would not appear in the render"
            )
        start, end = round(at, 3), round(at + hold, 3)
        # The type's own fields, in catalogue order (required, then optional),
        # and only the ones the operator actually wrote — script.py keeps
        # "absent" and "written empty" distinct and a plan that blanks the
        # difference hands the renderer a decision the operator did not make.
        #
        # Driven off BEAT_TYPES rather than dumping `beat.fields`: `fields` also
        # carries `claim_override`, which is Phase 5's verification input and not
        # content. Nothing the renderer cannot draw belongs in front of it.
        spec = BEAT_TYPES[beat.type]
        payload = {
            name: beat.fields[name]
            for name in (*spec["required"], *spec["optional"])
            if name in beat.fields
        }
        # emit in the documented order
        beats_out.append(
            {
                "type": beat.type,
                "act": beat.act,
                # The id is kept alongside the label: Phase 5 anchors claims to
                # beats, and it must join on the stable key, not on display text.
                # An undeclared id falls through as its own label rather than
                # raising — a script written before its series declared acts
                # still renders (R3 negative, spec §6 "advisory").
                "act_label": labels.get(beat.act, beat.act),
                "hold": hold,
                "start": start,
                "end": end,
                "start_frame": round(start * FPS),
                "end_frame": round(end * FPS),
                "kicker": beat.kicker,
                **payload,
                "src": beat.src,
                # The citation travels only with the types that may not render
                # without it, and it travels because `planbuild.js` enforces
                # that rule at the far end. A plan can reach the page without
                # passing through this module at all — `render.mjs --plan`
                # reads any JSON file, and engine/determinism.test.mjs writes
                # its own — so the renderer's gate is the one that holds for
                # spec §7.2's "no path", and a gate cannot check a field it was
                # never handed. On an uncited type there is nothing to enforce,
                # and a `quote` key in front of the renderer would be one more
                # field it has no business drawing.
                **({"quote": beat.quote} if spec["cited"] else {}),
            }
        )
        at = end

    return {
        "episode": episode.id,
        "series": series.slug,
        # The display name, next to the slug it belongs to. `title` and
        # `signoff` render it at 150px; the slug is a filesystem key and
        # `the-brief` is not what the brand card says.
        "series_name": series.name,
        "byline": series.byline,
        # `script_file_sha256`, not `script_sha256`: this is the WHOLE FILE,
        # metadata document included, and the APPROVAL's `script_sha256` covers
        # the beats document alone (see `episode.beats_sha256`). One key with
        # two meanings in two files is the D-036 pattern, and these two are
        # exactly the pair someone would eventually compare.
        "script_file_sha256": digest,
        "format": {"name": fmt, **FORMATS[fmt]},
        "fps": FPS,
        "pace": pace,
        "total_sec": beats_out[-1]["end"],
        "total_frames": beats_out[-1]["end_frame"],
        "design": dict(series.design),
        "beats": beats_out,
    }


def write_plan(series: Series, episode: Episode, fmt: str = "vertical") -> Path:
    plan = build_plan(series, episode, fmt)
    path = episode.out_dir / f"plan-{fmt}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return path


# --- §10: what an approval has to cover, derived from what this module copies -------
#
# `[design]` is copied WHOLE into the plan and repaints every frame of every
# episode in the series; `name` and `byline` are drawn at 150px on the title and
# signoff cards; act labels are the chip on every beat. All four live in
# `series.toml` — a file the approval did not read at all until Phase 7 Task 3.
#
# The set an approval covers is therefore NOT a list written by hand somewhere
# else. It is read out of `build_plan`'s own source, so a `series` attribute this
# module starts copying tomorrow is covered the day it is copied, and a `[design]`
# token added tomorrow is covered without anyone touching this file at all —
# `design` is copied as a whole table, so its keys are never enumerated.
#
# What cannot be derived is REFUSED, never skipped (D-096): an attribute nobody
# has classified, a `series` bound to another name, a `series` handed whole to a
# helper, or a value JSON cannot compare all raise `PlanError`, and the gate
# turns that into a refused approval. A silent gap here is indistinguishable
# from coverage, which is the failure this whole mechanism exists to prevent.

# Every attribute of `Series` that this module reads on the way to `plan.json`,
# and whether it describes the FRAME (an approval must cover it) or the episode's
# IDENTITY on this machine (it must not — a workspace moved to another path, or a
# series renamed on disk, would otherwise read as a change to the video).
SERIES_ATTR_COVERAGE = {
    "name": "frame",     # `series_name` — drawn at 150px on title and signoff
    "byline": "frame",   # drawn beside it
    "design": "frame",   # the palette and type, on every frame
    "acts": "frame",     # via `act_labels` — the act chip on every beat
    "slug": "identity",  # the directory this episode lives in
    "dir": "identity",   # where that directory is on this machine
}

# Functions `build_plan` may hand the whole `Series` to. Each is scanned in turn,
# so what it reads is covered too. Anything else defeats the derivation and is
# refused rather than trusted.
_SERIES_HELPERS = ("act_labels",)

# An attribute the plan does not receive raw. `acts` is the one that matters: the
# plan is given the RESOLVED labels, so rewording a label is drift and changing
# an act's `beats` budget — which reaches no frame — is not.
_SERIES_RESOLVERS = {
    "design": lambda s: dict(s.design),
    "acts": act_labels,
}


def series_reads_of(func) -> frozenset[str]:
    """Every `series.<attr>` read in `func`, from its AST. Refuses evasions.

    AST, not a regex: `build_plan`'s comments and messages are full of the words
    "series.toml", and a text scan would invent an attribute called `toml` and
    then refuse to approve anything because nobody had classified it.

    Two things would let a read slip past the scan, and both raise instead of
    passing quietly, because a derivation that can be defeated silently is not a
    derivation:

      * `s = series` — the reads then happen on a name this cannot follow;
      * `helper(series)` for a helper not in `_SERIES_HELPERS` — the reads then
        happen in a function this did not scan.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    reads: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "series":
                reads.add(node.attr)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            if node.value.id == "series":
                raise PlanError(
                    f"{func.__name__} binds `series` to another name, so what it "
                    "reads out of series.toml can no longer be derived — and an "
                    "approval that cannot name what it covers covers nothing. "
                    "Read `series.<attr>` directly, or add the helper to "
                    "_SERIES_HELPERS"
                )
        elif isinstance(node, ast.Call):
            callee = node.func.id if isinstance(node.func, ast.Name) else None
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id == "series":
                    if callee not in _SERIES_HELPERS:
                        raise PlanError(
                            f"{func.__name__} hands the whole `series` to "
                            f"{callee or 'a call'}(), whose reads this cannot "
                            "see. Add it to _SERIES_HELPERS so it is scanned "
                            "too, or pass the attribute it needs"
                        )
    return frozenset(reads)


def series_reads() -> frozenset[str]:
    """Every `Series` attribute that reaches `plan.json`, scanned, not listed."""
    reads: set[str] = set()
    scanned = [build_plan] + [globals()[name] for name in _SERIES_HELPERS]
    for func in scanned:
        reads |= series_reads_of(func)
    return frozenset(reads)


def series_inputs(series: Series) -> dict:
    """The `series.toml` values that reach the frame, as the plan receives them.

    This is what `approve` signs and what `approval_drift` compares — §10's rule
    applied to the half of the render that does not live in `script.yaml`. Keys
    are the `Series` attribute names, so the drift message can point at the
    field an operator would edit.

    Values only, never the file's bytes: a comment or a reordering in
    `series.toml` must not invalidate an approval, and hashing the file would
    make both of them approval-invalidating events.
    """
    inputs: dict = {}
    for attr in sorted(series_reads()):
        coverage = SERIES_ATTR_COVERAGE.get(attr)
        if coverage is None:
            raise PlanError(
                f"plan.py copies `series.{attr}` into plan.json and nothing says "
                "whether it reaches the frame, so an approval cannot honestly "
                "claim to cover it. Classify it in plan.SERIES_ATTR_COVERAGE as "
                "'frame' (an approval must bind it) or 'identity' (it names "
                "where the episode lives, not what it looks like). Refusing "
                "rather than skipping: a value nobody classified is not a value "
                "nobody has to think about"
            )
        if coverage != "frame":
            continue
        value = _SERIES_RESOLVERS.get(attr, lambda s, a=attr: getattr(s, a))(series)
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as e:
            raise PlanError(
                f"[design]/`series.{attr}` holds a value an approval cannot "
                f"compare — {value!r} ({e}). Dates, times and non-finite numbers "
                "have no comparable form here; write it as a string. Refusing "
                "rather than dropping it: an approval that silently skips a "
                "value covers less than it says it does"
            ) from e
        inputs[attr] = value
    return inputs

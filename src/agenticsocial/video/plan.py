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
`script_sha256` (spec 10, DECISIONS D-026).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..workspace import atomic_write
from .models import Episode, Series
from .script import (
    DEFAULT_HOLD,
    RENDERABLE,
    ScriptError,
    load_script_with_digest,
    validate_acts,
)

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
    "build_plan",
    "write_plan",
]


class PlanError(Exception):
    pass


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
        # emit in the documented order
        beats_out.append(
            {
                "type": beat.type,
                "act": beat.act,
                "hold": hold,
                "start": start,
                "end": end,
                "start_frame": round(start * FPS),
                "end_frame": round(end * FPS),
                "kicker": beat.kicker,
                "text": beat.fields["text"],
                "src": beat.src,
            }
        )
        at = end

    return {
        "episode": episode.id,
        "series": series.slug,
        "byline": series.byline,
        "script_sha256": digest,
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

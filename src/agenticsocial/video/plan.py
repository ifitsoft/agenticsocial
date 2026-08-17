"""`script.yaml` + `series.toml` -> `plan.json`, the Python->Node handoff.

The engine cannot read YAML: `scene.html` loads its script with `document.write`
because `fetch` and ES modules are both CORS-blocked over `file://`. Rather than
give Node a YAML dependency, Python parses and emits JSON, and `render.mjs`
consumes that. This keeps Node a pure renderer.

This module is the first code in the project to parse the beats document. It
only ever READS it — `script.yaml` bytes are load-bearing for `script_sha256`
(spec 10, DECISIONS D-026).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ..workspace import atomic_write
from .episode import read_script
from .models import Episode, Series

FPS = 30
DEFAULT_HOLD = 3.0
SUPPORTED_BEATS = frozenset({"statement"})
FORMATS = {"vertical": {"w": 1080, "h": 1920}}


class PlanError(Exception):
    pass


def _load_script(episode: Episode) -> tuple[dict, list, str]:
    """One read. Metadata, beats and the hash must describe the same bytes."""
    raw = episode.script_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    meta, beats_text, _ = read_script(episode.script_path)
    if beats_text is None:
        raise PlanError(f"{episode.script_path}: no beats document")
    try:
        doc = yaml.safe_load(beats_text)
    except yaml.YAMLError as e:
        raise PlanError(f"{episode.script_path}: cannot parse beats — {e}")
    if doc is None:
        raise PlanError(f"{episode.script_path}: no beats to render")
    if not isinstance(doc, dict) or "beats" not in doc:
        raise PlanError(
            f"{episode.script_path}: the beats document must be a mapping with a "
            "`beats:` key"
        )
    beats = doc["beats"]
    if not isinstance(beats, list):
        raise PlanError(f"{episode.script_path}: `beats` must be a list")
    if not beats:
        raise PlanError(f"{episode.script_path}: no beats to render")
    return meta, beats, digest


def _statement(raw: dict, index: int, where: Path) -> dict:
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise PlanError(f"{where}: beat {index} (statement) needs a non-empty `text`")
    hold = raw.get("hold", DEFAULT_HOLD)
    if not isinstance(hold, (int, float)) or isinstance(hold, bool) or hold <= 0:
        raise PlanError(f"{where}: beat {index} has a non-positive `hold`")
    return {
        "type": "statement",
        "act": str(raw.get("act", "")),
        "hold": float(hold),
        "kicker": str(raw.get("kicker", "")),
        "text": text,
        "src": str(raw.get("src", "")),
    }



def build_plan(series: Series, episode: Episode, fmt: str = "vertical") -> dict:
    if fmt not in FORMATS:
        raise PlanError(
            f"unsupported format {fmt!r} — this phase renders: "
            f"{', '.join(sorted(FORMATS))}"
        )
    where = episode.script_path
    meta, raw_beats, digest = _load_script(episode)

    pace = meta.get("pace", 1.0)
    if not isinstance(pace, (int, float)) or isinstance(pace, bool) or pace <= 0:
        raise PlanError(f"{where}: `pace` must be a positive number")
    pace = float(pace)

    beats_out: list[dict] = []
    at = 0.0
    for i, raw in enumerate(raw_beats):
        if not isinstance(raw, dict):
            raise PlanError(f"{where}: beat {i} must be a mapping")
        kind = raw.get("type")
        if not kind:
            raise PlanError(f"{where}: beat {i} has no `type`")
        if kind not in SUPPORTED_BEATS:
            raise PlanError(
                f"{where}: beat {i} has unsupported type {kind!r} — this phase "
                f"renders: {', '.join(sorted(SUPPORTED_BEATS))}"
            )
        b = _statement(raw, i, where)
        hold = round(b["hold"] * pace, 3)
        start, end = round(at, 3), round(at + hold, 3)
        b.update(
            {
                "hold": hold,
                "start": start,
                "end": end,
                "start_frame": round(start * FPS),
                "end_frame": round(end * FPS),
            }
        )
        # emit in the documented order
        beats_out.append(
            {
                "type": b["type"],
                "act": b["act"],
                "hold": b["hold"],
                "start": b["start"],
                "end": b["end"],
                "start_frame": b["start_frame"],
                "end_frame": b["end_frame"],
                "kicker": b["kicker"],
                "text": b["text"],
                "src": b["src"],
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

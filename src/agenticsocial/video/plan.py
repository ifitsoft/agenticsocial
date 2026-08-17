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

import json
from pathlib import Path

import yaml

from ..workspace import atomic_write
from .episode import _read_meta
from .models import Episode, Series

FPS = 30
DEFAULT_HOLD = 3.0
SUPPORTED_BEATS = frozenset({"statement"})
FORMATS = {"vertical": {"w": 1080, "h": 1920}}


class PlanError(Exception):
    pass


def _beats(episode: Episode) -> list:
    _, beats_text, _ = _read_meta(episode.script_path)
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
    return beats


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
    beats_out = []
    for i, raw in enumerate(_beats(episode)):
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
        beats_out.append(_statement(raw, i, where))

    pace = episode.meta.get("pace", 1.0)
    if not isinstance(pace, (int, float)) or isinstance(pace, bool) or pace <= 0:
        raise PlanError(f"{where}: `pace` must be a positive number")
    total = round(sum(b["hold"] for b in beats_out) * float(pace), 3)

    return {
        "episode": episode.id,
        "series": series.slug,
        "byline": series.byline,
        "format": {"name": fmt, **FORMATS[fmt]},
        "fps": FPS,
        "pace": float(pace),
        "total_sec": total,
        "design": dict(series.design),
        "beats": beats_out,
    }


def write_plan(series: Series, episode: Episode, fmt: str = "vertical") -> Path:
    plan = build_plan(series, episode, fmt)
    path = episode.out_dir / "plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return path

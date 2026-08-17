# Task 1 Brief: `plan.json` schema and emitter

**Phase:** 1.5 · **Branch:** `feat/video-phase-1.5-vertical-slice`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.** Do not hand-transcribe.
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it in your report** — seven of my briefs in Phase 1
  contained exactly that defect and implementers caught every one.
- Do not modify any existing test. Do not add dependencies.
- Never stage anything under `docs/`. Report observed counts, not predicted ones.

## Why this task carries the most design weight in the phase

This is the **first code in the project that reads the beats document**. Phase 1
deliberately never parsed it — it split `script.yaml` textually and re-emitted
document 2 byte-for-byte, because spec §10 binds approval to `script_sha256`
(see `DECISIONS.md` D-026).

**That guarantee still holds and you must not break it.** Reading beats is fine;
*writing* `script.yaml` is not. This task only ever reads.

`plan.json` is also the Python→Node handoff format that **Phase 4 inherits**.
Getting it right against a real render now is most of this phase's value.

## Context

`src/agenticsocial/video/episode.py` gives you `load_episode(series, ep_id)` and
the private `_read_meta(path) -> (meta, beats_text, nl)`. `beats_text` is the
**verbatim text** of document 2, or `None`. You parse that text with
`yaml.safe_load`; you never write it back.

`src/agenticsocial/video/series.py` gives you `load_series(ws, slug) -> Series`,
carrying `design`, `target_sec`, `tolerance_sec`, `byline`, `formats`.

`engine/engine.js` renders a `statement` beat as a kicker plus a headline with a
masked word rise. Phase 1.5 supports **only** `statement`.

## Files

- Create: `src/agenticsocial/video/plan.py`
- Test: `tests/test_video_plan.py`

## Interfaces you must produce

- `PlanError(Exception)`
- `SUPPORTED_BEATS: frozenset[str]` — exactly `{"statement"}` for Phase 1.5
- `FORMATS: dict[str, dict]` — `{"vertical": {"w": 1080, "h": 1920}}`
- `FPS: int = 30`
- `build_plan(series: Series, episode: Episode, fmt: str = "vertical") -> dict`
- `write_plan(series: Series, episode: Episode, fmt: str = "vertical") -> Path`
  — writes `<episode.out_dir>/plan.json`, returns the path

## The schema

`build_plan` returns exactly this shape:

```python
{
  "episode": "2026-08-14",
  "series": "the-brief",
  "byline": "Ali Abdukarim",
  "format": {"name": "vertical", "w": 1080, "h": 1920},
  "fps": 30,
  "pace": 1.0,
  "total_sec": 10.5,
  "design": {"surface": "#F2F5F8", "ink": "#0B1B2B", ...},
  "beats": [
    {"type": "statement", "act": "01", "hold": 3.5,
     "kicker": "Today's headline", "text": "…", "src": "blog.google"}
  ],
}
```

Rules, each of which has a test below:

- `pace` comes from the episode's metadata document, defaulting to `1.0`.
- `hold` defaults to `3.0` when a beat omits it. `total_sec` is
  `sum(hold) * pace`, rounded to 3 decimals.
- `kicker` and `src` default to `""`; `act` defaults to `""`.
- Beat keys are emitted in the order shown, with no extra keys, so the JSON is
  stable across runs and diffable.

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_video_plan.py`:

```python
import json

import pytest

from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.plan import (
    FPS,
    SUPPORTED_BEATS,
    PlanError,
    build_plan,
    write_plan,
)
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


def _script(ep, beats_yaml, pace=None):
    meta = "episode: e\nseries: the-brief\nstatus: draft\n"
    if pace is not None:
        meta += f"pace: {pace}\n"
    ep.script_path.write_text(f"---\n{meta}---\n{beats_yaml}", encoding="utf-8")


THREE = """beats:
  - type: statement
    act: "01"
    hold: 3.5
    kicker: Today's headline
    text: Google shipped its main agentic model.
    src: blog.google
  - type: statement
    hold: 3.0
    text: And it costs half of what the last one did.
  - type: statement
    hold: 4.0
    text: That is the whole story.
"""


def test_plan_has_the_documented_shape(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["episode"] == "2026-08-14"
    assert plan["series"] == "the-brief"
    assert plan["format"] == {"name": "vertical", "w": 1080, "h": 1920}
    assert plan["fps"] == FPS
    assert len(plan["beats"]) == 3


def test_first_beat_carries_every_field(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert b == {
        "type": "statement",
        "act": "01",
        "hold": 3.5,
        "kicker": "Today's headline",
        "text": "Google shipped its main agentic model.",
        "src": "blog.google",
    }


def test_optional_fields_default_rather_than_vanish(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][1]
    assert b["act"] == "" and b["kicker"] == "" and b["src"] == ""


def test_missing_hold_defaults_to_three_seconds(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: no hold here\n")
    assert build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]["hold"] == 3.0


def test_total_sec_is_the_sum_of_holds_times_pace(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["pace"] == 1.0
    assert plan["total_sec"] == 10.5


def test_pace_scales_total_but_not_holds(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.5)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["pace"] == 1.5
    assert plan["total_sec"] == 15.75
    assert plan["beats"][0]["hold"] == 3.5  # unscaled; the engine applies pace


def test_design_tokens_come_from_the_series(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["design"]["accent"] == "#2E6BFF"
    assert plan["design"]["surface"] == "#F2F5F8"


def test_unsupported_beat_type_is_refused_by_name(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: jumpChart\n    text: x\n")
    with pytest.raises(PlanError) as e:
        build_plan(series, load_episode(series, "2026-08-14"))
    assert "jumpChart" in str(e.value)
    assert "statement" in str(e.value)


def test_beat_without_a_type_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - text: typeless\n")
    with pytest.raises(PlanError, match="type"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_statement_without_text_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    kicker: only a kicker\n")
    with pytest.raises(PlanError, match="text"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_non_positive_hold_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: x\n    hold: 0\n")
    with pytest.raises(PlanError, match="hold"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_empty_beats_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats: []\n")
    with pytest.raises(PlanError, match="no beats"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_beats_not_a_list_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats: just a string\n")
    with pytest.raises(PlanError, match="list"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_unparseable_beats_raises_plan_error(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats: [unclosed\n  : : :\n")
    with pytest.raises(PlanError):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_unknown_format_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    with pytest.raises(PlanError, match="wide"):
        build_plan(series, load_episode(series, "2026-08-14"), fmt="wide")


def test_write_plan_lands_in_out_dir_and_is_valid_json(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    path = write_plan(series, load_episode(series, "2026-08-14"))
    assert path == ep.out_dir / "plan.json"
    assert json.loads(path.read_text(encoding="utf-8"))["episode"] == "2026-08-14"


def test_write_plan_is_byte_stable_across_runs(series):
    """plan.json is a build artifact — it must be diffable, so key order and
    formatting cannot wobble between runs."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    e = load_episode(series, "2026-08-14")
    first = write_plan(series, e).read_bytes()
    second = write_plan(series, e).read_bytes()
    assert first == second


def test_building_a_plan_never_rewrites_the_script(series):
    """D-026: script.yaml bytes are load-bearing for script_sha256. This task
    reads the beats document; it must never write it."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    before = ep.script_path.read_bytes()
    write_plan(series, load_episode(series, "2026-08-14"))
    assert ep.script_path.read_bytes() == before


def test_supported_beats_is_exactly_statement_for_this_phase():
    assert SUPPORTED_BEATS == frozenset({"statement"})
```

- [ ] **Step 2: Run, confirm failure, commit the tests**

```bash
uv run pytest tests/test_video_plan.py 2>&1 | tail -15
git add tests/test_video_plan.py
git commit -m "test: specify the plan.json schema and emitter"
```

Expected: collection error, `ModuleNotFoundError: No module named 'agenticsocial.video.plan'`.

- [ ] **Step 3: Implement**

Create `src/agenticsocial/video/plan.py`:

```python
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
```

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest tests/test_video_plan.py -v 2>&1 | tail -30
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/plan.py
git commit -m "feat: emit plan.json from script.yaml and series.toml

The engine cannot read YAML -- scene.html loads its script via
document.write because fetch and ES modules are CORS-blocked over
file://. Python parses and emits JSON so Node stays a pure renderer with
no new dependency. Reads the beats document; never writes it."
```

- [ ] **Step 5: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `_statement` → drop the `text` check
2. `_statement` → `DEFAULT_HOLD` 3.0 → 5.0
3. `build_plan` → drop the `kind not in SUPPORTED_BEATS` check
4. `build_plan` → `total` without `* pace`
5. `build_plan` → scale each beat's `hold` by `pace` as well
6. `write_plan` → `json.dumps(plan, indent=2, sort_keys=True)`
7. `_beats` → drop the `not beats` check

Mutant 6 is the one I am least sure the tests catch — if the byte-stability test
passes under it, the test is checking run-to-run stability but not key order, and
you should say so plainly rather than adjust anything.

---

## Your report

`docs/superpowers/worklog/video/phase-1.5/task-1-report.md`:

1. **What I implemented.**
2. **TDD evidence** — RED (piped) and GREEN (both runs).
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, both commit SHAs.
5. **Vacuity audit.** Phase 1 shipped four tests that could not fail (D-035,
   D-046). For each test you wrote, ask what it would do if the code did nothing
   at all. Fix any that pass, and say which ones you fixed.
6. **Issues or concerns**, including:
   - `plan.py` imports the private `_read_meta` from `episode.py`. Right call, or
     should `episode.py` expose something public for this?
   - Is `plan.json` the right boundary? You are the first to use it. Name
     anything Phase 4 will need that this schema cannot express — extra beat
     types are expected, but a *structural* gap is what I want to hear about.
   - `pace` scales `total_sec` but not per-beat `hold`, leaving the engine to
     apply it. Is that split right, or should the plan be fully resolved so the
     engine does no arithmetic at all?

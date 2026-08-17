# Task 1b Brief: Resolve the plan fully, and bind it to its script

**Phase:** 1.5 · **Branch:** `feat/video-phase-1.5-vertical-slice` · **Follows:** `0853a9d`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Task 1's implementer answered the design questions properly and three answers
change the format. `plan.json` is what Phase 4 inherits, `statement` is still its
only consumer, and this is the cheapest moment it will ever be.

**1. The `pace` split is the worst of both options.** `total_sec` is resolved but
per-beat `hold` is not, so the pace formula lives on *both* sides of the Python→Node
boundary — the exact duplication `plan.json` exists to eliminate. They can
silently disagree: a Node bug applying pace yields a render whose length
contradicts its own plan, with nothing comparing them. And rounding is
unspecified and lives in Node — `hold: 3.5` at `pace: 1.1` is 115.5 frames at
30fps, and nobody owns that half-frame.

**Fix: resolve everything in Python.** Emit scaled `hold`, absolute `start`/`end`,
and integer frame numbers. `pace` stays as provenance. `window.__seek(t)` becomes
a lookup rather than arithmetic.

**2. `total_sec = sum(hold)` bakes in "beats never overlap".** The implementer
named this precisely: nothing that *spans* beats has anywhere to live — a chart
persisting while the headline changes, an audio bed, a transition (which is
*between* two beats and belongs to neither). TTS is already staged in the spec
and audio spans beats by nature.

**We are not building a layer system today** — the MVP's whole beat catalogue
(spec §7.1) is within-beat, so tracks would be speculative. But deriving
`total_sec` from `beats[-1]["end"]` instead of a sum costs nothing and makes the
schema neutral about overlap, so adding tracks later does not change the timing
contract.

**3. The plan has no identity binding it to its script.** No `script_sha256`. A
`plan.json` on disk is unfalsifiable — edit `script.yaml` after emitting and
nothing can tell the artifact is stale. Spec §10 binds approval to exactly that
hash. The implementer's phrasing: *"your approval gate stops at the language
boundary."*

**4. And a live bug:** `build_plan` takes `pace` from `episode.meta` (in memory)
but beats from a fresh `_read_meta` call — **two reads of the same file**. Save
`script.yaml` between them and the plan mixes new beats with old metadata. Same
class as the stale-object gate bypass (D-045): two sources of truth for one fact.

**5.** `write_plan` always writes `out/plan.json`, so emitting `vertical` then
`wide` silently overwrites. The series already declares both formats.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not modify existing tests **except** the three amendments in Step 1b, which
  exist because the schema itself changes.
- Do not add dependencies. Never stage anything under `docs/`.

## Files

- Modify: `src/agenticsocial/video/episode.py` (expose one public reader)
- Modify: `src/agenticsocial/video/plan.py`
- Modify: `tests/test_video_plan.py`

## The schema, after this task

```python
{
  "episode": "2026-08-14",
  "series": "the-brief",
  "byline": "Ali Abdukarim",
  "script_sha256": "9f2c…",          # of script.yaml's exact bytes
  "format": {"name": "vertical", "w": 1080, "h": 1920},
  "fps": 30,
  "pace": 1.5,                        # provenance only; already applied below
  "total_sec": 15.75,
  "total_frames": 473,
  "design": {...},
  "beats": [
    {"type": "statement", "act": "01",
     "hold": 5.25, "start": 0.0, "end": 5.25,
     "start_frame": 0, "end_frame": 158,
     "kicker": "…", "text": "…", "src": "…"}
  ],
}
```

`hold` is **scaled** by pace. `start`/`end` are absolute seconds. Frames are
integers, `round()`ed, and `total_frames == beats[-1]["end_frame"]` so the parts
sum to the whole. `total_sec == beats[-1]["end"]`.

---

- [ ] **Step 1a: Amend three existing tests**

The schema changes, so three tests now assert the old shape. Change **only**
these three; no other assertion may move.

```python
def test_first_beat_carries_every_field(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert b == {
        "type": "statement",
        "act": "01",
        "hold": 3.5,
        "start": 0.0,
        "end": 3.5,
        "start_frame": 0,
        "end_frame": 105,
        "kicker": "Today's headline",
        "text": "Google shipped its main agentic model.",
        "src": "blog.google",
    }


def test_pace_scales_holds_and_total(series):
    """Renamed from test_pace_scales_total_but_not_holds: the plan is now fully
    resolved, so pace is applied in Python and the engine does no arithmetic."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.5)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["pace"] == 1.5
    assert plan["total_sec"] == 15.75
    assert plan["beats"][0]["hold"] == 5.25     # 3.5 * 1.5, scaled here
    assert plan["beats"][0]["end"] == 5.25


def test_missing_hold_defaults_to_three_seconds(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: no hold here\n")
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["beats"][0]["hold"] == 3.0
    assert plan["total_sec"] == 3.0
```

- [ ] **Step 1b: Append new tests**

```python
import hashlib


# --- the plan is fully resolved: the engine does no timing arithmetic ---------


def test_beats_are_contiguous_and_start_at_zero(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    beats = build_plan(series, load_episode(series, "2026-08-14"))["beats"]
    assert beats[0]["start"] == 0.0
    for a, b in zip(beats, beats[1:]):
        assert b["start"] == a["end"], (a, b)


def test_total_sec_is_the_last_end_not_a_sum(series):
    """Deriving the total from the last beat's end keeps the schema neutral
    about overlap, so adding tracks later does not change this contract."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["total_sec"] == plan["beats"][-1]["end"]


def test_frames_are_integers_and_sum_to_the_total(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.1)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    for b in plan["beats"]:
        assert isinstance(b["start_frame"], int)
        assert isinstance(b["end_frame"], int)
    assert plan["beats"][0]["start_frame"] == 0
    assert plan["total_frames"] == plan["beats"][-1]["end_frame"]
    for a, b in zip(plan["beats"], plan["beats"][1:]):
        assert b["start_frame"] == a["end_frame"]


def test_fractional_frames_are_resolved_in_python(series):
    """3.5s at pace 1.1 is 115.5 frames. Somebody must own that half-frame, and
    it is not the renderer."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: x\n    hold: 3.5\n", pace=1.1)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["beats"][0]["end_frame"] == 116          # round(115.5) -> banker's
    assert plan["total_frames"] == 116


# --- identity: the plan is bound to the exact script it came from -------------


def test_plan_carries_the_script_sha256(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    expected = hashlib.sha256(ep.script_path.read_bytes()).hexdigest()
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["script_sha256"] == expected


def test_editing_the_script_changes_the_hash(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    first = build_plan(series, load_episode(series, "2026-08-14"))["script_sha256"]
    _script(ep, THREE.replace("That is the whole story.", "Something else."))
    second = build_plan(series, load_episode(series, "2026-08-14"))["script_sha256"]
    assert first != second


# --- one read: two reads of one file is two sources of truth ------------------


def test_metadata_and_beats_come_from_the_same_read(series, monkeypatch):
    """build_plan read pace from episode.meta (in memory) and beats from a fresh
    file read. A script saved between the two produced a plan mixing versions."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.0)
    loaded = load_episode(series, "2026-08-14")
    _script(ep, THREE, pace=2.0)          # disk now disagrees with the stale object
    plan = build_plan(series, loaded)
    assert plan["pace"] == 2.0            # disk wins; one read, one truth
    assert plan["script_sha256"] == hashlib.sha256(
        ep.script_path.read_bytes()
    ).hexdigest()


# --- formats do not overwrite each other -------------------------------------


def test_write_plan_names_the_file_after_the_format(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    path = write_plan(series, load_episode(series, "2026-08-14"))
    assert path == ep.out_dir / "plan-vertical.json"
```

- [ ] **Step 2: Run, then commit the tests**

```bash
uv run pytest tests/test_video_plan.py 2>&1 | tail -25
git add tests/test_video_plan.py
git commit -m "test: pin a fully resolved plan bound to its script

The pace formula lived on both sides of the Python->Node boundary, frame
rounding was unowned and lived in Node, and the plan carried no identity
tying it to the script it came from."
```

- [ ] **Step 3: Implement**

**3a.** In `src/agenticsocial/video/episode.py`, expose the reader publicly —
`plan.py` depends on it as a contract, and an underscore is the wrong way to
publish a contract. Add directly below `_read_meta`:

```python
def read_script(path: Path) -> tuple[dict, str | None, str]:
    """Read `script.yaml`: (metadata, verbatim beats text, newline).

    READ ONLY. The beats text is returned exactly as written and must never be
    re-serialised — see this module's docstring and DECISIONS D-026.
    """
    return _read_meta(path)
```

**3b.** In `src/agenticsocial/video/plan.py`, replace the import and both
functions:

```python
import hashlib

from .episode import read_script
```

```python
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
```

Delete the now-unused `_beats` helper and the `_read_meta` import. Confirm with
`grep -n "_beats\|_read_meta" src/agenticsocial/video/plan.py`.

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest tests/test_video_plan.py -v 2>&1 | tail -35
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/episode.py src/agenticsocial/video/plan.py
git commit -m "feat: fully resolve the plan and bind it to its script

Pace and frame rounding now happen only in Python, so the engine does no
timing arithmetic and cannot disagree with its own plan. total_sec comes
from the last beat's end rather than a sum, keeping the schema neutral
about overlap. Adds script_sha256 so a plan cannot be silently stale, and
reads the script once so metadata, beats and hash describe the same bytes."
```

- [ ] **Step 5: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `build_plan` → do not scale `hold` by `pace`
2. `build_plan` → `total_sec` back to `sum(b["hold"] …)`
3. `build_plan` → `start_frame`/`end_frame` via `int()` instead of `round()`
4. `_load_script` → take `meta` from `episode.meta` instead of the fresh read
5. `_load_script` → hash `beats_text` instead of the whole file
6. `write_plan` → back to `plan.json`
7. `build_plan` → `at = end` becomes `at = 0.0` (all beats start at zero)

Mutant 4 is the two-sources-of-truth bug. Mutant 3 is the rounding-ownership one.

---

## Your report

`docs/superpowers/worklog/video/phase-1.5/task-1b-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN.
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, both commit SHAs.
5. **Vacuity audit** of every test you write, verified with mutants rather than
   by inspection. You caught three of mine this way last task; hold your own to
   the same standard.
6. **Issues or concerns**, including:
   - `round()` is banker's rounding: `round(115.5)` is 116 but `round(116.5)` is
     also 116. Is that acceptable for frame boundaries, or does it cause a
     visible one-frame drift over a long episode? Show the arithmetic.
   - With the plan fully resolved, is `pace` still worth carrying at all?
   - You said the plan needs identity. It now has `script_sha256` — but nothing
     *checks* it. Where should that check live, and what should it do?

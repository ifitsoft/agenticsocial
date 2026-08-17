# Task 0d Brief: Enforce what Task 0c only declared, and freeze `Series`

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `b379501`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Task 0c froze `Variant` and `Episode`. Three of its four mutants **survived**, and
the leader verified both of the important ones by hand:

```
frozen=True deleted from Variant  ->  379 passed        (nothing enforces it)
replace(v, status=PUBLISHING)     ->  forged: publishing | disk says: draft
```

So the guarantee is currently held up by a decorator that no test checks. A
future editor who hits `FrozenInstanceError`, deletes `(frozen=True)`, and sees
green has silently undone the fix for three separate gate bypasses.

**Also unverified:** `workspace.set_status`'s return value. Every `Variant` test
reloads from disk and `publish.py` never reads `variant.status` afterwards, so
`return v` instead of `return replace(v, ...)` passes the whole suite. The
`Episode` half is pinned by two tests; the `Variant` half by none.

**And `Series` should be frozen now, not later.** The Task 0c implementer's
argument, which I accept:

> `Series` carries `target_sec`/`tolerance_sec`, and the spec makes duration
> compliance a gate. The moment Phase 3 writes
> `if abs(dur - series.target_sec) > series.tolerance_sec: raise`,
> `tolerance_sec` becomes exactly what `v.status` was. It is free to freeze now
> (loaded from `series.toml`, never written back, no `set_*` to convert) and gets
> more expensive once Phase 3 adds a writer. You have deferred the fourth
> instance by about one phase.

`Source` stays mutable — pure identity and description, no gate reads it.

## What is NOT changing, and why

`frozen=True` freezes every field, not just `status`. Task 0c found this via
`test_save_variant_roundtrips_body_edits`, which had to move to `replace`. That
collateral is **accepted deliberately**: a `Variant` is a *snapshot of a file*,
and mutating any field makes it lie about the file, not just about status. Edits
go through `replace` or a reload. Do not add a custom `__setattr__` to make
`status` specially read-only — the blunt version states the right principle.

## Ground rules

- **Two commits.** Tests first (they must fail), then `Series`. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not add dependencies. Never stage anything under `docs/`.
- You may not change any existing assertion.

---

- [ ] **Step 1: Tests that actually enforce it**

Append to `tests/test_workspace.py`:

```python
def test_variant_status_cannot_be_assigned(tmp_path):
    """Three gate bypasses came from assigning this field. Deleting
    `frozen=True` passes the entire suite without this test."""
    import dataclasses

    import pytest

    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Kill staging")
    v = ws.create_variant(src, "x", body="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.status = Status.PUBLISHING


def test_set_status_returns_a_new_variant_and_leaves_the_argument_alone(tmp_path):
    """`return v` instead of `return replace(v, ...)` passes the whole suite:
    every other Variant test reloads from disk."""
    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Kill staging")
    v = ws.create_variant(src, "x", body="hi")

    moved = ws.set_status(v, Status.IN_REVIEW)
    assert moved is not v
    assert moved.status is Status.IN_REVIEW
    assert v.status is Status.DRAFT          # the argument is untouched
```

Append to `tests/test_video_episode.py`:

```python
def test_episode_status_cannot_be_assigned(series):
    import dataclasses

    ep = create_episode(series, "2026-08-14")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ep.status = Status.RENDERING
```

Append to `tests/test_video_series.py`:

```python
def test_series_runtime_targets_cannot_be_assigned(ws):
    """Phase 3 gates duration on target_sec/tolerance_sec. A writable value that
    a gate reads is exactly what caused three bypasses in the status field."""
    import dataclasses

    s = scaffold_series(ws, "the-brief")
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.target_sec = 9999
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.tolerance_sec = 9999
```

```bash
uv run pytest tests/test_workspace.py tests/test_video_episode.py tests/test_video_series.py 2>&1 | tail -12
git add tests/
git commit -m "test: enforce frozen status and the set_status return contract

Deleting frozen=True from Variant passed all 379 tests, and
workspace.set_status could return the argument unchanged with nothing
noticing. Series is gated on next: Phase 3 reads target_sec."
```

Expect one failure (`test_series_runtime_targets_cannot_be_assigned`); the other
three should pass immediately, since they pin behaviour Task 0c already
delivered but left unverified. **Report exactly which failed** — if any of the
first three fails, that is a finding.

- [ ] **Step 2: Freeze `Series`**

In `src/agenticsocial/video/models.py`:

```python
@dataclass(frozen=True)
class Series:
```

Nothing else changes: `Series` is loaded from `series.toml` and never written
back, so there is no `set_*` to convert. If anything in `src/` assigns to a
`Series` field, that is a finding — report it rather than working around it.

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/models.py
git commit -m "fix: freeze Series before a gate depends on it

target_sec and tolerance_sec become gate inputs in Phase 3. A writable
value that a gate reads is the shape that produced three status
bypasses; freezing is free now and costs a refactor later."
```

- [ ] **Step 3: Mutation check**

Apply, run the full suite, `git checkout` between. All must now fail:

1. `Variant` → `@dataclass` (unfrozen)
2. `Episode` → `@dataclass` (unfrozen)
3. `Series` → `@dataclass` (unfrozen)
4. `workspace.set_status` → `return v`
5. `video.episode.set_status` → `return episode`

All five survived or were unpinned before this task except 5. Report any that
still survive.

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-0d-report.md`:

1. **What I changed.**
2. **Which of the four new tests failed at RED**, and which passed immediately.
3. **Mutation results** for all five.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - `replace(v, status=...)` still forges a status in one line. Is there a
     mechanism worth having that closes that too, or is "no gate reads the
     object" the real and sufficient defence? Argue it — do not just agree with
     me. If the answer is that freezing was mostly symbolic, say so.
   - `Source` is still mutable. Same question as `Series` got: is it defensible
     permanently, or deferred?
   - Anything in `src/` that assigns to a `Series` field.

# Task 0 Brief: Carried debt — the text pipeline's gate, and two tests that could launch Chromium

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Two carried items, both found by implementers in earlier phases and deliberately
deferred. Small, and worth clearing before new work lands on top.

## D-049 — `Workspace.set_status` gates on memory, not disk

`src/agenticsocial/workspace.py:206`:

```python
    def set_status(self, v: Variant, target: Status) -> None:
        assert_transition(v.status, target)      # in-memory
```

This is the **identical shape** as the video gate bypass fixed in Phase 1
(D-045), where an episode whose file said `draft` was moved straight to
`rendering` because a stale object said `approved`. It protects posting to X.

Not reachable through the CLI today — `cli.py` loads variants fresh on every
invocation, and `cli.py::post` checks `assert_transition` before touching the
keyring. It is worth fixing anyway: the video gate had exactly this shape and it
was defended for two tasks before a reviewer broke it.

### The hazard that makes this less trivial than it looks

**Do not re-read `v.meta` from disk.** `x/publish.py::publish_variant` sets
`variant.meta["posted_url"]` **in memory** and then calls `set_status(...,
PUBLISHED)` expecting that value to be written. It also relies on
`meta["posted_ids"]` surviving. Replacing `v.meta` with the disk copy would
silently drop `posted_url` and break the resume invariant `CLAUDE.md` calls
load-bearing.

**Read only the status from disk, for the gate. Write from memory.**

## D-057 — two tests that would launch real Chromium

`test_missing_node_is_a_clean_error` and `test_missing_ffmpeg_is_a_clean_error`
in `tests/test_video_render.py` patch `shutil.which` but **not**
`subprocess.run`. They pass only because `_require_tools` raises first. Remove
that check and both tests launch real Chromium and real ffmpeg — violating the
offline-suite rule and turning a 1-second suite into a minutes-long one.

Found by an implementer's mutation audit, not by anything failing.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 14 of my briefs have had that defect across
  two phases, against zero implementer errors.
- Do not add dependencies. Never stage anything under `docs/`.
- **Do not modify any existing test except the two named in Step 1b.**
- Report observed counts.

---

- [ ] **Step 1a: Append tests to `tests/test_workspace.py`**

```python
def test_set_status_gates_on_disk_not_the_in_memory_variant(tmp_path):
    """D-049: the identical shape as the video gate bypass (D-045). A stale
    Variant must not be able to move a variant the file says is a draft."""
    import pytest

    from agenticsocial.models import Status, TransitionError
    from agenticsocial.workspace import Workspace

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Kill staging")
    v = ws.create_variant(src, "x", body="hello")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)

    v.path.write_text(
        v.path.read_text(encoding="utf-8").replace("status: approved", "status: draft"),
        encoding="utf-8",
    )
    with pytest.raises(TransitionError):
        ws.set_status(v, Status.PUBLISHING)
    assert ws.load_variant(src, "x").status is Status.DRAFT


def test_set_status_preserves_in_memory_meta(tmp_path):
    """publish_variant sets posted_url in memory and expects set_status to write
    it. Reading meta back from disk for the gate must not discard that."""
    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Kill staging")
    v = ws.create_variant(src, "x", body="hello")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    ws.set_status(v, Status.PUBLISHING)

    v.meta["posted_ids"] = ["1", "2"]
    v.meta["posted_url"] = "https://x.com/i/web/status/1"
    ws.set_status(v, Status.PUBLISHED)

    reloaded = ws.load_variant(src, "x")
    assert reloaded.meta["posted_url"] == "https://x.com/i/web/status/1"
    assert reloaded.meta["posted_ids"] == ["1", "2"]
    assert reloaded.status is Status.PUBLISHED


def test_set_status_rejects_an_unreadable_status_on_disk(tmp_path):
    import pytest

    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace, WorkspaceError

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Kill staging")
    v = ws.create_variant(src, "x", body="hello")
    v.path.write_text(
        v.path.read_text(encoding="utf-8").replace("status: draft", "status: banana"),
        encoding="utf-8",
    )
    with pytest.raises(WorkspaceError, match="banana"):
        ws.set_status(v, Status.IN_REVIEW)
```

- [ ] **Step 1b: Fix the two Chromium-capable tests**

In `tests/test_video_render.py`, give both the `fake` fixture so they cannot
reach a real subprocess whatever the source does. Change **only** the signature
line of each:

```python
def test_missing_node_is_a_clean_error(series, episode, fake, monkeypatch):
```

```python
def test_missing_ffmpeg_is_a_clean_error(series, episode, fake, monkeypatch):
```

`fake` patches `R.subprocess.run`; the per-test `monkeypatch.setattr` on
`R.shutil.which` still runs afterwards and still drives the assertion. Nothing
else in either test changes.

- [ ] **Step 2: Run, confirm the workspace tests fail, commit**

```bash
uv run pytest tests/test_workspace.py tests/test_video_render.py 2>&1 | tail -15
git add tests/test_workspace.py tests/test_video_render.py
git commit -m "test: pin the text pipeline's gate against disk, stop two tests reaching Chromium

Workspace.set_status gated on the in-memory Variant -- the identical
shape as the video gate bypass. Two render tests patched shutil.which but
not subprocess.run, so removing the toolchain check would have launched
real Chromium from the unit suite."
```

- [ ] **Step 3: Implement**

In `src/agenticsocial/workspace.py`, replace `set_status`:

```python
    def set_status(self, v: Variant, target: Status) -> None:
        """Move a variant to `target`.

        The gate is checked against the status ON DISK, not `v.status`: a caller
        holding a stale Variant must not be able to move a variant the file says
        is a draft. Same reasoning as video/episode.py::set_status (D-045/D-049).

        Only the status is taken from disk. `v.meta` is written as-is, because
        publish_variant sets `posted_url` in memory and expects this call to
        persist it — replacing meta with the disk copy would silently break the
        resume invariant.
        """
        disk_meta, _ = frontmatter.parse(v.path.read_text(encoding="utf-8"))
        raw = disk_meta.get("status", Status.DRAFT.value)
        try:
            current = Status(raw)
        except ValueError:
            raise WorkspaceError(
                f"{v.path}: invalid status '{raw}' — one of: "
                f"{', '.join(s.value for s in Status)}"
            )
        assert_transition(current, target)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        if target is Status.APPROVED:
            v.meta["approved_at"] = now
        if target is Status.PUBLISHED:
            v.meta["posted_at"] = now
        v.status = target
        self.save_variant(v)
```

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/workspace.py
git commit -m "fix: gate text-variant transitions on the status on disk

The identical shape as the video gate bypass: a stale Variant could move
a variant the file said was a draft. Only the status is read from disk --
v.meta is written as-is, because publish_variant sets posted_url in
memory and relies on this call to persist it."
```

- [ ] **Step 5: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `set_status` → gate on `v.status` again
2. `set_status` → also replace `v.meta` with `disk_meta`
3. `set_status` → drop the invalid-status guard
4. `_require_tools` in `render.py` → return without checking

Mutant 2 is the resume-invariant hazard. Mutant 4 proves Step 1b worked: with
the guard gone, those two tests must **fail on the assertion**, not hang or
launch a browser — report their runtime.

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-0-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN.
3. **Mutation results** — a row per mutant, plus the suite runtime under mutant 4.
4. **Files changed**, both commit SHAs.
5. **Vacuity audit** — construct the mutant each of your tests should kill and run
   it. Four implementers before you caught vacuous tests of mine this way.
6. **Issues or concerns**, including:
   - `publish_variant` calls `save_variant` inside its posting loop and
     `set_status` at the end. With the gate now reading disk, is the resume path
     still correct if the process dies between the two? Trace it.
   - Is there anywhere else in `src/` that gates on in-memory state while writing
     to disk? This is the third instance of the family; assume a fourth.

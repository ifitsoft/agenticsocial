# Task 1b Brief: Cut `RENDERED → PUBLISHING`, close the QA test gaps

**Phase:** 1 — Series & episode scaffolding
**Branch:** `feat/video-phase-01-scaffolding` (already checked out)
**Follows:** Task 1, commit `41ad23e`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why this task exists

QA reviewed `41ad23e` and returned **changes-required**. It ran mutation testing:
it deliberately broke `VIDEO_TRANSITIONS` so a render could only fail and never
complete, and **all 106 tests still passed**. That is a real gap — the tests
assert what is forbidden far better than what is permitted.

Separately, the human decided to cut the `RENDERED → PUBLISHING` edge (decision
D-006, spec §10 already updated). It was reachable but never exercised in MVP,
and it left `FAILED` with only `→ RENDERING` as a recovery path, so a *publish*
failure could only be recovered by re-rendering an artifact already on disk.

## Ground rules

- **Two commits this time.** Commit the tests first, in a state where they fail.
  Then commit the implementation. QA could not independently verify the RED phase
  on Task 1 because test and implementation arrived in one commit; this fixes
  that permanently. Both commits stay on this branch.
- Do not modify any existing test. You are only adding tests and changing
  `VIDEO_TRANSITIONS` / `TransitionError`.
- Do not add dependencies.
- If this brief is wrong, implement it as written and say so in your report.
- Run everything with `uv run`. **Pipe command output to a file and paste from
  it — do not hand-transcribe.** e.g. `uv run pytest 2>&1 | tail -20 > /tmp/out.txt`

## Files

- Modify: `src/agenticsocial/models.py`
- Modify: `tests/test_video_status.py` (append only — do not alter existing tests)

---

- [ ] **Step 1: Append the new tests**

Add these to the end of `tests/test_video_status.py`. Change nothing above them.

```python
# --- permitted-transition coverage -------------------------------------------
# QA mutation-tested the original suite: breaking the render path so a render
# could only fail and never complete left all 106 tests green. These assert what
# the table must ALLOW, not only what it must forbid.


def test_rendering_may_complete():
    assert_transition(Status.RENDERING, Status.RENDERED, VIDEO_TRANSITIONS)


def test_rendered_is_terminal_in_mvp():
    """Video publishing is out of MVP scope (spec §3.1, D-006).

    `rendered` deliberately has no outgoing edge. When publishing lands, this
    table gains `rendered -> publishing` AND `failed -> publishing` together, so
    recovery matches what actually failed.
    """
    assert VIDEO_TRANSITIONS[Status.RENDERED] == set()


def test_no_video_state_reaches_publishing():
    """Nothing in the MVP video lifecycle may enter the publish states."""
    for source, targets in VIDEO_TRANSITIONS.items():
        assert Status.PUBLISHING not in targets, f"{source} -> publishing"
        assert Status.PUBLISHED not in targets, f"{source} -> published"


def test_failed_has_exactly_one_recovery_edge():
    """A render failure recovers by re-rendering, and that is the only option.

    Guards D-006: if a future change adds an edge here without also revisiting
    the publish story, this fails and forces the conversation.
    """
    assert VIDEO_TRANSITIONS[Status.FAILED] == {Status.RENDERING}


def test_text_table_render_states_stay_dead_ends():
    """QA found that opening the text table to the render states passed all
    tests. A text variant must never be able to enter or leave them."""
    assert ALLOWED_TRANSITIONS[Status.RENDERING] == set()
    assert ALLOWED_TRANSITIONS[Status.RENDERED] == set()


def test_transition_error_requires_an_explicit_table():
    """QA finding 3: a defaulted table silently reported the TEXT allowed-set,
    so a video caller could be told 'allowed next: in_review, publishing'."""
    with pytest.raises(TypeError):
        TransitionError(Status.APPROVED, Status.PUBLISHED)
```

- [ ] **Step 2: Run and confirm the expected failures**

```bash
uv run pytest tests/test_video_status.py -v 2>&1 | tail -30
```

Expected: **2 failures**, the rest passing.
- `test_rendered_is_terminal_in_mvp` — currently `{Status.PUBLISHING}`
- `test_no_video_state_reaches_publishing` — currently `RENDERED -> PUBLISHING`
- `test_transition_error_requires_an_explicit_table` — also currently fails
  (no `TypeError` is raised, because `table` has a default)

So: **3 failures**. The other three new tests characterise behaviour that is
already correct and exist to stop it regressing — they should pass immediately.
Record in your report exactly which failed and which passed; do not assume.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_video_status.py
git commit -m "test: assert permitted video transitions and an explicit error table

Adds coverage QA's mutation testing proved was missing: breaking the
render path left all 106 tests green. Three of these fail until the
next commit."
```

- [ ] **Step 4: Implement**

**4a.** In `src/agenticsocial/models.py`, change one entry in `VIDEO_TRANSITIONS`:

```python
    Status.RENDERED: set(),   # terminal in MVP; see spec §10 and D-006
```

Leave `PUBLISHING` and `PUBLISHED` entries exactly as they are — they stay in the
table as unreachable empty-or-not sets purely so the table remains total. Do not
delete keys.

After the edit, `VIDEO_TRANSITIONS` must read exactly:

```python
VIDEO_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.RENDERING},
    Status.SCHEDULED: set(),
    Status.RENDERING: {Status.RENDERED, Status.FAILED},
    Status.RENDERED: set(),      # terminal in MVP; see spec §10 and D-006
    Status.PUBLISHING: set(),    # unreachable in MVP; kept for table totality
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.RENDERING},
}
```

**4b.** Make `TransitionError`'s `table` argument required. `assert_transition`
is the only construction site in the codebase and always passes it, so this is
safe:

```python
class TransitionError(Exception):
    def __init__(
        self,
        current: Status,
        target: Status,
        table: dict[Status, set[Status]],
    ):
        allowed = ", ".join(
            s.value for s in _ORDER if s in table[current]
        ) or "none (terminal)"
        super().__init__(
            f"cannot move {current.value} -> {target.value}; allowed next: {allowed}"
        )
```

Leave `assert_transition`'s own `table=None` default alone — `publish.py` and
`cli.py` call it without a table and must keep working.

- [ ] **Step 5: Run everything**

```bash
uv run pytest tests/test_video_status.py -v 2>&1 | tail -30
uv run pytest 2>&1 | tail -10
```

Expected: 19 passed in the new file; 112 passed overall. If anything else fails,
**stop and report** — do not edit an existing test.

- [ ] **Step 6: Commit the implementation**

```bash
git add src/agenticsocial/models.py
git commit -m "fix: make rendered terminal in MVP and require an explicit transition table

Cuts RENDERED -> PUBLISHING (D-006): the edge was reachable but never
exercised, and left FAILED -> RENDERING as the only recovery, so a
publish failure would force re-rendering an artifact already on disk.

Makes TransitionError's table required so it can no longer silently
report the text allowed-set to a video caller."
```

---

## Your report

Write `docs/superpowers/worklog/video/phase-01/task-1b-report.md`:

1. **What I changed** and why, briefly.
2. **TDD evidence** — `### RED` with the test-only commit's failures (piped, not
   transcribed) and `### GREEN` with both final runs. Name exactly which of the
   six new tests failed at RED and which passed.
3. **Files changed** and both commit SHAs.
4. **Self-review findings.**
5. **Issues or concerns** — in particular, say whether you think
   `test_failed_has_exactly_one_recovery_edge` is a useful guard or an annoyance
   that will just get edited away when publishing lands.

Do not update `PROGRESS.md` or `DECISIONS.md`.

# Task 1 Brief: Video status machine

**Phase:** 1 — Series & episode scaffolding
**Branch:** `feat/video-phase-01-scaffolding` (already checked out — commit here)
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Ground rules

- Strict TDD. Write the failing test, **run it**, paste the failure verbatim,
  then implement, run again, paste the pass. A report claiming green without
  pasted command output is rejected unread.
- Do not modify any existing test file, **with one exception granted in
  Amendment 1 below** (`tests/test_models.py::test_status_values_match_spec`).
- Do not add dependencies.
- If this brief is wrong or ambiguous, **say so in your report** — do not
  improvise a different design. Reporting a problem is a success; silently
  redesigning is not.
- Python ≥3.11. Run everything with `uv run`.

## Context

`src/agenticsocial/models.py` holds the status lifecycle for text variants
(tweets). It defines a `Status` enum, an `ALLOWED_TRANSITIONS` table, and
`assert_transition()` / `TransitionError`, both of which reference
`ALLOWED_TRANSITIONS` directly.

Video episodes are being added and need a *different* lifecycle: the expensive
step is rendering, and it sits behind the same human approval gate that
publishing sits behind for text.

We are **not** adding a second enum — `approved` must not mean two different
things depending on which enum you imported. Instead: add two states to the
existing enum, add a second transition table, and make the two checking
functions accept a table (defaulting to the existing one, so every current call
site is untouched).

## Files

- Modify: `src/agenticsocial/models.py`
- Create: `tests/test_video_status.py`

## Interfaces you must produce

- `Status.RENDERING` with value `"rendering"`
- `Status.RENDERED` with value `"rendered"`
- `VIDEO_TRANSITIONS: dict[Status, set[Status]]`
- `assert_transition(current: Status, target: Status, table: dict[Status, set[Status]] | None = None) -> None`
- `TransitionError(current: Status, target: Status, table: dict[Status, set[Status]] | None = None)`

Later tasks import all of these by these exact names.

---

- [ ] **Step 1: Write the failing test**

Create `tests/test_video_status.py`:

```python
import pytest

from agenticsocial.models import (
    ALLOWED_TRANSITIONS,
    VIDEO_TRANSITIONS,
    Status,
    TransitionError,
    assert_transition,
)


def test_render_states_exist():
    assert Status.RENDERING.value == "rendering"
    assert Status.RENDERED.value == "rendered"


def test_both_tables_are_total():
    """Every status must be a key in both tables, or lookups raise KeyError."""
    for s in Status:
        assert s in ALLOWED_TRANSITIONS, f"{s} missing from ALLOWED_TRANSITIONS"
        assert s in VIDEO_TRANSITIONS, f"{s} missing from VIDEO_TRANSITIONS"


def test_approved_may_enter_rendering():
    assert_transition(Status.APPROVED, Status.RENDERING, VIDEO_TRANSITIONS)


def test_in_review_may_not_skip_the_gate():
    with pytest.raises(TransitionError):
        assert_transition(Status.IN_REVIEW, Status.RENDERING, VIDEO_TRANSITIONS)


def test_approved_may_not_jump_straight_to_rendered():
    with pytest.raises(TransitionError):
        assert_transition(Status.APPROVED, Status.RENDERED, VIDEO_TRANSITIONS)


def test_failed_render_may_retry():
    assert_transition(Status.FAILED, Status.RENDERING, VIDEO_TRANSITIONS)


def test_rendering_may_fail():
    assert_transition(Status.RENDERING, Status.FAILED, VIDEO_TRANSITIONS)


def test_approval_may_be_revoked():
    assert_transition(Status.APPROVED, Status.IN_REVIEW, VIDEO_TRANSITIONS)


def test_published_is_terminal_for_video():
    assert VIDEO_TRANSITIONS[Status.PUBLISHED] == set()


def test_text_table_rejects_rendering():
    """A text variant must never enter a render state."""
    with pytest.raises(TransitionError):
        assert_transition(Status.APPROVED, Status.RENDERING)


def test_text_pipeline_is_unchanged():
    assert_transition(Status.APPROVED, Status.PUBLISHING)
    assert_transition(Status.IN_REVIEW, Status.APPROVED)


def test_error_message_lists_the_right_table_next_states():
    with pytest.raises(TransitionError) as excinfo:
        assert_transition(Status.APPROVED, Status.PUBLISHED, VIDEO_TRANSITIONS)
    message = str(excinfo.value)
    assert "rendering" in message
    assert "in_review" in message
    assert "publishing" not in message


def test_error_message_defaults_to_text_table():
    with pytest.raises(TransitionError) as excinfo:
        assert_transition(Status.APPROVED, Status.PUBLISHED)
    assert "publishing" in str(excinfo.value)
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
uv run pytest tests/test_video_status.py -v
```

Expected: collection error —
`ImportError: cannot import name 'VIDEO_TRANSITIONS' from 'agenticsocial.models'`

Paste the actual output into your report.

- [ ] **Step 3: Implement**

In `src/agenticsocial/models.py`:

**3a.** Add two members to `Status`, between `SCHEDULED` and `PUBLISHING`:

```python
class Status(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"  # reserved for the v2 calendar
    RENDERING = "rendering"
    RENDERED = "rendered"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
```

**3b.** Add the two new states to `ALLOWED_TRANSITIONS` as empty sets, and add
`VIDEO_TRANSITIONS` after it:

```python
ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.PUBLISHING},
    Status.SCHEDULED: set(),
    Status.RENDERING: set(),  # video-only; unreachable for text variants
    Status.RENDERED: set(),   # video-only; unreachable for text variants
    Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.PUBLISHING},
}

# Video episodes have their own lifecycle: the expensive step is rendering, and
# it sits behind the same human gate that publishing sits behind for text.
VIDEO_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.RENDERING},
    Status.SCHEDULED: set(),
    Status.RENDERING: {Status.RENDERED, Status.FAILED},
    Status.RENDERED: {Status.PUBLISHING},
    Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.RENDERING},
}

_ORDER = list(Status)
```

**3c.** Replace `TransitionError` and `assert_transition` with table-aware
versions. Keep the existing message wording exactly — other tests assert on it:

```python
class TransitionError(Exception):
    def __init__(
        self,
        current: Status,
        target: Status,
        table: dict[Status, set[Status]] | None = None,
    ):
        table = ALLOWED_TRANSITIONS if table is None else table
        allowed = ", ".join(
            s.value for s in _ORDER if s in table[current]
        ) or "none (terminal)"
        super().__init__(
            f"cannot move {current.value} -> {target.value}; allowed next: {allowed}"
        )


def assert_transition(
    current: Status,
    target: Status,
    table: dict[Status, set[Status]] | None = None,
) -> None:
    table = ALLOWED_TRANSITIONS if table is None else table
    if target not in table[current]:
        raise TransitionError(current, target, table)
```

Leave the module docstring, `Source`, and `Variant` untouched.

---

## Amendment 1 — issued 2026-08-16 after the task reported blocked

The original brief was internally contradictory: it required adding two `Status`
members, forbade touching existing tests, and required a green suite.
`tests/test_models.py::test_status_values_match_spec` snapshots the **entire**
enum as an ordered list, so all three cannot hold. The implementer was correct to
stop. This amendment resolves it.

- [ ] **Step 3d: Update the enum snapshot test**

This is a snapshot of an enum this task deliberately extends. Update it — and
change nothing else in `tests/test_models.py`.

In `tests/test_models.py`, replace the body of `test_status_values_match_spec`:

```python
def test_status_values_match_spec():
    assert [s.value for s in Status] == [
        "draft", "in_review", "approved", "scheduled",
        "rendering", "rendered",
        "publishing", "published", "failed",
    ]
```

Note in your report that you changed this test and why.

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
uv run pytest tests/test_video_status.py -v
```
Expected: 13 passed.

```bash
uv run pytest
```
Expected: every pre-existing test still passes. If any pre-existing test now
fails, **stop and report it** — do not edit that test.

Paste both outputs into your report.

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/models.py tests/test_models.py tests/test_video_status.py
git commit -m "feat: add rendering/rendered states and a video transition table"
```

---

## Your report

Write `docs/superpowers/worklog/video/phase-01/task-1-report.md` with these
sections, in this order:

1. **What I implemented** — a short factual summary.
2. **TDD evidence** — `### RED` and `### GREEN` headings, each with the command
   run and its verbatim output in a fenced block. Include the full-suite run.
3. **Files changed** — paths, and new/modified.
4. **Self-review findings** — what you checked beyond the tests passing.
5. **Issues or concerns** — anything about the brief you think is wrong,
   ambiguous, or likely to cause trouble later. Write "None" only if you mean it.
6. **Commit** — the resulting SHA.

Do not update `PROGRESS.md` or `DECISIONS.md`; the project leader owns those.

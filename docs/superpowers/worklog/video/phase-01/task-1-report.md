# Task 1 Report: Video status machine

**Status: COMPLETE.** Committed as `41ad23e` after Amendment 1 resolved the
brief's contradiction. Full suite green: 106 passed.

This report is chronological. Sections 1–6 are the original record, written
when the task was blocked; the failure evidence in section 2 is preserved
deliberately. The "Amendment 1" section at the end records the resolution.

## 1. What I implemented

In `src/agenticsocial/models.py`, exactly as the brief specified:

- Added `Status.RENDERING = "rendering"` and `Status.RENDERED = "rendered"`,
  positioned between `SCHEDULED` and `PUBLISHING`.
- Added `Status.RENDERING: set()` and `Status.RENDERED: set()` entries to
  `ALLOWED_TRANSITIONS` so the text table stays total and text variants can
  never enter a render state.
- Added `VIDEO_TRANSITIONS: dict[Status, set[Status]]` after
  `ALLOWED_TRANSITIONS`, with rendering gated behind `APPROVED`,
  `RENDERING -> {RENDERED, FAILED}`, `RENDERED -> {PUBLISHING}`, and
  `FAILED -> {RENDERING}`.
- Made `TransitionError.__init__` and `assert_transition()` accept an optional
  `table` argument defaulting to `ALLOWED_TRANSITIONS`, so all existing call
  sites are unchanged. Error message wording is byte-identical to before.

The module docstring, `Source`, and `Variant` are untouched. No dependencies
added. No existing test file edited.

Created `tests/test_video_status.py` with the 13 tests given in the brief,
verbatim.

## 2. TDD evidence

### RED

```
$ uv run pytest tests/test_video_status.py -v
============================= test session starts ==============================
platform darwin -- Python 3.11.13, pytest-9.1.1, pluggy-1.6.0 -- /Users/aabdukarim/Documents/Code/agenticsocial/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/aabdukarim/Documents/Code/agenticsocial
configfile: pyproject.toml
plugins: anyio-4.14.2, respx-0.23.1
collecting ... collected 0 items / 1 error

==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_video_status.py __________________
ImportError while importing test module '/Users/aabdukarim/Documents/Code/agenticsocial/tests/test_video_status.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Volumes/aabdukarimExternalSSD/aabdukarimEX/.local/share/uv/python/cpython-3.11.13-macos-aarch64-none/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_video_status.py:3: in <module>
    from agenticsocial.models import (
E   ImportError: cannot import name 'VIDEO_TRANSITIONS' from 'agenticsocial.models' (/Users/aabdukarim/Documents/Code/agenticsocial/src/agenticsocial/models.py)
=========================== short test summary info ============================
ERROR tests/test_video_status.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.05s ===============================
```

Matches the failure the brief predicted.

### GREEN (new test file)

```
$ uv run pytest tests/test_video_status.py -v
============================= test session starts ==============================
platform darwin -- Python 3.11.13, pytest-9.1.1, pluggy-1.6.0 -- /Users/aabdukarim/Documents/Code/agenticsocial/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/aabdukarim/Documents/Code/agenticsocial
configfile: pyproject.toml
plugins: anyio-4.14.2, respx-0.23.1
collecting ... collected 13 items

tests/test_video_status.py::test_render_states_exist PASSED              [  7%]
tests/test_video_status.py::test_both_tables_are_total PASSED            [ 15%]
tests/test_video_status.py::test_approved_may_enter_rendering PASSED     [ 23%]
tests/test_video_status.py::test_in_review_may_not_skip_the_gate PASSED  [ 30%]
tests/test_video_status.py::test_approved_may_not_jump_straight_to_rendered PASSED [ 38%]
tests/test_video_status.py::test_failed_render_may_retry PASSED          [ 46%]
tests/test_video_status.py::test_rendering_may_fail PASSED               [ 53%]
tests/test_video_status.py::test_approval_may_be_revoked PASSED          [ 61%]
tests/test_video_status.py::test_published_is_terminal_for_video PASSED  [ 69%]
tests/test_video_status.py::test_text_table_rejects_rendering PASSED     [ 76%]
tests/test_video_status.py::test_text_pipeline_is_unchanged PASSED       [ 84%]
tests/test_video_status.py::test_error_message_lists_the_right_table_next_states PASSED [ 92%]
tests/test_video_status.py::test_error_message_defaults_to_text_table PASSED [100%]

============================== 13 passed in 0.01s ==============================
```

13 passed, as the brief predicted.

### FULL SUITE — one pre-existing failure

```
$ uv run pytest
============================= test session starts ==============================
platform darwin -- Python 3.11.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/aabdukarim/Documents/Code/agenticsocial
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.2, respx-0.23.1
collected 106 items

tests/test_auth.py ........                                              [  7%]
tests/test_cli.py .......................                                [ 29%]
tests/test_frontmatter.py .......                                        [ 35%]
tests/test_models.py F..............                                     [ 50%]
tests/test_publish.py ........                                           [ 57%]
tests/test_research.py ...                                               [ 60%]
tests/test_textutils.py ........                                         [ 67%]
tests/test_video_status.py .............                                 [ 80%]
tests/test_workspace.py .................                                [ 96%]
tests/test_x_client.py ....                                              [100%]

=================================== FAILURES ===================================
________________________ test_status_values_match_spec _________________________

    def test_status_values_match_spec():
>       assert [s.value for s in Status] == [
            "draft", "in_review", "approved", "scheduled",
            "publishing", "published", "failed",
        ]
E       AssertionError: assert ['draft', 'in...endered', ...] == ['draft', 'in...blished', ...]
E
E         At index 4 diff: 'rendering' != 'publishing'
E         Left contains 2 more items, first extra item: 'published'
E         Use -v to get more diff

tests/test_models.py:7: AssertionError
=========================== short test summary info ============================
FAILED tests/test_models.py::test_status_values_match_spec - AssertionError: ...
======================== 1 failed, 105 passed in 0.32s =========================
```

Per the brief's ground rules I stopped here rather than editing
`tests/test_models.py`, and I did **not** commit.

*This failure was later resolved by Amendment 1 — see the section at the end
of this report for the passing full-suite run. The evidence above is retained
as the honest record of the blocked state.*

## 3. Files changed

| Path | State |
| --- | --- |
| `src/agenticsocial/models.py` | modified |
| `tests/test_video_status.py` | new |
| `tests/test_models.py` | modified — one line, under Amendment 1 |

## 4. Self-review findings

- Both tables are total over `Status` — verified by
  `test_both_tables_are_total`, which iterates the enum rather than a
  hardcoded list, so it will keep catching future additions.
- The error-message string is character-for-character what it was before; only
  the table it reads from is now parameterized. The pre-existing message
  assertions in `tests/test_models.py` still pass.
- `_ORDER = list(Status)` is still defined after both tables, so
  `TransitionError` orders the "allowed next" list by enum declaration order
  for both tables. With `RENDERING`/`RENDERED` placed before `PUBLISHING`, the
  video message for `APPROVED` reads `in_review, rendering` — declaration
  order, not pipeline order. Cosmetic only.
- `assert_transition` and `TransitionError` each independently default `table`
  to `ALLOWED_TRANSITIONS`. `assert_transition` always passes its resolved
  table explicitly, so the two cannot disagree. A caller who raises
  `TransitionError` directly with a video `current` state and no table would
  get a misleading message — no such caller exists today.
- Grepped for other importers of these names: only `tests/test_models.py` and
  the new test file reference `assert_transition`/`TransitionError`; no
  production call site passes positional arguments that the new third
  parameter could capture.
- No new imports, no dependency changes, no formatting churn outside the
  edited regions.

## 5. Issues or concerns

**The brief conflicts with an existing test and does not acknowledge it.**

`tests/test_models.py::test_status_values_match_spec` asserts the *exact
ordered list* of `Status` values. Adding any member to the enum breaks it, and
inserting `RENDERING`/`RENDERED` between `SCHEDULED` and `PUBLISHING` — which
the brief mandates in step 3a — breaks it in two ways at once (order shift and
length change).

The brief simultaneously requires:

- step 3a: insert two enum members at a specific position;
- ground rule: do not modify any existing test file;
- step 4: every pre-existing test must still pass.

These three cannot all hold. I implemented the code as written, did not touch
the existing test, and stopped at the failure, as the ground rules direct.

Resolution needed from the project leader. The options I see:

1. Update `test_status_values_match_spec` to expect the nine-member list. This
   is the intended-looking fix; the test is a literal snapshot of the enum and
   the brief deliberately changes the enum. Someone with authority to edit
   existing tests should make this one-line change.
2. Relax the test to assert a required *subset* and stable *relative* order,
   so it stops breaking on every future enum addition. More work, and it
   weakens the guard.
3. Append `RENDERING`/`RENDERED` at the end of the enum instead. This does not
   help — the test compares the whole list, so it still fails — and it would
   lose the readable pipeline ordering. Not recommended.

I recommend option 1.

Secondary, lower-priority notes:

- `VIDEO_TRANSITIONS[Status.FAILED] = {Status.RENDERING}` means a failure
  during the *publish* step of a video sends the retry back to re-rendering,
  which is the expensive operation. A publish failure arguably should retry
  `PUBLISHING`. As written, `FAILED` cannot reach `PUBLISHING` at all for
  video, so a failed video upload can only be recovered by re-rendering. Worth
  confirming this is intentional before Phase 2 wires up publishing.
- `Status.SCHEDULED` maps to `set()` in both tables, so it is a dead-end state
  reachable from nothing. Fine as a v2 placeholder; just noting it is inert.
- `RENDERING`/`RENDERED` are legal enum values for a text variant even though
  they are unreachable in `ALLOWED_TRANSITIONS`. Nothing stops code from
  constructing `Variant(status=Status.RENDERING)` directly, or from
  deserializing that value out of frontmatter. The transition table guards
  transitions, not construction. A later task may want a per-kind validity
  check at the parse boundary.

## 6. Commit

*(Original entry, superseded by Amendment 1 below.)*

**None.** No commit was made because the full suite is red on a pre-existing
test, and the brief directs me to stop rather than edit it.

Working tree state (uncommitted) on `feat/video-phase-01-scaffolding`:

```
 M src/agenticsocial/models.py
?? tests/test_video_status.py
```

The changes are intact on disk and ready to commit as
`feat: add rendering/rendered states and a video transition table` as soon as
the `test_models.py` conflict is resolved.

---

# Amendment 1 — resolution

The project leader verified the failure independently and issued Amendment 1
to the brief on 2026-08-16, granting a scoped, one-test exception to the
"do not modify any existing test file" ground rule.

## A1.1 The test change

`tests/test_models.py::test_status_values_match_spec` is a snapshot assertion
over the entire `Status` enum as an ordered list. This task deliberately
extends that enum, so the snapshot must be re-taken. Per Step 3d I updated
**only** the expected list, and changed nothing else in the file.

The complete diff to `tests/test_models.py`:

```diff
--- a/tests/test_models.py
+++ b/tests/test_models.py
@@ -6,6 +6,7 @@ from agenticsocial.models import Status, TransitionError, assert_transition
 def test_status_values_match_spec():
     assert [s.value for s in Status] == [
         "draft", "in_review", "approved", "scheduled",
+        "rendering", "rendered",
         "publishing", "published", "failed",
     ]
```

One line added. No other test in that file was touched, no assertion was
weakened, and the test still snapshots the full enum in declaration order — so
it will keep failing loudly on any future unreviewed enum change, which is the
behaviour that caught this task in the first place.

**Reason:** the test encodes "the enum is exactly these seven values in this
order". That statement was true before this task and is false after it, by
design. Updating the expectation is re-recording a fact the spec changed; it
is not suppressing a failure. The distinction matters, which is why the change
required explicit authorisation rather than my own judgement.

## A1.2 GREEN — new test file

```
$ uv run pytest tests/test_video_status.py -v
============================= test session starts ==============================
platform darwin -- Python 3.11.13, pytest-9.1.1, pluggy-1.6.0 -- /Users/aabdukarim/Documents/Code/agenticsocial/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/aabdukarim/Documents/Code/agenticsocial
configfile: pyproject.toml
plugins: anyio-4.14.2, respx-0.23.1
collecting ... collected 13 items

tests/test_video_status.py::test_render_states_exist PASSED              [  7%]
tests/test_video_status.py::test_both_tables_are_total PASSED            [ 15%]
tests/test_video_status.py::test_approved_may_enter_rendering PASSED     [ 23%]
tests/test_video_status.py::test_in_review_may_not_skip_the_gate PASSED  [ 30%]
tests/test_video_status.py::test_approved_may_not_jump_straight_to_rendered PASSED [ 38%]
tests/test_video_status.py::test_failed_render_may_retry PASSED          [ 46%]
tests/test_video_status.py::test_rendering_may_fail PASSED               [ 53%]
tests/test_video_status.py::test_approval_may_be_revoked PASSED          [ 61%]
tests/test_video_status.py::test_published_is_terminal_for_video PASSED  [ 69%]
tests/test_video_status.py::test_text_table_rejects_rendering PASSED     [ 76%]
tests/test_video_status.py::test_text_pipeline_is_unchanged PASSED       [ 84%]
tests/test_video_status.py::test_error_message_lists_the_right_table_next_states PASSED [ 92%]
tests/test_video_status.py::test_error_message_defaults_to_text_table PASSED [100%]

============================== 13 passed in 0.01s ==============================
```

13 passed.

## A1.3 GREEN — full suite

```
$ uv run pytest
============================= test session starts ==============================
platform darwin -- Python 3.11.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/aabdukarim/Documents/Code/agenticsocial
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.2, respx-0.23.1
collected 106 items

tests/test_auth.py ........                                              [  7%]
tests/test_cli.py .......................                                [ 29%]
tests/test_frontmatter.py .......                                        [ 35%]
tests/test_models.py ...............                                     [ 50%]
tests/test_publish.py ........                                           [ 57%]
tests/test_research.py ...                                               [ 60%]
tests/test_textutils.py ........                                         [ 67%]
tests/test_video_status.py .............                                 [ 80%]
tests/test_workspace.py .................                                [ 96%]
tests/test_x_client.py ....                                              [100%]

============================= 106 passed in 0.31s ==============================
```

106 passed, 0 failed. `tests/test_models.py` is fully green (15 dots, was
`F..............`). No other test file changed behaviour.

## A1.4 Commit

**SHA:** `41ad23e3d026d5ee75040bc613f6415b2534b632` (short: `41ad23e`)
**Branch:** `feat/video-phase-01-scaffolding`
**Message:** `feat: add rendering/rendered states and a video transition table`

```
 src/agenticsocial/models.py | 39 ++++++++++++++++++++---
 tests/test_models.py        |  1 +
 tests/test_video_status.py  | 77 +++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 112 insertions(+), 5 deletions(-)
```

Exactly the three files named in the amended Step 5. No branch created, no
merge, no push. `PROGRESS.md` and `DECISIONS.md` untouched.

## A1.5 Note on the open design concern

Per the leader's direction I left `VIDEO_TRANSITIONS` exactly as the brief
specifies. The concern is logged as **D-003** and raised with the human: the
reachable path `RENDERED -> PUBLISHING -> FAILED -> RENDERING` means a failed
*upload* forces a full re-render, because `FAILED` has no edge back to
`PUBLISHING` in the video table. Recording it here so the constraint is
visible to whoever picks up Phase 2 publishing.

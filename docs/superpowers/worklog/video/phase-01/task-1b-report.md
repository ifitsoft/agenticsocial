# Task 1b Report: Cut `RENDERED → PUBLISHING`, close the QA test gaps

**Branch:** `feat/video-phase-01-scaffolding`
**Commits:** `1016c09` (tests, RED) → `43799e5` (implementation, GREEN)

## 1. What I changed

**`tests/test_video_status.py`** — appended six tests at the end of the file.
Nothing above them was touched. Three assert what the tables must *allow*
(`rendering -> rendered`, the exact `FAILED` recovery set, the text table's
render dead-ends); three pin the D-006 decision (`rendered` terminal, no video
state reaching a publish state) and QA finding 3 (`TransitionError` must be
given a table).

**`src/agenticsocial/models.py`** — two changes:

- `VIDEO_TRANSITIONS[Status.RENDERED]` is now `set()` (was `{Status.PUBLISHING}`),
  and `VIDEO_TRANSITIONS[Status.PUBLISHING]` is now `set()` (was
  `{Status.PUBLISHED, Status.FAILED}`). Both keys stay in the table so it remains
  total. This implements D-006: the edge was reachable but never exercised in
  MVP, and it left `FAILED -> RENDERING` as the only recovery, so a *publish*
  failure could only be recovered by re-rendering an artifact already on disk.
- `TransitionError.__init__`'s `table` parameter is now required (the
  `| None = None` default and the `ALLOWED_TRANSITIONS` fallback are gone). A
  defaulted table meant a video caller could be handed the *text* allowed-set
  ("allowed next: in_review, publishing"). `assert_transition` is the only
  construction site in `src/` (verified by grep) and always passes a resolved
  table, so nothing else needed updating. `assert_transition`'s own `table=None`
  default is untouched — `publish.py` and `cli.py` rely on it.

## 2. TDD evidence

### RED — at commit `1016c09` (tests only, implementation unchanged)

Per-test result, `uv run pytest tests/test_video_status.py -v` (piped to file):

```
tests/test_video_status.py::test_render_states_exist PASSED              [  5%]
tests/test_video_status.py::test_both_tables_are_total PASSED            [ 10%]
tests/test_video_status.py::test_approved_may_enter_rendering PASSED     [ 15%]
tests/test_video_status.py::test_in_review_may_not_skip_the_gate PASSED  [ 21%]
tests/test_video_status.py::test_approved_may_not_jump_straight_to_rendered PASSED [ 26%]
tests/test_video_status.py::test_failed_render_may_retry PASSED          [ 31%]
tests/test_video_status.py::test_rendering_may_fail PASSED               [ 36%]
tests/test_video_status.py::test_approval_may_be_revoked PASSED          [ 42%]
tests/test_video_status.py::test_published_is_terminal_for_video PASSED  [ 47%]
tests/test_video_status.py::test_text_table_rejects_rendering PASSED     [ 52%]
tests/test_video_status.py::test_text_pipeline_is_unchanged PASSED       [ 57%]
tests/test_video_status.py::test_error_message_lists_the_right_table_next_states PASSED [ 63%]
tests/test_video_status.py::test_error_message_defaults_to_text_table PASSED [ 68%]
tests/test_video_status.py::test_rendering_may_complete PASSED           [ 73%]
tests/test_video_status.py::test_rendered_is_terminal_in_mvp FAILED      [ 78%]
tests/test_video_status.py::test_no_video_state_reaches_publishing FAILED [ 84%]
tests/test_video_status.py::test_failed_has_exactly_one_recovery_edge PASSED [ 89%]
tests/test_video_status.py::test_text_table_render_states_stay_dead_ends PASSED [ 94%]
tests/test_video_status.py::test_transition_error_requires_an_explicit_table FAILED [100%]
```

Failure detail and summary:

```
        recovery matches what actually failed.
        """
>       assert VIDEO_TRANSITIONS[Status.RENDERED] == set()
E       AssertionError: assert {<Status.PUBL...'publishing'>} == set()
E
E         Extra items in the left set:
E         <Status.PUBLISHING: 'publishing'>
E
E         Full diff:
E         - set()
E         + {
E         +     <Status.PUBLISHING: 'publishing'>,
E         + }

tests/test_video_status.py:97: AssertionError
____________________ test_no_video_state_reaches_publishing ____________________

    def test_no_video_state_reaches_publishing():
        """Nothing in the MVP video lifecycle may enter the publish states."""
        for source, targets in VIDEO_TRANSITIONS.items():
>           assert Status.PUBLISHING not in targets, f"{source} -> publishing"
E           AssertionError: Status.RENDERED -> publishing
E           assert <Status.PUBLISHING: 'publishing'> not in {<Status.PUBLISHING: 'publishing'>}
E            +  where <Status.PUBLISHING: 'publishing'> = Status.PUBLISHING

tests/test_video_status.py:103: AssertionError
_______________ test_transition_error_requires_an_explicit_table _______________

    def test_transition_error_requires_an_explicit_table():
        """QA finding 3: a defaulted table silently reported the TEXT allowed-set,
        so a video caller could be told 'allowed next: in_review, publishing'."""
>       with pytest.raises(TypeError):
E       Failed: DID NOT RAISE TypeError

tests/test_video_status.py:126: Failed
=========================== short test summary info ============================
FAILED tests/test_video_status.py::test_rendered_is_terminal_in_mvp - Asserti...
FAILED tests/test_video_status.py::test_no_video_state_reaches_publishing - A...
FAILED tests/test_video_status.py::test_transition_error_requires_an_explicit_table
========================= 3 failed, 16 passed in 0.03s =========================
```

**Of the six new tests:**

| New test | RED |
|---|---|
| `test_rendering_may_complete` | PASSED (characterisation) |
| `test_rendered_is_terminal_in_mvp` | **FAILED** |
| `test_no_video_state_reaches_publishing` | **FAILED** |
| `test_failed_has_exactly_one_recovery_edge` | PASSED (characterisation) |
| `test_text_table_render_states_stay_dead_ends` | PASSED (characterisation) |
| `test_transition_error_requires_an_explicit_table` | **FAILED** |

3 failures, exactly as the brief predicted, and the same three it named.

### GREEN — at commit `43799e5`

`uv run pytest tests/test_video_status.py -v`:

```
============================= test session starts ==============================
platform darwin -- Python 3.11.13, pytest-9.1.1, pluggy-1.6.0 -- /Users/aabdukarim/Documents/Code/agenticsocial/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/aabdukarim/Documents/Code/agenticsocial
configfile: pyproject.toml
plugins: anyio-4.14.2, respx-0.23.1
collecting ... collected 19 items

tests/test_video_status.py::test_render_states_exist PASSED              [  5%]
tests/test_video_status.py::test_both_tables_are_total PASSED            [ 10%]
tests/test_video_status.py::test_approved_may_enter_rendering PASSED     [ 15%]
tests/test_video_status.py::test_in_review_may_not_skip_the_gate PASSED  [ 21%]
tests/test_video_status.py::test_approved_may_not_jump_straight_to_rendered PASSED [ 26%]
tests/test_video_status.py::test_failed_render_may_retry PASSED          [ 31%]
tests/test_video_status.py::test_rendering_may_fail PASSED               [ 36%]
tests/test_video_status.py::test_approval_may_be_revoked PASSED          [ 42%]
tests/test_video_status.py::test_published_is_terminal_for_video PASSED  [ 47%]
tests/test_video_status.py::test_text_table_rejects_rendering PASSED     [ 52%]
tests/test_video_status.py::test_text_pipeline_is_unchanged PASSED       [ 57%]
tests/test_video_status.py::test_error_message_lists_the_right_table_next_states PASSED [ 63%]
tests/test_video_status.py::test_error_message_defaults_to_text_table PASSED [ 68%]
tests/test_video_status.py::test_rendering_may_complete PASSED           [ 73%]
tests/test_video_status.py::test_rendered_is_terminal_in_mvp PASSED      [ 78%]
tests/test_video_status.py::test_no_video_state_reaches_publishing PASSED [ 84%]
tests/test_video_status.py::test_failed_has_exactly_one_recovery_edge PASSED [ 89%]
tests/test_video_status.py::test_text_table_render_states_stay_dead_ends PASSED [ 94%]
tests/test_video_status.py::test_transition_error_requires_an_explicit_table PASSED [100%]

============================== 19 passed in 0.01s ==============================
```

`uv run pytest`:

```
tests/test_frontmatter.py .......                                        [ 33%]
tests/test_models.py ...............                                     [ 47%]
tests/test_publish.py ........                                           [ 54%]
tests/test_research.py ...                                               [ 57%]
tests/test_textutils.py ........                                         [ 64%]
tests/test_video_status.py ...................                           [ 81%]
tests/test_workspace.py .................                                [ 96%]
tests/test_x_client.py ....                                              [100%]

============================= 112 passed in 0.30s ==============================
```

19 in the file, 112 overall — both match the brief. No existing test was edited.

## 3. Files changed

| File | Commit |
|---|---|
| `tests/test_video_status.py` (append only, +52 lines) | `1016c097f4837e2c3b1e1a0f4f1bfd32eef54e85` |
| `src/agenticsocial/models.py` | `43799e5e1fd5bd47bae860b4e6559040c4490b56` |

`PROGRESS.md` and `DECISIONS.md` were not touched. (`DECISIONS.md` shows as
modified in `git status` — that change predates this task and is not mine; I
left it alone and did not stage it.)

## 4. Self-review findings

**The brief contradicts itself about `VIDEO_TRANSITIONS[Status.PUBLISHING]`, and
I followed the code block.** Step 4a's prose says "Leave `PUBLISHING` and
`PUBLISHED` entries exactly as they are", but the "must read exactly" block
immediately below it shows `Status.PUBLISHING: set()`, where the current code
has `{Status.PUBLISHED, Status.FAILED}`. These cannot both be satisfied. The
code block is the correct one: `test_no_video_state_reaches_publishing` asserts
`Status.PUBLISHED not in targets` for *every* source, so leaving
`PUBLISHING: {PUBLISHED, FAILED}` would keep that test red. The prose is also
self-consistent with the intent if read as "do not delete the keys", which is
what I did — both keys remain, now empty, and `test_both_tables_are_total` still
passes. Flagging it because the brief asked me to say so rather than quietly
paper over it.

**`TransitionError` is now positional-required, which is a public API break.** It
is an exported name (`from agenticsocial.models import TransitionError`). Only
`assert_transition` constructs it inside `src/` (grepped), and no test
constructs it with two args except the new one that *expects* the `TypeError`,
so nothing in-repo breaks. Worth knowing if anything outside the repo raises it.

**One pre-existing test now depends on the fallback living in
`assert_transition` rather than in `TransitionError`.**
`test_error_message_defaults_to_text_table` calls
`assert_transition(APPROVED, PUBLISHED)` with no table and asserts "publishing"
appears in the message. It still passes because `assert_transition` resolves
`None -> ALLOWED_TRANSITIONS` before constructing the error. That single
remaining default is now the only thing keeping the text-table behaviour, so it
is load-bearing; the brief was right to say leave it alone.

**`Status.SCHEDULED` remains an isolated node in both tables** — no in-edges, no
out-edges. Out of scope here, noted only because a total-table test can't
distinguish "reserved for v2" from "accidentally orphaned".

## 5. Issues or concerns

**Is `test_failed_has_exactly_one_recovery_edge` a useful guard or an annoyance?**

I think it is a useful guard, but it is one *because* it will be edited when
publishing lands — that is the mechanism, not a failure of it. The test is not
trying to prevent the edge from ever being added; it is trying to make adding it
impossible to do silently. A developer wiring up video publishing will naturally
add `rendered -> publishing` and stop, because at that point the feature works
and every other test is green. The exact-equality assertion on `FAILED` is what
puts a red test in front of them with a docstring pointing at D-006 and the
specific reasoning — a publish failure should recover by re-publishing, not by
re-rendering an artifact that is already on disk. That is a genuinely easy thing
to get wrong and a genuinely annoying one to discover in production.

The cost is real but small: one test to update, in a file where the update is
obvious and the docstring tells you what the right answer is. Compare it to
`test_no_video_state_reaches_publishing`, which will also need editing then —
these two are a matched pair, and I would not remove either.

Two caveats I'd note honestly:

1. The guard only works if the person who trips it reads the docstring instead
   of reflexively widening the set to match. Nothing in a test can prevent that.
   The docstring is written to be read, which is about as far as this technique
   goes.
2. Exact-equality assertions on a data structure are a blunt instrument, and if
   this file accumulated many of them the suite would become change-detector-ish
   rather than behaviour-testing. At two, it's fine. If a future task wants to
   add a third or fourth `== {exact set}` assertion on these tables, that would
   be the moment to reconsider the pattern rather than extend it.

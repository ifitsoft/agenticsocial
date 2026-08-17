# Task 1 Review — Video status machine (`41ad23e`)

**Reviewer:** QA (adversarial). I did not write this code.
I did **not** open `task-1-report.md`.

---

## Verdict

**changes-required**

The implementation matches the brief character-for-character and the full suite is
green, but the test file the brief supplied does not exercise the two edges that are
the entire point of this task. I proved that by mutation: a table in which a render
can never complete still passes all 106 tests. That is a test-suite defect the
implementer inherited rather than authored, but it ships in this commit and it should
be fixed before later tasks build on the table.

---

## Findings

### 1. MAJOR — the two defining video edges are untested; a broken table passes green

`src/agenticsocial/models.py:43-44` (`RENDERING -> {RENDERED, FAILED}`, `RENDERED -> {PUBLISHING}`)
and `tests/test_video_status.py` (whole file).

No test in the repo asserts `assert_transition(Status.RENDERING, Status.RENDERED, VIDEO_TRANSITIONS)`
or `assert_transition(Status.RENDERED, Status.PUBLISHING, VIDEO_TRANSITIONS)`.
`test_rendering_may_fail` covers only the failure edge out of `RENDERING`;
`test_published_is_terminal_for_video` only asserts an empty set.

Concrete failure scenario, verified by mutation. I edited the table to:

```python
Status.RENDERING: {Status.FAILED},
Status.RENDERED: set(),
```

i.e. a lifecycle in which a render can *only* fail and a rendered episode can never be
published — the pipeline is dead. Result: `uv run pytest` → **106 passed**. The suite
cannot distinguish the correct table from one that breaks the happy path entirely.
(File restored; `git status --porcelain` clean.)

This matters because later tasks import `VIDEO_TRANSITIONS` and will trust it. The one
test that would catch a regression here does not exist.

**Fix:** add to `tests/test_video_status.py`:

```python
def test_render_completes():
    assert_transition(Status.RENDERING, Status.RENDERED, VIDEO_TRANSITIONS)


def test_rendered_may_publish():
    assert_transition(Status.RENDERED, Status.PUBLISHING, VIDEO_TRANSITIONS)
```

Stronger and cheaper: replace the hand-picked positives with one snapshot assertion on
the whole `VIDEO_TRANSITIONS` dict, so no edge can be added, removed or altered silently.

### 2. MAJOR — a failed video *publish* can only be recovered by re-rendering

`src/agenticsocial/models.py:46-47`: `PUBLISHING -> {PUBLISHED, FAILED}` and
`FAILED -> {RENDERING}`. `FAILED` carries no memory of which step failed, and its only
outgoing edge is `RENDERING`.

Concrete scenario: an episode reaches `PUBLISHING`, the upload gets a transient 503,
status goes to `FAILED`. The operator retries. The only legal move is `FAILED -> RENDERING`
— a full re-render of a video whose artifact is sitting on disk, intact. The expensive
step is paid again to recover from a cheap, unrelated failure. There is no
`FAILED -> PUBLISHING` edge in `VIDEO_TRANSITIONS`, so this cannot be worked around at
the call site without bypassing the table.

This is the concrete reason retaining `RENDERED -> PUBLISHING` while video publish is
out of MVP scope is **not** free (checklist item 5). Keeping the edge is fine — it is
one entry and it matches spec §10's `rendered → published`. The defect is that keeping
it drags in `PUBLISHING -> FAILED` and leaves `FAILED` overloaded, and the resulting
recovery path is wrong. The lifecycle is only half-built and looks finished.

**Fix (pick one, and say which in the code):**
- Preferred while publish is staged: drop `PUBLISHING`/`PUBLISHED` reachability from the
  video table for now (`RENDERED: set()`), so the unfinished half cannot be entered and
  no wrong recovery path exists. Restore it with the chunked-upload work.
- Or keep the edges and add `FAILED -> {RENDERING, PUBLISHING}`, accepting that `FAILED`
  is ambiguous and the caller decides. Add a comment saying so.

Either way this should be a deliberate, recorded choice, not the current accident.

### 3. MINOR — `TransitionError`'s default-table fallback can report a wrong allowed-set

`src/agenticsocial/models.py:53-66`. The `table` parameter defaults to `None` →
`ALLOWED_TRANSITIONS`. `assert_transition` always forwards its own table, so the two stay
consistent *inside this module*. The brief tells later tasks to import `TransitionError`
by name, and nothing forces them to.

Verified concretely:

```
>>> raise TransitionError(Status.APPROVED, Status.PUBLISHED)
cannot move approved -> published; allowed next: in_review, publishing
```

A later render module that checks `VIDEO_TRANSITIONS` itself and raises
`TransitionError(cur, target)` without the third argument produces exactly that message
for a video episode — telling the operator to publish an unrendered episode. The message
is confidently wrong, and no test catches it because
`test_error_message_defaults_to_text_table` asserts precisely this behaviour is correct.

**Fix:** make `table` required on `TransitionError` and have `assert_transition` (which
already has the default) always pass it. If the signature must stay per the brief, add a
comment at the constructor stating the default is only valid for text callers.

### 4. MINOR — a partial table raises `KeyError`, not `TransitionError`

`src/agenticsocial/models.py:63` and `:75` both do `table[current]` unguarded.
Verified:

```
assert_transition(Status.RENDERED, Status.PUBLISHING, {Status.DRAFT: {Status.IN_REVIEW}})
→ KeyError: <Status.RENDERED: 'rendered'>
```

`cli.py:157/206/219` catch `TransitionError` only, so a partial custom table surfaces as
an unhandled traceback rather than a CLI error message. `test_both_tables_are_total`
guards the two shipped tables — correctly, and it is the best test in the file — but not
a caller-supplied one.

If a new `Status` member is added later without a table entry, `test_both_tables_are_total`
*does* fail, so that specific regression is covered. The residual risk is caller-supplied
tables only, which is why this is minor.

**Fix:** `table.get(current, frozenset())` in both places, or document that callers must
pass a total table.

### 5. MINOR — no test that the *text* table stays closed over the render states

`src/agenticsocial/models.py:30-31`. `test_text_table_rejects_rendering` only covers
`APPROVED -> RENDERING`. Mutation: setting `ALLOWED_TRANSITIONS[RENDERING] = {RENDERED}`
and `[RENDERED] = {PUBLISHING}` — i.e. text variants can now walk the render pipeline,
the exact thing the brief says must be impossible — still gives **106 passed**.

**Fix:** `assert ALLOWED_TRANSITIONS[Status.RENDERING] == set()` and the same for
`RENDERED`; or the whole-dict snapshot from finding 1.

---

## Checklist walkthrough

**1. Brief conformance — exact.** `Status.RENDERING`/`RENDERED` with the right values in
the right ordinal position; `VIDEO_TRANSITIONS` byte-identical to the brief; both
signatures exactly as specified, including the `| None = None` default; message wording
unchanged (`test_error_message_names_allowed_states` in `test_models.py` still passes).
`Source`, `Variant` and the module docstring untouched. Nothing extra was added — no
helper, no `VideoStatus` enum, no second `Status`. Diff is 3 files, 112 insertions.

**3. Tests.** Covered above. Positively: `test_both_tables_are_total` is a genuinely good
test that survives the "would this pass against a stub" question, and the two
error-message tests assert on real content including a negative (`"publishing" not in
message`), which is what makes them non-tautological. The rest are thin.

**4. TDD.** Test and implementation land in the same commit `41ad23e`, so the RED state
is not in git history and I cannot verify it independently. The tests are substantive
(they were dictated verbatim by the brief, so "retrofitted" does not really apply — the
implementer transcribed them). Not a finding against the implementer; recorded as
unverifiable.

**5. Spec §10 fidelity.** The `draft → in_review → approved → rendering → rendered →
published` spine and the `rendering → failed → rendering` retry loop match the diagram.
`approved → in_review` (revoke) is in the table and not in the diagram, which is correct
and consistent with the text pipeline. Spec §10 says "a second transition table **keyed by
kind**" — nothing in this commit does the keying; the table is a positional argument the
caller must remember. That is presumably a later task, but note the silent failure mode:
`workspace.py:206` calls `assert_transition(v.status, target)` with no table, so if a
video episode is ever routed through the existing path it will be *allowed* to go
`APPROVED -> PUBLISHING`, skipping rendering entirely, with no error. The default argument
makes the dangerous case the quiet one. Worth a guard when the kind dispatch lands.

**6. Amendment 1 / `tests/test_models.py`.** Verified with
`git diff 41ad23e~1 41ad23e -- tests/test_models.py`: exactly one hunk, one added line
(`"rendering", "rendered",`). No assertion was loosened, no `parametrize` case removed,
no test deleted or skipped. The list is still an ordered, exhaustive snapshot of the enum
and still fails if any member is added, removed or reordered — I confirmed the mechanism
by observing that the added members had to be inserted at the correct index. This is a
legitimate re-snapshot, exactly what the amendment authorised, and nothing else in the
file changed.

---

## What I verified

| Command | Result |
|---|---|
| `git show 41ad23e --stat` | 3 files, +112 −5. Only the files the brief names. |
| `git show 41ad23e` | Implementation is a verbatim transcription of brief §3a–3d. |
| `git diff 41ad23e~1 41ad23e -- tests/test_models.py` | Single one-line addition; no weakening. |
| `uv run pytest -q` | **106 passed** in 0.27s. |
| Mutation: `RENDERING: {FAILED}`, `RENDERED: set()` | **106 passed** — finding 1. |
| Mutation: text table opened to render states | **106 passed** — finding 5. |
| `assert_transition(RENDERED, PUBLISHING, {DRAFT: {...}})` | `KeyError` — finding 4. |
| `raise TransitionError(APPROVED, PUBLISHED)` | `allowed next: in_review, publishing` — finding 3. |
| `grep -rn assert_transition\|ALLOWED_TRANSITIONS\|TransitionError` | Call sites: `cli.py:205`, `workspace.py:206`, tests. All use the default table; all still correct for text. |
| `git status --porcelain` after mutations | Clean — working tree restored, nothing committed. |

## What I could not verify

- **The RED state.** Test and implementation are in one commit; I have no independent
  evidence the test was written first or ever failed. The brief's predicted
  `ImportError` is plausible but unconfirmed from git.
- **`task-1-report.md`** — not read, per instruction. Any TDD evidence pasted there is
  outside this review.
- **Whether findings 2 and 3 are already resolved by a later task's design.** I reviewed
  this commit against the brief and spec §§3/7/10 only; I did not read the phase-1 plan
  for tasks 2+, so the kind-dispatch and publish-retry concerns may be scheduled work
  rather than gaps.
- **Runtime behaviour of the video pipeline** — nothing consumes `VIDEO_TRANSITIONS` yet,
  so the table is only verified against tests, not against a real episode.

---

## Would I merge this?

Not as-is, but it is close. Finding 1 is two lines of test and should be fixed in this
commit — merging a table whose core edges no test defends is how the next task inherits a
silent bug. Finding 2 needs a decision recorded, not necessarily a code change. Findings
3–5 are safe to file as follow-ups.

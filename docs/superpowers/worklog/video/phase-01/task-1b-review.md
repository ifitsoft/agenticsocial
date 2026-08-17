# Task 1b Review — QA (adversarial)

**Commits reviewed:** `1016c09` (tests) · `43799e5` (implementation)
**Branch:** `feat/video-phase-01-scaffolding`
**Reviewer note:** I did not open `task-1b-report.md` or `task-1-report.md`. I read
`task-1b-brief.md`, spec §10, `src/agenticsocial/models.py`, `tests/test_video_status.py`,
`src/agenticsocial/cli.py`, `src/agenticsocial/workspace.py`, and the two commit diffs.
(I did incidentally see three lines of `task-1-review.md` in a repo-wide grep for
`TransitionError(` — that is my own prior review, not the implementer's account.)

---

## Verdict

**Approve.**

The two-commit split produced a real, independently reproducible RED. The mutation gap
QA found on `41ad23e` is closed for every mutation the brief named, plus several I added.
`VIDEO_TRANSITIONS` matches spec §10 as amended. Making `TransitionError.table` required
is safe — there is exactly one construction site in `src/`.

Three mutants still survive, all in edges that no test constrains. One of them
(`draft -> rendering`) is an approval-gate bypass and is the only finding I would ask for
before phase 2 wires this table to anything. It is not a blocker for this commit pair,
because `VIDEO_TRANSITIONS` has no consumer in `src/` yet, and because closing it was not
in the brief. I would merge and open it as the next task.

---

## Findings

### F1 — `draft -> rendering` can be added to `VIDEO_TRANSITIONS` and all 112 tests pass (medium)

`src/agenticsocial/models.py:40`

The video table's whole reason for existing is that "the expensive step is rendering, and
it sits behind the same human gate that publishing sits behind for text" (models.py:37-38,
spec §10). The suite guards exactly one bypass — `test_in_review_may_not_skip_the_gate`
(`tests/test_video_status.py:28`) — and nothing else.

Concrete scenario: someone editing this table adds `Status.DRAFT: {Status.IN_REVIEW,
Status.RENDERING}` (e.g. to support a `--force` render, or by copy-paste). CI is green.
Phase 2 wires `set_status` to the video table and an unapproved, unreviewed draft can now
start a paid render. The gate is gone and no test noticed.

Same class, lower stakes: `Status.SCHEDULED: {Status.RENDERING}` also survives (F2), and
so does widening `Status.PUBLISHING` (F3).

**Fix (kills F1, F2, F3 in one line):** the six new tests assert exact equality for three
of nine entries (`RENDERED`, `FAILED`, `PUBLISHED`). Assert the whole table instead — a
single structural test alongside the behavioural ones:

```python
def test_video_table_is_exactly_this():
    """The table IS the gate. Any edge change must be a deliberate edit here."""
    assert VIDEO_TRANSITIONS == {
        Status.DRAFT: {Status.IN_REVIEW},
        Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
        Status.APPROVED: {Status.IN_REVIEW, Status.RENDERING},
        Status.SCHEDULED: set(),
        Status.RENDERING: {Status.RENDERED, Status.FAILED},
        Status.RENDERED: set(),
        Status.PUBLISHING: set(),
        Status.PUBLISHED: set(),
        Status.FAILED: {Status.RENDERING},
    }
```

Keep the behavioural tests too — they say *why* each edge exists; this one says *only these*.

### F2 — `scheduled -> rendering` survives (low)

`src/agenticsocial/models.py:43`. Unconstrained by any test. Severity is low only because
no state has an in-edge to `SCHEDULED` in either table, so it is unreachable today.
`SCHEDULED` is explicitly "reserved for the v2 calendar" (models.py:17); when v2 adds
`approved -> scheduled`, this becomes a live gate bypass. Fixed by F1's table-equality test.

### F3 — `publishing -> {failed}` survives in the video table (low)

`src/agenticsocial/models.py:46`. Spec §10 says `publishing` and `published` "stay in
`VIDEO_TRANSITIONS` as unreachable empty sets purely so the table remains total."
`test_no_video_state_reaches_publishing` only checks that no entry *targets* `PUBLISHING`
or `PUBLISHED`; it does not check that those two entries are themselves empty
(`test_published_is_terminal_for_video` covers `PUBLISHED` but nothing covers `PUBLISHING`).
Cosmetic today — unreachable — but the spec states it as a property and nothing enforces it.
Fixed by F1's table-equality test.

### F4 — `test_transition_error_requires_an_explicit_table` is looser than its name (informational)

`tests/test_video_status.py:123`. It asserts only that `TransitionError(cur, target)` raises
`TypeError`. If someone restores `table: dict | None = None` in the signature but does *not*
restore the `ALLOWED_TRANSITIONS` fallback line, `None[current]` raises `TypeError` and this
test still passes (verified — M12 below, 112 passed). So it does not actually pin
"`table` is a required parameter."

I am filing this as informational, not a defect: the property QA finding 3 actually cared
about is "a video caller can never be handed the text allowed-set," and that property *is*
preserved under M12 — the call blows up instead of lying. And the test does kill the real
regression (re-adding the fallback), which is exactly what it failed on at RED. No change
required; if you want the stronger guarantee, use `inspect.signature` or assert on the
`TypeError` message.

### F5 — the brief contradicts itself about `Status.PUBLISHING`; the implementer followed the code, not the prose (informational, no action)

Brief step 4a says "Leave `PUBLISHING` and `PUBLISHED` entries exactly as they are," but the
verbatim target table three lines below shows `Status.PUBLISHING: set()`. The implementer
changed `PUBLISHING` from `{PUBLISHED, FAILED}` to `set()`.

This was the right call and was in fact *forced*: with `PUBLISHING: {PUBLISHED, FAILED}`,
`test_no_video_state_reaches_publishing` fails on `PUBLISHED in targets`. It also matches
spec §10. Noting it only so the record shows the deviation from the prose was deliberate
and correct.

### Not-findings I checked and cleared

- **Nothing unauthorised in the diff.** `git diff --stat` across the two commits under
  review touches exactly `src/agenticsocial/models.py` (7 lines) and
  `tests/test_video_status.py` (+50). No existing test was altered — `1016c09` is
  append-only below line 77. (`git diff 41ad23e..43799e5` looks much larger, but the extra
  22 files come from the two *intervening* commits `a728cd4` and `59c3a64`, which are not
  part of this review.)
- **No test is tautological.** Every one of the six new tests was observed failing under at
  least one mutation or at RED. See the kill table below.
- **The two exact-equality assertions are a useful tripwire, not brittle noise.**
  `test_failed_has_exactly_one_recovery_edge` (line 107) is the *only* test that kills M3
  (widening `FAILED`); `test_failed_render_may_retry` does not. `test_no_video_state_reaches_publishing`
  (line 100) is the only per-entry-independent guard on the D-006 cut. Both will have to be
  edited when publishing lands — that is the point: D-006's whole content is "these two
  edges must arrive together," and a test that must be consciously rewritten is the
  cheapest way to force that conversation. Their docstrings say so explicitly. The mild
  redundancy (M2 kills two tests, M10 kills two) costs nothing.

---

## What I verified

All commands run from `/Users/aabdukarim/Documents/Code/agenticsocial`.

### 1. RED is real — verified from history, not from the commit message

Restored `41ad23e`'s `models.py` under `HEAD`'s tests:

```
git show 41ad23e:src/agenticsocial/models.py > src/agenticsocial/models.py
uv run pytest tests/test_video_status.py
  FAILED test_rendered_is_terminal_in_mvp
  FAILED test_no_video_state_reaches_publishing
  FAILED test_transition_error_requires_an_explicit_table
  3 failed, 16 passed in 0.02s

uv run pytest
  3 failed, 109 passed in 0.34s
```

Exactly the three the brief predicted, and exactly those three. The other three new tests
(`test_rendering_may_complete`, `test_text_table_render_states_stay_dead_ends`,
`test_failed_has_exactly_one_recovery_edge`) passed at RED, as intended — they are
regression guards on already-correct behaviour, and each is proven able to fail by the
mutations below.

### 2. GREEN at HEAD

```
uv run pytest  →  112 passed in 0.37s
```

### 3. Mutation testing — 12 mutants, 9 killed, 3 survived

Each mutant applied to `src/agenticsocial/models.py`, full suite run, then
`git checkout -- src/agenticsocial/models.py`.

| # | Mutation | Result | Killed by |
|---|---|---|---|
| M1 | video `RENDERING: {FAILED}` (render can only fail) | **killed** 1F/111P | `test_rendering_may_complete` |
| M2 | video `RENDERED: {PUBLISHING}` (undo D-006) | **killed** 2F/110P | `test_rendered_is_terminal_in_mvp`, `test_no_video_state_reaches_publishing` |
| M3 | video `FAILED: {RENDERING, DRAFT}` (widen recovery) | **killed** 1F/111P | `test_failed_has_exactly_one_recovery_edge` |
| M4 | text `RENDERING: {RENDERED}`, `RENDERED: {PUBLISHING}` | **killed** 1F/111P | `test_text_table_render_states_stay_dead_ends` |
| M5 | video `PUBLISHING: {FAILED}` | **SURVIVED** 112P | — (F3) |
| M6 | video `SCHEDULED: {RENDERING}` | **SURVIVED** 112P | — (F2) |
| M7 | video `APPROVED: {RENDERING}` (drop rejection) | **killed** 2F/110P | `test_approval_may_be_revoked`, `test_error_message_lists_the_right_table_next_states` |
| M8 | video `DRAFT: {IN_REVIEW, RENDERING}` (gate bypass) | **SURVIVED** 112P | — (F1) |
| M9 | `assert_transition` default table → `VIDEO_TRANSITIONS` | **killed** 13F/99P | `test_text_table_rejects_rendering`, `test_text_pipeline_is_unchanged`, `test_error_message_defaults_to_text_table`, +10 |
| M10 | video `FAILED: set()` (no retry) | **killed** 2F/110P | `test_failed_render_may_retry`, `test_failed_has_exactly_one_recovery_edge` |
| M11 | video `IN_REVIEW: {DRAFT, APPROVED, RENDERING}` | **killed** 1F/111P | `test_in_review_may_not_skip_the_gate` |
| M12 | `TransitionError.table` optional again, fallback line left deleted | **SURVIVED** 112P | — (F4) |

Every mutation the brief asked me to try (M1, M2, M3, M4) is killed. The original QA
mutation — "breaking the render path so a render could only fail and never complete,
all 106 green" — is M1, and it now fails a test. **The gap the review was written to close
is closed.**

### 4. `VIDEO_TRANSITIONS` vs spec §10

Read `models.py:39-49` against spec §10 line by line. Match, including the two properties
§10 states in prose: `rendered` terminal, and `publishing`/`published` retained as
unreachable empty sets for table totality. `test_both_tables_are_total`
(`tests/test_video_status.py:17`) enforces totality for every `Status` member.

### 5. `TransitionError(table=...)` required — construction-site audit

`grep -rn "TransitionError(" .` over the whole repo. Every hit outside `docs/` (which is
prose and plan files, not executed):

- `src/agenticsocial/models.py:54` — the class definition.
- `src/agenticsocial/models.py:76` — `raise TransitionError(current, target, table)` inside
  `assert_transition`, which always resolves `table` first (line 74). **The only
  construction site in `src/`.**
- `tests/test_video_status.py:127` — the deliberate no-table call under `pytest.raises`.

Every other reference is a `catch`, not a construct: `cli.py:157`, `cli.py:206`, `cli.py:219`
(the post error paths), `tests/test_workspace.py:115`, `tests/test_publish.py:107`. All
`assert_transition` callers that omit a table — `cli.py:205`, `workspace.py:206` — still work,
because `assert_transition` kept its `table=None` default and coalesces before constructing.
Full suite green confirms it. **No caller path breaks.**

Side note for the record: the brief refers to `publish.py`; no such module exists
(`src/agenticsocial/` is `cli.py`, `frontmatter.py`, `models.py`, `research.py`,
`textutils.py`, `workspace.py`, `x/`). The publish path lives in `cli.py` and `x/`. The
brief's conclusion was right anyway.

### 6. Tree left clean

```
git status --porcelain   →  (empty)
uv run pytest            →  112 passed in 0.27s
```

No source or test file is modified. (The docs tree moved under me mid-review — an external
process committed `66fd109 docs: record task 1b, QA adjudication, and the two-commit rule`
while I was running mutations. That is not my change; I touched only
`src/agenticsocial/models.py`, always restored, and this review file.)

---

## What I could not verify

- **That D-006 is the right product decision.** I checked the code against the spec as
  amended; whether `rendered` *should* be terminal is a human call I take as given.
- **End-to-end behaviour of the video lifecycle.** `VIDEO_TRANSITIONS` has no consumer in
  `src/` yet — `workspace.set_status` (`workspace.py:206`) still calls `assert_transition`
  with no table, i.e. the text table. Everything reviewed here is inert scaffolding, which
  is why F1's severity is medium and not high: the gate bypass is currently unreachable at
  runtime. It stops being unreachable the moment phase 2 wires the table in, and the tests
  are the only thing standing between now and then.
- **Whether the implementer actually ran the tests before committing them.** I verified the
  RED state is reproducible from the committed tree, which is the property that matters and
  the one Task 1 could not offer. I did not and cannot verify the order of operations in
  the implementer's session.
- **The two report files** (`task-1b-report.md`, `task-1-report.md`) — deliberately unread,
  per the review instructions.

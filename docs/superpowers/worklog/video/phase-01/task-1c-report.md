# Task 1c Report: Pin both transition tables exactly

**Branch:** `feat/video-phase-01-scaffolding` · **Commit:** `7e240eb` · **Follows:** `66fd109`

## 1. What I added

Appended two guard tests to the end of `tests/test_video_status.py`, verbatim from
the brief, under an `# --- exact table pins ---` header comment:

- `test_video_transitions_table_is_exact` — pins `VIDEO_TRANSITIONS` by dict equality.
- `test_text_transitions_table_is_exact` — pins `ALLOWED_TRANSITIONS` by dict equality.

Why: the three surviving mutants from QA's review of `43799e5` are one class —
*an edge added to a table that no existing test forbids*. The behavioural tests
above them all assert either a permitted edge (`assert_transition(...)` succeeds),
a forbidden edge (`pytest.raises(TransitionError)`), or a single key's value. None
of those forms can notice a *new* key/value pair elsewhere in the dict. Whole-table
equality is the only assertion shape that closes the class rather than the three
instances.

No source file and no existing test was changed. Guard tests pin behaviour that is
already correct, so there is no RED phase and this is one commit (D-013).

## 2. Mutation evidence

Each mutant was applied to `src/agenticsocial/models.py`, the suite was run, output
was piped to a file, and `git checkout src/agenticsocial/models.py` restored the
source before the next. Command in all three cases:

```bash
uv run pytest 2>&1 | tail -5
```

| # | Mutation | Result | Killed by |
|---|---|---|---|
| 1 | `VIDEO_TRANSITIONS[DRAFT] = {IN_REVIEW, RENDERING}` | **KILLED** — `1 failed, 113 passed` | `test_video_transitions_table_is_exact` |
| 2 | `VIDEO_TRANSITIONS[SCHEDULED] = {RENDERING}` | **KILLED** — `1 failed, 113 passed` | `test_video_transitions_table_is_exact` |
| 3 | `VIDEO_TRANSITIONS[PUBLISHING] = {FAILED}` | **KILLED** — `1 failed, 113 passed` | `test_video_transitions_table_is_exact` |

Observed output (pasted from the pipe, not transcribed):

```
=== MUTANT 1: VIDEO_TRANSITIONS[DRAFT] |= {RENDERING} ===
@@ -40 +40 @@ VIDEO_TRANSITIONS: dict[Status, set[Status]] = {
-    Status.DRAFT: {Status.IN_REVIEW},
+    Status.DRAFT: {Status.IN_REVIEW, Status.RENDERING},

tests/test_video_status.py:141: AssertionError
=========================== short test summary info ============================
FAILED tests/test_video_status.py::test_video_transitions_table_is_exact - As...
======================== 1 failed, 113 passed in 0.34s =========================
E       AssertionError: assert {<Status.DRAF...>: set(), ...} == {<Status.DRAF...>: set(), ...}
E         Omitting 8 identical items, use -vv to show
E         Differing items:
E         {<Status.DRAFT: 'draft'>: {<Status.IN_REVIEW: 'in_review'>, <Status.RENDERING: 'rendering'>}} != {<Status.DRAFT: 'draft'>: {<Status.IN_REVIEW: 'in_review'>}}

=== MUTANT 2: VIDEO_TRANSITIONS[SCHEDULED] = {RENDERING} ===
@@ -43 +43 @@ VIDEO_TRANSITIONS: dict[Status, set[Status]] = {
-    Status.SCHEDULED: set(),
+    Status.SCHEDULED: {Status.RENDERING},
tests/test_video_status.py:141: AssertionError
=========================== short test summary info ============================
FAILED tests/test_video_status.py::test_video_transitions_table_is_exact - As...
======================== 1 failed, 113 passed in 0.27s =========================
E         Differing items:
E         {<Status.SCHEDULED: 'scheduled'>: {<Status.RENDERING: 'rendering'>}} != {<Status.SCHEDULED: 'scheduled'>: set()}

=== MUTANT 3: VIDEO_TRANSITIONS[PUBLISHING] = {FAILED} ===
@@ -46 +46 @@ VIDEO_TRANSITIONS: dict[Status, set[Status]] = {
-    Status.PUBLISHING: set(),    # unreachable in MVP; kept for table totality
+    Status.PUBLISHING: {Status.FAILED},
tests/test_video_status.py:141: AssertionError
=========================== short test summary info ============================
FAILED tests/test_video_status.py::test_video_transitions_table_is_exact - As...
======================== 1 failed, 113 passed in 0.30s =========================
E         Differing items:
E         {<Status.PUBLISHING: 'publishing'>: {<Status.FAILED: 'failed'>}} != {<Status.PUBLISHING: 'publishing'>: set()}
```

All three killed. Zero survivors from the class.

Note on mutant 3's diagnostic: the mutant also removes the `# unreachable in MVP`
comment, but only because the pin's failure message is what identifies it. The
mutation itself is the value change.

`src/agenticsocial/models.py` is unmodified after the run — it does not appear in
`git status --porcelain`. The only dirty tracked file is
`docs/superpowers/worklog/video/DECISIONS.md`, which I did not touch (it was
edited outside this task, and per instruction I left it alone and did not stage it).

## 3. Suite and commit

| | Tests |
|---|---|
| Before (`66fd109`) | 112 passed |
| After (`7e240eb`) | 114 passed |

Commit: `7e240eb` — `test: pin both transition tables exactly`. Only
`tests/test_video_status.py` is in the commit.

## 4. Issues and concerns

### Do four exact-equality assertions mean the pattern should be reconsidered?

**Partly. I agree the count is a smell, but I read the smell as pointing at the
older assertions, not the new ones — and I would not collapse anything yet.**

The file now contains six assertions that compare a table value to a literal:

| Test | Assertion |
|---|---|
| `test_published_is_terminal_for_video` | `VIDEO_TRANSITIONS[PUBLISHED] == set()` |
| `test_rendered_is_terminal_in_mvp` | `VIDEO_TRANSITIONS[RENDERED] == set()` |
| `test_failed_has_exactly_one_recovery_edge` | `VIDEO_TRANSITIONS[FAILED] == {RENDERING}` |
| `test_text_table_render_states_stay_dead_ends` | `ALLOWED_TRANSITIONS[RENDERING] == set()`, `[RENDERED] == set()` |
| `test_video_transitions_table_is_exact` | whole dict |
| `test_text_transitions_table_is_exact` | whole dict |

Every one of the first four is now **strictly implied** by one of the last two.
If a per-key pin fails, the whole-table pin fails too. On pure coverage
arithmetic, the first four are dead weight and QA's instinct is right.

Three reasons I would still keep them:

1. **They are not the same artefact.** The per-key tests carry docstrings that
   record *why* the value is what it is — D-006, spec §3.1, "when publishing lands,
   this table gains `rendered -> publishing` AND `failed -> publishing` together".
   That reasoning is the durable asset; the assertion under it is almost incidental.
   Collapsing them deletes the reasoning along with the redundancy, which is a bad
   trade. If they were to be collapsed, the docstrings must move to the pins first —
   and a pin with four paragraphs of unrelated rationale above it is worse than four
   small named tests.

2. **The failure message is better.** `test_failed_has_exactly_one_recovery_edge`
   failing tells a future engineer, by its name alone, which invariant they broke.
   The exact-table pin says "the dict differs" and makes them read a diff. Redundant
   tests with good names are a diagnostic layer, not just coverage. Mutant 1 above is
   the case in point: only the pin caught it, and the message it produced needed a
   `Differing items:` block to interpret.

3. **The redundancy is directional and cheap.** These are pure-data assertions with
   no setup, no I/O, and a combined runtime under a millisecond. The usual cost of
   duplicate tests — maintenance drag when behaviour changes — is real here (change a
   table and you fix two tests, not one), but that friction is the *feature*: it
   forces the person widening a table past both the tripwire and the rationale.

Where I do think the pattern should stop: **two whole-table pins is the ceiling.**
The pin is a class-killer, and there are exactly two tables. If a third table
appears, the right move is a parametrised pin over `(table, expected)` pairs, not a
third copy-pasted function. And no further *per-key* equality tests should be added
to this file — they now buy nothing that the pins do not already provide. New tests
here should be behavioural (`assert_transition` / `pytest.raises`) or should
strengthen the pins' rationale, not add another literal.

One narrow consolidation I would accept if you want the count down:
`test_published_is_terminal_for_video` is the weakest of the four — it has no
docstring and no decision record behind it, so it is redundancy without the
compensating rationale. Deleting that one alone would take the count to three and
lose nothing. I did not do it, because the brief said append-only and do not modify
existing tests.

### Other notes

- Neither pin asserts anything about *key* completeness beyond what dict equality
  gives — but dict equality does cover it, so `test_both_tables_are_total` is now
  also implied. Same argument as above applies: its loop produces a much better
  message (`{status} missing from ALLOWED_TRANSITIONS`), so it earns its place.
- The pins compare against literals rather than deriving from the spec, so a
  deliberate spec change requires editing two places (source and test). That is
  intended.

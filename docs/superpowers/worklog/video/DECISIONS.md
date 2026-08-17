# Video MVP — Decisions Log

Every adjudicated QA finding and every deviation from the spec, with reasoning.
Leader-owned. An unrecorded deviation is a defect regardless of whether the code
is correct.

Format: `D-NNN · phase/task · verdict · one-line reasoning`

Verdicts: `fix-now` · `defer` · `reject` · `spec-change`

---

## D-001 · project setup · spec-change
**Worklog is tracked in git**, not left in `.superpowers/sdd/` (whose `.gitignore`
is `*`). v1's audit trail exists only on one machine. Reports carrying RED/GREEN
evidence are the record of how the software was built and belong in history.
`.diff` files remain uncommitted — git already stores every diff.

## D-002 · phase 1 planning · fix-now
Episode functions (`create_episode`, `load_episode`, `list_episodes`,
`resolve_episode`) originally took a `ws: Workspace` parameter none of them used.
`Series` already carries `episodes_dir`, so `Series` is the correct scope. Fixed
in the plan before dispatch rather than costing four QA cycles.

## D-003 · phase 1 / task 1 · defer — SHARPENED 2026-08-16
`VIDEO_TRANSITIONS[Status.FAILED] == {Status.RENDERING}` is intentionally
render-only, even though `FAILED` is also reachable from `PUBLISHING`. Video
publishing is out of MVP scope (spec §3.1).

The Task 1 implementer independently flagged this and stated it more precisely
than I had: because the table also contains `RENDERED → PUBLISHING`, the path
`RENDERED → PUBLISHING → FAILED → RENDERING` is *reachable*, so a video **publish**
failure could only be recovered by re-running the expensive render. `FAILED`
cannot reach `PUBLISHING` at all.

Considered removing `RENDERED → PUBLISHING` to make the MVP table render-only,
which would dissolve the ambiguity. **Rejected for now:** spec §10's diagram
explicitly shows `rendered → published`, and deviating from the spec is not the
leader's unilateral call (roadmap §6). MVP never exercises the edge, so it blocks
nothing. **Must be resolved before video publishing is implemented** — raised
with the human 2026-08-16.

## D-005 · phase 1 / task 1 · fix-now
The original Task 1 brief was internally contradictory: add two `Status` members,
do not modify existing tests, keep the suite green. `test_models.py:7`
(`test_status_values_match_spec`) snapshots the whole enum as an ordered list, so
the three cannot hold together. The implementer implemented as written, refused
to edit the existing test, and stopped without committing — exactly correct.

Resolution: Amendment 1 to the brief grants a scoped exception to update that one
snapshot test to the nine-member list. It is a snapshot of an enum this task
deliberately extends; updating it is not weakening a test.

**Process lesson:** the Phase 1 plan's exit criterion "no existing test file was
modified" is wrong as an absolute. Snapshot/inventory tests legitimately change
when the thing they inventory changes. Criterion reworded to: *no existing test
was modified except where the plan explicitly authorises it, with reasoning.*

## D-004 · phase 1 / task 1 · defer
`ALLOWED_TRANSITIONS` gains `RENDERING`/`RENDERED` as empty sets purely so the
table stays total and `table[current]` cannot raise `KeyError`. A text variant
reaching either state is a bug elsewhere. Accepted as the cheapest option that
keeps one enum; revisit if a third lifecycle ever appears.

## D-006 · phase 1 / task 1b · spec-change — HUMAN DECISION 2026-08-16
**Cut `RENDERED → PUBLISHING` from `VIDEO_TRANSITIONS`.** `rendered` is terminal
for the MVP. Resolves D-003, which had been deferred pending this call.

Reasoning: the edge was reachable but never exercised, and it made `FAILED`
ambiguous — with `FAILED → RENDERING` as the only recovery edge, a *publish*
failure could only be recovered by re-rendering an artifact already on disk. A
state machine whose only exit from a state is the wrong one is worse than one
that declines to model the state.

When video publishing lands, the table gains `rendered → publishing` **and**
`failed → publishing` together. `PUBLISHING`/`PUBLISHED` keys stay as empty sets
so the table remains total. Spec §10 updated.

## D-007 · infrastructure · fix-now — HUMAN DECISION 2026-08-16
**Moved `workspace/brief-video/` → `engine/`.** `workspace/` is gitignored
wholesale, so ~1.5k lines of hand-written engine source had no version history,
and Phase 4 modifies `engine.js` on a branch — impossible for an ignored file.
Moved intact so relative paths keep working. Tracked: 11 files, 1562 lines.
Ignored within it: `node_modules/`, `frames/`, `probe/`, `*.mp4`, `*.png`.
Repo still 7.89 KiB with zero media tracked.

Noted while doing this: **everything under `workspace/` remains unversioned** —
including, from Phase 1 onward, the operator's series, episodes, and scripts.
That is correct for a distributed tool (a user's content is not the tool's repo)
but means the operator needs their own backup. Recorded in `CLAUDE.md`.

## D-008 · phase 1 / task 1 · QA adjudication 2026-08-16
QA verdict on `41ad23e`: **changes-required**. It mutation-tested the table —
broke the render path so a render could only fail, never complete — and all 106
tests passed. Adjudication:

| # | Sev | Finding | Verdict |
|---|---|---|---|
| 1 | major | No test exercises `RENDERING → RENDERED`; mutation survived | **fix-now** → Task 1b |
| 2 | major | `FAILED` has one edge; publish failure forces re-render | **resolved by D-006** |
| 3 | minor | `TransitionError`'s defaulted table silently reports the *text* allowed-set to a video caller | **fix-now** → Task 1b. Verified only one construction site, which always passes a table, so making it required is safe |
| 4 | minor | Unguarded `table[current]` raises `KeyError` on a partial caller-supplied table | **defer.** `test_both_tables_are_total` guards the two real tables; a partial table is a programming error, and `KeyError` is an honest signal for one. Revisit if a caller ever builds a table dynamically |
| 5 | minor | Nothing asserts the text table's render entries stay empty | **fix-now** → Task 1b |

Findings 1 and 5 are the valuable ones and both came from mutation testing rather
than reading. Worth keeping that in the QA brief for later phases.

## D-009 · process · fix-now
**Tasks now produce two commits: tests first (failing), then implementation.**
QA on Task 1 reported it *could not verify the RED phase* — test and
implementation arrived in one commit, so there was no independent evidence the
test ever failed. The implementer's pasted output is a claim; git history is
evidence. Cost is one extra commit per task.

Also: implementers must **pipe** command output into their reports rather than
hand-transcribe. Task 1's implementer disclosed it transcribed by hand and caught
its own error doing so — the honesty is welcome, the method is not.

## D-010 · phase 1 / task 1b · leader error, resolved by implementer
Task 1b's brief contradicted itself: Step 4a's prose said "leave `PUBLISHING` and
`PUBLISHED` entries exactly as they are", while the authoritative code block
below it showed `Status.PUBLISHING: set()` where the code had
`{Status.PUBLISHED, Status.FAILED}`.

The implementer followed the code block and justified it from the test:
`test_no_video_state_reaches_publishing` asserts `PUBLISHED not in targets` for
*every* source, so leaving `PUBLISHING: {PUBLISHED, FAILED}` would have kept that
test red. Correct resolution, correctly reasoned, and flagged rather than
silently absorbed.

**Second brief defect in two tasks, both from me.** Pattern: when a brief states
a rule in prose *and* shows the result in code, the two drift. Fix for Task 2
onward — briefs show the final state of any changed block in code and do not
also narrate what to preserve. Code blocks are authoritative; prose explains
*why*, never *what*.

## D-011 · phase 1 / task 1b · verification
RED reproduced independently from git history rather than from the report:
`git checkout 1016c09 -- src/agenticsocial/models.py` against the new tests gives
`3 failed, 16 passed`, matching the prediction exactly. Restored to `HEAD` →
`112 passed`. D-009's two-commit rule justified itself on first use.

---

## Open risks carried from the spec

- Mechanical verifier too strict → operators override reflexively → gate becomes
  theatre. Track override rate from Phase 5 onward.
- `custom` beat ratio above ~15% means the declarative type catalogue is wrong.
  Track from Phase 4.
- ~~Engine source untracked~~ — **resolved 2026-08-16, see D-007.**
- The operator's `workspace/` content (series, episodes, scripts, claims) is
  unversioned by design. No backup story yet. Not a code risk; is a data risk.

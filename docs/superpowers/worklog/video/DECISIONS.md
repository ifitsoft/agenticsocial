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

---

## Open risks carried from the spec

- Mechanical verifier too strict → operators override reflexively → gate becomes
  theatre. Track override rate from Phase 5 onward.
- `custom` beat ratio above ~15% means the declarative type catalogue is wrong.
  Track from Phase 4.
- Engine source (`engine.js`, `scene.html`, `render.mjs`, `content/*.js`) is
  currently **untracked** because `workspace/` is gitignored. Must move to
  `engine/` before Phase 4 can modify it on a branch. Raised 2026-08-16; awaiting
  the human's go-ahead.

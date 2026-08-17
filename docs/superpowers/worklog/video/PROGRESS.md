# Video MVP — Progress

Leader-owned. One block per phase, one line per task. Updated after every task
gate, not in batches.

Roadmap: `docs/superpowers/plans/2026-08-16-video-mvp-roadmap.md`
Spec: `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md`

---

## Phase 1 — Series & episode scaffolding
**Branch:** `feat/video-phase-01-scaffolding` (from `main` @ c7b7705)
**Plan:** `docs/superpowers/plans/2026-08-16-phase-01-scaffolding.md`
**Started:** 2026-08-16

Task 1 — Video status machine: **implemented** (commit `41ad23e`), QA dispatched
  Blocked once on a contradictory brief; resolved by Amendment 1 → see D-005.
  Implementer correctly refused to edit an existing test and did not commit.
  Leader-verified: `uv run pytest` → 106 passed; commit touches 3 files;
  `tests/test_models.py` diff is 1 added line, snapshot still full-enum.
  Carries D-003 (RENDERED → PUBLISHING → FAILED → RENDERING) to the human.
Task 1 QA: **changes-required** — mutation testing found the suite asserted
  forbidden transitions well and permitted ones barely at all. Breaking the
  render path left all 106 tests green. 5 findings adjudicated in D-008
  (3 fix-now → Task 1b, 1 resolved by D-006, 1 deferred).
Task 1b — Cut RENDERED→PUBLISHING + close test gaps: **implemented**
  (`1016c09` tests, `43799e5` impl), QA dispatched
  First task under the two-commit rule (D-009). Leader-verified RED from git
  history: old models.py + new tests → 3 failed / 16 passed, matching the
  prediction. Restored → 112 passed.
  Implementer caught a prose/code contradiction in my brief → D-010.
Task 1b QA: **approve**. 12 mutants, 9 killed, 3 survived — all one class
  (an edge added to a table no test forbids), incl. `DRAFT → RENDERING`, an
  approval-gate bypass. Adjudicated in D-012 → Task 1c.
Task 1c — Pin both transition tables: **complete** (`7e240eb`), 114 passed
  First task under D-013 (guard tests justified by mutation kills, not RED).
  All 3 mutants killed. Leader re-verified the gate bypass independently.
  No separate QA pass — see D-015 for why, and why it is not a precedent.
Task 2 — Series configuration: **complete** (`88752ac`, `52c3e4c`, `8a49f9a`)
Task 2 QA: **changes-required** — 34 mutants, 6 survived. Found hostile names
  corrupting both config files, misattributing it to the operator, and blocking
  retry. All findings were brief defects faithfully implemented (D-020).
Task 2b — Harden config: **complete** (`22a78c0`, `8af23fd`), 160 passed
  All 5 surviving mutants killed. Found the D-022 bug in my own fix.
Task 2c — Correct TOML escaper: **complete** (`a5d2ceb`, `2dbf3e9`), 184 passed
  6/6 mutants killed. First task in the phase with no brief defect.
  Leader-verified: emoji and CJK ext-B names now round-trip.
  No per-task QA — narrow change, strong mutation evidence, covered by the
  phase gate. See D-024; the phase gate is NOT optional as a result.
Task 3 — Episode scaffolding: **dispatched**
Task 4 — CLI wiring: not started (adds `series_slugs`, skip-and-warn listing,
  and lone-surrogate rejection at the operator-input boundary — D-025)
Task 5 — Config validation contract: created, runs after Task 4 (D-025)

Phase gate: not reached. Whole-branch QA over `series.py` is REQUIRED —
  2c did not get a per-task review on the understanding that this covers it.

### Phase 1 running notes
- Two leader-authored brief defects so far (D-005, D-010). Both caught by
  implementers rather than reaching QA. Briefs from Task 2 onward: code blocks
  are authoritative, prose explains *why* and never restates *what*.
- Mutation testing is earning its place in the QA brief. Keep it for all phases.

---

## Phases 2–12
Not started. Plans are written just before each phase begins — see roadmap §5
for the map and dependency order.

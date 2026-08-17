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

Planned 4 tasks. Ran 13. Every extra came from a defect an implementer or
reviewer found — none from scope drift.

| Task | Commits | Result |
|---|---|---|
| 1 — Video status machine | `41ad23e` | blocked once on a contradictory brief (D-005); QA: changes-required |
| 1b — Cut RENDERED→PUBLISHING, close test gaps | `1016c09` `43799e5` | QA: approve. First two-commit task (D-009) |
| 1c — Pin both transition tables | `7e240eb` | closed an approval-gate bypass QA found by mutation |
| 2 — Series configuration | `88752ac` `52c3e4c` `8a49f9a` | QA: changes-required, 34 mutants / 6 survivors |
| 2b — Harden config | `22a78c0` `8af23fd` | hostile names corrupted both config files (D-020) |
| 2c — Correct TOML escaper | `a5d2ceb` `2dbf3e9` | my json.dumps fix was itself broken (D-022) |
| 3 — Episode scaffolding | `98a6c7a` `512655e` | reproduced data loss in document 2 (D-027) |
| 3b — Never parse/rewrite beats | `4084bbc` `e0c00da` | two-document YAML confirmed, new reason (D-026) |
| 3c — Byte-exact preservation | `ff70230` `c47236b` | I had verified a proxy, not the guarantee (D-031) |
| 3d — Fix separator arithmetic | `910c850` `7f09648` | mixed line endings ate a byte, silently (D-033) |
| 4 — CLI wiring + input boundary | `37e2b75` `8343b15` `4f09274` | 14 tracebacks found; my CLI tests were vacuous (D-035) |
| 4b — Complete the error surface | `9350dcc` `8bd2cb3` | fixed one module, forgot its sibling (D-036) |
| 5 — Path safety | in flight | verified workspace escape (D-038) |

### What this phase cost, and what it bought
Four attempts were needed for one guarantee (byte preservation). Every failure
was a different defect in *my* specification; implementers made zero errors and
transcribed faithfully every time. The loop caught all of it before merge.

Three findings would have shipped as real harm: an approval-gate bypass, config
corruption that misattributed itself to the operator, and a workspace escape.

### The generalisable lessons
- **D-035** — a test whose own harness performs the transformation under test
  cannot fail. Three instances. Check: *what would this test do if the code did
  nothing?*
- **D-036** — a guard added to one of a matched pair and not the other. Three
  instances, all in `series.py`, all found late.
- **D-021** — briefs are the main defect source. Code blocks authoritative,
  prose explains *why* only.
- **D-040** — before the gate fix harm, after the gate fix confusion. Without a
  stated line the phase does not end.

Phase gate: pending Task 5. Whole-branch QA over `series.py` is MANDATORY —
2c skipped its per-task review on that promise (D-024).

---

## Phases 2–12
Not started. Plans are written just before each phase begins — see roadmap §5
for the map and dependency order.

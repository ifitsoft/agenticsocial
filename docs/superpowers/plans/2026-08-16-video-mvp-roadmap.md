# Video MVP — Roadmap and Development Process

**Spec:** `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md`
**Started:** 2026-08-16
**Status:** Phase 1 planned, not started

This document is the project's control surface. It defines who does what, how
work is tracked, what a phase must satisfy before it merges, and the order the
phases run in. The per-phase executable plans live beside it as
`YYYY-MM-DD-phase-NN-<slug>.md`.

---

## 1. Roles

Three roles, strictly separated. The separation is the point: an implementer who
also reviews their own work reviews it charitably, and a leader who also writes
feature code stops reading reports carefully.

### 1.1 Project Leader — the main session

Staff-level. Owns outcomes, not code. **Never writes feature code or tests.**

Responsibilities:
- Maintains this roadmap and `PROGRESS.md`.
- Writes each `task-N-brief.md` before dispatch. A brief is a contract: exact
  files, exact interfaces, the test cases, the implementation, the commit. The
  implementer should need no other context.
- Dispatches implementer and QA subagents.
- **Adjudicates QA findings.** Not every finding is correct and not every correct
  finding is worth fixing now. Each one is resolved as `fix-now`, `defer` (with a
  line in `DECISIONS.md` saying why), or `reject` (with the reasoning that
  refutes it). Silence is not a resolution.
- Runs the phase gate (§4) and decides whether the branch merges.
- Escalates to the human at the points listed in §6.

Explicitly *not* the leader's job: rewriting an implementer's code to fix it. If
a task comes back wrong, the leader amends the brief and re-dispatches. A leader
who patches code by hand destroys the audit trail the reports exist to create.

### 1.2 Implementer subagent — Opus 5, fresh per task

Sees only its brief. No conversation history, no other tasks' code, no spec
unless the brief cites a section.

- Works strictly TDD: write the failing test, **run it and paste the failure**,
  implement minimally, **run it and paste the pass**, commit.
- Writes `task-N-report.md` including verbatim RED and GREEN output. A report
  asserting tests pass without pasted output is rejected without review.
- Commits its own work with the message from the brief.
- Reports concerns rather than silently deviating. If the brief is wrong, say so
  in the report — do not improvise a better design.

### 1.3 QA subagent — Opus 5, fresh per task

Sees the diff, the brief, and the relevant spec sections. **Never sees the
implementer's report or reasoning** — otherwise it inherits the implementer's
framing and reviews the explanation instead of the code.

Checks, in order:
1. **Does it do what the brief said?** Interfaces match, names match, nothing extra.
2. **Is the logic correct?** Adversarially: what input breaks this?
3. **Do the tests actually test it?** A test that passes against a stubbed
   implementation is not a test. Tautological assertions, over-mocking, and
   tests that would pass if the function returned a constant are findings.
4. **Was TDD real?** The commit history should show the test existing before or
   with the implementation.
5. **Spec fidelity** for anything the spec constrains verbatim.

Writes `task-N-review.md`: verdict (`approve` / `changes-required`), findings
ranked by severity, each with a concrete failure scenario. "Consider renaming
this" is not a finding.

---

## 2. Tracking layout

```
docs/superpowers/
  specs/2026-08-15-agenticsocial-video-mvp-design.md    the design (source of truth)
  plans/
    2026-08-16-video-mvp-roadmap.md                     this file
    2026-08-16-phase-01-scaffolding.md                  executable plan, Phase 1
    …one per phase, written just before the phase starts

  worklog/video/
    PROGRESS.md            leader-owned. one line per task, one block per phase.
    DECISIONS.md           every adjudicated QA finding + every deviation from spec
    phase-01/
      task-1-brief.md      leader → implementer
      task-1-report.md     implementer → leader (RED/GREEN evidence)
      task-1-review.md     QA → leader
      …
      phase-review.md      whole-branch QA before the PR
```

**The worklog is committed.** v1 kept its equivalent in `.superpowers/sdd/`,
which carries a `*` gitignore — so that audit trail exists only on one machine
and dies with it. Reports carrying RED/GREEN evidence are the record of *how*
the software was built; they are worth more than the scratch space they were
written in. They are small markdown and they ship with the phase's commits.

Not committed: `.diff` files. Git history already holds every diff, and storing
them twice invites the two copies to disagree.

Plans are written **just before their phase starts**, not all up front. Phase 6's
plan depends on what Phases 1–5 actually built; writing it now would be fiction.
The phase map (§5) is the commitment; the plans are the execution.

### 2.1 PROGRESS.md format

Carried over from v1, which proved readable at 13 tasks:

```
## Phase 1 — Series & episode scaffolding   branch: feat/video-phase-01-scaffolding
Task 1: complete (commits abc1234..def5678, review clean)
Task 2: complete (commits def5678..9012abc, review: 1 changes-required → fixed 3456def)
  Deferred: series.toml unknown-key tolerance — see DECISIONS.md#d-004
Task 3: in progress
Phase gate: pending
```

---

## 3. Branching

```
main
 └── feat/video-phase-01-scaffolding     tasks 1..N commit here
      → full suite green
      → whole-branch QA review
      → PR → squash? NO. merge commit, history preserved
      → main
 └── feat/video-phase-02-ingest
      …
```

Rules:
- One branch per phase. Branch off `main` **after** the previous phase merged, so
  each phase starts from a known-green base.
- Every task commits separately on the phase branch. Task commits are never
  squashed — `task-N-report.md` cites commit ranges, and squashing breaks the
  audit trail those reports exist to provide.
- A phase branch never merges without passing the §4 gate.
- Phases 4 and 5 are independent (see §5) and may run concurrently in separate
  worktrees via `superpowers:using-git-worktrees`. Everything else is sequential.
- `main` stays green. If it isn't, that is the only work in flight.

---

## 4. The phase gate

The leader verifies each item **by running it and reading the output** — not by
believing a report. Evidence before assertions.

- [ ] Every task report shows a genuine RED (failure output pasted) followed by GREEN.
- [ ] `uv run pytest` passes on the phase branch — full suite, not just new tests.
- [ ] Node engine tests pass, once Phase 4 exists.
- [ ] Every QA finding is resolved: fixed, or recorded in `DECISIONS.md` with reasoning.
- [ ] Whole-branch QA review (`phase-review.md`) returns approve, or its findings are adjudicated.
- [ ] **Spec coverage:** every spec requirement in this phase's scope maps to a task. Gaps are named, not discovered later.
- [ ] `PROGRESS.md` updated; `DECISIONS.md` has an entry for every deviation.
- [ ] No new dependency added that isn't in the spec's stack without an explicit decision entry.

Failing the gate is normal and cheap. Merging a phase that failed it is the
expensive mistake.

---

## 5. Phase map

Order is dependency-driven. Each phase ships something demonstrable — that is the
test of whether the split is real.

| # | Phase | Ships | Depends on |
|---|---|---|---|
| 1 | **Series & episode scaffolding** | `agsoc series new/list`, `agsoc video new`; video status machine | — |
| **1.5** | **Vertical slice — `script.yaml` → MP4** | **a watchable 10s video from a hand-written script** | **1** |
| 2 | **Ingest** | corpus on disk from research / paste / existing source, with `_manifest.json` | 1 |
| 3 | **Script schema** | `script.yaml` parse + validate + runtime estimation; `agsoc video review` | 1 |
| 4 | **Declarative engine (vertical)** | beat types render from `script.yaml`; probe frames | 3 |
| 5 | **Mechanical verifier** | `claims.json`, pass 1, `agsoc video check` | 3 |
| 6 | **`storyboard` skill** | agent authors a valid, sourced `script.yaml` end to end | 2,3,5 |
| 7 | **Approve gate + drift detection** | `agsoc video approve`; `script_sha256` binding | 5 |
| 8 | **Render pipeline** | `agsoc video render` → vertical MP4; retire hand-written path | 4,7 |
| 9 | **Adversarial pass** | pass 2 + `verify` skill; the gate becomes two-pass | 5 |
| 10 | **Wide format** | 1920×1080 layouts + golden frames both formats | 8 |
| 11 | **Coverage ledger** | relocation to series, `agsoc coverage check/add` | 1 |
| 12 | **Review console** | the UI of spec §12 | 8,9 |

### Phase 1.5 — the vertical slice (added 2026-08-16, human decision)

**Purpose: move the human's first "watch a video come out of this" from Phase 8
to immediately after Phase 1.** Phases 2–7 all build toward a render nobody has
seen work. That is a long time to carry an unvalidated assumption, and Phase 4 —
retrofitting a declarative layer onto a working hand-written engine — is already
flagged as the project's highest-uncertainty work.

Ruthlessly minimal. It is a **proof, not a product**:

- **One beat type**, `statement`. It is the most common and its masked word rise
  already exists in `engine.js`.
- **Vertical only.** No `wide` layout.
- **No ingest, no verification, no approve gate.** Read a hand-written
  `script.yaml` directly.
- **Three beats, ~10 seconds.** Long enough to see pacing, short enough to render
  in seconds.

**The architectural question it settles early — how Node reads the script.**
`script.yaml` is two-document YAML, and Node has no YAML parser without a new
dependency. Rather than add one, **Python parses and emits a `plan.json`**, and
`render.mjs` consumes that. This keeps the D-007 boundary exactly where it was
argued to belong: Python orchestrates, Node stays a pure renderer, and the
handoff is a file. Settling that handoff format now is most of the value of this
phase, because Phase 4 inherits it.

**Non-negotiable:** `window.__seek(t)` stays pure. The determinism test ships
green in the same commit as any engine change, or the phase does not gate.

Three tasks, planned when the phase starts: the `plan.json` schema and Python
emitter; the engine building `statement` beats from a plan; and
`agsoc video render` wiring plan → node → ffmpeg.

**First demonstrable end-to-end video: after Phase 1.5.** Full-fidelity rendering
still lands at Phase 8; Phases 1–8 remain the critical path, and 9–12 harden and
extend it. If the project has to stop early, stopping after 8 leaves something
that works — but stopping after 1.5 at least leaves something you can watch.

**Concurrency:** 4 and 5 both depend only on 3 and touch disjoint files (Node
engine vs. Python verifier). They are the one safe parallel pair.

**Risk ordering note.** Phase 4 is the highest-uncertainty phase — it retrofits a
declarative layer onto a working hand-written engine. If it slips, the wide-format
work in Phase 10 slips with it. Its first task is therefore a narrow spike:
render exactly one `statement` beat from YAML through the existing engine, and
prove `__seek(t)` stays pure. That either de-risks the phase in an hour or tells
us the abstraction is wrong while it is still cheap to change.

---

## 6. Escalation to the human

The leader stops and asks rather than deciding, when:

- A QA finding contradicts the spec — the spec may be wrong, and that is not the
  leader's call.
- A phase needs a dependency not in the spec's stack.
- Two tasks in a row come back `changes-required` on the same brief — the brief
  is wrong, not the implementer, and rewriting it needs the human's intent.
- Actual scope exceeds the phase map by more than roughly one task.
- Anything touching auth, keychain, or posting to a live account.

Everything else the leader decides and records.

---

## 6a. How briefs specify tests (adopted 2026-08-17, D-064)

Vacuous tests — tests that pass whatever the code does — appeared in four
separate phases, always in leader-written briefs. The cause is not carelessness:
**a brief written after the implementation is known transcribes it.** An
assertion read off code you just designed cannot disagree with that code.

`passed on arrival` is therefore not a curiosity in a report. **It is the
transcription rate**, and it belongs in every report.

Four rules, in order of yield:

1. **Specify the mutant first; derive the assertion from it.** Mutants used to be
   written in a later step, after the tests, independently — that ordering was
   the bug. Name the weaker implementation, then ask what assertion would notice.
   `match="unsafe"` follows from "the mutant drops the guard"; nobody adds it
   while writing a happy path.
2. **State the rule with its negative half before writing any assertion.**
   "A leading `www-` is stripped; `www` elsewhere is not." Every pin that killed a
   mutant had a negative half; every one that killed nothing had none.
3. **Give each test a one-line `precondition:`** naming what the fixture must NOT
   already be in. Both vacuous tests in Phase 2 failed for exactly this.
4. **Use properties where the rule is infinite and the value is cited
   elsewhere** — keys, suffixes, anything another artifact hard-codes.

> An example should be chosen because it **discriminates**, not because it
> **illustrates**. `blog.google` is what a reader needs; `blog.wwwfoo.com` is what
> the mutant fears.

## 7. Standing conventions

Inherited from v1 and non-negotiable without a decision entry:

- TDD always. Test first, watch it fail, then implement.
- `uv run pytest` is the Python gate. No network in tests; `respx` for HTTP.
- Atomic writes only (`workspace.atomic_write`) for anything under `workspace/`.
- Only the CLI moves status. Agents draft and stop at `in_review`.
- The engine's `__seek(t)` purity is load-bearing — no `Date.now()`, no
  randomness, no CSS keyframes. Any change touching it needs the determinism
  test green in the same commit.
- Never invent a figure. Enforced in Phase 5, honoured from Phase 1.

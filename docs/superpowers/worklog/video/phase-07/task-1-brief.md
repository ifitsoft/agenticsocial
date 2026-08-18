# Task 1 Brief: `agsoc video approve` — the gate

**Phase:** 7 · **Branch:** `feat/video-phase-07-approve`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §8.4 (the gate), §10 (status machine)

Phase 5 can tell you a claim is unsupported. **Nothing stops you rendering
anyway.** This is the one place the project spends its authority.

## The defect this command exists to prevent

D-059, from v1, verified at the time: **a draft was published.**
`status on disk: draft` → 2 tweets posted → `status after: published`.

The mechanism is what matters, because it is the thing you must not rebuild:
the gate was checked against an **in-memory object**, then the save path stamped
`publishing` onto the draft, and the closing transition then passed
**legitimately**. *The bypass laundered itself.* Root cause: a second, ungated
status writer.

Hence D-072: **a gate takes identifiers, not objects.** `approve` loads what it
gates. There must be no argument a caller can shape to change the verdict.

## What `approve` does

`agsoc video approve <ep> [--series S]`:

1. Loads the episode and its `claims.json` **from disk**.
2. Refuses while any claim is `fail`, `no_source`, or an **unattested** `manual`.
3. Refuses on a **stale or absent** ledger — approving against a ledger that no
   longer describes the script is the same defect as never checking.
4. On success: `in_review → approved`, records `script_sha256` and the approver.

**Entity misses do not block** (D-102): they are recorded, not gated, because
gating them would refuse 62% of correct beats and none of the misses measured
were real errors.

**An attested `manual` passes** (D-088). Its `attest` is a person's signed
sentence, which is the honest substitute for a check nobody can run on arbitrary
JavaScript. An unattested one blocks.

## Decide these; do not default

- **Who is the approver?** §8.4's override carries `by:`. Approval should record
  one too, and this system has no user identity. `series.toml` has a `byline`.
  Decide the source, and say what happens when it is empty — the current
  `the-brief` series has `byline = ""`.
- **Does `approve` re-run `check`, or require a fresh ledger on disk?**
  Re-running is friendlier; requiring makes the ledger the artifact of record and
  keeps `approve` a gate rather than a pipeline. **This is the task's one real
  design decision — argue it, do not pick quietly.**

## Rules, each with its negative half

- **R1** `approve` takes identifiers and loads from disk. **Negative:** there is
  no parameter a caller can pass to supply the script or the ledger.
- **R2** Any `fail` / `no_source` / unattested `manual` refuses, **naming the
  claim**. **Negative:** an attested `manual` and a recorded entity miss do not
  block.
- **R3** A stale or absent ledger refuses, distinguishably from an open claim.
  **Negative:** a current, clean ledger approves.
- **R4** Success records `script_sha256` and the approver, and moves
  `in_review → approved` **through `assert_transition`**. **Negative:** approving
  from any other status refuses — `draft → approved` has no edge (§10).
- **R5** **There is no second status writer.** Negative half: prove it rather
  than assert it — enumerate every path in `src/` that writes an episode status
  and show this gate covers each. D-059 is exactly this check not being done.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `approve` accepts a caller-supplied `Script` or ledger | R1 |
| M2 | a `fail` claim approves | R2 |
| M3 | `no_source` treated as passing | R2 |
| M4 | unattested `manual` approves | R2 |
| M5 | attested `manual` blocks | R2 negative |
| M6 | an entity miss blocks | R2 negative, D-102 |
| M7 | stale ledger approves | R3 |
| M8 | absent ledger approves | R3 |
| M9 | `script_sha256` not recorded, or recorded over the wrong bytes | R4 |
| M10 | status written without `assert_transition` | R4, D-059 |
| M11 | `draft → approved` permitted | R4 negative |
| M12 | refusal names no claim | R2 |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1` in any mutation sweep** (D-100).
- **Never quote a piped exit code** (D-105) — twice in one phase, two actors.
- `CliRunner` has swallowed a crash here before (D-035): assert exit code **and**
  output **and** `result.exception`.
- All workspace writes via `workspace.atomic_write`.
- **If you modify `workspace/`, back it up first and restore it.** Real episode:
  `workspace/series/the-brief/episodes/2026-08-17`.
- **You may run `agsoc video approve` only against a throwaway workspace you
  created.** Never against `workspace/` — that is the operator's content and
  approving it is their decision, not yours.
- No new dependencies, no network, no LLM.
- **Report the mutation score.**

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — the command. Commit.
- [ ] **Step 3** — R5's enumeration: every status-writing path in `src/`, and how
      each is gated. Commit any fix separately.
- [ ] **Step 4** — mutants plus your own sweep.
- [ ] **Step 5** — end to end in a throwaway workspace: an episode with an open
      claim refuses; the same episode with the claim fixed approves. **Paste both
      screens.**

---

## Your report

`docs/superpowers/worklog/video/phase-07/task-1-report.md`:

1. **Your two decisions** (approver identity, re-run vs require), argued.
2. **R5's enumeration**, in full. This is the section I will read most carefully.
3. **TDD evidence**, the **mutation score**, all twelve mutants plus your sweep.
4. **Step 5's screens**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **Can you still get an unapproved episode into `rendering`?** Try it. D-059
     was found by asking exactly this and not stopping at the first "no".
   - Is the refusal actionable — does it tell an operator what to *do*?

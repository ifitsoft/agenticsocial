# Task 3 Brief: `agsoc video check`, and making the ledger readable

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier` · **Follows:** `6370d1e`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §8.1, §8.2, §8.4

Closes Phase 5. Tasks 1 and 2 built extraction and the mechanical pass; **nothing
an operator can run touches either of them yet.**

## Why this task is not plumbing

Task 2's run is the reason this phase exists. On the first real content, the
checker refused two fabricated figures — invented in good faith by the person
building the chart, from a source that did not contain them (D-099).

**That refusal is worth nothing until a human sees it, in a form they can act
on.** A verdict of `fail` with a claim id is a true statement and a useless one.
The operator needs the number, the quote it was checked against, and the source
it came from, in one view.

Phase 3 already named the gap: **`quote` is invisible in `review`.** An operator
sees `src` — that a citation exists — but never what the source actually says.
That is the difference between "this beat is cited" and "this beat is true", and
closing it is half this task.

## What to build

**`agsoc video check <series> <episode>`** — runs the pass, writes `claims.json`,
prints a human summary, exits non-zero when anything is `fail` / `no_source` /
unattested `manual`.

**D-072 is settled and load-bearing: a gate takes identifiers, not objects.**
`check` loads what it verifies. Do not accept a `Script` or an `Episode` built by
the caller — the whole point is that the thing verified is the thing on disk.
This is the same class as the v1 defect where a status gate was skipped by
passing an in-memory object (D-059): **a draft was published because the gate
trusted its argument.**

**`agsoc video review` learns to show `quote` and the verdict.** Design the
display; it is the operator's primary surface and terminal width is the real
constraint. Existing helpers `_one_line`, `_clip`, `_review_table` are there —
note `_one_line` maps C0 controls and DEL to spaces, which is what stops a
hostile `shown` spoofing this screen (D-095). Do not lose that.

**Stale ledgers must be obvious.** `claims.json` records `corpus_sha`; a ledger
whose sha no longer matches is *worse than absent*, because it looks like
verification. `review` must say so plainly rather than showing stale verdicts.

## The spec/code disagreement to fix — D-103

`claim_override` is a **mapping** in §8.4 (`reason`, `by`) and a **string** in the
code — `script.py` validates every shared field with `free_text`, so **§8.4's own
YAML example is refused at load.** Verify that yourself before changing anything;
if the code is already right, say so and stop.

The mapping is the right shape and it is load-bearing. §8.4: *passing verification
is automatic; bypassing it costs you a written sentence with your name on it.*
Both fields required and non-empty — an override with an empty `reason` is a
checkbox, which is the one thing §8.4 says it must never be.

**Scope discipline:** make the schema accept and carry it, and have `check`
report an overridden claim distinctly (neither a silent pass nor a failure).
**Phase 7's `approve` is what consumes it — do not build that gate here.**

## Rules, each with its negative half

- **R1** `check` verifies what is on disk. **Negative:** it takes identifiers, so
  there is no argument a caller can shape to skip the check (D-072, D-059).
- **R2** `check` exits non-zero when any claim is `fail`, `no_source`, or an
  unattested `manual`. **Negative:** a clean episode exits 0 and says so.
- **R3** `review` shows `quote` alongside `src`. **Negative:** it stays readable
  in a normal terminal — a wall of text is a different way of being unreadable.
- **R4** A ledger whose `corpus_sha` no longer matches is reported as **stale**.
  **Negative:** a matching ledger is shown normally, with no scary noise.
- **R5** `claim_override` is a mapping with non-empty `reason` and `by`.
  **Negative:** absent is fine and is the normal case.
- **R6** No network, no LLM, no new dependencies.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `check` accepts a caller-built `Script` | R1 |
| M2 | `check` exits 0 with a failing claim | R2 |
| M3 | `check` exits non-zero on a clean episode | R2 negative |
| M4 | unattested `manual` treated as a pass | R2 |
| M5 | `quote` shown for some types but not others | R3 |
| M6 | `quote` shown untruncated, breaking the table | R3 negative |
| M7 | stale ledger displayed as if current | R4 |
| M8 | every ledger reported stale | R4 negative |
| M9 | `claim_override` accepted as a bare string | R5 |
| M10 | `claim_override` accepted with empty `reason` or `by` | R5 |
| M11 | an overridden claim silently reported as `pass` | overrides |
| M12 | control characters reaching the terminal from a beat field | D-095 |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1` in any mutation sweep.** D-100: this suite is
  now fast enough that consecutive mutants land inside one mtime second and
  CPython reuses a stale `.pyc` — the harness then tests the *unmutated* module.
  It produced two false survivors last task, and the same mechanism produces
  false *kills*, which would inflate every score this project reports.
- **Pipe command output to a file and paste from it.**
- Code blocks and spec tables are authoritative; prose explains *why*. **If they
  disagree, follow the code block and flag it** — 24 brief defects across five
  phases against zero implementer errors.
- `CliRunner` has swallowed a crash in this project before (D-035): assert on
  exit codes *and* output, and check `result.exception`.
- All workspace writes through `workspace.atomic_write` (CLAUDE.md).
- **Agents must never run `agsoc approve` or `agsoc post`** — that includes you.
- **Report the mutation score.**

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — `agsoc video check`. Commit.
- [ ] **Step 3** — `review` shows `quote` and verdicts, with staleness. Commit.
- [ ] **Step 4** — `claim_override` (D-103), if the code is in fact wrong. Commit.
- [ ] **Step 5** — mutants plus your own sweep.
- [ ] **Step 6 — the whole phase, end to end, on the operator's real brief.**
      Build the episode from `workspace/inbox/2026-08-17-ai-brief.md`, ingest the
      sources, run `check`, then `review`. **Paste both screens verbatim.** I
      want to see what an operator actually sees — including, if you reproduce
      Task 2's fabricated-figure case, what the failure looks like on screen.
      That screen is the product.

---

## Your report

`docs/superpowers/worklog/video/phase-05/task-3-report.md`:

1. **What I implemented**, and the display decisions that were yours.
2. **TDD evidence**, the **mutation score**, all twelve mutants plus your sweep.
3. **Step 6's two screens**, pasted verbatim.
4. **Files changed**, all commit SHAs.
5. **Issues or concerns**, including:
   - **Is the failure screen actionable?** Put yourself in front of it knowing
     nothing about the codebase: does it tell you what to *do*? Task 2 measured a
     35% entity-atom miss rate that is deliberately not gated (D-102) — does the
     display make "recorded, not gated" clear, or does it read as a pass?
   - What is still missing before an operator could use this unsupervised?
   - Anything in Phase 5 you would not ship.

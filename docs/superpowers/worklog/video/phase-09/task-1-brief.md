# Task 1 Brief: the adversarial record, and the gate that reads it

**Phase:** 9 · **Branch:** `feat/video-phase-09-adversarial`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §8.1 (the record), §8.3 (pass 2), §8.4 (the gate)

Pass 1 compares numbers to bytes. **This task builds the place a judgement goes,
and makes the gate refuse on it.** The judging itself is Task 2's skill — the CLI
contains no LLM calls (CLAUDE.md), and that split is not negotiable here.

## Start from what already works

`classify()` **fails closed** (D-113). A verdict it does not recognise is `open`,
so a Phase 9 verdict written today already blocks approval. **The gate is safe
before this phase exists**, and your job is to make it *informative*, not to make
it safe.

That means: **extend `classify()`, do not fork it.** One function decides a
claim's status for `check`'s summary, `review`'s table and `approve`'s gate. Two
paths to one answer is the shape that published a draft in v1 (D-059, D-113), and
Phase 7 spent three tasks removing it.

## The record (§8.1)

```json
"adversarial": {
  "verdict": "supported",
  "attempted_refutation": "Checked whether the price applies to 3.7 Flash rather than 3.7 Pro; the source names Flash explicitly two sentences earlier. Checked whether pricing is promotional; no such qualifier appears.",
  "residual_risk": "Source does not state an effective date for the pricing."
}
```

Verdicts: `supported` · `unsupported` · `refuted`.

- **`residual_risk` is recorded even on `supported`** and surfaces in `review`.
  §8.3 calls it *often the most useful output of the whole pass*, and I agree:
  "the source does not state an effective date" is exactly what a human should
  read before signing.
- **`attempted_refutation` is not optional.** A `supported` with no account of
  what was attacked is a claim that someone looked, which is worth nothing. This
  project has caught itself four times printing a conclusion stronger than its
  evidence (D-106, D-110, D-112, D-118) — **this field is the evidence.**

## What this pass is for, and the honesty it requires

Pass 1 is mechanical, deterministic, and re-runnable in a year with the same
answer. **Pass 2 is none of those things.**

So the ledger must **say so plainly**. A `checked_at` on a pass-2 verdict means
something much weaker than on a mechanical one, and a reader who does not know
that will trust them equally. Design the record so the difference is visible
without reading the spec.

**Decide and argue: what invalidates a pass-2 verdict?** A changed script,
certainly — the drift machinery from D-114 already exists. A changed corpus? A
better model six months from now? There is no honest answer that does not involve
some notion of expiry, and pretending otherwise is how a stale `supported` gets
signed.

## Rules, each with its negative half

- **R1** `unsupported` and `refuted` refuse at the gate, **distinguishably** from
  a pass-1 `fail`. **Negative:** `supported` does not block.
- **R2** `residual_risk` surfaces in `review` **even on `supported`**.
  **Negative:** an absent `residual_risk` is normal and silent, not an error.
- **R3** A record with `adversarial` present but malformed is **`open`**, never
  passing. **Negative:** a claim with no `adversarial` block at all is *not yet
  judged* — distinguishable from one judged badly.
- **R4** One `classify()`. **Negative:** no second verdict path anywhere.
- **R5** A pass-2 verdict is bound to the claim it judged — a changed script makes
  it stale, exactly as it does the ledger.
- **R6** No LLM call, no network, in the CLI or its tests.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `refuted` approves | R1 |
| M2 | `unsupported` approves | R1 |
| M3 | pass-2 refusal indistinguishable from pass-1 `fail` | R1 negative |
| M4 | `supported` blocks | R1 negative |
| M5 | `residual_risk` shown only on failures | R2 |
| M6 | a missing `residual_risk` treated as an error | R2 negative |
| M7 | malformed `adversarial` treated as `supported` | R3 |
| M8 | "not yet judged" collapsed into "judged and open" | R3 negative |
| M9 | a second verdict path added | R4 |
| M10 | a pass-2 verdict survives a script edit | R5 |
| M11 | `attempted_refutation` optional or allowed empty | evidence |
| M12 | the ledger presents pass-1 and pass-2 as equally durable | honesty |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1`** in any mutation sweep, and **paste the harness
  output** — D-118: a claimed 26/26 with no log behind it re-measured at 23/26.
  **A mutation score is a measurement, not a claim.**
- **Assert on the line you mean**, not on a substring that appears anywhere in the
  screen. D-118's survivor was a test reading the *diagnosis* and calling it the
  *remedy*.
- **Never quote a piped exit code** (D-105).
- `CliRunner` has swallowed a crash here (D-035): assert exit code **and** output
  **and** `result.exception`.
- **Run `approve` only against a throwaway workspace you create**; `workspace/`
  holds three real operator episodes that stay unapproved and unedited. Verify
  your backup path does not already exist.
- All workspace writes via `workspace.atomic_write`. No new dependencies.
- **Report the mutation score, with evidence.**

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — the record and `classify()`'s extension. Commit.
- [ ] **Step 3** — `approve`'s refusals and `review`'s `residual_risk`. Commit.
- [ ] **Step 4** — staleness binding (R5). Commit.
- [ ] **Step 5** — mutants plus your own sweep.
- [ ] **Step 6** — end to end in a throwaway workspace: hand-write a `refuted`
      verdict into a ledger, show `approve` refusing and naming it; then
      `supported` with a `residual_risk`, and show it in `review`. **Paste both.**

---

## Your report

`docs/superpowers/worklog/video/phase-09/task-1-report.md`:

1. **Your expiry decision**, argued.
2. **How a reader can tell a pass-2 verdict from a pass-1 one** without the spec.
3. **TDD evidence**, the **mutation score with harness output**, all twelve
   mutants plus your sweep.
4. **Step 6's two screens**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What can a refuter be told that would corrupt it?** You are building the
     record; Task 2 builds the prompt. Name what must never reach it, so Task 2
     inherits the constraint rather than rediscovering it.

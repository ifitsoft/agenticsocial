# Task 2 Brief: overrides applied, and drift that names itself

**Phase:** 7 · **Branch:** `feat/video-phase-07-approve` · **Follows:** Task 1
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §8.4 (the override), §10 (drift)

Task 1 built the gate. Two things finish the phase: **an override that actually
clears a claim**, and **an approval bound to the bytes it approved.**

Task 1's own report flags the first as a promise the CLI is already making:
`check` tells the operator *"approve is what reads an override"* — and today
nothing does.

## Part A — the override

§8.4's design, and the asymmetry is the whole point:

> *Passing verification is automatic; bypassing it costs you a written sentence
> with your name on it.*

`claim_override` is a mapping of `reason` + `by`, both required and non-blank
(D-103), already accepted by the schema. **This task makes it clear a claim.**

- It clears **exactly the claim it names** — never a beat, never an episode.
- It is a **visible diff in a file you commit** — never a flag, never a prompt.
- An overridden claim is **not** `verified`. It is its own state, and it must
  read that way everywhere `classify()` is consumed. Task 1 built `classify()` as
  the single source of that answer; **extend it, do not add a second path** —
  two paths to one answer is D-059's shape.
- **Track the override rate.** D-040: a high rate means the checker is wrong, not
  the operator. Report it somewhere a person will see.

Decide and argue: **does an override on a claim that now passes anyway warn?** A
stale override is a written sentence about a problem that no longer exists, and
leaving it silently is how the sentence stops meaning anything.

## Part B — drift

§10 is explicit, and stricter than the text pipeline on purpose — *a render is
expensive and a video is harder to retract*:

> `approve` records `script_sha256`, and `render` refuses if the script has
> changed since approval, **naming the drift**.

Task 1 records the digest over the **beats document**, not the whole file,
because the approval record is written into the file it would otherwise hash —
there is no fixed point. Keep that; it is correct and it is subtle enough that
the next reader needs the reason in a comment.

**The case this must catch is the one Phase 5 named:** editing a chart's `scale`
shifts every bar while every claim still verifies and no number anywhere is
wrong. `corpus_sha` cannot see it. A numeric check cannot see it. **Only the
digest can.**

Task 1 also flagged a real trap: **`plan.json`'s `script_sha256` is the
whole-file digest — one key, two meanings** (D-036). Fix it or rename one of
them. A key that means different things in two files is a bug waiting for
someone to compare them.

`render` does not exist until Phase 8. **Build the refusal as a reusable check
with its own tests**, and wire Phase 8's `render` into it there — do not stub a
command.

## Rules, each with its negative half

- **R1** An override clears exactly the claim it names. **Negative:** every other
  open claim on the same beat still blocks.
- **R2** An override requires non-blank `reason` and `by`. **Negative:** absent is
  normal and silent.
- **R3** An overridden claim is distinguishable from a verified one everywhere.
  **Negative:** it does not block approval.
- **R4** Editing the script after approval is detected and **named**.
  **Negative:** re-approving after an intentional edit is possible — drift is not
  a trap you cannot escape.
- **R5** An edit that changes **no number** (the `scale` case) is still caught.
- **R6** One `classify()`. **Negative:** no second verdict path anywhere.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | override clears the whole beat | R1 |
| M2 | override clears the episode | R1 |
| M3 | blank `reason` or `by` accepted | R2 |
| M4 | overridden claim reported as `verified` | R3 |
| M5 | overridden claim still blocks | R3 negative |
| M6 | drift undetected | R4 |
| M7 | drift detected but not named | R4 |
| M8 | `scale`-only edit undetected | R5 |
| M9 | digest taken over the whole file | R5 / fixed point |
| M10 | a second verdict path added | R6 |
| M11 | override rate not reported | D-040 |
| M12 | re-approval after an edit impossible | R4 negative |

## Ground rules

- **Commits: tests first, then implementation**, Part A and Part B separate.
- **`PYTHONDONTWRITEBYTECODE=1`** in any mutation sweep (D-100).
- **Never quote a piped exit code** (D-105).
- `CliRunner` has swallowed a crash here (D-035): assert exit code **and** output
  **and** `result.exception`.
- **Run `approve` only against a throwaway workspace you create.** Never against
  `workspace/` — three real episodes live there and approving them is the
  operator's decision. Back it up; **verify the backup is not nested inside an
  older one**, which cost Task 1 a confusing diff.
- All workspace writes via `workspace.atomic_write`.
- No new dependencies, no network, no LLM.
- **Report the mutation score.**

---

- [ ] **Step 1** — tests for Part A. Failing. Commit.
- [ ] **Step 2** — the override. Commit.
- [ ] **Step 3** — tests for Part B, including the `scale`-only edit. Failing.
      Commit.
- [ ] **Step 4** — the digest and the drift check. Commit.
- [ ] **Step 5** — mutants plus your own sweep.
- [ ] **Step 6** — end to end in a throwaway workspace: a failing claim blocks;
      an override with a reason clears it; editing `scale` after approval is
      caught and named. **Paste all three screens.**

---

## Your report

`docs/superpowers/worklog/video/phase-07/task-2-report.md`:

1. **Your stale-override decision**, argued.
2. **The `script_sha256` two-meanings fix**, and which name you kept.
3. **TDD evidence**, the **mutation score**, all twelve mutants plus your sweep.
4. **Step 6's three screens**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What edit still slips past the digest?** Something outside the beats
     document, a corpus change, a `series.toml` design change that repaints every
     frame. Name what an approval does *not* cover.
   - Is the override screen honest — could an operator mistake an overridden
     episode for a clean one?

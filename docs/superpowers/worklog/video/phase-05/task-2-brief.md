# Task 2 Brief: The mechanical pass and the ledger

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier` · **Follows:** `3c039ac`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §8.1 (the record), §8.2 (pass 1), §8.2.1 (folding), §8.4 (the gate)

Task 1 built extraction and it survived real prose. **This task makes the
sentence true**: every claim a beat makes is checked against bytes on disk.

## Read D-098 before you design anything

Your predecessor found that **the spec's own §7 example fails**, and I verified
it. §8.2 used to say comparison is on "normalised digit sequences". That is the
defect, not the beat:

```
quote: "priced at $0.75 per million input tokens and $3.75 per million output"
  1M    -> digits '1'      present? NO   (the source spells the magnitude)
  2.00  -> digits '2.00'   present? NO   (display formatting reaches the compare)
  95B   -> against "95 billion"          NO
```

The third one is the argument: **`95B` versus "95 billion" is precisely the case
§8.2.2's unit-suffix rule exists to protect**, and a substring test fails it.

**Comparison is numeric.** Parse candidates out of the folded quote with the same
§8.2.2 rule, expand magnitude suffixes (`K M B T`) and spelled magnitudes
(thousand/million/billion/trillion) on **both** sides, compare values. The spec
is already amended; §8.2 point 2 is authoritative.

This is not a relaxation and you should be able to demonstrate that it isn't:
`95B` = 95e9 ≠ 9e9 = `9B` is a distinction substring matching **cannot make at
all**. Trailing zeros and thousands separators stop causing refusals; `75 cents`
against `0.75` still fails.

## The three checks

1. **Quote presence** — `quote` occurs in `sources/<src>.txt` after folding
   (§8.2.1). Record the span in the **original** text, not the folded one; the UI
   highlights the real bytes. Folding changes lengths (`…` → `...`), so a span
   computed on folded text and applied to the original is a live bug — pin it.
2. **Numeric containment** — above.
3. **Entity presence** — every entity atom appears in `quote` or elsewhere in
   the source document.

**Task 1 was honest that entity atoms are not an implementation of §8.2 step 3**:
the orthographic rule over-generates (~1/3 of 75 atoms on the real brief), glues
multi-entity runs together, and misses lowercase names like `cline` entirely.
**Do not let that failure mode reach a `fail` verdict.** An entity miss should be
distinguishable and weaker than a numeric miss — a wrong number is fabrication, a
missed proper noun is usually our tokeniser. Decide the shape and defend it.

## Verdicts, and the one that matters

`pass` · `fail` · `no_source` · `manual`.

- `custom` → always `manual`, with its `attest` recorded (D-088). **Never
  `pass`.**
- A beat asserting something with no `src` → `no_source`, distinguishable from
  `fail`. "I checked and it's wrong" and "there was nothing to check against" are
  different sentences and an operator acts differently on each.
- `title`/`signoff` are exempt (§8.2).

**Near-misses report with the closest candidate span attached** (§8.2), so the
operator sees *why*. A bare red mark is what teaches people to override.

## `claims.json`

Per §8.1, including **`corpus_sha`** so a check is invalidated when the corpus
changes. Write through `workspace.atomic_write` — never `write_text` (CLAUDE.md).
`script.yaml` is never written by this phase.

**Two spec defects Task 1 flagged in §8.1's example record, neither
load-bearing:** `id: c-014` paired with `beat_index: 7` is unreachable under any
one-claim-per-beat scheme, and the example `text` is fluent prose no mechanical
walk produces. Follow the field *shape*; do not reproduce the example's values.

## The `shown` check — new, and cheap

D-085 called `jumpChart.shown` unverifiable by design. **Phase 4 changed that**
(D-094): it is now a closed vocabulary, and its digits sit in the same mapping as
the row's own `before`/`after`.

So: **`shown`'s claim numbers must agree with its own row's values.** `shown:
"…&rarr; 91.7"` on a row drawing `43.6` states a figure the bar does not draw.
No corpus needed — an internal consistency check on one mapping, and it retires
the last route by which a chart asserts a number nothing verifies.

D-081 still holds: `shown` is where the frame and script legitimately differ.
This is the narrower guarantee underneath that, not a retreat from it.

## Rules, each with its negative half

- **R1** A claim number absent from its quote **fails**, naming the claim.
  **Negative:** a magnitude written differently on the two sides (`1M` /
  "1 million" / `1,000,000`) **passes** — that is D-098's whole point.
- **R2** A quote absent from the corpus fails **distinguishably** from a number
  miss. **Negative:** folding differences are never the reason — `V4‑Pro` with
  U+2011 matches `V4-Pro`.
- **R3** `corpus_sha` is recorded and a changed corpus invalidates the check.
  **Negative:** re-running on an unchanged corpus is stable — no timestamp or
  ordering churn that makes `claims.json` a noisy diff.
- **R4** `custom` lands `manual` with `attest`. **Negative:** no other type does.
- **R5** `shown`'s numbers agree with the row's `before`/`after`. **Negative:** a
  `shown` carrying no digits (`<s>up</s> &rarr; down`) is fine.
- **R6** No network, no LLM, no new dependencies.

## The mutants this task must kill

Derive assertions from these **before** implementing (D-064).

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | substring comparison instead of value comparison | R1 negative (`1M`) |
| M2 | value comparison so loose `9B` matches `95B` | R1 |
| M3 | `2.00` vs `2` refused | R1 negative |
| M4 | `75 cents` accepted for `0.75` | R1 |
| M5 | span computed on folded text, returned as an original offset | quote highlighting |
| M6 | folding skipped on the corpus side only | R2 negative |
| M7 | `no_source` collapsed into `fail` | verdicts |
| M8 | `custom` can reach `pass` | R4 |
| M9 | `attest` not recorded | R4 |
| M10 | `corpus_sha` absent, or not covering the documents actually read | R3 |
| M11 | `claims.json` re-ordered or re-timestamped on an unchanged re-run | R3 negative |
| M12 | `shown` digits unchecked | R5 |
| M13 | a `shown` with no digits refused | R5 negative |
| M14 | an entity miss produces the same verdict as a number miss | entities |
| M15 | `title`/`signoff` verified rather than exempt | §8.2 |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks and spec tables are authoritative; prose explains *why*. **If they
  disagree, follow the code block and flag it.** 24 brief defects across five
  phases against zero implementer errors — and the most recent was an explicit
  instruction *not* to test something that turned out to be broken. Testing
  anyway was correct and I want that repeated.
- **Include falsy values.** Task 1's own sweep found two real gaps, both `0`.
- **State a `precondition:` per test** (D-035): what must be true for this test to
  be *capable* of failing. Ask of each: *what would it do if the code did
  nothing?*
- No network (conftest guards sockets and the `research` seam), no LLM, suite
  stays fast.
- **Report the mutation score.**

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — `src/agenticsocial/video/verify.py`: fold-aware quote
      presence with original-text spans, value-based numeric containment, entity
      presence, verdicts. Commit.
- [ ] **Step 3** — `claims.json` per §8.1 with `corpus_sha`, atomic. Commit.
- [ ] **Step 4** — the `shown` consistency check. Commit.
- [ ] **Step 5** — mutants plus your own sweep.
- [ ] **Step 6 — measure the false-refusal rate, and report it as a number.**
      Run against (a) the spec's §7 example beat and (b) beats built from
      `workspace/inbox/2026-08-17-ai-brief.md`. **Both must verify clean.** If
      anything is refused, paste it and say whether the checker or the beat is
      wrong. This is the phase's health signal: D-040's failure mode is a gate so
      strict operators override reflexively, and *a high override rate means the
      checker is wrong, not the operator.*

---

## Your report

`docs/superpowers/worklog/video/phase-05/task-2-report.md`:

1. **What I implemented**, and the value-comparison design specifically.
2. **Proof the value comparison is stricter, not looser** than substring — show
   a case it catches that substring cannot.
3. **TDD evidence**, the **mutation score**, all fifteen mutants plus your sweep.
4. **Step 6's numbers**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What can still ship a wrong number?** Name a concrete beat that passes
     pass 1 and is false. Pass 2 (Phase 9) exists for these — a good list here is
     that phase's specification, so this is a contribution, not an admission.
   - Your entity-presence decision and its error rate in both directions.
   - The override rate you would expect an operator to hit in a month.

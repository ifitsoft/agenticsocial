# Task 3 Brief: self-contained beats, and the fifth overclaim

**Phase:** 9 · **Branch:** `feat/video-phase-09-adversarial` · **Follows:** Task 2
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Task 2 ran five real claims through blind refuters. **Four came back
`unsupported`, every one citing a missing subject.** The single card that names
its own subject is the only one that survived.

That is an **80% refusal rate on content that is not wrong** — and D-040's
failure mode arriving in pass 2, one phase after D-102 refused to gate entity
presence for exactly this arithmetic (62% would have made the gate theatre).

## The decision, which is mine and which I want implemented

**Beats must be self-contained.** A card asserting "raised prices by up to
1,100%" without naming DeepSeek is refused, and the fix is the beat, not the
checker.

I considered and rejected the two alternatives:

- **Give the refuter its neighbouring beats.** This destroys the pass. Task 1
  §6.1 item 2 and Task 2's four reproductions are the *same finding* twice: a
  refuter that can see the sibling supplies the missing subject and supports the
  claim. Task 2's skill already forbids widening the prompt and calls it "the
  wrong response that feels like debugging" — it is right.
- **Accept the refusal rate and let overrides carry it.** That is precisely how a
  gate becomes theatre. A 4-in-5 refusal rate on correct work teaches an operator
  to override everything, including the true refusal in the same run.

**The rule pays for itself twice.** A viewer scrubbing a vertical video does not
watch it in order, and a card that does not name its subject is weaker
journalism regardless of what any checker thinks. The cost is a few words per
card. **The honest fix here happens to be the better artifact**, which is the
strongest kind of resolution available and the reason I am not treating this as a
verification-tuning problem.

## What to change

**`skills/storyboard/SKILL.md`:** every beat that asserts something names its
subject in its own text. Give the rule, the reason, and a worked before/after
from the real episode — `2026-08-17c`'s `c-005`, `c-007`, `c-010`, `c-019` are
four ready-made examples. Say it where an author writes the beat, not in a
appendix.

**`skills/verify/SKILL.md`:** a paragraph saying that a wall of "missing subject"
`unsupported` verdicts means the *script* needs rewriting, and pointing at the
storyboard rule. Task 2 predicted the blind runner will widen the prompt when it
sees that wall; the skill should meet that instinct with an explanation.

## The fifth overclaim — fix it

`review`'s claim summary prints **pass 1's verdict over a pass-2 refusal**:
`claims 24 pass` and `! c-005 · beat 4 · pass`, while `c-005` is `unsupported`.
Task 1 converted `_claim_cell`; `_counts` and `_print_claim_summary`'s head line
were **not**.

This is the **fifth** instance of the shape (D-106, D-110, D-112, D-118, and
this) and the second time *in one phase* that a summary disagreed with the table
under it. `classify()` exists precisely so this cannot happen — **route every
count and every head line through it**, and add a test that pins summary and
table to the same source. A partially-converted call site is worse than an
unconverted one, because the screen looks updated.

## The money bug

`--refutation "$1.32"` records `.32` — the shell eats it, and **the verdict looks
completely normal**. Task 2's skill mandates `--refutation "$(cat file)"`, which
is a documentation fix for a data-loss bug.

Decide whether the CLI should defend itself. A refutation that silently loses
`$1.32` is a claim record that misquotes its own evidence, and this project has
a rule about tools that say more than they know.

## Rules, each with its negative half

- **R1** A summary count never disagrees with the table beneath it.
  **Negative:** the two are derived from one function, not kept in sync by care.
- **R2** The storyboard skill requires self-contained asserting beats.
  **Negative:** `title` and `signoff` assert nothing and are exempt.
- **R3** A refutation reaches the ledger byte-exact. **Negative:** whatever you
  do about quoting, `$`, backticks and apostrophes survive.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `_counts` still reports pass-1 verdicts | R1 |
| M2 | head line converted, table left behind | R1 |
| M3 | summary and table kept in sync by two code paths | R1 negative |
| M4 | a refutation loses `$1.32` silently | R3 |
| M5 | the storyboard rule stated but with no worked example | R2 |

## Ground rules

- **Commits: tests first, then implementation**; skill changes separate from code.
- **`PYTHONDONTWRITEBYTECODE=1`, and paste the harness output** (D-118).
- **Assert on the line you mean**, not a substring appearing anywhere on screen.
- **Never quote a piped exit code** (D-105).
- **If you modify `workspace/`, back it up first**, verify the path does not
  already exist, and restore it. Three real episodes; unapproved, unedited.
- No new dependencies, no network, no LLM in the CLI.

---

- [ ] **Step 1** — failing tests for R1 and R3. Commit.
- [ ] **Step 2** — route every count through `classify()`. Commit.
- [ ] **Step 3** — the refutation quoting decision. Commit.
- [ ] **Step 4** — both skills. Commit.
- [ ] **Step 5** — mutants, and re-run `review` on `2026-08-17c` to show the
      summary and table agreeing. **Paste it.**

---

## Your report

`docs/superpowers/worklog/video/phase-09/task-3-report.md`:

1. **The `_counts` fix**, and how you proved no other call site is half-converted.
   **Go looking for a sixth** — five instances is a pattern, not a coincidence.
2. **Your refutation-quoting decision**, argued.
3. **The storyboard before/after**, pasted.
4. **TDD evidence**, the **mutation score with harness output**.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns.**

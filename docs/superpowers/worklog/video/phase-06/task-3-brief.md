# Task 3 Brief: the coverage check clears stories it should catch

**Phase:** 6 · **Branch:** `feat/video-phase-06-storyboard`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Both blind runs passed — 22/22 and 24/24 claims on their first `check`, zero
overrides, both runtimes dead on 120.0s. Phase 6's exit criterion is met twice by
two different agents.

**This task fixes the one thing that is dangerous, plus the two places the skill
is wrong.**

## The defect

Leader-verified:

```
node engine/coverage.mjs check gemini-3.7   ->  "NOT COVERED. Safe to run as new."
node engine/coverage.mjs check gemini       ->  4 prior mention(s)
```

The second blind runner passed `gemini-3.7`, got a clean bill, and **cleared the
brief's headline story — which this series ran three days earlier as its own
headline.** It was caught only because the runner independently re-ran bare
vendor terms and read the titles.

CLAUDE.md states the invariant plainly: *the series must never re-tell a story as
if it were new.* This is that invariant failing, silently, **in the safe-looking
direction.**

Two things make it worse:

- **The ledger stores product names with spaces** (`gemini 3.7 flash`) and the
  check is a substring match, so **every hyphenated product term is a possible
  false negative** — and hyphenated is exactly how an author writes a product.
- **The message asserts a conclusion the match cannot support.** "NOT COVERED.
  Safe to run as new" is a claim about the world; a substring miss only supports
  "this string does not appear". Same class as the comment in `verify.py` that
  stated a guarantee the code did not provide (D-106).

## What to do

Fix `engine/coverage.mjs` so a hyphenated product term cannot silently miss a
spaced ledger entry. Tokenise both sides and match on tokens, or normalise
separators before comparing — your call, argued.

**And fix the message.** A miss should say what was searched and what that does
and does not prove. A tool that says "safe" must be right about it, or it should
not use the word.

**Add tests.** `engine/` has node test files (`determinism.test.mjs`,
`network.test.mjs`) — follow that pattern. `coverage.mjs` has none today, which
is why this survived. Include the exact case above as a regression test.

## The two places the skill is wrong

Both from the second blind run, both verifiable in one minute:

1. **The beat arithmetic does not reconcile.** "22–26 beats, laid out as two
   cold-open beats + four acts of 4–6 beats + one signoff" yields **19–27**, not
   22–26. Neither endpoint matches, so the two numbers cannot both be the
   constraint. Make them agree.
2. **`agsoc video new`'s `next:` hint is `--research`**, which is the wrong ingest
   mode for the workflow the skill describes (a brief handed over as a file, i.e.
   `--paste`). The skill says "the hint is correct" — it is correct about
   `--series` and wrong as an instruction. Either fix the hint in the CLI to match
   the documented workflow, or stop telling the author to trust it.

## Also worth closing, cheap

- **Quote extraction does not scale.** Step 3.5 prescribes a manual
  `t.index(...)` + `repr()` loop *per quote* — 24 round trips, each an
  opportunity to retype. Both runners independently wrote a script instead, and
  that is what made both first checks green. **Describe the script.** A rule
  whose compliant path is 24 manual steps will be routed around.
- **Claim id numbering skips** (`c-001`, `c-003`, …) because `title` consumes an
  id and emits no row. Both runners noticed; one read it as a lost claim. Either
  do not consume ids for unextracted beats, or say so in the display.
- **The episode-id date is ambiguous** when the clock rolls past the brief's date
  mid-run. Say whether the id tracks the brief or today.
- **`title.sub` is not verified.** Say whether it must still be defensible.

## Rules, each with its negative half

- **R1** A hyphenated product term finds a spaced ledger entry. **Negative:** a
  genuinely new story still reports NOT COVERED — do not make everything match.
- **R2** The coverage message never claims more than the search supports.
  **Negative:** a real hit still reads as an unambiguous stop.
- **R3** `coverage.mjs` has tests. **Negative:** they run under `node`, with no
  new dependency.
- **R4** The skill's beat arithmetic is internally consistent.
- **R5** Every command the skill tells an author to trust behaves as described.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `gemini-3.7` still clears | R1 |
| M2 | matching so loose every term hits | R1 negative |
| M3 | message still says "safe" on a miss | R2 |
| M4 | a real hit softened into a maybe | R2 negative |
| M5 | tests assert only the happy path | R3 |
| M6 | beat arithmetic still yields 19–27 | R4 |
| M7 | skill still says the `next:` hint is correct | R5 |

## Ground rules

- **Commits: tests first, then implementation**; skill changes separate from code.
- **Never quote a piped exit code** (D-105).
- **`PYTHONDONTWRITEBYTECODE=1`** in any Python mutation sweep (D-100).
- **`workspace/` now holds three episodes** — `2026-08-17`, `-17b`, `-17c`. Back
  it up before touching it and **leave all three**; all three must still pass
  `check`.
- `engine/coverage.json` is the real series ledger. **Do not rewrite its
  contents** to make a test pass — fixtures go in a temp file.
- No new dependencies, no network, no LLM.
- **Report the mutation score.**

---

- [ ] **Step 1** — a failing test for `gemini-3.7`. Commit.
- [ ] **Step 2** — the matcher and the message. Commit.
- [ ] **Step 3** — the skill fixes. Commit.
- [ ] **Step 4** — mutants, all three episodes re-checked, full pytest, both node
      suites.

---

## Your report

`docs/superpowers/worklog/video/phase-06/task-3-report.md`:

1. **The matching rule you chose**, and the false-positive cost of it.
2. **Before/after on the real ledger** for `gemini-3.7`, `gemini`, `v4-pro`,
   `deepseek`, pasted.
3. **TDD evidence** and the **mutation score**.
4. **All three episodes' `check` results.**
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What else in this pipeline says something stronger than it knows?** The
     coverage message and a `verify.py` comment have both now been caught doing
     it. Look for a third.

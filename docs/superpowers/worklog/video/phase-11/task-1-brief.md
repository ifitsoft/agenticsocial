# Task 1 Brief: `agsoc coverage` — relocation, and a scoping change that can lose history

**Phase:** 11 · **Branch:** `feat/video-phase-11-coverage`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §6 (pipeline), §11 (coverage)

## This is not a file move

`engine/coverage.json` is **one ledger, shared by every series**, sitting in a
working directory. The product model is per-series: each series tells its own
stories and must not re-tell them. **Two series sharing one ledger means one
series' history suppresses another's stories.**

So this is a relocation **plus a scoping change**, and the scoping change is the
part that can lose data. A migration that silently drops an entry is worse than
no migration at all, because the failure mode is *a story re-told as new* — the
exact thing the ledger exists to prevent.

## What must survive the port, deliberately

D-112 fixed a defect where `gemini-3.7` reported *"NOT COVERED. Safe to run as
new"* over three prior stories, and **a blind runner cleared the brief's headline
story — one the series had run three days earlier.** Two properties of that fix
are load-bearing:

1. **The matcher is one-directional.** It strips non-alphanumerics from both
   sides, so it can only ever *add* matches, never drop one. That property is
   what made it safe to change quickly, and it is what you must not lose in a
   reimplementation. Its cost is false positives (`aiact` finds *EU AI Act*),
   which is the correct direction to be wrong in.
2. **The message never says "safe".** It names what was searched and states the
   bound — *the ledger holds only what a person wrote into it after an episode
   shipped.* A substring miss supports "this string does not appear", nothing
   more.

**`engine/coverage.test.mjs` exists because the tool had no tests at all**, which
is precisely why a tool that said "safe" was never asked whether it was.
**Port the tests, or the guarantee does not move** — porting the behaviour alone
leaves you with the same untested tool in a new language.

## The tasks, in one

**`agsoc coverage check <terms…>`** — per-series, behaviour-identical.
**`agsoc coverage add <ep>`** — records after render (§6).
**Migration** — move existing entries into the series that produced them, with
**proof** nothing was lost.
**Retirement** — `engine/coverage.mjs` goes the way Phase 8 retired the
hand-written render path: **the command goes, the data survives.**

`skills/storyboard/SKILL.md` names today's spelling in a bracket **precisely so
this phase changes the bracket and nothing else** (D-109). Change it, and verify
the new command by running it — the CLI's own `next:` hint was wrong once, and an
author trusts the tool over the doc.

## Decide these; do not default

- **What is a "story"?** §6 says `add` records stories after render. The beat
  text? The entities? An operator-supplied list? **This decides whether `check`
  works at all in six months**, because it decides what is in the ledger to
  match against.
- **Who writes it — the operator or the pipeline?** An automatic `add` after
  render records what was *rendered*, not what was *published*, and those differ
  the moment a render is discarded.
- **What does `check` do across series?** Silence is a defensible answer; so is
  *"this ran in another series three days ago"*. Pick one and say why.

## Rules, each with its negative half

- **R1** `check` is one-directional: a hyphenated term finds a spaced entry.
  **Negative:** a genuinely new story still reports not covered — do not make
  everything match.
- **R2** The message never claims more than the search supports. **Negative:** a
  real hit still reads as an unambiguous stop.
- **R3** Coverage is per-series. **Negative:** migration puts every existing
  entry in the series that produced it, and **loses none**.
- **R4** The node command retires; its tests' guarantees live on in Python.
- **R5** `add` records after render. **Negative:** it does not run itself as a
  side effect of `render` unless you decide it should — and if it does, say so.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `gemini-3.7` misses a spaced entry again | R1 |
| M2 | matching so loose everything hits | R1 negative |
| M3 | the word "safe" returns | R2 |
| M4 | a real hit softened into a maybe | R2 negative |
| M5 | migration drops an entry | R3 |
| M6 | migration duplicates an entry into every series | R3 |
| M7 | ported behaviour, unported tests | R4 |
| M8 | `add` writes an entry `check` cannot then find | R1/R5 — **the round trip** |

**M8 is the one I most expect to be got wrong.** `add` and `check` must agree
about normalisation, or the ledger fills with entries the checker cannot see —
and that failure is invisible until a story is re-told.

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1`, and paste the harness output** (D-118).
- **Never quote a piped exit code** (D-105).
- **`engine/coverage.json` is real history.** Back it up; **migrate, do not
  regenerate**; prove the entry count and content survive.
- **If you modify `workspace/`, back it up first**, verify the path does not
  already exist, and restore it. Three real episodes, unapproved and unedited.
- All workspace writes via `workspace.atomic_write`.
- No new dependencies, no network.

---

- [ ] **Step 1** — port the node tests to Python, failing. Commit.
- [ ] **Step 2** — `coverage check`. Commit.
- [ ] **Step 3** — `coverage add`, and the round trip (M8). Commit.
- [ ] **Step 4** — migration with proof. Commit.
- [ ] **Step 5** — retire the node command; update the skill. Commit.
- [ ] **Step 6** — mutants, and **run the real check**: `gemini-3.7`, `gemini`,
      `v4-pro`, `deepseek` against the migrated ledger. **Paste it**, and paste
      the before/after entry counts.

---

## Your report

`docs/superpowers/worklog/video/phase-11/task-1-report.md`:

1. **Your three decisions** (what a story is, who writes, cross-series), argued.
2. **Migration proof** — entry counts and a content diff.
3. **TDD evidence**, the **mutation score with harness output**.
4. **Step 6's output**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What can now be re-told as new?** Be concrete. The ledger's whole purpose
     is one guarantee, and this phase is the one that could quietly weaken it.

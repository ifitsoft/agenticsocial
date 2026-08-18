# Phase 11 — The coverage ledger

**Goal:** Coverage moves from `engine/` to the series, and `agsoc coverage
check/add` exists as §6 specifies.

**Spec:** §6 (pipeline), §11 (coverage) · **Roadmap:** §5
**Branch:** `feat/video-phase-11-coverage` · **Depends on:** 1 — merged.

## Why this is not a move

`engine/coverage.json` is a **single ledger in a gitignored-adjacent working
directory**, shared by every series. The product model is per-series: each series
tells its own stories and must not re-tell them. Two series sharing one ledger
means one series' history suppresses another's stories.

So this is a **relocation plus a scoping change**, and the scoping change is the
part that can lose data.

## What this phase inherits, and must not undo

**D-112.** The check used to be a raw substring match against a ledger that
stores product names with spaces, so `gemini-3.7` reported *"NOT COVERED. Safe to
run as new"* over three prior stories — and a blind runner cleared the brief's
headline story, which the series had run three days earlier.

The fix has two properties worth preserving deliberately:

1. **The matcher is one-directional** — it strips non-alphanumerics from both
   sides, so it can only *add* matches, never drop one. That is what made it safe
   to change quickly.
2. **The message never says "safe".** It names what was searched and states the
   bound: *the ledger holds only what a person wrote into it after an episode
   shipped.*

`engine/coverage.test.mjs` exists because the tool had **no tests at all**, which
is why a tool that said "safe" was never asked whether it was. **Those tests move
too, or the guarantee does not.**

## Global constraints

- **`agsoc coverage check` must not lose the one-directional property** when it
  is reimplemented in Python. Port the behaviour *and* the tests.
- `skills/storyboard/SKILL.md` names today's spelling in a bracket precisely so
  this phase changes the bracket and nothing else (D-109). **Change it.**
- `coverage.json`'s existing entries are real history. **Migrate, do not
  regenerate** — and a migration that silently drops an entry is worse than no
  migration, because the failure is a story re-told as new.
- All workspace writes via `workspace.atomic_write`.

## Tasks

**Task 1 — `agsoc coverage check`**, per-series, behaviour-identical to the node
version including the one-directional match and the honest message. Port the
tests.

**Task 2 — `agsoc coverage add <ep>`**, recording after render (§6). Decide what
it records: §6 says "record stories after render", and *what a story is* is the
question — the beat text? the entities? an operator-supplied list?

**Task 3 — migration and retirement.** Move the existing ledger into the series
that actually produced those episodes, prove nothing was lost, and retire
`engine/coverage.mjs` the way Phase 8 retired the hand-written render path: the
**command** goes, the **data** survives.

## Open questions to decide, not default

- **Who writes the ledger — the operator or the pipeline?** `add` after render is
  automatic; an automatic ledger records what was *rendered*, not what was
  *published*, and those differ when a render is discarded.
- **What does `check` do across series?** Silence is a real answer, but so is
  "this story ran in another series three days ago".

## Exit criteria

- [ ] `agsoc coverage check <terms>` exists, per-series, one-directional.
- [ ] The honest message survives the port — nothing says "safe".
- [ ] `agsoc coverage add <ep>` records after render.
- [ ] Existing entries migrated with **proof** nothing was dropped.
- [ ] `skills/storyboard/SKILL.md` updated to the new spelling.
- [ ] The node command retires; its tests' guarantees live on in Python.

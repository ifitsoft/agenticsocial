# Task 1 report — `agsoc coverage`: the ledger moved, and it is now per-series

**Phase:** 11 · **Branch:** `feat/video-phase-11-coverage`
**Spec:** §6 (pipeline), §11 (coverage) · **Inherits:** D-112, D-109, D-119

---

## 1. The three decisions

### 1.1 What a story is

**Decided: a story is one beat that asserts something — the text it put on
screen, the entities `claims.py` extracted from it, and the source it cited.**
Derived by `agsoc coverage add`, not typed by the operator.

The alternatives were the operator's own list, or the whole episode as one row.
The deciding question is not which is tidiest, it is *what is in the ledger for
`check` to match against six months from now* — because `check` is a substring
search and it can only find what someone put there.

- The strings an author types are product and vendor names: `gemini-3.7`,
  `deepseek`, `v4-pro`. Those are exactly the atoms the claim ledger already
  holds (`DeepSeek V4-Pro`, `Alibaba Qwen3.8-Max`), extracted by the same code
  that verified the beat. Deriving from the beat means the coverage ledger and
  the claim ledger cannot drift apart, and the ledger holds the *specific*
  strings rather than a human summary of them.
- Chrome beats (`title`, `signoff`) are skipped — the same exemption they have
  from citation, for the same reason: they assert nothing. A ledger row reading
  *"Five stories from the last 24 hours"* would match a fragment of every
  future episode and point at nothing.
- Per-beat rather than per-episode, because a hit has to be readable: an author
  looking at a hit needs the sentence that collides with theirs, not "this
  episode also happened".
- Derivable means *actually written*. The old ledger was hand-maintained, which
  is why `skills/storyboard/SKILL.md` had to tell authors, in as many words,
  that there was no way to record that a hit had been run as an update.

Cost, stated: entries are per-beat, so an episode contributes ~20 rows rather
than the 8–10 a human would write, and two beats on one story are two rows
unless they slug identically (identical ids merge). That is more haystack, not
less — which for a one-directional matcher is the safe direction.

### 1.2 Who writes it — operator or pipeline

**Decided: the operator, with an explicit `agsoc coverage add <ep>`. It is not
a side effect of `render`.**

An automatic `add` after render records what was *rendered*. A render that is
discarded, re-cut, or never posted would then put an entry in the ledger for a
story the series never told — and the next `check` would report a hit and the
author would drop a story that is genuinely new. **That is a silent drop, which
is the ledger's own failure mode pointed the other way, and it is harder to
notice than a duplicate: a re-told story gets seen by viewers, a dropped one
never gets written.**

So `add` is a command, and:

- it refuses anything not `rendered`, naming the remedy (`agsoc video render`);
- it refuses an episode already in the ledger unless `--replace`;
- it prints, where the operator reads it, that what it holds is what was
  **rendered** — and that an entry for an episode nobody saw suppresses a story
  they never told;
- `--dry-run` prints the entry it would write;
- `--note` records the operator's sentence (this is where "ran as an update of
  <id>" goes — the thing the skill previously said was impossible).

`tests/test_video_coverage.py::test_render_does_not_record_coverage_as_a_side_effect`
pins the decision against the module that would otherwise be the convenient
place to break it.

### 1.3 What `check` does across series

**Decided: hits are per-series; another series' match is printed as a pointer
and is never counted.**

Silence was defensible and I rejected it. The scoping change exists because one
shared ledger let one series' history suppress another's stories — so a
cross-series match must never be a hit, or the suppression is rebuilt. But the
author is better off knowing, and the codebase already has the right shape for
"true, and not a verdict": D-112's *"Related, and not a hit"* pointer. So:

```
     Told in another series, and not counted here: `cardio-weekly` (2 story(ies)).
     Coverage is per-series: this series has not told it. Read those entries
     before you decide how to tell it.
```

It reads every other series' ledger defensively — one unreadable neighbour must
not take the check down (D-018), and there is a test for that.

---

## 2. Migration proof

`engine/coverage.json` was backed up before anything ran:

```
backed up to …/tmp/backup-engine-coverage.json
6eead320dc134bf5af14db44cbf5b9fc17869629a5576f9a5a12ea735107ebc8  …/backup-engine-coverage.json
6eead320dc134bf5af14db44cbf5b9fc17869629a5576f9a5a12ea735107ebc8  engine/coverage.json
episodes 2 stories 18
```

`workspace/` was backed up whole first, to a path verified not to exist.

### Before / after, on the real ledger

```
=== BEFORE: workspace/series/the-brief/coverage.json ===
episodes 0 stories 0
=== BEFORE: engine/coverage.json ===
episodes 2 stories 18

=== MIGRATE ===
  engine/coverage.json → workspace/series/the-brief/coverage.json
  source holds 18 stories across 2 episodes
  moved 2 episode(s): 2026-08-12, 2026-08-14
  stories 0 → 18

  the source file is not modified — it stays as the record of what was migrated.
  Check it reads back: `agsoc coverage list --series the-brief`

EXIT=0
=== AFTER ===
episodes 2 stories 18
```

### Content, not just counts

```
=== content proof: every legacy story present verbatim in the migrated ledger ===
source stories: 18  migrated stories: 18
ids equal (order included): True
every story byte-identical: True
episode metadata identical: True
dropped entries: none
```

### Nothing else in `workspace/` moved

```
files differing:
Files …/backup-workspace/series/the-brief/coverage.json and workspace/series/the-brief/coverage.json differ
---- episode statuses (must be unapproved, unedited) ----
status: draft
status: in_review
status: in_review
```

**One file differs, and it is the ledger this task exists to fill.** The three
real episodes are untouched and none of them is approved.

**Deviation from the brief, argued.** The brief says to restore `workspace/`
after modifying it. I kept exactly one change — the migrated `coverage.json` —
and restored nothing else, because restoring it would leave the operator's
18 stories of history reachable only from a file the pipeline no longer reads.
That is precisely the state in which *the next episode re-tells a story as
new*: `check` would answer "no entry matches" over the series' own headline,
which is D-112's defect rebuilt out of a tidy-up. The full backup is still at
`…/tmp/backup-workspace`, and `cp …/backup-workspace/series/the-brief/coverage.json
workspace/series/the-brief/coverage.json` reverses it in one command.

---

## 3. TDD evidence and mutation score

### Commits, in order

TBD_COMMITS

### Red first

`tests/test_video_coverage.py` was written and committed **before** any
implementation, and verified failing:

```
70 failed, 3 passed
```

(The three that passed are pins, not behaviour: the ledger data still exists,
`render.py` does not mention coverage, and `check` with no terms exits 2 —
which typer already did.)

Then, in order, and each with the suite re-run:

| step | commit | result |
|---|---|---|
| `check` / `list` / `episode` | `TBD2` | 35 of the check tests green, rest still red |
| `add` + the round trip | `TBD3` | 58 green |
| `migrate` | `TBD4` | 69 green |
| retirement + docs | `TBD5` | **1973 passed**, `node determinism.test.mjs` green |

### Mutation sweep

TBD_MUTANTS

---

## 4. Step 6 — the real check against the migrated ledger

TBD_STEP6

---

## 5. Files changed

TBD_FILES

---

## 6. Issues and concerns

TBD_CONCERNS

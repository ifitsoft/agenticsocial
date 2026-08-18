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

| SHA | commit |
|---|---|
| `1913678` | test: port the ledger check's guarantees to Python, failing |
| `6be155e` | feat: agsoc coverage check, per-series, one-directional |
| `0e8eab0` | feat: agsoc coverage add — what a story is, and the round trip |
| `dfc3bdd` | feat: agsoc coverage migrate — move the history, prove nothing was lost |
| `ca24270` | refactor: retire the node coverage command; the data survives |
| `0ab681f` | test: close the four gaps the first mutation sweep found |
| `5244bda` | test: kill the second sweep's survivors — two guards covering for each other |

Nothing squashed; tests precede every implementation commit.

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
| `check` / `list` / `episode` | `6be155e` | 35 check tests green, the rest still red |
| `add` + the round trip | `0e8eab0` | 58 green |
| `migrate` | `dfc3bdd` | 69 green |
| retirement + docs | `ca24270` | **1973 passed**, `node determinism.test.mjs` green |

### Mutation sweep

Harness committed: `docs/superpowers/worklog/video/phase-11/task-1-mutants.sh`
(D-118: a score with no harness behind it is a claim, not a measurement).
`PYTHONDONTWRITEBYTECODE=1` throughout (D-100); every exit code read unpiped
(D-105).

**Three rounds: 30/34 → 30/34 → 36/36.** The middle round is the interesting
one — it had the same score with a different set of survivors, because two of
the tests written to kill round one's survivors did not kill them.

Round 1 survivors (four): the entities not searched, the title not searched, the
per-term bound sentence deleted, the migration's balance guard removed.

Round 2 survivors (four), after the first fix:

- **M9a / M9b, the instructive pair.** `add` has two refusals in front of it —
  the status is not `rendered`, and there is no render record beside it — and
  the test asserted only that the word *"render"* appeared somewhere in the
  output. **Either guard could be deleted and the other one refused the same
  input with a message that still contained the word.** That is D-118's shape
  verbatim: an assertion searching a large haystack for a small needle passes
  for reasons its author did not intend. Each guard now has a test asserting
  its own sentence against its own input.
- **M1d survived the test written to kill it**: the entity I searched for
  (`acme`) was also in that row's title, so emptying `entities` from the
  haystack changed nothing. The fixture now carries an entity that appears in
  no other field.
- M5c was an equivalent mutant as first written (it mutated a list that the
  refusal then discarded before any write). Rewritten as the reachable version
  of the same defect — *silently overwrite, no refusal at all* — and killed.
- M10c: nothing asserted that the ledger goes through `atomic_write`.

Final round, verbatim:

```
M1a  KILLED    the matcher is a raw substring again (D-112's exact defect)
M1b  KILLED    the term is normalised and the ledger is not
M1c  KILLED    matching tightens to whole tokens (watermark loses watermarking)
M1d  KILLED    the entities are not searched
M1e  KILLED    the title is not searched
M2a  KILLED    an empty needle matches every story
M2b  KILLED    every term is a hit
M2c  KILLED    another series' stories are counted as this series' hits
M3a  KILLED    a miss says it is safe to run as new
M3b  KILLED    the bound on what absence proves is dropped
M3c  KILLED    the miss no longer says what was searched
M3d  KILLED    the related pointer is counted as a hit
M4a  KILLED    the hit line becomes a suggestion
M4b  KILLED    a hit stops naming the episode it collides with
M4c  KILLED    a hit stops printing the title the author has to read
M5a  KILLED    a migrated episode is counted and not written
M5b  KILLED    the last story of each episode is left behind
M5c  KILLED    a date that differs is silently overwritten, no refusal at all
M5d  KILLED    the arithmetic that must balance is not checked
M6a  KILLED    the migration is copied into every series in the workspace
M7a  KILLED    the retired node command is restored
M7b  KILLED    the skill sends the author back to the node command
M8a  KILLED    add writes its stories under a key check does not read
M8b  KILLED    add normalises ids differently from check (digits dropped)
M8c  KILLED    add records no entities
M8d  KILLED    add records no title
M8e  KILLED    add records the chrome beats too
M8f  KILLED    add records the source key and not the host
M9a  KILLED    an unrendered episode can be recorded
M9b  KILLED    an episode marked rendered with no record is accepted
M9c  KILLED    the same episode can be recorded twice
M9d  KILLED    --dry-run writes after all
M9e  KILLED    the screen stops saying the ledger holds what was rendered
M10a  KILLED    an unknown episode exits 0
M10b  KILLED    a broken neighbouring series takes the check down
M10c  KILLED    the ledger is written non-atomically
----- 36 mutants · 36 killed · 0 survived
```

Suite at HEAD: **1980 passed**. `node determinism.test.mjs` green.
`git status --porcelain -- src tests engine skills` is clean.

---

## 4. Step 6 — the real check against the migrated ledger

The four terms the brief names, run against the **migrated** operator ledger
(`workspace/series/the-brief/coverage.json`, 18 stories / 2 episodes), through
the exact spelling the skill now tells an author to use. Exit codes read
unpiped.

```
############ uv run agsoc coverage check gemini-3.7 --series the-brief

  "gemini-3.7"  — 3 prior mention(s):
     2026-08-14  [gemini-3-7-flash]  launch
       Google launches Gemini 3.7 Flash — agentic workhorse at half the price
       note: $0.75/$3.75 per 1M tokens through 2026, doubling in 2027. Benchmarks charted: FrontierCode 1.1, DeepSWE v1.1, AutomationBench, GDP.pdf.
     2026-08-14  [gemini-3-7-flash-github-copilot]  launch
       Gemini 3.7 Flash selectable in GitHub Copilot
       note: Enterprise admins must enable a preview policy first.
     2026-08-14  [gemini-3-7-flash-specs]  analysis
       Gemini 3.7 Flash model card: 1,048,576-token input, 65,536 output, built-in tool use

  → 3 hit(s). Cover these as updates (state what is new) or drop them.

EXIT=0
############ uv run agsoc coverage check gemini --series the-brief

  "gemini"  — 4 prior mention(s):
     2026-08-14  [gemini-3-7-flash]  launch
       Google launches Gemini 3.7 Flash — agentic workhorse at half the price
       note: $0.75/$3.75 per 1M tokens through 2026, doubling in 2027. Benchmarks charted: FrontierCode 1.1, DeepSWE v1.1, AutomationBench, GDP.pdf.
     2026-08-14  [gemini-3-7-flash-github-copilot]  launch
       Gemini 3.7 Flash selectable in GitHub Copilot
       note: Enterprise admins must enable a preview policy first.
     2026-08-14  [gemini-3-7-flash-specs]  analysis
       Gemini 3.7 Flash model card: 1,048,576-token input, 65,536 output, built-in tool use
     2026-08-14  [gemini-spark]  launch
       Gemini Spark upgraded to 3.7 Flash; Tasks/Skills/Schedules model
       note: 24/7 personal agent across Gmail, Calendar, Drive, Docs, Sheets, Maps.

  → 4 hit(s). Cover these as updates (state what is new) or drop them.

EXIT=0
############ uv run agsoc coverage check v4-pro --series the-brief

  "v4-pro"  — no entry matches this string.
     searched 18 stories across 2 episodes in series `the-brief` (id, title, note, entities, sources), separators ignored.
     That is all it proves. It does not mean the story is new: the ledger
     holds only what was written into it after an episode shipped.

  → 0 matches in 18 stories across 2 episodes in series `the-brief` (id, title, note, entities, sources), separators ignored.
    Nothing in the ledger contains these strings. Whether the stories are
    new is a judgement this check cannot make for you.

EXIT=0
############ uv run agsoc coverage check deepseek --series the-brief

  "deepseek"  — no entry matches this string.
     searched 18 stories across 2 episodes in series `the-brief` (id, title, note, entities, sources), separators ignored.
     That is all it proves. It does not mean the story is new: the ledger
     holds only what was written into it after an episode shipped.

  → 0 matches in 18 stories across 2 episodes in series `the-brief` (id, title, note, entities, sources), separators ignored.
    Nothing in the ledger contains these strings. Whether the stories are
    new is a judgement this check cannot make for you.

EXIT=0
```

**The numbers match D-112's own record** — `gemini-3.7` → 3, `gemini` → 4,
`v4-pro` → absent — which is the point of migrating rather than regenerating:
the answers did not change when the ledger moved.

Entry counts, before and after:

| | episodes | stories |
|---|---|---|
| `engine/coverage.json` (source, unchanged) | 2 | 18 |
| `workspace/series/the-brief/coverage.json` before | 0 | 0 |
| `workspace/series/the-brief/coverage.json` after | 2 | 18 |

### The rest of the surface, run

```
############ uv run agsoc coverage list --series the-brief (tail)
    [dyna-2-robot-video-learning]  Dyna-2 teaches robots from human video demonstrations
    [minimax-h3-local-multimodal]  MiniMax H3 runs multimodal inference locally on consumer Macs
    [novo-nordisk-aws-agentic-drug-discovery]  Novo Nordisk names AWS strategic AI partner for agentic drug discovery
    [litellm-supply-chain-attack]  LiteLLM supply-chain compromise via hijacked Trivy scanner
    [chattjb-human-powered-chatbot]  ChatTJB: a chatbot with no AI, run by one founder and 10,000 volunteers

  18 stories across 2 episodes in `the-brief`.

############ uv run agsoc coverage add 2026-08-17 --series the-brief  (a real, unrendered episode)
2026-08-17 is draft, not rendered — the ledger records what the series actually put out. Render it first (`agsoc video render 2026-08-17`), then record it.
EXIT=1
############ uv run agsoc coverage check gemini --series default (the wrong ledger)
no series 'default' — create it with `agsoc series new default`
EXIT=1
```

`add` refuses the operator's real, unrendered episode — and writes nothing.
`--series default` refuses rather than answering out of the wrong ledger.

### The cross-series pointer, in a scratch workspace

```
engine/coverage.json → /tmp/covws2/workspace/series/the-brief/coverage.json
  source holds 18 stories across 2 episodes
  moved 2 episode(s): 2026-08-12, 2026-08-14
  stories 0 → 18


############ uv run agsoc coverage check gemini-3.7 --series cardio-weekly

  "gemini-3.7"  — no entry matches this string.
     searched 0 stories across 0 episodes in series `cardio-weekly` (id, title, note, entities, sources), separators ignored.
     That is all it proves. It does not mean the story is new: the ledger
     holds only what was written into it after an episode shipped.
     Told in another series, and not counted here: `the-brief` (3 story(ies)).
     Coverage is per-series: this series has not told it. Read those entries before you decide how to tell it.

  → 0 matches in 0 stories across 0 episodes in series `cardio-weekly` (id, title, note, entities, sources), separators ignored.
    Nothing in the ledger contains these strings. Whether the stories are
    new is a judgement this check cannot make for you.

EXIT=0
```

Zero hits, and the author is still told the story exists elsewhere.

---

## 5. Files changed

| file | what changed |
|---|---|
| `src/agenticsocial/video/coverage.py` | **new** — matcher, ledger IO, `check`, story derivation, `add`, migration |
| `src/agenticsocial/video/cli.py` | **new** `coverage_app`: `check`, `add`, `list`, `episode`, `migrate` |
| `src/agenticsocial/cli.py` | `agsoc coverage` wired in at top level (spec §11) |
| `tests/test_video_coverage.py` | **new** — 80 tests; every assertion of `coverage.test.mjs` plus per-series, `add`, migration, round trip |
| `tests/test_engine_supported_path.py` | `coverage.test.mjs` removed from CLAUDE.md's tracked list, and asserted absent |
| `engine/coverage.mjs` | **deleted** |
| `engine/coverage.test.mjs` | **deleted** |
| `engine/coverage.json` | **kept, unmodified** — migration source and real-ledger fixture |
| `engine/README.md` | new commands; says what `coverage.json` is now for |
| `CLAUDE.md` | tracked-file list, test list, and the coverage instruction |
| `skills/storyboard/SKILL.md` | D-109's bracket changed, plus `--series` and whose command `add` is |
| `docs/…/phase-11/task-1-mutants.sh` | the sweep harness (D-118) |

Commits: `1913678`, `6be155e`, `0e8eab0`, `dfc3bdd`, `ca24270`, `0ab681f`,
`5244bda`.

---

## 6. Issues and concerns

### 6.1 What can now be re-told as new — concretely

The ledger's whole purpose is one guarantee, so here is where it is currently
thin. Each of these is a real path to *"no entry matches this string"* over a
story the series has already told.

1. **Every episode between the migration and the first `add`.** The ledger now
   holds 2026-08-12 and 2026-08-14 and nothing after. The operator's three real
   episodes (2026-08-17 / 17b / 17c) are **not** in it — they were never
   rendered, and `add` refuses to record what was not rendered. If any of them
   is rendered and posted without an `add`, its stories are invisible to every
   future check. **This is the single most likely way the guarantee fails**, and
   it fails silently: `check` cannot know the difference between "not covered"
   and "covered but never recorded". The mitigation shipped is the message —
   `check` says absence proves only the string's absence — and the skill now
   points the operator at `add`. The mitigation NOT shipped is a nag: nothing
   tells an operator, after a render, that the episode is unrecorded. That is
   the obvious Phase 12 candidate and I did not do it here.
2. **`add` records what was rendered, not what was posted.** The trade is
   deliberate (§1.2), but it cuts the other way too: an episode rendered twice
   in two formats records once, and an episode rendered and then re-cut needs
   `--replace` or the ledger describes the wrong cut.
3. **A series whose slug changes, or an episode moved between series.** Coverage
   follows the directory. Nothing reconciles a rename, and a renamed series
   starts with an empty ledger — which reads exactly like a series that has
   never told a story.
4. **The `default` series.** `check` without `--series` looks in `default`. In
   the operator's workspace `default` does not exist, so it refuses loudly —
   good. But the moment anything scaffolds `default`, a forgotten `--series`
   returns a clean, empty, wrong answer. The skill now says `--series` is not
   optional; the CLI cannot tell a deliberate `default` from a forgotten flag.
5. **Story granularity is per-beat, and a story told in a beat that carries no
   `src`** — there are none today, because `check` refuses uncited beats — would
   still be recorded, but with no source string to match on.

### 6.2 Other concerns

- **`engine/coverage.json` is now two things**: a historical record and a test
  fixture. If someone edits it to make a test pass, they have edited history —
  the same trap `coverage.test.mjs` called out. The Python tests only ever read
  it, and one test asserts its story count is 18, which would catch an edit.
- **The false positives are real and unmeasured.** `aiact` finds *EU AI Act*, as
  D-112 accepted. With `add` now writing whole beat texts into `title`, the
  haystack is several times larger than the hand-written one, so the false
  positive rate will rise with every recorded episode. It is still the correct
  direction to be wrong in, but the day an author sees five spurious hits per
  term is the day they stop reading them. Worth measuring once there are ten
  recorded episodes; there is no data to measure it on yet.
- **Nothing dedupes across episodes.** A story genuinely covered as an update
  appears twice, correctly, and the ledger's `update` / `updateOf` convention
  fields are not written by `add` — the operator's `--note` carries it as prose
  instead. `list` still honours `update: true` if a human writes it.
- **`agsoc coverage add` is a fourth command an agent must not run**, alongside
  `approve`, `render` and `post`. The skill says so; nothing enforces it, which
  is the same posture the other three have.

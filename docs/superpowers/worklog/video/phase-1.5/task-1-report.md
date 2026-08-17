# Task 1 Report: `plan.json` schema and emitter

**Phase:** 1.5 · **Branch:** `feat/video-phase-1.5-vertical-slice`

## 1. What I implemented

`src/agenticsocial/video/plan.py` — the `script.yaml` + `series.toml` → `plan.json`
emitter, exactly as the brief's code block specifies:

- `PlanError`, `FPS = 30`, `DEFAULT_HOLD = 3.0`,
  `SUPPORTED_BEATS = frozenset({"statement"})`,
  `FORMATS = {"vertical": {"w": 1080, "h": 1920}}`
- `_beats(episode)` — reads the verbatim beats document via `episode._read_meta`
  and `yaml.safe_load`s it. Never writes.
- `_statement(raw, index, where)` — validates and normalises one statement beat.
- `build_plan(series, episode, fmt="vertical") -> dict`
- `write_plan(series, episode, fmt="vertical") -> Path` — `atomic_write` of
  `<out_dir>/plan.json`.

The brief's implementation block and its prose agreed everywhere I checked
(defaults, ordering, `total_sec = sum(hold) * pace` rounded to 3 dp,
`pace` from the metadata document). **No code-block/prose contradiction found in
this brief.** The only inconsistency I found is between the brief's *tests* and
its own stated goals, not within the brief — see section 5.

A real emitted artifact (episode with `pace: 1.2`, two beats) is in section 6 of
my reasoning and reproduced here for the record:

```json
{
  "episode": "2026-08-14",
  "series": "the-brief",
  "byline": "",
  "format": { "name": "vertical", "w": 1080, "h": 1920 },
  "fps": 30,
  "pace": 1.2,
  "total_sec": 9.0,
  "design": { "surface": "#F2F5F8", "ink": "#0B1B2B", "...": "..." },
  "beats": [
    { "type": "statement", "act": "01", "hold": 3.5,
      "kicker": "Today's headline",
      "text": "Google shipped its main agentic model.", "src": "blog.google" },
    { "type": "statement", "act": "", "hold": 4.0,
      "kicker": "", "text": "That is the whole story.", "src": "" }
  ]
}
```

## 2. TDD evidence

### RED (`/tmp/red.txt`, before `plan.py` existed)

```
==================================== ERRORS ====================================
__________________ ERROR collecting tests/test_video_plan.py ___________________
ImportError while importing test module '.../tests/test_video_plan.py'.
tests/test_video_plan.py:6: in <module>
    from agenticsocial.video.plan import (
E   ModuleNotFoundError: No module named 'agenticsocial.video.plan'
=========================== short test summary info ============================
ERROR tests/test_video_plan.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.08s
```

Collection error, as predicted.

### GREEN — module suite (`/tmp/green1.txt`)

```
23 passed in 0.42s
```

### GREEN — full suite (`/tmp/green2.txt`)

```
342 passed in 1.33s
```

### GREEN — full suite after the section-5 vacuity fix (`/tmp/green3.txt`)

```
343 passed in 1.28s
```

**Final full-suite count: 343 passed.**

## 3. Mutation results

Run against the final test suite; `git checkout` between each; working tree
verified clean afterwards (`/tmp/mutants_final.txt`).

| # | Mutant | Result | Caught by |
|---|--------|--------|-----------|
| 1 | `_statement` — drop the `text` check | KILLED | `test_statement_without_text_is_refused` |
| 2 | `DEFAULT_HOLD` 3.0 → 5.0 | KILLED | `test_missing_hold_defaults_to_three_seconds` |
| 3 | `build_plan` — drop `kind not in SUPPORTED_BEATS` | KILLED | `test_unsupported_beat_type_is_refused_by_name` |
| 4 | `total` without `* pace` | KILLED | `test_pace_scales_total_but_not_holds` |
| 5 | scale each beat's `hold` by `pace` too | KILLED | `test_pace_scales_total_but_not_holds` |
| 6 | `json.dumps(plan, indent=2, sort_keys=True)` | KILLED | `test_written_json_preserves_the_documented_key_order` |
| 7 | `_beats` — drop the `not beats` check | KILLED | `test_empty_beats_is_refused` |

Every mutant killed exactly one test (342 passed, 1 failed).

**Mutant 6 — your suspicion was correct.** It is killed *only* by a test I added.
`test_write_plan_is_byte_stable_across_runs` passed under `sort_keys=True`, and it
always will: any deterministic key order is stable run to run. That test checks
determinism, not order. Rather than adjust it, I added
`test_top_level_keys_are_exactly_the_documented_ones_in_order`,
`test_beat_keys_are_emitted_in_the_documented_order`, and
`test_written_json_preserves_the_documented_key_order` — the last of which is what
kills mutant 6. The brief documents key order as a requirement ("so the JSON is
stable across runs and diffable"), so it needed a test that can see it.

### Three extra mutants I ran to substantiate the vacuity audit

| Mutant | Result | Caught by |
|--------|--------|-----------|
| V-a: drop the `if not kind:` missing-`type` branch | KILLED | `test_beat_without_a_type_names_the_missing_key_not_an_unsupported_one` (added) |
| V-b: reverse the beat dict's key order | KILLED | the two added key-order tests |
| V-c: `write_plan` re-emits `script.yaml` through `_compose` | KILLED | `test_a_comment_bearing_script_survives_plan_building_byte_for_byte` (added) |

All three **survived the brief's tests alone**. Details in section 5.

## 4. Files changed and commits

- `tests/test_video_plan.py` (new)
- `src/agenticsocial/video/plan.py` (new)

Nothing under `docs/` was staged. `git status --porcelain -- src tests` is clean.

| Commit | SHA | Message |
|--------|-----|---------|
| 1 | `dc21bd5654a454a4e8c830f98e4ef6a5a2cb5e56` | `test: specify the plan.json schema and emitter` |
| 2 | `d00056c37be1bcbb7182ac5dfdb54a6bdcc3e0cd` | `feat: emit plan.json from script.yaml and series.toml` |
| 3 | `0853a9d8659c05eff94d1bba5cf8cd247a6f60b4` | `test: pin D-026 against a script that does not round-trip` |

**Deviation to flag:** the brief mandated two commits. There are three. The third
is the Step 5 vacuity fix — the brief instructs "Fix any that pass, and say which
ones you fixed", and I only discovered the D-026 guard's weakness during the
mutation run, after committing. Amending would have meant rewriting history under
the implementation commit; a third commit that names the fix is more legible than
a squash. Commits 1 and 2 remain the failing-tests-then-implementation pair.

## 5. Vacuity audit

I asked of each test: *what would this do against an implementation that does
nothing meaningful, and against the smallest wrong implementation a reasonable
person would write?* Three tests failed that audit. I did not modify the brief's
tests — I added tests that cover what they miss, so the gaps are visible in the
suite rather than only in this report.

### Weak test 1 — `test_write_plan_is_byte_stable_across_runs`

Its docstring claims it protects **key order**. It cannot. Any fixed order is
byte-stable across runs, so `sort_keys=True` (mutant 6) sails through. Proven:
under mutant 6 this test passed and only my added test failed.
**Added:** three key-order tests (dict order, beat-key order, and order as it
survives serialisation to the file).

### Weak test 2 — `test_beat_without_a_type_is_refused`

`pytest.raises(PlanError, match="type")` — but the *unsupported*-type message
also contains the word "type". Delete the `if not kind:` branch and a typeless
beat falls through to the `kind not in SUPPORTED_BEATS` check, raising
`unsupported type None` — which still matches `"type"`. The test cannot tell the
two failure modes apart. Proven by mutant V-a, which this test did not catch.
**Added:** `test_beat_without_a_type_names_the_missing_key_not_an_unsupported_one`,
which asserts `"no \`type\`"` is present and `"unsupported"` is absent.

### Weak test 3 — `test_building_a_plan_never_rewrites_the_script` (the D-026 guard)

**This is the one that matters, and it is the same failure class as the Phase 1
test that was written to pin a known mutant and did not.** The test's fixture
metadata is `episode: e\nseries: the-brief\nstatus: draft\n` — which
`yaml.safe_dump(sort_keys=False)` reproduces byte-for-byte. So a `write_plan` that
re-composes `script.yaml` through `episode._compose` leaves the file *identical*
and the guard stays green (mutant V-c: 342 passed, 0 failed). The test was
green against precisely the bug it is named after.

D-026 is not about writes in general; it is about writes that are **lossy** —
comments, quoting, key order, blank lines that `safe_dump` destroys. A fixture
that round-trips cleanly cannot express that.
**Added:** `test_a_comment_bearing_script_survives_plan_building_byte_for_byte`,
using a metadata document with a comment, a quoted `status`, and a blank line.
Mutant V-c now fails it (commit 3).

### Tests that passed the audit

The remaining 16 brief tests all pin a value, a message, or a refusal that a
do-nothing or naively-wrong implementation would get wrong; each mutant in
section 3 confirmed at least one of them can fail.
`test_supported_beats_is_exactly_statement_for_this_phase` is a constant assertion
— it can only fail if someone widens the phase's scope, which is exactly its job,
so I left it.

## 6. Issues and concerns

### 6.1 `plan.py` imports the private `_read_meta` from `episode.py`

**It works, but it is the wrong seam, and I found a live bug behind it.**

`episode.py`'s docstring is emphatic that `frontmatter.parse` is a
silent-wrong-answer trap and that `_read_meta` is the only correct reader. That
makes `_read_meta` a *contract*, not an implementation detail — and a
leading-underscore name is the wrong way to publish a contract that a second
module now depends on. I'd expose:

```python
def read_beats_text(path: Path) -> str | None:
    """The verbatim bytes of document 2, for READING only. Never write this back
    through _compose — see D-026."""
```

so `plan.py` imports one public, single-purpose function whose docstring carries
the read-only warning, instead of reaching for a private 3-tuple whose middle
element happens to be what it wants.

**The live bug:** `build_plan` takes `pace` from `episode.meta` (in memory, from
`load_episode`) but reads beats from a **fresh** `_read_meta(episode.script_path)`
call. Those are two different reads of the same file. If the operator saves
`script.yaml` between `load_episode` and `build_plan`, the plan is assembled from
two different versions of the script — new beats, old pace — and nothing detects
it. It is a narrow window, but the whole point of the two-document design is that
the script's bytes are authoritative and versioned. A public reader that returns
*both* halves from one read (or a `beats` field cached on `Episode` at load time)
closes it. I did not change this: the brief's code block is authoritative and its
tests pin the current behaviour.

### 6.2 Is `plan.json` the right boundary? Structural gaps for Phase 4

The boundary itself is right — Node stays a pure renderer with no YAML
dependency, and JSON is the one format both sides parse without a library. Three
gaps are **structural**, i.e. the shape cannot express them at all:

**(a) `beats` is a sequence, not a timeline with layers. This is the big one.**
The schema hard-codes the assumption that beats are a strict, non-overlapping,
gapless partition of the timeline: every visual belongs to exactly one beat, and
nothing crosses a boundary. There is nowhere to put anything that *spans* beats —
a persistent chart that stays up while the headline changes, a lower-third that
outlives its beat, a background treatment, an audio bed, an act-level progress
indicator, a cross-beat transition (any beat-to-beat wipe or morph is *between*
two beats and belongs to neither). `total_sec = sum(hold)` encodes the same
assumption arithmetically: overlap would make the sum wrong, not just incomplete.
Adding beat types never fixes this. The fix, if Phase 4 needs it, is a top-level
`tracks` or `layers` array with items carrying explicit `start`/`end`, and beats
becoming one track among several. I would rather that shape were decided now,
while `statement` is the only consumer, than retrofitted once `render.mjs` has
been written against a flat list.

**(b) The plan carries no identity binding it to the script it came from.**
Spec §10 binds approval to `script_sha256`, but `plan.json` records neither the
hash nor the episode's status. So a `plan.json` on disk is unfalsifiable: edit
`script.yaml` after emitting it and nothing — not the renderer, not a later
`agsoc video render` — can tell that the artifact is stale, or that it was built
from an unapproved script. The approval gate is the project's core invariant, and
right now it stops at the language boundary. A `"script_sha256"` field (plus
possibly `"status"` and a generator version) would make the renderer able to
refuse a plan that no longer matches its source. The shape cannot express drift
today, and that is a gap in the same category as the CLI's `assert_transition`
running before the keyring is touched.

**(c) One `plan.json` per episode, but `format` is a field inside it.**
`write_plan` always writes `<out_dir>/plan.json`, so emitting `vertical` and
`wide` for the same episode means the second overwrites the first, silently. The
series already declares `formats = ["vertical", "wide"]`, so this is a
foreseeable collision, not a hypothetical. Either the filename carries the format
(`plan.vertical.json`) or the file holds all enabled formats. A one-line fix
today; a migration once Phase 4 hard-codes the path.

Two smaller notes: nothing in the plan is expressed in **frames** even though the
renderer is frame-based, so whoever converts seconds to frames owns the rounding
and it isn't specified here; and `series.target_sec` / `tolerance_sec` don't reach
the plan, so nothing downstream can report "this episode is 12s over target"
without re-reading `series.toml`.

### 6.3 Should `pace` be resolved in the plan rather than in the engine?

**The current split is the worst of the two options, and I'd resolve it fully.**

Today `total_sec` is pace-scaled but per-beat `hold` is not, so the pace formula
exists in *two* places on opposite sides of the language boundary. That is
precisely the duplication `plan.json` was created to eliminate. Worse, the two
can silently disagree: a Node bug applying `pace` produces a render whose actual
length contradicts the `total_sec` in its own plan, and nothing compares them.

Resolving fully also serves the engine's load-bearing invariant. `window.__seek(t)`
must position every element purely as a function of `t`. Handing the engine
pre-resolved absolute times turns seeking into a lookup — find the beat whose
`[start, start+hold)` contains `t` — with no arithmetic that could drift.
Arithmetic in the renderer is arithmetic the determinism test has to police.

Concretely I'd emit, per beat, a scaled `hold` **and** an absolute `start`, and
demote `pace` to informational provenance (keep it in the plan so a human can see
why the numbers are what they are, but let nothing downstream multiply by it).
That also puts rounding in one place: Python decides the frame boundaries, so
`sum(per-beat frames)` is guaranteed to equal the total frame count. Under the
current shape it isn't — `hold: 3.5` at `pace: 1.1` is 3.85s, or 115.5 frames at
30fps, and whether that rounds up or down is currently undefined and lives in
Node.

I did not implement this: `test_pace_scales_total_but_not_holds` explicitly pins
the unscaled holds with the comment "the engine applies pace", so it is a
deliberate decision of yours and a change would need your call, not mine.

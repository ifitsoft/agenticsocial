# Task 0 Report — Carried debt that becomes load-bearing this phase

**Branch:** `feat/video-phase-03-script-schema`
**Commits:** `807c11e` (RED) · `4dcfc4b` (GREEN) · `1fe0a6f` (mutation-sweep test)

## 1. What I changed

`src/agenticsocial/video/series.py`

- Added `REGISTERS = ("reported", "first-person")` with a comment stating why
  `cadence` is deliberately *not* given the same treatment.
- `load_series` now validates, after `target_sec`:
  - `tolerance_sec` — bool-rejected, int-required, `>= 0`. `0` is explicitly
    valid and the error message says so.
  - `register` — must be in `REGISTERS`; the error names Phase 4 as the
    consumer.
  - `name` / `byline` — must be strings *if present*; absent still defaults.
- The `Series(...)` call now passes the validated locals (`tolerance_sec=`,
  `register=`) rather than re-reading the raw dict.

`src/agenticsocial/video/episode.py`

- `MAX_ID_LEN = 64` deleted; replaced with
  `from .series import MAX_NAME_LEN as MAX_ID_LEN`.

`cadence` is untouched. Nothing branches on it (spec §6 marks it advisory), and
validating it would reject a legitimate `"fortnightly"`.

## 2. TDD evidence and mutation score

RED (`uv run pytest tests/test_video_series.py`, at `807c11e`):

```
14 failed, 95 passed in 0.57s
```

Failures: `test_bad_tolerance_sec_is_rejected` ×4,
`test_unknown_register_is_rejected` ×3, `test_non_string_text_fields_are_rejected`
×6, `test_episode_does_not_redeclare_the_length_limit`. All four negative-half
tests (`zero_tolerance`, `both_registers`, `cadence_stays_free_form`,
`absent_text_fields_still_default`) passed before the change, which is what a
negative-half guard should do.

GREEN (full suite, `4dcfc4b`):

```
501 passed in 1.94s
```

Final (`1fe0a6f`):

```
509 passed in 2.00s
```

**MUTATION SCORE: 14/14 non-equivalent mutants killed — 100%.**
(7/7 from the brief; 7/7 from my own sweep after `1fe0a6f`; 2 further sweep
mutants are provably equivalent and excluded from the denominator.)

## 3. Mutant results

### The brief's seven

| # | Mutant | Result | Killed by |
|---|---|---|---|
| M1 | `tolerance_sec` check dropped | **KILLED** (4 failed) | `test_bad_tolerance_sec_is_rejected` ×4 |
| M2 | `tolerance_sec` rejects `0` (`<= 0`) | **KILLED** (1 failed) | `test_zero_tolerance_is_valid` |
| M3 | `tolerance_sec` accepts `True` (bool check dropped) | **KILLED** (1 failed) | `test_bad_tolerance_sec_is_rejected[true]` |
| M4 | `register` check dropped | **KILLED** (3 failed) | `test_unknown_register_is_rejected` ×3 |
| M5 | `cadence` validated against a set too | **KILLED** (1 failed) | `test_cadence_stays_free_form` |
| M6 | `name`/`byline` type check dropped | **KILLED** (6 failed) | `test_non_string_text_fields_are_rejected` ×6 |
| M7 | one module's limit changed, the other left | **KILLED** (3 failed) | `test_one_length_limit_shared_by_both_modules` + `test_episode_does_not_redeclare_the_length_limit` |

### My own sweep

| # | Mutant | Result |
|---|---|---|
| S1 | `tolerance_sec` default `8` → `5` | **KILLED** |
| S2 | `register` default → `"first-person"` | **KILLED** |
| S3 | off-by-one on the negative half: `< 0` → `< -1`, so `-1` loads | **KILLED** |
| S4 | `REGISTERS` drops `"first-person"` | **KILLED** |
| S5 | only `name` type-checked, `byline` dropped from the loop | **KILLED** |
| S6 | validated `tolerance_sec` discarded; raw value re-read into `Series(...)` | SURVIVED — **equivalent**, see below |
| S7 | validated `register` discarded; raw value re-read into `Series(...)` | SURVIVED — **equivalent**, see below |
| S8 | shared length limit `64` → `32` in both modules at once | **KILLED** |
| S9 | `if value is not None:` → `if value:` on `name`/`byline` | **SURVIVED, then killed** |

**S9 was a genuine gap.** Every bad value in the brief (`5`, `["a"]`, `true`) is
truthy, so a validator that only rejects *truthy* non-strings passed the entire
501-test suite. `name = 0` or `byline = false` would have loaded and reached
`_toml_str` on the next scaffold — precisely the TypeError-far-from-here the
check exists to prevent. Commit `1fe0a6f` adds
`test_falsy_non_string_text_fields_are_rejected` (`0`, `false`, `[]`, `0.0` ×
both fields); the mutant now fails 8 tests. No implementation change was needed —
the shipped code was already correct, the tests were not strong enough to prove
it.

**S6/S7 are equivalent mutants, and that is worth stating explicitly** because
they are the *exact shape* the brief warns about: validate a value, then hand a
freshly re-read raw value to the consumer. Today `runtime.get("tolerance_sec", 8)`
is a pure read of an unmutated dict, so the mutant is behaviourally identical and
no test can distinguish it. It stops being equivalent the moment anything mutates
`meta`/`runtime` between validation and construction, or the validator starts
*normalising* (e.g. coercing a float, trimming a string) rather than only
rejecting. Passing the locals — which the implementation does — is the shape that
stays correct under both changes.

## 4. Files changed

| Commit | Files |
|---|---|
| `807c11e` test | `tests/test_video_series.py` |
| `4dcfc4b` fix | `src/agenticsocial/video/series.py`, `src/agenticsocial/video/episode.py` |
| `1fe0a6f` test | `tests/test_video_series.py` |

`git status --porcelain -- src tests` is clean. Nothing under `docs/` was staged.

## 5. Issues and concerns

### 5a. Defect in the brief's R4 test — flagged, not silently fixed

The brief's `test_one_length_limit_shared_by_both_modules` asserts
`S.MAX_NAME_LEN is E.MAX_ID_LEN`. **That test passes on the unfixed tree.**
CPython interns small integers (−5…256), so two entirely independent `= 64`
literals in two modules satisfy `is`:

```
$ python3 -c "a=64;b=64;print(a is b)"
True
```

`is` therefore buys nothing over `==` here, and the test cannot detect the very
thing R4 is about: a *duplicated definition* that has not drifted yet. It only
catches drift after it has already happened — i.e. after the defect ships.

I kept the brief's test verbatim (code blocks are authoritative) and added
`test_episode_does_not_redeclare_the_length_limit`, which asserts structurally
that `episode.py` contains the import and contains no `MAX_ID_LEN = ...`
assignment. That is the test that was RED before the fix. Source-text assertions
are normally a smell; here the property being pinned genuinely is "there is one
definition", which is not observable through values.

### 5b. Did the shared constant need moving to `workspace.py`?

**No.** `from .series import MAX_NAME_LEN as MAX_ID_LEN` in `episode.py` is
acyclic: `series.py` imports `..workspace` and `.models` only, and never imports
`episode`. Full suite green (509) confirms no import-order problem.

I left it in `series.py` rather than pre-emptively moving it to `workspace.py`.
If a third module ever needs it, `workspace.py` beside `assert_safe_name` is the
right home and the move is a one-liner — but moving it now would put a
video-specific limit in the text-pipeline module for no current benefit.

### 5c. `design.*` is still unvalidated — whose problem?

`accent = 5` loads today. `design` is `_table`-checked (it must be a table) and
then passed through untouched: `load_series` stores `design=design`, and
`plan.py` copies it wholesale into `plan.json` (`"design": dict(series.design)`),
which the Node engine interpolates into `scene.html`.

**My read: it is Phase 4's problem, but with one caveat this phase should
record.** The argument for deferring is that `design` has no consumer in Phase 3
— nothing in the duration gate or the beat schema reads a colour — and the rule
that has served this project is *validate the field when a gate reads it*.
Validating it now means inventing a colour/typography schema with no consumer,
which the plan itself flags as the risk in "Scope of the beat catalogue".

What breaks first if it is left: a non-string `design` value is written straight
into `plan.json` as JSON (`"accent": 5`), survives the handoff, and lands in a
CSS custom property as `--accent: 5`. CSS discards the invalid declaration
silently, so the failure mode is **a rendered video with the wrong colours and no
error anywhere** — the most expensive failure shape in this pipeline, because it
is only detectable by watching the output. It is not a crash, it is not a gate
bypass, and it is 100% contained to rendering, which is why it can wait — but
Phase 4 must validate `design` **before** it writes `plan.json`, not at render
time, or the diagnosis point is a browser instead of a CLI error.

### 5d. Anything else a Phase 3 gate will read that nothing validates

Ordered by how directly Phase 3 touches them.

1. **`acts[]` entry shape — the real one.** `load_series` validates that `acts`
   is a list of tables and stops there. The individual `id`, `label` and `beats`
   keys are entirely unvalidated: `beats = "six"`, a missing `id`, a duplicate
   `id`, or `beats = -1` all load. Phase 3's script schema is the first thing
   that will plausibly cross-check beats against acts (spec §7), and
   `test_acts_are_loaded_in_order` already reads `s.acts[0]["beats"]` as a
   number. **This is the closest analogue to `tolerance_sec` and I would fix it
   in Task 1, not later.**
2. **`warm_acts` entries are strings but reference nothing.** `warm_acts = ["99"]`
   with no act `99` loads clean. It is a silent no-op at render time — the same
   invisible-failure shape as 5c. Cheap to check now that `acts` is in hand
   (`set(warm_acts) <= {a["id"] for a in acts}`), and it is the only
   cross-field invariant in `series.toml`.
3. **`formats` allows duplicates.** `enabled = ["vertical", "vertical"]` loads,
   and Phase 3's runtime estimate is per-format. Harmless today, renders twice
   later.
4. **`slug` in `[series]` is read by nobody and checked by nobody.** The scaffold
   writes it; `load_series` uses the directory name and ignores the field
   entirely. A `series.toml` whose `slug` disagrees with its directory is a
   silent lie that an operator will eventually trust. Either drop it from the
   template or assert it matches.
5. **Episode `date_long` is an unvalidated free string** in `script.yaml`
   metadata, and `agsoc video review` (Task 2) will display it.
6. **Already fine, checked so the next task need not:** `pace` and per-beat
   `hold` are both bool-rejected, numeric-checked and `> 0` in `plan.py`
   (lines 64–65, 87–89). Those are the two other direct duration-gate inputs and
   they do not need this treatment.

One further note for Task 2, from the plan's own D-063 section: the duration gate
reads `tolerance_sec` off a `Series` **object**. This task made the value
*trustworthy at load time*; it does nothing about *staleness*. A caller holding a
`Series` loaded before `series.toml` changed will gate against the old tolerance,
and `frozen=True` is inert against that. The stale-object test the plan requires
is still required.

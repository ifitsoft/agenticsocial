# Task 1b Report: Resolve the plan fully, and bind it to its script

**Branch:** `feat/video-phase-1.5-vertical-slice`
**Commits:** `6a25338` (tests, RED) → `3a603b0` (implementation, GREEN)

---

## 1. What I changed

- `src/agenticsocial/video/episode.py` — added a public `read_script(path)` directly
  below `_read_meta`, delegating to it. `plan.py` now depends on a published
  contract rather than an underscore.
- `src/agenticsocial/video/plan.py`
  - `_beats` deleted; replaced by `_load_script(episode)`, which reads the file
    **once** — `read_bytes()` for the digest, then `read_script` for metadata and
    the verbatim beats text — and returns `(meta, beats, digest)`.
  - `build_plan` now takes `pace` from that read's `meta`, not from
    `episode.meta`. This is the D-045-class bug the brief named: two reads of one
    file are two sources of truth.
  - Every beat now carries scaled `hold`, absolute `start`/`end`, and integer
    `start_frame`/`end_frame`. Pace and frame rounding happen only in Python.
  - `total_sec = beats[-1]["end"]`, `total_frames = beats[-1]["end_frame"]`.
  - `script_sha256` added to the top level, after `byline`.
  - `write_plan` writes `plan-{fmt}.json`.
- `tests/test_video_plan.py` — the three amendments in Step 1a, **four further
  schema-forced amendments** (see §7), and the nine new tests from Step 1b.

## 2. TDD evidence

RED, after the test commit and before any implementation
(`uv run pytest tests/test_video_plan.py`):

```
FAILED tests/test_video_plan.py::test_first_beat_carries_every_field
FAILED tests/test_video_plan.py::test_pace_scales_holds_and_total
FAILED tests/test_video_plan.py::test_write_plan_lands_in_out_dir_and_is_valid_json
FAILED tests/test_video_plan.py::test_top_level_keys_are_exactly_the_documented_ones_in_order
FAILED tests/test_video_plan.py::test_beat_keys_are_emitted_in_the_documented_order
FAILED tests/test_video_plan.py::test_written_json_preserves_the_documented_key_order
FAILED tests/test_video_plan.py::test_beats_are_contiguous_and_start_at_zero
FAILED tests/test_video_plan.py::test_total_sec_is_the_last_end_not_a_sum
FAILED tests/test_video_plan.py::test_frames_are_integers_and_sum_to_the_total
FAILED tests/test_video_plan.py::test_fractional_frames_are_resolved_in_python
FAILED tests/test_video_plan.py::test_plan_carries_the_script_sha256
FAILED tests/test_video_plan.py::test_editing_the_script_changes_the_hash
FAILED tests/test_video_plan.py::test_metadata_and_beats_come_from_the_same_read
FAILED tests/test_video_plan.py::test_write_plan_names_the_file_after_the_format
======================== 14 failed, 18 passed in 0.35s =========================
```

Each failure is for the right reason: `KeyError: 'start'`, `KeyError:
'script_sha256'`, `assert 3.5 == 5.25`, `assert 1.0 == 2.0` — absent behaviour,
not broken plumbing.

GREEN:

```
tests/test_video_plan.py .......................... 32 passed in 0.31s
```

Full suite, after implementation:

```
============================= 351 passed in 1.05s ==============================
```

Baseline before this task was **343 passed**; +8 is nine new tests minus one that
did not exist as a separate node (`test_pace_scales_total_but_not_holds` was
renamed rather than added). Observed, not predicted.

## 3. Mutation results

All seven brief mutants, applied one at a time against the full suite, `git
checkout`-clean between each.

| # | Mutant | Result | Caught by |
|---|---|---|---|
| 1 | `hold` not scaled by `pace` | **2 failed** | `test_pace_scales_holds_and_total`, `test_fractional_frames_are_resolved_in_python` |
| 2 | `total_sec` back to `sum(hold)` | **351 passed — SURVIVED** | nothing (see §5) |
| 3 | frames via `int()` not `round()` | **1 failed** | `test_fractional_frames_are_resolved_in_python` |
| 4 | `meta` from `episode.meta` | **1 failed** | `test_metadata_and_beats_come_from_the_same_read` |
| 5 | hash `beats_text` not the whole file | **2 failed** | `test_plan_carries_the_script_sha256`, `test_metadata_and_beats_come_from_the_same_read` |
| 6 | `write_plan` back to `plan.json` | **2 failed** | `test_write_plan_lands_in_out_dir_and_is_valid_json`, `test_write_plan_names_the_file_after_the_format` |
| 7 | `at = end` → `at = 0.0` | **4 failed** | `test_total_sec_is_the_sum_of_holds_times_pace`, `test_pace_scales_holds_and_total`, `test_beats_are_contiguous_and_start_at_zero`, `test_frames_are_integers_and_sum_to_the_total` |

Three further mutants I wrote for the vacuity audit:

| # | Mutant | Result | Caught by |
|---|---|---|---|
| 8 | `total_frames` = last `start_frame` | **2 failed** | `test_frames_are_integers_and_sum_to_the_total`, `test_fractional_frames_are_resolved_in_python` |
| 9 | digest over the metadata document only | **3 failed** | `test_plan_carries_the_script_sha256`, `test_editing_the_script_changes_the_hash`, `test_metadata_and_beats_come_from_the_same_read` |
| 10 | drop `round(..., 3)` on `start`/`end` | **351 passed — SURVIVED** | nothing (see §6) |

## 4. Files changed

```
 src/agenticsocial/video/episode.py |  9 +++++
 src/agenticsocial/video/plan.py    | 67 ++++++++++++++++++++++++++--------
 tests/test_video_plan.py           | (test commit)
```

- Tests: `6a25338`
- Implementation: `3a603b0`

Nothing under `docs/` was staged. `git status --porcelain -- src tests` is clean.

## 5. Vacuity audit

Every test I added or amended, with the mutant constructed to kill it.

| Test | Killing mutant | Verdict |
|---|---|---|
| `test_first_beat_carries_every_field` (amended) | exact-dict equality; mutant 3 and 8 both move fields inside it | non-vacuous by construction |
| `test_pace_scales_holds_and_total` (amended) | 1, 7 | non-vacuous |
| `test_missing_hold_defaults_to_three_seconds` (amended) | the `hold == 3.0` half is killed by changing `DEFAULT_HOLD`; the added `total_sec == 3.0` half is killed by 2? **no** — see below | half-weak |
| `test_beats_are_contiguous_and_start_at_zero` | 7 | non-vacuous |
| `test_total_sec_is_the_last_end_not_a_sum` | **none — mutant 2 survives** | **VACUOUS** |
| `test_frames_are_integers_and_sum_to_the_total` | 7, 8 | non-vacuous |
| `test_fractional_frames_are_resolved_in_python` | 1, 3, 8 | non-vacuous; this is the one that owns the half-frame |
| `test_plan_carries_the_script_sha256` | 5, 9 | non-vacuous |
| `test_editing_the_script_changes_the_hash` | 9 (not 5) | non-vacuous, but strictly weaker than the one above |
| `test_metadata_and_beats_come_from_the_same_read` | 4, 5, 9 | non-vacuous; this is the one that owns the two-reads bug |
| `test_write_plan_names_the_file_after_the_format` | 6 | non-vacuous |

### The one that is vacuous: `test_total_sec_is_the_last_end_not_a_sum`

Mutant 2 restores `total_sec = round(sum(hold), 3)` and **the whole suite stays
green**. The test named for exactly that distinction cannot see it. Reporting it
rather than papering over it, per the brief's standard.

This is not a fixable test — it is unkillable by construction. Under today's
builder, `sum(hold)` and `beats[-1]["end"]` are *provably* the same number:

- `at` starts at `0.0` and the only assignment is `at = end`, so beats are
  contiguous with no gaps and no overlap;
- `hold` and every `end` are rounded to 3 decimals, so `end_n = at + hold_n` is
  exact at 3 decimals and the telescoping sum is exact too.

There is no input to `build_plan` today that separates the two expressions. The
guarantee the test names — *"the schema is neutral about overlap"* — is a
**forward-compatibility property of the code's shape**, not observable behaviour
of its output. It only becomes testable when something can span beats (tracks,
an audio bed, a transition), which the brief explicitly defers.

Two honest options, neither of which I took unilaterally:

1. Keep the test as a documented marker and say so in its docstring — it pins
   the *value* correctly, it just cannot pin the *derivation*.
2. Delete it and record the decision in DECISIONS, re-adding it in the phase that
   introduces tracks, where it will kill mutant 2 immediately.

I lean (1), with the docstring amended to admit that it is equivalent to a sum
today. I did not amend it in this task because it would mean editing a test after
its RED commit, and the brief's code block is authoritative on its wording.

### The half-weak one

The `total_sec == 3.0` assertion I added to
`test_missing_hold_defaults_to_three_seconds` (per Step 1a's code block) is not
independently killable: with one beat of default hold at pace 1.0, `total_sec`
equals `hold` under every plausible derivation. It is a consistency check, not a
guard. Flagging it rather than claiming coverage it does not have.

## 6. Issues and concerns

### Q1 — Is `round(115.5) == 116` true, and does ties-to-even drift?

**Your number is correct**, but for a reason worth stating precisely.

Verified directly:

```
round(115.5)= 116   round(116.5)= 116   round(114.5)= 114
```

`round(115.5)` is 116 because **116 is the even neighbour** — not because Python
rounds half up. Change the input by one frame and it goes the other way:
`round(114.5)` is 114, i.e. *down*. So the assertion in
`test_fractional_frames_are_resolved_in_python` is true, and its comment
(`# round(115.5) -> banker's`) is accurate. Nothing in the brief's arithmetic is
wrong.

I also checked that the value is exactly `115.5` and not a float hair above it,
because the answer would differ if it were:

```
round(3.5 * 1.1, 3)      -> 3.85
3.85 * 30                -> 115.5        (exactly representable, == 115.5 is True)
3.5 * 1.1 * 30           -> 115.50000000000001   (rounds to 116 for a different reason)
```

The implementation rounds `hold` to 3 decimals *before* multiplying by FPS, so it
is the exact-`115.5` path and the tie is real.

**Does it drift?** No, and the reason is structural rather than lucky: frames are
computed from **absolute** times (`round(start * FPS)`, `round(end * FPS)`), not
by accumulating per-beat frame counts. Error is therefore bounded at ±0.5 frame
at every boundary and cannot compound. Measured over 200 consecutive beats of
3.85 s (770 s of video, 23100 frames):

```
last end sec 770.0   exact 770.0
last end_frame 23100 ideal 23100.0
max abs drift 0.500000000003638   (frames, across all 200 boundaries)
```

Half a frame at boundary 1, half a frame at boundary 200. Ties-to-even is in fact
*better* here than ties-away-from-zero: it is unbiased, so a run of ties does not
systematically lengthen the episode.

The one real consequence is not drift but **collapse**: a beat shorter than one
frame (`hold * pace < 1/30 s`) rounds to `start_frame == end_frame` and renders
for zero frames — it silently vanishes. Confirmed: `hold: 0.01` yields frames
`0 → 0`. `_statement` only rejects `hold <= 0`. If a beat that produces no output
should be an error, the check belongs next to that one, and it is a one-line
addition. Out of scope here; raising it rather than adding it.

### Q2 — Is `pace` still worth carrying?

Yes, but only as what the schema already calls it: provenance. It is now
strictly redundant for rendering — the engine reads `hold`/`start`/`end`/frames
and never touches `pace`. Two things keep it earning its slot:

1. **Diff legibility.** `plan.json` is a build artifact people read. A diff that
   changes every beat's four timing fields is unintelligible; the same diff with
   `pace: 1.0 → 1.5` at the top explains itself in one line.
2. **It is the only field that cannot be recovered.** Given a resolved plan you
   cannot invert the scaled holds back to the operator's authored values without
   knowing `pace`. Dropping it makes the artifact lossy with respect to its
   source, which is the opposite of what `script_sha256` is for.

The risk is that a future reader treats it as an instruction rather than a
record. The schema comment (`# provenance only; already applied below`) is the
mitigation, and it should survive into whatever documents `plan.json` for Phase 4.

### Q3 — Nothing checks `script_sha256`. Where should the check live?

Correct, and it is the honest limitation of this task: the plan now *has*
identity, but no code compares it to anything, so a stale `plan-vertical.json`
is still indistinguishable from a fresh one. Two distinct checks are needed, and
they are not the same check:

1. **Approval → render (spec §10).** Approval must record the hash of the script
   it approved, and the render entry point must recompute the script's hash and
   refuse if it differs. This one belongs in `episode.py` alongside `set_status`,
   for the same reason that gate reads status **from disk**: an in-memory
   comparison is not a guarantee. Concretely, `set_status(..., APPROVED)` writes
   `approved_sha256` into the metadata document, and the transition into
   `RENDERING` recomputes and compares. It should raise `EpisodeError` naming
   both hashes and telling the operator to re-approve.

2. **Plan → render.** Before `render.mjs` consumes a plan, whoever invokes it
   should recompute the script's hash and compare it to `plan["script_sha256"]`,
   refusing a plan built from different bytes. This belongs in the Python render
   command, not in Node — Node has no reason to learn what a script is, and
   keeping it out preserves "Node is a pure renderer". The cheaper alternative is
   to make the render command always rebuild the plan, in which case the field
   becomes an audit record rather than a gate.

Both fail closed, both name the file and both hashes. Neither belongs in this
task, but until (1) exists the sentence from Task 1's report still stands: the
approval gate stops at the language boundary.

### Additional finding: mutant 10 survives — `round(start, 3)` is unpinned

Not on your list; I wrote it for the audit. Removing the `round(..., 3)` from
`start`/`end` leaves the entire suite green. That is a real gap: without it,
accumulated float error puts values like `11.550000000000002` into a JSON file
whose stated purpose is to be diffable. `test_write_plan_is_byte_stable_across_runs`
cannot catch it, because the noise is deterministic and therefore stable.

The rounding is correct in the implementation as shipped — it is simply not
defended by a test. A single assertion (`plan["total_sec"] == 11.55` on a
pace that produces drift) would pin it. I did not add it because the brief's
test list is explicit and I would rather report the gap than quietly widen scope.

## 7. Deviations from the brief — flagged

**The three-amendment limit was not sufficient.** Four further existing tests
assert the *old schema* and could not survive the change. All four are
schema-forced in exactly the sense that licensed the original three; none is a
behavioural assertion I moved to make something pass. Listing them so the
decision is reviewable rather than buried in a diff:

| Test | Change | Why it was unavoidable |
|---|---|---|
| `test_write_plan_lands_in_out_dir_and_is_valid_json` | `plan.json` → `plan-vertical.json` | Step 5 mutant 6 requires this file rename; the test asserts the old name |
| `test_top_level_keys_are_exactly_the_documented_ones_in_order` | added `script_sha256`, `total_frames` | asserts the exact top-level key list, which the new schema extends |
| `test_beat_keys_are_emitted_in_the_documented_order` | added the four timing keys | asserts the exact beat key order, which the new schema extends |
| `test_written_json_preserves_the_documented_key_order` | same | same, through serialisation |

These are the three vacuity-fix tests added at the end of Task 1 plus the
existing `write_plan` path assertion. The brief's Step 1a was written against the
schema but not against those three later additions. In every case I changed only
the schema-derived literal and left the assertion's shape and intent untouched.

**One test now has a misleading name and I left it alone.**
`test_total_sec_is_the_sum_of_holds_times_pace` still passes (10.5 at pace 1.0)
but its name asserts the derivation this task deliberately abandoned. It is not
on the amendment list, so I did not touch it. It should be renamed — and, given
§5, it is the *only* test that actually dies to mutant 7, so it is carrying
weight its name misdescribes.

**Unused fixture.** `test_metadata_and_beats_come_from_the_same_read` takes a
`monkeypatch` parameter it never uses. The code block is authoritative, so I
transcribed it as written. Harmless; worth dropping next time the file is touched.

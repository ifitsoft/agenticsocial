# Task 6 Report: Gate fixes — the four (five) findings that block the merge

**Branch:** `feat/video-phase-01-scaffolding`
**Commits:** `24a1a03` (tests, RED) · `d469bdb` (implementation, GREEN)
**Baseline:** 311 passed · **Final:** 319 passed

---

## 1. What I changed

**F2 — the approval gate is now checked against disk.** `set_status` reads
`script.yaml` first, parses the status it finds there, and gates on *that*. A
caller holding a stale `Episode` can no longer walk a `draft` file into
`RENDERING`. An unparseable status on disk now raises `EpisodeError` from
`set_status` (previously only `load_episode` checked it), which is what makes
`Status(raw)` safe to build there at all.

**F3 — an ambiguous single-document `script.yaml` is refused.** `_read_meta`
raises when `beats` appears in the metadata document and there is no second
document. The old behaviour parsed the operator's beats as metadata, then
`_compose` fabricated `beats: []` as document 2 — comments destroyed and the
beats contract claiming an empty episode. Refusal is the point: the alternative
is silently reflowing hand-written beats through `safe_dump`.

**F5 — `create_episode` claims the directory atomically outside the cleanup
block.** `d.mkdir(parents=True)` is now its own `try`, converting
`FileExistsError` into `EpisodeError("episode already exists: …")`. The
`rmtree` cleanup covers only the subdirectory/script build that follows, so a
losing concurrent create can never delete the winner's finished episode. The
existing `d.exists() or d.is_symlink()` precheck is kept — it gives the clean
message in the common case; `mkdir` is the race-safe backstop.

**F1 — `--series` goes through `_text()`** in both `video new` and `video list`.
Fourth instance of D-036 closed.

**F4 — the 3d tripwire now fires.** See §3, mutant 2.

## 2. TDD evidence

### RED — after Step 1, before any implementation (`/tmp/t6_red.txt`)

```
FAILED tests/test_video_cli.py::test_series_option_with_undecodable_text_fails_cleanly - UnicodeEncodeError: 'utf-8' codec can't encode character '\udce9' in positi...
FAILED tests/test_video_episode.py::test_set_status_checks_the_gate_against_disk_not_memory - Failed: DID NOT RAISE TransitionError
FAILED tests/test_video_episode.py::test_set_status_refreshes_the_object_from_disk - agenticsocial.models.TransitionError: cannot move draft -> approved; allowe...
FAILED tests/test_video_episode.py::test_set_status_rejects_an_unreadable_status_on_disk - Failed: DID NOT RAISE EpisodeError
FAILED tests/test_video_episode.py::test_script_without_a_separator_is_refused_not_reflowed - Failed: DID NOT RAISE EpisodeError
FAILED tests/test_video_episode.py::test_a_lost_create_race_does_not_delete_the_winner - FileExistsError: [Errno 17] File exists: '/Volumes/aabdukarimExternalSSD/aa...
======================== 6 failed, 313 passed in 1.05s =========================
```

### GREEN — after Step 2 (`/tmp/t6_final.txt`)

```
============================= 319 passed in 0.78s ==============================
```

Two of the eight tests added in Step 1 were green on arrival by design:
`test_metadata_only_script_is_still_allowed` (a guard that F3's refusal must not
over-reach) and the briefed `test_create_over_an_existing_dir_does_not_delete_it`
(see §5.3). Both are shown to be non-vacuous in §3.

## 3. Mutation results

`git checkout -- src` between every mutant; `git status --porcelain` verified
clean after each.

| # | Mutant | Result | Killed by |
|---|--------|--------|-----------|
| 1 | `set_status` gates on `episode.status` | **2 failed**, 317 passed | `test_set_status_checks_the_gate_against_disk_not_memory`, `test_set_status_refreshes_the_object_from_disk` |
| 2 | `_split` searches from `start.end()` (**the 3d mutant that survived**) | **1 failed**, 318 passed | `test_empty_metadata_document_keeps_its_beats` |
| 3 | drop the `"beats" in meta` refusal | **1 failed**, 318 passed | `test_script_without_a_separator_is_refused_not_reflowed` |
| 4 | drop `_text(series, …)` in `video_new` | **1 failed**, 318 passed | `test_series_option_with_undecodable_text_fails_cleanly` |
| 5 | `d.mkdir` back inside the cleanup `try` | **1 failed**, 318 passed | `test_a_lost_create_race_does_not_delete_the_winner` |
| 6 (extra) | over-broad refusal: `if beats_text is None:` | **5 failed**, 314 passed | `test_metadata_only_script_is_still_allowed` + 4 pre-existing |

### Mutant 2 in isolation — proving F4 is actually fixed

Mutant 2 alone dies at the *F3 refusal*, not at the byte assertion — which would
leave open whether the strengthened tripwire does any work. I applied mutants 2
and 3 **together**, removing the refusal so only the assertion can catch it:

```
--- mutants 2+3, new assertion ---
E        +    where <built-in method endswith of bytes object at 0x10b738b10> = b'---\nbeats:\n- type: statement\nstatus: in_review\n---\nbeats: []\n'.endswith
FAILED tests/test_video_episode.py::test_empty_metadata_document_keeps_its_beats
============================== 1 failed in 0.17s ===============================
--- mutants 2+3, OLD substring assertion (what the gate review found) ---
tests/test_video_episode.py .                                            [100%]
============================== 1 passed in 0.17s ===============================
```

The corrupted output is `b'---\nbeats:\n- type: statement\nstatus: in_review\n---\nbeats: []\n'`.
It contains `- type: statement`, which is exactly why the old substring
assertion passed on corruption. The `endswith` form kills it. F4 confirmed
closed, and the strengthening is load-bearing rather than incidental.

## 4. Files changed

- `src/agenticsocial/video/episode.py` — `set_status`, `_read_meta`, `create_episode`
- `src/agenticsocial/video/cli.py` — `video_new`, `video_list`
- `tests/test_video_episode.py` — 1 replacement + 7 added (`Path` import added)
- `tests/test_video_cli.py` — 1 added

Commits: `24a1a03` (tests), `d469bdb` (implementation). Nothing under `docs/`
staged. `git status --porcelain -- src tests` is empty.

## 5. Issues and concerns

### 5.1 Re-running the F2 bypass by hand

Before (`/tmp/t6_repro_before.txt`):

```
on disk now      : draft
stale object says: approved
after set_status : rendering    *** GATE BYPASSED ***
```

After (`/tmp/t6_repro_after.txt`):

```
on disk now      : draft
stale object says: approved
after set_status : refused — TransitionError cannot move draft -> rendering; allowed next: in_review
```

**Any other way to reach RENDERING without passing the gate?** Not in Phase 1
code. `grep` over `src/` shows `video/episode.py::set_status` is the only writer
of an episode status: the only `meta["status"] =` and the only `_compose` call
that carries an existing episode's metadata. `create_episode` always writes
`draft`. `RENDERING` has no other producer — Phase 1 ships no `render` command.

Three residual ways in, all outside the code's reach and all pre-existing:

1. **Editing `script.yaml` by hand.** `status: rendering` typed into the file is
   accepted by `load_episode`. The gate governs *transitions*, not the file; the
   file is operator-owned. Spec §10's `script_sha256` is the intended answer and
   Phase 1 does not implement it.
2. **TOCTOU inside `set_status` itself.** The read, the gate check, and the
   write are not atomic. A human approving between our read and our write is
   harmless; a human *un*-approving in that window would be overwritten. This is
   now a microsecond-wide window against a human action, versus the previous
   unbounded window (a stale object lives as long as its holder). No locking was
   added — out of scope, and it would need a real advisory-lock design.
3. **`Status.FAILED → RENDERING`** is a legal edge in `VIDEO_TRANSITIONS`
   (`models.py:48`), so a failed render can be retried without re-approval. That
   is intended by the table and unchanged here, but worth naming: it is the one
   path to `RENDERING` that does not pass through `APPROVED`. If Phase 7 ever
   lets a *failed* episode be edited before retry, that edge becomes a hole.

**Related, not fixed:** `Workspace.set_status` for text variants
(`workspace.py:206`) has the identical shape — `assert_transition(v.status, …)`
against an in-memory `Variant`. It is less exposed (the CLI loads and acts in
one process) but it is the same bug class. Out of scope for this task; flagging
it so it does not get discovered as a Phase 7 surprise.

### 5.2 Does gating on disk break any legitimate caller?

No current caller, and I do not think it breaks a future batch one either.

Phase 1's only callers are the tests; no CLI command calls `set_status` yet.
The behaviour change for any caller is narrow: it now diverges only when the
in-memory status and the on-disk status **disagree**, i.e. exactly when the old
code was wrong. When they agree — the case for every episode loaded and acted on
without an intervening external write — behaviour is byte-identical.

A batch operation holding several `Episode` objects is *helped*, not hurt: it is
the canonical way to end up with a stale object (load ten, act on them over
several seconds, the operator edits one meanwhile). Under the old code that
batch would write a transition the file never permitted; under the new code it
gets a `TransitionError` naming the real current status. Two consequences a
batch author should know, both now covered by tests:

- `set_status` refreshes `episode.status` and `episode.meta` from what it read,
  so an object that was stale becomes current (`test_set_status_refreshes_the_object_from_disk`).
- `set_status` can now raise `EpisodeError`, not just `TransitionError`, if the
  file's status became unparseable. A batch loop catching only `TransitionError`
  will now propagate. Worth a line in Phase 7's batch code.

One ordering detail: the read now happens *before* the gate check. Nothing is
written unless the check passes, so
`test_a_rejected_transition_does_not_touch_the_file` still holds (it passes).
The cost is that a rejected transition now performs a read it previously
skipped — irrelevant at this scale.

### 5.3 Auditing my own tests: what would each do if the code did nothing?

I ran this test against all eight. **One failed it, and I fixed it before
committing.**

**The failure — the briefed F5 test is vacuous as written.**
`test_create_over_an_existing_dir_does_not_delete_it` calls `create_episode`
twice in one process. The `d.exists()` precheck — which the brief explicitly
says to keep — answers first and raises `EpisodeError` before control ever
reaches the `mkdir` that F5 is about. So the test passes identically with the
fix, without the fix, and with mutant 5 applied. It never executes the branch it
names. (I also read the unused `monkeypatch` in its signature as a hint that
this was anticipated.)

The brief's code block is authoritative and the brief forbids weakening existing
assertions, so **I kept it exactly as written and added a second test** that
reaches the real branch: `test_a_lost_create_race_does_not_delete_the_winner`
monkeypatches `Path.exists` to answer `False` for the target directory only —
which is precisely what a concurrent winner does by creating the directory after
we looked — so `mkdir` raises `FileExistsError` and the loser path is the code
under test. It was RED in Step 1 (`FileExistsError` escaping, and the winner's
`script.yaml` deleted) and it is what kills mutant 5. **Flagging this as a
brief/behaviour disagreement per the ground rules.**

The other seven:

| Test | If the code did nothing |
|---|---|
| `test_set_status_checks_the_gate_against_disk_not_memory` | **fails** — `DID NOT RAISE TransitionError` (RED, verified) |
| `test_set_status_refreshes_the_object_from_disk` | **fails** — `TransitionError: draft -> approved` (RED, verified) |
| `test_set_status_rejects_an_unreadable_status_on_disk` | **fails** — `DID NOT RAISE EpisodeError` (RED, verified) |
| `test_script_without_a_separator_is_refused_not_reflowed` | **fails** — `DID NOT RAISE EpisodeError` (RED, verified) |
| `test_empty_metadata_document_keeps_its_beats` | **fails** under the mutant it exists to pin — demonstrated in §3 with the refusal removed, alongside the old assertion passing on the same corrupted bytes |
| `test_series_option_with_undecodable_text_fails_cleanly` | **fails** — `UnicodeEncodeError` (RED, verified). Uses the `run()` helper with `catch_exceptions=False`, so a traceback cannot masquerade as a clean `_fail` (D-035) |
| `test_metadata_only_script_is_still_allowed` | **passes** — and it is meant to. It is a boundary guard, not a change-driver: it constrains F3's refusal from over-reaching. To show it is not merely decorative I ran a sixth mutant (`if beats_text is None:`) and it dies, along with four pre-existing tests. Flagged honestly as green-on-arrival rather than presented as TDD evidence |

Two further notes on assertion strength, since that is what the gate review
found:

- `test_set_status_checks_the_gate_against_disk_not_memory` asserts both the
  raise *and* that disk still reads `draft`. Without the second assertion an
  implementation that raised after writing would pass.
- `test_a_lost_create_race_does_not_delete_the_winner` compares
  `read_bytes()` before and after, not `exists()`. `exists()` would be satisfied
  by an implementation that deleted and recreated the episode — which is the
  data loss F5 is about.

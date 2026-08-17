# Phase 1 gate review — `feat/video-phase-01-scaffolding`

**Reviewer:** QA (adversarial, whole-branch). Did not write any of this code.
**Base:** 311 tests passing, 38 commits ahead of `main`, nothing merged.
**Read:** spec §§3, 5, 6, 7, 10, 11; the plan and its exit criteria; DECISIONS
D-001..D-043. Did **not** read any `task-*-report.md`.

---

## Verdict

**merge-after-fixes.**

The branch is in far better shape than a nine-task phase with four extra defect
tasks usually is. The transition tables are pinned exactly and survived every
mutant I threw at them; `series.py` — the module that never had a review — killed
30 of 34 mutants and none of the survivors is a correctness bug in the loader.
The path-safety work of Task 5 holds against everything I could throw at it from
a real subprocess.

Three things stop me signing a clean merge:

1. An operator-typable input still reaches a traceback (`--series`). D-040 draws
   its own line at "none reaches a traceback". This is on the wrong side of the
   leader's own line, and it is a two-line fix.
2. `set_status` enforces the approval gate against a **stale in-memory status**
   while writing against the **on-disk file**. I reached `rendering` from an
   episode whose `script.yaml` said `draft`. D-032 F6 recorded a weaker version
   of this and deferred it to Phase 7; the recorded version understates it.
3. A test written specifically as a tripwire for the D-033 fix
   (`test_empty_metadata_document_keeps_its_beats`) **does not trip**. The
   mutant it names survives. That is a fourth instance of D-035 in the very test
   that was added to close the third.

None of these is architectural. F1 and F3 are small; F2 is small but wants a
decision. Fix F1–F4 and I would merge without hesitation.

---

## Findings, ranked

### F1 · high · Operator input still reaches a traceback via `--series`

`src/agenticsocial/video/cli.py:108` (and `:126`) — the `--series` option is the
only operator-typable string in the video CLI that is **not** passed through
`_text()`. `src/agenticsocial/video/series.py:171` compounds it: the
missing-series message interpolates the slug bare (`f"no series '{slug}' — …"`)
rather than with `!r`, so a lone surrogate survives into the message that
`typer.secho` then tries to encode.

Reproduced with the real CLI in a subprocess (not `CliRunner`):

```
$ AGSOC_WORKSPACE=/tmp/qa5/ws agsoc video new 2026-01-01 --series $'caf\xe9'
… rich traceback panel …
UnicodeEncodeError: 'utf-8' codec can't encode character '\udce9' in position 14:
surrogates not allowed
exit=1
```

`agsoc video list --series $'caf\xe9'` does the same. This is exactly the D-025
defect that commit `8bd2cb3` ("fix: no operator input reaches a traceback")
claimed to close, on the one input the fix missed — a fourth instance of D-036
(guard added to some call sites, not all).

Note the reason `slug`/`episode` do *not* traceback without `_text()` is
incidental: `_validate_slug` and `EPISODE_ID_RE` use `{slug!r}`, and `repr()`
escapes the surrogate to ASCII. The guard is load-bearing only where a message
uses plain interpolation — which is every "not found" message in both modules.

**Fix:** run `series` through `_text()` in `video_new` and `video_list`, and use
`!r` in the "no series" / "no episode" / "matches multiple" messages in both
modules. Both halves, not either.

**Test gap:** mutants C3 (`skip _text on slug`) and C5 (`skip _text on episode`)
both survive. Only `--name` has a surrogate test
(`test_a_name_that_cannot_be_encoded_is_rejected_cleanly`). Four operator inputs,
one tested.

---

### F2 · high (importance) / deferred-harm · The approval gate is checked against memory and written against disk

`src/agenticsocial/video/episode.py:218-225`:

```python
def set_status(episode: Episode, target: Status) -> None:
    assert_transition(episode.status, target, VIDEO_TRANSITIONS)   # in-memory
    meta, beats_text, nl = _read_meta(episode.script_path)          # disk
    meta["status"] = target.value
```

The guard reads `episode.status`; everything after it reads the file. Those can
disagree. Reproduced:

```
disk status now: draft
RESULT disk status: rendering
```

An `Episode` held at `approved` moved an on-disk `draft` straight to `rendering`
— the one edge spec §8.4 and §10 make unreachable without a human. Any long-lived
`Episode`, any second process, any operator who edits `script.yaml` between load
and act, opens this. `_read_meta` is *already* reading the file two lines later,
so validating against the disk status costs nothing.

D-032 F6 recorded this as "*Stale `Episode` can regress `approved` → `in_review`;
no disk re-check*" and sent it to Phase 7 on the rationale that "the approve gate
owns freshness". I think that adjudication is under-scoped on both halves:

- The consequence is not a regression to `in_review`, it is a **gate bypass to
  `rendering`**.
- The bug is in `set_status`, not in the approve gate. Deferring it to Phase 7
  assigns it to a component that will *call* the broken function rather than the
  one that contains it, and Phase 7 will be written against the assumption that
  `set_status` already checked.

It is not *harm today* — Phase 1 ships no command that calls `set_status`, so
nothing can reach it yet. That is precisely why it is cheap to fix now and
expensive to fix later.

**Fix:**

```python
    meta, beats_text, nl = _read_meta(episode.script_path)
    current = Status(meta.get("status", Status.DRAFT.value))   # reuse load_episode's parse
    assert_transition(current, target, VIDEO_TRANSITIONS)
```

...and a test that reverts the file under a held `Episode` and asserts
`TransitionError`. If you keep the deferral, please re-word D-032 F6 so the
Phase 7 reader learns that the gate itself is reachable, not just that a status
can regress.

---

### F3 · medium · A single-document `script.yaml` silently becomes an empty episode

`src/agenticsocial/video/episode.py:42-63` (`_split`) and `:101-105` (`_compose`).

When `script.yaml` has a leading `---` but no separator, `_split` returns
`beats_text = None` and hands the **entire** file to `_parse_meta`. If beats live
in that document — a natural hand-edit, and the shape `test_load_tolerates_a_
single_document_script` explicitly says must not crash — `set_status` then
re-`safe_dump`s them into document 1 and appends a fabricated `beats: []` as
document 2:

```
in:  ---\nepisode: b\nseries: s1\nstatus: draft\nbeats:\n  # hand written comment\n  - type: statement\n    text: hello\n
out: ---\nepisode: b\nseries: s1\nstatus: in_review\nbeats:\n- type: statement\n  text: hello\n---\nbeats: []\n
```

The comment is gone, the formatting is reflowed, and — the part that matters —
**document 2, which is the beats contract, now says the episode has no beats.**
A Phase 3 parser reading document 2 gets an empty script for an episode the
operator wrote. That is silent data loss plus a silent wrong answer, both on the
harm side of D-040's line.

The same mechanism truncates metadata when a `---` line appears inside a
metadata block scalar — `note: |` containing `---` loses everything after it,
with no error:

```
in:  note: |\n  before\n---\n  after\n   →   out: note: before   ("after" leaks into document 2)
```

**Fix (minimal, does not require a beats parser):** if `beats_text is None` and
the parsed metadata contains a `beats` key, raise `EpisodeError` naming the file
and telling the operator to add the `---` separator. Refusing is correct here —
`_compose` cannot honestly round-trip a shape it cannot represent.

---

### F4 · medium · The test written to pin the D-033 fix does not pin it

`tests/test_video_episode.py:547-553`:

```python
def test_empty_metadata_document_keeps_its_beats(series):
    """Pins the 3d mutant that survived: searching from start.end() instead of
    start.end() - len(nl) discards the beats of an empty-metadata script."""
    ...
    assert b"- type: statement" in ep.script_path.read_bytes()
```

I applied exactly that mutant. **All 311 tests still pass.** Verified output:

| | document 2 |
|---|---|
| correct | `---\nstatus: in_review\n---\nbeats:\n  - type: statement\n` |
| mutant | `---\nbeats:\n- type: statement\nstatus: in_review\n---\nbeats: []\n` |

The mutant's beats got swallowed into document 1 by the F3 mechanism above, so
the substring the test looks for is still *somewhere* in the file — while
document 2 is `beats: []`, i.e. an empty episode. A substring-anywhere assertion
cannot distinguish "preserved" from "relocated into the wrong document". This is
D-035 form 1 (a fixture broken in the wrong dimension) reappearing inside the
test that was added to close D-035's third instance.

**Fix:** assert on document 2's *bytes*, the way the byte-level block further
down the same file already does:

```python
raw = ep.script_path.read_bytes()
assert raw.split(b"\n---\n", 1)[1] == b"beats:\n  - type: statement\n"
```

---

### F5 · medium-low · `create_episode`'s cleanup destroys a concurrent winner's episode

Sibling asymmetry with a destructive consequence.

- `series.py:154-163` — `(d / "episodes").mkdir(parents=True)` is **outside** the
  `try`. A `FileExistsError` from a racing process therefore propagates as an
  `OSError` and *nothing is deleted*. Correct.
- `episode.py:123-132` — the `mkdir` loop is **inside** the `try`, whose
  `except BaseException` calls `shutil.rmtree(d, ignore_errors=True)`.

So two concurrent `agsoc video new 2026-08-14`: both pass the `d.exists()` check,
A completes and writes `script.yaml`, B's `(d/"sources").mkdir()` raises
`FileExistsError`, B's handler deletes A's finished episode. Confirmed by
simulating the interleaving:

```
A wrote: ['out', 'probe', 'script.yaml', 'sources']
after B's cleanup, exists: False
```

Low probability in a single-operator local-first tool, but the failure mode is
silent destruction of an episode the operator created, and the fix is to match
the sibling: move the `mkdir` loop above the `try`, or only `rmtree` when this
call is the one that created `d`.

---

### F6 · medium-low · `list_series`'s strictness — the D-018 contract — is unpinned

Mutant **S33** (make `list_series` swallow `SeriesError` and return partial
results) **survives the whole suite.** `list_episodes` has
`test_list_episodes_is_strict_about_a_corrupt_episode`; `list_series` has no
counterpart. D-018 makes the strict/lenient split load-bearing — `agsoc series
list` deliberately does *not* use `list_series` — and nothing enforces the half
of it that lives in `series.py`. Exactly the debt this gate was meant to settle.

**Fix:** the mirror test. Two corrupt-series lines.

---

### F7 · low · Two "rejection happens before any write" tests assert on the wrong directory

- `tests/test_video_series.py:223-226` asserts `not (ws.root.parent / "escape").exists()`.
  A `../escape` slug would land in **`ws.root / "escape"`**.
- `tests/test_video_episode.py:536-539` asserts `not (series.episodes_dir.parent.parent / "escape").exists()`.
  A `../escape` id would land in **`series.dir / "escape"`** (one level lower).

Verified by printing both paths. Neither assertion can ever fail regardless of
what the code does; the `pytest.raises` in the same tests is doing all the work.
Harmless today because the guards are correct, but these are the tests that would
be pointed at if the guard regressed.

---

### F8 · low · `is_file()` vs `exists()` is unpinned in **both** modules

Mutants **S8** (`load_series`) and **E2** (`load_episode`) both survive. With
`exists()`, a `series.toml` that is a *directory* stops producing the actionable
"no series 'x' — create it with `agsoc series new x`" and instead falls through
to `open()` → `IsADirectoryError` → "cannot read series.toml". Still a
`SeriesError`, so `test_unreadable_series_toml_raises_series_error`
(`tests/test_video_series.py:264-269`) passes either way — that test believes it
is exercising the `except OSError` branch and is in fact exercising the
missing-file branch. The `except OSError` clause in `load_series` is reachable
only via permissions, and is untested.

This is the exact `is_file()`/`exists()` axis D-036 names. It is currently right
in both modules and pinned in neither.

---

### F9 · low · Untested error clauses and unpinned metadata behaviour (mutation survivors)

- **C13** — `video_new`'s `except OSError` is untested (the series equivalent is
  covered by the read-only-workspace test). Sibling asymmetry in the tests.
- **C15** — `video_list` catching `EpisodeError` from `episode_ids` is untested.
- **E21** — `resolve_episode`'s exact-match-wins precedence is unpinned: with
  episodes `ep` and `ep-2`, removing the exact-match branch would make `ep`
  ambiguous, and no test notices.
- **E10 / E11** — `safe_dump(sort_keys=False, allow_unicode=True)` is unpinned.
  Dropping `allow_unicode` would `\uXXXX`-escape every non-ASCII metadata value
  on the next status change; for a news product this is near-certain to bite.
- **E27 / E28** — `_new_meta`'s `pace` and `date_long` fields are unpinned;
  removing either passes.

---

### F10 · note · Smaller observations, no fix demanded

- `series.py:207-210` — the acts error message says "write `[[structure.acts]]`
  blocks, not a bare `acts = value`", but spec §6 documents acts as an inline
  array of tables (`acts = [ { id = … }, … ]`). I verified that form loads
  correctly, so the message misdirects an operator who copied the spec. One
  sentence.
- `episode.py:133-139` — `create_episode` calls `_new_meta` **twice** and returns
  an `Episode` built from the second call rather than round-tripping through
  disk. `scaffold_series` returns `load_series(...)`. If `_compose` ever altered
  metadata, the returned object would silently disagree with the file.
- `episode.py:31` imports `_assert_safe_name` — a private name — from
  `series.py`. It is shared path-safety policy, not series policy; it belongs in
  `models.py` or a `_paths.py` so neither module owns the other's private API.
- `MAX_NAME_LEN` (series) and `MAX_ID_LEN` (episode) are the same constant under
  two names.
- `video_new` scaffolds the `default` series as a side effect even when the
  command then fails on a bad episode id. Cosmetic; the directory is inert.
- `_fail` uses `err=False`, so errors go to stdout. This matches the existing
  `src/agenticsocial/cli.py:33`, so it is a project convention, not a new
  asymmetry — but it means `agsoc series list | grep` swallows the diagnostics
  that D-018 exists to surface.

---

## Harness-blindness audit (D-035)

For each negative test I asked: *what would this test do if the code did nothing?*

**Tests that cannot fail as written:**

| Test | Why |
|---|---|
| `test_video_episode.py:547 test_empty_metadata_document_keeps_its_beats` | **F4** — substring-anywhere assertion; the named mutant survives it. Verified by running the mutant. |
| `test_video_series.py:223 test_slug_rejection_happens_before_any_write` | **F7** — asserts on `ws.root.parent`, escape target is `ws.root`. |
| `test_video_episode.py:536 test_invalid_episode_id_is_rejected_before_any_write` | **F7** — asserts on `ws.series_dir`, escape target is `series.dir`. |
| `test_video_series.py:264 test_unreadable_series_toml_raises_series_error` | **F8** — `is_file()` short-circuits before `open()`, so the `except OSError` branch the test is named for is never entered. Passes either way. |

**Tests that are weaker than they read, but do fail on the mutant they target:**

| Test | Weakness |
|---|---|
| `test_video_episode.py:468 test_mixed_line_endings_preserve_beats_bytes` | `assert beats.encode() in read_bytes()` — a `set_status` that wrote nothing at all passes. No preservation test in this file asserts the status was actually persisted, so a no-op `set_status` passes the entire byte-preservation block. Pair one of them with a `load_episode(...).status is IN_REVIEW`. |
| `test_video_episode.py:483 test_first_byte_of_beats_is_never_eaten` | `raw.replace(b"beats:", b"")` then a `not in` — depends on the corruption producing that exact residue. |
| `test_video_episode.py:528 test_invalid_episode_id_is_rejected` | `match="episode id"` matches both the `_assert_safe_name` and the regex message, so it cannot tell you which guard fired (E24 is an equivalent mutant partly for this reason). |
| `test_video_cli.py:37 test_series_new_rejects_a_bad_slug` | `"slug" in output` matches almost any slug-related message. |

**Forms I checked for and did not find:**

- Symmetric encode/decode around an assertion — the TOML round-trip tests decode
  with `tomllib`, a genuinely independent parser. Clean.
- A runner converting failures into return values — `run()` in
  `test_video_cli.py:10` uses `catch_exceptions=False` with a docstring
  explaining why. D-035's third instance is properly closed. I still re-ran every
  behavioural claim through a real subprocess and found one thing `CliRunner`
  had not been pointed at (F1) — because no test points at `--series` at all,
  not because the runner hid it.
- Byte-level fixtures cancelling their own transformation — the `_write_bytes` /
  `_beats_bytes` block correctly uses `write_bytes`/`read_bytes` on both sides.
  Clean; this is the strongest part of the suite.

---

## Sibling asymmetry list (D-036)

`series.py` vs `episode.py`, every difference I found, whether or not it matters:

| # | Axis | `series.py` | `episode.py` | Matters? |
|---|---|---|---|---|
| 1 | cleanup scope | `mkdir` **outside** the `try`; `rmtree` only covers the writes | `mkdir` loop **inside** the `try`; `rmtree` covers it | **Yes — F5**, destroys a racing winner's episode |
| 2 | error-message interpolation | `no series '{slug}'` — bare | `no episode '{ep_id}'`, `'{query}' matches multiple`, `no episode matching '{query}'` — bare | **Yes — F1**, the traceback path |
| 3 | CLI `_text()` coverage | slug ✔, `--name` ✔ | episode ✔, `--series` ✘ | **Yes — F1** |
| 4 | strictness test for `list_*` | absent | `test_list_episodes_is_strict_about_a_corrupt_episode` | **Yes — F6** |
| 5 | `except OSError` on create, tested | yes (read-only workspace) | no (**C13** survives) | Minor — F9 |
| 6 | validation structure | `_validate_slug()` helper, length then regex | length + regex inlined in `create_episode` | Cosmetic |
| 7 | constructor return | `scaffold_series` returns `load_series(...)` (round-trips through disk) | `create_episode` builds `Episode` from a second `_new_meta()` call | Latent — F10 |
| 8 | `shutil` import | module top | inside the `except` block | Cosmetic |
| 9 | length constant | `MAX_NAME_LEN` | `MAX_ID_LEN` | Cosmetic |
| 10 | name regex | `^[a-z0-9][a-z0-9-]*$` | `^[a-z0-9][a-z0-9.-]*$` (dots for dates) | Intentional |
| 11 | resolver | none — series are addressed exactly | `resolve_episode` (substring, ambiguity) | Intentional |
| 12 | content validation | heavy (`_table`, formats, target_sec, acts, warm_acts) | status only | Intentional (Phase 3 owns beats) |
| 13 | ownership of `_assert_safe_name` | defines it | imports the private name | Layering — F10 |
| 14 | `is_file()` | `load_series` ✔, unpinned (**S8**) | `load_episode` ✔, unpinned (**E2**) | Symmetric but untested — F8 |
| 15 | `d.exists() or d.is_symlink()` | ✔ | ✔ | **Symmetric — the D-036 fix held** |
| 16 | enumerator OSError → domain error | ✔ (`series_slugs`) | ✔ (`episode_ids`) | **Symmetric** |
| 17 | UTF-8 decode → domain error | ✔ | ✔ | **Symmetric** |
| 18 | atomic writes | ✔ | ✔ | **Symmetric** |

Rows 15–18 are the ones previous reviews fixed, and they are genuinely symmetric
now. Rows 1–4 are new.

---

## Mutation results

Harness: replace one source pattern, run the **full** suite, restore. 87 mutants
across the four modules. Survivors listed with an equivalence judgement.

### `series.py` — the unreviewed module (34 mutants, 30 killed)

Killed, notably: every `_assert_safe_name` weakening (drop `..`, drop backslash
and NUL, no-op entirely, skip the call in `load_series`, skip it in
`scaffold_series`); both `SLUG_RE` and length-limit weakenings; the `is_symlink`
guard; `rmtree` cleanup; `_table` type-checking; `target_sec` bool and zero;
formats default / unknown / empty; acts and warm_acts validation; **every**
`_toml_str` escaping branch (short escapes, C0, U+007F); the `series_slugs`
`is_file` filter and its `OSError` wrap; sort order; and every loader default
(`name`, `cadence`, `register`, `byline`, `tolerance_sec`, `design`,
`coverage.json` conventions).

That is a strong result. The D-024 promise — accepting Task 2c on mutation
evidence — is honoured by the code. The *loader* is well tested.

| Survivor | Judgement |
|---|---|
| **S33** `list_series` → lenient | **Real gap — F6.** D-018's strict half is unenforced. |
| **S8** `is_file()` → `exists()` | **Real gap — F8.** Error quality changes, class does not. |
| **S27** scaffold creates an extra `eps/` directory | Weak: nothing pins the *exact* contents of a scaffolded series directory. Low value on its own; worth one `sorted(d.iterdir())` assertion. |
| **S17** `sorted()` → source order | **Order-lucky, not a survivor.** Re-ran as an explicit `reverse=True` (**S17b**): killed. |

### `episode.py` (31 mutants, 24 killed, 1 not applied)

Killed, notably: `set_status` skipping `assert_transition` **and** `set_status`
using the *text* table; the in-memory update; both `\r` alternations in
`_DOC_START_RE` and `_SEP_RE`; `head.replace("\n", nl)`; `newline=""` on read;
the `beats: []` default; the non-mapping metadata guard; the
`UnicodeDecodeError` and `OSError` clauses; all three `_assert_safe_name` call
sites in `load_episode`/`resolve_episode`; the id regex and length; sort order;
`SUBDIRS`; the `is_symlink` guard; `rmtree`.

| Survivor | Judgement |
|---|---|
| **E12** `_split` searches from `start.end()` instead of `start.end() - len(nl)` | **Real — F4.** The test named for this mutant does not kill it. Verified end-to-end; the mutant emits `beats: []` as document 2. |
| **E2** `is_file()` → `exists()` | **Real — F8**, sibling of S8. |
| **E10** `sort_keys=True` | Real but low: metadata key order churns on every status change. Document-1 churn is D-040-accepted; still unpinned. |
| **E11** drop `allow_unicode` | **Real — F9.** Non-ASCII metadata would be `\uXXXX`-escaped on the next status change. Unpinned. |
| **E21** drop exact-match precedence in `resolve_episode` | Real but low — F9. Needs an `ep` / `ep-2` fixture. |
| **E27 / E28** drop `pace` / `date_long` from `_new_meta` | Real but low — F9. Nothing pins the stub metadata shape. |
| **E24** `create_episode` skips `_assert_safe_name` | **Equivalent.** `EPISODE_ID_RE` already rejects `/`, `\`, NUL, `.`, `..` and empty. The guard is defence in depth. |
| **E18** drop `newline=""` from `atomic_write` | **Equivalent on POSIX.** `newline=None` translates `\n` → `os.linesep` = `\n` here. It is a live difference on Windows only, so it cannot be tested on this platform. Worth a comment in `workspace.py` saying so. |
| **E15** | Not applied (pattern ambiguous). |

### `video/cli.py` + `video/models.py` (22 mutants, 18 killed)

Killed, notably: `_fail` exit code; `_text` no-op; `--name` guard; both
`list`-dies-on-one-broken-member mutants; `?` vs `0` episode count;
`autocreate any series`; `autocreate off`; `DEFAULT_SERIES` rename; swapping
`series list` onto the strict `list_series`; the `WorkspaceError` clause; and
**every** on-disk name in `models.py` (`script.yaml`, `episodes`, `out`,
`sources`) plus the `FORMATS` tuple. The spec §5 layout is properly pinned.

| Survivor | Judgement |
|---|---|
| **C3 / C5** skip `_text()` on slug / episode id | **Near-equivalent by accident** — `!r` in those messages saves them. Real as a test gap, and the reason F1's fix must cover message formatting too. |
| **C13** `video_new` drops `except OSError` | Real — F9. |
| **C15** `video_list` drops `EpisodeError` from the guard | Real — F9. |

---

## Spec coverage

Walked spec §§5, 6, 10, 11 and the plan's File Structure table.

**Implemented and correct:**

- §5 layout — `series/<slug>/{series.toml, coverage.json, episodes/}` and
  `episodes/<id>/{sources,out,probe}/ + script.yaml`. Exactly the spec minus
  `brief.md` and `claims.json`, which the plan assigns to later phases. Every
  directory name is mutation-pinned.
- §6 — the scaffolded `series.toml` carries every key the spec shows, with the
  spec's own comments and values. I verified the spec's literal inline-table
  `acts = [ { id = … } ]` form loads correctly, as well as the
  `[[structure.acts]]` form the template suggests.
- §10 — `VIDEO_TRANSITIONS` matches the spec diagram edge for edge, `rendered`
  is terminal (D-006), `publishing`/`published` are present-but-empty for
  totality, and both tables are pinned exactly *and* behaviourally. This is the
  best-tested part of the branch: every table mutant died.
- §11 — `series new`, `series list`, `video new`, `video list` are the four
  commands Phase 1 owns; nothing later-phase leaked in.
- `coverage.json`'s shape (`series` / `conventions` / `episodes`) matches
  `engine/coverage.json`, so the Phase 11 relocation will not need a migration.

**In scope with no implementation — correctly, per the plan:** `script_sha256`,
`claims.json`, and the `approve`/`render` commands. Consequence worth stating
plainly: **Phase 1 ships `set_status` with no caller.** The approval gate is
enforced only by a function nothing invokes yet, which is why F2 is cheap now.

**Implemented without authorisation:** nothing. `coverage.json` is explicitly
authorised by the File Structure table.

**Plan constraints:** all writes go through `atomic_write` ✓; no new
dependencies ✓; no status auto-advances ✓; formats are exactly
`vertical`/`wide` ✓; status strings match the plan's literal list ✓. Only the
authorised existing test was modified — `git diff main..HEAD` over the eight
pre-existing test files shows a single three-word change to
`test_status_values_match_spec` ✓.

One un-flagged change to shared code: `TransitionError.__init__` now **requires**
`table`. That is a breaking change to a public exception's signature, deliberate
(D-012) and pinned by `test_transition_error_requires_an_explicit_table`, with no
other construction site in the repo. Correct, worth knowing.

---

## On the D-040 deferrals — is any of them harm?

You asked me to say if I think you drew the line wrong.

- **`%YAML` / leading blank line / missing leading `---` / BOM → `EpisodeError`.**
  Confusion, not harm. Agreed — they refuse loudly and lose nothing. The BOM one
  is the most likely in practice (a Windows editor), and its message
  ("cannot parse script metadata") will not tell the operator what to do; a
  one-line message improvement would be cheap, but the deferral is right.
- **`tolerance_sec` / `name` / `byline` / `register` / `design.*` accept wrong
  types.** Confusion. Agreed — these are read by consumers that do not exist yet,
  and specifying their behaviour now is exactly the speculative work D-040 says
  to avoid.
- **Document 1 comments and block scalars reflowed by `safe_dump`.** Agreed as
  stated — *for the document-1 metadata the tool itself writes*. But note F3:
  the same `safe_dump` reaches operator-written **beats** whenever the separator
  is missing, and there the loss is not cosmetic. That case is not covered by
  this deferral and is on the harm side of your own line.
- **`list_series`/`list_episodes` strict by design.** Agreed, and the CLI uses
  the enumerators correctly. My only issue is that half of it is untested (F6).
- **D-041 symlinks as an operator affordance.** Agreed, and I confirmed the
  reasoning holds under attack: I made `series/` itself a symlink, and made a
  series directory a symlink, and both wrote outside the workspace — but in
  every case the operator had to create the link themselves, and no
  attacker-supplied *string* reaches a link. The destructive cleanup paths
  (`shutil.rmtree`) do not follow links into pre-existing data, because both
  guard on `d.exists() or d.is_symlink()` before creating anything. Confusion,
  not harm. I would only ask that D-041 mention `series/` itself, since the
  wording currently says "series or episodes directories".

---

## What I verified

- `git log`/`git diff main..HEAD` over `src` and `tests`; the eight pre-existing
  test files carry exactly one authorised change.
- Full suite green (311) before, during and after; tree restored and
  `git status --porcelain -- src tests` empty (confirmed twice).
- **Path safety through the real CLI in a subprocess** (`uv run agsoc`, not
  `CliRunner`): `../../victim` traversal, absolute paths on both `series new` and
  `--series`, fullwidth-solidus and one-dot-leader unicode, `AGSOC_WORKSPACE`
  containing `..`, `series/` as a symlink, a series directory as a symlink, a
  `series.toml` naming other paths. Only the D-041-accepted symlink routes reach
  outside, and no directory was created outside the workspace by any string
  input.
- **Byte preservation**: all three line endings and five mixed-ending
  combinations, no trailing newline, trailing tabs and blank lines, a third
  document, astral-plane characters, NUL in beats, repeated status cycles. All
  byte-identical. This part of the implementation is solid.
- **Approval gate**: attempted `rendering` from every other state through
  `set_status`; from a hand-edited `script.yaml`; via a status the enum accepts
  but the table does not; and via a caller-supplied table (`set_status`
  hardcodes `VIDEO_TRANSITIONS` — no injection point). Only the stale in-memory
  route (F2) got through.
- **87 mutants** across four modules, each against the full suite.
- The two escape-test location assertions, by printing the real and asserted
  paths side by side.
- The `--series` traceback, and the F2 gate bypass, both reproduced from a clean
  workspace with printed before/after state.

## What I could not verify

- **Windows behaviour.** `newline=""` in `atomic_write` (E18) is a no-op on
  POSIX. Whether the text pipeline's line endings change for Windows users — a
  "existing text-pipeline behaviour must not change" question — cannot be
  answered on this machine.
- **Real concurrency.** F5 is demonstrated by simulating the interleaving, not by
  racing two processes. The interleaving is the obvious one and the code path is
  unambiguous, but I did not produce it under a real race.
- **Case-insensitive-filesystem collisions.** This machine's `/tmp` is on a
  case-insensitive volume; `SLUG_RE` forbids uppercase so `agsoc`-created names
  cannot collide, but a hand-made `My-Show` and a created `my-show` would be the
  same directory on macOS and different on Linux. Untested either way.
- **`script_sha256` drift in practice.** Phase 1 does not compute it, so the
  byte-preservation guarantee is verified directly rather than through the
  mechanism that will consume it.
- I did not review `engine/` beyond confirming the `coverage.json` schema match.

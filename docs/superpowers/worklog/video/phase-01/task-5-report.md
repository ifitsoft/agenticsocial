# Task 5 Report: Path safety, and stop the two modules drifting

**Branch:** `feat/video-phase-01-scaffolding`
**Commits:** `5555056` (tests, RED) · `94b4797` (implementation, GREEN)
**Full suite:** 311 passed, 0 failed.

---

## 1. What I changed

**`src/agenticsocial/video/series.py`**

- Added `_UNSAFE_CHARS` and `_assert_safe_name(name, kind, error)` above
  `_validate_slug`, verbatim from the brief.
- `scaffold_series`: calls `_assert_safe_name` first, and the existence check
  became `if d.exists() or d.is_symlink():`.
- `load_series`: calls `_assert_safe_name` first — the missing guard that was
  the whole bug.

**`src/agenticsocial/video/episode.py`**

- `from .series import _assert_safe_name` (no cycle: `series.py` does not import
  `episode.py`).
- `create_episode`, `load_episode`, `resolve_episode` each call it first.
- Deleted `resolve_episode`'s two-line empty-query guard; the shared helper's
  `not name` check now owns it. `test_empty_query_does_not_resolve_an_episode`
  still passes unchanged, and mutant 3 shows it is exactly that test which now
  pins the shared guard.

**Tests** — Step 1a additions to `test_video_series.py` and
`test_video_episode.py`, the single authorised assertion change in Step 1b, and
the Step 1c CLI escape test. Nothing else in the test suite was touched.

### Deviation from the brief's code block — flagged

The brief's code block passes `"series name"` as `kind`:

```python
_assert_safe_name(slug, "series name", SeriesError)
```

Taken literally this **broke six pre-existing tests**, because
`_assert_safe_name` now runs *before* `_validate_slug` and therefore owns the
message for every path-shaped slug, while those tests assert the word `slug`:

```
FAILED tests/test_video_cli.py::test_series_new_rejects_a_bad_slug - assert 'slug' in "unsafe series name '../escape' — must be a single directo...
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[../escape] - AssertionError: Regex pattern did not match.
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[a/b]
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[]
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[.]
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[..]
```

The standing rule "do not weaken any other assertion" outranks the literal
string, so I changed the **code**, not the tests: both call sites pass
`"series slug"`. One word, no structural change, and it makes the two modules
consistent with their own existing vocabulary (`"episode id"` already matches
`test_invalid_episode_id_is_rejected`'s `match="episode id"`, which is why the
episode side needed no adjustment). If you want the literal `"series name"`
back, the price is editing five assertions in two files; I did not think that
was the trade you wanted.

---

## 2. TDD evidence

### RED — `/tmp/t5_red.txt`, after Steps 1a/1b/1c, before any src change

```
17 failed, 181 passed in 0.65s
```

The 17 failures:

| count | test | failure |
|---|---|---|
| 8 | `test_video_series.py::test_load_series_refuses_unsafe_names[...]` | `Regex pattern did not match. Expected 'unsafe', Actual: "no series '../../outside' — create it with ..."` |
| 8 | `test_video_episode.py::test_load_episode_refuses_unsafe_ids[...]` | `Expected 'unsafe', Actual: "no episode '/abs' in the-brief — create it with ..."` |
| 1 | `test_video_series.py::test_scaffold_series_detects_a_dangling_symlink` | `FileExistsError: [Errno 17] File exists` — the raw OSError the brief predicted |

### Which of the new tests were already green at RED, and why

Reported rather than hidden, because a test that is green before the fix pins
nothing today:

- `test_scaffold_series_refuses_unsafe_names` (all 8) — `_validate_slug`
  already rejected every one of these. It is a regression guard, not a RED test.
- `test_resolve_episode_refuses_unsafe_ids` (all 4) — previously passed via
  "no episode matching". Now passes via the guard; mutant 3 confirms it is
  `test_empty_query_does_not_resolve_an_episode`, not this one, that kills the
  `resolve_episode` call site.
- Both `..._still_accepts_a_hand_made_directory_name` tests — these pin the
  *non*-regression (path safety must not become a naming rule), so green on
  both sides is the correct outcome.
- **`test_video_new_cannot_escape_the_workspace` passed at RED.** This is worth
  a sentence: the `ws` fixture calls `Workspace.init`, which creates
  `sources/` but **not** `series/`. Path traversal is lexical in `pathlib` but
  resolved by the kernel, so `<ws>/series/../../outside` cannot be opened when
  `<ws>/series` does not exist — `load_series` failed with "no series" for an
  incidental reason and the test passed without the fix. The escape needs
  `series/` to exist, which it does the moment the operator has ever created a
  series. My by-hand reproduction in §5 had to `mkdir -p ws/series` before the
  escape appeared. The test is a correct end-state assertion and I left it
  exactly as briefed, but it is **not** a red-to-green witness — mutants 1 and 2
  are what actually hold this line.

### GREEN

```
311 passed in 0.89s
```

---

## 3. Mutation results

All seven fail. `git checkout` of both source files between each; suite run in
full each time (`/tmp/t5_m1.txt` … `/tmp/t5_m7.txt`).

| # | Mutation | Result | Caught by |
|---|---|---|---|
| 1 | `load_series` → drop `_assert_safe_name` | **8 failed**, 303 passed | `test_load_series_refuses_unsafe_names` (all 8 params) |
| 2 | `load_episode` → drop `_assert_safe_name` | **8 failed**, 303 passed | `test_load_episode_refuses_unsafe_ids` (all 8 params) |
| 3 | `resolve_episode` → drop `_assert_safe_name` | **1 failed**, 310 passed | `test_empty_query_does_not_resolve_an_episode` — `DID NOT RAISE EpisodeError` |
| 4 | drop the `name in {".", ".."}` check | **4 failed**, 307 passed | `test_load_{series,episode}_refuses_unsafe_{names,ids}[.]` and `[..]` |
| 5 | drop `"\\"` from `_UNSAFE_CHARS` | **2 failed**, 309 passed | `test_load_series_refuses_unsafe_names[a\\b]`, `test_load_episode_refuses_unsafe_ids[a\\b]` |
| 6 | `scaffold_series` → drop `or d.is_symlink()` | **1 failed**, 310 passed | `test_scaffold_series_detects_a_dangling_symlink` — `FileExistsError: [Errno 17]` |
| 7 | `_validate_slug` → drop the length cap | **1 failed**, 310 passed | `test_over_long_name_fails_cleanly[cmd0]` — `assert 'limit 64' in "cannot create series 'aaa…"` |

**Mutant 7 is the Task 4b survivor, now dead.** The old assertion accepted the
kernel's `[Errno 63] File name too long`; `"limit 64"` is a string only agsoc's
own message contains. Note it is caught by `[cmd0]` (`series new`) only —
`[cmd1]` (`video new`) exercises `MAX_ID_LEN` in `episode.py`, a separate
constant this mutant did not touch. Both halves of the parametrisation are
individually load-bearing.

Mutant 3's single kill is narrow but genuine: with the old two-line guard
deleted, that test is the only thing standing between `video review ""` and
silently resolving the only episode.

Working tree restored: `git status --porcelain -- src tests` is empty.

---

## 4. Files changed

| File | Commit |
|---|---|
| `tests/test_video_series.py` | `5555056` |
| `tests/test_video_episode.py` | `5555056` |
| `tests/test_video_cli.py` | `5555056` |
| `src/agenticsocial/video/series.py` | `94b4797` |
| `src/agenticsocial/video/episode.py` | `94b4797` |

Nothing under `docs/` was staged in either commit. (An unrelated `docs:` commit,
`f722f0d`, landed between my two — the branch moved under me. My two commits are
still adjacent in intent and separately revertable.)

---

## 5. Issues and concerns

### 5.1 The escape, by hand, against the real CLI

Not through `CliRunner`. Real `agsoc` binary, real subprocess, real filesystem.

**Before the fix** (`/tmp/t5esc`, `AGSOC_WORKSPACE=/tmp/t5esc/ws`, with
`/tmp/t5esc/outside` a valid series):

```
$ AGSOC_WORKSPACE=/tmp/t5esc/ws agsoc video new 2026-08-14 --series ../../outside
created episode ../../outside/2026-08-14 at /tmp/t5esc/ws/series/../../outside/episodes/2026-08-14/
next: agsoc video ingest 2026-08-14 --research "<query>"
exit=0
/tmp/t5esc/outside
/tmp/t5esc/outside/series.toml
/tmp/t5esc/outside/episodes
/tmp/t5esc/outside/episodes/2026-08-14
/tmp/t5esc/outside/episodes/2026-08-14/script.yaml
/tmp/t5esc/outside/episodes/2026-08-14/out
/tmp/t5esc/outside/episodes/2026-08-14/sources
/tmp/t5esc/outside/episodes/2026-08-14/probe
```

Exit code 0 and four real directories outside the workspace. Precondition
confirmed by hand: with `ws/series` absent, the same command fails with
`no series '../../outside'` — which is exactly why the pytest version of this
test was green before the fix.

**After the fix**, same layout (`/tmp/t5after`):

```
=== 1. relative traversal ===
unsafe series slug '../../outside' — must be a single directory name, not a path
exit=1
=== 2. absolute path ===
unsafe series slug '/tmp/t5after/outside' — must be a single directory name, not a path
exit=1
=== 5. traversal in the episode id ===
unsafe episode id '../../../pwned' — must be a single directory name, not a path
exit=1
```

Nothing was created under `/tmp/t5after/outside`.

### 5.2 Other routes to a path outside the workspace — yes, there are three

You assumed there was one. There are three, and two of them still work.

**(a) Symlinked series directory — STILL ESCAPES.** Real CLI, post-fix:

```
$ ln -s /tmp/t5after/outside /tmp/t5after/ws/series/link
$ AGSOC_WORKSPACE=/tmp/t5after/ws agsoc video new 2026-08-14 --series link
created episode link/2026-08-14 at /tmp/t5after/ws/series/link/episodes/2026-08-14/
exit=0
$ find /tmp/t5after/outside
/tmp/t5after/outside/episodes/2026-08-14/script.yaml
/tmp/t5after/outside/episodes/2026-08-14/out
/tmp/t5after/outside/episodes/2026-08-14/probe
/tmp/t5after/outside/episodes/2026-08-14/sources
```

The name `link` is safe by every rule we have. The escape is in the
**filesystem**, not the name, and `_assert_safe_name` is by construction blind
to it. `series_slugs()` lists such a symlink happily, so it also appears in
`agsoc series list` as an ordinary series.

**(b) Symlinked `episodes/` inside a legitimate series — STILL ESCAPES.**

```
$ agsoc series new real
$ rmdir ws/series/real/episodes && ln -s /tmp/t5b/far ws/series/real/episodes
$ AGSOC_WORKSPACE=/tmp/t5b/ws agsoc video new 2026-08-14 --series real
created episode real/2026-08-14 at /tmp/t5b/ws/series/real/episodes/2026-08-14/
exit=0
$ find /tmp/t5b/far
/tmp/t5b/far/2026-08-14/script.yaml   ← outside the workspace
```

Both (a) and (b) are one fix: the only thing that actually proves containment is
resolving the final path and checking it is under `ws.root` — a
`Path.resolve()` + `is_relative_to` check, which no code in either module does.
Name-based guards cannot get there. **I did not implement it**: it is outside
this brief's code blocks, it needs its own tests, and it needs a decision from
you first, because a deliberate symlink is also a legitimate way an operator
puts big episode directories on another volume. My recommendation is a
containment assertion in `create_episode`/`scaffold_series` (the writers) and a
warning rather than an error in the readers. Flagging for the phase gate.

**(c) `AGSOC_WORKSPACE` itself — works, and correctly so.**

```
$ AGSOC_WORKSPACE=/tmp/t5after/elsewhere agsoc series new escaped
created series escaped at /tmp/t5after/elsewhere/series/escaped/
exit=0
```

This is not an escape. `AGSOC_WORKSPACE` *defines* the workspace; the operator
naming a different root is the documented feature (`CLAUDE.md`, "Workspace
resolution"). It only requires `<root>/sources/` to exist. Recording it so it is
not re-reported as a finding later.

**(d) A `series.toml` whose contents point elsewhere — does NOT escape.**
Verified: a series at `ws/series/liar` whose file says
`slug = "../../../far"` still writes to `ws/series/liar/episodes/`.
`load_series` builds `Series.dir` from the caller's argument and ignores the
file's own `slug` key entirely — it never even reads it. Safe, though only by
accident: nothing tests that the on-file `slug` is ignored, and a future
"trust the file" change would open the hole.

**(e) Unicode path lookalikes** — `..⁄..` (U+2044 FRACTION SLASH) is not a path
separator to the kernel and produced an ordinary "no series". Not a route.

### 5.3 Final sibling sweep, `series.py` vs `episode.py`

Function by function, every asymmetry I can find, largest first. Nothing here is
fixed by this commit — this is the list, as requested.

1. **Symlinks: creators symmetric, readers and enumerators not.** After this
   task both creators check `d.exists() or d.is_symlink()`. Neither
   `load_series`, `load_episode`, `series_slugs` nor `episode_ids` looks at
   symlinks at all. That is §5.2 (a)/(b). **Highest severity item on this list.**

2. **No containment check anywhere in either module.** `Series.dir` and
   `Episode.dir` are built by `/`-joining and never resolved. The workspace
   boundary is enforced entirely by name rules — an invariant no test states
   and no function asserts.

3. **Two constants for one number.** `MAX_NAME_LEN = 64` (series) and
   `MAX_ID_LEN = 64` (episode). Change one and the sibling silently keeps the
   old value — precisely the D-036 shape. They should be one constant, or at
   minimum a test asserting they are equal.

4. **`MAX_NAME_LEN` is misnamed and caps the wrong thing.** It caps the *slug*.
   The display `--name` has **no cap at all** — a 100 KB `--name` is accepted
   and written into both `series.toml` and `coverage.json`. Episodes have no
   display name, so no sibling exists to compare against.

5. **Naming rules are a named function on one side and inline on the other.**
   `series.py` has `_validate_slug`; `episode.py` inlines the length + regex
   checks inside `create_episode`. When a second episode-creating path appears
   there is nothing to call, which is how the original asymmetry was born.
   `_validate_episode_id` should exist.

6. **Different alphabets.** `SLUG_RE = ^[a-z0-9][a-z0-9-]*$` vs
   `EPISODE_ID_RE = ^[a-z0-9][a-z0-9.-]*$`. The dot is allowed in episode ids
   (`2026.08.14`) and refused in slugs. Probably deliberate, but undocumented
   and untested as a deliberate difference.

7. **Rollback scope differs.** In `create_episode` the `mkdir` of every subdir
   is *inside* the try/except that rmtrees. In `scaffold_series`,
   `(d / "episodes").mkdir(parents=True)` is *outside* it. A failure during that
   mkdir leaves a partial series directory, which is the exact condition
   `test_failed_scaffold_leaves_no_partial_directory` exists to prevent — it
   just does not exercise that line.

8. **Post-create read-back differs.** `scaffold_series` returns
   `load_series(ws, slug)` — it re-reads from disk. `create_episode` constructs
   the `Episode` in memory and calls `_new_meta` **twice** (once for the file,
   once for the return value). A create followed by a load can therefore
   disagree in a way the series path structurally cannot.

9. **`shutil` import placement.** Module-level in `series.py`, function-level
   inside `create_episode`. Cosmetic, but it is a reader's cue that the two
   rollbacks were written at different times by different hands.

10. **No `resolve_series`.** `resolve_episode` does exact-then-case-insensitive-
    substring matching; `--series` accepts only an exact slug. So
    `video review brie` works and `video list --series brie` does not.

11. **Error-message vocabulary.** Series says "series slug"; episode says
    "episode id". Consistent internally, but a caller cannot grep one word for
    both. `_assert_safe_name`'s `kind` parameter now carries this difference, so
    it is at least explicit.

12. **CLI ordering wart (not a sibling issue, but found while probing).**
    `agsoc video new ../../../pwned` correctly refuses the id — *after*
    `_resolve_series(autocreate=True)` has already scaffolded the `default`
    series on disk. A rejected command leaves a directory behind. Worth folding
    into whatever fixes item 2, since both are "validate before you touch the
    filesystem".

### 5.4 On importing `_assert_safe_name` across modules

You invited the objection. I have a mild one and I did what the brief said.

The leading underscore now advertises something false: it *is* a cross-module
API, imported by `episode.py`, and if a third module ever grows a path-taking
function it will import it too. Underscore-private names are also the ones
refactoring tools and reviewers assume are safe to rename or move.

But the alternative — two copies — is the entire bug this task exists to fix,
and I would not trade a real invariant for a naming convention. My suggestion
for Phase 2, when a third caller appears: move `_assert_safe_name` (and ideally
the merged length constant from item 3) into a small `video/names.py` and drop
the underscore. Until then, one shared underscore-name is the right call.

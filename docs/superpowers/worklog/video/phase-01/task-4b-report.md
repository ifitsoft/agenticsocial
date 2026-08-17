# Task 4b Report: Complete the CLI error surface, and make the CLI tests able to fail

**Branch:** `feat/video-phase-01-scaffolding`
**Commits:** `9350dcc` (tests, RED) · `8bd2cb3` (implementation, GREEN)

---

## 1. What I changed

**`tests/test_video_cli.py`** — Step 1a: added the `run(*args)` helper that calls
`runner.invoke(..., catch_exceptions=False)`, and mechanically rewrote all **29**
`runner.invoke(app, [...])` call sites to `run(...)`. The rewrite was done with a
single regex substitution (`re.subn`), not by hand; it reported 29 replacements
and no assertion text was touched. Step 1b appended the 6 new test functions
(7 test cases, one is parametrized over two commands).

**`src/agenticsocial/video/series.py`**
- `MAX_NAME_LEN = 64` beside `SLUG_RE`.
- `_validate_slug` gains the length check as its first clause.
- `load_series` gains the `except UnicodeDecodeError` clause between
  `TOMLDecodeError` and `OSError` — `tomllib.load` decodes UTF-8 itself and
  raises `ValueError`, not `OSError`, so the existing `except OSError` never
  saw it.
- `series_slugs` gains the `except OSError -> SeriesError` guard that its
  sibling `episode_ids` already had.

**`src/agenticsocial/video/episode.py`**
- `MAX_ID_LEN = 64` beside `EPISODE_ID_RE`.
- `create_episode` gains the length check ahead of the regex check.

**`src/agenticsocial/video/cli.py`**
- `series_new` and `video_new` each gain `except OSError -> _fail(...)` on the
  write path.
- `series_list` wraps `series_slugs(ws)` in `try/except SeriesError`.
- `series_list` reports `"?"` rather than `0` when `episode_ids` fails.

---

## 2. TDD evidence

### RED — `uv run pytest tests/test_video_cli.py` at commit `9350dcc`

```
FAILED tests/test_video_cli.py::test_over_long_name_fails_cleanly[cmd0] - OSError: [Errno 63] File name too long: '/Volumes/aabdukarimExternalSSD/aab...
FAILED tests/test_video_cli.py::test_over_long_name_fails_cleanly[cmd1] - OSError: [Errno 63] File name too long: '/Volumes/aabdukarimExternalSSD/aab...
FAILED tests/test_video_cli.py::test_series_list_survives_a_non_utf8_series_toml - UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 20: in...
FAILED tests/test_video_cli.py::test_load_series_on_non_utf8_raises_series_error - UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 20: in...
FAILED tests/test_video_cli.py::test_series_list_survives_an_unreadable_series_dir - PermissionError: [Errno 13] Permission denied: '/Volumes/aabdukarimExternal...
FAILED tests/test_video_cli.py::test_series_new_into_a_read_only_workspace_fails_cleanly - PermissionError: [Errno 13] Permission denied: '/Volumes/aabdukarimExternal...
FAILED tests/test_video_cli.py::test_series_list_reports_an_unknown_episode_count_rather_than_zero - AssertionError: assert '? episodes' in 'the-brief  [daily]  0 episodes  120...
========================= 7 failed, 18 passed in 0.88s =========================
```

All 7 failures are the new tests, and 5 of the 7 fail with a **raw traceback
class in the failure line** (`OSError`, `UnicodeDecodeError`, `PermissionError`).
That is the harness fix working: under the old runner every one of those would
have been reported as `exit_code == 1` with empty output.

Note the RED shape confirms the diagnosis. `test_series_list_reports_an_unknown_episode_count_rather_than_zero`
fails on `assert '? episodes' in 'the-brief  [daily]  0 episodes ...'` — i.e.
`series_list` *silently reported a wrong count* rather than crashing. That defect
class is invisible to exit-code assertions entirely.

### How many previously-passing tests changed behaviour under `catch_exceptions=False`

**Zero.** All 18 pre-existing tests passed before Step 1a and pass after it
(`18 passed` in the RED run above, `25 passed` after implementation). **No
previously-passing test began failing** — the harness was not hiding a live bug
in the code the existing tests cover. It was hiding the *absence of coverage*:
the assertions were vacuous, not wrong. See §3 mutant 1' for proof.

### GREEN — `uv run pytest tests/test_video_cli.py -v` at commit `8bd2cb3`

```
tests/test_video_cli.py::test_series_new_creates_and_reports PASSED       [  4%]
tests/test_video_cli.py::test_series_new_rejects_a_bad_slug PASSED        [  8%]
tests/test_video_cli.py::test_series_new_twice_fails_cleanly PASSED       [ 12%]
tests/test_video_cli.py::test_series_list_shows_runtime_and_formats PASSED [ 16%]
tests/test_video_cli.py::test_series_list_when_empty PASSED               [ 20%]
tests/test_video_cli.py::test_series_list_survives_one_broken_series PASSED [ 24%]
tests/test_video_cli.py::test_video_new_autocreates_the_default_series PASSED [ 28%]
tests/test_video_cli.py::test_video_new_into_a_named_series PASSED        [ 32%]
tests/test_video_cli.py::test_video_new_into_missing_named_series_fails PASSED [ 36%]
tests/test_video_cli.py::test_video_new_rejects_a_bad_id PASSED           [ 40%]
tests/test_video_cli.py::test_video_new_twice_fails_cleanly PASSED        [ 44%]
tests/test_video_cli.py::test_video_list_shows_status PASSED              [ 48%]
tests/test_video_cli.py::test_video_list_when_empty PASSED                [ 52%]
tests/test_video_cli.py::test_video_list_survives_an_unparseable_episode PASSED [ 56%]
tests/test_video_cli.py::test_video_list_survives_an_undecodable_episode PASSED [ 60%]
tests/test_video_cli.py::test_a_name_that_cannot_be_encoded_is_rejected_cleanly PASSED [ 64%]
tests/test_video_cli.py::test_commands_without_a_workspace_fail_cleanly PASSED [ 68%]
tests/test_video_cli.py::test_existing_text_commands_still_work PASSED    [ 72%]
tests/test_video_cli.py::test_over_long_name_fails_cleanly[cmd0] PASSED   [ 76%]
tests/test_video_cli.py::test_over_long_name_fails_cleanly[cmd1] PASSED   [ 80%]
tests/test_video_cli.py::test_series_list_survives_a_non_utf8_series_toml PASSED [ 84%]
tests/test_video_cli.py::test_load_series_on_non_utf8_raises_series_error PASSED [ 88%]
tests/test_video_cli.py::test_series_list_survives_an_unreadable_series_dir PASSED [ 92%]
tests/test_video_cli.py::test_series_new_into_a_read_only_workspace_fails_cleanly PASSED [ 96%]
tests/test_video_cli.py::test_series_list_reports_an_unknown_episode_count_rather_than_zero PASSED [100%]

============================== 25 passed in 0.23s ==============================
```

No test skipped — the permission-revocation tests ran for real on this machine
(not root).

### GREEN — full suite

```
============================= 279 passed in 0.76s ==============================
```

---

## 3. Mutation results

Each mutant applied to the committed code, full suite run, `git checkout` between.

| # | Mutant | Result | Caught by |
|---|---|---|---|
| 1 | `run()` drops `catch_exceptions=False` | **SURVIVED** — 279 passed | — (see below) |
| 1' | *(supplementary)* `cli._text` drops its `UnicodeEncodeError` guard | **KILLED** under new harness / **SURVIVED** under old | `test_a_name_that_cannot_be_encoded_is_rejected_cleanly` |
| 2 | `load_series` drops the `UnicodeDecodeError` clause | **KILLED** — 2 failed, 277 passed | `test_series_list_survives_a_non_utf8_series_toml`, `test_load_series_on_non_utf8_raises_series_error` |
| 3 | `series_slugs` drops the `OSError` guard | **KILLED** — 1 failed, 278 passed | `test_series_list_survives_an_unreadable_series_dir` |
| 4 | `_validate_slug` drops the length cap | **SURVIVED** — 279 passed | — (see below) |
| 5 | `series_list` reports `0` instead of `"?"` | **KILLED** — 1 failed, 278 passed | `test_series_list_reports_an_unknown_episode_count_rather_than_zero` |

### Mutant 1 survived — the mutant is mis-specified, the fix did take

The brief says mutant 1 "must fail; if it does not, the harness fix did not take."
It did not fail, and I want to be precise about why, because the conclusion the
brief attaches to that outcome is **not** the correct one here.

`catch_exceptions` only has an observable effect when something raises. On the
*fixed* code nothing raises, so dropping the flag is a semantic no-op and cannot
be killed by any test. Mutant 1 is not a mutant of the production code at all —
it is a mutant of the detector. A detector can only be shown to work against a
defect, so it must be run **in combination** with a code mutant.

I ran that combination, and it is unambiguous. Mutant 1' is the exact mutant that
**survived in Task 4** (disable the `_text` UTF-8 guard):

```
# with catch_exceptions=False  (this task's harness)
FAILED tests/test_video_cli.py::test_a_name_that_cannot_be_encoded_is_rejected_cleanly - UnicodeEncodeError: 'utf-8' codec can't encode character '\udce9' in positi...
======================= 1 failed, 24 deselected in 0.30s =======================

# with catch_exceptions dropped  (the old harness)
tests/test_video_cli.py .                                                [100%]
======================= 1 passed, 24 deselected in 0.24s =======================
```

Same mutant, same test, same code: **killed by the new harness, survives the
old.** That is the property mutant 1 was meant to establish, and it holds. I ran
the mutant-2/mutant-1 combination too; it degrades the diagnostic from
`UnicodeDecodeError: ...` to a bare `assert 1 == 0`, which is the same loss of
signal in a milder form.

**Flagging per the ground rules:** the brief's prose ("Mutant 1 is the important
one: it proves the tests can now see a crash") and its code block (mutant 1
standalone) disagree about what is being tested. I followed the code block —
applied mutant 1 exactly as written and reported the observed survival — and then
added mutant 1' to actually establish the property the prose asks for. I did not
adjust any test to make mutant 1 die.

### Mutant 4 survived — the length cap is masked by the new `OSError` handler

This one is a genuine coverage gap in the delivered work, not a specification
artefact. With the cap removed, `series new aaa…(300)` still exits 1 with:

```
cannot create series 'aaa…': [Errno 63] File name too long: '/…/series/aaa…'
```

The errno string contains the literal substring `"too long"`, so
`assert "too long" in result.output.lower()` passes through the Step-2d `OSError`
path. Step 2c and Step 2d were specified in the same task and 2d masks 2c's test.

The consequence is bounded but real: the length cap is currently **unpinned**.
If someone deletes it, the tests stay green and the behaviour degrades from a
portable, explanatory error to a platform-dependent `errno 63` (and on a
filesystem with a longer `NAME_MAX`, to no error at all — the directory would
simply be created with a 300-character name). Per the ground rules I did not
edit the brief's test to reach the predicted result. The fix is one added
assertion, e.g. `assert "limit 64" in result.output`, or asserting the absence
of `"Errno"`. Say the word and I will add it as a follow-up commit.

---

## 4. Files changed

| File | Commit |
|---|---|
| `tests/test_video_cli.py` | `9350dcc` |
| `src/agenticsocial/video/series.py` | `8bd2cb3` |
| `src/agenticsocial/video/episode.py` | `8bd2cb3` |
| `src/agenticsocial/video/cli.py` | `8bd2cb3` |

Nothing under `docs/` was staged. `git status --porcelain -- src tests` is empty
after the Step 4 mutation runs.

**Commit SHAs:** `9350dcc3405b76b474ff1094a2959dc168768e5f` ·
`8bd2cb36ffa8b9b874aec820a2ba02d7140c9154`

---

## 5. Issues and concerns

### 5.1 Traceback hunt re-run against the fixed code

I re-ran the Task 4 hunt as a script driving the real CLI through
`CliRunner(catch_exceptions=False)`, 24 probes over the operator-reachable
surface. **Zero crashes.** Every probe produced a clean `exit_code` and a
readable message:

```
[ok ] series new 300-char: exit=1 out='series slug is too long (300 characters, limit 64)'
[ok ] video new 300-char: exit=1 out='episode id is too long (300 characters, limit 64)'
[ok ] series new 64-char (at cap): exit=0
[ok ] video new id 64-char: exit=0
[ok ] series/ is a regular file: exit=1 out="cannot create series 'the-brief': [Errno 20] Not a directory: ..."
[ok ] series/<slug> is a dangling symlink: exit=1 out="cannot create series 'the-brief': [Errno 17] File exists: ..."
[ok ] series list with dangling symlink entry: exit=0 out='no series yet — ...'
[ok ] video new into series that is a dangling symlink: exit=1 out="no series 'the-brief' — ..."
[ok ] video new into read-only episodes/: exit=1 out="cannot create episode '2026-08-14': [Errno 13] Permission denied: ..."
[ok ] video list with unreadable script.yaml: exit=0 out='2026-08-14  [unreadable]  ...'
[ok ] video list --series ../../etc (traversal): exit=1
[ok ] series new with a NUL in the slug: exit=1 out="invalid series slug 'a\\x00b' — ..."
[ok ] video new with a NUL in the id: exit=1 out="invalid episode id 'a\\x00b' — ..."
[ok ] video new id '.'-leading rejected: exit=1
[ok ] series list with UTF-16 BOM toml: exit=0 out='s1  [unreadable]  ...'
[ok ] series list where series.toml is a directory: exit=0 out='no series yet — ...'
[ok ] video list with a symlink loop in episodes/: exit=0 out='no episodes in the-brief — ...'
[ok ] text new 400-char title: exit=0
[ok ] text new 4000-char title: exit=0
[ok ] text new surrogate title: exit=0
```

Two residual observations, neither a crash:

- **A series whose `series.toml` is a directory is silently invisible** to
  `series list` (`is_file()` is False, so the slug is never enumerated). It
  reports "no series yet" rather than "[unreadable]". Contradicts the D-018
  spirit — `list` is the diagnostic command — but it is an exotic corruption.
- **Error messages on the new `OSError` path leak raw `errno` text and absolute
  paths.** Acceptable for a local-first tool; noting it because it is why
  mutant 4 survived.

### 5.2 Is `MAX_NAME_LEN = 64` right?

Yes for the video pipeline, and it is very close to what the codebase already
chose elsewhere. `textutils.slugify` — the text pipeline's sibling — truncates
with `slug[:60]`. So 64 sits just above the existing house limit rather than
inventing a new scale.

I could not construct a plausible real id that 64 breaks:

- Dates (`2026-08-14`) are 10; date + topic slug (`2026-08-14-anthropic-opus-5-launch`)
  is ~35. A 64-char episode id would be a full sentence.
- Series slugs are brand-shaped (`the-brief`, `daily-ai-standup`): under 20.
- The real ceiling is `NAME_MAX = 255` on both APFS and ext4, so 64 leaves
  ~4x headroom and, importantly, is **not derived from the platform** — the cap
  is identical on every filesystem, which is what makes the error message
  portable.

One asymmetry worth a decision: text ids are `date-slug` = up to 71 chars while
video ids cap at 64. Different pipelines, different namespaces, so I would leave
it — but if you want one number, 60 would unify them.

### 5.3 Sibling asymmetries — where else one module was fixed and the other was not

You asked me to assume the UTF-8-guard mistake recurs. It does. I diffed
`series.py` against `episode.py` function by function, and the video `cli.py`
against the text-pipeline `cli.py`.

**Now symmetric (fixed by this task):** `load_series`/`_read_meta` both guard
`OSError` + `UnicodeDecodeError`; `series_slugs`/`episode_ids` both guard
`OSError`; `_validate_slug`/`create_episode` both cap length; `scaffold_series`/
`create_episode` both clean up with `except BaseException: shutil.rmtree(...)`;
`_fail` is byte-identical in both `cli.py` files.

**Still asymmetric — and one of them is serious:**

**(a) `--series` is never validated, and `video new` will write outside the
workspace.** This is the biggest thing I found and it is not a crash, which is
why the traceback hunt did not surface it. `scaffold_series` calls
`_validate_slug`; **`load_series` does not.** `video new --series <slug>` reaches
`create_episode` through `load_series`, so the slug is completely unvalidated on
that path. Demonstrated against the real CLI:

```
video list --series ../../outside -> 0 'no episodes in ../../outside — create one with `agsoc video new <id>`'
video new  --series ../../outside -> 0 'created episode ../../outside/2026-08-14 at /…/workspace/series/../../outside/episodes/2026-08-14/'
WROTE OUTSIDE WORKSPACE: True
```

`agsoc video new 2026-08-14 --series ../../outside` **creates directories and
writes `script.yaml` outside `workspace/`.** The write path validates; the read
path that also happens to write does not. (It only escapes once `series/` exists
on disk — until then the OS resolves `..` through a missing component and returns
ENOENT, which is why my first probe misleadingly reported it as safe.)

The one-line fix is `_validate_slug(slug)` at the top of `load_series`, matching
`scaffold_series`. I did **not** apply it: it is outside this brief's four
specified changes, it needs its own failing test, and it will change the error
message for `video list --series <bad>` (from "no series 'x'" to "invalid series
slug 'x'"), which existing tests may pin. **I recommend it as the next task, and
before the phase gate.**

**(b) `scaffold_series` misses the `is_symlink()` check `create_episode` has.**
`create_episode` guards `if d.exists() or d.is_symlink()`; `scaffold_series`
guards only `if d.exists()`. `Path.exists()` follows symlinks, so a **dangling**
symlink at `series/<slug>` is invisible to it — the code proceeds to `mkdir` and
fails with `[Errno 17] File exists`, which (post-2d) is a clean failure but a
confusing message where the sibling would say "already exists". Exactly the same
shape of one-side-only fix as the UTF-8 guard.

**(c) Length validation lives in different places.** `series.py` has a
`_validate_slug` helper; `episode.py` inlines the same two checks at the top of
`create_episode`. Cosmetic, but it is the structural reason the two drifted in
the first place — there is no single place a reviewer can see both.

**(d) `episode.py` has an explicit module docstring warning against
`frontmatter.parse`; `series.py` has no equivalent guidance.** Not a defect,
noted for completeness.

The pattern across (a), (b), and the original UTF-8 bug is consistent: **the
`episode.py` side has been hardened by three tasks of attention, and `series.py`
receives each fix late or not at all.** I would treat any future change to one of
these two modules as requiring an explicit check of the other.

# Task 4 Report: CLI wiring, and the input boundary

**Branch:** `feat/video-phase-01-scaffolding` · **Commits:** `37e2b75`, `8343b15`, `4f09274`

## 1. What I implemented

**Step 0 — `src/agenticsocial/video/episode.py`**

- `_read_meta` gained an `except UnicodeDecodeError` clause. `UnicodeDecodeError`
  subclasses `ValueError`, not `OSError`, so a latin-1 byte in a `script.yaml`
  previously escaped the `EpisodeError` contract entirely.
- Added `EPISODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")` beside `SUBDIRS`,
  enforced as the first statement of `create_episode`. Ids become directory
  names, so `../escape` previously wrote outside the series.
- Appended 5 test functions (12 test cases with the parametrize) to
  `tests/test_video_episode.py`, exactly as the brief specified.

I checked every existing `create_episode` call site before adding validation —
the ids in use are `2026-08-14`, `2026-08-15`, `doomed`, `ep`, `ghost`, all of
which remain valid under the new regex. No existing test was modified.

**Steps 1–4 — the CLI**

- New `src/agenticsocial/video/cli.py` with `series_app` (`new`, `list`) and
  `video_app` (`new`, `list`), copying `cli.py`'s `_fail`/`_workspace` idioms
  including the `raise _fail(...)` form.
- `_text()` guards the operator input boundary against lone surrogates from
  `sys.argv`'s surrogateescape decoding (D-025).
- Both `list` commands follow D-018: enumerate cheaply, load each member inside
  a try/except, report the broken ones, exit 0.
- `src/agenticsocial/cli.py`: added the `from .video.cli import series_app,
  video_app` import and the two `app.add_typer(...)` registrations immediately
  after the `app = typer.Typer(...)` block.

Implemented verbatim from the brief's code blocks. **No discrepancy between the
brief's prose and its code blocks this time** — the only prose/reality mismatch
is the RED expectation, noted in §2.

## 2. TDD evidence

### Step 0 — fix-plus-test, not a RED/GREEN pair

As the brief notes, Step 0 is a single commit carrying both the fix and its
tests, so there is no RED run to show. What I observed after applying both:

```
tests/test_video_episode.py ......................................... [ 62%]
..........................                                           [100%]
============================== 70 passed in 0.38s ==============================
```

70 passed, up from 58 (the 5 new functions expand to 12 cases via the
parametrize). The tests are not merely asserted-green: mutants 4 and 5 in §3
remove exactly the two Step 0 changes and both die, which is the RED evidence
this commit would otherwise lack.

### Step 2 — RED

`uv run pytest tests/test_video_cli.py` (from `/tmp/red.txt`):

```
FAILED tests/test_video_cli.py::test_series_new_creates_and_reports - assert 2 == 0
FAILED tests/test_video_cli.py::test_series_new_rejects_a_bad_slug - assert 2 == 1
FAILED tests/test_video_cli.py::test_series_new_twice_fails_cleanly - assert 2 == 1
FAILED tests/test_video_cli.py::test_series_list_shows_runtime_and_formats - assert 2 == 0
FAILED tests/test_video_cli.py::test_series_list_when_empty - assert 2 == 0
FAILED tests/test_video_cli.py::test_series_list_survives_one_broken_series - assert 2 == 0
FAILED tests/test_video_cli.py::test_video_new_autocreates_the_default_series - assert 2 == 0
FAILED tests/test_video_cli.py::test_video_new_into_a_named_series - assert 2 == 0
FAILED tests/test_video_cli.py::test_video_new_into_missing_named_series_fails - assert 2 == 1
FAILED tests/test_video_cli.py::test_video_new_rejects_a_bad_id - assert 2 == 1
FAILED tests/test_video_cli.py::test_video_new_twice_fails_cleanly - assert 2 == 1
FAILED tests/test_video_cli.py::test_video_list_shows_status - assert 2 == 0
FAILED tests/test_video_cli.py::test_video_list_when_empty - assert 2 == 0
FAILED tests/test_video_cli.py::test_video_list_survives_an_unparseable_episode - FileNotFoundError: [Errno 2] No such file or directory: '/Volumes/aabdukari...
FAILED tests/test_video_cli.py::test_video_list_survives_an_undecodable_episode - FileNotFoundError: [Errno 2] No such file or directory: '/Volumes/aabdukari...
FAILED tests/test_video_cli.py::test_a_name_that_cannot_be_encoded_is_rejected_cleanly - assert 2 == 1
FAILED tests/test_video_cli.py::test_commands_without_a_workspace_fail_cleanly - assert 2 == 1
========================= 17 failed, 1 passed in 0.31s =========================
```

**Observed 17 failed, 1 passed — not "every test fails" as the brief predicted.**
The passing one is `test_existing_text_commands_still_work`, which exercises the
pre-existing `agsoc new` and is a regression guard, not a specification of new
behaviour. Correct that it passes at RED. Reported, not adjusted.

The `assert 2 == 0` failures are Typer's exit code 2 for an unknown command.

### Step 4 — GREEN

`uv run pytest tests/test_video_cli.py -v` (from `/tmp/green1.txt`), all 18:

```
tests/test_video_cli.py::test_series_new_creates_and_reports PASSED       [  5%]
tests/test_video_cli.py::test_series_new_rejects_a_bad_slug PASSED        [ 11%]
tests/test_video_cli.py::test_series_new_twice_fails_cleanly PASSED       [ 16%]
tests/test_video_cli.py::test_series_list_shows_runtime_and_formats PASSED [ 22%]
tests/test_video_cli.py::test_series_list_when_empty PASSED               [ 27%]
tests/test_video_cli.py::test_series_list_survives_one_broken_series PASSED [ 33%]
tests/test_video_cli.py::test_video_new_autocreates_the_default_series PASSED [ 38%]
tests/test_video_cli.py::test_video_new_into_a_named_series PASSED        [ 44%]
tests/test_video_cli.py::test_video_new_into_missing_named_series_fails PASSED [ 50%]
tests/test_video_cli.py::test_video_new_rejects_a_bad_id PASSED           [ 55%]
tests/test_video_cli.py::test_video_new_twice_fails_cleanly PASSED        [ 61%]
tests/test_video_cli.py::test_video_list_shows_status PASSED              [ 66%]
tests/test_video_cli.py::test_video_list_when_empty PASSED                [ 72%]
tests/test_video_cli.py::test_video_list_survives_an_unparseable_episode PASSED [ 77%]
tests/test_video_cli.py::test_video_list_survives_an_undecodable_episode PASSED [ 83%]
tests/test_video_cli.py::test_a_name_that_cannot_be_encoded_is_rejected_cleanly PASSED [ 88%]
tests/test_video_cli.py::test_commands_without_a_workspace_fail_cleanly PASSED [ 94%]
tests/test_video_cli.py::test_existing_text_commands_still_work PASSED    [100%]

============================== 18 passed in 0.39s ==============================
```

Full suite (`uv run pytest`, from `/tmp/green2.txt`):

```
============================= 272 passed in 0.82s ==============================
```

**272 passed, 0 failed.** No test was modified, no dependency added.

## 3. Mutation results

Each mutant applied, run, then `git checkout` before the next.

| # | Mutant | Result | Caught by |
|---|--------|--------|-----------|
| 1 | `series_list` uses `list_series(ws)` instead of per-slug loading | **KILLED** (1 failed, 17 passed) | `test_series_list_survives_one_broken_series` — `assert 1 == 0` |
| 2 | `video_list` drops the per-episode `try/except` | **KILLED** (2 failed, 16 passed) | `test_video_list_survives_an_unparseable_episode`, `test_video_list_survives_an_undecodable_episode` |
| 3 | `_text` returns `value` unchanged | **SURVIVED** (18 passed) | nothing — see below |
| 4 | `create_episode` drops the `EPISODE_ID_RE` check | **KILLED** (10 failed, 78 passed) | `test_video_new_rejects_a_bad_id`, all 8 `test_invalid_episode_id_is_rejected[...]` cases, `test_invalid_episode_id_is_rejected_before_any_write` |
| 5 | `_read_meta` drops the `UnicodeDecodeError` clause | **KILLED** (2 failed, 86 passed) | `test_undecodable_script_raises_episode_error`, `test_video_list_survives_an_undecodable_episode` |

### Mutant 3 survived — the D-025 test is vacuous

`test_a_name_that_cannot_be_encoded_is_rejected_cleanly` does not pin `_text`.
Probed directly (`/tmp/m3out.txt`):

```
UNMUTATED exit: 1 exception: SystemExit(1)
  output: "The series name contains bytes that are not valid UTF-8 text. Check your terminal's encoding, or retype the value.\n"
MUTANT    exit: 1 exception: UnicodeEncodeError('utf-8', '[series]\nname       = "caf\udce9"\n...', 26, 27, 'surrogates not allowed')
  output: ''
  cafe dir exists: False
```

Root cause: `CliRunner.invoke` defaults to `catch_exceptions=True`, which turns
*any* uncaught exception into `exit_code == 1` and stashes it on
`result.exception` — the traceback never reaches `result.output`. So all three
assertions hold under the mutant:

- `exit_code == 1` — true either way;
- `"traceback" not in result.output.lower()` — vacuously true, output is `""`;
- `not (ws.series_dir / "cafe").exists()` — true because `scaffold_series`
  already `rmtree`s on `BaseException`.

In a real terminal the mutant prints a full rich traceback. The test would need
`catch_exceptions=False`, or an assertion on `result.exception`, or a positive
assertion on the error message text. **I did not change it** — the brief's rule
is to report observed results rather than adjust tests toward a predicted
number, and this is a defect in the specified test, worth deciding on
deliberately rather than papering over.

Note this also means the same blind spot applies to every other CLI test in the
file: `exit_code == 1` alone never distinguishes "clean error" from "crash".

## 4. Files changed

| Commit | SHA | Files |
|---|---|---|
| Step 0 | `37e2b753f61e12422b3f2a14be0f9d5a6a6524d4` | `src/agenticsocial/video/episode.py`, `tests/test_video_episode.py` |
| Step 2 | `8343b158c145339d89314b6dc55b7550705b5076` | `tests/test_video_cli.py` (new) |
| Step 4 | `4f09274bb89f88d0b90bfa1ed97c9b7210a00ed5` | `src/agenticsocial/video/cli.py` (new), `src/agenticsocial/cli.py` |

Nothing under `docs/` was staged. `git status --porcelain -- src tests` is
empty after the mutation round.

## 5. Issues and concerns

### Q1 — `series list` swallows `EpisodeError` and reports 0 episodes

**Yes, this is worse than the alternative, and I reproduced it.** With
`episodes/` at mode 000:

```
clean rc=0   chmod 000 episodes/ + series list
    out: s  [daily]  0 episodes  120s  vertical/wide
```

A series with 40 episodes reports `0 episodes` and exits 0. The operator's
reasonable conclusion is "my episodes are gone", which is both false and
alarming, and the command gives no thread to pull. Meanwhile `video list
--series s` on the *same* workspace prints the real diagnosis:

```
.../episodes: cannot list episodes — [Errno 13] Permission denied
```

So the information exists and `series list` throws it away. This is not really a
D-018 tension — D-018 says don't *die* over one bad member, and printing `?` or
`[episodes unreadable]` in the count column satisfies that fully while staying
exit 0. Silently substituting a plausible-looking wrong number is the one option
D-018 doesn't buy you anything for. Recommend rendering the count as `?` (or
appending `[episodes unreadable]`) instead of `0` in the `except EpisodeError`
branch. Small change, and it makes the diagnostic command actually diagnostic.

### Q2 — `video new --series nope` auto-creates only for `default`

Mildly surprising, but I'd keep it. The asymmetry is defensible: `default` is a
name the operator never typed, so materialising it on demand is the system
filling in its own placeholder; `nope` is a name the operator *did* type, and
auto-creating it would silently convert a typo into a new series — the failure
mode where `agsoc video new x --series the-breif` looks like it worked and the
episode lands somewhere invisible. The current error is already the right
teaching moment, since it names the fix verbatim:

```
no series 'nope' — create it with `agsoc series new nope`
```

The one thing I'd change is discoverability, not behaviour: the `--series` help
text is just `"series slug"` and doesn't mention that `default` is
auto-created. Worth a word there.

### Q3 — Operator input that still produces a traceback

**14 reproducing cases, in 4 distinct root causes.** All confirmed by running
the real CLI in a subprocess (`/tmp/hunt3.py`, `/tmp/hunt3.txt`) rather than
through `CliRunner`, which — as §3 shows — hides tracebacks. My first pass
reported these as clean because rich renders `Traceback (most recent call
last)` with ANSI escapes interleaved; the final detector strips ANSI first.
**Anyone testing this via `CliRunner` and `exit_code` alone will not see any of
these.**

#### (a) A slug/id longer than 255 characters — no filesystem tampering required

The only one reachable by pure typing, and therefore the one I'd fix first.
`SLUG_RE` and `EPISODE_ID_RE` constrain the *alphabet* but not the *length*, and
these values become directory names, so at `NAME_MAX + 1` the `mkdir` raises
`OSError: [Errno 63] File name too long`, uncaught. Threshold located exactly:

```
--- series new <200 chars>  rc=0    (ok)
--- series new <250 chars>  rc=0    (ok)
--- series new <255 chars>  rc=0    (ok)
--- series new <256 chars>  rc=1    OSError traceback
--- series new <300 chars>  rc=1    OSError traceback
--- video  new <301 chars>  rc=1    OSError traceback
```

A pasted URL or an accidentally-pasted paragraph reaches this. Note 255 is
macOS/APFS `NAME_MAX`; on other filesystems the cliff sits elsewhere, so the
guard should be a validation-time length cap (say 64) rather than anything
platform-derived. This belongs next to the existing regex checks in
`_validate_slug` and `create_episode`, where it also gets caught before any
write.

#### (b) Non-UTF-8 `series.toml` → `UnicodeDecodeError` — Step 0's bug, still open in `series.py`

```
*** TRACEBACK rc=1   non-UTF8 series.toml + series list   -> UnicodeDecodeError
*** TRACEBACK rc=1   non-UTF8 series.toml + video list    -> UnicodeDecodeError
*** TRACEBACK rc=1   non-UTF8 series.toml + video new     -> UnicodeDecodeError
```

**This is precisely the hole Step 0 closed for episodes, unclosed for series.**
`load_series` catches `tomllib.TOMLDecodeError` and `OSError`, but `tomllib.load`
decodes the file as UTF-8 itself and raises `UnicodeDecodeError` — a `ValueError`
— on a latin-1 byte. It escapes `SeriesError`, so `series list`'s D-018
try/except never fires and **the whole listing dies over one bad file**: exactly
the failure mode the phase exists to prevent, reachable by saving `series.toml`
from an editor defaulting to cp1252. Fix is the mirror of Step 0a: add an
`except UnicodeDecodeError` clause to `load_series` raising `SeriesError`. I'd
call this the highest-value item in this report after (a).

#### (c) `series_slugs` has no `OSError` guard, unlike `episode_ids`

```
*** TRACEBACK rc=1   chmod 000 series/ + series list   -> PermissionError
*** TRACEBACK rc=1   chmod 000 series/ + video list    -> PermissionError
```

`episode_ids` wraps its `iterdir()` in `try/except OSError` with the comment
"even an unreadable directory must surface as EpisodeError rather than
OSError". `series_slugs` does the bare `iterdir()` with no such guard, so an
unreadable `series/` (restrictive umask, a workspace on a mounted volume, a
workspace restored from a backup with wrong ownership) crashes both listings.
The asymmetry looks like an oversight rather than a decision. Same treatment,
raising `SeriesError`.

#### (d) Write-path `OSError` is uncaught throughout `new`

```
*** TRACEBACK rc=1   read-only series/ + series new      -> PermissionError
*** TRACEBACK rc=1   read-only series/ + video new       -> PermissionError
*** TRACEBACK rc=1   chmod 000 series/ + series new      -> PermissionError
*** TRACEBACK rc=1   chmod 000 series/ + video new       -> PermissionError
*** TRACEBACK rc=1   series/ is a FILE + series new      -> NotADirectoryError
*** TRACEBACK rc=1   series/ is a FILE + video new       -> NotADirectoryError
*** TRACEBACK rc=1   episodes/ is a FILE + video new     -> NotADirectoryError
```

`scaffold_series`/`create_episode` only convert *validation* failures into
`SeriesError`/`EpisodeError`; the `mkdir`/`atomic_write` calls let `OSError`
through, and the CLI's `except (SeriesError, EpisodeError)` doesn't cover it.
Read-only or full disks are ordinary operational states, not exotic ones. The
cleanup handlers do the right thing (`shutil.rmtree` on `BaseException` — I
verified nothing is left half-written), so this is purely about the error
surface. Cheapest fix is an `except OSError` in the CLI's `new` handlers
alongside the domain errors; the more consistent one is to wrap the write paths
in the domain error types the way the read paths already are.

#### Inputs I tried that ARE handled cleanly

Worth recording so the gate knows the boundary was actually probed: empty
string, `.`, `..`, `../escape`, `/abs/path`, `Upper`, `has space`,
`-abc`/`--force` (Typer exit 2), missing required argument, extra positional
argument, `café`, emoji in `--name`, U+007F in `--name`, a 100,000-character
`--name` (fine — it's a file *body*, not a name), `--series ''`,
`--series ../escape`, `series/` as a file for `list`, `episodes/` as a file,
`script.yaml` as a directory, `chmod 000 script.yaml`, `chmod 000 episodes/`,
a symlink loop in `episodes/`, a dangling `series.toml` symlink, an empty
`script.yaml`, YAML metadata that is a list, a `!!python/object/apply` YAML tag
bomb (refused by `safe_load`, reported as unreadable), `acts = 3`,
`formats.enabled = 5`, `target_sec = "x"`, and an invalid `status:` value. All
exit 0 or 1 with a readable message. A NUL byte in an argument is not
operator-reachable at all — `execve` rejects it before Python starts.

### Summary of recommendations, in priority order

1. Length-cap slugs and episode ids at validation time (fixes (a), the only
   traceback reachable by typing alone).
2. Add `except UnicodeDecodeError` to `load_series` (fixes (b); this is the
   Step 0 defect surviving in the sibling module, and it breaks D-018 listing).
3. Add the `OSError` guard to `series_slugs` to match `episode_ids` (fixes (c)).
4. Catch `OSError` on the `new` write paths (fixes (d)).
5. Make `test_a_name_that_cannot_be_encoded_is_rejected_cleanly` actually pin
   `_text` — `catch_exceptions=False` or an assertion on `result.exception` —
   and consider the same for the other CLI tests, since `exit_code == 1` under
   `CliRunner` cannot distinguish a clean error from a crash.
6. Render an unknown episode count in `series list` as `?`, not `0` (Q1).

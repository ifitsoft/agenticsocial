# Task 2 Report: Series configuration

**Branch:** `feat/video-phase-01-scaffolding`
**Commits:** `88752ac` (Step 0), `52c3e4c` (RED), `8a49f9a` (GREEN)

## 1. What I implemented

Created the `agenticsocial.video` package:

- `src/agenticsocial/video/__init__.py` — package docstring only.
- `src/agenticsocial/video/models.py` — `FORMATS`, `SeriesError`, `EpisodeError`,
  and the `Series` / `Episode` dataclasses. `Episode` is unused until Task 3, as
  the brief specifies.
- `src/agenticsocial/video/series.py` — `SERIES_TEMPLATE`, `COVERAGE_TEMPLATE`,
  `scaffold_series`, `load_series`, `list_series`. Loading is tolerant (a file
  containing only `[series] name` loads with defaults) and strict on exactly two
  things: `[formats] enabled` and `[runtime] target_sec`.
- `src/agenticsocial/workspace.py` — one added line, `self.series_dir =
  self.root / "series"`. `Workspace.init` does not create `series/` and
  `Workspace.locate` does not require it; `scaffold_series` creates it on demand.

Step 0 (separate commit, unrelated to series config): deleted
`test_published_is_terminal_for_video` from `tests/test_video_status.py`.

Everything was written exactly as the brief's code blocks show. No deviations.

## 2. TDD evidence

### RED

Step 0 baseline — the suite was at 114 passed before the deletion; after it:

```
tests/test_x_client.py ....                                              [100%]

============================= 113 passed in 0.32s ==============================
```

`uv run pytest tests/test_video_series.py` at commit `52c3e4c` (tests only, no
implementation):

```
==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_video_series.py __________________
ImportError while importing test module '/Users/aabdukarim/Documents/Code/agenticsocial/tests/test_video_series.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Volumes/aabdukarimExternalSSD/aabdukarimEX/.local/share/uv/python/cpython-3.11.13-macos-aarch64-none/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_video_series.py:3: in <module>
    from agenticsocial.video.models import SeriesError
E   ModuleNotFoundError: No module named 'agenticsocial.video'
=========================== short test summary info ============================
ERROR tests/test_video_series.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.05s ===============================
```

Exactly the predicted collection error.

### GREEN

`uv run pytest tests/test_video_series.py -v`:

```
cachedir: .pytest_cache
rootdir: /Users/aabdukarim/Documents/Code/agenticsocial
configfile: pyproject.toml
plugins: anyio-4.14.2, respx-0.23.1
collecting ... collected 17 items

tests/test_video_series.py::test_scaffold_creates_the_layout PASSED      [  5%]
tests/test_video_series.py::test_scaffold_is_not_destructive PASSED      [ 11%]
tests/test_video_series.py::test_scaffolded_series_loads_with_expected_defaults PASSED [ 17%]
tests/test_video_series.py::test_scaffold_defaults_name_to_slug PASSED   [ 23%]
tests/test_video_series.py::test_scaffolded_coverage_json_is_valid_and_empty PASSED [ 29%]
tests/test_video_series.py::test_minimal_config_loads_with_defaults PASSED [ 35%]
tests/test_video_series.py::test_design_tokens_are_loaded PASSED         [ 41%]
tests/test_video_series.py::test_acts_are_loaded_in_order PASSED         [ 47%]
tests/test_video_series.py::test_unknown_format_is_rejected PASSED       [ 52%]
tests/test_video_series.py::test_empty_format_list_is_rejected PASSED    [ 58%]
tests/test_video_series.py::test_non_positive_runtime_is_rejected PASSED [ 64%]
tests/test_video_series.py::test_non_integer_runtime_is_rejected PASSED  [ 70%]
tests/test_video_series.py::test_missing_series_is_actionable PASSED     [ 76%]
tests/test_video_series.py::test_malformed_toml_names_the_file PASSED    [ 82%]
tests/test_video_series.py::test_list_series_is_sorted_and_skips_non_series_dirs PASSED [ 88%]
tests/test_video_series.py::test_list_series_on_empty_workspace PASSED   [ 94%]
tests/test_video_series.py::test_scaffold_does_not_disturb_the_text_pipeline PASSED [100%]

============================== 17 passed in 0.07s ==============================
```

`uv run pytest`:

```
tests/test_video_status.py ....................                          [ 83%]
tests/test_workspace.py .................                                [ 96%]
tests/test_x_client.py ....                                              [100%]

============================= 130 passed in 0.41s ==============================
```

Observed counts match the brief's prediction exactly: 113 after Step 0, 17 new,
130 overall. No pre-existing test failed.

## 3. Files changed

| Commit | Files |
| --- | --- |
| `88752ac` | `tests/test_video_status.py` (deletion only) |
| `52c3e4c` | `tests/test_video_series.py` (new) |
| `8a49f9a` | `src/agenticsocial/video/__init__.py`, `src/agenticsocial/video/models.py`, `src/agenticsocial/video/series.py` (new); `src/agenticsocial/workspace.py` (+1 line) |

Nothing under `docs/` was staged in any of the three commits.

## 4. Self-review findings

**No prose/code-block contradiction found in this brief.** I checked each place
prose makes a claim a code block could falsify — the tolerant-vs-strict
description matches `load_series`; "nothing else in `workspace.py` changes"
matches the one-line edit; the Step 0 rationale matches what is actually in
`test_video_status.py` (the three retained per-key assertions all carry
docstrings, the deleted one did not); and the arithmetic 113 + 17 = 130 holds.

Two pieces of stale metadata, neither affecting the work:

- The header says **Follows: Task 1b, commit `43799e5`**, but the branch tip was
  `7e240eb` ("test: pin both transition tables exactly", Task 1c). The Step 0
  prose correctly refers to Task 1c, so this is just a stale header line.
- Step 4c's `list_series` docstring-free helper and Step 4b's `Episode` are both
  dead code at this commit. Intentional per the brief; noted so a reviewer does
  not flag it.

Observations on the implementation as written (all left alone, per the brief):

1. **`scaffold_series` is not atomic.** It `mkdir`s first, then writes two files.
   If either `atomic_write` fails, the directory survives and every retry hits
   `series already exists`, leaving the operator with a half-scaffolded series
   they must delete by hand. A `tempfile`-then-`os.replace` of the whole
   directory, or an `except: shutil.rmtree(d)` unwind, would fix it.
2. **`formats` is not checked for being a list.** `enabled = "vertical"` iterates
   the *characters* of the string, so the error reads `unknown format(s) v, e, r,
   t, i, c, a, l`. It correctly fails, but the message misdirects.
3. **Duplicates are not rejected or deduped.** `enabled = ["wide", "wide"]` loads
   and later phases would render `wide` twice.
4. **`tolerance_sec` is unvalidated**, so `tolerance_sec = "loose"` loads and
   fails wherever it is first used arithmetically. Consistent with the brief's
   "strict on exactly two things", but worth a decision later.
5. **`raise SeriesError(...)` inside `except`** does not use `from e`. Implicit
   chaining still preserves the traceback, so the operator-facing message is
   clean and the cause is not lost. Fine as is; `from None` would be the choice
   if you wanted to suppress the tomllib frame entirely.
6. `Series.formats`'s default factory repeats the `["vertical", "wide"]` literal
   rather than deriving from `FORMATS`. Two places to edit when a third format
   lands. Cosmetic, and `models.py` cannot import `FORMATS` from itself into the
   dataclass default any more cheaply than `list(FORMATS)` would — that is
   actually available and would be marginally better.

## 5. Issues and concerns

### The `bool` / `int` wart in `isinstance(target_sec, int)`

It matters, but only barely, and I would not fix it here.

Concretely: `target_sec = true` in TOML passes `isinstance(x, int)` (bool
subclasses int) and passes `x <= 0` (True == 1), so the series loads with a
one-second target runtime. `target_sec = false` is caught, but by the wrong
branch — the operator is told "must be a positive integer" when the real problem
is that they wrote a boolean.

Why it is low severity: nobody types `target_sec = true` by accident. There is no
adjacent key where a bool is plausible, and TOML has no coercion that could
produce one from a number or a quoted string. The realistic failure modes are the
two the tests already cover — a string, and zero or negative.

Why I would still fix it eventually: the cost is one clause,
`if isinstance(target_sec, bool) or not isinstance(target_sec, int) or
target_sec <= 0`, and the same shape will be copy-pasted for `tolerance_sec`,
beat holds, and every other numeric field the config grows. Fixing the pattern
once at the first site is cheaper than fixing five instances later. My
recommendation: a small `_require_positive_int(value, path, key)` helper in
`series.py` when the second numeric field arrives, not before. Adding the helper
now for a single call site would be premature.

### Should one malformed `series.toml` fail `agsoc series list` entirely?

**No. `list_series` should skip-and-warn, not abort.** I think the current
behaviour is wrong, though it is the right thing to ship in this task since no
CLI consumes it yet.

The argument for the current strictness is consistency — a broken config is a
broken config, and silently omitting a series could let an operator believe a
series was deleted. That concern is real, but it is an argument for *warning
loudly*, not for failing the command.

The argument against is the failure mode. `list` is the diagnostic command. It is
what an operator runs precisely when something is wrong and they do not yet know
what. The current code makes the one command that could tell them "series
`the-brief` is fine, series `cardio-weekly` has a syntax error on line 4" instead
refuse to tell them anything at all — including which series is broken, unless
they read the traceback. A ten-series workspace becomes entirely unlistable
because of one typo in one file, and the blast radius of an edit is inversely
related to how useful the tool is at that moment. That is the opposite of what a
list command should do under partial failure.

The distinction I would draw is between **addressed** and **enumerating**
operations:

- `load_series(ws, slug)` — the operator named one series. If it is broken, raise.
  There is no partial answer to give.
- `list_series(ws)` — the operator asked what exists. A broken series is a *fact
  about the workspace*, and reporting it is more useful than hiding it behind an
  exception.

Concretely I would change `list_series` to return `list[Series]` plus a parallel
list of `(slug, error)` pairs — or, less invasively, keep the return type and
have the CLI layer call `load_series` per slug itself so it can catch per-series.
The second option keeps `series.py` free of presentation concerns and puts the
"print a warning to stderr, exit 0, list the good ones" decision where it
belongs. Either way, the exit code should stay 0: the command succeeded at
answering the question it was asked.

This needs your decision before Task 4 wires up the CLI, since it changes
`list_series`'s signature or its callers. I have left it exactly as the brief
specifies.

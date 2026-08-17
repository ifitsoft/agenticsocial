# Task 2b Report: Harden series config against malformed input

**Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `8a49f9a`
**Commits:** `22a78c0` (tests) · `8af23fd` (implementation)

---

## 1. What I changed

- `tests/test_video_series.py` — moved `import json` and the `_write_series`
  helper to just below the `ws` fixture (Step 1b), rewrote
  `test_minimal_config_loads_with_defaults` to use the helper, appended the 15
  new test functions (36 cases after parametrisation).
- `src/agenticsocial/video/models.py` — `Series` gains `warm_acts: list[str]`
  directly after `acts`.
- `src/agenticsocial/video/series.py` — rewritten per the brief's code block:
  `_toml_str`/`render_series_toml`/`render_coverage_json` (escaped rendering,
  coverage.json now built by `json.dumps` instead of a text template),
  `SLUG_RE` + `_validate_slug`, `_table` type guard, `shutil.rmtree` cleanup on
  any failure in `scaffold_series`, `is_file()` + `OSError` handling in
  `load_series`, bool-rejection on `target_sec`, `warm_acts` loading, and a new
  `series_slugs()` that `list_series()` now delegates to.

**One deviation from the brief, flagged as instructed** — see §5.0. Four of the
five `test_wrong_typed_section_raises_series_error` bodies were invalid as
written: in TOML, a bare `runtime = 5` *after* a `[series]` header is a key
*inside* `[series]`, not a top-level key.

```
'[series]\nname = "B"\n\nruntime = 5\n' -> {'series': {'name': 'B', 'runtime': 5}}
'runtime = 5\n\n[series]\nname = "B"\n' -> {'runtime': 5, 'series': {'name': 'B'}}
```

So the brief's bodies never produced a wrong-typed top-level section and the
cases failed GREEN with `DID NOT RAISE`. I hoisted the bare key above the
`[series]` header in all four, preserving the stated intent exactly, and
confirmed the corrected bodies are still RED against `8a49f9a` before folding
the correction into the tests-only commit (amended, not squashed — the two
commits and their order are intact).

## 2. TDD evidence

### RED — corrected tests against `8a49f9a`'s implementation

```
FAILED tests/test_video_series.py::test_hostile_series_name_round_trips[He said "hi"]
FAILED tests/test_video_series.py::test_hostile_series_name_round_trips[back\\slash]
FAILED tests/test_video_series.py::test_hostile_series_name_round_trips[line\nbreak]
FAILED tests/test_video_series.py::test_hostile_series_name_round_trips[both "quotes" and \\slashes\\]
FAILED tests/test_video_series.py::test_hostile_series_name_leaves_valid_coverage_json[He said "hi"]
FAILED tests/test_video_series.py::test_hostile_series_name_leaves_valid_coverage_json[back\\slash]
FAILED tests/test_video_series.py::test_hostile_series_name_leaves_valid_coverage_json[line\nbreak]
FAILED tests/test_video_series.py::test_failed_scaffold_leaves_no_partial_directory
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[../escape]
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[a/b] - Faile...
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[] - Failed: ...
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[.] - Failed:...
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[..] - Failed...
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[Upper] - Fai...
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[has space]
FAILED tests/test_video_series.py::test_invalid_slug_is_rejected[-leading] - ...
FAILED tests/test_video_series.py::test_slug_rejection_happens_before_any_write
FAILED tests/test_video_series.py::test_non_string_format_entries_raise_series_error
FAILED tests/test_video_series.py::test_string_instead_of_format_list_raises_series_error
FAILED tests/test_video_series.py::test_wrong_typed_section_raises_series_error[series = "hello"\n]
FAILED tests/test_video_series.py::test_wrong_typed_section_raises_series_error[runtime = 5\n\n[series]\nname = "B"\n]
FAILED tests/test_video_series.py::test_wrong_typed_section_raises_series_error[design = "blue"\n\n[series]\nname = "B"\n]
FAILED tests/test_video_series.py::test_wrong_typed_section_raises_series_error[structure = true\n\n[series]\nname = "B"\n]
FAILED tests/test_video_series.py::test_wrong_typed_section_raises_series_error[formats = 1\n\n[series]\nname = "B"\n]
FAILED tests/test_video_series.py::test_unreadable_series_toml_raises_series_error
FAILED tests/test_video_series.py::test_boolean_target_sec_is_rejected - Fail...
FAILED tests/test_video_series.py::test_minimal_config_reaches_every_loader_default
FAILED tests/test_video_series.py::test_warm_acts_is_loaded - AttributeError:...
======================== 28 failed, 19 passed in 0.30s =========================
```

28 of the 36 new cases fail. The eight that pass are genuinely already-satisfied
assertions, not gaps: `test_hostile_series_name_round_trips[tab\there]` (a raw
tab is legal inside a TOML basic string, so naive interpolation happened to
survive it), `test_series_dir_is_literally_named_series`, and the six
`test_hostile_*` / minimal-config cases whose surrounding behaviour was correct.

### GREEN

```
tests/test_video_series.py::test_warm_acts_is_loaded PASSED              [100%]

============================== 47 passed in 0.10s ==============================
```

```
tests/test_x_client.py ....                                              [100%]

============================= 160 passed in 0.47s ==============================
```

Full suite: **160 passed**. (Your predicted count was not stated for the suite;
Task 2 finished at 130, and 30 net new cases land here.)

## 3. Mutation re-test

Each mutant applied to a clean tree, `uv run pytest`, `git checkout` between.

| # | Mutation | Result | Killed by |
|---|---|---|---|
| 1 | loader default `cadence` `"daily"` → `"weekly"` | **KILLED** (1 failed, 159 passed) | `test_minimal_config_reaches_every_loader_default` |
| 2 | loader default `register` `"reported"` → `"XXX"` | **KILLED** (1 failed, 159 passed) | `test_minimal_config_reaches_every_loader_default` |
| 3 | loader default `tolerance_sec` `8` → `99` | **KILLED** (1 failed, 159 passed) | `test_minimal_config_reaches_every_loader_default` |
| 4 | loader `name` fallback `slug` → `"UNNAMED"` | **KILLED** (1 failed, 159 passed) | `test_minimal_config_reaches_every_loader_default` |
| 5 | `workspace.py`: `series_dir = root / "shows"` | **KILLED** (1 failed, 159 passed) | `test_series_dir_is_literally_named_series` |

All five previously-surviving mutants are now killed. Working tree restored;
`git status --porcelain` shows nothing under `src/` or `tests/`.

Note that mutants 1–4 are killed by a *single* test. That test is now a
single point of failure for four independent defaults — acceptable, but worth
knowing if it is ever edited.

## 4. Files changed

- `src/agenticsocial/video/series.py`
- `src/agenticsocial/video/models.py`
- `tests/test_video_series.py`

Commits: `22a78c0` (tests), `8af23fd` (implementation). Nothing under `docs/`
staged; `DECISIONS.md` and `PROGRESS.md` untouched.

## 5. Issues and concerns

### 5.0 Brief defect: four F3 test bodies were invalid TOML for their purpose

Covered in §1. Flagging per the ground rule — this is the fifth brief with a
code-block defect.

### 5.1 **`json.dumps` is NOT a safe TOML basic-string escaper. This is a live bug.**

The docstring the brief specifies for `_toml_str` claims JSON escaping is "a
valid subset of TOML's basic-string escaping". **That claim is false**, and the
divergence is reachable with ordinary operator input, not an adversarial edge
case.

`json.dumps` defaults to `ensure_ascii=True`, which encodes every non-ASCII
character as a `\uXXXX` escape — and for characters **outside the BMP** it emits
a **UTF-16 surrogate pair**, `😀`. TOML v1.0.0 requires every `\uXXXX`
escape to denote a Unicode *scalar* value; surrogate code points are explicitly
not scalar values, so a surrogate pair is invalid TOML. `tomllib` rejects it.

Reproduced end-to-end against the committed code:

```
rendered name line: name       = "The Brief 😀"
SeriesError: .../series/the-brief/series.toml: malformed series.toml —
  Escaped character is not a Unicode scalar value (at line 2, column 31)
dir left behind: False
```

That is precisely the D-020 failure this task exists to eliminate, reproduced
with an emoji instead of a quote mark:

- `agsoc series new the-brief --name "The Brief 😀"` **can never succeed.**
- The error blames the operator's `series.toml` for being malformed when the
  tool wrote it one millisecond earlier.
- Any non-BMP character does it: emoji, but also historic scripts, many CJK
  extension-B ideographs, and mathematical alphanumerics.

The one mitigation the new code does buy: `shutil.rmtree` cleanup means the
directory is gone and there is no `series already exists` dead end. The severity
drops from *unrecoverable* to *permanently impossible*, which is better but not
acceptable.

The full probe (`tomllib.loads(f"name = {json.dumps(v)}")`):

| input | rendered | result |
|---|---|---|
| `He said "hi"` | `"He said \"hi\""` | round-trips |
| `back\slash` | `"back\\slash"` | round-trips |
| `line\nbreak` | `"line\nbreak"` | round-trips |
| `tab\there` | `"tab\there"` | round-trips |
| `a\x7fb` (DEL) | `"ab"` | round-trips |
| `Café Noir` | `"Café Noir"` | round-trips |
| `a﻿b` (BOM) | `"a﻿b"` | round-trips |
| `a\x00b` (NUL) | `"a b"` | round-trips |
| **`The Brief 😀`** | `"The Brief 😀"` | **TOMLDecodeError** |
| **lone surrogate `\ud800`** | `"\ud800"` | **TOMLDecodeError** |

Note the trap in the obvious one-line fix. `ensure_ascii=False` fixes the emoji
case — but it then emits U+007F **raw**, and TOML lists U+007F among the control
characters that *must* be escaped, so it converts one failure into another.
Neither flag setting is correct on its own. A correct escaper needs an explicit
character map (`"`, `\`, and control chars incl. U+007F escaped; everything else
passed through as literal UTF-8), roughly:

```python
_TOML_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t",
                 "\n": "\\n", "\f": "\\f", "\r": "\\r"}

def _toml_str(value: str) -> str:
    out = []
    for ch in value:
        if ch in _TOML_ESCAPES:
            out.append(_TOML_ESCAPES[ch])
        elif ch < " " or ch == "\x7f":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)  # literal UTF-8, no surrogates
    return '"' + "".join(out) + '"'
```

I did **not** apply this — the brief's code block is authoritative and this is a
specification change, not an implementation slip. It needs a decision from you,
plus a test case (`'emoji 😀'` and `'DEL \x7f'` appended to the
`test_hostile_series_name_round_trips` parametrisation) that the current spec
would fail. Recommend a Task 2c.

Also worth noting: `render_coverage_json` uses `ensure_ascii=False` while
`_toml_str` uses the default `True`. The two files therefore disagree about
encoding policy for the same operator string — coverage.json handles the emoji
fine, series.toml does not.

### 5.2 `scaffold_series` catching `BaseException`

I think catching `BaseException` is right, and I would keep it. The rationale is
that the cleanup is not error *handling* — it is a bare `raise` after undoing a
half-finished mutation, so no exception is swallowed and no diagnostic is lost.
`KeyboardInterrupt` is in fact the case that most needs it: Ctrl-C during
`agsoc series new` is a normal operator action, and the operator's very next
move is to run the command again. Leaving a partial directory for "forensics"
would greet them with `series already exists` for a series they never created.

There is nothing to be forensic *about*: the directory contains at most a
freshly-rendered `series.toml` from a deterministic template, reproducible at
any time by re-running the command. Contrast with a failure that *destroys*
operator data — that would deserve preservation. This one does not.

Two caveats I would accept rather than fix:

- `shutil.rmtree(..., ignore_errors=True)` inside the handler means a cleanup
  failure is silent, and the operator gets the original error plus a partial
  directory anyway. Rare, and the alternative (raising from the handler) hides
  the real cause, which is worse.
- On `KeyboardInterrupt` the rmtree runs during unwinding; a second Ctrl-C
  lands mid-cleanup. Not worth defending against.

### 5.3 Should `load_series` validate `acts` entries?

Yes, but not here — and "it blows up in Phase 4's renderer" is not acceptable as
the permanent answer, for one specific reason: `acts` is the only remaining
field that reaches the rest of the system completely unvalidated, and it is the
most structurally complex thing in the file. Every other escape from the
`SeriesError` contract was closed in this task; `acts` keeps a hole open.
`acts = "hello"`, `acts = [1, 2]`, or an act missing `beats` all load cleanly
today and surface much later as `TypeError`/`KeyError` from renderer internals,
with no file path in the message — exactly the failure mode F2 and F3 exist to
prevent.

My recommendation is to add the cheap *shape* check now and defer the semantic
check to Phase 4:

- **Now, in `load_series`:** `acts` must be a list of tables. That is three
  lines, mirrors the `formats` guard, and is enough to guarantee that anything
  downstream can at least call `.get()` on each entry.
- **Phase 4, in the renderer's own validation:** required keys, `beats` being a
  positive int, `id` uniqueness, `warm_acts` referencing act ids that exist.
  These are renderer contracts, and duplicating them in the loader would mean
  two places to update whenever the act schema moves.

Note the asymmetry the current code has: `warm_acts` is loaded with no check
that its entries are strings, while `formats` right above it is strictly
checked. Same argument, same three lines.

# Task 2c Report: A correct TOML string escaper, and the last two unvalidated fields

**Branch:** `feat/video-phase-01-scaffolding`
**Commits:** `a5d2ceb` (RED, tests only) → `2dbf3e9` (GREEN, implementation)

## 1. What I changed

- `src/agenticsocial/video/series.py`
  - Replaced `_toml_str` (was `json.dumps(value)`) with an explicit TOML v1.0.0
    basic-string escaper plus a `_TOML_SHORT_ESCAPES` table. Non-ASCII —
    including non-BMP — is now written literally as UTF-8; only `"`, `\`, the
    C0 controls and U+007F are escaped. The docstring records why neither
    `ensure_ascii` setting is acceptable.
  - Added shape validation for `acts` (list of tables) and `warm_acts` (list of
    strings) in `load_series`, immediately after the `target_sec` check, and
    switched the `Series(...)` call to the new locals.
  - `json` is still imported and still used by `render_coverage_json`.
- `tests/test_video_series.py` — appended 21 test cases (append-only; no
  existing test touched).

No dependencies added. Nothing under `docs/` staged.

## 2. TDD evidence

### RED — after the test-only commit `a5d2ceb`

`uv run pytest tests/test_video_series.py 2>&1 | tail -40`:

```
=========================== short test summary info ============================
FAILED tests/test_video_series.py::test_any_name_round_trips_through_toml[The Brief \U0001f600]
FAILED tests/test_video_series.py::test_any_name_round_trips_through_toml[北京 \U0002000b]
FAILED tests/test_video_series.py::test_any_name_round_trips_through_toml[mixed \U0001f600 \x07 "q" \\s \xfcn\xefc\xf6d\xe9]
FAILED tests/test_video_series.py::test_non_bmp_name_produces_a_literal_utf8_file
FAILED tests/test_video_series.py::test_hostile_name_round_trips_through_coverage_json_too
FAILED tests/test_video_series.py::test_wrong_shaped_acts_is_rejected["not a list"]
FAILED tests/test_video_series.py::test_wrong_shaped_acts_is_rejected[5] - Fa...
FAILED tests/test_video_series.py::test_wrong_shaped_acts_is_rejected[{a = 1}]
FAILED tests/test_video_series.py::test_wrong_shaped_acts_is_rejected[["a", "b"]]
FAILED tests/test_video_series.py::test_wrong_shaped_warm_acts_is_rejected["03"]
FAILED tests/test_video_series.py::test_wrong_shaped_warm_acts_is_rejected[[3]]
FAILED tests/test_video_series.py::test_wrong_shaped_warm_acts_is_rejected[5]
======================== 12 failed, 59 passed in 0.40s =========================
```

12 failed / 59 passed. Note which cases did **not** fail: the pure-control-char
cases (`del\x7fhere`, `bell\x07here`, `null\x00byte`, `esc\x1bseq`, the
`< 0x100` sweep) already passed under `json.dumps` — `ensure_ascii=True` handles
them fine. The only pre-existing defect was non-BMP. Those control cases exist
to pin the *replacement*, and they earn their keep against mutants 2 and 4.

### GREEN — after `2dbf3e9`

`uv run pytest tests/test_video_series.py -v 2>&1 | tail -40` (last line):

```
============================== 71 passed in 0.25s ==============================
```

`uv run pytest 2>&1 | tail -5`:

```
tests/test_video_status.py ....................                          [ 88%]
tests/test_workspace.py .................                                [ 97%]
tests/test_x_client.py ....                                              [100%]

============================= 184 passed in 0.56s ==============================
```

**Observed full-suite count: 184 passed.** (163 before this task, plus the 21
new cases.)

## 3. Mutation results

Applied programmatically, `git checkout` between each, `uv run pytest -q`.
**All six died. No survivors.**

| # | Mutant | Result | Representative killers |
|---|--------|--------|------------------------|
| 1 | `_toml_str` → `return json.dumps(value)` | **killed** — 5 failed, 179 passed | `test_any_name_round_trips_through_toml[The Brief 😀]`, `[北京 𠀋]`, `[mixed …]`, `test_non_bmp_name_produces_a_literal_utf8_file`, `test_hostile_name_round_trips_through_coverage_json_too` |
| 2 | `_toml_str` → `return json.dumps(value, ensure_ascii=False)` | **killed** — 3 failed, 181 passed | `test_any_name_round_trips_through_toml[del\x7fhere]`, `test_every_codepoint_below_0x100_round_trips`, `test_del_and_control_chars_are_escaped_not_literal` |
| 3 | `_toml_str` → `return '"' + value + '"'` | **killed** — 18 failed, 166 passed | `test_hostile_series_name_round_trips[…]` (all 4 non-trivial), `test_hostile_series_name_leaves_valid_coverage_json[…]`, plus the new hostile params |
| 4 | drop the `elif ord(ch) < 0x20 or ord(ch) == 0x7F` branch | **killed** — 8 failed, 176 passed | `[del\x7fhere]`, `[bell\x07here]`, `[null\x00byte]`, `[esc\x1bseq]`, `[mixed …]`, `test_every_codepoint_below_0x100_round_trips` |
| 5 | drop the `acts` shape check | **killed** — 4 failed, 180 passed | all four `test_wrong_shaped_acts_is_rejected` params |
| 6 | drop the `warm_acts` shape check | **killed** — 3 failed, 181 passed | all three `test_wrong_shaped_warm_acts_is_rejected` params |

Mutant 2 — the one that mattered — is killed by three independent tests. The
decisive one is `test_del_and_control_chars_are_escaped_not_literal`, which
asserts on the *file bytes* rather than on the round trip; `ensure_ascii=False`
writes a raw `\x7f` and tomllib then rejects the file it just wrote.

Working tree restored: `git status --porcelain src tests` is empty.

## 4. Files changed

- `src/agenticsocial/video/series.py` (commit `2dbf3e9`)
- `tests/test_video_series.py` (commit `a5d2ceb`)

Commit SHAs: **`a5d2ceb`** (RED), **`2dbf3e9`** (GREEN).

## 5. Issues and concerns

### Brief defects

None found. I looked specifically for the code-vs-prose disagreement pattern.
Two things I checked and cleared:

- The sweep test uses `range(1, 0x100)` (skips U+0000) while the parametrized
  list separately includes `"null\x00byte"`. This looked like a possible gap,
  but it is coherent: U+0000 *is* a Unicode scalar value, `tomllib` accepts the escape,
  and the parametrized case covers it. Verified:
  `tomllib.loads('a = "\\u0000"')` → `{'a': '\x00'}`.
- `_TOML_SHORT_ESCAPES` matches the TOML v1.0.0 short-escape set exactly
  (`\b \t \n \f \r \" \\`); nothing missing, nothing invented.

### Q1 — Is the escaper correct against TOML v1.0.0? And lone surrogates?

**For every string Python can encode as UTF-8, yes, and I could not break it.**
Things I tried, all round-tripping: U+10FFFF (max scalar), U+FFFE (a
noncharacter), U+FEFF (BOM mid-string), U+2028/U+2029, the full C0/C1 +
Latin-1 sweep, and every combination of quote/backslash/control/non-BMP. The
escaper is total over `str` values that are valid Unicode text.

**But `str` in Python is wider than "valid Unicode text", and there the answer
is: we need another fix.** A lone surrogate is not a Unicode scalar value, so
UTF-8 cannot encode it and TOML cannot represent it — `\uD800` is exactly the
escape `tomllib` rejects with *"Escaped character is not a Unicode scalar
value"*, i.e. the very bug this task removed. There is no escaping that saves
it. Today:

```
name="\ud800" → UnicodeEncodeError: 'utf-8' codec can't encode character
                '\ud800' in position 23: surrogates not allowed
```

It fails inside `atomic_write` while writing `series.toml`, i.e. before
`coverage.json`, and `scaffold_series`'s `except BaseException` cleanup does
fire — I confirmed no partial directory is left behind, so the operator can
retry. That part is fine.

**Why this is reachable rather than theoretical.** Python decodes `sys.argv`
with the `surrogateescape` error handler, so *any* byte in a CLI argument that
is not valid UTF-8 arrives as a lone surrogate in U+DC80–U+DCFF. Verified on
this machine:

```
$ python a.py $'caf\xe9'
'caf\udce9'
```

So an operator on a latin-1 terminal, or one pasting a mis-decoded name, types
`agsoc series new the-brief --name 'café'` and gets a raw `UnicodeEncodeError`
traceback out of the guts of `atomic_write`. That is the D-020 shape once more:
a stack trace where an actionable message belongs.

**What should happen:** reject it at the boundary with a `SeriesError`, because
the data genuinely cannot be stored. Something on the order of

```python
try:
    name.encode("utf-8")
except UnicodeEncodeError:
    raise SeriesError(
        f"series name contains bytes that are not valid UTF-8 — "
        "retype it, or check your terminal's encoding"
    )
```

in `scaffold_series` before any write. I did **not** implement this: it is
outside this brief's scope and it deserves its own test. Right now nothing
calls `scaffold_series` from `cli.py` — the `agsoc series new` subcommand is
not wired yet — so this is not yet operator-reachable. **It becomes reachable
the moment the CLI lands.** That makes it a Task 3 concern, not a Phase 4 one.
I would fix it in whatever task wires the command.

### Q2 — Are `series.toml` and `coverage.json` consistent about encoding now?

**Almost. One character still differs: U+007F.** `json.dumps(ensure_ascii=False)`
escapes `"`, `\`, and controls below U+0020, but it writes U+007F *raw*. Our
escaper escapes it. Same input, two files:

```
series.toml    b'name       = "a\\u007Fb"'
coverage.json  b'  "series": "a\\x7fb",'
```

This is a byte-level divergence, not a correctness bug — a raw DEL is legal in
a JSON string (JSON only forbids U+0000–U+001F unescaped), and I confirmed the
value round-trips through `json.loads` unchanged, which
`test_hostile_name_round_trips_through_coverage_json_too` pins. So both files
are valid and both preserve the string; they simply spell one control character
differently, because their two formats have different rules. On the question
that actually matters — non-ASCII is written literally as UTF-8, never as
`\uXXXX` — the two files now agree, where before this task they flatly
contradicted each other.

The one place they still fail *together* is Q1's lone surrogate: `json.dumps`
returns a `str` containing the surrogate and the `UnicodeEncodeError` surfaces
at write time for `coverage.json` too. A single guard on `name` fixes both.

### Q3 — What else in `series.py` still reaches the system unvalidated?

`acts` and `warm_acts` are done, but they were not the last ones. Verified by
loading crafted files:

| Field | Accepted today | Why it matters |
|---|---|---|
| `tolerance_sec` | `"eight"`, `-99`, `true` | **The biggest remaining hole.** It sits one line below `target_sec`, which is strictly validated for exactly this, and gets nothing. Phase 4 will do arithmetic with it. |
| `name` | `5`, `["a"]` | `Series.name` becomes an int or a list. Anything rendering it as text, or re-escaping it through `_toml_str`, will raise a `TypeError` far from here. |
| `byline` | any type | same shape as `name`, lower stakes. |
| `cadence` / `register` | `"whenever"`, `"shouty"` | The template documents closed sets (`daily\|weekly\|adhoc`, `reported\|first-person`). `cadence` is explicitly advisory, so leaving it open is defensible; `register` is not advisory — Phase 4 branches on it, and a typo will silently pick a default branch. |
| `design.*` values | `accent = 5` | `_table` checks only that `[design]` is a table; every token inside is unchecked. Phase 4 interpolates these into rendered output, so this is both a type hole and — for string values — an injection surface into whatever markup the renderer emits. It wants its own escaping decision, not just a type check. |

My recommendation, in priority order: `tolerance_sec` (trivial, and its absence
next to a validated `target_sec` reads as an oversight), then `name`/`byline`
types, then a decision on `register`, then `design` tokens as part of the
Phase 4 renderer task that owns their meaning.

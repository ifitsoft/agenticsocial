# Task 2 QA Review — series scaffolding and `series.toml` loading

Reviewed: `88752ac`, `52c3e4c`, `8a49f9a` (diff `7e240eb..8a49f9a`).
Reviewer did **not** read `task-2-report.md`.

## Verdict

**changes-required** — one operator-reachable defect that leaves the workspace in
an unrecoverable state (F1), one strict-validation path that raises `TypeError`
instead of `SeriesError` (F2), plus six surviving mutants showing real coverage
holes (F4).

The implementation is a faithful, character-accurate transcription of the brief:
`models.py`, `series.py`, `__init__.py` and the one-line `workspace.py` change all
match the brief's code blocks exactly, the test file matches the brief's block
exactly, and the Step 0 deletion removed exactly the named function and its
padding. Nothing extra, nothing missing (checklist 1 and 8: clean). Every finding
below is therefore a **brief-level** defect, not implementer deviation — but they
are still defects in the merged code.

Full suite: **130 passed**, matching the brief's prediction.

---

## Findings

### F1 — HIGH · `scaffold_series` corrupts the workspace when `name` contains `"`, `\` or a newline

`src/agenticsocial/video/series.py:96` (`SERIES_TEMPLATE.format(...)`) and `:97`
(`COVERAGE_TEMPLATE.format(...)`).

Both templates interpolate `name` straight into a TOML basic string and a JSON
string literal with no escaping. `str.format` does not escape anything.

Repro:

```python
ws = Workspace.init(tmp / "workspace")
scaffold_series(ws, "the-brief", name='Ali\'s "Brief"')
# SeriesError: .../series/the-brief/series.toml: malformed series.toml —
#              Expected newline or end of document after a statement (at line 2, column 22)
```

Three separate problems compound:

1. **Both files are written corrupt.** `series.toml` fails `tomllib`;
   `coverage.json` fails `json.loads` (`Expecting ',' delimiter: line 2 column 23`).
   The JSON corruption is *silent* — nothing validates `coverage.json` at scaffold
   time, so it only surfaces in Phase 11 when the dedup ledger is read.
2. **The error blames the operator's file.** The message is
   "malformed series.toml", as if a human had hand-edited it. The tool wrote it
   one line earlier.
3. **It is unrecoverable without `rm -rf`.** The partial directory survives the
   raise (no cleanup around `mkdir` + two `atomic_write`s), so the obvious retry
   fails:

```python
scaffold_series(ws, "the-brief", name="The Brief")
# SeriesError: series already exists: the-brief
```

Reachability: Task 3's `agsoc series new <slug> --name "..."` is the intended
caller, so `name` is arbitrary operator text on a shell command line. A
publication name containing a straight double quote or an em-dash-free
`Foo "Bar"` is unusual but not exotic; a Windows-style path or `\` in a name is
rarer. Backslash and newline reproduce the same three symptoms.

Fix: escape at interpolation — `json.dumps(name)` for the JSON template (it emits
its own quotes, so drop the literal `"` around `{name}`), and for TOML either
`json.dumps(name)` again (TOML basic strings are JSON-string-compatible for these
cases) or `tomllib`'s inverse via a small `_toml_str()` helper. Additionally wrap
the body of `scaffold_series` so a failure removes the directory it just created,
and validate/round-trip both files before returning.

### F2 — MEDIUM · non-string entries in `formats.enabled` raise `TypeError`, not `SeriesError`

`src/agenticsocial/video/series.py:86-89`.

`formats` is one of the two things the brief declares **strictly** validated, but
the guard assumes the list holds strings:

```toml
[series]
name = "X"
[formats]
enabled = [1, 2]
```

```
TypeError: sequence item 0: expected str instance, int found
```

— from `', '.join(unknown)`. The caller catches `SeriesError`, so this escapes as
an uncaught traceback out of `agsoc series list` / `load_series`. Exactly the
"blows up in a confusing way" case the strict boundary exists to prevent.

Related, same block: `enabled = "vertical"` (a bare string, a very natural typo —
the operator drops the brackets) iterates *characters* and produces
`unknown format(s) v, e, r, t, i, c, a, l — one of: vertical, wide`. It is a
`SeriesError`, so it is contained, but the message is nonsense.

Fix: before the membership check, require
`isinstance(formats, list) and all(isinstance(f, str) for f in formats)`, else
`raise SeriesError(f"{path}: [formats] enabled must be a list of strings")`.

### F3 — MEDIUM · `[series]` as a non-table raises `AttributeError`

`src/agenticsocial/video/series.py:79` — `meta = raw.get("series", {})`.

```toml
series = "hello"
```

```
AttributeError: 'str' object has no attribute 'get'
```

Same for `runtime`, `design`, `structure` (`runtime = 5`, etc.) — though those
happen to survive because `.get` is only reached on `runtime`/`structure`, and
`formats = "x"` at top level is swallowed by `raw.get("formats", {}).get(...)`
returning the default. `series` is the one that crashes, and `[series]` is the one
table every file has.

The brief's "tolerant" rule is about *missing* keys, not *wrong-typed tables*; an
`AttributeError` traceback is not a tolerant failure. Same class of problem:
`series.toml` existing as a *directory* gives an uncaught `IsADirectoryError`
(only `TOMLDecodeError` is caught at `:74`).

Fix: coerce non-dict sections to `{}`, or catch `OSError` alongside
`tomllib.TOMLDecodeError` and re-raise as `SeriesError` naming the path.

### F4 — MEDIUM · six mutants survive; four are loader defaults that no test reaches

Full table in "What I verified". The substantive ones:

- **Loader defaults for `cadence`, `register`, `tolerance_sec` are untested.**
  `src/agenticsocial/video/series.py:104-107`. `test_scaffolded_series_loads_with_expected_defaults`
  asserts `cadence == "daily"` / `tolerance_sec == 8`, but it *scaffolds first*, so
  the template supplies those values explicitly and the loader's fallback never
  runs. `test_minimal_config_loads_with_defaults` — the only test that exercises
  the fallbacks — asserts only `target_sec`, `formats`, `acts`, `byline`. Changing
  `meta.get("cadence", "daily")` to `"weekly"` keeps 130 tests green.
  Fix: add `cadence`, `register`, `tolerance_sec` assertions to
  `test_minimal_config_loads_with_defaults`.
- **`meta.get("name", slug)` fallback is untested.** `:103`. `test_scaffold_defaults_name_to_slug`
  looks like it covers this, but it scaffolds, and the scaffold writes
  `name = "cardio-weekly"` into the file — so it kills the *scaffold-side*
  fallback (`name = name or slug`, verified) and not the loader's. A `series.toml`
  with no `name` key is completely uncovered; changing the fallback to
  `"UNNAMED"` keeps 130 green.
  Fix: add a `name`-less minimal config to `test_minimal_config_loads_with_defaults`.
- **The on-disk directory name `series/` is not pinned.** `src/agenticsocial/workspace.py:82`.
  Renaming it to `shows/` keeps **all 130 tests green**, because
  `test_scaffold_creates_the_layout` asserts `s.dir == ws.series_dir / "the-brief"`
  — both sides derive from the same attribute, so the assertion is tautological
  with respect to the literal. Spec §5 fixes this path on disk and Phase 11
  relocates `coverage.json` into it.
  Fix: one assertion — `assert ws.series_dir == ws.root / "series"`.

### F5 — LOW · `[structure] warm_acts` is written by the scaffold and silently dropped by the loader

`SERIES_TEMPLATE` line `warm_acts = []` (`series.py:38`) and spec §6 both carry it,
but `load_series` reads only `structure.get("acts", [])` and `Series` has no
`warm_acts` field. An operator who sets `warm_acts = ["03"]` — the one documented
way to opt an act into `accent_warm` — gets no error and no effect. Nothing
consumes it yet, so this is latent rather than broken today, but it means
`models.py` and `series.py` both get re-opened when `accent_warm` lands.
Fix: add `warm_acts: list[str] = field(default_factory=list)` now, or delete the
line from the template until it is wired.

### F6 — LOW · no slug validation; `scaffold_series(ws, "../escape")` writes outside `series_dir`

`series.py:93` — `d = ws.series_dir / slug`, no normalisation. `slug="../escape"`
resolves outside the series tree, `slug="a/b"` creates a nested layout that
`list_series` will never list (it only scans one level). `slug=""` gives the
comically wrong `SeriesError: series already exists: ` (because `series_dir / ""`
is `series_dir`, which exists once anything has been scaffolded). Task 3 takes the
slug from `argv`. Not a security boundary in a local-first CLI, but it is a
confusing failure mode.
Fix: reject a slug that is not `^[a-z0-9][a-z0-9-]*$`, reusing `slugify` if
appropriate.

### F7 — NOTE · answers to the two questions the brief asked

- **`bool`/`int` wart** (`:99`): confirmed live. `target_sec = true` loads as
  `target_sec == True`, i.e. 1 second; `target_sec = false` is caught only by the
  `<= 0` arm. Spec §6 derives pace as `target_sec / sum(beat holds)`, so `true`
  yields a one-second episode with no diagnostic. It costs one clause —
  `isinstance(target_sec, bool)` — and I would fix it. Low severity because nobody
  writes `target_sec = true`.
- **`load_series` raising inside `list_series`** (`:117`): I confirmed one
  malformed `series.toml` makes `list_series` raise and list nothing —
  `list_series` on a workspace with a good `good/` and a broken `bad/` returns no
  results at all. For a *list* command that is wrong: listing is the operator's
  tool for finding out what state they are in, and it should degrade, not vanish.
  I would have `list_series` skip-and-warn (or return a partial list plus errors)
  and let `load_series` stay strict for direct callers. Not blocking; no CLI
  consumes it yet.

---

## What I verified

**Static conformance (checklist 1, 6, 8).** `git show 8a49f9a` byte-compared
against the brief's Step 4a–4d code blocks: identical. `git diff` on
`workspace.py` is exactly the one added line at `:82`; `Workspace.init` does not
create `series/` (verified on a fresh workspace: `(root/"series").exists()` is
`False` after `init`) and `Workspace.locate` still only requires `sources/` — a v1
workspace with no `series/` locates fine and `list_series` returns `[]`. The
committed `tests/test_video_series.py` diffs clean against the brief's block
(only the closing markdown fence differs) and is unchanged between `52c3e4c` and
`HEAD`, so the RED phase is genuine. Step 0 removed exactly the four lines named.

**Round-trip (checklist 2).** `SERIES_TEMPLATE` → `scaffold_series` →
`load_series` produces exactly the documented defaults:
`name="The Brief"`, `slug="the-brief"`, `byline=""`, `cadence="daily"`,
`register="reported"`, `target_sec=120`, `tolerance_sec=8`,
`formats=["vertical","wide"]`, `acts=[]`, and all eight `design` tokens including
`accent="#2E6BFF"` / `surface="#F2F5F8"`. **No drift** between template and
loader for ASCII names. I also confirmed the spec §6 *inline* acts form
(`acts = [ { id = "cold-open", ... } ]`) loads identically to the template's
commented `[[structure.acts]]` form.

**`COVERAGE_TEMPLATE` (checklist 3).** Valid JSON after `.format()` for ordinary
names — the doubled braces are correct and `json.loads` round-trips, with
`series == "The Brief"`, `episodes == []`, `conventions` present. It breaks for
`"`, `\`, and newline in `name` — see F1, and note the corruption is silent for
the JSON (no scaffold-time parse) and only surfaces because the *TOML* file
happens to break on the same characters. A name containing `{slug}` is safe
(`.format` only expands the outer call's placeholders once).

**Validation boundary (checklist 4).** Fifteen wrong-type configs run through
`load_series`. Tolerated as designed (loads, no error): `byline = 42`,
`acts = "not a list"` (loads the string; later `for a in s.acts` will iterate
characters), `acts = ["a","b"]`, `design = "nope"` (top-level key shadowed by the
`[design]` lookup → `{}`), `[design] accent = 5`, `name = 1`,
`tolerance_sec = "lots"`, `formats = "x"` / `runtime = 5` as top-level scalars.
Correctly rejected: `target_sec = 0`, `= "two minutes"`, `= 120.5`, `= false`,
`enabled = []`, `enabled = ["square"]`. Blew up wrongly: F2 (`enabled = [1,2]` →
`TypeError`), F3 (`series = "hello"` → `AttributeError`;
`series.toml` as a directory → `IsADirectoryError`). Passed through as `True`:
`target_sec = true` (F7).

**`atomic_write` (checklist 7).** Both call sites are preceded by
`(d / "episodes").mkdir(parents=True)`, which creates `d`, so
`mkstemp(dir=path.parent)` always has an existing parent. No defect. (The
`.exists()` guard at `:94` also means `d` is never pre-existing at that point.)
`atomic_write` itself unlinks its temp file on failure, so F1 leaves no `.tmp`
litter — only the two corrupt real files.

**Mutation testing (checklist 5).** 34 mutants; source restored via
`git checkout` after each. Two of the first-pass mutants (`M18b`, an escaping
error in my own shell quoting, and `M19` / `M30`-style message edits that left the
matched substring intact) were invalid and re-run correctly as `M18c`, `M19b`,
`M30`. Results:

| # | Mutation | Result |
|---|---|---|
| M1 | remove `unknown formats` check | **killed** (1 failed) |
| M2 | remove empty-`formats` check | **killed** |
| M3 | remove `target_sec` check | **killed** (2 failed) |
| M4a | loader default `target_sec` 120→60 | **killed** |
| M4b | template `target_sec` 120→60 | **killed** |
| M4c | loader default `cadence` `daily`→`weekly` | **SURVIVED** |
| M4d | template `cadence` `daily`→`weekly` | **killed** |
| M5 | `scaffold_series` overwrites instead of raising | **killed** |
| M6 | drop `coverage.json` creation | **killed** (2 failed) |
| M7 | loader default `register` `reported`→`XXX` | **SURVIVED** |
| M8 | loader default `tolerance_sec` 8→99 | **SURVIVED** |
| M9 | loader default `byline` `""`→`XXX` | **killed** |
| M10 | loader `name` fallback `slug`→`"UNNAMED"` | **SURVIVED** |
| M11 | loader `formats` fallback → `["wide"]` | **killed** |
| M12 | loader `acts` fallback → non-empty | **killed** |
| M13 | template `tolerance_sec` 8→99 | **killed** |
| M14 | template `register` → `first-person` | **killed** |
| M15 | template `accent` colour changed | **killed** |
| M16 | template `ink` colour changed | **SURVIVED** (only `accent` + `surface` are pinned; acceptable) |
| M17b | template `formats` → `["wide"]` only | **killed** |
| M18c | missing-series message drops `agsoc series new` hint | **killed** |
| M19b | malformed message drops `{path}` | **killed** |
| M20 | `list_series` drops the `is_dir()` guard | **killed** |
| M21 | `list_series` stops skipping non-series dirs | **killed** |
| M22 | `list_series` returns unsorted | **killed** |
| M23 | `coverage.json` `name` not interpolated | **killed** |
| M24 | `coverage.json` `conventions` key renamed | **killed** |
| M25 | `coverage.json` `episodes` non-empty | **killed** |
| M26 | scaffold does not create `episodes/` | **killed** |
| M27 | scaffold `name` fallback `slug`→`"UNTITLED"` | **killed** |
| M28 | `load_series` path indirection (sanity check) | **killed** (15 failed) |
| M29 | scaffold error message drops `already exists` | **killed** |
| M31 | empty-formats message drops `at least one` | **killed** |
| M32 | `target_sec` message drops the word `target_sec` | **killed** (2 failed) |
| M33 | `FORMATS` gains `"square"` | **killed** (2 failed) |
| M34 | `Workspace.series_dir` renamed `series/`→`shows/` | **SURVIVED** |
| M35 | remove the missing-series existence guard | **killed** |

**28 killed, 6 survived.** M16 is a deliberate, acceptable gap. M4c/M7/M8/M10/M34
are F4.

**Tree state.** `git status --porcelain` shows no modified source or test file.
The only modified tracked file is `docs/superpowers/worklog/video/DECISIONS.md`,
which changed *during* this review and which I did not touch (the brief notes the
orchestrator edits worklog docs concurrently). Untracked: `task-2-report.md`
(unread, per instruction), `task-3-brief.md`, and this file. Nothing committed.

---

## What I could not verify

- **Whether F1 is reachable in practice** — Task 3's CLI surface does not exist
  yet, so I inferred the `--name` path from the brief's `scaffold_series(ws, slug, name=None)`
  signature and spec §6. If Task 3 slugifies or restricts `name`, F1 shrinks to a
  library-level defect.
- **Downstream consequences of the tolerant path.** `acts = "not a list"`,
  `tolerance_sec = "lots"` and `target_sec = True` all load cleanly; I could not
  confirm *where* they eventually fail, because no consumer of `Series` exists yet.
  Whether those become confusing Phase-3 tracebacks is a Task 3+ question.
- **`Episode` is entirely unexercised** — defined in `models.py` per the brief but
  imported by nothing and covered by no test. Deferred to Task 3 by design; I did
  not review it beyond confirming it matches the brief character for character.
- **Concurrency.** Two simultaneous `scaffold_series` calls for the same slug race
  between `d.exists()` and `mkdir(parents=True)`; the loser gets `FileExistsError`,
  not `SeriesError`. Not tested — single-operator local-first tool, low value.
- **`coverage.json` schema correctness** against Phase 11's reader, which does not
  exist. I verified only that it is valid JSON with the three keys the test names.

# Task 2b Brief: Harden series config against malformed input

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `8a49f9a`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

QA reviewed Task 2 with 34 mutants; 28 killed, 6 survived. It confirmed the
implementation was a character-exact transcription of my brief — so **every
finding below is a defect in my brief, not in the previous implementer's work.**

The one that matters:

```python
scaffold_series(ws, "the-brief", name='He said "hi"')
```

Naive `.format()` interpolation writes a **corrupt `series.toml` and a corrupt
`coverage.json`**, then reports "malformed series.toml" as though the operator
hand-edited it — and leaves the partial directory behind, so the obvious retry
fails with `series already exists`. Unrecoverable without `rm -rf`. Same for `\`
and newlines. This is the operator's first contact with the product.

Also: renaming `series/` → `shows/` in `Workspace` passes all 130 tests, because
`assert s.dir == ws.series_dir / "the-brief"` compares an attribute against
itself. Spec §5 fixes that directory name; nothing pins it.

## Ground rules

- **Two commits.** Failing tests first, then the implementation. Do not squash.
- **Pipe command output to a file and paste from it.** Do not hand-transcribe.
- Code blocks are authoritative. Prose explains *why*. If they disagree, follow
  the code block **and flag it** — four earlier briefs of mine had that defect.
- Do not modify existing tests except the two amendments named in Step 1b.
- Do not add dependencies. `json`, `re`, `shutil` are stdlib.
- Never stage anything under `docs/`.
- Predicted counts are my arithmetic. Report what you observe.

## Files

- Modify: `src/agenticsocial/video/series.py`
- Modify: `src/agenticsocial/video/models.py` (add one field — Step 2b)
- Modify: `tests/test_video_series.py` (append, plus two amendments)

---

- [ ] **Step 1a: Append the new tests**

Add to the end of `tests/test_video_series.py`:

```python
import json


# --- F1: hostile names must not corrupt the files they are written into -------


@pytest.mark.parametrize(
    "hostile",
    [
        'He said "hi"',
        "back\\slash",
        "line\nbreak",
        "tab\there",
        'both "quotes" and \\slashes\\',
    ],
)
def test_hostile_series_name_round_trips(ws, hostile):
    """A name is operator input. It must survive scaffold -> load unchanged."""
    scaffold_series(ws, "hostile", name=hostile)
    assert load_series(ws, "hostile").name == hostile


@pytest.mark.parametrize("hostile", ['He said "hi"', "back\\slash", "line\nbreak"])
def test_hostile_series_name_leaves_valid_coverage_json(ws, hostile):
    s = scaffold_series(ws, "hostile", name=hostile)
    data = json.loads((s.dir / "coverage.json").read_text(encoding="utf-8"))
    assert data["series"] == hostile
    assert data["episodes"] == []


def test_failed_scaffold_leaves_no_partial_directory(ws, monkeypatch):
    """If writing fails midway, the operator must be able to simply retry."""
    import agenticsocial.video.series as series_mod

    real = series_mod.atomic_write
    calls = {"n": 0}

    def explode(path, text):
        calls["n"] += 1
        if calls["n"] == 2:  # fail on coverage.json, after series.toml succeeded
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(series_mod, "atomic_write", explode)
    with pytest.raises(OSError):
        scaffold_series(ws, "doomed", name="Doomed")
    assert not (ws.series_dir / "doomed").exists()
    scaffold_series(ws, "doomed", name="Doomed")  # retry must now work


# --- F6: slugs become filesystem paths ---------------------------------------


@pytest.mark.parametrize(
    "bad", ["../escape", "a/b", "", ".", "..", "Upper", "has space", "-leading"]
)
def test_invalid_slug_is_rejected(ws, bad):
    with pytest.raises(SeriesError, match="slug"):
        scaffold_series(ws, bad)


def test_slug_rejection_happens_before_any_write(ws):
    with pytest.raises(SeriesError):
        scaffold_series(ws, "../escape")
    assert not (ws.root.parent / "escape").exists()


# --- F2: the strictly-validated path must raise SeriesError, never TypeError --


def _write_series(ws, slug, body):
    d = ws.series_dir / slug
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(body, encoding="utf-8")


def test_non_string_format_entries_raise_series_error(ws):
    _write_series(ws, "bad", '[series]\nname = "B"\n\n[formats]\nenabled = [1, 2]\n')
    with pytest.raises(SeriesError, match="list of strings"):
        load_series(ws, "bad")


def test_string_instead_of_format_list_raises_series_error(ws):
    """`enabled = "vertical"` must not be iterated character by character."""
    _write_series(ws, "bad", '[series]\nname = "B"\n\n[formats]\nenabled = "vertical"\n')
    with pytest.raises(SeriesError, match="list of strings"):
        load_series(ws, "bad")


# --- F3: wrong-typed sections must raise SeriesError, not AttributeError ------


@pytest.mark.parametrize(
    "body",
    [
        'series = "hello"\n',
        '[series]\nname = "B"\n\nruntime = 5\n',
        '[series]\nname = "B"\n\ndesign = "blue"\n',
        '[series]\nname = "B"\n\nstructure = true\n',
        '[series]\nname = "B"\n\nformats = 1\n',
    ],
)
def test_wrong_typed_section_raises_series_error(ws, body):
    _write_series(ws, "bad", body)
    with pytest.raises(SeriesError, match="must be a table"):
        load_series(ws, "bad")


def test_unreadable_series_toml_raises_series_error(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").mkdir()  # a directory where a file belongs
    with pytest.raises(SeriesError):
        load_series(ws, "bad")


# --- F7: bool is a subclass of int ---------------------------------------------


def test_boolean_target_sec_is_rejected(ws):
    """`target_sec = true` would otherwise load as a 1-second episode."""
    _write_series(ws, "bad", '[series]\nname = "B"\n\n[runtime]\ntarget_sec = true\n')
    with pytest.raises(SeriesError, match="target_sec"):
        load_series(ws, "bad")


# --- F4: pin the loader defaults the scaffold-first tests never reach ---------


def test_minimal_config_reaches_every_loader_default(ws):
    """QA mutated cadence, register, tolerance_sec and the name fallback; all
    four survived, because the only test touching them asserts none of them."""
    _write_series(ws, "minimal2", "[series]\n")
    s = load_series(ws, "minimal2")
    assert s.name == "minimal2"  # falls back to slug
    assert s.cadence == "daily"
    assert s.register == "reported"
    assert s.tolerance_sec == 8
    assert s.byline == ""
    assert s.design == {}
    assert s.warm_acts == []


# --- F4/mutant 6: pin the on-disk directory name that spec §5 fixes -----------


def test_series_dir_is_literally_named_series(ws):
    """`ws.series_dir / slug` compares an attribute to itself. Spec §5 fixes the
    on-disk name; renaming it to `shows/` passed all 130 tests."""
    assert ws.series_dir == ws.root / "series"
    s = scaffold_series(ws, "the-brief")
    assert s.dir == ws.root / "series" / "the-brief"
    assert (ws.root / "series" / "the-brief" / "series.toml").is_file()


# --- F5: warm_acts was written by the scaffold and dropped by the loader ------


def test_warm_acts_is_loaded(ws):
    _write_series(
        ws, "warm", '[series]\nname = "W"\n\n[structure]\nwarm_acts = ["03"]\n'
    )
    assert load_series(ws, "warm").warm_acts == ["03"]
```

- [ ] **Step 1b: Two amendments to existing tests**

Both are now wrong, not merely incomplete.

1. `test_malformed_toml_names_the_file` writes `"[series\nname ="`. Keep it as is
   — it still exercises `TOMLDecodeError`.
2. `test_minimal_config_loads_with_defaults` constructs its directory inline.
   Replace its two setup lines with the helper so there is one way to do it:

```python
def test_minimal_config_loads_with_defaults(ws):
    _write_series(ws, "minimal", '[series]\nname = "Minimal"\n')
    s = load_series(ws, "minimal")
    assert s.name == "Minimal"
    assert s.target_sec == 120
    assert s.formats == ["vertical", "wide"]
    assert s.acts == []
    assert s.byline == ""
```

`_write_series` is defined lower in the file than this test. That is fine at
runtime — it resolves at call time, not import time — but move `_write_series`
and `import json` to just below the `ws` fixture so the file reads top-down.

- [ ] **Step 2: Run and confirm failures, then commit the tests**

```bash
uv run pytest tests/test_video_series.py 2>&1 | tail -40
```

Record which fail. Then:

```bash
git add tests/test_video_series.py
git commit -m "test: pin series config against hostile names, bad types, and path escapes

QA mutation testing on 8a49f9a: 34 mutants, 6 survived. Four were loader
defaults no test reached; one was the on-disk directory name, pinned only
by a tautological assertion."
```

- [ ] **Step 3a: Add `warm_acts` to `Series`**

In `src/agenticsocial/video/models.py`, `Series` gains one field, placed directly
after `acts`:

```python
    acts: list[dict] = field(default_factory=list)
    warm_acts: list[str] = field(default_factory=list)
```

- [ ] **Step 3b: Rewrite `src/agenticsocial/video/series.py`**

Replace the whole file with:

```python
"""Series configuration: scaffolding and loading `series.toml`."""
from __future__ import annotations

import json
import re
import shutil
import tomllib

from ..workspace import Workspace, atomic_write
from .models import FORMATS, Series, SeriesError

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

SERIES_TEMPLATE = """\
[series]
name       = {name}
slug       = {slug}
byline     = ""
cadence    = "daily"              # daily | weekly | adhoc — advisory, nothing schedules
register   = "reported"           # reported | first-person

[runtime]
target_sec = 120                  # pace is derived: target_sec / sum(beat holds)
tolerance_sec = 8

[formats]
enabled = ["vertical", "wide"]    # vertical 1080x1920 · wide 1920x1080

[design]
surface     = "#F2F5F8"
ink         = "#0B1B2B"
ink_muted   = "#5A6B7C"
accent      = "#2E6BFF"
accent_alt  = "#00C2D7"
accent_warm = "#FF6B4A"           # reserved; see warm_acts
type_family = "SF Pro Display, Helvetica Neue, system-ui"
type_scale  = "default"           # default | compact | large

[structure]
warm_acts = []                    # acts permitted to use accent_warm

# [[structure.acts]]
# id = "01"
# label = "01 — The headline"
# beats = 6
"""

CONVENTIONS = {
    "id": "Stable kebab-case slug for a story THREAD, not a single day's article. Reuse the same id when the story returns.",
    "angle": "launch | analysis | incident | deployment | research | culture — what the beat actually did with the story.",
    "update": "Set true when an entry revisits an id covered on an earlier date. Put the earlier date in updateOf and say what is new in note.",
    "rule": "Before writing a new episode, check coverage. A hit means either skip it or run it as an explicit update — never re-tell it as if it were new.",
}


def _toml_str(value: str) -> str:
    """Render a TOML basic string.

    JSON's string escaping is a valid subset of TOML's basic-string escaping
    (both use \\", \\\\, \\n, \\t, \\uXXXX), so json.dumps produces a correct
    quoted TOML string. Interpolating raw operator input instead corrupts the
    file it is written into — see D-020.
    """
    return json.dumps(value)


def render_series_toml(name: str, slug: str) -> str:
    return SERIES_TEMPLATE.format(name=_toml_str(name), slug=_toml_str(slug))


def render_coverage_json(name: str) -> str:
    return (
        json.dumps(
            {"series": name, "conventions": CONVENTIONS, "episodes": []},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def _validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise SeriesError(
            f"invalid series slug {slug!r} — use lowercase letters, digits and "
            "hyphens, starting with a letter or digit (slugs become directory names)"
        )


def _table(raw: dict, key: str, path) -> dict:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise SeriesError(
            f"{path}: [{key}] must be a table, got {type(value).__name__}"
        )
    return value


def scaffold_series(ws: Workspace, slug: str, name: str | None = None) -> Series:
    _validate_slug(slug)
    d = ws.series_dir / slug
    if d.exists():
        raise SeriesError(f"series already exists: {slug}")
    name = name or slug
    (d / "episodes").mkdir(parents=True)
    try:
        atomic_write(d / "series.toml", render_series_toml(name, slug))
        atomic_write(d / "coverage.json", render_coverage_json(name))
        return load_series(ws, slug)
    except BaseException:
        # Leave nothing half-written: the operator's obvious next move is to
        # retry, and a partial directory would fail with "already exists".
        shutil.rmtree(d, ignore_errors=True)
        raise


def load_series(ws: Workspace, slug: str) -> Series:
    d = ws.series_dir / slug
    path = d / "series.toml"
    if not path.is_file():
        raise SeriesError(f"no series '{slug}' — create it with `agsoc series new {slug}`")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SeriesError(f"{path}: malformed series.toml — {e}")
    except OSError as e:
        raise SeriesError(f"{path}: cannot read series.toml — {e}")

    meta = _table(raw, "series", path)
    runtime = _table(raw, "runtime", path)
    design = _table(raw, "design", path)
    structure = _table(raw, "structure", path)

    formats = _table(raw, "formats", path).get("enabled", list(FORMATS))
    if not isinstance(formats, list) or not all(isinstance(f, str) for f in formats):
        raise SeriesError(f"{path}: [formats] enabled must be a list of strings")
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        raise SeriesError(
            f"{path}: unknown format(s) {', '.join(unknown)} — one of: {', '.join(FORMATS)}"
        )
    if not formats:
        raise SeriesError(f"{path}: [formats] enabled is empty — enable at least one")

    target_sec = runtime.get("target_sec", 120)
    if isinstance(target_sec, bool) or not isinstance(target_sec, int) or target_sec <= 0:
        raise SeriesError(f"{path}: [runtime] target_sec must be a positive integer")

    return Series(
        slug=slug,
        name=meta.get("name", slug),
        dir=d,
        byline=meta.get("byline", ""),
        cadence=meta.get("cadence", "daily"),
        register=meta.get("register", "reported"),
        target_sec=target_sec,
        tolerance_sec=runtime.get("tolerance_sec", 8),
        formats=formats,
        design=design,
        acts=structure.get("acts", []),
        warm_acts=structure.get("warm_acts", []),
    )


def series_slugs(ws: Workspace) -> list[str]:
    """Enumerate series slugs. Cannot fail on a malformed series — see D-018."""
    if not ws.series_dir.is_dir():
        return []
    return sorted(
        d.name for d in ws.series_dir.iterdir() if (d / "series.toml").is_file()
    )


def list_series(ws: Workspace) -> list[Series]:
    """Load every series. Strict: raises if ANY series is malformed.

    For partial results — which is what `agsoc series list` needs — iterate
    `series_slugs()` and load each inside a try/except. See D-018.
    """
    return [load_series(ws, s) for s in series_slugs(ws)]
```

`_toml_str` is deliberately not applied to the design tokens or comments in the
template: those are literals under our control, not operator input. Only `name`
and `slug` cross that boundary, and `slug` is already constrained by `SLUG_RE`.

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest tests/test_video_series.py -v 2>&1 | tail -40
uv run pytest 2>&1 | tail -5
```

Then:

```bash
git add src/agenticsocial/video/series.py src/agenticsocial/video/models.py
git commit -m "fix: escape operator input, validate config types, reject unsafe slugs

Hostile series names corrupted both series.toml and coverage.json and
left a partial directory that blocked the obvious retry. Wrong-typed
config sections escaped the SeriesError contract as AttributeError and
TypeError. Slugs became directory names unvalidated, so ../escape wrote
outside the workspace. Adds series_slugs() per D-018."
```

- [ ] **Step 5: Re-run QA's surviving mutants**

Confirm each now fails. Apply to `series.py`, run `uv run pytest 2>&1 | tail -3`,
`git checkout` between each:

1. loader default `cadence` `"daily"` → `"weekly"`
2. loader default `register` `"reported"` → `"XXX"`
3. loader default `tolerance_sec` `8` → `99`
4. loader `name` fallback `slug` → `"UNNAMED"`
5. in `workspace.py`: `self.series_dir = self.root / "shows"`

All five must now fail. Report any that survive — do not strengthen the tests
yourself, tell me the guard was inadequate. Finish with a clean
`git status --porcelain`.

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-2b-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped, from the test-only commit) and GREEN (both runs).
3. **Mutation re-test** — a row per mutant: mutation, result, which test caught it.
4. **Files changed** and both commit SHAs.
5. **Issues or concerns**, including:
   - Is `json.dumps` genuinely safe as a TOML basic-string escaper? Name any
     input where TOML and JSON escaping diverge. If you find one, that is a
     finding, not a footnote.
   - `scaffold_series` now catches `BaseException` to clean up. Is that right, or
     should a `KeyboardInterrupt` leave the directory for forensics?
   - Should `load_series` validate `acts` entries at all, or is "wrong shape
     blows up in Phase 4's renderer" acceptable?

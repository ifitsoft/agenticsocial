# Task 2 Brief: Series configuration

**Phase:** 1 — Series & episode scaffolding
**Branch:** `feat/video-phase-01-scaffolding` (already checked out)
**Follows:** Task 1b, commit `43799e5`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Ground rules

- **Three commits**, in order: Step 0's cleanup, then the failing tests, then the
  implementation. A reviewer must be able to verify the RED phase from git
  history rather than from your report. Do not squash.
- I may edit files under `docs/superpowers/worklog/` while you work — that is me
  recording decisions, not interference. Never stage anything under `docs/`.
- **Pipe command output to a file and paste from it.** Do not hand-transcribe.
- Do not modify any existing test.
- Do not add dependencies. `tomllib` is stdlib on Python 3.11+.
- Every code block below is authoritative — write exactly what it shows. Prose
  explains *why*; where prose and a code block appear to disagree, the code block
  wins and you should flag the contradiction in your report.
- If the brief is wrong, implement it as written and say so in your report.

## Context

Spec §6. A *series* is a recurring show — "The Brief", or a cardiologist's weekly
round-up. `series.toml` is the one file a new operator edits to make the product
theirs: palette, byline, act structure, target runtime, enabled formats. It
carries design tokens and structure, never layout code.

Loading is deliberately **tolerant** — a minimal file containing only
`[series] name` must load with sensible defaults, because an operator should be
able to delete anything they don't care about. Validation is **strict** on
exactly two things later phases depend on: `formats` and `target_sec`. A bad
format string must fail at load, not three phases later inside the renderer.

You are creating the `agenticsocial.video` package. Nothing depends on it yet.

## Files

- Create: `src/agenticsocial/video/__init__.py`
- Create: `src/agenticsocial/video/models.py`
- Create: `src/agenticsocial/video/series.py`
- Modify: `src/agenticsocial/workspace.py` (one line — see Step 4d)
- Create: `tests/test_video_series.py`

## Interfaces you must produce

Later tasks import these by these exact names:

- `agenticsocial.video.models`: `FORMATS: tuple[str, ...]`, `SeriesError`,
  `EpisodeError`, `Series`, `Episode`
- `agenticsocial.video.series`: `scaffold_series(ws, slug, name=None) -> Series`,
  `load_series(ws, slug) -> Series`, `list_series(ws) -> list[Series]`
- `agenticsocial.workspace.Workspace`: attribute `series_dir: Path`

---

- [ ] **Step 0: Delete one redundant test (its own commit)**

Unrelated to series config — a carried-over cleanup, committed separately so it
does not muddy the Task 2 diff.

Task 1c added `test_video_transitions_table_is_exact`, which strictly implies
four earlier per-key assertions. Three of those four keep their place because
their docstrings carry the *reasoning* (D-006, spec §3.1) and their names state
the broken invariant in the failure line — a table pin only reports "the dict
differs". `test_published_is_terminal_for_video` is the exception: no docstring,
no decision record behind it, fully implied by the pin. Redundancy without the
compensating rationale.

In `tests/test_video_status.py`, delete exactly this function and its blank-line
padding:

```python
def test_published_is_terminal_for_video():
    assert VIDEO_TRANSITIONS[Status.PUBLISHED] == set()
```

Then:

```bash
uv run pytest 2>&1 | tail -3
git add tests/test_video_status.py
git commit -m "test: drop an assertion the table pin already covers

test_published_is_terminal_for_video is implied by
test_video_transitions_table_is_exact and, unlike the other per-key
assertions, carries no docstring or decision record to justify keeping
the redundancy."
```

Expected after: 113 passed.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_video_series.py`:

```python
import pytest

from agenticsocial.video.models import SeriesError
from agenticsocial.video.series import list_series, load_series, scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


def test_scaffold_creates_the_layout(ws):
    s = scaffold_series(ws, "the-brief", name="The Brief")
    assert (s.dir / "series.toml").exists()
    assert (s.dir / "coverage.json").exists()
    assert (s.dir / "episodes").is_dir()
    assert s.dir == ws.series_dir / "the-brief"


def test_scaffold_is_not_destructive(ws):
    scaffold_series(ws, "the-brief")
    with pytest.raises(SeriesError, match="already exists"):
        scaffold_series(ws, "the-brief")


def test_scaffolded_series_loads_with_expected_defaults(ws):
    scaffold_series(ws, "the-brief", name="The Brief")
    s = load_series(ws, "the-brief")
    assert s.slug == "the-brief"
    assert s.name == "The Brief"
    assert s.target_sec == 120
    assert s.tolerance_sec == 8
    assert s.formats == ["vertical", "wide"]
    assert s.cadence == "daily"
    assert s.register == "reported"


def test_scaffold_defaults_name_to_slug(ws):
    scaffold_series(ws, "cardio-weekly")
    assert load_series(ws, "cardio-weekly").name == "cardio-weekly"


def test_scaffolded_coverage_json_is_valid_and_empty(ws):
    import json

    s = scaffold_series(ws, "the-brief", name="The Brief")
    data = json.loads((s.dir / "coverage.json").read_text(encoding="utf-8"))
    assert data["series"] == "The Brief"
    assert data["episodes"] == []
    assert "conventions" in data


def test_minimal_config_loads_with_defaults(ws):
    d = ws.series_dir / "minimal"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text('[series]\nname = "Minimal"\n', encoding="utf-8")
    s = load_series(ws, "minimal")
    assert s.name == "Minimal"
    assert s.target_sec == 120
    assert s.formats == ["vertical", "wide"]
    assert s.acts == []
    assert s.byline == ""


def test_design_tokens_are_loaded(ws):
    scaffold_series(ws, "the-brief")
    s = load_series(ws, "the-brief")
    assert s.design["accent"] == "#2E6BFF"
    assert s.design["surface"] == "#F2F5F8"


def test_acts_are_loaded_in_order(ws):
    d = ws.series_dir / "acted"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Acted"\n\n'
        '[[structure.acts]]\nid = "01"\nlabel = "One"\nbeats = 6\n\n'
        '[[structure.acts]]\nid = "02"\nlabel = "Two"\nbeats = 4\n',
        encoding="utf-8",
    )
    s = load_series(ws, "acted")
    assert [a["id"] for a in s.acts] == ["01", "02"]
    assert s.acts[0]["beats"] == 6


def test_unknown_format_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[formats]\nenabled = ["square"]\n', encoding="utf-8"
    )
    with pytest.raises(SeriesError, match="square"):
        load_series(ws, "bad")


def test_empty_format_list_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[formats]\nenabled = []\n', encoding="utf-8"
    )
    with pytest.raises(SeriesError, match="at least one"):
        load_series(ws, "bad")


def test_non_positive_runtime_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[runtime]\ntarget_sec = 0\n', encoding="utf-8"
    )
    with pytest.raises(SeriesError, match="target_sec"):
        load_series(ws, "bad")


def test_non_integer_runtime_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[runtime]\ntarget_sec = "two minutes"\n',
        encoding="utf-8",
    )
    with pytest.raises(SeriesError, match="target_sec"):
        load_series(ws, "bad")


def test_missing_series_is_actionable(ws):
    with pytest.raises(SeriesError, match="agsoc series new"):
        load_series(ws, "nope")


def test_malformed_toml_names_the_file(ws):
    d = ws.series_dir / "broken"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text("[series\nname =", encoding="utf-8")
    with pytest.raises(SeriesError, match="series.toml"):
        load_series(ws, "broken")


def test_list_series_is_sorted_and_skips_non_series_dirs(ws):
    scaffold_series(ws, "zulu")
    scaffold_series(ws, "alpha")
    (ws.series_dir / "not-a-series").mkdir()
    assert [s.slug for s in list_series(ws)] == ["alpha", "zulu"]


def test_list_series_on_empty_workspace(ws):
    assert list_series(ws) == []


def test_scaffold_does_not_disturb_the_text_pipeline(ws):
    """series/ is additive; v1 workspaces have no series/ and must still work."""
    scaffold_series(ws, "the-brief")
    assert ws.sources_dir.is_dir()
    assert (ws.root / "voice.md").exists()
```

- [ ] **Step 2: Run and confirm they fail**

```bash
uv run pytest tests/test_video_series.py 2>&1 | tail -15
```

Expected: a collection error —
`ModuleNotFoundError: No module named 'agenticsocial.video'`

Record the observed output.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_video_series.py
git commit -m "test: specify series scaffolding and series.toml loading"
```

- [ ] **Step 4: Implement**

**4a.** Create `src/agenticsocial/video/__init__.py`:

```python
"""Video pipeline: series, episodes, scripts, verification, rendering."""
```

**4b.** Create `src/agenticsocial/video/models.py`:

```python
"""Domain model for video series and episodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models import Status

FORMATS = ("vertical", "wide")


class SeriesError(Exception):
    pass


class EpisodeError(Exception):
    pass


@dataclass
class Series:
    slug: str
    name: str
    dir: Path
    byline: str = ""
    cadence: str = "daily"
    register: str = "reported"
    target_sec: int = 120
    tolerance_sec: int = 8
    formats: list[str] = field(default_factory=lambda: ["vertical", "wide"])
    design: dict = field(default_factory=dict)
    acts: list[dict] = field(default_factory=list)

    @property
    def episodes_dir(self) -> Path:
        return self.dir / "episodes"


@dataclass
class Episode:
    id: str
    series_slug: str
    dir: Path
    status: Status
    meta: dict = field(default_factory=dict)

    @property
    def script_path(self) -> Path:
        return self.dir / "script.yaml"

    @property
    def sources_dir(self) -> Path:
        return self.dir / "sources"

    @property
    def out_dir(self) -> Path:
        return self.dir / "out"
```

`Episode` is defined here but unused until Task 3. That is intentional — the two
dataclasses are one unit of meaning and splitting them across tasks would mean
editing this file twice.

**4c.** Create `src/agenticsocial/video/series.py`:

```python
"""Series configuration: scaffolding and loading `series.toml`."""
from __future__ import annotations

import tomllib

from ..workspace import Workspace, atomic_write
from .models import FORMATS, Series, SeriesError

SERIES_TEMPLATE = """\
[series]
name       = "{name}"
slug       = "{slug}"
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

COVERAGE_TEMPLATE = """\
{{
  "series": "{name}",
  "conventions": {{
    "id": "Stable kebab-case slug for a story THREAD, not a single day's article. Reuse the same id when the story returns.",
    "angle": "launch | analysis | incident | deployment | research | culture — what the beat actually did with the story.",
    "update": "Set true when an entry revisits an id covered on an earlier date. Put the earlier date in updateOf and say what is new in note.",
    "rule": "Before writing a new episode, check coverage. A hit means either skip it or run it as an explicit update — never re-tell it as if it were new."
  }},
  "episodes": []
}}
"""


def scaffold_series(ws: Workspace, slug: str, name: str | None = None) -> Series:
    d = ws.series_dir / slug
    if d.exists():
        raise SeriesError(f"series already exists: {slug}")
    (d / "episodes").mkdir(parents=True)
    name = name or slug
    atomic_write(d / "series.toml", SERIES_TEMPLATE.format(name=name, slug=slug))
    atomic_write(d / "coverage.json", COVERAGE_TEMPLATE.format(name=name))
    return load_series(ws, slug)


def load_series(ws: Workspace, slug: str) -> Series:
    d = ws.series_dir / slug
    path = d / "series.toml"
    if not path.exists():
        raise SeriesError(f"no series '{slug}' — create it with `agsoc series new {slug}`")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SeriesError(f"{path}: malformed series.toml — {e}")

    meta = raw.get("series", {})
    runtime = raw.get("runtime", {})
    design = raw.get("design", {})
    structure = raw.get("structure", {})

    formats = raw.get("formats", {}).get("enabled", list(FORMATS))
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        raise SeriesError(
            f"{path}: unknown format(s) {', '.join(unknown)} — one of: {', '.join(FORMATS)}"
        )
    if not formats:
        raise SeriesError(f"{path}: [formats] enabled is empty — enable at least one")

    target_sec = runtime.get("target_sec", 120)
    if not isinstance(target_sec, int) or target_sec <= 0:
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
    )


def list_series(ws: Workspace) -> list[Series]:
    if not ws.series_dir.is_dir():
        return []
    slugs = sorted(
        d.name for d in ws.series_dir.iterdir() if (d / "series.toml").exists()
    )
    return [load_series(ws, s) for s in slugs]
```

Note on `isinstance(target_sec, int)`: in Python `bool` is a subclass of `int`, so
`target_sec = true` in TOML would pass this check and then fail as `<= 0` only if
false. This is a known wart; do not fix it in this task — flag it in your report
if you think it matters.

**4d.** In `src/agenticsocial/workspace.py`, `Workspace.__init__` must read
exactly:

```python
    def __init__(self, root: Path):
        self.root = Path(root)
        self.sources_dir = self.root / "sources"
        self.series_dir = self.root / "series"
```

Nothing else in `workspace.py` changes. In particular `Workspace.init` must not
create `series/`, and `Workspace.locate` must not require it — v1 workspaces on
disk have no `series/` directory and must keep loading. `scaffold_series` creates
it on demand via `mkdir(parents=True)`.

- [ ] **Step 5: Run everything**

```bash
uv run pytest tests/test_video_series.py -v 2>&1 | tail -25
uv run pytest 2>&1 | tail -5
```

Expected: 17 passed in the new file; **130 passed overall** (113 after Step 0,
plus 17 new). If a pre-existing test fails, **stop and report** — do not edit it.

Arithmetic is my prediction, not gospel. If your count differs, report the number
you observe and do not adjust anything to reach mine.

- [ ] **Step 6: Commit the implementation**

```bash
git add src/agenticsocial/video/ src/agenticsocial/workspace.py
git commit -m "feat: add series scaffolding and series.toml loading"
```

---

## Your report

Write `docs/superpowers/worklog/video/phase-01/task-2-report.md`:

1. **What I implemented.**
2. **TDD evidence** — `### RED` (piped output from the test-only commit) and
   `### GREEN` (both final runs, piped).
3. **Files changed** and both commit SHAs.
4. **Self-review findings.**
5. **Issues or concerns** — including your view on the `bool`/`int` wart in 4c,
   and on whether `load_series` raising inside `list_series` is right: one
   malformed `series.toml` currently makes `agsoc series list` fail entirely
   rather than listing the good ones. Say which behaviour you think is correct.

Do not update `PROGRESS.md` or `DECISIONS.md`.

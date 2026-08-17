# Phase 1 — Series & Episode Scaffolding: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the on-disk structure and status machine for video series and episodes, so later phases have somewhere to write and a lifecycle to move through.

**Architecture:** A new `agenticsocial.video` package holds all video domain code. The shared `Status` enum gains two states and a second transition table, so text variants and video episodes have separate lifecycles without a second enum. Series and episode state live on disk exactly as the spec's workspace layout describes; the CLI gains `series` and `video` Typer sub-apps.

**Tech Stack:** Python ≥3.11, typer, pyyaml, tomllib (stdlib, read-only), pytest.

**Spec:** `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md` — §5 (workspace layout), §6 (series config), §10 (status machine), §11 (CLI surface).

**Roadmap:** `docs/superpowers/plans/2026-08-16-video-mvp-roadmap.md`

**Branch:** `feat/video-phase-01-scaffolding`

## Global Constraints

- Python `>=3.11`. No new third-party dependencies in this phase.
- All writes under `workspace/` go through `workspace.atomic_write` — never `Path.write_text` for content files. Directory creation uses `mkdir`.
- Only the CLI moves status. Nothing in this phase auto-advances a status.
- `uv run pytest` must pass in full after every task, not just the new tests.
- No network access in any test.
- Formats are exactly `vertical` (1080×1920) and `wide` (1920×1080).
- Status values are the literal strings: `draft`, `in_review`, `approved`, `scheduled`, `rendering`, `rendered`, `publishing`, `published`, `failed`.
- Existing text-pipeline behaviour must not change. Every currently-passing test stays passing, unmodified.

## File Structure

| File | Responsibility |
|---|---|
| `src/agenticsocial/models.py` *(modify)* | Add `RENDERING`/`RENDERED`; add `VIDEO_TRANSITIONS`; make transition checking table-aware |
| `src/agenticsocial/workspace.py` *(modify)* | Add `series_dir` |
| `src/agenticsocial/video/__init__.py` | Package marker |
| `src/agenticsocial/video/models.py` | `Series`, `Episode` dataclasses; `SeriesError` |
| `src/agenticsocial/video/series.py` | Scaffold, load, list series; `series.toml` + `coverage.json` templates |
| `src/agenticsocial/video/episode.py` | Create, resolve, list episodes; read/write episode status |
| `src/agenticsocial/video/cli.py` | `series` and `video` Typer sub-apps |
| `src/agenticsocial/cli.py` *(modify)* | Register the two sub-apps |
| `tests/test_video_status.py` | Task 1 |
| `tests/test_video_series.py` | Task 2 |
| `tests/test_video_episode.py` | Task 3 |
| `tests/test_video_cli.py` | Task 4 |

---

### Task 1: Video status machine

**Files:**
- Modify: `src/agenticsocial/models.py`
- Test: `tests/test_video_status.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Status.RENDERING`, `Status.RENDERED`; `VIDEO_TRANSITIONS: dict[Status, set[Status]]`; `assert_transition(current: Status, target: Status, table: dict[Status, set[Status]] | None = None) -> None`; `TransitionError(current: Status, target: Status, table: dict | None = None)`.

**Context:** `models.py` currently defines `ALLOWED_TRANSITIONS` for text variants and hardcodes it inside both `assert_transition` and `TransitionError`. Video episodes need a different lifecycle. Rather than a second enum (which would make `status: approved` mean two different things), we add a second table and pass it explicitly. The default stays `ALLOWED_TRANSITIONS`, so every existing call site is unchanged.

- [ ] **Step 1: Write the failing test**

`tests/test_video_status.py`:

```python
import pytest

from agenticsocial.models import (
    ALLOWED_TRANSITIONS,
    VIDEO_TRANSITIONS,
    Status,
    TransitionError,
    assert_transition,
)


def test_render_states_exist():
    assert Status.RENDERING.value == "rendering"
    assert Status.RENDERED.value == "rendered"


def test_both_tables_are_total():
    """Every status must be a key in both tables, or lookups raise KeyError."""
    for s in Status:
        assert s in ALLOWED_TRANSITIONS, f"{s} missing from ALLOWED_TRANSITIONS"
        assert s in VIDEO_TRANSITIONS, f"{s} missing from VIDEO_TRANSITIONS"


def test_approved_may_enter_rendering():
    assert_transition(Status.APPROVED, Status.RENDERING, VIDEO_TRANSITIONS)


def test_in_review_may_not_skip_the_gate():
    with pytest.raises(TransitionError):
        assert_transition(Status.IN_REVIEW, Status.RENDERING, VIDEO_TRANSITIONS)


def test_approved_may_not_jump_straight_to_rendered():
    with pytest.raises(TransitionError):
        assert_transition(Status.APPROVED, Status.RENDERED, VIDEO_TRANSITIONS)


def test_failed_render_may_retry():
    assert_transition(Status.FAILED, Status.RENDERING, VIDEO_TRANSITIONS)


def test_rendering_may_fail():
    assert_transition(Status.RENDERING, Status.FAILED, VIDEO_TRANSITIONS)


def test_approval_may_be_revoked():
    assert_transition(Status.APPROVED, Status.IN_REVIEW, VIDEO_TRANSITIONS)


def test_published_is_terminal_for_video():
    assert VIDEO_TRANSITIONS[Status.PUBLISHED] == set()


def test_text_table_rejects_rendering():
    """A text variant must never enter a render state."""
    with pytest.raises(TransitionError):
        assert_transition(Status.APPROVED, Status.RENDERING)


def test_text_pipeline_is_unchanged():
    assert_transition(Status.APPROVED, Status.PUBLISHING)
    assert_transition(Status.IN_REVIEW, Status.APPROVED)


def test_error_message_lists_the_right_table_next_states():
    with pytest.raises(TransitionError) as excinfo:
        assert_transition(Status.APPROVED, Status.PUBLISHED, VIDEO_TRANSITIONS)
    message = str(excinfo.value)
    assert "rendering" in message
    assert "in_review" in message
    assert "publishing" not in message


def test_error_message_defaults_to_text_table():
    with pytest.raises(TransitionError) as excinfo:
        assert_transition(Status.APPROVED, Status.PUBLISHED)
    assert "publishing" in str(excinfo.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_video_status.py -v`

Expected: FAIL at collection with `ImportError: cannot import name 'VIDEO_TRANSITIONS' from 'agenticsocial.models'`

- [ ] **Step 3: Implement**

In `src/agenticsocial/models.py`, add the two states to `Status` (between `SCHEDULED` and `PUBLISHING`):

```python
class Status(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"  # reserved for the v2 calendar
    RENDERING = "rendering"
    RENDERED = "rendered"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
```

Add the two render states to `ALLOWED_TRANSITIONS` as unreachable-and-terminal, so the table stays total:

```python
ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.PUBLISHING},
    Status.SCHEDULED: set(),
    Status.RENDERING: set(),  # video-only; unreachable for text variants
    Status.RENDERED: set(),   # video-only; unreachable for text variants
    Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.PUBLISHING},
}

# Video episodes have their own lifecycle: the expensive step is rendering, and
# it sits behind the same human gate that publishing sits behind for text.
VIDEO_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.RENDERING},
    Status.SCHEDULED: set(),
    Status.RENDERING: {Status.RENDERED, Status.FAILED},
    Status.RENDERED: {Status.PUBLISHING},
    Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.RENDERING},
}

_ORDER = list(Status)
```

Replace `TransitionError` and `assert_transition` with table-aware versions:

```python
class TransitionError(Exception):
    def __init__(
        self,
        current: Status,
        target: Status,
        table: dict[Status, set[Status]] | None = None,
    ):
        table = ALLOWED_TRANSITIONS if table is None else table
        allowed = ", ".join(
            s.value for s in _ORDER if s in table[current]
        ) or "none (terminal)"
        super().__init__(
            f"cannot move {current.value} -> {target.value}; allowed next: {allowed}"
        )


def assert_transition(
    current: Status,
    target: Status,
    table: dict[Status, set[Status]] | None = None,
) -> None:
    table = ALLOWED_TRANSITIONS if table is None else table
    if target not in table[current]:
        raise TransitionError(current, target, table)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_video_status.py -v`
Expected: 13 PASS

Run: `uv run pytest`
Expected: all previously-passing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/models.py tests/test_video_status.py
git commit -m "feat: add rendering/rendered states and a video transition table"
```

---

### Task 2: Series configuration

**Files:**
- Create: `src/agenticsocial/video/__init__.py`
- Create: `src/agenticsocial/video/models.py`
- Create: `src/agenticsocial/video/series.py`
- Modify: `src/agenticsocial/workspace.py`
- Test: `tests/test_video_series.py`

**Interfaces:**
- Consumes: `Workspace`, `atomic_write` from `agenticsocial.workspace`.
- Produces: `Workspace.series_dir: Path`; `SeriesError(Exception)`; dataclass `Series(slug, name, byline, cadence, register, target_sec, tolerance_sec, formats, design, acts, dir)`; `scaffold_series(ws, slug, name=None) -> Series`; `load_series(ws, slug) -> Series`; `list_series(ws) -> list[Series]`; constants `FORMATS = ("vertical", "wide")`.

**Context:** Spec §6. `series.toml` is what a new operator edits to make the product theirs. It carries design tokens and structure, never layout code. Loading is tolerant — a minimal file with only `[series] name` must load with sensible defaults — but validation is strict on the two things later phases depend on: `formats` and `target_sec`.

- [ ] **Step 1: Write the failing test**

`tests/test_video_series.py`:

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


def test_non_positive_runtime_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[runtime]\ntarget_sec = 0\n', encoding="utf-8"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_video_series.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'agenticsocial.video'`

- [ ] **Step 3: Implement**

`src/agenticsocial/video/__init__.py`:

```python
"""Video pipeline: series, episodes, scripts, verification, rendering."""
```

`src/agenticsocial/video/models.py`:

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

`src/agenticsocial/video/series.py`:

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

In `src/agenticsocial/workspace.py`, add `series_dir` to `Workspace.__init__`:

```python
    def __init__(self, root: Path):
        self.root = Path(root)
        self.sources_dir = self.root / "sources"
        self.series_dir = self.root / "series"
```

Do **not** create `series/` in `Workspace.init` and do **not** require it in `Workspace.locate` — existing v1 workspaces have no `series/`, and `scaffold_series` creates it on demand via `mkdir(parents=True)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_video_series.py -v`
Expected: 13 PASS

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/video/ src/agenticsocial/workspace.py tests/test_video_series.py
git commit -m "feat: add series scaffolding and series.toml loading"
```

---

### Task 3: Episode scaffolding

**Files:**
- Create: `src/agenticsocial/video/episode.py`
- Test: `tests/test_video_episode.py`

**Interfaces:**
- Consumes: `Series`, `Episode`, `EpisodeError` from `.models`; `atomic_write` from `..workspace`; `Status`, `VIDEO_TRANSITIONS`, `assert_transition` from `..models`.
- Produces: `create_episode(series: Series, ep_id: str) -> Episode`; `load_episode(series: Series, ep_id: str) -> Episode`; `resolve_episode(series: Series, query: str) -> Episode`; `list_episodes(series: Series) -> list[Episode]`; `set_status(episode: Episode, target: Status) -> None`; `SUBDIRS: tuple[str, ...]`.

**Note on signatures:** these take `Series`, not `Workspace`. A `Series` already
carries its own `episodes_dir`, so a workspace argument would be dead weight —
`Series` is the correct scope for episode operations. Series functions (Task 2)
do take `ws`, because they resolve `ws.series_dir`.

**Context:** Spec §5 and §10. An episode always has a `script.yaml`, from creation onward — that is where status lives, so there is never a moment when an episode's status has nowhere to be stored. `script.yaml` is a **two-document YAML file**: document 1 is metadata, document 2 is `beats:`. This is why the spec's example has `---` fences that look like frontmatter — they are YAML document separators, and `yaml.safe_load_all` reads them natively. Phase 1 only touches document 1; Phase 3 builds the beat schema on document 2.

`resolve_episode` mirrors `Workspace.resolve_source`: exact match wins, otherwise unique substring, otherwise an actionable error.

- [ ] **Step 1: Write the failing test**

`tests/test_video_episode.py`:

```python
import pytest
import yaml

from agenticsocial.models import Status, TransitionError
from agenticsocial.video.episode import (
    create_episode,
    list_episodes,
    load_episode,
    resolve_episode,
    set_status,
)
from agenticsocial.video.models import EpisodeError
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


def test_create_makes_the_full_layout(series):
    ep = create_episode(series, "2026-08-14")
    assert ep.dir == series.episodes_dir / "2026-08-14"
    assert ep.script_path.exists()
    assert ep.sources_dir.is_dir()
    assert ep.out_dir.is_dir()
    assert ep.status is Status.DRAFT


def test_created_script_is_two_yaml_documents(series):
    ep = create_episode(series, "2026-08-14")
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert len(docs) == 2
    assert docs[0]["episode"] == "2026-08-14"
    assert docs[0]["series"] == "the-brief"
    assert docs[0]["status"] == "draft"
    assert docs[1] == {"beats": []}


def test_create_is_not_destructive(series):
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError, match="already exists"):
        create_episode(series, "2026-08-14")


def test_load_returns_status_from_disk(series):
    create_episode(series, "2026-08-14")
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_load_missing_episode_is_actionable(series):
    with pytest.raises(EpisodeError, match="agsoc video new"):
        load_episode(series, "2026-01-01")


def test_invalid_status_names_the_file_and_valid_values(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: banana\n---\nbeats: []\n",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError) as excinfo:
        load_episode(series, "2026-08-14")
    assert "banana" in str(excinfo.value)
    assert "rendering" in str(excinfo.value)


def test_resolve_exact_id_wins(series):
    create_episode(series, "2026-08-14")
    assert resolve_episode(series, "2026-08-14").id == "2026-08-14"


def test_resolve_by_unique_substring(series):
    create_episode(series, "2026-08-14")
    assert resolve_episode(series, "08-14").id == "2026-08-14"


def test_resolve_ambiguous_lists_candidates(series):
    create_episode(series, "2026-08-14")
    create_episode(series, "2026-08-15")
    with pytest.raises(EpisodeError) as excinfo:
        resolve_episode(series, "2026-08")
    assert "2026-08-14" in str(excinfo.value)
    assert "2026-08-15" in str(excinfo.value)


def test_resolve_no_match_is_actionable(series):
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError, match="agsoc video list"):
        resolve_episode(series, "1999")


def test_list_episodes_is_sorted(series):
    create_episode(series, "2026-08-15")
    create_episode(series, "2026-08-14")
    assert [e.id for e in list_episodes(series)] == ["2026-08-14", "2026-08-15"]


def test_list_episodes_when_none(series):
    assert list_episodes(series) == []


def test_set_status_persists_and_preserves_beats(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    reloaded = load_episode(series, "2026-08-14")
    assert reloaded.status is Status.IN_REVIEW
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert docs[1] == {"beats": []}


def test_set_status_enforces_the_video_table(series):
    ep = create_episode(series, "2026-08-14")
    with pytest.raises(TransitionError):
        set_status(ep, Status.RENDERING)


def test_set_status_allows_the_approved_render_path(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    set_status(ep, Status.APPROVED)
    set_status(ep, Status.RENDERING)
    assert load_episode(series, "2026-08-14").status is Status.RENDERING
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_video_episode.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'agenticsocial.video.episode'`

- [ ] **Step 3: Implement**

`src/agenticsocial/video/episode.py`:

```python
"""Episode directories and the episode status lifecycle.

`script.yaml` is a two-document YAML file: document 1 is metadata (episode id,
series, status, pace), document 2 is `beats:`. Phase 1 owns document 1 only.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ..models import Status, VIDEO_TRANSITIONS, assert_transition
from ..workspace import atomic_write
from .models import Episode, EpisodeError, Series

SUBDIRS = ("sources", "out", "probe")


def _dump(meta: dict, beats_doc: dict) -> str:
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    body = yaml.safe_dump(beats_doc, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{head}\n---\n{body}\n"


def _read(path: Path) -> tuple[dict, dict]:
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    meta = docs[0] if docs and isinstance(docs[0], dict) else {}
    beats = docs[1] if len(docs) > 1 and isinstance(docs[1], dict) else {"beats": []}
    return meta, beats


def create_episode(series: Series, ep_id: str) -> Episode:
    d = series.episodes_dir / ep_id
    if d.exists():
        raise EpisodeError(f"episode already exists: {series.slug}/{ep_id}")
    for sub in SUBDIRS:
        (d / sub).mkdir(parents=True)
    meta = {
        "episode": ep_id,
        "series": series.slug,
        "status": Status.DRAFT.value,
        "date_long": "",
        "pace": 1.0,
    }
    atomic_write(d / "script.yaml", _dump(meta, {"beats": []}))
    return Episode(id=ep_id, series_slug=series.slug, dir=d, status=Status.DRAFT, meta=meta)


def load_episode(series: Series, ep_id: str) -> Episode:
    d = series.episodes_dir / ep_id
    path = d / "script.yaml"
    if not path.exists():
        raise EpisodeError(
            f"no episode '{ep_id}' in {series.slug} — create it with `agsoc video new {ep_id}`"
        )
    meta, _ = _read(path)
    raw = meta.get("status", "draft")
    try:
        status = Status(raw)
    except ValueError:
        raise EpisodeError(
            f"{path}: invalid status '{raw}' — one of: "
            f"{', '.join(s.value for s in Status)}"
        )
    return Episode(id=ep_id, series_slug=series.slug, dir=d, status=status, meta=meta)


def list_episodes(series: Series) -> list[Episode]:
    if not series.episodes_dir.is_dir():
        return []
    ids = sorted(
        d.name for d in series.episodes_dir.iterdir() if (d / "script.yaml").exists()
    )
    return [load_episode(series, i) for i in ids]


def resolve_episode(series: Series, query: str) -> Episode:
    episodes = list_episodes(series)
    exact = [e for e in episodes if e.id == query]
    if exact:
        return exact[0]
    matches = [e for e in episodes if query.lower() in e.id.lower()]
    if len(matches) > 1:
        ids = ", ".join(e.id for e in matches)
        raise EpisodeError(f"'{query}' matches multiple episodes: {ids}")
    if not matches:
        raise EpisodeError(
            f"no episode matching '{query}' in {series.slug} — see `agsoc video list`"
        )
    return matches[0]


def set_status(episode: Episode, target: Status) -> None:
    assert_transition(episode.status, target, VIDEO_TRANSITIONS)
    meta, beats = _read(episode.script_path)
    meta["status"] = target.value
    atomic_write(episode.script_path, _dump(meta, beats))
    episode.status = target
    episode.meta = meta
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_video_episode.py -v`
Expected: 15 PASS

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/video/episode.py tests/test_video_episode.py
git commit -m "feat: add episode scaffolding and video status persistence"
```

---

### Task 4: CLI wiring

**Files:**
- Create: `src/agenticsocial/video/cli.py`
- Modify: `src/agenticsocial/cli.py`
- Test: `tests/test_video_cli.py`

**Interfaces:**
- Consumes: everything produced by Tasks 2 and 3.
- Produces: `series_app: typer.Typer`; `video_app: typer.Typer`; commands `agsoc series new`, `agsoc series list`, `agsoc video new`, `agsoc video list`.

**Context:** Spec §11. The existing `cli.py` pattern is: `_workspace()` locates or exits 1, `_fail(msg)` prints red and returns `typer.Exit(1)` (raised by the caller). Follow it exactly — including `raise _fail(...)`, which reads oddly but is the established idiom.

`--series` defaults to `default`, which is the implicit series that makes a one-off "a series of one" (spec §5). `agsoc video new` auto-scaffolds the `default` series if it is missing, so a first-time one-off needs no setup; any *named* series must be created explicitly.

- [ ] **Step 1: Write the failing test**

`tests/test_video_cli.py`:

```python
import pytest
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.workspace import Workspace

runner = CliRunner()


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


def test_series_new_creates_and_reports(ws):
    result = runner.invoke(app, ["series", "new", "the-brief", "--name", "The Brief"])
    assert result.exit_code == 0
    assert "the-brief" in result.output
    assert (ws.series_dir / "the-brief" / "series.toml").exists()


def test_series_new_twice_fails_cleanly(ws):
    runner.invoke(app, ["series", "new", "the-brief"])
    result = runner.invoke(app, ["series", "new", "the-brief"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_series_list_shows_runtime_and_formats(ws):
    runner.invoke(app, ["series", "new", "the-brief", "--name", "The Brief"])
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 0
    assert "the-brief" in result.output
    assert "120s" in result.output
    assert "vertical" in result.output


def test_series_list_when_empty(ws):
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 0
    assert "no series" in result.output


def test_video_new_autocreates_the_default_series(ws):
    result = runner.invoke(app, ["video", "new", "2026-08-14"])
    assert result.exit_code == 0
    assert (ws.series_dir / "default" / "episodes" / "2026-08-14" / "script.yaml").exists()


def test_video_new_into_a_named_series(ws):
    runner.invoke(app, ["series", "new", "the-brief"])
    result = runner.invoke(app, ["video", "new", "2026-08-14", "--series", "the-brief"])
    assert result.exit_code == 0
    assert (ws.series_dir / "the-brief" / "episodes" / "2026-08-14").is_dir()


def test_video_new_into_missing_named_series_fails(ws):
    result = runner.invoke(app, ["video", "new", "2026-08-14", "--series", "nope"])
    assert result.exit_code == 1
    assert "agsoc series new" in result.output


def test_video_new_twice_fails_cleanly(ws):
    runner.invoke(app, ["video", "new", "2026-08-14"])
    result = runner.invoke(app, ["video", "new", "2026-08-14"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_video_list_shows_status(ws):
    runner.invoke(app, ["video", "new", "2026-08-14"])
    result = runner.invoke(app, ["video", "list"])
    assert result.exit_code == 0
    assert "2026-08-14" in result.output
    assert "draft" in result.output


def test_video_list_when_empty(ws):
    runner.invoke(app, ["series", "new", "the-brief"])
    result = runner.invoke(app, ["video", "list", "--series", "the-brief"])
    assert result.exit_code == 0
    assert "no episodes" in result.output


def test_commands_without_a_workspace_fail_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "missing"))
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 1
    assert "agsoc init" in result.output


def test_existing_text_commands_still_work(ws):
    result = runner.invoke(app, ["new", "Kill staging"])
    assert result.exit_code == 0
    assert "-kill-staging" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_video_cli.py -v`
Expected: FAIL — `series` and `video` are not commands; exit code 2 with "No such command".

- [ ] **Step 3: Implement**

`src/agenticsocial/video/cli.py`:

```python
"""`agsoc series` and `agsoc video` commands."""
from __future__ import annotations

from typing import Optional

import typer

from ..workspace import Workspace, WorkspaceError
from .episode import create_episode, list_episodes
from .models import EpisodeError, SeriesError
from .series import list_series, load_series, scaffold_series

series_app = typer.Typer(help="Manage video series.", no_args_is_help=True)
video_app = typer.Typer(help="Create and manage video episodes.", no_args_is_help=True)

DEFAULT_SERIES = "default"


def _fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=False)
    return typer.Exit(code=1)


def _workspace() -> Workspace:
    try:
        return Workspace.locate()
    except WorkspaceError as e:
        raise _fail(str(e))


@series_app.command("new")
def series_new(
    slug: str,
    name: Optional[str] = typer.Option(None, "--name", help="display name (default: slug)"),
) -> None:
    """Scaffold a series: series.toml, coverage.json, episodes/."""
    ws = _workspace()
    try:
        s = scaffold_series(ws, slug, name=name)
    except SeriesError as e:
        raise _fail(str(e))
    typer.echo(f"created series {s.slug} at {s.dir}/")
    typer.echo(f"next: edit {s.dir / 'series.toml'} (palette, byline, acts, runtime)")


@series_app.command("list")
def series_list() -> None:
    """List series and their key settings."""
    ws = _workspace()
    try:
        all_series = list_series(ws)
    except SeriesError as e:
        raise _fail(str(e))
    if not all_series:
        typer.echo("no series yet — create one with `agsoc series new <slug>`")
        return
    for s in all_series:
        n = len(list_episodes(s))
        formats = "/".join(s.formats)
        typer.echo(f"{s.slug}  [{s.cadence}]  {n} episodes  {s.target_sec}s  {formats}")


def _resolve_series(ws: Workspace, slug: str, autocreate: bool):
    try:
        return load_series(ws, slug)
    except SeriesError:
        if autocreate and slug == DEFAULT_SERIES:
            return scaffold_series(ws, DEFAULT_SERIES, name="Default")
        raise


@video_app.command("new")
def video_new(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Create an episode directory with a stub script.yaml."""
    ws = _workspace()
    try:
        s = _resolve_series(ws, series, autocreate=True)
        ep = create_episode(s, episode)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))
    typer.echo(f"created episode {s.slug}/{ep.id} at {ep.dir}/")
    typer.echo(f"next: agsoc video ingest {ep.id} --research \"<query>\"")


@video_app.command("list")
def video_list(
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """List episodes in a series and their statuses."""
    ws = _workspace()
    try:
        s = load_series(ws, series)
        episodes = list_episodes(s)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))
    if not episodes:
        typer.echo(f"no episodes in {s.slug} — create one with `agsoc video new <id>`")
        return
    for ep in episodes:
        typer.echo(f"{ep.id}  {ep.status.value}")
```

In `src/agenticsocial/cli.py`, add the import beside the existing ones:

```python
from .video.cli import series_app, video_app
```

and register the sub-apps immediately after the `app = typer.Typer(...)` block:

```python
app.add_typer(series_app, name="series")
app.add_typer(video_app, name="video")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_video_cli.py -v`
Expected: 12 PASS

Run: `uv run pytest`
Expected: all pass, including every pre-existing test unmodified.

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/video/cli.py src/agenticsocial/cli.py tests/test_video_cli.py
git commit -m "feat: add agsoc series and agsoc video command groups"
```

---

## Phase 1 exit criteria

Beyond the standard gate in the roadmap §4:

- [ ] `agsoc series new the-brief --name "The Brief"` produces a `series.toml` a human can read and edit without documentation.
- [ ] `agsoc video new 2026-08-14 --series the-brief` produces the directory layout of spec §5 (minus `claims.json` and `brief.md`, which later phases write).
- [ ] The status machine refuses `draft → rendering` and `in_review → rendering`, and permits `approved → rendering`.
- [ ] No existing test file was modified.

## Notes for the QA reviewer

- `VIDEO_TRANSITIONS[Status.FAILED] == {Status.RENDERING}` is intentional even though `FAILED` is also reachable from `PUBLISHING`. Video publishing is out of MVP scope (spec §3.1); when it lands, this entry needs revisiting. Flag it if it is *not* noted in `DECISIONS.md`.
- `ALLOWED_TRANSITIONS` gains `RENDERING`/`RENDERED` as empty sets purely for table totality. A text variant reaching either state is a bug elsewhere, not something this table should make representable — worth challenging if you see a cleaner option.
- The two-document `script.yaml` choice is deliberate (spec §7's `---` fences are YAML document separators, not frontmatter). Check that `_read` degrades safely on a single-document or empty file rather than raising `IndexError`.

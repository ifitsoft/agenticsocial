# Task 4 Brief: CLI wiring, and the input boundary

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `7f09648`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

This is the task that makes Phase 1 usable: `agsoc series new/list` and
`agsoc video new/list`. It is also where operator input first enters the system,
so three defects deferred from earlier tasks become reachable here and are fixed
here rather than in the abstract.

**The error contract has a hole that this task depends on.** `_read_meta` catches
only `OSError`, so one latin-1 byte in a `script.yaml` raises a raw
`UnicodeDecodeError`. Leader-verified:

```
episode_ids        -> OK ['2026-08-14', '2026-08-15']
load_episode(bad)  -> *** UnicodeDecodeError ESCAPES the contract ***
```

The CLI you are about to write catches `EpisodeError`. Without the fix, one
corrupt episode kills the whole listing — precisely the D-018 failure mode this
phase exists to prevent.

## Ground rules

- **Three commits**, in order: Step 0 (contract + validation), Step 2 (failing
  CLI tests), Step 4 (CLI implementation). Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**. Six of my briefs have had that defect.
- Do not modify any existing test. Do not add dependencies.
- Never stage anything under `docs/`. Report observed counts, not predicted ones.

## Context you need

`src/agenticsocial/cli.py` already exists for the text pipeline. Follow its
idioms exactly, including the slightly odd `raise _fail(...)`:

```python
def _fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=False)
    return typer.Exit(code=1)
```

`series.py` provides `series_slugs`, `load_series`, `scaffold_series`,
`SLUG_RE`, `SeriesError`. `episode.py` provides `episode_ids`, `load_episode`,
`create_episode`, `EpisodeError`.

**D-018 is the rule for listing:** an *addressed* operation may raise; an
*enumerating* one must not die over one bad member. `agsoc series list` and
`agsoc video list` are the diagnostic commands — an operator runs them precisely
when something is broken. They iterate the enumerator, load each item inside a
try/except, report the broken ones, and **exit 0**: the command succeeded at
answering the question it was asked.

---

- [ ] **Step 0: Close the error contract and validate episode ids**

**0a.** In `src/agenticsocial/video/episode.py`, `_read_meta`'s `except OSError`
becomes:

```python
    try:
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
    except OSError as e:
        raise EpisodeError(f"{path}: cannot read script.yaml — {e}")
    except UnicodeDecodeError as e:
        raise EpisodeError(
            f"{path}: script.yaml is not valid UTF-8 — {e}. "
            "Re-save it as UTF-8; agsoc writes and expects UTF-8 everywhere."
        )
```

`UnicodeDecodeError` is a subclass of `ValueError`, not `OSError`, so it needs
its own clause.

**0b.** Episode ids become directory names, exactly as series slugs do. Add
beside `SUBDIRS`:

```python
EPISODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
```

and make it the first statement of `create_episode`:

```python
    if not EPISODE_ID_RE.match(ep_id):
        raise EpisodeError(
            f"invalid episode id {ep_id!r} — use lowercase letters, digits, dots "
            "and hyphens, starting with a letter or digit (ids become directory names)"
        )
```

Dots are allowed because ids are usually dates; the leading-character rule still
rejects `.`, `..` and `../escape`.

**0c.** Append these tests to `tests/test_video_episode.py`:

```python
def test_undecodable_script_raises_episode_error(series):
    """Task 4's CLI catches EpisodeError. UnicodeDecodeError is a ValueError,
    not an OSError, so it needs its own clause or it escapes the contract."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_bytes(b"---\nepisode: e\nname: caf\xe9\n---\nbeats: []\n")
    with pytest.raises(EpisodeError, match="UTF-8"):
        load_episode(series, "2026-08-14")


@pytest.mark.parametrize(
    "bad", ["../escape", "a/b", "", ".", "..", "Upper", "has space", "-leading"]
)
def test_invalid_episode_id_is_rejected(series, bad):
    with pytest.raises(EpisodeError, match="episode id"):
        create_episode(series, bad)


def test_invalid_episode_id_is_rejected_before_any_write(series):
    with pytest.raises(EpisodeError):
        create_episode(series, "../escape")
    assert not (series.episodes_dir.parent.parent / "escape").exists()


def test_date_shaped_episode_ids_are_accepted(series):
    for ok in ["2026-08-14", "2026.08.14", "ep-01"]:
        create_episode(series, ok)


def test_empty_metadata_document_keeps_its_beats(series):
    """Pins the 3d mutant that survived: searching from start.end() instead of
    start.end() - len(nl) discards the beats of an empty-metadata script."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_bytes(b"---\n---\nbeats:\n  - type: statement\n")
    set_status(load_episode(series, "2026-08-14"), Status.IN_REVIEW)
    assert b"- type: statement" in ep.script_path.read_bytes()
```

```bash
uv run pytest tests/test_video_episode.py 2>&1 | tail -20
git add src/agenticsocial/video/episode.py tests/test_video_episode.py
git commit -m "fix: complete the EpisodeError contract and validate episode ids

UnicodeDecodeError is a ValueError, not an OSError, so one latin-1 byte
in a script.yaml escaped the contract the CLI relies on. Episode ids
become directory names and were unvalidated, so ../escape wrote outside
the series."
```

- [ ] **Step 1: Write the CLI tests**

Create `tests/test_video_cli.py`:

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


# --- series --------------------------------------------------------------------


def test_series_new_creates_and_reports(ws):
    result = runner.invoke(app, ["series", "new", "the-brief", "--name", "The Brief"])
    assert result.exit_code == 0
    assert "the-brief" in result.output
    assert (ws.series_dir / "the-brief" / "series.toml").exists()


def test_series_new_rejects_a_bad_slug(ws):
    result = runner.invoke(app, ["series", "new", "../escape"])
    assert result.exit_code == 1
    assert "slug" in result.output


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


def test_series_list_survives_one_broken_series(ws):
    """D-018: `list` is the diagnostic command. One bad file must not silence
    it — a ten-series workspace cannot become unlistable over one typo."""
    runner.invoke(app, ["series", "new", "good-one"])
    d = ws.series_dir / "broken-one"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text("[series\nname =", encoding="utf-8")
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 0
    assert "good-one" in result.output
    assert "broken-one" in result.output


# --- video ---------------------------------------------------------------------


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


def test_video_new_rejects_a_bad_id(ws):
    result = runner.invoke(app, ["video", "new", "../escape"])
    assert result.exit_code == 1
    assert "episode id" in result.output


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


def test_video_list_survives_an_unparseable_episode(ws):
    runner.invoke(app, ["video", "new", "2026-08-14"])
    runner.invoke(app, ["video", "new", "2026-08-15"])
    bad = ws.series_dir / "default" / "episodes" / "2026-08-15" / "script.yaml"
    bad.write_bytes(b"\x00\x01 : : not yaml [\n")
    result = runner.invoke(app, ["video", "list"])
    assert result.exit_code == 0
    assert "2026-08-14" in result.output
    assert "2026-08-15" in result.output


def test_video_list_survives_an_undecodable_episode(ws):
    """The Step 0 fix, exercised through the CLI it exists for."""
    runner.invoke(app, ["video", "new", "2026-08-14"])
    runner.invoke(app, ["video", "new", "2026-08-15"])
    bad = ws.series_dir / "default" / "episodes" / "2026-08-15" / "script.yaml"
    bad.write_bytes(b"---\nepisode: e\nname: caf\xe9\n---\nbeats: []\n")
    result = runner.invoke(app, ["video", "list"])
    assert result.exit_code == 0
    assert "2026-08-14" in result.output


# --- the operator input boundary ------------------------------------------------


def test_a_name_that_cannot_be_encoded_is_rejected_cleanly(ws):
    """Python decodes sys.argv with surrogateescape, so a non-UTF-8 byte in an
    argument arrives as U+DC80-U+DCFF. UTF-8 cannot encode a lone surrogate, so
    this must fail as a clean CLI error rather than a UnicodeEncodeError
    traceback from inside atomic_write. See D-025."""
    result = runner.invoke(app, ["series", "new", "cafe", "--name", "caf\udce9"])
    assert result.exit_code == 1
    assert "traceback" not in result.output.lower()
    assert not (ws.series_dir / "cafe").exists()


# --- shared ---------------------------------------------------------------------


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

- [ ] **Step 2: Run, confirm failure, commit the tests**

```bash
uv run pytest tests/test_video_cli.py 2>&1 | tail -20
git add tests/test_video_cli.py
git commit -m "test: specify the series and video CLI, including D-018 listing"
```

Expected: every test fails — `series` and `video` are not commands yet.

- [ ] **Step 3: Implement**

Create `src/agenticsocial/video/cli.py`:

```python
"""`agsoc series` and `agsoc video` commands."""
from __future__ import annotations

from typing import Optional

import typer

from ..workspace import Workspace, WorkspaceError
from .episode import create_episode, episode_ids, load_episode
from .models import EpisodeError, SeriesError
from .series import load_series, scaffold_series, series_slugs

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


def _text(value: str, label: str) -> str:
    """Reject operator input that cannot be encoded as UTF-8.

    Python decodes sys.argv with surrogateescape, so a non-UTF-8 byte arrives as
    a lone surrogate. No escaping saves it — UTF-8 cannot encode a non-scalar
    value — so it must be refused at the boundary rather than becoming a
    UnicodeEncodeError traceback from inside atomic_write. See D-025.
    """
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _fail(
            f"{label} contains bytes that are not valid UTF-8 text. "
            "Check your terminal's encoding, or retype the value."
        )
    return value


@series_app.command("new")
def series_new(
    slug: str,
    name: Optional[str] = typer.Option(None, "--name", help="display name (default: slug)"),
) -> None:
    """Scaffold a series: series.toml, coverage.json, episodes/."""
    ws = _workspace()
    slug = _text(slug, "The series slug")
    if name is not None:
        name = _text(name, "The series name")
    try:
        s = scaffold_series(ws, slug, name=name)
    except SeriesError as e:
        raise _fail(str(e))
    typer.echo(f"created series {s.slug} at {s.dir}/")
    typer.echo(f"next: edit {s.dir / 'series.toml'} (palette, byline, acts, runtime)")


@series_app.command("list")
def series_list() -> None:
    """List series and their key settings. Reports broken ones rather than dying."""
    ws = _workspace()
    slugs = series_slugs(ws)
    if not slugs:
        typer.echo("no series yet — create one with `agsoc series new <slug>`")
        return
    for slug in slugs:
        try:
            s = load_series(ws, slug)
        except SeriesError as e:
            typer.secho(f"{slug}  [unreadable]  {e}", fg=typer.colors.YELLOW)
            continue
        try:
            n = len(episode_ids(s))
        except EpisodeError:
            n = 0
        typer.echo(
            f"{s.slug}  [{s.cadence}]  {n} episodes  {s.target_sec}s  "
            f"{'/'.join(s.formats)}"
        )


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
    episode = _text(episode, "The episode id")
    try:
        s = _resolve_series(ws, series, autocreate=True)
        ep = create_episode(s, episode)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))
    typer.echo(f"created episode {s.slug}/{ep.id} at {ep.dir}/")
    typer.echo(f'next: agsoc video ingest {ep.id} --research "<query>"')


@video_app.command("list")
def video_list(
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """List episodes and their statuses. Reports broken ones rather than dying."""
    ws = _workspace()
    try:
        s = load_series(ws, series)
        ids = episode_ids(s)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))
    if not ids:
        typer.echo(f"no episodes in {s.slug} — create one with `agsoc video new <id>`")
        return
    for ep_id in ids:
        try:
            typer.echo(f"{ep_id}  {load_episode(s, ep_id).status.value}")
        except EpisodeError as e:
            typer.secho(f"{ep_id}  [unreadable]  {e}", fg=typer.colors.YELLOW)
```

In `src/agenticsocial/cli.py`, add the import beside the existing ones:

```python
from .video.cli import series_app, video_app
```

and register both immediately after the `app = typer.Typer(...)` block:

```python
app.add_typer(series_app, name="series")
app.add_typer(video_app, name="video")
```

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest tests/test_video_cli.py -v 2>&1 | tail -30
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/cli.py src/agenticsocial/cli.py
git commit -m "feat: add agsoc series and agsoc video command groups

Listing follows D-018: enumerate cheaply, load each item individually,
report the broken ones and exit 0. `list` is the diagnostic command --
one malformed file must not silence it."
```

- [ ] **Step 5: Mutation check**

Apply, run, `git checkout` between. All must fail:

1. `series_list` → use `list_series(ws)` instead of per-slug loading
2. `video_list` → drop the per-episode `try/except`
3. `_text` → return `value` unchanged
4. `create_episode` → drop the `EPISODE_ID_RE` check
5. `_read_meta` → drop the `UnicodeDecodeError` clause

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-4-report.md`:

1. **What I implemented.**
2. **TDD evidence** — RED for Step 2 (piped) and GREEN (both runs). Note that
   Step 0 is a fix-plus-test commit, not a RED/GREEN pair; say what you observed.
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, all three commit SHAs.
5. **Issues or concerns**, including:
   - `series list` swallows `EpisodeError` when counting episodes and reports 0.
     Is silently showing a wrong count worse than the alternative?
   - `video new --series nope` auto-creates only for `default`. Is that
     surprising? Would you rather it always required an explicit `series new`?
   - Anything an operator can type that still produces a traceback rather than a
     clean error. Try hard — this is the last task before the phase gate.

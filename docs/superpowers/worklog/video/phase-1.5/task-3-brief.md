# Task 3 Brief: `agsoc video preview` — one command, end to end

**Phase:** 1.5 · **Branch:** `feat/video-phase-1.5-vertical-slice` · **Follows:** Task 2b
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why it is `preview`, not `render`

Spec §11 names this command `agsoc video render`, and Phase 8 will ship it. **This
task must not.**

`render` is gated: spec §10 makes `RENDERING` reachable only from `APPROVED`, and
Phase 1 built that gate. But Phase 1.5 has no `agsoc video approve` — that is
Phase 7 — so a `render` command today would either be blocked for every episode,
or would have to bypass the gate it is named after.

**Shipping a gate-bypassing command under the name the gated one will later take
is how a gate quietly stops meaning anything.** So Phase 1.5 ships
`agsoc video preview`: it renders, it never touches status, and its help text
says so. Phase 8 adds `render`, which moves `APPROVED → RENDERING → RENDERED`
and shares this implementation.

Recorded as a deliberate spec deviation.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — ten of my briefs have had that defect.
- Do not add dependencies. `subprocess` and `shutil` are stdlib.
- Never stage anything under `docs/`. Report observed counts.
- **No test may invoke Playwright or ffmpeg.** The suite runs offline in under
  two seconds and must stay that way — stub the subprocess boundary.

## What it does

```
agsoc video preview 2026-08-14 --series the-brief
```

1. Loads the series and episode, emits `out/plan-vertical.json`.
2. Runs `node render.mjs --plan <plan> --out <tmp frames dir>`.
3. Runs `ffmpeg` over those frames → `out/vertical-1080x1920.mp4`.
4. Deletes the frames directory (~2.5 GB for a full episode; spec §5).
5. Prints the output path, duration and size.

`--probe` stops after one frame per beat, leaving PNGs in `out/probe/`.

**Every failure becomes a clean CLI error.** Missing `node`, missing `ffmpeg`, a
page error, a non-zero exit, an unwritable output directory — none may reach the
operator as a traceback. Phase 1's Task 4b found 14 tracebacks; this command adds
two new subprocess boundaries and must not reintroduce them.

## Files

- Create: `src/agenticsocial/video/render.py`
- Modify: `src/agenticsocial/video/cli.py`
- Test: `tests/test_video_render.py`

## Interfaces

- `RenderError(Exception)`
- `ENGINE_DIR: Path` — the repo's `engine/`, resolved from `__file__`
- `preview(series, episode, fmt="vertical", probe=False) -> Path`

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_video_render.py`:

```python
import subprocess
from pathlib import Path

import pytest

from agenticsocial.video import render as R
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

THREE = """beats:
  - type: statement
    hold: 3.5
    text: One.
  - type: statement
    hold: 3.0
    text: Two.
"""


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


@pytest.fixture()
def episode(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: e\nseries: the-brief\nstatus: draft\n---\n" + THREE,
        encoding="utf-8",
    )
    return load_episode(series, "2026-08-14")


class FakeRun:
    """Records subprocess calls; fabricates the artifacts each step promises."""

    def __init__(self, fail_on=None, returncode=0, stderr=""):
        self.calls = []
        self.fail_on = fail_on
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        exe = Path(cmd[0]).name
        if self.fail_on and exe.startswith(self.fail_on):
            return subprocess.CompletedProcess(cmd, self.returncode, "", self.stderr)
        if exe == "node":
            out = Path(cmd[cmd.index("--out") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "00000.png").write_bytes(b"\x89PNG")
        else:  # ffmpeg
            Path(cmd[-1]).write_bytes(b"\x00\x00\x00 ftypmp42")
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture()
def fake(monkeypatch):
    f = FakeRun()
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    return f


def test_preview_writes_the_mp4_into_out(series, episode, fake):
    out = R.preview(series, episode)
    assert out == episode.out_dir / "vertical-1080x1920.mp4"
    assert out.exists()


def test_preview_emits_the_plan_first(series, episode, fake):
    R.preview(series, episode)
    assert (episode.out_dir / "plan-vertical.json").exists()


def test_node_is_invoked_with_the_plan_and_an_out_dir(series, episode, fake):
    R.preview(series, episode)
    node = [c for c in fake.calls if Path(c[0]).name == "node"][0]
    assert "--plan" in node and "--out" in node
    assert node[node.index("--plan") + 1].endswith("plan-vertical.json")


def test_ffmpeg_receives_the_plans_fps_and_the_frames(series, episode, fake):
    R.preview(series, episode)
    ff = [c for c in fake.calls if Path(c[0]).name == "ffmpeg"][0]
    assert "-framerate" in ff and ff[ff.index("-framerate") + 1] == "30"
    assert any("%05d.png" in str(a) for a in ff)


def test_the_mp4_records_the_script_hash(series, episode, fake):
    """The artifact must be traceable to the exact script it came from."""
    R.preview(series, episode)
    ff = [c for c in fake.calls if Path(c[0]).name == "ffmpeg"][0]
    joined = " ".join(str(a) for a in ff)
    assert "script_sha256=" in joined


def test_frames_are_cleaned_up(series, episode, fake):
    R.preview(series, episode)
    assert not any(episode.out_dir.glob("**/*.png"))


def test_probe_stops_before_ffmpeg(series, episode, fake):
    R.preview(series, episode, probe=True)
    assert not [c for c in fake.calls if Path(c[0]).name == "ffmpeg"]


def test_missing_node_is_a_clean_error(series, episode, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "node" else "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="node"):
        R.preview(series, episode)


def test_missing_ffmpeg_is_a_clean_error(series, episode, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "ffmpeg" else "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="ffmpeg"):
        R.preview(series, episode)


def test_missing_ffmpeg_is_detected_before_rendering_frames(series, episode, monkeypatch):
    """Rendering 3600 frames and then discovering ffmpeg is absent wastes
    minutes. Check the whole toolchain up front."""
    calls = []
    monkeypatch.setattr(R.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "ffmpeg" else "/usr/bin/" + n)
    with pytest.raises(R.RenderError):
        R.preview(series, episode)
    assert calls == []


def test_node_failure_surfaces_its_stderr(series, episode, monkeypatch):
    f = FakeRun(fail_on="node", returncode=1, stderr="page errors: ReferenceError")
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="ReferenceError"):
        R.preview(series, episode)


def test_ffmpeg_failure_surfaces_its_stderr(series, episode, monkeypatch):
    f = FakeRun(fail_on="ffmpeg", returncode=1, stderr="Invalid data found")
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="Invalid data"):
        R.preview(series, episode)


def test_no_frames_produced_is_a_clean_error(series, episode, monkeypatch):
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "", "")  # succeeds, writes nothing

    monkeypatch.setattr(R.subprocess, "run", run)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="no frames"):
        R.preview(series, episode)


def test_an_invalid_script_fails_before_any_subprocess(series, monkeypatch):
    ep = create_episode(series, "2026-08-15")
    ep.script_path.write_text(
        "---\nstatus: draft\n---\nbeats:\n  - type: jumpChart\n    text: x\n",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(R.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    from agenticsocial.video.plan import PlanError

    with pytest.raises(PlanError):
        R.preview(series, load_episode(series, "2026-08-15"))
    assert calls == []


def test_preview_does_not_change_the_episode_status(series, episode, fake):
    """Phase 1.5 has no approve command, so preview must not pretend to be the
    gated render. Status is Phase 7 and 8 business."""
    R.preview(series, episode)
    assert load_episode(series, "2026-08-14").status.value == "draft"


def test_preview_does_not_rewrite_the_script(series, episode, fake):
    before = episode.script_path.read_bytes()
    R.preview(series, episode)
    assert episode.script_path.read_bytes() == before
```

Append to `tests/test_video_cli.py`:

```python
def test_video_preview_reports_the_output_path(ws, monkeypatch):
    import agenticsocial.video.render as R

    run("series", "new", "the-brief")
    run("video", "new", "2026-08-14", "--series", "the-brief")
    ep_dir = ws.series_dir / "the-brief" / "episodes" / "2026-08-14"
    (ep_dir / "script.yaml").write_text(
        "---\nstatus: draft\n---\nbeats:\n  - type: statement\n    text: hi\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(R, "preview", lambda *a, **k: ep_dir / "out" / "x.mp4")
    result = run("video", "preview", "2026-08-14", "--series", "the-brief")
    assert result.exit_code == 0
    assert "x.mp4" in result.output


def test_video_preview_render_failure_is_a_clean_error(ws, monkeypatch):
    import agenticsocial.video.render as R

    run("series", "new", "the-brief")
    run("video", "new", "2026-08-14", "--series", "the-brief")

    def boom(*a, **k):
        raise R.RenderError("ffmpeg not found on PATH")

    monkeypatch.setattr(R, "preview", boom)
    result = run("video", "preview", "2026-08-14", "--series", "the-brief")
    assert result.exit_code == 1
    assert "ffmpeg" in result.output
```

- [ ] **Step 2: Run, confirm failure, commit the tests**

```bash
uv run pytest tests/test_video_render.py tests/test_video_cli.py 2>&1 | tail -20
git add tests/test_video_render.py tests/test_video_cli.py
git commit -m "test: specify agsoc video preview and its subprocess error surface"
```

- [ ] **Step 3: Implement**

Create `src/agenticsocial/video/render.py`:

```python
"""Drive the Node renderer and ffmpeg from Python.

Phase 1.5 ships `preview`, not `render`. Spec 10 makes RENDERING reachable only
from APPROVED, and there is no approve command until Phase 7 — so a command
named `render` today would have to bypass the gate it is named after. `preview`
never touches status. Phase 8 adds the gated `render` on top of this.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import Episode, Series
from .plan import FORMATS, write_plan

ENGINE_DIR = Path(__file__).resolve().parents[3] / "engine"
TOOLS = ("node", "ffmpeg")


class RenderError(Exception):
    pass


def _require_tools(probe: bool) -> None:
    # Check everything up front: rendering thousands of frames and only then
    # discovering ffmpeg is missing wastes minutes of the operator's time.
    needed = ("node",) if probe else TOOLS
    missing = [t for t in needed if shutil.which(t) is None]
    if missing:
        raise RenderError(
            f"{', '.join(missing)} not found on PATH — "
            "install it, or check the PATH this shell uses"
        )


def _run(cmd: list[str], what: str) -> None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ENGINE_DIR)
    except OSError as e:
        raise RenderError(f"could not start {what}: {e}")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        raise RenderError(f"{what} failed (exit {proc.returncode}):\n  " + "\n  ".join(tail))


def preview(
    series: Series, episode: Episode, fmt: str = "vertical", probe: bool = False
) -> Path:
    """Render an episode without touching its status. Returns the output path."""
    if fmt not in FORMATS:
        raise RenderError(f"unsupported format {fmt!r}")
    _require_tools(probe)

    plan_path = write_plan(series, episode, fmt)   # raises PlanError before any subprocess
    import json

    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    if probe:
        out = episode.out_dir / "probe"
        _run(["node", "render.mjs", "--plan", str(plan_path), "--probe"], "the renderer")
        return out

    frames = episode.out_dir / ".frames"
    shutil.rmtree(frames, ignore_errors=True)
    try:
        _run(
            ["node", "render.mjs", "--plan", str(plan_path), "--out", str(frames)],
            "the renderer",
        )
        if not any(frames.glob("*.png")):
            raise RenderError(
                "the renderer produced no frames — check the script has beats"
            )
        w, h = plan["format"]["w"], plan["format"]["h"]
        mp4 = episode.out_dir / f"{fmt}-{w}x{h}.mp4"
        _run(
            [
                "ffmpeg", "-y",
                "-framerate", str(plan["fps"]),
                "-i", str(frames / "%05d.png"),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-metadata", f"comment=script_sha256={plan['script_sha256']}",
                "-metadata", f"title={series.name} — {episode.id}",
                str(mp4),
            ],
            "ffmpeg",
        )
        return mp4
    finally:
        # ~2.5 GB per full episode (spec 5). Never leave these behind.
        shutil.rmtree(frames, ignore_errors=True)
```

In `src/agenticsocial/video/cli.py`, add the import and the command:

```python
from . import render as render_mod
```

```python
@video_app.command("preview")
def video_preview(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    probe: bool = typer.Option(False, "--probe", help="one frame per beat, no video"),
) -> None:
    """Render an episode to video. Does NOT change its status — the gated
    `render` command arrives with the approval workflow."""
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        out = render_mod.preview(s, ep, probe=probe)
    except (SeriesError, EpisodeError, PlanError, render_mod.RenderError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write output: {e}")
    typer.echo(f"wrote {out}")
```

Import `PlanError` from `.plan` at the top of `cli.py`.

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/render.py src/agenticsocial/video/cli.py
git commit -m "feat: add agsoc video preview

Renders an episode end to end -- plan.json, Node frames, ffmpeg -- and
records the script's sha256 in the MP4's metadata so the artifact is
traceable to the exact script it came from. Named preview, not render:
spec 10 gates RENDERING behind APPROVED and there is no approve command
until Phase 7, so a `render` today would bypass the gate it is named
after. Frames are always cleaned up; the toolchain is checked before any
frame is rendered."
```

- [ ] **Step 5: Prove it end to end for real**

Not a test — a real run, with real Playwright and real ffmpeg:

```bash
export AGSOC_WORKSPACE=/tmp/t3/workspace && rm -rf /tmp/t3
uv run agsoc init /tmp/t3/workspace && uv run agsoc series new the-brief --name "The Brief"
uv run agsoc video new 2026-08-14 --series the-brief
cat > /tmp/t3/workspace/series/the-brief/episodes/2026-08-14/script.yaml <<'YAML'
---
episode: '2026-08-14'
series: the-brief
status: draft
pace: 1.0
---
beats:
  - type: statement
    act: "01"
    hold: 3.0
    kicker: One command
    text: This was rendered by agsoc video preview.
    src: agsoc
  - type: statement
    hold: 3.0
    text: Plan, frames, encode, cleanup.
YAML
time uv run agsoc video preview 2026-08-14 --series the-brief
ffprobe -v error -show_entries format=duration,tags=comment -of default=nw=1 \
  /tmp/t3/workspace/series/the-brief/episodes/2026-08-14/out/vertical-1080x1920.mp4
ls -la /tmp/t3/workspace/series/the-brief/episodes/2026-08-14/out/
```

Paste all of it. The `comment` tag must carry the script's real sha256, and no
`.frames` directory may survive.

---

## Your report

`docs/superpowers/worklog/video/phase-1.5/task-3-report.md`:

1. **What I implemented.**
2. **TDD evidence** — RED (piped) and GREEN.
3. **Step 5's real end-to-end run**, pasted in full.
4. **Files changed**, both commit SHAs.
5. **Vacuity audit** — for each test you wrote, what would it do if the code did
   nothing? Three implementers before you caught vacuous tests of mine this way.
6. **Issues or concerns**, including:
   - `ENGINE_DIR` is derived with `parents[3]` from `__file__`. That breaks the
     moment `agsoc` is pip-installed rather than run from a checkout. What should
     it be instead?
   - Anything an operator can type at `agsoc video preview` that still produces a
     traceback.
   - Is `preview` the right name, or does splitting it from `render` create two
     commands that will drift?

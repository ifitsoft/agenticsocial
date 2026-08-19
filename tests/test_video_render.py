"""plan -> node -> ffmpeg: the toolchain half of a render.

Every test here used to drive `preview`, because `preview` was the cheap handle
on `_encode` — no approval to arrange, no ledger to keep fresh. D-130 is what
that convenience cost: the handle was also a command, and it wrote
`out/<fmt>-<w>x<h>.mp4` with none of the three checks `render` asks. It is
retired (`tests/test_video_gated_artifact.py`).

So these tests drive the gated path instead, and that is not merely a
substitution. **A test that reached the encoder by a route the product does not
have would be testing a harness** — D-035's pattern, and here it would hide
exactly the defect that produced this file: the ordering claims below
("ffmpeg is checked before any frame is rendered") are claims about
`render_episode`, and asserting them anywhere else asserts them about nothing.

What stays ungated is `probe`, which is where the pre-subprocess claims that do
not need an approval are made: it writes frames, never a video.

R6: no test renders a full episode. Every subprocess is faked and the fixture
script is six seconds long.
"""
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import corpus
from agenticsocial.video import render as R
from agenticsocial.video.episode import create_episode, load_episode, read_script
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()

EP = "2026-08-14"
BY = "Ali Abdukarim"

SOURCE = (
    "DeepSeek's 1.6T MoE flagship quietly moved from preview to general "
    "availability this week, then announced new pricing starting August 16 at "
    "about $1.32 / $3.96 per 1M tokens (in/out)."
)


def run(*args):
    """D-035: a crash inside the runner reads as a clean refusal without this."""
    result = runner.invoke(app, list(args), catch_exceptions=False)
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"a crash reached the runner: {result.exception!r}"
    )
    return result


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


def clean_beat(**over):
    beat = {
        "type": "statement",
        "hold": 3.0,
        "text": "DeepSeek's flagship is a 1.6T MoE model.",
        "src": "local-ai-zone",
        "quote": "DeepSeek's 1.6T MoE flagship quietly moved from preview",
    }
    beat.update(over)
    return beat


def write_script(ep, beats, status="in_review"):
    # The id is QUOTED: `episode: 2026-08-14` unquoted is a YAML date.
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f"---\nepisode: '{ep.id}'\nseries: the-brief\nstatus: {status}\n---\n{body}",
        encoding="utf-8",
    )


def draft(series, beats=None, ep_id=EP):
    """An episode with a corpus, not yet approved. What `probe` works on."""
    ep = create_episode(series, ep_id)
    corpus.write_document(
        ep, SOURCE, url="https://local-ai-zone.example/x", key="local-ai-zone",
        fetched_at="2026-08-14",
    )
    write_script(ep, beats or [clean_beat(), clean_beat()])
    return load_episode(series, ep_id)


@pytest.fixture()
def approved(series):
    """Approved, undrifted, checked against a fresh corpus — the only state from
    which an MP4 can be produced at all, which is the point of D-130's fix."""
    ep = draft(series)
    assert run("video", "check", EP, "--series", "the-brief").exit_code == 0
    assert run(
        "video", "approve", EP, "--series", "the-brief", "--by", BY
    ).exit_code == 0, "the fixture must actually be approvable"
    return load_episode(series, EP)


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


def render(ws, fmt=None):
    return R.render_episode(ws, "the-brief", EP, fmt=fmt)


def only(fake, exe):
    return [c for c in fake.calls if Path(c[0]).name == exe][0]


# --- what the encoder produces ---------------------------------------------------------


def test_the_render_writes_the_mp4_into_out(ws, approved, fake):
    run_ = render(ws)
    assert run_.rendered[0].path == approved.out_dir / "vertical-1080x1920.mp4"
    assert run_.rendered[0].path.exists()


def test_the_plan_is_emitted_first(ws, approved, fake):
    render(ws)
    assert (approved.out_dir / "plan-vertical.json").exists()


def test_node_is_invoked_with_the_plan_and_an_out_dir(ws, approved, fake):
    render(ws)
    node = only(fake, "node")
    assert "--plan" in node and "--out" in node
    assert node[node.index("--plan") + 1].endswith("plan-vertical.json")


def test_ffmpeg_receives_the_plans_fps_and_the_frames(ws, approved, fake):
    render(ws)
    ff = only(fake, "ffmpeg")
    assert "-framerate" in ff and ff[ff.index("-framerate") + 1] == "30"
    assert any("%05d.png" in str(a) for a in ff)


def test_the_mp4_records_the_script_hash(ws, approved, fake):
    """The artifact must be traceable to the exact script it came from — and
    since D-130 that is also how a file in `out/` can be told apart from one no
    gate produced."""
    render(ws)
    joined = " ".join(str(a) for a in only(fake, "ffmpeg"))
    assert "script_file_sha256=" in joined


def test_frames_are_cleaned_up(ws, approved, fake):
    render(ws)
    assert not any(approved.out_dir.glob("**/*.png"))


# --- the toolchain is checked before it is used ----------------------------------------


def test_missing_node_is_a_clean_error(ws, approved, fake, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "node" else "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="node"):
        render(ws)


def test_missing_ffmpeg_is_a_clean_error(ws, approved, fake, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "ffmpeg" else "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="ffmpeg"):
        render(ws)


def test_missing_ffmpeg_is_detected_before_rendering_frames(ws, approved, monkeypatch):
    """Rendering 3600 frames and then discovering ffmpeg is absent wastes
    minutes. Check the whole toolchain up front."""
    calls = []
    monkeypatch.setattr(R.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "ffmpeg" else "/usr/bin/" + n)
    with pytest.raises(R.RenderError):
        render(ws)
    assert calls == []


def test_a_probe_needs_node_and_says_so(series, monkeypatch):
    """`probe` is ungated and encodes nothing, so it demands node and not
    ffmpeg — and the missing-tool refusal still has to be legible."""
    ep = draft(series)
    monkeypatch.setattr(R.shutil, "which", lambda n: None)
    with pytest.raises(R.RenderError, match="node"):
        R.probe(series, ep)


# --- failures surface what the tool said -----------------------------------------------


def test_node_failure_surfaces_its_stderr(ws, approved, monkeypatch):
    f = FakeRun(fail_on="node", returncode=1, stderr="page errors: ReferenceError")
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="ReferenceError"):
        render(ws)


def test_ffmpeg_failure_surfaces_its_stderr(ws, approved, monkeypatch):
    f = FakeRun(fail_on="ffmpeg", returncode=1, stderr="Invalid data found")
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="Invalid data"):
        render(ws)


def test_no_frames_produced_is_a_clean_error(ws, approved, monkeypatch):
    def no_op(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "", "")  # succeeds, writes nothing

    monkeypatch.setattr(R.subprocess, "run", no_op)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="no frames"):
        render(ws)


def test_an_invalid_script_fails_before_any_subprocess(series, monkeypatch):
    """Asserted on `probe`, which builds the same plan and is the only remaining
    command that reaches the renderer without spending a gate."""
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
        R.probe(series, load_episode(series, "2026-08-15"))
    assert calls == []


# --- what the render does to the episode -----------------------------------------------


def test_a_probe_does_not_change_the_episode_status(series, fake):
    """The half of `preview`'s contract that survives it: looking is free, and
    free means it moves nothing. Producing the artifact is what is gated."""
    ep = draft(series)
    R.probe(series, ep)
    assert load_episode(series, EP).status.value == "in_review"


def test_a_probe_does_not_rewrite_the_script(series, fake):
    ep = draft(series)
    before = ep.script_path.read_bytes()
    R.probe(series, ep)
    assert ep.script_path.read_bytes() == before


def test_the_render_moves_the_status_and_nothing_else_in_the_beats(ws, approved, fake):
    """The gated counterpart. The status moves — that is what a gate spends —
    and the beats the approver signed are byte-identical afterwards."""
    _, _, before = read_script(approved.script_path)
    render(ws)
    meta, _, after = read_script(approved.script_path)
    assert meta["status"] == "rendered"
    assert after == before

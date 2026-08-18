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
    assert "script_file_sha256=" in joined


def test_frames_are_cleaned_up(series, episode, fake):
    R.preview(series, episode)
    assert not any(episode.out_dir.glob("**/*.png"))


def test_probe_stops_before_ffmpeg(series, episode, fake):
    R.preview(series, episode, probe=True)
    assert not [c for c in fake.calls if Path(c[0]).name == "ffmpeg"]


def test_missing_node_is_a_clean_error(series, episode, fake, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "node" else "/usr/bin/" + n)
    with pytest.raises(R.RenderError, match="node"):
        R.preview(series, episode)


def test_missing_ffmpeg_is_a_clean_error(series, episode, fake, monkeypatch):
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

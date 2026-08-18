"""`agsoc video probe` — look at the frames without waiting for a render.

Spec §6: `agsoc video probe <ep> [--at T] [--format F]`, one frame per beat or
one frame at T.

**Why this is a command and not a flag.** D-116 measured what an approval covers
and it stops at the pixels: `engine.js`, `planbuild.js`, `scene.html`'s CSS, the
resolved font, Chromium, ffmpeg are all outside it, and a font substitution
changes every frame with all three of `render`'s checks green. `render`'s own
success screen says so, and then says *nobody has looked at this video*. That
sentence is only honest if looking is cheap — and it was reachable only as
`preview --probe`, a flag on the fourteen-minute command it exists to avoid. One
dropped flag and the operator gets the render they were trying not to wait for.

So: `probe` is its own command, `preview` no longer takes `--probe`, and there is
one way to get frames on disk.

**And it is ungated, deliberately.** Probing is inspection, not production: it
moves no status, and it works on a `draft` as readily as on a `rendered`
episode. Gating the way you look at something on having already approved it is
the wrong way round.

No test here renders a full episode (R6): every subprocess is faked, and the
shape of the arguments handed to the renderer is what pins that a probe shoots a
handful of frames rather than all of them.
"""
import json
import subprocess
from pathlib import Path

import pytest
import typer
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import render as R
from agenticsocial.video.episode import create_episode, load_episode, read_script
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()
EP = "2026-08-17"


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


class FakeRun:
    """Fakes node; fabricates the PNGs it promises. See R6 — a real probe is a
    Chromium launch and a screenshot per beat, and what is under test is which
    frames get asked for and where they land."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        exe = Path(cmd[0]).name
        if self.fail_on and exe.startswith(self.fail_on):
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        if exe == "node":
            out = Path(cmd[cmd.index("--out") + 1])
            out.mkdir(parents=True, exist_ok=True)
            if "--at" in cmd:
                (out / f"at-{cmd[cmd.index('--at') + 1]}.png").write_bytes(b"\x89PNG")
            else:
                for i in range(2):
                    (out / f"s{i:02d}.png").write_bytes(b"\x89PNG")
        else:
            Path(cmd[-1]).write_bytes(b"\x00" * 4096)
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture()
def fake(monkeypatch):
    f = FakeRun()
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    return f


def beat(**over):
    b = {"type": "statement", "hold": 3.0, "text": "The flagship reached GA."}
    b.update(over)
    return b


def episode(series, status="draft", ep_id=EP):
    ep = create_episode(series, ep_id)
    body = yaml.safe_dump({"beats": [beat(), beat(text="Pricing moved.")]}, sort_keys=False)
    ep.script_path.write_text(
        f"---\nepisode: '{ep_id}'\nseries: the-brief\nstatus: {status}\npace: 1.0\n---\n{body}",
        encoding="utf-8",
    )
    return load_episode(series, ep_id)


def probe(*extra, ep_id=EP):
    return run("video", "probe", ep_id, "--series", "the-brief", *extra)


def status_on_disk(series, ep_id=EP):
    meta, _, _ = read_script(series.episodes_dir / ep_id / "script.yaml")
    return meta.get("status")


def node_call(fake):
    calls = [c for c in fake.calls if Path(c[0]).name == "node"]
    assert len(calls) == 1, fake.calls
    return calls[0]


# --- the command exists, and it is the one `render` sends you to ----------------------


def test_probe_is_a_command(fake, series):
    """Spec §6 lists `agsoc video probe`. It was never built; the behaviour
    existed as a flag on `preview`."""
    ep = episode(series)
    result = probe()
    assert result.exit_code == 0, result.output


def test_the_render_screen_points_at_a_command_that_exists():
    """The success screen tells the operator to go look at the frames. A screen
    that names a command the CLI does not have is worse than saying nothing —
    it reads as a working suggestion right up until it is typed.

    Read off the CLI's own registry rather than a literal, so registering the
    command and quoting it stay one fact.
    """
    from agenticsocial.video import cli as vcli

    source = Path(vcli.__file__).read_text(encoding="utf-8")
    named = {
        c.name for c in typer.main.get_command(vcli.video_app).commands.values()
    }
    assert "probe" in named
    assert "`agsoc video probe " in source


def test_preview_no_longer_takes_probe(fake, series):
    """One door. `preview --probe` and `probe` doing the same thing is two
    commands to keep identical and two places to look."""
    episode(series)
    result = run("video", "preview", EP, "--series", "the-brief", "--probe")
    assert result.exit_code != 0
    assert "--probe" in result.output or "No such option" in result.output


# --- what a probe costs ----------------------------------------------------------------


def test_a_probe_does_not_encode_a_video(fake, series):
    """The point of the command. ffmpeg is not run, and it is not even required
    to be installed — a probe is frames."""
    episode(series)
    assert probe().exit_code == 0
    assert [Path(c[0]).name for c in fake.calls] == ["node"]


def test_a_probe_asks_for_one_frame_per_beat_not_all_of_them(fake, series):
    """R6's operator-facing half: ~230 ms a frame means the all-frames
    invocation is the fourteen-minute one. The renderer is asked for the probe
    modes, never the full sweep."""
    episode(series)
    probe()
    assert "--probe" in node_call(fake)


def test_a_probe_at_a_time_asks_for_exactly_one_frame(fake, series):
    """`--at T`, which the flag on `preview` never offered at all."""
    episode(series)
    result = probe("--at", "1.5")
    assert result.exit_code == 0, result.output
    cmd = node_call(fake)
    assert cmd[cmd.index("--at") + 1] == "1.5"
    assert "--probe" not in cmd


def test_a_refused_probe_does_not_destroy_the_last_one(fake, series):
    """Found by running it. The clearing ran before the range check, so
    `--at 90` on a six-second episode refused correctly — and took the frames
    the operator was looking at with it. A refusal must cost nothing; that is
    what makes it safe to type a number and see."""
    ep = episode(series)
    probe()
    before = sorted(p.name for p in (ep.dir / "probe").glob("*.png"))
    assert before
    assert probe("--at", "90").exit_code == 1
    assert sorted(p.name for p in (ep.dir / "probe").glob("*.png")) == before


def test_a_time_outside_the_episode_is_refused(fake, series):
    """A frame at t=90 of a 6-second episode is a black rectangle, and a black
    rectangle reads as a broken renderer. Python knows the runtime — it resolved
    it — so the refusal is free and names the length."""
    episode(series)
    result = probe("--at", "90")
    assert result.exit_code == 1
    assert "6.0" in result.output
    assert not fake.calls


# --- where the frames land -------------------------------------------------------------


def test_the_frames_land_in_the_episodes_probe_directory(fake, series):
    """Spec §5 puts `probe/` beside `out/` in the episode, and `create_episode`
    has made that directory since Phase 1 — it was simply never written to.
    Frames belong to the episode that produced them: two episodes probed in a
    row must not overwrite each other."""
    ep = episode(series)
    result = probe()
    frames = sorted((ep.dir / "probe").glob("*.png"))
    assert frames, list((ep.dir / "probe").iterdir())
    assert str(ep.dir / "probe") in result.output
    assert not list((ep.out_dir).rglob("*.png"))


def test_nothing_is_written_into_the_engine(fake, series):
    """M10's probe half. `engine/` is a gitignored working area; a frame there
    is a frame nobody finds and nobody cleans up."""
    engine = Path(R.ENGINE_DIR)
    before = sorted(p.name for p in engine.iterdir())
    episode(series)
    probe()
    assert sorted(p.name for p in engine.iterdir()) == before


def test_a_second_probe_replaces_the_first(fake, series):
    """Stale frames beside fresh ones are the same class of problem as a stale
    ledger: an operator cannot tell which describes the current script.

    The renderer clears its own `--probe` directory, but only that one and only
    in that mode — so the clearing this asserts is Python's, which is also the
    only version this test could see: the fake renderer writes files, it does
    not reimplement `rm -rf`.
    """
    ep = episode(series)
    probe()
    (ep.dir / "probe" / "s99.png").write_bytes(b"\x89PNG")
    probe()
    assert not (ep.dir / "probe" / "s99.png").exists()


# --- probing changes nothing -----------------------------------------------------------


def test_a_probe_does_not_change_the_status(fake, series):
    episode(series)
    probe()
    assert status_on_disk(series) == "draft"


def test_a_probe_does_not_rewrite_the_script(fake, series):
    ep = episode(series)
    before = ep.script_path.read_bytes()
    probe()
    assert ep.script_path.read_bytes() == before


def test_an_unapproved_episode_can_be_probed(fake, series):
    """Deliberate, and the opposite of `render`. Inspection is how you decide
    whether to approve; requiring approval first inverts the workflow."""
    episode(series, status="in_review")
    assert probe().exit_code == 0


def test_a_rendered_episode_can_still_be_probed(fake, series):
    """`rendered` is terminal (D-006) — for status. Looking at it is not a
    transition."""
    episode(series, status="rendered")
    assert probe().exit_code == 0
    assert status_on_disk(series) == "rendered"


# --- refusals --------------------------------------------------------------------------


def test_an_unsupported_format_is_refused_before_anything_runs(fake, series):
    episode(series)
    result = probe("--format", "square")
    assert result.exit_code == 1
    assert "square" in result.output
    assert not fake.calls


def test_a_missing_episode_is_a_clean_error(fake, series):
    result = probe(ep_id="2026-01-01")
    assert result.exit_code == 1
    assert "2026-01-01" in result.output


def test_a_missing_node_is_a_clean_error(fake, series, monkeypatch):
    """ffmpeg is NOT required: a probe never encodes. Naming ffmpeg here would
    send an operator to install something this command does not use."""
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "node" else "/x")
    episode(series)
    result = probe()
    assert result.exit_code == 1
    assert "node" in result.output


def test_a_renderer_crash_is_a_clean_error(series, monkeypatch):
    f = FakeRun(fail_on="node")
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    episode(series)
    result = probe()
    assert result.exit_code == 1
    assert "renderer" in result.output


# --- the plan the probe renders --------------------------------------------------------


def test_the_probe_renders_the_same_plan_render_would(fake, series):
    """D-007 and the whole point of probing: if the probe drew its frames from
    anywhere but the plan `render` uses, it would be inspecting something else
    and reporting on the render."""
    ep = episode(series)
    probe()
    cmd = node_call(fake)
    plan_path = Path(cmd[cmd.index("--plan") + 1])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["format"]["name"] == "vertical"
    assert len(plan["beats"]) == 2
    assert plan["total_frames"] == round(plan["total_sec"] * plan["fps"])

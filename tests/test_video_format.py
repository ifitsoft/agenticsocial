"""Wide format — a declared context, not a stylesheet fork. Spec §9.

The mutant table is in the Phase 10 Task 1 brief; every test here names the
mutant it kills. The Node half of this contract — one builder per beat, the same
words in both formats, and overflow refused loudly — lives in
`engine/format.test.mjs`, because it can only be measured in a laid-out page.

What is testable HERE is the half Python owns: the format is DATA, it changes
layout and never timing, it reaches `render.mjs` through the plan, and the
operator is told that nobody approved it.
"""
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import plan as plan_mod
from agenticsocial.video import render as R
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.plan import FORMATS, PlanError, build_plan, write_plan
from agenticsocial.video.series import SeriesError, load_series, scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()

THREE = """beats:
  - type: statement
    hold: 3.5
    text: Google shipped its main agentic model.
  - type: body
    hold: 3.0
    text: It costs half of what the last one did.
  - type: signoff
    hold: 4.0
    text: Same time tomorrow.
"""


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


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
    """Records subprocess calls and fabricates what each step promises.

    No test here renders a full episode: ~230 ms a frame (D-119), and what is
    under test is the plan and the screens, neither of which a real Chromium
    makes more true.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if Path(cmd[0]).name == "node":
            out = Path(cmd[cmd.index("--out") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "00000.png").write_bytes(b"\x89PNG")
        else:
            Path(cmd[-1]).write_bytes(b"\x00" * 4096)
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture()
def fake(monkeypatch):
    f = FakeRun()
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    return f


# --- 1 · the format is a declared context --------------------------------------------


def test_both_formats_declare_the_whole_context():
    """R1. Spec §9's five properties, per format — the data every per-format
    difference is driven from. A format that carried only `w`/`h` would push the
    rest into a stylesheet, which is the fork this phase exists to avoid."""
    for name, fmt in FORMATS.items():
        assert set(fmt) == {"w", "h", "safe_top", "safe_bottom", "measure", "scale"}, name
        assert fmt["safe_top"] < fmt["safe_bottom"] <= fmt["h"], name
        assert 0 < fmt["scale"] <= 1, name
    assert FORMATS["wide"]["w"] == 1920 and FORMATS["wide"]["h"] == 1080
    assert FORMATS["vertical"]["w"] == 1080 and FORMATS["vertical"]["h"] == 1920
    assert FORMATS["wide"]["measure"] == "wide"
    assert FORMATS["vertical"]["measure"] == "narrow"


def test_the_plan_carries_the_format_it_was_built_for(series, episode):
    """M7. `--format wide` that renders 1080×1920 is the mutant, and the plan is
    the only place the viewport comes from — render.mjs does no arithmetic."""
    plan = build_plan(series, episode, "wide")
    assert plan["format"] == {"name": "wide", **FORMATS["wide"]}
    assert plan["format"]["w"] == 1920 and plan["format"]["h"] == 1080


def test_format_changes_layout_never_timing(series, episode):
    """M2, and spec §9's invariant. A probe at t=42.9 is the same instant in both
    formats: pacing is verified once and holds for every format.

    Asserted beat by beat rather than on the total — a total can agree while two
    beats swap length between them."""
    v = build_plan(series, episode, "vertical")
    w = build_plan(series, episode, "wide")
    assert (v["fps"], v["pace"], v["total_sec"], v["total_frames"]) == (
        w["fps"], w["pace"], w["total_sec"], w["total_frames"]
    )
    for a, b in zip(v["beats"], w["beats"], strict=True):
        assert a == b, "a beat differs between formats — the format is layout, not content"


def test_each_format_writes_its_own_plan(series, episode):
    """M8's negative half at the file level: rendering wide must not overwrite
    the vertical plan an operator may be mid-render on."""
    pv = write_plan(series, episode, "vertical")
    pw = write_plan(series, episode, "wide")
    assert pv.name == "plan-vertical.json" and pw.name == "plan-wide.json"
    assert json.loads(pv.read_text())["format"]["name"] == "vertical"
    assert json.loads(pw.read_text())["format"]["name"] == "wide"


def test_an_unknown_format_is_still_refused(series, episode):
    with pytest.raises(PlanError) as e:
        build_plan(series, episode, "square")
    assert "square" in str(e.value)
    assert "wide" in str(e.value) and "vertical" in str(e.value)


# --- 2 · end to end ------------------------------------------------------------------


def test_preview_wide_encodes_at_1920x1080(series, episode, fake):
    """M7 end to end: the mp4 is named for the format AND its geometry, so a
    wide render that quietly produced 1080×1920 is visible in `out/`."""
    out = R.preview(series, episode, "wide")
    assert out.name == "wide-1920x1080.mp4"
    node = [c for c in fake.calls if Path(c[0]).name == "node"][0]
    plan = json.loads(Path(node[node.index("--plan") + 1]).read_text())
    assert plan["format"]["w"] == 1920


def test_probe_wide_reaches_the_renderer_with_the_wide_plan(series, episode, fake):
    R.probe(series, episode, "wide")
    node = [c for c in fake.calls if Path(c[0]).name == "node"][0]
    assert node[node.index("--plan") + 1].endswith("plan-wide.json")


def test_the_probe_command_accepts_wide(series, episode, fake):
    result = runner.invoke(
        app, ["video", "probe", "2026-08-14", "--series", "the-brief", "--format", "wide"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "wide" in result.output


def test_the_probe_screen_says_the_format_was_not_approved(series, episode, fake):
    """M9, R5. The format is chosen at render time and is outside the approval
    (D-116) — said where the operator reads it, not only in a docstring."""
    result = runner.invoke(
        app, ["video", "probe", "2026-08-14", "--series", "the-brief", "--format", "wide"],
        catch_exceptions=False,
    )
    flat = " ".join(result.output.split()).lower()
    assert "wide" in flat
    assert "chosen at render time" in flat and "not part of the approval" in flat


def test_the_render_screen_says_the_format_was_not_approved(series, episode, monkeypatch):
    """M9. A render screen that lists the format among the things that were
    signed is the mutant: `approve` binds what the operator authored, and the
    format is picked minutes later on a command line."""
    record = {
        "at": "2026-08-18T10:00:00+03:00",
        "outcome": "rendered",
        "format": "wide",
        "file": "out/wide-1920x1080.mp4",
        "bytes": 4096,
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "frames": 315,
        "runtime_sec": 10.5,
        "script_file_sha256": "abc",
        "approval": {"by": "Ali Abdukarim", "at": "2026-08-18T09:00:00+03:00"},
    }
    monkeypatch.setattr(
        R, "render_episode",
        lambda *a, **k: R.RenderResult(record=record, path=Path("/tmp/wide-1920x1080.mp4")),
    )
    result = runner.invoke(
        app, ["video", "render", "2026-08-14", "--series", "the-brief", "--format", "wide"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split()).lower()
    assert "1920x1080" in flat
    assert "wide" in flat
    assert "chosen at render time" in flat and "not part of the approval" in flat


# --- 3 · type_family and type_scale (D-116, D-077) -----------------------------------


def _declares_type_family(series):
    """An operator's series.toml, scaffolded before the key was retired. Every
    one this tool has ever written has the line in it, including the three real
    episodes' series on the author's machine."""
    toml = series.dir / "series.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(
            'type_scale  = "default"',
            'type_family = "SF Pro Display, Helvetica Neue, system-ui"\n'
            'type_scale  = "default"',
        ),
        encoding="utf-8",
    )


def test_type_family_reaches_neither_the_plan_nor_the_approval(ws, series, episode):
    """M10. It was copied into `plan.json` and the engine ignored it: a knob an
    operator would believe controls the typography that controls nothing — and,
    because the approval binds what the plan copies, a false positive in drift.

    Retired (D-077): a font stack naming a family the render host lacks falls
    back silently, and unlike a colour it cannot be validated, because whether
    `SF Pro Display` resolves is a property of the machine, not of the string."""
    _declares_type_family(series)
    series = load_series(ws, "the-brief")
    assert "type_family" in series.design, "the operator's file still has the line"
    plan = build_plan(series, episode)
    assert "type_family" not in plan["design"]
    assert "type_family" not in json.dumps(plan_mod.series_inputs(series))


def test_type_scale_reaches_the_plan(series, episode):
    """The other half of D-077: three enumerated values, validatable like
    `register`, and now actually drawn — see engine/format.test.mjs, which
    measures the type it produces."""
    plan = build_plan(series, episode)
    assert plan["design"]["type_scale"] == "default"


def test_an_unknown_type_scale_is_refused(ws, series):
    toml = series.dir / "series.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace('type_scale  = "default"', 'type_scale = "huge"'),
        encoding="utf-8",
    )
    with pytest.raises(SeriesError) as e:
        load_series(ws, "the-brief")
    assert "type_scale" in str(e.value) and "huge" in str(e.value)


def test_a_series_that_still_declares_type_family_keeps_loading(ws, series, recwarn):
    """The negative half. It is a retired key in a file the operator owns, and
    refusing to load their series over a line that now does nothing would cost
    them every command in the tool. Warned, ignored, and left where it is."""
    _declares_type_family(series)
    s = load_series(ws, "the-brief")
    assert s.design["type_family"]
    assert any("type_family" in str(w.message) for w in recwarn)


def test_the_engine_reads_type_scale_and_knows_nothing_of_type_family():
    """D-116 was found by grepping `engine/` for both strings. Same grep, as a
    test: whichever way the question is resolved, the answer has to be visible
    in the renderer."""
    engine = Path(__file__).resolve().parents[1] / "engine"
    # The TRACKED sources, named. `engine/*.js` also matches `.plan.js`, which
    # is a build artifact written by whatever was rendered last — a scan that
    # reads it is a test whose answer depends on the previous command.
    text = "\n".join(
        (engine / name).read_text(encoding="utf-8")
        for name in ("engine.js", "planbuild.js", "render.mjs", "scene.html")
    )
    assert "type_scale" in text
    assert "type_family" not in text

"""Every writer of the gated artifact goes through the gate. D-130, D-059.

`agsoc video render` is three checks in front of one file:
`<episode>/out/<fmt>-<w>x<h>.mp4`. D-130 found a sibling command — `preview` —
calling the same `_encode`, writing the same path, asking none of the three. A
draft could be rendered, and the resulting file is byte-identical to an approved
one and sits exactly where an operator or a publishing step looks for it.

That is D-059's shape: **a gate protects a decision, not a file, unless every
writer of that file goes through it.** Phase 7's R5 enumerated the writers of the
status key from the AST and found a hole nobody had asserted about. This file is
the same enumeration for the *artifact*, run on every commit rather than once in
a report:

  * the mp4 path is built in exactly one function,
  * it is handed to a writing process in exactly one function,
  * that function has exactly one caller,
  * that caller is the gate,
  * and exactly one CLI command can reach it.

A fifth writer cannot be added without a test going red here.
"""
import ast
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import cli as vcli
from agenticsocial.video import render as R
from agenticsocial.video.episode import create_episode, load_episode, read_script
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()

EP = "2026-08-14"
SRC = Path(R.__file__).resolve().parent.parent
GATED = "vertical-1080x1920.mp4"

TWO = """beats:
  - type: statement
    hold: 3.0
    text: One.
  - type: statement
    hold: 3.0
    text: Two.
"""


def run(*args):
    """Invoke the CLI, and refuse to let a crash read as a clean refusal (D-035)."""
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


@pytest.fixture()
def draft(series):
    ep = create_episode(series, EP)
    ep.script_path.write_text(
        f"---\nepisode: '{EP}'\nseries: the-brief\nstatus: draft\n---\n" + TWO,
        encoding="utf-8",
    )
    return load_episode(series, EP)


class FakeRun:
    """Fabricates what each step promises, so a bypass leaves a real file.

    R6: no test renders a full episode. The subprocess is faked — but the fake
    WRITES, because the thing being detected here is a file appearing on disk.
    A fake that produced nothing would pass this file's tests with the bypass
    wide open, which is D-035's harness-hides-the-bug pattern exactly.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if Path(cmd[0]).name == "node":
            out = Path(cmd[cmd.index("--out") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "00000.png").write_bytes(b"\x89PNG")
        else:  # ffmpeg
            Path(cmd[-1]).write_bytes(b"\x00" * 4096)
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture()
def fake(monkeypatch):
    f = FakeRun()
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    return f


def status_on_disk(series):
    meta, _, _ = read_script(series.episodes_dir / EP / "script.yaml")
    return meta.get("status")


# --- the bypass, reproduced ------------------------------------------------------------


def test_the_gate_refuses_a_draft(series, draft, fake):
    """The control. Without this the test below could pass because nothing
    renders at all."""
    result = run("video", "render", EP, "--series", "the-brief")
    assert result.exit_code == 1, result.output
    assert not (draft.out_dir / GATED).exists()
    assert status_on_disk(series) == "draft"


def test_no_second_command_produces_the_file_the_gate_refused(series, draft, fake):
    """D-130, leader-verified: `render` refused this exact episode one test up,
    and `preview` produced the artifact anyway — same `_encode`, same path, no
    status check, no drift check, no ledger check, status still `draft`
    afterwards.

    Asserted on the FILE and not on the command, because the property is about
    the artifact: whatever the CLI grows next, an episode the gate refuses must
    have nothing in `out/`.
    """
    for name in _video_command_names() - {"render"}:
        result = runner.invoke(
            app, ["video", name, EP, "--series", "the-brief"], catch_exceptions=False
        )
        assert not (draft.out_dir / GATED).exists(), (
            f"`agsoc video {name}` wrote the gated artifact "
            f"(exit {result.exit_code}) on a draft the gate refused"
        )
    assert status_on_disk(series) == "draft"


# --- the enumeration -------------------------------------------------------------------


def _functions(path: Path) -> dict:
    """`{name: FunctionDef}` for every function defined in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        n.name: n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _called_names(node) -> set:
    out = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            f = child.func
            out.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", None))
    return out - {None}


def _callers_of(target: str) -> set:
    """`module:function` for every function in `src/` that calls `target`."""
    found = set()
    for path in sorted(SRC.rglob("*.py")):
        for name, fn in _functions(path).items():
            if target in _called_names(fn):
                found.add(f"{path.relative_to(SRC).as_posix()}:{name}")
    return found


def _video_command_names() -> set:
    return {c.name for c in typer.main.get_command(vcli.video_app).commands.values()}


def test_the_mp4_path_is_built_in_exactly_one_place():
    """`output_path` is the ONE answer to "where does this format's mp4 live".
    A second spelling of the f-string is the D-036 pattern, and here it means a
    file the gate's existence check does not guard."""
    builders = set()
    for path in sorted(SRC.rglob("*.py")):
        for name, fn in _functions(path).items():
            if any(
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and ".mp4" in n.value
                for n in ast.walk(fn)
            ) or any(
                isinstance(n, ast.JoinedStr)
                and ".mp4" in "".join(
                    v.value for v in n.values if isinstance(v, ast.Constant)
                )
                for n in ast.walk(fn)
            ):
                builders.add(f"{path.relative_to(SRC).as_posix()}:{name}")
    assert builders == {"video/render.py:output_path"}, sorted(builders)


def test_the_only_encoder_is_reached_from_exactly_one_function():
    """The enumeration D-130 says nobody ran. `_encode` is the only function
    that hands a path under `out/` to a writing process (ffmpeg `-y`), and its
    caller list is the list of ways to produce the artifact.

    Before the fix this set was `{preview, render_episode}` — two callers, one
    of them gated. That second entry is the whole defect.
    """
    assert _callers_of("_encode") == {"video/render.py:render_episode"}


def test_every_caller_of_output_path_is_named():
    """`output_path` is also read by the gate (does the file exist yet?) and by
    the success screen. Reading it is harmless; the point of the enumeration is
    that a NEW reader shows up here and has to say which kind it is."""
    assert _callers_of("output_path") == {
        # writes it (through ffmpeg), and only from the gated caller above
        "video/render.py:_encode",
        # reads it: the existence check, and the kept/replaced lists
        "video/render.py:render_episode",
    }


def test_exactly_one_cli_command_can_reach_the_encoder():
    """Transitively, off the AST. A command that calls something that calls
    `_encode` is a second door however deep the chain is — which is precisely
    how `preview` stayed invisible to an audit aimed at `render.mjs`."""
    graph = {}
    for path in sorted(SRC.rglob("*.py")):
        for name, fn in _functions(path).items():
            graph.setdefault(name, set()).update(_called_names(fn))

    def reaches(name, seen=None):
        seen = seen or set()
        if name in seen:
            return False
        seen.add(name)
        callees = graph.get(name, set())
        if "_encode" in callees:
            return True
        return any(reaches(c, seen) for c in callees)

    commands = _functions(SRC / "video" / "cli.py")
    encoders = {
        n for n in commands if n.startswith("video_") and reaches(n)
    }
    assert encoders == {"video_render"}, sorted(encoders)


def test_the_video_command_list_is_closed():
    """Not a style assertion. A command added here without a line in this test
    is a command nobody asked "what does it write" — which is the one question
    D-130 says was never put to `preview`."""
    assert _video_command_names() == {
        "new", "list", "ingest", "review", "check", "judge",
        "approve", "probe", "render", "console",
    }


def test_nothing_else_writes_into_the_out_directory():
    """`out/` holds the deliverable. The plan is the one other thing written
    there and it is an INPUT to the render, regenerated from the script every
    time — `plan-<fmt>.json`, never an `.mp4`."""
    writers = set()
    for path in sorted(SRC.rglob("*.py")):
        for name, fn in _functions(path).items():
            if "out_dir" in {
                n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)
            }:
                writers.add(f"{path.relative_to(SRC).as_posix()}:{name}")
    assert writers == {
        "video/plan.py:write_plan",       # plan-<fmt>.json
        "video/render.py:output_path",    # <fmt>-<w>x<h>.mp4
    }, sorted(writers)


def test_preview_is_retired(series, draft, fake):
    """D-119 retired `render.mjs --day` for being a second route to an MP4. The
    Python one survived because the audit was aimed at Node. `probe` covers
    looking; `render` covers producing; there is no third thing."""
    assert not hasattr(R, "preview")
    assert "preview" not in _video_command_names()
    result = runner.invoke(
        app, ["video", "preview", EP, "--series", "the-brief"], catch_exceptions=False
    )
    assert result.exit_code != 0
    assert not (draft.out_dir / GATED).exists()

"""No cwd-relative path may reach a subprocess.

precondition: `_run` starts both node and ffmpeg with `cwd=ENGINE_DIR`, while
`Workspace.locate()` returns `Path("workspace")` when `AGSOC_WORKSPACE` is unset
-- which is the DEFAULT. Any relative path therefore resolves against `engine/`.

This test enumerates the arguments rather than naming the ones that were known
to be broken: the first version of this file checked only node's `--plan`/`--out`
and passed while ffmpeg's output path was still relative, which cost a real
13-minute render. D-123's rule, applied late: enumerate, do not grep for symptoms.
"""
from pathlib import Path

import pytest

from agenticsocial.video import render as R

_PATHLIKE_SUFFIXES = (".json", ".png", ".mp4")


def _relative_paths(cmd: list[str]) -> list[str]:
    """Every argument that looks like a path and is not absolute."""
    bad = []
    for tok in cmd:
        if not isinstance(tok, str) or tok.startswith("-"):
            continue
        if tok.endswith(_PATHLIKE_SUFFIXES) or "/" in tok:
            if not Path(tok).is_absolute():
                bad.append(tok)
    return bad


@pytest.fixture
def spy(monkeypatch):
    seen: list[list[str]] = []
    monkeypatch.setattr(R, "_run", lambda cmd, what: seen.append(cmd))
    monkeypatch.setattr(R, "_require_tools", lambda probe: None)
    monkeypatch.setattr(
        R, "write_plan", lambda s, e, f: Path("workspace/ep/out/plan-vertical.json")
    )
    monkeypatch.setattr(
        R.json,
        "loads",
        lambda t: {
            "total_sec": 10.0,
            "fps": 30,
            "format": {"w": 1080, "h": 1920},
            "script_file_sha256": "abc",
        },
    )
    monkeypatch.setattr(Path, "read_text", lambda self, **k: "{}")
    return seen


class _Ep:
    id = "2026-08-18"
    probe_dir = Path("workspace/ep/probe")
    out_dir = Path("workspace/ep/out")


class _Series:
    name = "The Brief"


def test_probe_hands_node_no_relative_path(spy):
    R.probe(_Series(), _Ep(), "vertical")
    assert spy, "the renderer was never invoked"
    for cmd in spy:
        assert not _relative_paths(cmd), f"relative path reached {cmd[0]}: {_relative_paths(cmd)}"


def test_encode_hands_node_and_ffmpeg_no_relative_path(spy, monkeypatch, tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "00001.png").write_bytes(b"")
    monkeypatch.setattr(R.tempfile, "mkdtemp", lambda prefix: str(frames))
    monkeypatch.setattr(R.shutil, "rmtree", lambda p, ignore_errors=False: None)

    R._encode(_Series(), _Ep(), "vertical", Path("workspace/ep/out/plan.json"), R.json.loads(""))

    assert any(c[0] == "ffmpeg" for c in spy), "ffmpeg was never invoked"
    for cmd in spy:
        assert not _relative_paths(cmd), f"relative path reached {cmd[0]}: {_relative_paths(cmd)}"

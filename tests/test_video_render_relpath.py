"""A relative workspace root must not break the renderer subprocess.

precondition: node runs with cwd=ENGINE_DIR, so any cwd-relative path handed to
it resolves against the wrong directory. `Workspace.locate()` returns
Path("workspace") when AGSOC_WORKSPACE is unset, which is the DEFAULT, so this
is the normal path rather than an edge case.
"""
from pathlib import Path
from agenticsocial.video import render as R


def test_every_path_handed_to_node_is_absolute(monkeypatch):
    seen: list[list[str]] = []
    monkeypatch.setattr(R, "_run", lambda cmd, what: seen.append(cmd))
    monkeypatch.setattr(R, "_require_tools", lambda probe: None)
    monkeypatch.setattr(R, "write_plan", lambda s, e, f: Path("workspace/ep/out/plan-vertical.json"))
    monkeypatch.setattr(R.json, "loads", lambda t: {"total_sec": 10.0, "format": {"w": 1, "h": 2}})
    monkeypatch.setattr(Path, "read_text", lambda self, **k: "{}")

    class E:
        id = "2026-08-18"
        probe_dir = Path("workspace/ep/probe")
    R.probe(object(), E(), "vertical")

    assert seen, "the renderer was never invoked"
    for cmd in seen:
        for i, tok in enumerate(cmd):
            if tok in ("--plan", "--out"):
                p = cmd[i + 1]
                assert Path(p).is_absolute(), f"{tok} got a relative path: {p!r}"

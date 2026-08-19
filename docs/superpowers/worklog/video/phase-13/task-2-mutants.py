"""Mutation sweep for Phase 13 Task 2 — every writer of the gated artifact.

Each mutant is a one-line-ish source edit that re-opens a route to
`out/<fmt>-<w>x<h>.mp4` that does not pass the three checks, or that breaks one
of the checks. PYTHONDONTWRITEBYTECODE=1 (D-100): consecutive mutants land inside
one mtime second and CPython would otherwise import a stale .pyc and report the
UNMUTATED module as surviving.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RENDER = ROOT / "src/agenticsocial/video/render.py"
CLI = ROOT / "src/agenticsocial/video/cli.py"

TESTS = [
    "tests/test_video_gated_artifact.py",
    "tests/test_video_render.py",
    "tests/test_video_render_cmd.py",
    "tests/test_video_probe_cmd.py",
    "tests/test_video_format.py",
    "tests/test_video_cli.py",
    "tests/test_video_approve.py",
]

PREVIEW = '''
def preview(series: Series, episode: Episode, fmt: str = "vertical") -> Path:
    """The retired ungated route, restored."""
    if fmt not in FORMATS:
        raise RenderError(f"unsupported format {fmt!r}")
    _require_tools(False)
    plan_path = write_plan(series, episode, fmt)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return _encode(series, episode, fmt, plan_path, plan)[0]


'''

PREVIEW_CMD = '''
@video_app.command("preview")
def video_preview(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """The retired ungated command, restored."""
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        out = render_mod.preview(s, ep)
    except (SeriesError, EpisodeError, PlanError, render_mod.RenderError) as e:
        raise _fail(str(e))
    typer.echo(f"wrote {out}")


'''

# (name, file, old, new)
MUTANTS = [
    (
        "M1 the defect itself: `preview` restored, function and command",
        None, None, None,  # handled specially: two files
    ),
    (
        "M2 the module-level function comes back, no CLI command",
        RENDER, "def probe(\n", PREVIEW + "def probe(\n",
    ),
    (
        "M3 a second caller of `_encode` inside src/",
        RENDER,
        "def output_path(episode: Episode, fmt: str) -> Path:",
        "def quick(series, episode, fmt='vertical'):\n"
        "    p = write_plan(series, episode, fmt)\n"
        "    return _encode(series, episode, fmt, p, json.loads(p.read_text()))\n\n\n"
        "def output_path(episode: Episode, fmt: str) -> Path:",
    ),
    (
        "M4 a CLI command reaches the encoder directly",
        CLI,
        '@video_app.command("probe")',
        '@video_app.command("draftcut")\n'
        "def video_draftcut(episode: str, series: str = DEFAULT_SERIES) -> None:\n"
        '    """A cut of the draft."""\n'
        "    ws = _workspace()\n"
        "    s = load_series(ws, series)\n"
        "    ep = load_episode(s, episode)\n"
        "    p = render_mod.write_plan(s, ep, 'vertical')\n"
        "    render_mod._encode(s, ep, 'vertical', p, json.loads(p.read_text()))\n\n\n"
        '@video_app.command("probe")',
    ),
    (
        "M5 the mp4 path is spelled a second time, inside the encoder",
        RENDER,
        "        mp4 = output_path(episode, fmt)",
        "        geometry = FORMATS[fmt]\n"
        "        mp4 = episode.out_dir / f\"{fmt}-{geometry['w']}x{geometry['h']}.mp4\"",
    ),
    (
        "M6 `probe` writes its frames into out/ beside the deliverable",
        RENDER, "    out = episode.probe_dir", "    out = episode.out_dir",
    ),
    (
        "M7 the status check goes",
        RENDER,
        "    assert_transition(episode.status, Status.RENDERING, VIDEO_TRANSITIONS)",
        "    pass",
    ),
    (
        "M8 the drift check goes",
        RENDER,
        "    drift = approve_mod.approval_drift(episode)\n    if drift:",
        "    drift = approve_mod.approval_drift(episode)\n    if False:",
    ),
    (
        "M9 the ledger check goes",
        RENDER,
        "    stale = verify_mod.stale_reason(episode, verify_mod.read_ledger(episode))\n"
        "    if stale:",
        "    stale = verify_mod.stale_reason(episode, verify_mod.read_ledger(episode))\n"
        "    if False:",
    ),
    (
        "M10 the encode happens before the gate is asked",
        RENDER,
        "    # --- 1. status ------------------------------------------------------------",
        "    _p = write_plan(series, episode, targets[0])\n"
        "    _encode(series, episode, targets[0], _p, json.loads(_p.read_text()))\n"
        "    # --- 1. status ------------------------------------------------------------",
    ),
    (
        "M11 ffmpeg is no longer required up front",
        RENDER,
        "    _require_tools(False)\n\n    series = load_series(ws, series_slug)",
        "    _require_tools(True)\n\n    series = load_series(ws, series_slug)",
    ),
    (
        "M12 the artifact lands beside the script instead of in out/",
        RENDER,
        "    return episode.out_dir / f\"{fmt}-{geometry['w']}x{geometry['h']}.mp4\"",
        "    return episode.dir / f\"{fmt}-{geometry['w']}x{geometry['h']}.mp4\"",
    ),
    (
        "M13 the mp4 loses the script hash that ties it to an approval",
        RENDER,
        '                "-metadata", f"comment=script_file_sha256={plan[\'script_file_sha256\']}",',
        '                "-metadata", "comment=agsoc",',
    ),
]


def run_tests():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        ["uv", "run", "pytest", "-x", "-q", "-p", "no:randomly", *TESTS],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout


def apply(path, old, new):
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"MUTANT DID NOT APPLY: {old[:60]!r}")
    path.write_text(text.replace(old, new, 1))


def main():
    originals = {p: p.read_text() for p in (RENDER, CLI)}
    killed, survived = [], []
    try:
        for name, path, old, new in MUTANTS:
            if path is None:  # M1: two files at once
                apply(RENDER, "def probe(\n", PREVIEW + "def probe(\n")
                apply(CLI, '@video_app.command("probe")', PREVIEW_CMD + '@video_app.command("probe")')
            else:
                apply(path, old, new)
            code, out = run_tests()
            for p, text in originals.items():
                p.write_text(text)
            tail = [l for l in out.splitlines() if "passed" in l or "failed" in l]
            verdict = "KILLED  " if code != 0 else "SURVIVED"
            (killed if code != 0 else survived).append(name)
            first = next(
                (l for l in out.splitlines() if l.startswith("FAILED") or "assert" in l),
                "",
            )
            print(f"{verdict} {name}\n         {tail[-1] if tail else ''}")
            sys.stdout.flush()
    finally:
        for p, text in originals.items():
            p.write_text(text)
    print(f"\n{len(killed)}/{len(MUTANTS)} killed")
    for s in survived:
        print(f"  SURVIVED: {s}")


main()

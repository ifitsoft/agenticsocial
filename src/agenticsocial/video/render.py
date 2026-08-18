"""Drive the Node renderer and ffmpeg from Python.

Phase 1.5 ships `preview`, not `render`. Spec §10 makes RENDERING reachable only
from APPROVED, and there is no approve command until Phase 7 — so a command
named `render` today would have to bypass the gate it is named after. `preview`
never touches status. Phase 8 adds the gated `render` on top of this.
"""
from __future__ import annotations

import json
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

    plan_path = write_plan(series, episode, fmt)  # raises PlanError before any subprocess
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    if probe:
        # --out, not engine/probe: probe frames belong to the episode that
        # produced them, and two episodes probed in a row must not overwrite
        # each other. render.mjs honours --out in probe mode for this reason.
        out = episode.out_dir / "probe"
        _run(
            ["node", "render.mjs", "--plan", str(plan_path), "--probe", "--out", str(out)],
            "the renderer",
        )
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
                "-metadata", f"comment=script_file_sha256={plan['script_file_sha256']}",
                "-metadata", f"title={series.name} — {episode.id}",
                str(mp4),
            ],
            "ffmpeg",
        )
        return mp4
    finally:
        # ~2.5 GB per full episode (spec §5). Never leave these behind.
        shutil.rmtree(frames, ignore_errors=True)

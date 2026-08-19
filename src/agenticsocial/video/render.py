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
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..models import VIDEO_TRANSITIONS, Status, assert_transition
from ..workspace import Workspace
from . import approve as approve_mod
from . import verify as verify_mod
from .episode import load_episode, set_status
from .models import Episode, Series
from .plan import FORMATS, write_plan
from .series import load_series

ENGINE_DIR = Path(__file__).resolve().parents[3] / "engine"
TOOLS = ("node", "ffmpeg")


class RenderError(Exception):
    pass


class RenderRefused(Exception):
    """A refusal an operator can act on, and `kind` says which thing moved.

    `status` · `drift` · `ledger` — D-115's three checks, kept three answers all
    the way to the screen. The distinction is the whole point: one says "nobody
    has approved this", one says "you edited it after approving", one says "the
    corpus moved under the check". They are three different files to open, and a
    single message the operator has to pattern-match would be one screen for
    three different problems.
    """

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


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


def _abs(p: Path) -> str:
    """A path for the renderer, always absolute.

    `_run` starts node with `cwd=ENGINE_DIR`, and `Workspace.locate()` returns
    `Path("workspace")` when `AGSOC_WORKSPACE` is unset — which is the DEFAULT.
    A cwd-relative path therefore resolved against `engine/` and the renderer
    died with a raw `ENOENT` on a path that plainly existed. Handing a
    cwd-relative path to a process with a different cwd is the bug; resolving at
    the boundary is the fix, and it belongs here rather than in `locate()`
    because this is the only place the cwd changes.
    """
    return str(Path(p).resolve())


def _run(cmd: list[str], what: str) -> None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ENGINE_DIR)
    except OSError as e:
        raise RenderError(f"could not start {what}: {e}")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        raise RenderError(f"{what} failed (exit {proc.returncode}):\n  " + "\n  ".join(tail))


def preview(series: Series, episode: Episode, fmt: str = "vertical") -> Path:
    """Render an episode to video without touching its status. Returns the mp4.

    It took a `probe=True` until Phase 8. That made the cheap operation a flag
    on the expensive one — see `probe` below for why that is the wrong way
    round — and `probe` is now its own function and its own command.
    """
    if fmt not in FORMATS:
        raise RenderError(f"unsupported format {fmt!r}")
    _require_tools(False)

    plan_path = write_plan(series, episode, fmt)  # raises PlanError before any subprocess
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return _encode(series, episode, fmt, plan_path, plan)[0]


def probe(
    series: Series, episode: Episode, fmt: str = "vertical", at: float | None = None
) -> Path:
    """One frame per beat, or one frame at `at`. No encode. Spec §6.

    **This is the answer to D-116's gap.** The approval covers everything the
    operator authors and nothing the renderer is: a font substitution changes
    every frame with all three of `render`'s checks green. Nothing can make the
    approval cover the pixels, so the honest response is to make looking at them
    cheap — seconds and a handful of PNGs, against ~230 ms per frame for the
    fourteen minutes a full episode costs.

    **Ungated, deliberately.** No status is read and none is written. Probing is
    how an operator decides whether to approve, so requiring approval first
    inverts the workflow; and `rendered` being terminal (D-006) is a statement
    about transitions, not about whether you may look at the file.

    It renders the SAME plan `render` would — `write_plan` is called the same
    way — because a probe drawn from anywhere else would be inspecting something
    other than the render it is meant to inform.
    """
    if fmt not in FORMATS:
        raise RenderError(
            f"unsupported format {fmt!r} — this phase renders: "
            f"{', '.join(sorted(FORMATS))}"
        )
    # node only. A probe never encodes, and demanding ffmpeg here would send an
    # operator to install something this command does not use.
    _require_tools(True)

    plan_path = write_plan(series, episode, fmt)  # raises PlanError before any subprocess
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    # Every refusal BEFORE anything is removed. `--at 90` on a six-second
    # episode used to refuse correctly and take the last probe's frames with
    # it, which makes typing a number and looking expensive in exactly the way
    # this command exists to avoid.
    total = plan["total_sec"]
    if at is not None and (at < 0 or at > total):
        # Python resolved the runtime, so this costs nothing — and the frame it
        # would otherwise shoot is a black rectangle, which reads as a broken
        # renderer rather than as a number typed past the end.
        raise RenderError(
            f"t={at:g}s is outside this episode — it runs {total:.1f}s"
        )

    out = episode.probe_dir
    # Clear the last probe, HERE rather than in the renderer. Stale frames
    # beside fresh ones are the stale-ledger problem in PNG form: an operator
    # cannot tell which of them describes the script they are reading. render.mjs
    # also clears its --probe directory, but only that one and only in that mode,
    # and a guarantee that lives in the subprocess is one Python cannot state.
    out.mkdir(parents=True, exist_ok=True)
    for stale_png in out.glob("*.png"):
        stale_png.unlink()

    if at is None:
        _run(
            ["node", "render.mjs", "--plan", _abs(plan_path), "--probe", "--out", _abs(out)],
            "the renderer",
        )
        return out

    # Frames belong to the episode that produced them: --out, never
    # engine/probe, so two episodes probed in a row cannot overwrite each other.
    _run(
        ["node", "render.mjs", "--plan", _abs(plan_path), "--at", str(at), "--out", _abs(out)],
        "the renderer",
    )
    return out / f"at-{at}.png"


def output_path(episode: Episode, fmt: str) -> Path:
    """Where one format's MP4 lives. The ONE answer to that question.

    It is asked twice and by two different kinds of caller — the encoder, which
    is about to write the file, and the gate, which needs to know whether a file
    is already there before it overwrites thirteen minutes of somebody's
    machine. Two spellings of the same f-string is the D-036 pattern, and here
    the two answers disagreeing means the check guards a path nothing writes.

    Derived from `FORMATS`, not from `plan.json`: the plan is built from the
    same table, and the caller that needs to ask "does this exist yet?" has not
    built a plan and must not have to build one to find out.
    """
    geometry = FORMATS[fmt]
    return episode.out_dir / f"{fmt}-{geometry['w']}x{geometry['h']}.mp4"


def _encode(
    series: Series, episode: Episode, fmt: str, plan_path: Path, plan: dict
) -> tuple[Path, dict]:
    """plan -> node -> ffmpeg. Returns (the mp4, the plan it was made from).

    One function, two callers: `preview` (ungated) and `render_episode` (gated).
    Two renderers would be two things to keep identical, and the gated one would
    be the one nobody exercised while developing.
    """
    # Spec §5: the frames are ~2.5 GB per episode and they live in a temp
    # directory, never inside `workspace/`. A SIGKILL runs no `finally`, and
    # 2.5 GB of PNGs left in the operator's content directory is a mess they
    # have to find before they can understand it.
    frames = Path(tempfile.mkdtemp(prefix=f"agsoc-frames-{episode.id}-"))
    try:
        _run(
            ["node", "render.mjs", "--plan", _abs(plan_path), "--out", _abs(frames)],
            "the renderer",
        )
        if not any(frames.glob("*.png")):
            raise RenderError(
                "the renderer produced no frames — check the script has beats"
            )
        mp4 = output_path(episode, fmt)
        _run(
            [
                "ffmpeg", "-y",
                "-framerate", str(plan["fps"]),
                "-i", _abs(frames / "%05d.png"),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-metadata", f"comment=script_file_sha256={plan['script_file_sha256']}",
                "-metadata", f"title={series.name} — {episode.id}",
                _abs(mp4),
            ],
            "ffmpeg",
        )
        return mp4, plan
    finally:
        shutil.rmtree(frames, ignore_errors=True)


# --- §10: the gated render ------------------------------------------------------------


@dataclass(frozen=True)
class RenderResult:
    """What was rendered and where it landed.

    Frozen for D-062's reason: this is the object the success screen is written
    from, and a verdict a caller can edit after the fact is not a verdict. The
    record is what `script.yaml` received; `path` is that same file resolved on
    this machine, and the record keeps it relative so a moved workspace does not
    turn the artifact into a dangling absolute path.
    """

    record: dict
    path: Path


@dataclass(frozen=True)
class RenderRun:
    """What ONE invocation did — which is not the same as what it rendered.

    `kept` is here because a format that was skipped is a thing the operator has
    to be told: `render <ep>` on an episode with a vertical cut already on disk
    does less than its name says, and a success screen listing two files it did
    not make is this project's overclaim pattern in its purest form (D-123).
    `replaced` is the other half — an 18 MB file that is gone.
    """

    rendered: tuple[RenderResult, ...]
    # Paths, not format names: the operator's question about a kept file is
    # "which file did you leave alone", and a name it can be pasted after is a
    # better answer than a word they have to map back onto a filename.
    kept: tuple[Path, ...] = ()
    replaced: tuple[Path, ...] = ()


def render_episode(
    ws: Workspace,
    series_slug: str,
    ep_id: str,
    *,
    fmt: str | None = None,
    replace: bool = False,
    restart: bool = False,
    now: str | None = None,
) -> RenderRun:
    """Render an approved episode's formats, or refuse. Spec §9, §10.

    **`fmt=None` means every format `series.toml` enables**, which is what §9's
    `agsoc video render 2026-08-14` has always been documented to do. Before
    Phase 13 it rendered `vertical` and `[formats] enabled` was read by nothing
    but the list screen.

    **A second format is a second artifact, not a second story.** The episode
    may already be `rendered`, and `rendered → rendering` is the edge that
    allows it (D-006 is untouched — see `VIDEO_TRANSITIONS`). The three gates
    are re-asked in full every time: a second format is only safe *because* the
    script and the design are provably unchanged since approval, so the drift
    check is what makes the new edge legitimate rather than something the new
    edge had to get past.

    **What protects an existing file is not the status machine.** It is that a
    format already on disk is never re-rendered without `replace=True`. That is
    the honest place for the guarantee: `rendered` being terminal never
    protected anything a `--restart` or a `failed` retry could not walk around,
    and it forbade the one operation §9 promises.

    **Takes identifiers, not objects (D-072).** It loads the series, the episode
    and the ledger itself, immediately before the transition, so there is no
    argument a caller can shape to change the verdict. D-059 is the reason the
    standing rule exists: a gate checked against an in-memory object, with a
    second writer stamping the gated value onto disk, laundered its own bypass.

    **The gate is three checks and they stay three (D-115).** Status, then
    authored drift, then ledger freshness — in that order, each raising
    distinguishably, so an operator is told *which* thing moved rather than that
    something did:

      1. `assert_transition(... RENDERING ...)` — has a human approved this?
      2. `approval_drift` — has anything the operator authored changed since?
      3. `stale_reason` — does the check still describe the corpus?

    Folding them into one predicate would rebuild the two-paths-to-one-answer
    shape Phase 7 spent three tasks eliminating (D-113). It would also make the
    screen useless: the three answers send you to three different files.

    **It does not re-run `check`.** Same argument `approve` makes: the ledger is
    the artifact of record and the screen a human read before signing, so a
    second set of verdicts computed in here would be verdicts nobody displayed —
    and a second producer of verdicts is the D-059 shape again. This requires
    the ledger to be fresh; it does not recompute it.

    **A crash leaves a state the operator can recover from.** This is the video
    analogue of `publish_variant`'s save-after-every-tweet: the point is not
    that nothing is lost, it is that the episode is never left in a status no
    supported command can leave. Any failure — `BaseException`, so Ctrl-C
    counts, and it is the likeliest way a fourteen-minute render ends early —
    moves `rendering → failed` and records why. §10's `failed → rendering` is
    then the retry, and it passes all three checks again.

    The one thing no handler catches is SIGKILL or power loss, which leaves
    `rendering` on disk with no live process. `--restart` is the door out:
    `rendering → failed`, then the normal path. It answers the STATUS question
    only — drift and staleness are still asked — so it is a recovery, not a
    bypass.

    **What it does NOT establish, and the success screen says so:** that these
    frames are the frames the approver would have seen. D-116 states the scope
    exactly — the approval covers everything the operator authors and nothing
    the renderer is. The font this machine resolved is outside it, and a font
    substitution changes every frame with all three checks green.
    """
    if fmt is not None and fmt not in FORMATS:
        raise RenderError(
            f"unsupported format {fmt!r} — this phase renders: "
            f"{', '.join(sorted(FORMATS))}"
        )
    # Before the gate is spent, not after: an absent ffmpeg must not cost an
    # approved episode its status, and it must not be discovered after minutes
    # of frames.
    _require_tools(False)

    series = load_series(ws, series_slug)
    # Two different refusals, and collapsing them would send an operator to the
    # wrong file: an UNSUPPORTED format is a name the engine cannot draw and the
    # fix is in plan.py; a format this SERIES has not enabled is a name the
    # engine draws fine and the fix is one line of series.toml. `series.formats`
    # is validated against FORMATS at load, so the list below is always a subset.
    if fmt is None:
        targets = list(series.formats)
    elif fmt not in series.formats:
        raise RenderError(
            f"{series.slug} does not render {fmt!r} — series.toml's "
            f"`[formats] enabled` lists: {', '.join(series.formats)}. Add it "
            "there, or render one of those"
        )
    else:
        targets = [fmt]

    # Matched exactly. `resolve_episode`'s substring matching is right for
    # `review`, which shows you what it found, and wrong here, where the thing
    # it might find is an expensive render of an episode you did not name.
    episode = load_episode(series, ep_id)

    # --- 1. status ------------------------------------------------------------
    if episode.status is Status.RENDERING:
        # No handler runs on SIGKILL or a power cut, so this is a real state and
        # the CLI has to be able to leave it. It is also indistinguishable from
        # a render running in another terminal, which is why it takes a flag: a
        # status that can only be escaped by hand-editing a file is a bug, and a
        # render that silently steals another one's episode is a worse one.
        if not restart:
            raise RenderRefused(
                "interrupted",
                "this episode is already `rendering` — either a render is "
                "running right now, or one was killed before it could record "
                "how it ended",
            )
        episode = set_status(
            episode,
            Status.FAILED,
            {
                "render": _failure_record(
                    "the previous render was abandoned", targets[0], now
                )
            },
        )
    assert_transition(episode.status, Status.RENDERING, VIDEO_TRANSITIONS)

    # --- 2. has anything the operator authored moved? -------------------------
    drift = approve_mod.approval_drift(episode)
    if drift:
        raise RenderRefused("drift", drift)

    # --- 3. does the check still describe the corpus? -------------------------
    stale = verify_mod.stale_reason(episode, verify_mod.read_ledger(episode))
    if stale:
        raise RenderRefused("ledger", stale)

    # --- 4. is there anything left to render? ---------------------------------
    # AFTER the three gates, deliberately. A drifted episode whose formats all
    # happen to be on disk must still be told it has drifted: "everything is
    # already rendered" is only a true account of the situation when nothing
    # else would have stopped you.
    on_disk = [f for f in targets if output_path(episode, f).is_file()]
    todo = list(targets) if replace else [f for f in targets if f not in on_disk]
    if not todo:
        # Not a success with an empty list. A screen that names two files this
        # invocation did not make, under a green heading, is the overclaim
        # pattern (D-123) with the operator's own artifacts as the subject.
        raise RenderRefused(
            "exists",
            "already rendered: "
            + ", ".join(
                str(output_path(episode, f).relative_to(episode.dir)) for f in on_disk
            ),
        )

    # The authoritative gate: `set_status` re-reads the status ON DISK and
    # asserts the transition itself, in the same function that performs the
    # write. The check above is the same assertion made early so the refusal is
    # cheap and legible; this one is the guarantee.
    #
    # ONE transition covers every format in the run: the formats are the same
    # story, `rendering → rendering` is not an edge, and a status written per
    # format would be a second reason to write status inside the loop.
    episode = set_status(episode, Status.RENDERING)

    results: list[RenderResult] = []
    current = todo[0]
    try:
        for current in todo:
            plan_path = write_plan(series, episode, current)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            mp4, plan = _encode(series, episode, current, plan_path, plan)
            results.append(
                RenderResult(record=_render_record(episode, plan, mp4, now), path=mp4)
            )
    except BaseException as e:
        # `BaseException`, not `Exception`: Ctrl-C is the likeliest way a
        # fourteen-minute render ends early, and an `except Exception` here
        # would leave exactly the `rendering` forever this exists to prevent.
        # `current` is the format that died, not the one that was asked for:
        # "wide failed" and "vertical failed" send an operator to different
        # frames, and a two-format run can fail on either.
        _fail_episode(episode, e, current, now)
        raise

    # The LAST record, and `render` keeps the meaning it has always had: the
    # most recent render ATTEMPT, success or failure. It is not a per-format
    # archive and must not become one — the per-format audit trail is in the MP4
    # itself, where ffmpeg wrote `script_file_sha256` into the container's
    # comment tag, so each file can be matched back to the script it was made
    # from without this record at all.
    set_status(episode, Status.RENDERED, {"render": results[-1].record})
    return RenderRun(
        rendered=tuple(results),
        kept=tuple(output_path(episode, f) for f in targets if f not in todo),
        replaced=tuple(output_path(episode, f) for f in todo if f in on_disk),
    )


def _fail_episode(episode: Episode, error: BaseException, fmt: str, now) -> None:
    """`rendering → failed`, with what failed, and never masking the original.

    A `failed` status with no account of what failed sends the operator back to
    a terminal they have already closed. If the write itself fails there is
    nothing useful left to do — the original exception is the one that explains
    the episode, and swallowing it to report a second one would lose both.
    """
    reason = f"{type(error).__name__}: {error}".rstrip(": ")
    try:
        set_status(episode, Status.FAILED, {"render": _failure_record(reason, fmt, now)})
    except Exception:  # pragma: no cover - the disk is failing under us
        pass


def _failure_record(reason: str, fmt: str, now) -> dict:
    return {
        "at": now or datetime.now().astimezone().isoformat(timespec="seconds"),
        "outcome": "failed",
        "format": fmt,
        "error": reason,
    }


def _render_record(episode: Episode, plan: dict, mp4: Path, now: str | None) -> dict:
    """What went into `script.yaml` beside the status.

    R4's "somewhere stated": an operator a month later reads the episode, not
    the terminal it was rendered in. It names the approval it acted on, because
    an artifact that cannot say which signature it was made under is an artifact
    nobody can audit — and `script_file_sha256` is the same value ffmpeg wrote
    into the container's `comment` tag, so the file on disk can be matched back
    to the script without this file at all.
    """
    approval = approve_mod.approval_record(episode) or {}
    return {
        "at": now or datetime.now().astimezone().isoformat(timespec="seconds"),
        "outcome": "rendered",
        "format": plan["format"]["name"],
        # Relative to the episode directory: absolute paths in a committed
        # artifact are a lie the moment the workspace moves.
        "file": str(mp4.relative_to(episode.dir)),
        "bytes": mp4.stat().st_size,
        "width": plan["format"]["w"],
        "height": plan["format"]["h"],
        "fps": plan["fps"],
        "frames": plan["total_frames"],
        "runtime_sec": plan["total_sec"],
        "script_file_sha256": plan["script_file_sha256"],
        "approval": {"by": approval.get("by"), "at": approval.get("at")},
    }

"""Phase 8 Task 2 — the engine has one supported entrypoint, and it is a plan.

`render.mjs --day <date>` read `content/<date>.js`: two hand-written episodes,
each a JavaScript file calling `scene()` per beat. That path proved the plumbing
in Phase 1.5 and produced the two videos in `engine/`. It is not the product.
Nothing it renders has been through `check`, nothing it renders has been
approved, and a second way to turn an episode into an MP4 is a second way to
skip the gate Phase 7 spent three tasks building.

**The split, stated once:**

* `content/2026-08-12.js` and `content/2026-08-14.js` **stay**, and stay
  exercised. They are the engine's only real regression fixtures — two full
  episodes, every builder, both chart forms — and `determinism.test.mjs` drives
  them through `scene.html?day=…`, which is also how an operator scrubs the
  slider in a browser. Deleting them would trade the invariant's only realistic
  input for a tidier directory.
* `render.mjs --day` **goes**. The renderer takes a resolved `plan.json` and
  nothing else, so the only way to get frames out of this engine is through
  Python, which means through the gate.

The tests here read source and documentation rather than running a render: a
render is ~230 ms per frame (R6), and what is being pinned is which doors exist,
which is a property of the text.
"""
import re
from pathlib import Path

import pytest

from agenticsocial.video import render as R

ENGINE = Path(R.ENGINE_DIR)
ROOT = ENGINE.parent


@pytest.fixture()
def mjs():
    return (ENGINE / "render.mjs").read_text(encoding="utf-8")


@pytest.fixture()
def code(mjs):
    """`render.mjs` with its comments removed.

    The flag assertions run on the CODE, because the file's header is where the
    retirement is explained to the next reader and that explanation has to be
    able to name the thing it retired. A comment saying `--day` is gone is the
    opposite of a `--day` that still works.
    """
    return re.sub(r"/\*.*?\*/", "", mjs, flags=re.S)


# --- the renderer takes a plan, and only a plan ---------------------------------------


def test_the_renderer_has_no_day_path(code):
    """The retirement itself. `--day` is the flag that made the hand-written
    episodes *the way to render a video*, and while it exists there are two
    routes to an MP4 — one of them past `approve`."""
    assert "--day" not in code
    assert "content/" not in code


def test_the_renderer_refuses_to_run_without_a_plan(mjs, code):
    """Refused, not defaulted. `--day` defaulted to today, so a bare
    `node render.mjs` rendered *something*; the replacement must say what is
    missing and name the command that supplies it."""
    assert "--plan" in code
    assert "if (!planPath)" in code, "nothing refuses a bare invocation"
    assert "process.exit(2)" in code
    assert "agsoc video render" in mjs  # the header names the supported path


def test_the_renderer_has_no_timing_arithmetic_of_its_own(code):
    """M9/D-007, and the reason the day path had to go rather than be left
    alone: the fallback `Math.round(total * FPS)` existed *for* `--day`, and a
    fallback is a second answer to a question the plan already answers. They
    disagree at the rounding boundary, and that reaches a viewer as a video
    that stops a frame early."""
    assert "plan.total_frames" in code
    assert "plan.fps" in code
    for arithmetic in ("* FPS", "*FPS", "const FPS", "Math.round(total"):
        assert arithmetic not in code, arithmetic


def test_a_plan_with_no_frame_count_is_refused_before_a_browser_is_launched(code):
    """Fail fast on the cheap check. Launching Chromium to discover the plan is
    unrenderable spends seconds to learn something readable from the file."""
    guard = "Number.isInteger(plan.total_frames)"
    launch = "chromium" + ".launch"  # assembled: test files are scanned for this
    assert guard in code
    assert code.index(guard) < code.index(launch), (
        "the frame-count guard runs after the browser is launched"
    )


# --- what does NOT retire --------------------------------------------------------------


def test_the_two_hand_written_episodes_are_still_present():
    """The split's other half. These are the engine's only real regression
    fixtures; "retired" means "no longer the way to render", not "deleted"."""
    for day in ("2026-08-12", "2026-08-14"):
        assert (ENGINE / "content" / f"{day}.js").is_file()


def test_the_hand_written_episodes_are_still_exercised_by_a_test():
    """A fixture nothing runs is a file waiting to be deleted by the next person
    who greps for `--day` and finds nothing. `determinism.test.mjs` drives them
    through `scene.html?day=…` — which is the browser path, not the renderer's,
    and is why retiring `render.mjs --day` does not cost the coverage."""
    det = (ENGINE / "determinism.test.mjs").read_text(encoding="utf-8")
    assert "day=2026-08-14" in det


def test_the_browser_still_loads_an_episode_by_day():
    """`scene.html?day=…` is the operator's scrubbing surface and the fixture
    loader. Retiring the renderer's flag must not take it with it."""
    scene = (ENGINE / "scene.html").read_text(encoding="utf-8")
    assert "day" in scene


# --- the supported path is obvious to a reader ----------------------------------------


def test_the_engine_readme_names_the_supported_path():
    """R4's documentation half. Someone reading `engine/README.md` a month from
    now must be told which command makes a video, and must not be handed a
    recipe that pipes hand-written frames into ffmpeg by hand."""
    readme = (ENGINE / "README.md").read_text(encoding="utf-8")
    assert "agsoc video render" in readme
    assert "node render.mjs --day" not in readme


def test_claude_md_lists_the_engine_test_files():
    """CLAUDE.md enumerates what `engine/` tracks, and the three test files were
    missing from it — including the determinism test that the same paragraph
    calls load-bearing."""
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for name in ("determinism.test.mjs", "network.test.mjs", "coverage.test.mjs"):
        assert name in claude, name

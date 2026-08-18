"""`agsoc video render` — the gated path from an approved episode to an MP4.

Spec §6, §9, §10. The mutant table is in the Phase 8 Task 1 brief; every test
here names the mutant it kills.

Four habits, each because the matching mutant is a one-line source edit:

  * **Exit code AND output AND `result.exception`** (D-035). `CliRunner` turns a
    traceback into exit code 1 with empty output, which is byte-identical to a
    clean refusal from a test's point of view.
  * **Every refusal also asserts the status ON DISK did not move** (D-059). A
    gate that refuses while a second writer moves the status is exactly the
    defect that published a draft in v1.
  * **The three refusals are asserted to be DISTINGUISHABLE from each other**,
    not merely to be refusals. M4 is a render that refuses correctly and tells
    the operator nothing about which of three files to open.
  * **No test renders a full episode** (R6). Every subprocess is faked, and the
    fixture script is seconds long. See `test_the_render_fixture_is_seconds_...`.
"""
import ast
import inspect
import json
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import corpus
from agenticsocial.video import render as R
from agenticsocial.video.episode import create_episode, load_episode, read_script
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()

EP = "2026-08-17"
BY = "Ali Abdukarim"

SOURCE = (
    "DeepSeek's 1.6T MoE flagship quietly moved from preview to general "
    "availability this week, then announced new pricing starting August 16 at "
    "about $1.32 / $3.96 per 1M tokens (in/out)."
)


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


class FakeRun:
    """Records subprocess calls; fabricates the artifacts each step promises.

    R6: this is why the suite costs milliseconds instead of minutes. A real
    render is ~230 ms per frame — a 120 s episode is fourteen minutes — and the
    thing under test here is the gate and the status machine, neither of which
    is made more true by a real Chromium.
    """

    def __init__(self, fail_on=None, returncode=1, stderr="", raises=None):
        self.calls = []
        self.fail_on = fail_on
        self.returncode = returncode
        self.stderr = stderr
        self.raises = raises

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        exe = Path(cmd[0]).name
        if self.fail_on and exe.startswith(self.fail_on):
            if self.raises is not None:
                raise self.raises
            return subprocess.CompletedProcess(cmd, self.returncode, "", self.stderr)
        if exe == "node":
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


def broken(monkeypatch, **kw):
    f = FakeRun(**kw)
    monkeypatch.setattr(R.subprocess, "run", f)
    monkeypatch.setattr(R.shutil, "which", lambda n: "/usr/bin/" + n)
    return f


# --- fixtures on disk ----------------------------------------------------------------


def clean_beat(**over):
    beat = {
        "type": "statement",
        "hold": 3.0,
        "text": "DeepSeek's flagship is a 1.6T MoE model.",
        "src": "local-ai-zone",
        "quote": "DeepSeek's 1.6T MoE flagship quietly moved from preview",
    }
    beat.update(over)
    return beat


def fabricated_beat(**over):
    beat = {
        "type": "statement",
        "hold": 3.0,
        "text": "DeepSeek's old price was $0.11 per 1M tokens.",
        "src": "local-ai-zone",
        "quote": "announced new pricing starting August 16",
    }
    beat.update(over)
    return beat


def write_script(ep, beats, status="in_review"):
    # The id is QUOTED: `episode: 2026-08-17` unquoted is a YAML date.
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f"---\nepisode: '{ep.id}'\nseries: the-brief\nstatus: {status}\n---\n{body}",
        encoding="utf-8",
    )


def episode(series, beats=None, sources=None, ep_id=EP, status="in_review"):
    ep = create_episode(series, ep_id)
    for key, text in (sources or {"local-ai-zone": SOURCE}).items():
        corpus.write_document(
            ep, text, url=f"https://{key}.example/x", key=key, fetched_at="2026-08-17"
        )
    write_script(ep, beats or [clean_beat(), clean_beat()], status=status)
    return load_episode(series, ep_id)


def edit_beats(series, beats, ep_id=EP):
    """Change the beats and NOTHING else.

    `write_script` rewrites the whole file, which wipes the approval record —
    and "no approval on record" is a different drift from "the beats moved".
    The bug this file is pinning is an edit to an episode that is still, on
    disk, approved by a named human.
    """
    path = series.episodes_dir / ep_id / "script.yaml"
    head, sep, _ = path.read_text(encoding="utf-8").partition("\n---\n")
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    path.write_text(head + sep + body, encoding="utf-8")


def force_status_on_disk(series, status, ep_id=EP):
    """Set the status by editing the file, which is what a SIGKILL leaves behind
    and what no supported command can do."""
    path = series.episodes_dir / ep_id / "script.yaml"
    text = path.read_text(encoding="utf-8")
    before = status_on_disk(series, ep_id)
    assert f"status: {before}" in text
    path.write_text(text.replace(f"status: {before}", f"status: {status}", 1), "utf-8")


def check(ep_id=EP):
    return run("video", "check", ep_id, "--series", "the-brief")


def approve(ep_id=EP, by=BY):
    return run("video", "approve", ep_id, "--series", "the-brief", "--by", by)


def render(*extra, ep_id=EP):
    return run("video", "render", ep_id, "--series", "the-brief", *extra)


def status_on_disk(series, ep_id=EP):
    """Read the status back from the FILE, never from a loaded object."""
    meta, _, _ = read_script(series.episodes_dir / ep_id / "script.yaml")
    return meta.get("status")


def meta_on_disk(series, ep_id=EP):
    meta, _, _ = read_script(series.episodes_dir / ep_id / "script.yaml")
    return meta


def approved(series, ep_id=EP, **kw):
    """An episode that is approved, undrifted, and checked against a fresh corpus."""
    ep = episode(series, ep_id=ep_id, **kw)
    assert check(ep_id).exit_code == 0
    assert approve(ep_id).exit_code == 0, "the fixture must actually be approvable"
    return ep


# --- R1: only an approved, undrifted episode with a current ledger renders ------------


def test_an_approved_undrifted_episode_renders(series, fake):
    """The positive half. A gate that refuses everything kills M1-M3 and is useless."""
    approved(series)
    result = render()
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "rendered"
    assert (series.episodes_dir / EP / "out" / "vertical-1080x1920.mp4").is_file()


def test_an_unapproved_episode_does_not_render(series, fake):
    """M1. `in_review` is one status away from approved and must not render."""
    episode(series)
    result = render()
    assert result.exit_code == 1, result.output
    assert "in_review" in result.output
    assert status_on_disk(series) == "in_review"
    assert fake.calls == []


def test_a_draft_does_not_render(series, fake):
    """M1. The status furthest from the gate, in case the check reads `!= approved`
    off the wrong end."""
    episode(series, status="draft")
    result = render()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "draft"
    assert fake.calls == []


def test_a_drifted_episode_does_not_render(series, fake):
    """M2. An edit after approval, which §10 exists to catch: the approval is
    still on the file and still says `approved`."""
    approved(series)
    edit_beats(series, [clean_beat(), clean_beat(text="Something else entirely.")])
    result = render()
    assert result.exit_code == 1, result.output
    assert "sha256" in result.output
    assert status_on_disk(series) == "approved"
    assert fake.calls == []


def test_a_design_change_after_approval_does_not_render(series, fake):
    """M2, the half D-115 found: `series.toml` repaints every frame and lives in
    a file nothing about editing feels like touching an approved episode."""
    approved(series)
    toml = series.dir / "series.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace("#2E6BFF", "#12A150"), encoding="utf-8"
    )
    result = render()
    assert result.exit_code == 1, result.output
    assert "series.toml" in result.output
    assert status_on_disk(series) == "approved"
    assert fake.calls == []


def test_a_stale_corpus_does_not_render(series, fake):
    """M3. The claims were checked against bytes that no longer exist."""
    approved(series)
    corpus.write_document(
        load_episode(series, EP),
        SOURCE + " A sentence nobody checked.",
        url="https://local-ai-zone.example/x",
        key="local-ai-zone",
        fetched_at="2026-08-18",
        replace=True,
    )
    result = render()
    assert result.exit_code == 1, result.output
    assert "corpus" in result.output
    assert status_on_disk(series) == "approved"
    assert fake.calls == []


def test_a_missing_ledger_does_not_render(series, fake):
    """M3. `check` deleted, approval intact — nothing verifies these sentences."""
    approved(series)
    (series.episodes_dir / EP / "claims.json").unlink()
    result = render()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "approved"
    assert fake.calls == []


# --- R1 negative: the three refusals are DISTINGUISHABLE ------------------------------


def _three_refusals(series):
    """The three refusals, as text, with the episode id normalised away.

    Without the normalisation the screens differ because they name different
    episodes, and a test comparing them would pass on three identical messages.
    """
    out = {}

    episode(series, ep_id="ep-status")
    out["status"] = render(ep_id="ep-status").output.replace("ep-status", "<ep>")

    approved(series, ep_id="ep-drift")
    edit_beats(series, [clean_beat(text="Moved.")], ep_id="ep-drift")
    out["drift"] = render(ep_id="ep-drift").output.replace("ep-drift", "<ep>")

    approved(series, ep_id="ep-stale")
    (series.episodes_dir / "ep-stale" / "claims.json").unlink()
    out["ledger"] = render(ep_id="ep-stale").output.replace("ep-stale", "<ep>")
    return out


def test_the_three_refusals_are_three_different_screens(series, fake):
    """M4. Three failures with one message is a render that refuses correctly and
    tells the operator nothing about which of three files to open."""
    screens = _three_refusals(series)
    assert len(set(screens.values())) == 3, screens


def test_each_refusal_names_the_file_the_operator_must_open(series, fake):
    """M4. The distinction is not cosmetic: status is `agsoc video approve`,
    drift is `script.yaml`/`series.toml`, staleness is `agsoc video check`."""
    screens = _three_refusals(series)
    assert "approve" in screens["status"]
    assert "sha256" in screens["drift"]
    assert "check" in screens["ledger"]
    # and each says only its own thing
    assert "sha256" not in screens["status"]
    assert "sha256" not in screens["ledger"]


def test_the_gate_calls_three_named_checks(series):
    """M5, D-113. Folding them into one predicate rebuilds the two-paths-to-one-
    answer shape Phase 7 spent three tasks eliminating. Read off the AST, not
    off a comment."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(R.render_episode)))
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", None))
    assert {"assert_transition", "approval_drift", "stale_reason"} <= called


def test_the_gate_loads_what_it_gates(series):
    """D-072. There must be no argument a caller can shape to change the verdict."""
    params = inspect.signature(R.render_episode, eval_str=True).parameters
    forbidden = {"script", "ledger", "claims", "episode", "series", "plan", "records"}
    assert forbidden.isdisjoint(params)


def test_render_offers_no_way_to_skip_the_gate(ws):
    """M1-M3's CLI half — a flag is an argument a caller can shape."""
    result = run("video", "render", "--help")
    assert result.exit_code == 0
    for flag in ("--force", "--skip", "--no-check", "--script", "--ledger"):
        assert flag not in result.output


# --- R2: a crash leaves a recoverable state ------------------------------------------


def test_a_renderer_crash_leaves_the_episode_failed(series, monkeypatch):
    """M6. `rendering` forever is the video analogue of a half-posted thread."""
    approved(series)
    broken(monkeypatch, fail_on="node", stderr="page errors: ReferenceError")
    result = render()
    assert result.exit_code == 1, result.output
    assert "ReferenceError" in result.output
    assert status_on_disk(series) == "failed"


def test_an_ffmpeg_crash_leaves_the_episode_failed(series, monkeypatch):
    """M6, the second subprocess. Frames rendered, encode died."""
    approved(series)
    broken(monkeypatch, fail_on="ffmpeg", stderr="Invalid data found")
    result = render()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "failed"


def test_an_interrupt_mid_render_leaves_the_episode_failed(ws, series, monkeypatch):
    """M6. Ctrl-C is not an exception the `except Exception` habit catches, and
    it is the most likely way a fourteen-minute render ends early.

    Driven through the module rather than the CLI on purpose: click turns a
    KeyboardInterrupt into `Abort` inside `main()`, so the runner would report
    a clean exit 1 and the test would be pinning click's handler instead of
    this one."""
    approved(series)
    broken(monkeypatch, fail_on="node", raises=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        R.render_episode(ws, "the-brief", EP)
    assert status_on_disk(series) == "failed"


def test_a_failed_render_records_why(series, monkeypatch):
    """R2. `failed` with no account of what failed sends the operator back to a
    terminal they have already closed."""
    approved(series)
    broken(monkeypatch, fail_on="ffmpeg", stderr="Invalid data found")
    render()
    record = meta_on_disk(series).get("render")
    assert isinstance(record, dict)
    assert "Invalid data" in json.dumps(record)


def test_a_failed_render_can_be_retried(series, monkeypatch, fake):
    """M7. §10 draws `failed → rendering` and it must be reachable from the CLI
    — a status escapable only by hand-editing a file on disk is a bug."""
    approved(series)
    broken(monkeypatch, fail_on="node", stderr="boom")
    assert render().exit_code == 1
    assert status_on_disk(series) == "failed"

    monkeypatch.setattr(R.subprocess, "run", fake)
    result = render()
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "rendered"


def test_a_retry_still_passes_all_three_checks(series, monkeypatch, fake):
    """M7's negative. `failed → rendering` must not be a way around the gate."""
    approved(series)
    broken(monkeypatch, fail_on="node", stderr="boom")
    assert render().exit_code == 1

    edit_beats(series, [clean_beat(text="Moved.")])
    monkeypatch.setattr(R.subprocess, "run", fake)
    result = render()
    assert result.exit_code == 1, result.output
    assert "sha256" in result.output
    assert status_on_disk(series) == "failed"


def test_a_killed_render_can_be_recovered_without_editing_a_file(series, fake):
    """M6. SIGKILL and power loss run no handler, so `rendering` on disk with no
    live process is a state the CLI has to be able to leave."""
    approved(series)
    force_status_on_disk(series, "rendering")
    refused = render()
    assert refused.exit_code == 1, refused.output
    assert "--restart" in refused.output
    assert status_on_disk(series) == "rendering"

    result = render("--restart")
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "rendered"


def test_restart_does_not_skip_the_gate(series, fake):
    """M1-M3 through the recovery door. `--restart` answers the status question
    only; drift and staleness are still asked."""
    approved(series)
    edit_beats(series, [clean_beat(text="Moved.")])
    force_status_on_disk(series, "rendering")
    result = render("--restart")
    assert result.exit_code == 1, result.output
    assert "sha256" in result.output
    assert status_on_disk(series) in ("rendering", "failed")
    assert fake.calls == []


def test_rendered_is_terminal(series, fake):
    """R2 negative, D-006. A second render of a finished episode is refused, not
    silently repeated."""
    approved(series)
    assert render().exit_code == 0
    result = render()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "rendered"


def test_render_writes_status_only_through_set_status(series):
    """M8, D-059. Enumerated rather than asserted: every status write in this
    module must be the gated one, so there is no second writer to launder a
    bypass through."""
    src = inspect.getsource(R)
    assert "atomic_write" not in src
    assert "write_text" not in src
    assert 'meta["status"]' not in src


# --- R3: timing stays in Python -------------------------------------------------------


def test_node_is_handed_a_plan_and_an_output_directory_and_nothing_else(series, fake):
    """M9, D-007. Every timing flag `render.mjs` accepts is arithmetic Node would
    then be doing; the plan already carries the answer."""
    approved(series)
    render()
    node = [c for c in fake.calls if Path(c[0]).name == "node"][0]
    assert "--plan" in node and "--out" in node
    for timing in ("--pace", "--at", "--day", "--fps"):
        assert timing not in node


def test_the_plan_carries_the_resolved_frame_count(series, fake):
    """M9. If the plan did not resolve it, something downstream would have to."""
    approved(series)
    render()
    plan = json.loads(
        (series.episodes_dir / EP / "out" / "plan-vertical.json").read_text("utf-8")
    )
    assert plan["fps"] == 30
    assert plan["total_frames"] == round(plan["total_sec"] * plan["fps"])
    assert all("start_frame" in b and "end_frame" in b for b in plan["beats"])


def test_the_renderer_takes_its_frame_count_from_the_plan(series):
    """M9. `render.mjs` recomputing `total * FPS` is a second answer to a
    question the plan already answered — the D-036 pattern, in the one place
    where disagreeing with Python means a truncated video."""
    src = (Path(R.ENGINE_DIR) / "render.mjs").read_text(encoding="utf-8")
    assert "plan.total_frames" in src
    assert "plan.fps" in src


# --- R4: the MP4 lands somewhere stated and findable -----------------------------------


def test_the_mp4_lands_in_the_episodes_out_directory(series, fake):
    """M10, R4. `engine/` is a gitignored working area; a file there is a file
    nobody finds in a month and `git clean` deletes."""
    approved(series)
    before = set(Path(R.ENGINE_DIR).rglob("*.mp4"))
    result = render()
    mp4 = series.episodes_dir / EP / "out" / "vertical-1080x1920.mp4"
    assert mp4.is_file()
    assert set(Path(R.ENGINE_DIR).rglob("*.mp4")) == before
    assert str(mp4) in result.output


def test_no_frames_are_left_behind_anywhere_in_the_workspace(series, ws, fake):
    """R4. ~2.5 GB per episode (spec §5). Frames are intermediate, and the spec
    puts them outside `workspace/` entirely."""
    approved(series)
    render()
    assert not list(Path(ws.root).rglob("*.png"))


def test_the_render_is_recorded_in_the_script(series, fake):
    """R4. "somewhere stated" means stated in the artifact, not in scrollback."""
    approved(series)
    render()
    record = meta_on_disk(series)["render"]
    assert record["file"].endswith("vertical-1080x1920.mp4")
    assert record["format"] == "vertical"
    assert record["script_file_sha256"]


# --- R5: the success message does not claim the pixels were approved -------------------


def test_the_success_message_names_what_the_approval_does_not_cover(series, fake):
    """M11, D-116. A font substitution changes every frame with all three checks
    green, so a message that stops at "approved" has told the operator something
    false by omission. The resolved font is the one that differs between
    machines and it is named."""
    approved(series)
    out = render().output
    assert "font" in out
    for renderer in ("engine.js", "Chromium", "ffmpeg"):
        assert renderer in out


def test_the_success_message_does_not_claim_the_frames_were_seen(series, fake):
    """M11. The overclaim has landed on the summary line four times (D-106,
    D-110, D-112, D-113) because the summary is written last, by someone who
    already knows the answer."""
    approved(series)
    out = render().output.lower()
    for claim in (
        "what the approver saw",
        "this is what was approved",
        "approved output",
        "verified frames",
        "the approved video",
    ):
        assert claim not in out


def test_the_success_message_says_what_IS_true(series, fake):
    """M11's negative. Refusing to overclaim by saying nothing is its own defect:
    the three checks did pass and the operator is entitled to be told so."""
    approved(series)
    out = render().output
    assert "approved" in out
    assert BY in out


# --- R6: no test renders a full episode ------------------------------------------------


def test_the_render_fixture_is_seconds_not_minutes(series):
    """M12. ~230 ms/frame: a 120 s episode is fourteen minutes of test suite."""
    from agenticsocial.video.plan import build_plan

    ep = episode(series)
    plan = build_plan(series, ep)
    assert plan["total_sec"] <= 10


def test_no_test_launches_the_real_toolchain(series):
    """M12. Every render test fakes `subprocess.run`. This pins the shapes that
    would bypass the fake: spawning the renderer directly, or driving Chromium
    from Python. It is a shallow check — the load-bearing guarantee is that
    every test in this file and in test_video_render.py patches
    `render.subprocess.run` — so the suite's wall-clock is reported alongside
    it, and 1.7k tests in ~18s is what a suite that renders nothing looks
    like."""
    # Assembled rather than written whole: a literal here is a literal in a test
    # file, and this test reads test files.
    mjs, pw = "render" + ".mjs", "play" + "wright"
    forbidden = (
        f'"node", "{mjs}"',
        f"'node', '{mjs}'",
        f"import {pw}",
        f"from {pw}",
        "chromium" + ".launch",
    )
    for path in Path(__file__).parent.glob("test_*.py"):
        src = path.read_text(encoding="utf-8")
        for bad in forbidden:
            assert bad not in src, f"{path} may launch a real render: {bad}"


# --- the questions the plan asked to be decided, not defaulted --------------------------


def test_render_does_not_re_run_check(series, fake):
    """The ledger is the artifact of record and the screen the human read before
    signing — the same argument `approve` makes. Computing a second set of
    verdicts inside `render` is two paths to one answer with only one of them
    ever displayed (D-113)."""
    approved(series)
    before = (series.episodes_dir / EP / "claims.json").read_bytes()
    render()
    assert (series.episodes_dir / EP / "claims.json").read_bytes() == before


def test_render_does_not_rewrite_the_beats(series, fake):
    """`script_sha256` is bytes. A render that reflows the beats invalidates the
    approval it just acted on."""
    approved(series)
    _, beats_before, _ = read_script(series.episodes_dir / EP / "script.yaml")
    render()
    _, beats_after, _ = read_script(series.episodes_dir / EP / "script.yaml")
    assert beats_after == beats_before


def test_an_unsupported_format_is_refused_before_anything_moves(series, fake):
    """§9 lists `wide`; `plan.FORMATS` does not implement it yet. Refuse, and do
    not spend the gate on it."""
    approved(series)
    result = render("--format", "wide")
    assert result.exit_code == 1, result.output
    assert "wide" in result.output
    assert status_on_disk(series) == "approved"
    assert fake.calls == []


def test_a_missing_toolchain_is_reported_before_the_gate_is_spent(series, monkeypatch):
    """ffmpeg absent must not cost an approved episode its status."""
    monkeypatch.setattr(R.shutil, "which", lambda n: None if n == "ffmpeg" else "/x/" + n)
    approved(series)
    result = render()
    assert result.exit_code == 1, result.output
    assert "ffmpeg" in result.output
    assert status_on_disk(series) == "approved"


def test_a_missing_episode_is_a_clean_error(ws, series):
    result = render(ep_id="nope")
    assert result.exit_code == 1, result.output
    assert "nope" in result.output


def test_the_episode_id_is_matched_exactly(series, fake):
    """`resolve_episode`'s substring match is right for `review`, which shows you
    what it found, and wrong here, where the thing it might find is a render of
    an episode you did not name."""
    approved(series)
    result = render(ep_id="2026")
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "approved"

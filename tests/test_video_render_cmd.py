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
import re
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


def _fix_line(screen: str) -> str:
    """The `fix` block of a refusal screen, as one squashed line.

    Read off the rendered screen rather than off the source, because the thing
    that has to differ is what the operator reads, and `_detail` wraps it.
    """
    marker = f"\n      {'fix':<9}"
    assert marker in screen, f"no fix line on this screen:\n{screen}"
    return " ".join(screen.split(marker, 1)[1].split())


def test_each_refusal_offers_its_own_fix(series, fake):
    """M4, the half the first version of this file missed.

    Collapsing the three screens into one framing SURVIVED the distinctness
    check above, because the underlying reasons still read differently — the
    `why` line comes from `approval_drift` and `stale_reason` and those were
    always going to differ. What collapsed was the FIX line, which is the half
    an operator acts on, and it was pointing every refusal at `--restart`.

    And the FIX lines are compared to EACH OTHER, not searched for a phrase.
    The phrase version of this test also survived: it asserted "put the change
    back" was in the drift screen, and that sentence is `approval_drift`'s own
    wording — it arrives on the `why` line whatever the `fix` line says, so the
    drift and ledger remedies could be made identical with this test green.
    Measured, as a mutant, before this version was written.
    """
    screens = _three_refusals(series)
    # The status refusal is one sentence and carries its remedy inline; the two
    # that print a `fix` block are the pair that can collapse into each other.
    fixes = {k: _fix_line(screens[k]) for k in ("drift", "ledger")}
    assert fixes["drift"] != fixes["ledger"], fixes
    assert "put the change back" in fixes["drift"]
    assert "agsoc video check" in fixes["ledger"]
    assert "agsoc video approve" in screens["status"]
    assert "agsoc video approve" not in screens["drift"] + screens["ledger"]
    for other in ("drift", "ledger", "status"):
        assert "--restart" not in screens[other], other


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


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def help_text(*args):
    """`--help` with the ANSI stripped and the whitespace squashed.

    Rich renders a flag as `ESC[1;36m-ESC[0mESC[1;36m-forceESC[0m`, so the
    literal string `--force` NEVER appears in `result.output` — and every
    `assert "--force" not in result.output` in this file was therefore
    unfailable. Measured during Phase 13 Task 1 by adding a `--force` flag to
    `video render`: the assertion below stayed green. It also wraps inside a
    box, so a long help string is split across lines.
    """
    result = run(*args, "--help")
    assert result.exit_code == 0
    return " ".join(ANSI.sub("", result.output).split())


def test_render_offers_no_way_to_skip_the_gate(ws):
    """M1-M3's CLI half — a flag is an argument a caller can shape."""
    text = help_text("video", "render")
    for flag in ("--force", "--skip", "--no-check", "--script", "--ledger"):
        assert flag not in text


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


def test_a_finished_episode_is_not_re_rendered_by_accident(series, fake):
    """R2 negative. Every enabled format is already on disk, so there is nothing
    to do and a success screen would be a lie.

    This test used to assert the word "terminal" — Phase 13 Task 1. `rendered`
    being terminal was D-006's *consequence*, not its purpose, and it made
    `--format wide` unreachable on the one episode most likely to want it. What
    protects the artifact is not the status machine, it is that an existing file
    is never replaced without the operator saying so.
    """
    approved(series)
    assert render().exit_code == 0
    result = render()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "rendered"
    assert "--replace" in result.output
    # And it must not send them to `approve`, which would refuse them for a
    # second reason. A fix line that names the wrong command costs the reader
    # the only thing the message was trying to give them.
    assert "agsoc video approve" not in result.output


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


def _frames_dir(fake):
    node = [c for c in fake.calls if Path(c[0]).name == "node"][0]
    return Path(node[node.index("--out") + 1])


def test_the_frames_are_deleted_after_the_encode(series, fake):
    """R4. ~2.5 GB per episode. They live outside `workspace/` (spec §5), which
    is exactly why the workspace check above cannot see them leak — this one
    follows the directory the renderer was actually given."""
    approved(series)
    render()
    assert not _frames_dir(fake).exists()


def test_the_frames_are_deleted_when_the_render_fails(series, monkeypatch):
    """The same, on the path where the disk is likeliest to be the problem."""
    approved(series)
    f = broken(monkeypatch, fail_on="ffmpeg", stderr="No space left on device")
    assert render().exit_code == 1
    assert not _frames_dir(f).exists()


def test_the_render_is_recorded_in_the_script(series, fake):
    """R4. "somewhere stated" means stated in the artifact, not in scrollback."""
    approved(series)
    render("--format", "vertical")
    record = meta_on_disk(series)["render"]
    assert record["file"] == "out/vertical-1080x1920.mp4"
    # Relative to the episode, not absolute: a committed artifact that names
    # `/Users/someone/...` is a lie the moment the workspace moves, and it
    # names the machine it was rendered on to anyone who reads the file.
    assert not Path(record["file"]).is_absolute()
    assert (series.episodes_dir / EP / record["file"]).is_file()
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
    """§9 lists two formats and Phase 10 ships both. A THIRD name is refused,
    and the gate is not spent on it — an approved episode must not come out of a
    typo as `failed`."""
    approved(series)
    result = render("--format", "square")
    assert result.exit_code == 1, result.output
    assert "square" in result.output
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


# --- Phase 13 Task 1: one approval renders every format --------------------------------
#
# The defect, against the operator's own episode:
#
#     $ agsoc video render 2026-08-18 --series the-brief --format wide
#     NOT rendered — cannot move rendered -> rendering; allowed next: none (terminal).
#
# while the success screen the same command had printed minutes earlier said
# "one approval renders every format". Spec §9 documents both `render <ep>`
# (every enabled format) and `--format wide` (one); neither worked after the
# first render, and `[formats] enabled` in series.toml was read by nothing but
# the list screen.
#
# The mutant table is in the Phase 13 Task 1 brief. Every test below names its
# mutant, and every refusal also asserts the status ON DISK did not move and
# that no subprocess ran (D-059).

VERTICAL = "vertical-1080x1920.mp4"
WIDE = "wide-1920x1080.mp4"
SENTINEL = b"the bytes of the render that already existed"


def out_file(series, name, ep_id=EP):
    return series.episodes_dir / ep_id / "out" / name


def set_enabled(series, formats):
    """Rewrite `[formats] enabled`, and NOTHING else.

    `[formats]` is not one of the series values `build_plan` reads, so this is
    deliberately not a drift-triggering edit — which is what makes it a fair
    test of the enabled list rather than of the drift check.
    """
    toml = series.dir / "series.toml"
    text = toml.read_text(encoding="utf-8")
    old = 'enabled = ["vertical", "wide"]'
    assert old in text, text
    new = "enabled = [" + ", ".join(f'"{f}"' for f in formats) + "]"
    toml.write_text(text.replace(old, new, 1), encoding="utf-8")


def encoded(fake, since=0):
    """The basenames ffmpeg was asked to write, from `since` onward.

    Read off the calls rather than off the output directory: a format that is
    correctly skipped and a format that is re-rendered to identical bytes look
    the same on disk, and the thing under test is whether the work was done.
    """
    return [
        Path(c[-1]).name for c in fake.calls[since:] if Path(c[0]).name == "ffmpeg"
    ]


def flat(result):
    return " ".join(result.output.split())


# --- R1: a format the episode has not produced yet -------------------------------------


def test_a_rendered_episode_renders_a_format_it_has_not_produced(series, fake):
    """M1. The defect itself. `rendered` describes the story — verified,
    approved, committed to — and a second format is a second artifact from the
    same signed bytes, not a second story."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    result = render("--format", "wide")
    assert result.exit_code == 0, result.output
    assert out_file(series, WIDE).is_file()
    assert out_file(series, VERTICAL).is_file(), "the first format must survive"
    assert status_on_disk(series) == "rendered"


def test_a_drifted_rendered_episode_renders_no_second_format(series, fake):
    """M2 — the dangerous one. A second format is only safe BECAUSE the script
    is provably unchanged since approval; an implementation that reaches the new
    edge by loosening the drift check inverts the point of the gate."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    edit_beats(series, [clean_beat(), clean_beat(text="Something else entirely.")])
    n = len(fake.calls)
    result = render("--format", "wide")
    assert result.exit_code == 1, result.output
    assert "sha256" in result.output
    assert not out_file(series, WIDE).exists()
    assert status_on_disk(series) == "rendered"
    assert fake.calls[n:] == []


def test_a_design_change_after_rendering_blocks_the_second_format(series, fake):
    """M2, D-115's half: `series.toml` repaints every frame, and the wide cut is
    exactly where an operator would be tempted to "just adjust the accent"."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    toml = series.dir / "series.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace("#2E6BFF", "#12A150"), encoding="utf-8"
    )
    n = len(fake.calls)
    result = render("--format", "wide")
    assert result.exit_code == 1, result.output
    assert "series.toml" in result.output
    assert not out_file(series, WIDE).exists()
    assert status_on_disk(series) == "rendered"
    assert fake.calls[n:] == []


def test_a_stale_corpus_blocks_the_second_format(series, fake):
    """M3. The ledger no longer describes the bytes it was computed from, and
    that is as true for the wide cut as for the vertical one."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    corpus.write_document(
        load_episode(series, EP),
        SOURCE + " A sentence nobody checked.",
        url="https://local-ai-zone.example/x",
        key="local-ai-zone",
        fetched_at="2026-08-18",
        replace=True,
    )
    n = len(fake.calls)
    result = render("--format", "wide")
    assert result.exit_code == 1, result.output
    assert "corpus" in result.output
    assert not out_file(series, WIDE).exists()
    assert status_on_disk(series) == "rendered"
    assert fake.calls[n:] == []


def test_a_missing_ledger_blocks_the_second_format(series, fake):
    """M3. `check` deleted after the first render: nothing verifies these
    sentences any more, whatever the episode's status says."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    (series.episodes_dir / EP / "claims.json").unlink()
    n = len(fake.calls)
    result = render("--format", "wide")
    assert result.exit_code == 1, result.output
    assert not out_file(series, WIDE).exists()
    assert status_on_disk(series) == "rendered"
    assert fake.calls[n:] == []


def test_an_unapproved_episode_still_renders_nothing_in_any_format(series, fake):
    """M2/M1's floor. The new edge starts at `rendered`, and nothing about it
    may make an unapproved episode reachable — in either format."""
    episode(series)
    for extra in (("--format", "wide"), ("--format", "vertical"), ()):
        result = render(*extra)
        assert result.exit_code == 1, result.output
        assert status_on_disk(series) == "in_review"
    assert fake.calls == []
    assert not list((series.episodes_dir / EP / "out").glob("*.mp4"))


# --- R2: `[formats] enabled` is the list, and it is read -------------------------------


def test_render_with_no_format_renders_every_enabled_format(series, fake):
    """M4. Spec §9: `agsoc video render <ep>` is documented as every enabled
    format. It rendered the default one and printed a screen claiming the
    other."""
    approved(series)
    result = render()
    assert result.exit_code == 0, result.output
    assert out_file(series, VERTICAL).is_file()
    assert out_file(series, WIDE).is_file()
    assert "vertical" in result.output and "wide" in result.output


def test_no_format_renders_only_the_formats_the_series_enabled(series, fake):
    """M4's negative. A series that has turned `wide` off must not get one."""
    set_enabled(series, ["vertical"])
    approved(series)
    result = render()
    assert result.exit_code == 0, result.output
    assert out_file(series, VERTICAL).is_file()
    assert not out_file(series, WIDE).exists()
    assert encoded(fake) == [VERTICAL]


def test_a_format_the_series_has_not_enabled_is_refused_by_name(series, fake):
    """M5. `wide` is a format the engine supports and this series does not, and
    the refusal has to say which of the two it is — "unsupported format" would
    send the operator to plan.py instead of to series.toml."""
    set_enabled(series, ["vertical"])
    approved(series)
    result = render("--format", "wide")
    assert result.exit_code == 1, result.output
    assert "wide" in result.output
    assert "series.toml" in result.output or "enabled" in result.output
    assert "vertical" in result.output, "name the list they could have chosen from"
    assert status_on_disk(series) == "approved", "a typo must not spend the gate"
    assert fake.calls == []
    assert not out_file(series, WIDE).exists()


def test_the_enabled_list_is_read_from_the_series_not_from_a_constant(series, fake):
    """M5. `enabled = ["wide"]` renders wide and only wide — the mutant that
    hard-codes plan.FORMATS passes the test above and fails this one."""
    set_enabled(series, ["wide"])
    approved(series)
    result = render()
    assert result.exit_code == 0, result.output
    assert encoded(fake) == [WIDE]
    assert not out_file(series, VERTICAL).exists()


# --- R3: replacing an existing file is explicit ----------------------------------------


def test_an_existing_file_is_not_silently_replaced(series, fake):
    """M6. The operator's vertical cut is 18 MB and thirteen minutes; a command
    that quietly overwrites it has spent both without asking."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    out_file(series, VERTICAL).write_bytes(SENTINEL)
    n = len(fake.calls)
    result = render("--format", "vertical")
    assert result.exit_code == 1, result.output
    assert VERTICAL in result.output
    assert "--replace" in result.output
    assert out_file(series, VERTICAL).read_bytes() == SENTINEL
    assert fake.calls[n:] == []
    assert status_on_disk(series) == "rendered"


def test_replace_re_renders_the_existing_file(series, fake):
    """M6's positive half. Refusing forever is its own defect: an engine fix is
    exactly the reason to re-render an approved, undrifted episode."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    out_file(series, VERTICAL).write_bytes(SENTINEL)
    result = render("--format", "vertical", "--replace")
    assert result.exit_code == 0, result.output
    assert out_file(series, VERTICAL).read_bytes() != SENTINEL
    assert status_on_disk(series) == "rendered"


def test_replace_says_which_file_it_replaced(series, fake):
    """M6. "Explicit" is not only the flag: the screen has to state that the
    file the operator had is gone."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    result = render("--format", "vertical", "--replace")
    assert result.exit_code == 0, result.output
    assert "replaced" in flat(result).lower()
    assert VERTICAL in result.output


def test_the_default_run_renders_what_is_missing_and_names_what_it_kept(series, fake):
    """M6 + M4 together, and the shape the operator's episode is actually in:
    vertical on disk, wide never rendered. The wide cut must be produced and the
    18 MB file must not be touched — and the screen must say so, because a
    silent skip is the same overclaim from the other direction."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    out_file(series, VERTICAL).write_bytes(SENTINEL)
    n = len(fake.calls)
    result = render()
    assert result.exit_code == 0, result.output
    assert encoded(fake, n) == [WIDE]
    assert out_file(series, VERTICAL).read_bytes() == SENTINEL
    assert out_file(series, WIDE).is_file()
    assert VERTICAL in result.output and "--replace" in result.output
    assert status_on_disk(series) == "rendered"


def test_a_run_with_nothing_left_to_do_refuses_rather_than_claiming_success(series, fake):
    """M6. Exit 0 with a screen listing two files it did not make is the
    overclaim pattern in its purest form."""
    approved(series)
    assert render().exit_code == 0
    n = len(fake.calls)
    result = render()
    assert result.exit_code == 1, result.output
    assert "--replace" in result.output
    assert fake.calls[n:] == []
    assert status_on_disk(series) == "rendered"


# --- R4: no new way to reach `rendering` that skips a gate -----------------------------


def test_a_second_format_still_passes_through_rendering(series, fake, monkeypatch):
    """M7. The proof that the second format is a TRANSITION and not a side door:
    a crash mid-way leaves `failed`, which is reachable only from `rendering`.
    An implementation that renders without the status write cannot produce this
    — the episode would still read `rendered` with no artifact."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    broken(monkeypatch, fail_on="ffmpeg", stderr="Invalid data found")
    result = render("--format", "wide")
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "failed"


def test_that_failure_recovers_without_re_rendering_the_first_format(series, monkeypatch, fake):
    """M7. §10's `failed -> rendering` is the retry, and it must not charge the
    operator thirteen minutes for the format that already succeeded."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    out_file(series, VERTICAL).write_bytes(SENTINEL)
    broken(monkeypatch, fail_on="ffmpeg", stderr="Invalid data found")
    assert render("--format", "wide").exit_code == 1
    assert status_on_disk(series) == "failed"

    monkeypatch.setattr(R.subprocess, "run", fake)
    n = len(fake.calls)
    result = render()
    assert result.exit_code == 0, result.output
    assert encoded(fake, n) == [WIDE]
    assert out_file(series, VERTICAL).read_bytes() == SENTINEL
    assert status_on_disk(series) == "rendered"


def test_only_two_functions_write_a_status_key():
    """M7, D-059, and Phase 7's R5 enumeration re-run as a test rather than as a
    paragraph in a report.

    D-059's root cause was a SECOND, ungated status writer: `save_variant`
    stamped `publishing` onto a draft and the closing `set_status(PUBLISHED)`
    then passed legitimately. So the property is not "the gate is checked" — it
    is that the set of functions able to write the key is closed, enumerated
    from the AST of everything under `src/`, and each member is gated.

    `save_variant` is the third, and it is here deliberately: it writes the
    status it just READ FROM DISK, which is the fix D-059 shipped. If it ever
    writes a caller-supplied value again, the `disk_status` assertion below
    fails.
    """
    src_root = Path(R.__file__).resolve().parent.parent
    writers = {}
    for path in sorted(src_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AugAssign):
                    targets = [node.target]
                for t in targets:
                    if (
                        isinstance(t, ast.Subscript)
                        and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "status"
                    ):
                        key = (path.name, fn.name)
                        writers[key] = ast.dump(node) + "|" + ast.unparse(fn)
    assert set(writers) == {
        ("episode.py", "set_status"),
        ("workspace.py", "set_status"),
        ("workspace.py", "save_variant"),
    }, sorted(writers)
    for name in ("set_status",):
        for module in ("episode.py", "workspace.py"):
            assert "assert_transition" in writers[(module, name)], module
    # The one writer that is not a gate writes what disk already says.
    save = writers[("workspace.py", "save_variant")]
    assert "disk_status" in save
    assert "assert_transition" not in save


def test_the_new_edge_is_the_only_change_to_the_video_table(series):
    """M7. `rendered -> rendering` is one edge. A table opened up more widely
    than that — `rendered -> approved`, say — would let a re-approval launder an
    edit past the drift check."""
    from agenticsocial.models import VIDEO_TRANSITIONS, Status

    assert VIDEO_TRANSITIONS[Status.RENDERED] == {Status.RENDERING}
    assert VIDEO_TRANSITIONS[Status.APPROVED] == {Status.IN_REVIEW, Status.RENDERING}
    assert VIDEO_TRANSITIONS[Status.FAILED] == {Status.RENDERING}
    assert VIDEO_TRANSITIONS[Status.RENDERING] == {Status.RENDERED, Status.FAILED}


def test_render_still_offers_no_way_to_skip_the_gate(ws):
    """M7. `--replace` is a decision about a FILE. It must not become a decision
    about the approval — the flags that would do that are still absent."""
    text = help_text("video", "render")
    for flag in ("--force", "--skip", "--no-check", "--script", "--ledger"):
        assert flag not in text


def test_replace_does_not_skip_the_gate(series, fake):
    """M2 through the new door. `--replace` answers "may this file be
    overwritten"; it answers nothing about drift."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    edit_beats(series, [clean_beat(text="Moved.")])
    n = len(fake.calls)
    result = render("--format", "vertical", "--replace")
    assert result.exit_code == 1, result.output
    assert "sha256" in result.output
    assert fake.calls[n:] == []
    assert status_on_disk(series) == "rendered"


# --- R5: the message's claims are true -------------------------------------------------


def test_the_success_screens_promise_is_executable(series, fake):
    """M8. The screen says "one approval renders every format". The test does
    not check the wording — it reads the claim off the screen and then performs
    it, which is the only version of this assertion the defect would have
    failed."""
    approved(series)
    first = render("--format", "vertical")
    assert first.exit_code == 0, first.output
    assert "one approval renders every format" in flat(first)
    for fmt in ("vertical", "wide"):
        result = render("--format", fmt, "--replace")
        assert result.exit_code == 0, (fmt, result.output)
        assert status_on_disk(series) == "rendered"


def test_no_screen_tells_the_operator_that_rendered_is_terminal(series, fake):
    """M8. The sentence that made the defect legible — "`rendered` is terminal
    in the MVP … there is no supported way back" — was TRUE of the code and
    false of the tool's own promise. Whichever half was going to move, both
    could not stay."""
    approved(series)
    assert render("--format", "vertical").exit_code == 0
    screens = (
        render("--format", "wide").output
        + render("--format", "wide").output
        + render().output
    ).lower()
    assert "terminal" not in screens
    assert "no supported way back" not in screens


def test_the_help_says_what_no_format_does(series):
    """M8. §9 documents `render <ep>` as every enabled format; the flag's own
    help said only "output format", which is how the behaviour went unnoticed."""
    text = help_text("video", "render")
    assert "every enabled format" in text
    assert "--replace" in text

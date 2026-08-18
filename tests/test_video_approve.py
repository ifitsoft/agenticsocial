"""`agsoc video approve` — the gate. Spec §8.4, §10.

Every test here exists because a weaker `approve` passes without it. The table
is in the Phase 7 Task 1 brief; the mutant number is named in each docstring.

Three habits this file keeps, each because the matching mutant is a one-line
source edit:

  * **Exit code AND output AND `result.exception`** (D-035). `CliRunner`
    converts a traceback into exit code 1 with empty output, which is
    byte-identical to a clean refusal from the test's point of view.
  * **Every refusal also asserts the status ON DISK did not move.** D-059 was a
    gate that refused and a second writer that moved the status anyway; a test
    that only reads the exit code cannot see that.
  * **Every negative test is paired with its positive half.** A gate that
    refuses everything kills M2-M4 and is useless.
"""
import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.models import Status
from agenticsocial.video import approve as approve_mod
from agenticsocial.video import cli as video_cli
from agenticsocial.video import corpus
from agenticsocial.video import verify as V
from agenticsocial.video.episode import load_episode, read_script
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()


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


EP = "2026-08-17"
BY = "Ali Abdukarim"

SOURCE = (
    "DeepSeek's 1.6T MoE flagship quietly moved from preview to general "
    "availability this week, then announced new pricing starting August 16 at "
    "about $1.32 / $3.96 per 1M tokens (in/out). Alibaba's Qwen3.8-Max, at "
    "roughly 2.4 trillion parameters with about 95B active, is the largest "
    "open-weight release so far."
)


def write_script(ep, beats, status="in_review"):
    # The id is QUOTED: `episode: 2026-08-17` unquoted is a YAML date.
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f"---\nepisode: '{ep.id}'\nseries: the-brief\nstatus: {status}\n---\n{body}",
        encoding="utf-8",
    )


def episode(series, beats, sources=None, ep_id=EP, status="in_review"):
    from agenticsocial.video.episode import create_episode

    ep = create_episode(series, ep_id)
    for key, text in (sources or {"local-ai-zone": SOURCE}).items():
        corpus.write_document(
            ep, text, url=f"https://{key}.example/x", key=key, fetched_at="2026-08-17"
        )
    write_script(ep, beats, status=status)
    return load_episode(series, ep_id)


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
    """A figure invented in good faith, absent from the source — a `fail`."""
    beat = {
        "type": "statement",
        "hold": 3.0,
        "text": "DeepSeek's old price was $0.11 per 1M tokens.",
        "src": "local-ai-zone",
        "quote": "announced new pricing starting August 16",
    }
    beat.update(over)
    return beat


def custom_beat(**over):
    beat = {
        "type": "custom",
        "hold": 3.0,
        "js": "c.fillRect(0,0,10,10)",
        "attest": "Draws the price ladder from the two figures above.",
    }
    beat.update(over)
    return beat


def check(series_slug="the-brief", ep_id=EP):
    return run("video", "check", ep_id, "--series", series_slug)


def approve(*extra, ep_id=EP, by=BY):
    return run("video", "approve", ep_id, "--series", "the-brief", "--by", by, *extra)


def status_on_disk(series, ep_id=EP):
    """Read the status back from the FILE, never from a loaded object."""
    meta, _, _ = read_script(series.episodes_dir / ep_id / "script.yaml")
    return meta.get("status")


def approval_on_disk(series, ep_id=EP):
    meta, _, _ = read_script(series.episodes_dir / ep_id / "script.yaml")
    return meta.get("approval")


def ledger_path(series, ep_id=EP):
    return series.episodes_dir / ep_id / "claims.json"


def read_ledger_file(series, ep_id=EP):
    return json.loads(ledger_path(series, ep_id).read_text(encoding="utf-8"))


def write_ledger_file(series, ledger, ep_id=EP):
    ledger_path(series, ep_id).write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# --- R1: the gate takes identifiers -----------------------------------------------


def test_approve_takes_identifiers_not_objects():
    """M1. D-072: there must be no argument a caller can shape to change the
    verdict — no `Script`, no ledger, no pre-loaded `Episode` or `Series`."""
    params = inspect.signature(approve_mod.approve_episode, eval_str=True).parameters
    assert list(params) == ["ws", "series_slug", "ep_id", "by", "now"]
    for name in ("series_slug", "ep_id", "by"):
        assert params[name].annotation is str
    forbidden = {"script", "ledger", "claims", "episode", "series", "records"}
    assert forbidden.isdisjoint(params)


def test_the_command_offers_no_way_to_supply_the_script_or_the_ledger():
    """M1's CLI half — an option is an argument a caller can shape."""
    result = run("video", "approve", "--help")
    assert result.exit_code == 0
    for flag in ("--script", "--ledger", "--claims", "--force", "--skip"):
        assert flag not in result.output


def test_approve_reads_the_ledger_on_disk_not_one_the_caller_computed(series):
    """M1, behavioural. Doctoring `claims.json` to `fail` refuses even though a
    fresh check of the same script passes — the file is the authority."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["mechanical"]["verdict"] = "fail"
    write_ledger_file(series, ledger)
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-001" in result.output
    assert status_on_disk(series) == "in_review"


# --- R2: open claims refuse, and only open claims ---------------------------------


def test_a_fail_claim_refuses_and_names_it(series):
    """M2 and M12. A refusal that names no claim is one nobody can act on."""
    episode(series, [clean_beat(), fabricated_beat()])
    assert check().exit_code == 1
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-002" in result.output
    assert "fail" in result.output
    assert status_on_disk(series) == "in_review"
    assert approval_on_disk(series) is None


def test_a_no_source_claim_refuses_and_names_it(series):
    """M3. `no_source` is not a pass: nothing was checked at all."""
    episode(series, [{"type": "body", "hold": 3.0, "text": "Prices moved a lot."}])
    assert check().exit_code == 1
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-001" in result.output
    assert "no_source" in result.output
    assert status_on_disk(series) == "in_review"


def test_an_unattested_manual_refuses_and_names_it(series):
    """M4. `script.py` refuses an empty `attest` at load, so the unattested
    ledger record is written by hand — which is also the case that matters: the
    gate reads the FILE, and an attestation lost between check and file is
    unattested to everyone who reads the file."""
    episode(series, [clean_beat(), custom_beat()])
    assert check().exit_code == 0
    ledger = read_ledger_file(series)
    manual = [r for r in ledger["claims"] if r["mechanical"]["verdict"] == "manual"]
    assert len(manual) == 1
    manual[0]["mechanical"]["attest"] = "   "
    write_ledger_file(series, ledger)
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-002" in result.output
    assert status_on_disk(series) == "in_review"


def test_an_attested_manual_approves(series):
    """M5, R2's negative half. D-088: an attested `custom` beat passes on a
    human's signed sentence. If it blocked, `custom` would be unusable."""
    episode(series, [clean_beat(), custom_beat()])
    assert check().exit_code == 0
    result = approve()
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "approved"


def test_an_entity_miss_does_not_block(series):
    """M6, D-102. 35% of entity atoms on the real brief are unfindable and not
    one was a real error; gating them refuses 62% of correct beats."""
    episode(
        series,
        [
            clean_beat(
                text="Anthropic's flagship moved to general availability.",
                quote="quietly moved from preview to general availability",
            )
        ],
    )
    assert check().exit_code == 0
    record = read_ledger_file(series)["claims"][0]
    assert record["mechanical"]["entities_missing"], "precondition: a miss is recorded"
    assert record["mechanical"]["verdict"] == "pass"
    result = approve()
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "approved"


def test_an_unknown_verdict_fails_closed(series):
    """Own sweep. `is_blocking` used to answer "not blocking" for any verdict it
    did not recognise — the D-106 shape: a value the rule cannot read treated as
    "nothing to check" rather than "cannot be checked"."""
    assert V.is_blocking({"mechanical": {"verdict": "ok"}}) is True
    assert V.is_blocking({"mechanical": {}}) is True
    assert V.is_blocking({}) is True
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["mechanical"]["verdict"] = "supported"  # a Phase 9 verdict
    write_ledger_file(series, ledger)
    result = approve()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "in_review"


# --- R3: the ledger must describe THIS script ------------------------------------


def test_an_absent_ledger_refuses_and_says_what_to_run(series):
    """M8. Approving with no check at all is the defect in its purest form."""
    episode(series, [clean_beat()])
    assert not ledger_path(series).exists()
    result = approve()
    assert result.exit_code == 1, result.output
    assert "check" in result.output
    assert status_on_disk(series) == "in_review"


def test_a_stale_ledger_refuses_distinguishably_from_an_open_claim(series):
    """M7 and R3. The script moved under the ledger: every verdict still lines
    up by `beat_index` and is now about a sentence nobody wrote."""
    ep = episode(series, [clean_beat()])
    assert check().exit_code == 0
    write_script(
        ep,
        [clean_beat(text="DeepSeek's flagship is a 1.6T mixture-of-experts model.")],
    )
    result = approve()
    assert result.exit_code == 1, result.output
    assert "changed" in result.output
    assert "check" in result.output
    assert "open claim" not in result.output
    assert status_on_disk(series) == "in_review"


def test_a_stale_corpus_refuses(series):
    """M7's other half — the bytes the claim was checked AGAINST moved."""
    ep = episode(series, [clean_beat()])
    assert check().exit_code == 0
    corpus.write_document(
        ep,
        SOURCE.replace("1.6T", "1.9T"),
        url="https://local-ai-zone.example/x",
        key="local-ai-zone",
        fetched_at="2026-08-17",
        replace=True,
    )
    result = approve()
    assert result.exit_code == 1, result.output
    assert "corpus" in result.output
    assert status_on_disk(series) == "in_review"


def test_a_current_clean_ledger_approves(series):
    """R3's negative half, and the whole point of the command."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = approve()
    assert result.exit_code == 0, result.output
    assert "approved" in result.output
    assert status_on_disk(series) == "approved"


# --- R4: what an approval records, and the transition it makes --------------------


def test_approval_records_the_approver_and_the_digest(series):
    """R4. The record is a visible diff in the file you commit — the same
    property §8.4 demands of an override."""
    episode(series, [clean_beat()])
    check()
    result = approve()
    assert result.exit_code == 0, result.output
    record = approval_on_disk(series)
    assert record["by"] == BY
    assert record["at"]
    assert len(record["script_sha256"]) == 64
    ledger = read_ledger_file(series)
    assert record["corpus_sha"] == ledger["corpus_sha"]
    assert record["claims_checked_at"] == ledger["checked_at"]


def test_script_sha256_is_over_the_beats_document_not_the_whole_file(series):
    """M9 — "recorded over the wrong bytes".

    The whole file carries the status and the approval record itself, so a
    whole-file digest is either self-invalidating or invalidated by the
    pipeline's own next transition (`approved → rendering` rewrites the status).
    The beats document is the thing the viewer sees, and it is re-emitted
    verbatim by every status write.
    """
    ep = episode(series, [clean_beat()])
    check()
    assert approve().exit_code == 0
    recorded = approval_on_disk(series)["script_sha256"]

    _, beats_text, _ = read_script(ep.script_path)
    assert recorded == hashlib.sha256(beats_text.encode("utf-8")).hexdigest()
    assert recorded != hashlib.sha256(ep.script_path.read_bytes()).hexdigest()


def test_the_recorded_digest_still_matches_after_the_approval_write(series):
    """M9. An approval whose own write invalidates its digest binds nothing."""
    episode(series, [clean_beat()])
    check()
    approve()
    recorded = approval_on_disk(series)["script_sha256"]
    assert approve_mod.beats_sha256(load_episode(series, EP)) == recorded


def test_editing_the_beats_changes_the_digest(series):
    """M9's negative half: a digest that never moves detects no drift."""
    ep = episode(series, [clean_beat()])
    check()
    approve()
    before = approval_on_disk(series)["script_sha256"]
    write_script(ep, [clean_beat(hold=4.0)], status="approved")
    assert approve_mod.beats_sha256(load_episode(series, EP)) != before


def test_approving_does_not_invalidate_the_check_it_approved(series):
    """The write must be invisible to `stale_reason`, or the episode is stale
    the instant it is approved and Phase 8 refuses to render anything ever."""
    episode(series, [clean_beat()])
    check()
    assert approve().exit_code == 0
    ep = load_episode(series, EP)
    assert V.stale_reason(ep, V.read_ledger(ep)) is None
    again = check()
    assert again.exit_code == 0, again.output


def test_approving_preserves_the_beats_bytes_exactly(series):
    """D-026/D-031: the approval write must not reflow or re-encode the beats.
    CRLF is the case that has bitten this project before."""
    ep = episode(series, [clean_beat()])
    raw = ep.script_path.read_bytes()
    ep.script_path.write_bytes(raw.replace(b"\n", b"\r\n"))
    check()
    _, before, _ = read_script(ep.script_path)
    assert approve().exit_code == 0, "precondition: the episode is approvable"
    _, after, _ = read_script(ep.script_path)
    assert after == before
    assert "\r\n" in after


def test_approving_from_draft_refuses(series):
    """M11, R4's negative half. §10 has no `draft → approved` edge: the agent
    writes `in_review` and stops, and that hand-off is what `approve` gates."""
    episode(series, [clean_beat()], status="draft")
    assert check().exit_code == 0
    result = approve()
    assert result.exit_code == 1, result.output
    assert "draft" in result.output
    assert status_on_disk(series) == "draft"
    assert approval_on_disk(series) is None


def test_approving_twice_refuses(series):
    """M11's sibling: `approved → approved` is not an edge either, so a second
    approval cannot silently restamp a digest over an edited script."""
    episode(series, [clean_beat()])
    check()
    assert approve().exit_code == 0
    result = approve()
    assert result.exit_code == 1, result.output
    assert "approved" in result.output


def test_the_approver_must_be_named(series):
    """The decision, pinned: identity is asserted by a human, never inferred.
    A blank `--by` is a signature nobody wrote."""
    episode(series, [clean_beat()])
    check()
    result = approve(by="   ")
    assert result.exit_code == 1, result.output
    assert "--by" in result.output
    assert status_on_disk(series) == "in_review"


def test_by_is_required(series):
    """Omitting it must not fall back to the series byline or the OS user."""
    episode(series, [clean_beat()])
    check()
    result = runner.invoke(
        app, ["video", "approve", EP, "--series", "the-brief"], catch_exceptions=False
    )
    assert result.exit_code != 0
    assert status_on_disk(series) == "in_review"


def test_the_byline_is_not_used_as_the_approver(series):
    """The series `byline` is a display credit on the frame, not an
    accountability record — and it is empty in the real workspace."""
    toml = series.dir / "series.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace('byline = ""', 'byline = "The Brief"'),
        encoding="utf-8",
    )
    episode(series, [clean_beat()])
    check()
    approve(by="Someone Else")
    assert approval_on_disk(series)["by"] == "Someone Else"


# --- R5: there is no second status writer -----------------------------------------


SRC = Path(__file__).resolve().parent.parent / "src" / "agenticsocial"


def _status_writers() -> set[str]:
    """Every `<mapping>["status"] = ...` in `src/`, as `module:function`."""
    found = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def walk(node, where):
            for child in ast.iter_child_nodes(node):
                name = where
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = child.name
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if (
                            isinstance(target, ast.Subscript)
                            and isinstance(target.slice, ast.Constant)
                            and target.slice.value == "status"
                        ):
                            found.add(
                                f"{path.relative_to(SRC).as_posix()}:{name}"
                            )
                walk(child, name)

        walk(tree, "<module>")
    return found


def test_only_two_functions_write_a_status_key(series):
    """R5, mechanised. D-059's root cause was a SECOND, ungated status writer —
    found only because someone enumerated them. This is that enumeration, run on
    every commit instead of once in a report.

    `workspace.save_variant` is on the list and is not a hole: it writes back
    the status it read from disk, precisely so it cannot stamp a forged one.
    """
    assert _status_writers() == {
        "workspace.py:save_variant",
        "workspace.py:set_status",
        "video/episode.py:set_status",
    }


def test_the_gate_does_not_write_the_script_itself(series):
    """R5. `approve.py` must reach disk only through `episode.set_status`, which
    re-reads the status it gates on. A convenience write here is D-059."""
    source = (SRC / "video" / "approve.py").read_text(encoding="utf-8")
    assert "atomic_write" not in source
    assert '"status"' not in source
    assert "set_status" in source


def test_the_video_cli_never_writes_a_status_outside_the_gate(series):
    """R5. Every `set_status` call in the video CLI belongs to `approve`."""
    source = (SRC / "video" / "cli.py").read_text(encoding="utf-8")
    assert "set_status" not in source


# --- the ride-along: `check`'s summary and the gate must agree --------------------


def test_check_does_not_call_a_manual_claim_verified(series):
    """M13, D-112. The green line counted as "verified" a claim the same screen
    calls "attested by hand — no machine checked these"."""
    episode(series, [clean_beat(), custom_beat()])
    result = check()
    assert result.exit_code == 0, result.output
    assert "2 claims verified" not in result.output
    assert "1 verified" in result.output
    assert "attested" in result.output
    assert "none open" in result.output


def test_check_still_says_verified_when_everything_was_machine_checked(series):
    """M13's negative half — the honest line must survive the fix."""
    episode(series, [clean_beat()])
    result = check()
    assert result.exit_code == 0, result.output
    assert "1 claim verified" in result.output


def test_the_summary_and_the_gate_share_one_predicate(series):
    """M14. Two paths to one answer, one of them ungated, is the D-059 shape."""
    assert video_cli.is_blocking is V.is_blocking


@pytest.mark.parametrize(
    "record,expected",
    [
        ({"mechanical": {"verdict": "pass"}}, "verified"),
        ({"mechanical": {"verdict": "manual", "attest": "it draws x"}}, "attested"),
        ({"mechanical": {"verdict": "manual", "attest": " "}}, "open"),
        ({"mechanical": {"verdict": "fail"}}, "open"),
        ({"mechanical": {"verdict": "no_source"}}, "open"),
        ({"mechanical": {"verdict": "refuted"}}, "open"),
        ({"mechanical": {"verdict": "pass"}, "override": {"by": "x"}}, "verified"),
    ],
)
def test_classify_and_is_blocking_cannot_disagree(record, expected):
    """M14. One record, one classification, and `is_blocking` is derived from
    it rather than restating the list of verdicts a second time."""
    assert V.classify(record) == expected
    assert V.is_blocking(record) is (expected == "open")


def test_every_claim_is_counted_exactly_once(series):
    """M14. Verified + attested + open == total, so no summary can round toward
    reassurance by dropping a claim from the denominator (D-112)."""
    episode(series, [clean_beat(), fabricated_beat(), custom_beat()])
    check()
    records = read_ledger_file(series)["claims"]
    counts = [V.classify(r) for r in records]
    assert len(counts) == 3
    assert counts.count("verified") + counts.count("attested") + counts.count(
        "open"
    ) == len(records)
    assert sorted(counts) == ["attested", "open", "verified"]


# --- refusals an operator can act on ----------------------------------------------


def test_the_refusal_says_what_to_do_about_the_claim(series):
    """M12 / D-040: a checker that refuses without teaching trains an operator
    to override everything."""
    episode(series, [fabricated_beat()])
    assert check().exit_code == 1
    result = approve()
    assert result.exit_code == 1, result.output
    assert "fix" in result.output
    assert "quote" in result.output


def test_an_unknown_episode_fails_cleanly(series):
    result = approve(ep_id="nope")
    assert result.exit_code == 1, result.output
    assert "nope" in result.output


def test_an_unknown_series_fails_cleanly(ws):
    result = run("video", "approve", EP, "--series", "ghost", "--by", BY)
    assert result.exit_code == 1, result.output
    assert "ghost" in result.output


def test_an_episode_that_asserts_nothing_says_so(series):
    """A script of only exempt beats produces an empty ledger. `check` exits 0
    on it, so `approve` must too — but the screen has to say that the gate
    checked nothing, or "approved" reads as "verified"."""
    episode(
        series,
        [
            {"type": "title", "hold": 3.0, "text": "The Brief", "kicker": "Aug 17"},
            {"type": "signoff", "hold": 3.0, "text": "See you tomorrow"},
        ],
    )
    assert check().exit_code == 0
    result = approve()
    assert result.exit_code == 0, result.output
    assert "asserts nothing" in result.output
    assert status_on_disk(series) == "approved"


def test_approve_never_moves_a_status_it_did_not_gate(series):
    """D-059's closing question, as a test: after every refusal in this file the
    status is untouched — this one checks the ledger is untouched too, so a
    refused approval cannot leave a half-written record behind."""
    episode(series, [fabricated_beat()])
    check()
    before = ledger_path(series).read_bytes()
    assert approve().exit_code == 1
    assert ledger_path(series).read_bytes() == before
    assert status_on_disk(series) == "in_review"
    assert Status(status_on_disk(series)) is Status.IN_REVIEW


def test_the_extra_record_cannot_smuggle_a_status(series):
    """R5. `set_status` gained a second parameter in this task, and a parameter
    that reaches the metadata document is a status writer unless the write order
    forbids it: merge the record FIRST, then set the status from `target`.

    Reversed, `approve` — or anything else with a dict — writes any status it
    likes through the one function this project trusts. That is D-059 rebuilt
    inside the fix for D-059.
    """
    from agenticsocial.video.episode import set_status

    episode(series, [clean_beat()], status="draft")
    ep = load_episode(series, EP)
    set_status(ep, Status.IN_REVIEW, {"status": "published", "note": "kept"})
    assert status_on_disk(series) == "in_review"
    meta, _, _ = read_script(ep.script_path)
    assert meta["note"] == "kept"


def test_approve_does_not_resolve_a_partial_episode_id(series):
    """The gate names its subject exactly. `resolve_episode`'s substring match
    is right for `review`, which shows you what it found; here the thing it
    might find is an approval of an episode nobody named."""
    episode(series, [clean_beat()])
    check()
    result = approve(ep_id="2026-08-1")
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "in_review"


# --- Part A: §8.4's override, applied ---------------------------------------------
#
# Task 1 recorded an override and consumed nothing. `check` told the operator
# *"`approve` is what reads an override"* while `approve` read no such thing —
# a promise, not a description. These tests are what makes the sentence true.
#
# The asymmetry §8.4 states is the whole design: *passing verification is
# automatic; bypassing it costs you a written sentence with your name on it.*
# So every test here has two halves — the sentence clears its claim, and
# anything less than a sentence with a name on it clears nothing.

OVERRIDE = {
    "reason": "Framed as expectation, not fact; 'widely expected' is my read of "
    "three sourced analyst quotes, not a claim the article makes.",
    "by": BY,
}


def test_an_override_clears_the_claim_it_names(series):
    """R1. The whole of Part A: a `fail` plus a written sentence approves.

    Task 1's `test_an_override_does_not_clear_a_fail_in_this_task` is the
    negative this replaces — it pinned the scope of that task, not a property.
    """
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    assert check().exit_code == 0, "the override clears the claim on check too"
    result = approve()
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "approved"


def test_an_override_clears_exactly_the_claim_it_names(series):
    """M1. An override on one claim must not clear the claim beside it — the
    two beats are the same type, the same source and the same shape of failure,
    so an implementation that clears "the beat" or "a failing claim" passes on
    everything except which id it names."""
    episode(
        series,
        [
            fabricated_beat(),
            fabricated_beat(
                text="DeepSeek's old price was $0.12 per 1M tokens.",
                claim_override=dict(OVERRIDE),
            ),
        ],
    )
    assert check().exit_code == 1
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-001" in result.output
    assert "c-002" not in result.output, "the overridden claim was re-opened"
    assert status_on_disk(series) == "in_review"


def test_an_override_does_not_clear_the_episode(series):
    """M2. One written sentence buys one claim. The unattested `custom` beat is
    a different KIND of open claim, so an override that clears the episode —
    or that clears "everything after it" — shows up here and nowhere else."""
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE)), custom_beat()])
    assert check().exit_code == 0, "precondition: both claims clear"
    # `script.py` refuses a blank `attest` at load, so the unattested manual is
    # made in the LEDGER — which is the artifact the gate reads anyway, and an
    # attestation lost between the check and the file is lost to every reader.
    ledger = read_ledger_file(series)
    ledger["claims"][1]["mechanical"]["attest"] = "   "
    write_ledger_file(series, ledger)
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-002" in result.output
    assert status_on_disk(series) == "in_review"


@pytest.mark.parametrize(
    "bad",
    [
        {"reason": "   ", "by": BY},
        {"reason": "it is fine", "by": ""},
        {"reason": "it is fine"},
        {"by": BY},
        "it is fine, trust me",
        {"reason": "it is fine", "by": BY, "approved": True},
        {},
        [],
    ],
    ids=[
        "blank-reason",
        "blank-by",
        "no-by",
        "no-reason",
        "bare-string",
        "unknown-key",
        "empty-mapping",
        "not-a-mapping",
    ],
)
def test_an_override_that_is_not_a_sentence_with_a_name_clears_nothing(series, bad):
    """M3, at the gate rather than at the loader.

    `script.py` refuses these at load (D-103), but `claims.json` is a file on
    disk and the gate reads the LEDGER. A gate that trusts the loader to have
    already refused is a gate that clears a claim on `{}` the moment anyone
    hand-edits the artifact — and `approved: true` sitting beside a reason
    nobody reads is the checkbox §8.4 says this must never be.
    """
    episode(series, [fabricated_beat()])
    assert check().exit_code == 1
    ledger = read_ledger_file(series)
    ledger["claims"][0]["override"] = bad
    write_ledger_file(series, ledger)
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-001" in result.output
    assert status_on_disk(series) == "in_review"


def _screen(result) -> str:
    """The output, minus the `wrote <path>` line — pytest's tmp directories are
    named after the test, so a test about the word "override" writes it into
    every path it prints. Lowercased, because these assertions are about words
    a human reads, not about capitalisation."""
    return "\n".join(
        line for line in result.output.splitlines() if not line.startswith("wrote ")
    ).lower()


def test_an_absent_override_is_normal_and_silent(series):
    """M3's negative half. Overrides are rare; a screen that mentions them on
    every clean run is a screen whose mention gets tuned out."""
    episode(series, [clean_beat()])
    result = check()
    assert result.exit_code == 0, result.output
    assert "override" not in _screen(result), result.output
    approved = approve()
    assert approved.exit_code == 0, approved.output
    assert "override" not in _screen(approved), approved.output


def test_an_overridden_claim_is_not_verified(series):
    """M4. It is its own state. "Cleared by a person" and "checked by a machine"
    are the two things this project exists to keep apart (D-088's argument, one
    door along), and a summary that collapses them is D-112's overclaim."""
    record = {"mechanical": {"verdict": "fail"}, "override": dict(OVERRIDE)}
    assert V.classify(record) == "overridden"
    assert V.is_blocking(record) is False


def test_the_approval_record_counts_an_override_separately(series):
    """M4 in the artifact. The committed diff must not say "1 of 1 verified"
    about a claim a machine refused."""
    episode(series, [clean_beat(), fabricated_beat(claim_override=dict(OVERRIDE))])
    assert check().exit_code == 0
    assert approve().exit_code == 0, "precondition"
    counted = approval_on_disk(series)["claims"]
    assert counted == {"total": 2, "verified": 1, "attested": 0, "overridden": 1}


def test_the_approval_names_every_claim_it_cleared_by_override(series):
    """§8.4's accountability, carried into the record a human commits. A count
    says how many sentences were spent; only the ids and the names say which
    claims are standing on a person rather than on a source."""
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    check()
    assert approve().exit_code == 0, "precondition"
    overrides = approval_on_disk(series)["overrides"]
    assert overrides == [{"id": "c-001", "by": BY, "reason": OVERRIDE["reason"]}]


def test_the_approve_screen_does_not_call_an_overridden_episode_verified(series):
    """M4 on the screen — and the screen is the deliverable (D-104). The exit
    code is read by a machine; this line is read by the person who signed."""
    episode(series, [clean_beat(), fabricated_beat(claim_override=dict(OVERRIDE))])
    check()
    result = approve()
    assert result.exit_code == 0, result.output
    assert "2 of 2 verified" not in result.output
    assert "1 of 2 verified" in result.output
    assert "override" in result.output


def test_an_overridden_claim_does_not_block(series):
    """M5, R3's negative half. A state that is distinguishable everywhere and
    still refuses is not an override, it is a slower refusal."""
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    result = check()
    assert result.exit_code == 0, result.output
    assert "not verified" in _screen(result)
    assert "fail" in result.output, "the measurement is still on the screen"


def test_the_override_rate_is_on_the_screen(series):
    """M11 / D-040. A high override rate means the checker is wrong, not the
    operator — and nobody can notice a rate that is never printed. It is on
    BOTH screens because `check` is where the operator decides to write one and
    `approve` is where they sign for it."""
    episode(series, [clean_beat(), fabricated_beat(claim_override=dict(OVERRIDE))])
    checked = check()
    assert checked.exit_code == 0, checked.output
    assert "override rate" in checked.output
    assert "1 of 2" in checked.output
    approved = approve()
    assert approved.exit_code == 0, approved.output
    assert "override rate" in approved.output


def test_the_override_rate_is_not_printed_when_there_are_none(series):
    """M11's negative half — `override rate 0%` on every clean run is noise,
    and noise is what the rate has to cut through when it matters."""
    episode(series, [clean_beat()])
    assert "override rate" not in check().output


def test_an_override_on_a_claim_that_passes_anyway_is_flagged_stale(series):
    """The decision this task had to make, pinned. A stale override is a
    written sentence about a problem that no longer exists; leaving it silent is
    how the sentence stops meaning anything. It WARNS and does not refuse —
    refusing would make the remedy "delete the paragraph you wrote", which
    inverts §8.4's cost asymmetry."""
    episode(series, [clean_beat(claim_override=dict(OVERRIDE))])
    result = check()
    assert result.exit_code == 0, result.output
    assert "stale" in _screen(result)
    assert "c-001" in result.output
    approved = approve()
    assert approved.exit_code == 0, approved.output
    assert status_on_disk(series) == "approved"
    assert approval_on_disk(series)["claims"] == {
        "total": 1,
        "verified": 1,
        "attested": 0,
        "overridden": 0,
    }


def test_a_stale_override_is_not_reported_on_a_claim_it_clears(series):
    """The negative half of the stale warning: an override that is doing its
    job must not be nagged about, or the warning is one more line to skip."""
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    result = check()
    assert result.exit_code == 0, result.output
    assert "stale" not in _screen(result)


def test_an_override_clears_an_unattested_manual_claim(series):
    """A `custom` beat with no `attest` but a written override: the override is
    strictly MORE than an attestation — a sentence plus a name — so refusing it
    would mean the weaker artifact clears and the stronger one does not."""
    episode(series, [custom_beat(claim_override=dict(OVERRIDE))])
    assert check().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["mechanical"]["attest"] = "   "
    write_ledger_file(series, ledger)
    assert approve().exit_code == 0
    assert approval_on_disk(series)["claims"] == {
        "total": 1,
        "verified": 0,
        "attested": 0,
        "overridden": 1,
    }


@pytest.mark.parametrize(
    "record,expected",
    [
        ({"mechanical": {"verdict": "pass"}, "override": dict(OVERRIDE)}, "verified"),
        (
            {
                "mechanical": {"verdict": "manual", "attest": "it draws x"},
                "override": dict(OVERRIDE),
            },
            "attested",
        ),
        ({"mechanical": {"verdict": "fail"}, "override": dict(OVERRIDE)}, "overridden"),
        ({"mechanical": {"verdict": "no_source"}, "override": dict(OVERRIDE)}, "overridden"),
        ({"mechanical": {"verdict": "refuted"}, "override": dict(OVERRIDE)}, "overridden"),
        ({"mechanical": {}, "override": dict(OVERRIDE)}, "overridden"),
        ({"mechanical": {"verdict": "fail"}, "override": {"by": BY}}, "open"),
        ({"mechanical": {"verdict": "fail"}, "override": None}, "open"),
    ],
    ids=[
        "pass-wins",
        "attested-wins",
        "fail",
        "no_source",
        "unknown-phase-9-verdict",
        "no-mechanical-block",
        "malformed",
        "absent",
    ],
)
def test_classify_answers_the_override_too(record, expected):
    """M6/M10. One record, one answer, four states — and the MEASUREMENT wins
    where it is clean, so an override never has to be deleted to make a passing
    claim read as passing."""
    assert V.classify(record) == expected
    assert V.is_blocking(record) is (expected == "open")


def test_the_gate_and_every_screen_share_one_classify():
    """M10. Not "they agree" — the same object. A wrapper is where two answers
    to one question drift apart (D-059)."""
    assert video_cli.classify is V.classify
    assert video_cli.is_blocking is V.is_blocking


def test_only_verify_reads_a_claims_override():
    """M10, mechanised. Any module that reads `record["override"]` for itself
    is a second place §8.4's rule is spelled out, and the first time the two
    disagree is the first time a checkbox clears a claim.

    Enumerated over the AST rather than by grep, so that a docstring, a comment
    or the display LABEL `override` does not count — only an actual read of the
    field: `record["override"]`, `record.get("override")` and friends.
    """
    import agenticsocial.video as pkg

    def reads_the_field(node) -> bool:
        if isinstance(node, ast.Subscript):
            index = node.slice
            return isinstance(index, ast.Constant) and index.value == "override"
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"get", "pop", "setdefault"}
            and node.args
        ):
            first = node.args[0]
            return isinstance(first, ast.Constant) and first.value == "override"
        return False

    root = Path(pkg.__file__).parent
    offenders = {}
    for path in sorted(root.glob("*.py")):
        if path.name == "verify.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = [node for node in ast.walk(tree) if reads_the_field(node)]
        if found:
            offenders[path.name] = len(found)
    assert offenders == {}, offenders

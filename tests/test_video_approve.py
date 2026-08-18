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
    params = inspect.signature(approve_mod.approve_episode).parameters
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


def test_an_override_does_not_clear_a_fail_in_this_task(series):
    """Task 1 scope. §8.4's override is Task 2; until it lands, `approve` must
    not treat a recorded override as an applied one — a gate that goes quiet
    because someone wrote a sentence nobody consumed is worse than no gate."""
    episode(
        series,
        [
            fabricated_beat(
                claim_override={"reason": "the figure is my own arithmetic", "by": BY}
            )
        ],
    )
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-001" in result.output
    assert status_on_disk(series) == "in_review"


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

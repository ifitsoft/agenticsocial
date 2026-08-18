"""Pass 2 — the adversarial record, and the gate that reads it. §8.1, §8.3, §8.4.

Every test here exists because a weaker implementation passes without it; the
mutant number from the Phase 9 Task 1 brief is named in each docstring.

Four habits, each because the matching mutant is a one-line source edit:

  * **Exit code AND output AND `result.exception`** (D-035). `CliRunner` turns a
    traceback into exit 1 with empty output, which is byte-identical to a clean
    refusal from a test's point of view.
  * **Every refusal also asserts the status ON DISK did not move** (D-059).
  * **Assertions name the LINE they mean, not a word that appears somewhere on
    the screen** (D-118): the survivor last phase was a test reading the
    *diagnosis* and calling it the *remedy*, and both are on the same screen.
  * **Every negative test has its positive half.** A gate that refuses
    everything kills half this table and is useless.

No LLM call and no network anywhere here: the CLI records a judgement, it never
makes one (CLAUDE.md), and `conftest` guards the sockets either way.
"""
import ast
import inspect
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
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
JUDGE = "refuter (claude, skills/verify)"

SOURCE = (
    "DeepSeek's 1.6T MoE flagship quietly moved from preview to general "
    "availability this week, then announced new pricing starting August 16 at "
    "about $1.32 / $3.96 per 1M tokens (in/out). Alibaba's Qwen3.8-Max, at "
    "roughly 2.4 trillion parameters with about 95B active, is the largest "
    "open-weight release so far."
)

REFUTATION = (
    "Checked whether the 1.6T figure belongs to the preview build rather than "
    "the GA one; the source names the flagship in the same sentence as GA. "
    "Checked whether 1.6T is a token count rather than a parameter count; the "
    "source writes MoE flagship, not context."
)
RISK = "The source does not state an effective date for the parameter count."


def write_script(ep, beats, status="in_review"):
    # The id is QUOTED: `episode: 2026-08-17` unquoted is a YAML date.
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f"---\nepisode: '{ep.id}'\nseries: the-brief\nstatus: {status}\n---\n{body}",
        encoding="utf-8",
    )


def episode(series, beats, ep_id=EP, status="in_review"):
    from agenticsocial.video.episode import create_episode

    ep = create_episode(series, ep_id)
    corpus.write_document(
        ep, SOURCE, url="https://z.example/x", key="local-ai-zone",
        fetched_at="2026-08-17",
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


def second_beat(**over):
    beat = {
        "type": "statement",
        "hold": 3.0,
        "text": "Qwen3.8-Max runs about 95B active parameters.",
        "src": "local-ai-zone",
        "quote": "roughly 2.4 trillion parameters with about 95B active",
    }
    beat.update(over)
    return beat


def fabricated_beat(**over):
    """A figure invented in good faith, absent from the source — a pass-1 `fail`."""
    beat = {
        "type": "statement",
        "hold": 3.0,
        "text": "DeepSeek's old price was $0.11 per 1M tokens.",
        "src": "local-ai-zone",
        "quote": "announced new pricing starting August 16",
    }
    beat.update(over)
    return beat


OVERRIDE = {
    "reason": "Framed as expectation, not fact; my read of three analyst quotes.",
    "by": BY,
}


def check(ep_id=EP):
    return run("video", "check", ep_id, "--series", "the-brief")


def review(ep_id=EP):
    return run("video", "review", ep_id, "--series", "the-brief")


def approve(ep_id=EP, by=BY):
    return run("video", "approve", ep_id, "--series", "the-brief", "--by", by)


def judge(
    claim="c-001",
    verdict="supported",
    refutation=REFUTATION,
    risk=None,
    by=JUDGE,
    ep_id=EP,
):
    args = [
        "video", "judge", ep_id, "--series", "the-brief",
        "--claim", claim, "--verdict", verdict, "--refutation", refutation,
        "--by", by,
    ]
    if risk is not None:
        args += ["--risk", risk]
    return run(*args)


def status_on_disk(series, ep_id=EP):
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


def block_of(series, claim_id="c-001", ep_id=EP):
    ledger = read_ledger_file(series, ep_id)
    return next(r for r in ledger["claims"] if r["id"] == claim_id)["adversarial"]


def set_block(series, block, claim_id="c-001", ep_id=EP):
    """Hand-write an `adversarial` block — the case that matters, because
    `claims.json` is a file on disk and the gate reads the file."""
    ledger = read_ledger_file(series, ep_id)
    record = next(r for r in ledger["claims"] if r["id"] == claim_id)
    record["adversarial"] = block
    write_ledger_file(series, ledger, ep_id)
    return record


def _screen(result) -> str:
    """The output minus the `wrote <path>` line — pytest's tmp dirs are named
    after the test, so a test about "refuted" writes it into every path."""
    return "\n".join(
        line for line in result.output.splitlines() if not line.startswith("wrote ")
    ).lower()


def labelled(result, label: str) -> str:
    """The one detail line with this label, joined and lowercased.

    D-118: an assertion that searches a whole screen for a small string passes
    for reasons its author did not intend — the survivor last phase asserted a
    remedy and matched the diagnosis three lines above it. `fix` and `why` are
    different lines and this test suite must be able to say which one it means.
    """
    lines = result.output.splitlines()
    out = []
    for i, line in enumerate(lines):
        if line.strip().startswith(label):
            value = [line.strip()[len(label):].strip()]
            for cont in lines[i + 1:]:
                if not cont.startswith(" " * 12) or not cont.strip():
                    break
                value.append(cont.strip())
            out.append(" ".join(value))
    assert out, f"no {label!r} line on the screen:\n{result.output}"
    return " || ".join(out).lower()


def days_ago(n: int) -> str:
    return (datetime.now().astimezone() - timedelta(days=n)).isoformat(
        timespec="seconds"
    )


# --- the record, §8.1 ---------------------------------------------------------------


def test_a_recorded_verdict_has_every_key_the_record_needs(series):
    """The shape §8.1 names, plus the four this task adds. `attempted_refutation`
    is what makes a `supported` worth anything (M11)."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = judge(risk=RISK)
    assert result.exit_code == 0, result.output
    block = block_of(series)
    assert block["verdict"] == "supported"
    assert block["attempted_refutation"] == REFUTATION
    assert block["residual_risk"] == RISK
    assert block["judged_by"] == JUDGE
    assert isinstance(block["judged_at"], str) and block["judged_at"]
    assert block["reproducible"] is False
    assert block["claim_sha256"] == V.claim_sha256(
        next(r for r in read_ledger_file(series)["claims"] if r["id"] == "c-001")
    )


def test_recording_a_verdict_does_not_restamp_the_pass_1_check(series):
    """`checked_at` is pass 1's answer about the bytes. A judgement is not a
    re-check, and moving that stamp would date the mechanical pass to the day
    somebody argued about it."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    before = read_ledger_file(series)["checked_at"]
    assert judge().exit_code == 0
    after = read_ledger_file(series)
    assert after["checked_at"] == before
    assert after["claims"][0]["adversarial"]["judged_at"] != before


def test_the_judge_writes_through_atomic_write(series):
    """No plain `write_text` on a workspace artifact (CLAUDE.md)."""
    source = Path(V.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    writers = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "write_text" not in writers


def test_the_cli_makes_no_model_call_and_no_fetch():
    """R6. The CLI records a judgement; it never makes one. There is no seam
    here a network guard would have to catch, and this asserts that."""
    for module in (V, video_cli):
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not imported & {"requests", "httpx", "urllib", "openai", "anthropic"}


# --- M1, M2, M4: the gate --------------------------------------------------------


def test_a_refuted_claim_refuses_at_the_gate(series):
    """M1. §8.4 lists `refuted` beside `fail`; a claim a refuter knocked over
    must not be approvable because pass 1 could not see the problem."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="refuted").exit_code == 0
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-001" in result.output
    assert "refuted" in _screen(result)
    assert status_on_disk(series) == "in_review"
    assert approval_on_disk(series) is None


def test_an_unsupported_claim_refuses_at_the_gate(series):
    """M2. `unsupported` is the verdict a refuter defaults to under uncertainty
    (§8.3), so it is the one a weak gate is most likely to wave through."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="unsupported").exit_code == 0
    result = approve()
    assert result.exit_code == 1, result.output
    assert "c-001" in result.output
    assert "unsupported" in _screen(result)
    assert status_on_disk(series) == "in_review"


def test_a_supported_claim_approves(series):
    """M4, R1's negative half. A gate that refuses everything is not a gate."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    result = approve()
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "approved"


def test_an_unjudged_claim_still_approves(series):
    """M4's other half, and the decision behind it: §8.4's refusal list is
    `fail · refuted · unsupported · no_source · unattested manual`. Absence of a
    judgement is not on it — pass 2 coverage is REPORTED (below), not gated."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert block_of(series) is None
    result = approve()
    assert result.exit_code == 0, result.output
    assert status_on_disk(series) == "approved"


def test_the_gate_refuses_the_refuted_claim_and_only_it(series):
    """M1 again, with a clean sibling: the refusal must name c-002 and let
    c-001 alone, or "one claim is bad" becomes "the episode is bad"."""
    episode(series, [clean_beat(), second_beat()])
    assert check().exit_code == 0
    assert judge(claim="c-001").exit_code == 0
    assert judge(claim="c-002", verdict="refuted").exit_code == 0
    result = approve()
    assert result.exit_code == 1, result.output
    assert "1 of 2 claims are open" in result.output
    rows = [line for line in result.output.splitlines() if " c-00" in line]
    assert len(rows) == 1 and "c-002" in rows[0]


# --- M3: refusing distinguishably -------------------------------------------------


def test_the_pass_2_refusal_does_not_read_like_a_pass_1_fail(series):
    """M3. Both refuse; the two remedies are different acts. A pass-1 `fail` is
    "your figure is not in the quote" — correct the figure or widen the quote. A
    `refuted` claim's figure IS in the quote: nothing about the citation is
    wrong, and widening it changes nothing. Asserted on the `fix` LINE, because
    the diagnosis is three lines above it and D-118's survivor matched that."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="refuted").exit_code == 0
    refuted = approve()
    assert refuted.exit_code == 1, refuted.output
    pass_2_fix = labelled(refuted, "fix")

    episode(series, [fabricated_beat()], ep_id="2026-08-18")
    assert check(ep_id="2026-08-18").exit_code == 1
    failed = approve(ep_id="2026-08-18")
    assert failed.exit_code == 1, failed.output
    pass_1_fix = labelled(failed, "fix")

    assert pass_2_fix != pass_1_fix
    assert "widen" in pass_1_fix and "widen" not in pass_2_fix
    assert "refut" in pass_2_fix


def test_the_refusal_carries_the_refutation_that_produced_it(series):
    """M3, and the evidence rule. "This claim is refuted" is a conclusion; the
    account of what was attacked is the only part an operator can check."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="refuted", refutation=REFUTATION).exit_code == 0
    result = approve()
    assert result.exit_code == 1, result.output
    assert "token count rather than a parameter count" in labelled(result, "pass 2")


def test_the_pass_2_state_is_on_the_claim_row_not_only_the_mechanical_one(series):
    """M3. A refuted claim's mechanical verdict is `pass`, so a row that prints
    only pass 1 shows a green word on the line the gate just refused."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="refuted").exit_code == 0
    result = approve()
    row = next(line for line in result.output.splitlines() if " c-001" in line)
    assert "refuted" in row.lower()


def test_reviews_table_shows_the_verdict_that_binds_not_the_one_that_passed(series):
    """M3 on `review`'s table. A refuted claim's mechanical verdict is `pass`,
    and this is the column an operator scans down the page before signing."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="refuted").exit_code == 0
    result = review()
    row = next(line for line in result.output.splitlines() if "statement" in line)
    assert "refuted" in row
    assert "pass" not in row
    # And the measurement is not lost — it is on the claim's own line below.
    assert "pass" in next(
        line for line in result.output.splitlines() if line.strip().startswith("! c-001")
    )


# --- M5, M6: residual_risk --------------------------------------------------------


def test_residual_risk_surfaces_in_review_on_a_supported_claim(series):
    """M5. §8.3: often the most useful output of the whole pass. A risk shown
    only on failures is a risk nobody reads on the episode they are signing."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(risk=RISK).exit_code == 0
    result = review()
    assert result.exit_code == 0, result.output
    assert "effective date" in labelled(result, "c-001")
    assert "residual risk" in _screen(result)


def test_residual_risk_surfaces_in_check_too(series):
    """M5. `check` is the screen an agent reads; `review` is the screen a human
    reads before signing. One function, both call sites."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(risk=RISK).exit_code == 0
    result = check()
    assert result.exit_code == 0, result.output
    assert "effective date" in labelled(result, "c-001")


def test_a_verdict_with_no_residual_risk_is_normal_and_silent(series):
    """M6, R2's negative half. Most supported claims carry no residual risk;
    treating its absence as an error would refuse the ordinary case, and a
    screen that says "no residual risk" on every claim is noise."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = judge()
    assert result.exit_code == 0, result.output
    assert block_of(series)["residual_risk"] is None
    assert approve().exit_code == 0
    assert status_on_disk(series) == "approved"
    assert "residual risk" not in _screen(review())


def test_residual_risk_survives_onto_a_refused_claim_too(series):
    """M5's other direction: a risk recorded beside a blocking verdict is not
    dropped because the claim is already refusing."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="unsupported", risk=RISK).exit_code == 0
    result = check()
    assert result.exit_code == 1, result.output
    assert "effective date" in _screen(result)


# --- M7, M8, M11: malformed, unjudged, and the evidence -----------------------------


DELETE = object()

# Each case is an override on a block that is otherwise well formed, so that the
# check under test is the one that fires. Written as a full valid base rather
# than as hand-built fragments because the first version of this table left
# three cases refused by an EARLIER check than the one they were written for —
# and a mutant removing the check they named survived the test that named it.
MALFORMED = {
    "no-verdict": {"verdict": DELETE},
    "unknown-verdict": {"verdict": "ok"},
    "empty-refutation": {"attempted_refutation": "  "},
    "missing-refutation": {"attempted_refutation": DELETE},
    "refutation-not-a-string": {"attempted_refutation": 1},
    "no-author": {"judged_by": DELETE},
    "blank-author": {"judged_by": "   "},
    "claims-reproducible": {"reproducible": True},
    "no-honesty-flag": {"reproducible": DELETE},
    "risk-not-a-string": {"residual_risk": 7},
}


def malformed_block(series, name):
    """A well-formed block with exactly one thing wrong with it."""
    block = {
        "verdict": "supported",
        "attempted_refutation": REFUTATION,
        "judged_by": JUDGE,
        "judged_at": days_ago(1),
        "reproducible": False,
        "claim_sha256": V.claim_sha256(read_ledger_file(series)["claims"][0]),
    }
    for key, value in MALFORMED[name].items():
        if value is DELETE:
            block.pop(key, None)
        else:
            block[key] = value
    return block


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_a_malformed_adversarial_block_never_passes(series, name):
    """M7 and M11. D-113's rule, one door along: a block this code cannot read
    is `open`, never `supported`. `attempted_refutation` is required and
    non-empty — a `supported` with no account of what was attacked records only
    that somebody looked, and that is what the other four overclaims (D-106,
    D-110, D-112, D-118) all were. `judged_by` is required for the same reason
    §8.4's override needs a name: a judgement nobody signed is not one."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    set_block(series, malformed_block(series, name))
    record = read_ledger_file(series)["claims"][0]
    assert V.classify(record) == "open"
    assert V.is_blocking(record) is True
    result = approve()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "in_review"


@pytest.mark.parametrize("block", [{}, "supported", [1], 7])
def test_an_adversarial_block_of_the_wrong_shape_never_passes(series, block):
    """M7's other half: an empty object, and a block that is not an object."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    set_block(series, block)
    assert V.classify(read_ledger_file(series)["claims"][0]) == "open"
    assert approve().exit_code == 1
    assert status_on_disk(series) == "in_review"


def test_a_malformed_block_does_not_get_its_residual_risk_quoted(series):
    """A block nothing can read must not have half of it printed as though the
    rest were sound — the screen would be quoting a risk out of a record whose
    verdict nobody could parse."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    block = malformed_block(series, "unknown-verdict")
    block["residual_risk"] = RISK
    set_block(series, block)
    assert "effective date" not in _screen(review())
    assert "effective date" not in _screen(check())


def test_an_unjudged_claim_is_not_a_badly_judged_one(series):
    """M8, R3's negative half. "Nobody has attacked this yet" and "somebody
    wrote a judgement nobody can read" are different facts with different
    remedies — run pass 2, versus find out what happened to the one that ran."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    unjudged = read_ledger_file(series)["claims"][0]
    assert V.adversarial_state(unjudged)[0] == "unjudged"
    assert V.classify(unjudged) == "verified"

    set_block(series, {"verdict": "supported"})
    malformed = read_ledger_file(series)["claims"][0]
    state, why = V.adversarial_state(malformed)
    assert state == "malformed"
    assert V.classify(malformed) == "open"
    assert why and "not been" not in why


def test_the_screen_says_how_many_claims_pass_2_has_not_reached(series):
    """M8 on the screen. An episode approved with pass 2 never run is a normal,
    allowed thing — and it must not look like an episode pass 2 cleared."""
    episode(series, [clean_beat(), second_beat()])
    assert check().exit_code == 0
    assert judge(claim="c-001").exit_code == 0
    result = check()
    assert result.exit_code == 0, result.output
    line = next(
        line for line in result.output.splitlines() if line.lower().startswith("pass 2")
    )
    assert "1 of 2" in line


def test_the_coverage_line_is_printed_when_pass_2_has_judged_nothing(series):
    """M8's loudest case, and the one a banner printed only on judged episodes
    would lose: an episode nothing has attacked must say so on the screen the
    operator reads before signing. Zero is the number this line exists for."""
    episode(series, [clean_beat()])
    result = check()
    assert result.exit_code == 0, result.output
    line = next(
        line for line in result.output.splitlines() if line.lower().startswith("pass 2")
    )
    assert "0 of 1 claim" in line
    assert "0 of 1 claim" in next(
        line for line in review().output.splitlines()
        if line.lower().startswith("pass 2")
    )


def test_the_approval_record_says_what_pass_2_covered(series):
    """M8, M12, in the artifact a human commits. An approval that cannot say how
    much of it was attacked is a signature on an unnamed document."""
    episode(series, [clean_beat(), second_beat()])
    assert check().exit_code == 0
    assert judge(claim="c-001").exit_code == 0
    assert approve().exit_code == 0
    record = approval_on_disk(series)["adversarial"]
    assert record["judged"] == 1
    assert record["unjudged"] == 1
    assert record["reproducible"] is False


def test_the_writer_refuses_an_empty_attempted_refutation(series):
    """M11 at the other end. The gate refuses a blank refutation on disk; this
    stops one being written in the first place, where the remedy is cheap."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = judge(refutation="   ")
    assert result.exit_code == 1, result.output
    assert "refut" in result.output.lower()
    assert block_of(series) is None


def test_the_writer_refuses_a_judgement_nobody_signed(series):
    """A judgement is somebody's argument. `--by` carries the refuter's identity
    — which model, run under which skill — and it is the only thing in the
    record that says what made this call. §8.4 asks a human for a name on an
    override for the same reason."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = judge(by="   ")
    assert result.exit_code == 1, result.output
    assert "author" in result.output.lower()
    assert block_of(series) is None


def test_the_writer_refuses_a_verdict_it_does_not_know(series):
    """M7 at the other end: `supported · unsupported · refuted`, and nothing else
    reaches the file to be misread later."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = judge(verdict="probably")
    assert result.exit_code == 1, result.output
    assert block_of(series) is None


# --- M9: one classify -------------------------------------------------------------


def test_the_gate_and_every_screen_share_one_classify():
    """M9. Not "they agree" — the same object (D-059, D-113)."""
    assert video_cli.classify is V.classify
    assert video_cli.is_blocking is V.is_blocking
    assert video_cli.adversarial_state is V.adversarial_state


def test_no_other_module_subscripts_the_adversarial_field():
    """M9, the assertion the test above describes — written as a source scan
    over subscripts and `.get`, which is how the field would actually be read."""
    for path in sorted(Path("src/agenticsocial/video").glob("*.py")):
        if path.name == "verify.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                index = node.slice
                assert not (
                    isinstance(index, ast.Constant) and index.value == "adversarial"
                ), f"{path.name} reads the adversarial field itself"
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "adversarial"
            ):
                raise AssertionError(f"{path.name} reads the adversarial field itself")


def test_classify_answers_pass_2_too(series):
    """M9. One record, one answer — pass 2 is a fourth input to `classify`, not
    a second function that also decides."""
    cases = [
        ({"verdict": "supported"}, "verified"),
        ({"verdict": "refuted"}, "open"),
        ({"verdict": "unsupported"}, "open"),
        (None, "verified"),
    ]
    for block, expected in cases:
        record = {
            "id": "c-001", "beat_index": 0, "text": "t", "src": "s", "quote": "q",
            "mechanical": {"verdict": "pass"},
            "adversarial": None if block is None else {
                "attempted_refutation": REFUTATION,
                "judged_by": JUDGE,
                "judged_at": days_ago(1),
                "reproducible": False,
                **block,
            },
        }
        if record["adversarial"]:
            record["adversarial"]["claim_sha256"] = V.claim_sha256(record)
        assert V.classify(record) == expected, block
        assert V.is_blocking(record) is (expected == "open")


def test_an_override_is_still_the_only_way_past_a_refuted_claim(series):
    """§8.4: the override clears any refusal, and it costs a written sentence
    with a name on it. A pass-2 refusal is not a special case with no exit."""
    episode(series, [clean_beat(claim_override=dict(OVERRIDE))])
    assert check().exit_code == 0
    assert judge(verdict="refuted").exit_code == 0
    record = read_ledger_file(series)["claims"][0]
    assert V.classify(record) == "overridden"
    assert V.stale_override(record) is None, "it is doing work; it is not stale"
    result = approve()
    assert result.exit_code == 0, result.output
    assert approval_on_disk(series)["overrides"][0]["id"] == "c-001"


# --- M10, R5: a verdict is bound to the claim it judged -----------------------------


def test_a_pass_2_verdict_does_not_survive_an_edit_to_the_beat_it_judged(series):
    """M10, R5. Rewrite the sentence and the judgement is about words nobody
    wrote — the same lie as a stale ledger, through the other door."""
    ep = episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    write_script(ep, [clean_beat(text="DeepSeek's flagship is a 1.6T MoE system.")])
    assert check().exit_code == 0
    assert block_of(series) is None, "a verdict about other words was carried over"


def test_a_hand_edited_claim_leaves_its_verdict_stale_at_the_gate(series):
    """M10. The carry-forward rule is not trusted: the gate re-checks the
    binding, because `claims.json` is a file on disk (D-114's re-validation)."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["adversarial"]["claim_sha256"] = "0" * 64
    write_ledger_file(series, ledger)
    record = read_ledger_file(series)["claims"][0]
    assert V.adversarial_state(record)[0] == "stale"
    assert V.classify(record) == "open"
    result = approve()
    assert result.exit_code == 1, result.output
    assert status_on_disk(series) == "in_review"


def test_an_unchanged_claim_keeps_its_verdict_across_a_re_check(series):
    """M10's negative half, and the reason the binding is per-claim rather than
    per-ledger: one refuter per claim, ~24 an episode. If every re-check threw
    all of them away, an operator who fixes one beat pays for 24 judgements, and
    a pass that expensive is a pass people stop running."""
    ep = episode(series, [clean_beat(), fabricated_beat()])
    assert check().exit_code == 1
    assert judge(claim="c-001", risk=RISK).exit_code == 0
    write_script(ep, [clean_beat(), second_beat()])
    assert check().exit_code == 0
    carried = block_of(series)
    assert carried is not None and carried["residual_risk"] == RISK
    assert V.classify(read_ledger_file(series)["claims"][0]) == "verified"


def test_the_verdict_is_bound_to_the_source_and_quote_as_well_as_the_text(series):
    """R5. Re-citing the same sentence to a different quote is a different
    claim, even when the beat text is byte-identical."""
    ep = episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    write_script(
        ep, [clean_beat(quote="DeepSeek's 1.6T MoE flagship quietly moved")]
    )
    assert check().exit_code == 0
    assert block_of(series) is None


# --- M12: pass 2 is not reproducible, and the ledger says so ------------------------


def test_the_record_itself_says_pass_2_is_not_reproducible(series):
    """M12. Visible without the spec: the block carries `reproducible: false`,
    an author, and a `judged_at` that is deliberately not called `checked_at`."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    ledger = read_ledger_file(series)
    block = ledger["claims"][0]["adversarial"]
    assert block["reproducible"] is False
    assert "checked_at" not in block, "pass 1's word for pass 2's answer"
    assert block["judged_by"]
    assert ledger["claims"][0]["mechanical"].keys().isdisjoint(
        {"reproducible", "judged_by", "judged_at"}
    ), "the mechanical block must not borrow pass 2's vocabulary"


def test_a_block_claiming_to_be_reproducible_is_malformed(series):
    """M12 with teeth. The honesty flag is checked, not decorative: a ledger
    that says a judgement is reproducible is a ledger nobody may act on."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["adversarial"]["reproducible"] = True
    write_ledger_file(series, ledger)
    assert V.classify(read_ledger_file(series)["claims"][0]) == "open"
    assert approve().exit_code == 1
    assert status_on_disk(series) == "in_review"


def test_the_screen_calls_pass_2_a_judgement_and_names_who_made_it(series):
    """M12 on the screen. Pass 1's verdicts carry no author because there is
    none; a judgement that names nobody reads like a measurement."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    screen = _screen(review())
    assert "not reproducible" in screen
    assert JUDGE.lower() in screen


def test_a_supported_verdict_expires(series):
    """M12, the expiry decision. The corpus and the script are covered by
    digests; the JUDGE is not. Nothing on disk can compare the model, the prompt
    or what the world knew that day, so the only honest control left is time."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["adversarial"]["judged_at"] = days_ago(
        V.PASS2_HORIZON_DAYS + 1
    )
    write_ledger_file(series, ledger)
    record = read_ledger_file(series)["claims"][0]
    assert V.adversarial_state(record)[0] == "expired"
    assert V.classify(record) == "open"
    result = approve()
    assert result.exit_code == 1, result.output
    assert "expire" in _screen(result)
    assert status_on_disk(series) == "in_review"


def test_a_verdict_inside_the_horizon_does_not_expire(series):
    """The negative half — an expiry that fires on a fresh judgement is an
    expiry operators route around."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["adversarial"]["judged_at"] = days_ago(
        V.PASS2_HORIZON_DAYS - 1
    )
    write_ledger_file(series, ledger)
    assert V.classify(read_ledger_file(series)["claims"][0]) == "verified"
    assert approve().exit_code == 0


def test_an_expired_refutation_still_reads_as_refuted(series):
    """The ordering, argued: age makes a `supported` less believable and does
    not make a `refuted` less alarming. "Re-judge this" is the wrong remedy to
    print over "a refuter knocked this claim over"."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="refuted").exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["adversarial"]["judged_at"] = days_ago(
        V.PASS2_HORIZON_DAYS + 30
    )
    write_ledger_file(series, ledger)
    assert V.adversarial_state(read_ledger_file(series)["claims"][0])[0] == "refuted"


def test_an_unreadable_judged_at_is_malformed_not_forever_fresh(series):
    """Fail closed: a timestamp nothing can parse must not read as "not
    expired". D-106's shape is a value the rule cannot read treated as fine."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge().exit_code == 0
    ledger = read_ledger_file(series)
    ledger["claims"][0]["adversarial"]["judged_at"] = "last tuesday"
    write_ledger_file(series, ledger)
    assert V.classify(read_ledger_file(series)["claims"][0]) == "open"


# --- the gated write --------------------------------------------------------------


def test_the_writer_takes_identifiers_not_objects(series):
    """D-072. There must be no argument a caller can shape into a verdict about
    a claim other than the one on disk."""
    params = inspect.signature(V.record_adversarial, eval_str=True).parameters
    forbidden = {"ledger", "record", "claims", "script", "series"}
    assert forbidden.isdisjoint(params)


def test_the_writer_refuses_when_the_ledger_is_stale(series):
    """A judgement recorded against a ledger that no longer describes the script
    is a judgement of words nobody wrote — refused at the door, not stored and
    quietly ignored later."""
    ep = episode(series, [clean_beat()])
    assert check().exit_code == 0
    write_script(ep, [clean_beat(text="DeepSeek's flagship is a 1.6T MoE system.")])
    result = judge()
    assert result.exit_code == 1, result.output
    assert "check" in result.output.lower()


def test_the_writer_refuses_when_there_is_no_ledger_at_all(series):
    """Pass 2 runs on claims that survived pass 1. There is nothing to judge
    before `check` has said what the claims are."""
    episode(series, [clean_beat()])
    result = judge()
    assert result.exit_code == 1, result.output
    assert "check" in result.output.lower()


def test_the_writer_refuses_an_unknown_claim_id(series):
    """A verdict silently dropped because the id was a typo is worse than a
    refusal: the skill would report 24 judgements and the ledger would hold 23."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = judge(claim="c-099")
    assert result.exit_code == 1, result.output
    assert "c-099" in result.output


def test_the_writer_refuses_to_judge_a_claim_pass_1_did_not_clear(series):
    """§8.3: one subagent per claim THAT SURVIVES PASS 1. A `supported` on a
    claim pass 1 already refused reads, on every later screen, like a claim with
    two verdicts that disagree."""
    episode(series, [fabricated_beat()])
    assert check().exit_code == 1
    result = judge()
    assert result.exit_code == 1, result.output
    assert "pass 1" in result.output.lower()
    assert block_of(series) is None


def test_a_verdict_can_be_re_judged(series):
    """The remedy for an expired or stale verdict has to exist: recording again
    replaces the block rather than refusing because one is already there."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    assert judge(verdict="supported").exit_code == 0
    assert judge(verdict="refuted", refutation="Second pass: the GA date is "
                 "not in the source at all.").exit_code == 0
    block = block_of(series)
    assert block["verdict"] == "refuted"
    assert "Second pass" in block["attempted_refutation"]


def test_the_judge_command_offers_no_way_to_supply_the_ledger():
    """D-072's CLI half — an option is an argument a caller can shape."""
    result = run("video", "judge", "--help")
    assert result.exit_code == 0
    for flag in ("--ledger", "--claims", "--force", "--skip", "--checked-at"):
        assert flag not in result.output


def test_the_judge_command_says_what_it_wrote_and_what_it_is(series):
    """The screen after a write. An agent that records 24 verdicts and is told
    nothing cannot tell a stored judgement from a swallowed one."""
    episode(series, [clean_beat()])
    assert check().exit_code == 0
    result = judge(risk=RISK)
    assert result.exit_code == 0, result.output
    assert "c-001" in result.output
    assert "supported" in result.output
    assert "not reproducible" in _screen(result)

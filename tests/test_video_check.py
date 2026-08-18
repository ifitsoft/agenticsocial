"""`agsoc video check`, the verdicts in `review`, and §8.4's override — spec §8.1/§8.2/§8.4.

The screen is the product. Tasks 1 and 2 built extraction and the mechanical
pass; a `fail` with a claim id is a true statement and a useless one, so most of
this file is about whether an operator can *act* on what is printed.

Three habits, each because the matching mutant is a one-line source edit:

  * **Assert on the exit code AND the output AND `result.exception`** (D-035).
    A `CliRunner` that swallows a traceback reports the same exit code as a
    clean refusal, and this project has been bitten by exactly that.
  * **Nothing on this screen may be untruncated or unescaped.** A quote is
    operator-authored text of unbounded length carrying whatever bytes a YAML
    block scalar allows; the table's readability (D-074) and D-095's control
    mapping are both load-bearing for a screen that is meant to be *scanned*.
  * **A stale ledger is worse than an absent one**, because it looks like
    verification. Every staleness assertion here also pins the negative half —
    a current ledger shows verdicts and no warning at all.
"""
import inspect
import json

import pytest
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import cli as video_cli
from agenticsocial.video import corpus
from agenticsocial.video import script as S
from agenticsocial.video import verify as V
from agenticsocial.video.episode import create_episode, load_episode
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

SOURCE = (
    "DeepSeek's 1.6T MoE flagship quietly moved from preview to general "
    "availability this week, then announced new pricing starting August 16 at "
    "about $1.32 / $3.96 per 1M tokens (in/out). Alibaba's Qwen3.8-Max, at "
    "roughly 2.4 trillion parameters with about 95B active, is the largest "
    "open-weight release so far."
)


def write_script(ep, beats, status="draft"):
    # The id is QUOTED: `episode: 2026-08-17` unquoted is a YAML date.
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f"---\nepisode: '{ep.id}'\nseries: the-brief\nstatus: {status}\n---\n{body}",
        encoding="utf-8",
    )


def episode(series, beats, sources=None, ep_id=EP, status="draft"):
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
    """The Task 2 case: a figure invented in good faith, absent from the source."""
    beat = {
        "type": "statement",
        "hold": 3.0,
        "text": "DeepSeek's old price was $0.11 per 1M tokens.",
        "src": "local-ai-zone",
        "quote": "announced new pricing starting August 16",
    }
    beat.update(over)
    return beat


def ledger_of(series, ep_id=EP):
    return json.loads(
        (load_episode(series, ep_id).dir / "claims.json").read_text(encoding="utf-8")
    )


def printable(text):
    """Every character a terminal would be asked to interpret, other than \\n."""
    return sorted({c for c in text if ord(c) < 0x20 and c != "\n"} | {c for c in text if ord(c) == 0x7F})


# --- R1 / M1 — the gate takes identifiers, and verifies what is on disk ---------------


def test_check_takes_identifiers_and_no_caller_built_object(series):
    """precondition: D-072/D-059 — every bypass in this project was a trusted
    in-memory object, and one of them published a draft.

    The property is not "it re-reads": it is that the command accepts nothing a
    caller could shape. A `Script` or `Episode` parameter is the mutant, and it
    is visible in the signature.
    """
    sig = inspect.signature(video_cli.video_check)
    assert [p.name for p in sig.parameters.values()] == ["episode", "series"]
    for p in sig.parameters.values():
        assert p.annotation is str, f"`{p.name}` takes {p.annotation!r}, not an identifier"


def test_check_verifies_the_script_on_disk_after_it_changes(series):
    """precondition: the first run passes, so a second run reporting `pass` is
    not trivially right.

    The behavioural half of M1. An implementation holding on to anything loaded
    before the fabricated figure was written answers `pass` twice.
    """
    ep = episode(series, [clean_beat()])
    first = run("video", "check", EP, "--series", "the-brief")
    assert first.exit_code == 0, first.output

    write_script(ep, [fabricated_beat()])
    second = run("video", "check", EP, "--series", "the-brief")
    assert second.exit_code == 1, second.output
    assert "0.11" in second.output


# --- R2 / M2, M3, M4 — the exit code -------------------------------------------------


def test_a_failing_claim_exits_non_zero_and_says_which(series):
    """precondition: the figure is absent from the source by value, not by
    spelling — `0.11` is nowhere in it in any notation."""
    episode(series, [clean_beat(), fabricated_beat()])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1
    assert "fail" in result.output
    assert "c-002" in result.output, result.output
    assert "0.11" in result.output


def test_a_clean_episode_exits_zero_and_says_so(series):
    """precondition: R2's negative half. A gate that refuses everything is not a
    gate, and a check nobody can pass is one operators route around."""
    episode(series, [clean_beat(), clean_beat()])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "fail" not in result.output
    assert "2" in result.output


def test_a_beat_with_no_source_exits_non_zero(series):
    """precondition: §8.4 lists `no_source` beside `fail`. They are different
    problems — one is a rewrite, the other a citation — and both refuse."""
    episode(series, [{"type": "body", "hold": 3.0, "text": "Prices moved a lot."}])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1
    assert "no_source" in result.output


def test_an_unattested_manual_claim_blocks(series):
    """precondition: §8.4 — "or an unattested `manual`".

    Asserted on the predicate rather than through YAML because `script.py`
    refuses an empty `attest` at load today, so the CLI path cannot construct
    one. That agreement is checked below; this is the half that must not depend
    on it. A `manual` treated as a pass is M4.
    """
    record = {"mechanical": {"verdict": "manual", "attest": "   "}, "override": None}
    assert video_cli.is_blocking(record) is True


def test_an_attested_manual_claim_does_not_block(series):
    """precondition: M4's negative half. `custom` is `manual` by design (D-088)
    and an attested one is approvable — otherwise `custom` is unusable."""
    record = {
        "mechanical": {"verdict": "manual", "attest": "Draws the price ladder."},
        "override": None,
    }
    assert video_cli.is_blocking(record) is False


def test_a_custom_beat_with_its_attestation_exits_zero_and_shows_the_sentence(series):
    """precondition: the script-level half of M4 — the schema and the gate agree
    that an attestation is what makes a `manual` claim approvable."""
    episode(
        series,
        [
            {
                "type": "custom",
                "hold": 3.0,
                "js": "c.fillRect(0,0,10,10)",
                "attest": "Draws the price ladder from the two figures above.",
            }
        ],
    )
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "manual" in result.output
    assert "Draws the price ladder" in result.output


def test_the_schema_refuses_the_empty_attestation_the_gate_would_block(series):
    """precondition: the two rules above are only consistent if this holds."""
    ep = create_episode(series, EP)
    write_script(ep, [{"type": "custom", "hold": 3.0, "js": "x", "attest": ""}])
    with pytest.raises(S.ScriptError) as e:
        S.load_script(load_episode(series, EP))
    assert "attest" in str(e.value)


# --- the ledger `check` writes -------------------------------------------------------


def test_check_writes_the_ledger_beside_the_script(series):
    """precondition: §8.1 — `claims.json` is the artifact the human adjudicates,
    and Phase 7's gate reads it rather than re-running the check."""
    ep = episode(series, [clean_beat()])
    run("video", "check", EP, "--series", "the-brief")
    ledger = json.loads((ep.dir / "claims.json").read_text(encoding="utf-8"))
    assert ledger["episode"] == EP
    assert isinstance(ledger["corpus_sha"], str) and ledger["corpus_sha"]
    assert [c["mechanical"]["verdict"] for c in ledger["claims"]] == ["pass"]


def test_re_running_an_unchanged_check_leaves_the_file_byte_identical(series):
    """precondition: `checked_at` is a clock reading, so the naive version
    rewrites the file every run and the ledger becomes a diff nobody reads."""
    ep = episode(series, [clean_beat()])
    run("video", "check", EP, "--series", "the-brief")
    before = (ep.dir / "claims.json").read_bytes()
    run("video", "check", EP, "--series", "the-brief")
    assert (ep.dir / "claims.json").read_bytes() == before


def test_an_unreadable_script_is_reported_not_crashed(series):
    """precondition: D-035 — a traceback through `CliRunner` and a refusal look
    the same to a test that only reads the exit code."""
    ep = create_episode(series, EP)
    ep.script_path.write_text("---\nepisode: '2026-08-17'\n---\nbeats: 3\n", encoding="utf-8")
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "beats" in result.output


# --- the failure screen is meant to be acted on --------------------------------------


def test_a_missing_quote_reports_the_nearest_thing_the_source_says(series):
    """precondition: §8.2 — "near-misses report as failures with the closest
    candidate span attached, so the human sees *why* rather than a bare red
    mark". A bare red mark is what teaches people to override without looking."""
    episode(
        series,
        [
            clean_beat(
                quote="DeepSeek's 1.6T MoE flagship was retired from preview",
            )
        ],
    )
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1
    assert "quietly moved" in result.output, result.output


def test_an_entity_miss_is_shown_as_recorded_not_gated(series):
    """precondition: D-102 — 35% of entity atoms on the real brief are unfindable
    and not one was a real error. The display must not let that read as a check
    that passed, and must not let it read as a refusal either."""
    episode(series, [clean_beat(text="Mistral Nemotron ships a 1.6T MoE flagship.")])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "Mistral Nemotron" in result.output
    assert "not gated" in result.output


# --- R5 / M9, M10, M11 — `claim_override` is a mapping (D-103) ------------------------


OVERRIDE = {"reason": "Framed as expectation, not fact.", "by": "Ali Abdukarim"}


def test_the_spec_8_4_override_loads_verbatim(series):
    """precondition: §8.4's own YAML example was refused at load before D-103.

    `reason` plus `by` is what makes an override "a written sentence with your
    name on it" rather than a checkbox — the asymmetry §8.4 is built on.
    """
    ep = episode(series, [clean_beat(claim_override=dict(OVERRIDE))])
    script = S.load_script(ep)
    assert script.beats[0].fields["claim_override"] == OVERRIDE


BAD_OVERRIDES = [
    ("a bare string", "Framed as expectation. — Ali"),
    ("a list", [{"reason": "r", "by": "b"}]),
    ("no reason", {"by": "Ali Abdukarim"}),
    ("no by", {"reason": "Framed as expectation, not fact."}),
    ("an empty reason", {"reason": "", "by": "Ali Abdukarim"}),
    ("a blank reason", {"reason": "   ", "by": "Ali Abdukarim"}),
    ("an empty by", {"reason": "Framed as expectation.", "by": ""}),
    ("a blank by", {"reason": "Framed as expectation.", "by": "\t"}),
    ("a non-string reason", {"reason": 3, "by": "Ali"}),
    ("a non-string by", {"reason": "Framed as expectation.", "by": ["Ali"]}),
    ("an unknown key", {"reason": "r", "by": "b", "approved": True}),
]


@pytest.mark.parametrize("what,bad", BAD_OVERRIDES, ids=[w for w, _ in BAD_OVERRIDES])
def test_an_override_that_is_not_a_written_sentence_with_a_name_is_refused(
    series, what, bad
):
    """precondition: M9 and M10. §8.4 — "passing verification is automatic;
    bypassing it costs you a written sentence with your name on it". An empty
    `reason` is a checkbox, which is the one thing §8.4 says it must never be,
    and a bare string loses the name entirely."""
    ep = create_episode(series, EP)
    write_script(ep, [clean_beat(claim_override=bad)])
    with pytest.raises(S.ScriptError) as e:
        S.load_script(load_episode(series, EP))
    assert "claim_override" in str(e.value)


def test_an_absent_override_is_the_normal_case(series):
    """precondition: R5's negative half — overrides are rare, and a schema that
    demanded one would be absurd."""
    ep = episode(series, [clean_beat()])
    assert "claim_override" not in S.load_script(ep).beats[0].fields
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output


def test_the_override_rides_into_the_ledger_as_a_mapping(series):
    """precondition: Phase 7's gate reads `claims.json`, not `script.yaml`. An
    override that does not survive into the artifact is not an override."""
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    run("video", "check", EP, "--series", "the-brief")
    assert ledger_of(series)["claims"][0]["override"] == OVERRIDE


def test_an_overridden_claim_is_never_reported_as_a_pass(series):
    """precondition: M11. The verdict is what was measured; the override is what
    a human decided about it. A display that collapses the two hides both."""
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    result = run("video", "check", EP, "--series", "the-brief")
    assert "fail" in result.output
    assert "Ali Abdukarim" in result.output
    assert "Framed as expectation" in result.output
    assert result.exit_code == 1, result.output


# --- R3 / M5, M6 — `review` shows the quote ------------------------------------------


QUOTED_TYPES = {
    "statement": {"text": "The flagship is a 1.6T MoE model."},
    "body": {"text": "The flagship is a 1.6T MoE model."},
    "list": {"lead": "Two things", "items": ["1.6T MoE", "GA this week"]},
    "kpis": {"items": [{"value": 1.6, "unit": "T", "label": "parameters", "decimals": 1}]},
    "jumpChart": {
        "rows": [
            {"label": "input", "before": 1.32, "after": 3.96, "shown": "1.32 &rarr; 3.96"}
        ],
        "scale": 10,
        "footnote": "Prices per 1M tokens, as published.",
    },
    "quote": {"text": "It moved to GA.", "attribution": "DeepSeek"},
    "dumbbell": {
        "rows": [{"label": "price", "values": [0.3, 0.9], "note": "up"}],
        "series": ["before", "after"],
        "caption": "Prices moved",
        "footnote": "Direction only — the source reports a range.",
    },
}


@pytest.mark.parametrize("beat_type", sorted(QUOTED_TYPES))
def test_review_shows_the_quote_for_every_type_that_can_carry_one(series, beat_type):
    """precondition: M5 — a display keyed on beat type shows the citation for the
    types its author was thinking about and hides it for the rest.

    Phase 3 named this gap: an operator sees `src` — that a citation exists —
    but never what the source actually says. That is the difference between
    "this beat is cited" and "this beat is true".
    """
    mark = "quietly moved from preview"
    beat = dict(
        {"type": beat_type, "hold": 3.0, "src": "local-ai-zone", "quote": f"flagship {mark}"},
        **QUOTED_TYPES[beat_type],
    )
    episode(series, [beat])
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert mark in result.output, result.output


def test_review_stays_inside_its_width_however_long_the_quote_is(series):
    """precondition: M6 and D-074 — the first real twelve-beat run came out 156
    columns wide, every row wrapped, and a table whose rows wrap is not a table.
    A quote is unbounded operator text and is the obvious way to bring that back.
    """
    long_quote = "DeepSeek's 1.6T MoE flagship quietly moved from preview to general availability this week, then announced new pricing starting August 16 at about $1.32 / $3.96 per 1M tokens (in/out)."
    episode(series, [clean_beat(quote=long_quote)])
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    over = [line for line in result.output.splitlines() if len(line) > video_cli.ROW_WIDTH]
    assert not over, over
    assert "DeepSeek's 1.6T MoE flagship" in result.output


def test_review_shows_the_verdict_beside_the_beat_it_belongs_to(series):
    """precondition: two beats with different verdicts, so a display that prints
    one verdict everywhere cannot pass."""
    episode(series, [clean_beat(), fabricated_beat()])
    run("video", "check", EP, "--series", "the-brief")
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    rows = [line for line in result.output.splitlines() if "  0  " in line or "  1  " in line]
    passing = [r for r in rows if "pass" in r]
    failing = [r for r in rows if "fail" in r]
    assert len(passing) == 1 and len(failing) == 1, result.output
    assert " 0 " in passing[0] and " 1 " in failing[0]


# --- R4 / M7, M8 — a stale ledger is worse than an absent one ------------------------


def test_a_ledger_whose_corpus_has_changed_is_reported_stale_and_shows_no_verdicts(series):
    """precondition: M7. `claims.json` records `corpus_sha` precisely so this is
    answerable; recording it and never comparing is a field, not a guarantee.

    A stale ledger displayed as current is worse than no ledger at all, because
    it looks like verification.
    """
    ep = episode(series, [clean_beat()])
    run("video", "check", EP, "--series", "the-brief")
    corpus.write_document(
        ep,
        SOURCE.replace("1.6T", "9.9T"),
        url="https://local-ai-zone.example/x",
        key="local-ai-zone",
        fetched_at="2026-08-17",
        replace=True,
    )
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "stale" in result.output.lower()
    assert "pass" not in result.output, result.output


def test_a_current_ledger_is_shown_normally_with_no_scary_noise(series):
    """precondition: M8's negative half — a warning that fires on every healthy
    episode is one operators learn to scroll past, and then the real one goes
    with it."""
    episode(series, [clean_beat()])
    run("video", "check", EP, "--series", "the-brief")
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "stale" not in result.output.lower()
    assert "pass" in result.output


def test_review_without_a_ledger_says_to_run_check_and_does_not_cry_wolf(series):
    """precondition: absent and stale are different states. "Not checked yet" is
    the normal state of a script an agent has just written."""
    episode(series, [clean_beat()])
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "agsoc video check" in result.output
    assert "stale" not in result.output.lower()


def test_a_ledger_written_for_a_script_that_has_since_changed_is_stale(series):
    """precondition: the corpus is untouched, so `corpus_sha` alone answers
    "current". A verdict shown against a beat that has been rewritten since is
    the same lie as a stale corpus, arriving by the other door."""
    ep = episode(series, [clean_beat()])
    run("video", "check", EP, "--series", "the-brief")
    write_script(ep, [fabricated_beat()])
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "stale" in result.output.lower()
    assert "pass" not in result.output


def test_an_unreadable_ledger_does_not_take_the_review_screen_down(series):
    """precondition: `review` is a REPORT (D-018). A diagnostic command that
    refuses to speak when something is wrong takes away the one screen that
    would have explained the problem."""
    ep = episode(series, [clean_beat()])
    (ep.dir / "claims.json").write_text("{not json", encoding="utf-8")
    result = run("video", "review", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "claims.json" in result.output
    assert "DeepSeek" in result.output


# --- D-095 / M12 — nothing authored reaches the terminal as a control sequence --------

HOSTILE = "\x1b[2J\x1b[31mVERIFIED\x07\r\n\x00"


def test_no_control_character_from_a_beat_reaches_the_check_screen(series):
    """precondition: M12/D-095 — `shown` and every other authored field is
    operator text, and a screen a human approves is a screen that can be
    spoofed. `_one_line` maps C0 and DEL to spaces; losing that on the new
    fields is a one-line mutant."""
    episode(
        series,
        [
            clean_beat(
                text=f"Prices {HOSTILE} moved",
                quote=f"announced new pricing {HOSTILE}",
                kicker=HOSTILE,
                act=HOSTILE,
            )
        ],
    )
    result = run("video", "check", EP, "--series", "the-brief")
    assert printable(result.output) == [], printable(result.output)


def test_no_control_character_from_a_beat_reaches_the_review_screen(series):
    """precondition: the same fields, on the screen that is read more often."""
    episode(
        series,
        [
            clean_beat(
                text=f"Prices {HOSTILE} moved",
                quote=f"announced new pricing {HOSTILE}",
                kicker=HOSTILE,
                act=HOSTILE,
            )
        ],
    )
    run("video", "check", EP, "--series", "the-brief")
    result = run("video", "review", EP, "--series", "the-brief")
    assert printable(result.output) == [], printable(result.output)


# --- the summary line ----------------------------------------------------------------


def test_check_counts_every_claim_and_names_the_ones_that_refuse(series):
    """precondition: a mixed episode. The count is the only part of this screen
    an operator reads when they are in a hurry, so it must be arithmetic rather
    than an impression."""
    episode(
        series,
        [
            clean_beat(),
            fabricated_beat(),
            {"type": "body", "hold": 3.0, "text": "Prices moved a lot."},
        ],
    )
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1
    assert "3 claims" in result.output, result.output
    assert "1 pass" in result.output
    assert "1 fail" in result.output
    assert "1 no_source" in result.output


def test_check_reports_a_missing_episode_rather_than_a_traceback(series):
    """precondition: the commonest operator typo."""
    result = run("video", "check", "2026-01-01", "--series", "the-brief")
    assert result.exit_code == 1
    assert "2026-01-01" in result.output
    assert "Traceback" not in result.output

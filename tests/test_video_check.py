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
    # eval_str: `from __future__ import annotations` makes every annotation a
    # string, and `"Script" is not str` would pass with the mutant in place.
    sig = inspect.signature(video_cli.video_check, eval_str=True)
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


def test_the_magnitude_spelling_nothing_knew_reaches_the_screen(series):
    """precondition: the source says `about 95B active`; the beat says `950bn`,
    which is ten times more, and `check` printed `pass` for it.

    F1/M9. Every fix in this task has to be reachable from `agsoc video check`
    on a real episode, not only from a unit test — the gate review reproduced
    this defect through this command, on the operator's own content, and a
    silent exemption in `claims.py` is only a defect once it is a green line on
    this screen.
    """
    episode(series, [clean_beat(
        text="About 950bn parameters are active.",
        quote="roughly 2.4 trillion parameters with about 95B active",
    )])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1, result.output
    assert "fail" in result.output
    assert "950" in result.output


def test_a_figure_check_cannot_read_is_named_on_the_screen(series):
    """precondition: `3/4` is not digits-and-separators, so it produced no atom
    and the claim reported `pass` with nothing checked at all.

    M8/M9. The operator can act on "I cannot read 3/4 and the quote does not
    spell it" and is misled by silence; the token has to be on the screen for
    either sentence to be true.
    """
    episode(series, [clean_beat(
        text="Nearly 3/4 of the fleet moved.",
        quote="quietly moved from preview to general availability",
    )])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1, result.output
    assert "3/4" in result.output


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
    a human decided about it. A display that collapses the two hides both.

    Phase 7 Task 2 applied the override, so this claim no longer BLOCKS — and
    that is exactly when the display matters most: the exit code now says
    "approvable" and only these lines say why.
    """
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    result = run("video", "check", EP, "--series", "the-brief")
    assert "fail" in result.output
    assert "Ali Abdukarim" in result.output
    assert "Framed as expectation" in result.output
    assert "not verified" in result.output.lower()
    assert result.exit_code == 0, result.output


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


def test_the_check_screen_stays_inside_its_width_too(series):
    """precondition: M6 on the other screen. The failure screen carries the
    longest strings in the product — a whole quote, a reason, a source excerpt —
    and it is the screen an operator reads when they are already annoyed."""
    episode(
        series,
        [
            fabricated_beat(
                text="DeepSeek's old price was $0.11 per 1M tokens, which is a "
                "long sentence about Mistral Nemotron and Qwen and several other "
                "names nobody will find in this source at all.",
                quote="announced new pricing starting August 16 at about $1.32 / "
                "$3.96 per 1M tokens (in/out), which is a very long citation",
            )
        ],
    )
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1
    # The path to claims.json is exempt: a clipped path is a path you cannot
    # paste, and its length is the operator's own directory layout, not
    # something this screen chose.
    over = [
        line
        for line in result.output.splitlines()
        if len(line) > video_cli.ROW_WIDTH and not line.startswith("wrote ")
    ]
    assert not over, over


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
    # The banner is the longest line this screen ever prints, and it is printed
    # on the run where the operator is least inclined to read carefully.
    over = [line for line in result.output.splitlines() if len(line) > video_cli.ROW_WIDTH]
    assert not over, over


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


# --- what the sweep found: six things the screen claims to show, unpinned ------------


def test_the_failure_screen_says_what_to_do_about_each_kind_of_refusal(series):
    """precondition: the two refusals need DIFFERENT actions — one is a
    citation, the other a rewrite. A screen that names the problem and not the
    move is the bare red mark §8.2 exists to avoid, one step later."""
    episode(
        series,
        [
            fabricated_beat(),
            {"type": "body", "hold": 3.0, "text": "Prices moved a lot."},
        ],
    )
    result = run("video", "check", EP, "--series", "the-brief")
    assert "widen `quote:`" in result.output, result.output
    assert "claim_override" in result.output
    assert "cite the beat" in result.output


def test_the_failure_screen_shows_the_quote_the_claim_was_checked_against(series):
    """precondition: the whole point of the task. The operator needs the number,
    the quote it was checked against and the source it came from in one view;
    the reason alone sends them back to the file to find out what was compared.
    """
    episode(series, [fabricated_beat()])
    result = run("video", "check", EP, "--series", "the-brief")
    assert "announced new pricing starting August 16" in result.output
    assert "sources/local-ai-zone.txt" in result.output


def test_check_lists_every_claim_not_only_the_ones_that_refuse(series):
    """precondition: three claims, one refusing. A screen showing only failures
    cannot answer "was this beat checked at all?" — which is the question a
    `no_source` beat and an exempt beat give different answers to."""
    episode(series, [clean_beat(), fabricated_beat(), clean_beat()])
    result = run("video", "check", EP, "--series", "the-brief")
    for claim_id in ("c-001", "c-002", "c-003"):
        assert claim_id in result.output, result.output


def test_review_names_the_open_claims_and_why_under_the_table(series):
    """precondition: the verdict column says WHICH beat; nothing in the table
    says why. An operator working from a bare verdict is an operator overriding
    from a bare verdict."""
    episode(series, [clean_beat(), fabricated_beat()])
    run("video", "check", EP, "--series", "the-brief")
    result = run("video", "review", EP, "--series", "the-brief")
    assert "c-002" in result.output, result.output
    assert "does not contain 0.11" in result.output


def test_review_shows_an_overridden_claim_as_what_it_measured(series):
    """precondition: M11 on the review screen. The verdict is what was measured;
    the override is what a human decided about it. `pass` on that row is the one
    thing this display must never say."""
    episode(series, [fabricated_beat(claim_override=dict(OVERRIDE))])
    run("video", "check", EP, "--series", "the-brief")
    result = run("video", "review", EP, "--series", "the-brief")
    rows = [line for line in result.output.splitlines() if "  0  " in line]
    assert rows and "fail*" in rows[0], result.output
    # Everything except the pass-2 coverage banner, which is headed "pass 2 …"
    # and is about how many claims an adversarial refuter reached — not a
    # verdict on this or any other claim. The exclusion is named rather than the
    # assertion loosened: "the word `pass` is nowhere on this screen" was always
    # a whole-screen search for a four-letter string (D-118), and the property
    # this test is for is that no VERDICT on this claim reads `pass`.
    verdicts = [
        line for line in result.output.splitlines()
        if not line.lower().startswith("pass 2")
    ]
    assert "pass" not in "\n".join(verdicts)
    assert "Ali Abdukarim" in result.output


def test_an_unchecked_episode_is_not_dressed_up_as_a_warning(series):
    """precondition: M8's negative half, at the level colour actually reaches
    the terminal. "Not checked yet" is the normal state of a fresh script; a
    yellow line about it trains the operator to skip yellow lines, and the stale
    banner goes with it. Asserted with `color=True` because `CliRunner` strips
    styling by default, and the mutant is invisible without it."""
    ep = episode(series, [clean_beat()])
    fresh = runner.invoke(
        app, ["video", "review", EP, "--series", "the-brief"], color=True
    )
    # Scoped to the ledger's own line: the runtime verdict is legitimately
    # yellow on this fixture, and asserting over the whole screen would pass for
    # the wrong reason.
    note = [ln for ln in fresh.output.splitlines() if "agsoc video check" in ln]
    assert note, fresh.output
    assert "\x1b[33m" not in note[0], "an unchecked episode is not a warning"

    run("video", "check", EP, "--series", "the-brief")
    corpus.write_document(
        ep,
        SOURCE.replace("1.6T", "9.9T"),
        url="https://local-ai-zone.example/x",
        key="local-ai-zone",
        fetched_at="2026-08-17",
        replace=True,
    )
    stale = runner.invoke(
        app, ["video", "review", EP, "--series", "the-brief"], color=True
    )
    banner = [ln for ln in stale.output.splitlines() if "STALE" in ln]
    assert banner and "\x1b[33m" in banner[0], "a stale ledger IS a warning"


def test_check_reports_a_missing_episode_rather_than_a_traceback(series):
    """precondition: the commonest operator typo."""
    result = run("video", "check", "2026-01-01", "--series", "the-brief")
    assert result.exit_code == 1
    assert "2026-01-01" in result.output
    assert "Traceback" not in result.output


# --- phase 6 task 2: `check` reports the runtime (D-109 #3, #4) -----------------------
#
# `review` was the only command that mentioned runtime, and an agent that runs
# `check`, sees exit 0 and stops never learns its episode is a third of its
# target — which is exactly the state the one committed script.yaml is in. The
# runtime line is a REPORT here, as it is in `review`: it never changes the exit
# code, in either direction.


def write_script_with_pace(ep, beats, pace):
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f"---\nepisode: '{ep.id}'\nseries: the-brief\nstatus: draft\n"
        f"pace: {pace}\n---\n{body}",
        encoding="utf-8",
    )


def test_check_reports_the_runtime_and_the_tolerance(series):
    """precondition: a single 4.0s beat at pace 1.0 against a 120s ± 8s series —
    every claim passes and the episode is 116 seconds short. The claim gate and
    the length report are independent, and `check` must say both."""
    episode(series, [clean_beat(hold=4.0)])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "holds 4.0s × pace 1.0 = runtime 4.0s" in result.output
    assert "target 120s ± 8s · OUT OF TOLERANCE (-116.0s)" in result.output


def test_check_does_not_refuse_an_out_of_tolerance_episode(series):
    """precondition NEGATIVE (M6, R4's negative half). Spec §11 puts the gate at
    `approve`; a `check` that exits non-zero on length would refuse an episode
    for something that is not a claim, and it is the claim ledger the exit code
    speaks for."""
    episode(series, [clean_beat(hold=4.0)])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "verified, none open" in result.output


def test_check_reports_a_runtime_that_is_within_tolerance(series):
    """precondition NEGATIVE: the line is not a fixed string of doom. 30 beats
    of 4.0s at pace 1.0 is 120.0s dead on target."""
    ep = create_episode(series, EP)
    corpus.write_document(
        ep, SOURCE, url="https://x.example/y", key="local-ai-zone",
        fetched_at="2026-08-17",
    )
    write_script_with_pace(ep, [clean_beat(hold=4.0)] * 30, 1.0)
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "holds 120.0s × pace 1.0 = runtime 120.0s" in result.output
    assert "within tolerance (+0.0s)" in result.output


def test_check_reports_the_runtime_even_when_a_claim_fails(series):
    """precondition: the fabricated figure makes this exit 1. An author whose
    check refuses must still see the length, or they fix the claim, re-run, see
    green and ship 4 seconds of video."""
    episode(series, [fabricated_beat(hold=4.0)])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1, result.output
    assert "runtime 4.0s" in result.output


def test_check_and_review_report_the_same_runtime_lines(series):
    """precondition: two commands printing one fact from two code paths is two
    facts as soon as one changes. Both read `plan.check_runtime`."""
    episode(series, [clean_beat(hold=4.0), clean_beat(hold=2.6)])
    checked = run("video", "check", EP, "--series", "the-brief")
    reviewed = run("video", "review", EP, "--series", "the-brief")
    lines = [ln for ln in checked.output.splitlines() if "runtime" in ln or "target" in ln]
    assert lines, checked.output
    for line in lines:
        assert line in reviewed.output, f"{line!r} is not in review's output"


# --- phase 6 task 2: the two modules agree about citation (D-109 #1) -----------------


UNCITED_TYPES = {
    "statement": {"type": "statement", "text": "The flagship moved to GA."},
    "body": {"type": "body", "text": "The flagship moved to GA."},
    "list": {"type": "list", "items": ["The flagship moved to GA."]},
    "quote": {"type": "quote", "text": "we moved to GA", "attribution": "DeepSeek"},
}


@pytest.mark.parametrize("kind", sorted(UNCITED_TYPES))
def test_check_refuses_a_beat_of_any_extracted_type_that_cites_nothing(series, kind):
    """precondition: R2. `claims.EXTRACTED_TYPES` is the list of types `check`
    demands a source from, and it is the list the skill's "every beat except
    title and signoff carries src and quote" is written against. Pinned
    behaviourally so that a change to citation in `script.py` cannot silently
    take one of these off the list."""
    episode(series, [UNCITED_TYPES[kind]])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 1, result.output
    assert "no_source" in result.output


@pytest.mark.parametrize(
    "beat",
    [
        {"type": "title", "sub": "Five stories from the last 24 hours."},
        {"type": "signoff", "text": "Same time tomorrow."},
    ],
)
def test_an_exempt_type_is_asked_for_no_citation(series, beat):
    """precondition NEGATIVE (R2's negative half): the two exempt types stay
    exempt. Filing a claim on a title card would refuse every episode on its
    first beat.

    Asserted against the ledger, not the screen: `check` prints the path it
    wrote, and a tmp_path carrying this test's own name would satisfy a
    substring assertion on the output all by itself."""
    episode(series, [beat, clean_beat()])
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    verdicts = [c["mechanical"]["verdict"] for c in ledger_of(series)["claims"]]
    assert verdicts == ["pass"]


def test_check_passes_a_cited_dumbbell_and_refuses_an_uncited_one(series):
    """precondition: the end-to-end half of the dumbbell decision. The uncited
    one no longer reaches `check` at all — the loader refuses it — and the
    message an author gets names the two fields to add."""
    dumb = {
        "type": "dumbbell",
        "rows": [{"label": "History-taking", "values": [0.72, 0.72]}],
        "series": ["AMIE", "Primary care physician"],
        "caption": "Evaluator ratings, AMIE against primary care physicians",
        "footnote": "Direction only.",
    }
    episode(series, [dict(dumb, src="local-ai-zone", quote="DeepSeek's 1.6T MoE flagship")])
    passed = run("video", "check", EP, "--series", "the-brief")
    assert "dumbbell" in passed.output

    write_script(load_episode(series, EP), [dumb])
    refused = run("video", "check", EP, "--series", "the-brief")
    assert refused.exit_code == 1, refused.output
    assert "src" in refused.output and "quote" in refused.output


def test_the_holds_line_is_the_unscaled_total(series):
    """precondition: pace is not 1.0, so `holds × pace = runtime` is three
    different numbers. A `holds` figure that has already been scaled reads as an
    authored total the author never wrote, and it is the number they are told to
    recompute `pace` from."""
    ep = create_episode(series, EP)
    corpus.write_document(
        ep, SOURCE, url="https://x.example/y", key="local-ai-zone",
        fetched_at="2026-08-17",
    )
    write_script_with_pace(ep, [clean_beat(hold=4.0)] * 30, 1.25)
    result = run("video", "check", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    assert "holds 120.0s × pace 1.25 = runtime 150.0s" in result.output

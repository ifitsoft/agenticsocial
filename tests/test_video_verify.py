"""Pass 1 — the mechanical check and the ledger. Spec §8.1, §8.2, §8.2.1, §8.4.

Every test carries a `precondition:` line (D-035): the fact that has to be true
for the assertion to be capable of failing. The question asked of each one is
*what would this do if the code did nothing at all?*

Three habits this file is written around, each because the matching mutant is a
one-line source edit:

  * **Comparison is by value, never by digit sequence** (D-098). Every numeric
    assertion here is chosen so that a substring implementation gives the wrong
    answer — `1M` against `1,000,000` (substring says no, value says yes) and
    `9B` against `95B` (substring says yes, value says no). An example that both
    implementations agree on pins nothing.
  * **Spans are in the ORIGINAL text.** Folding changes lengths in both
    directions — `…` grows to `...`, a run of whitespace shrinks to one space,
    `ß` case-folds to `ss` — so every span assertion slices the original
    document and compares bytes, never compares offsets to a literal.
  * **Falsy values are real.** `0` is a figure, `0.00` is what the frame draws
    for `value: 0, decimals: 2`, and a `before: 0` row is the benchmark that
    scored nothing.
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from agenticsocial.video import claims as C
from agenticsocial.video import corpus
from agenticsocial.video import script as S
from agenticsocial.video import verify as V
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

REPO = Path(__file__).resolve().parents[1]


# --- harness ---------------------------------------------------------------------
#
# Claims are built directly rather than routed through YAML: this task is about
# what the CHECK does with a claim, and running every case through the schema
# would make script.py's own refusals part of the fixture. The ledger tests use
# a real episode on disk, because that is where atomicity and paths are real.


def beat(type_, index=0, src="local-ai-zone", quote="q", kicker="", act="", **fields):
    return S.Beat(
        index=index,
        type=type_,
        hold=3.0,
        act=act,
        kicker=kicker,
        src=src,
        quote=quote,
        fields=dict(fields),
    )


def script_of(*beats):
    return S.Script(
        episode="2026-08-14",
        series="the-brief",
        status="draft",
        pace=1.0,
        beats=tuple(beats),
    )


def claim_of(*beats):
    """One beat in, one claim out — the single-claim cases below."""
    (claim,) = C.extract_claims(script_of(*beats))
    return claim


def check(beat_, document, **kw):
    """The beat goes in as well as the claim: the `shown` check reads the row.

    Deliberately NOT `shown_problems=V.shown_problems(beat_)` — a harness that
    calls the function under test and feeds it back in is D-035's exact shape,
    and would report green with the check deleted.
    """
    return V.check_claim(claim_of(beat_), document, beat=beat_, **kw)


def episode_on_disk(tmp_path, sources=None, beats=None, status="draft"):
    ws = Workspace.init(tmp_path / "workspace")
    series = scaffold_series(ws, "the-brief", name="The Brief")
    ep = create_episode(series, "2026-08-14")
    for key, text in (sources or {}).items():
        corpus.write_document(
            ep, text, url=f"https://{key}.example/x", key=key, fetched_at="2026-08-14"
        )
    body = yaml.safe_dump({"beats": list(beats or [])}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f'---\nepisode: "2026-08-14"\nseries: the-brief\nstatus: {status}\n---\n' + body,
        encoding="utf-8",
    )
    return series, load_episode(series, "2026-08-14")


# --- §8.2.1 folding, and the span it must not corrupt --------------------------------


def test_the_verifier_folds_with_the_same_table_extraction_does():
    """precondition: the sample contains a codepoint from every fold class.

    Two spellings of one rule is the divergence D-096 exists to prevent, in
    miniature: a verifier that folds slightly differently from the extractor
    refuses claims the extractor said were fine. The folded string this module
    searches with must be `claims.fold`'s, character for character.
    """
    sample = "\n  V4‑Pro — “quoted”  it’s\t1,100… end \t"
    folded, _spans = V.fold_spans(sample)
    assert folded == C.fold(sample)


@pytest.mark.parametrize(
    "document",
    [
        "…priced at $0.75 per million input tokens and $3.75 per million output.",
        "priced   at $0.75 per\n\n  million input tokens and $3.75 per million output.",
        "Preisgroße priced at $0.75 per million input tokens and $3.75 per million output.",
        "  priced at $0.75 per million input tokens and $3.75 per million output",
    ],
    ids=["ellipsis-grows", "whitespace-shrinks", "casefold-grows", "nbsp-prefix"],
)
def test_the_quote_span_indexes_the_original_bytes_not_the_folded_ones(document):
    """precondition: folding changes the document's LENGTH before the match.

    M5. `…` folds to `...` (one char becomes three), a whitespace run folds to
    one space (many become one), and `ß` case-folds to `ss`. A span computed on
    the folded text and handed back as an original offset is off by exactly
    those deltas, and the UI highlights the wrong bytes. Asserted by SLICING the
    original — comparing the offsets to a literal would only re-transcribe
    whatever the implementation produced.
    """
    quote = "priced at $0.75 per million input tokens and $3.75 per million output"
    span = V.quote_span(quote, document)
    assert span is not None
    start, end = span
    # The slice is the SOURCE's own spelling, so it is compared after folding
    # rather than byte for byte — the source is allowed to write the run of
    # whitespace it wrote. What cannot survive is an offset shifted by the
    # fold's own length change, which lands the slice a character or three off
    # and makes the two sides unequal under any comparison.
    assert C.fold(document[start:end]) == C.fold(quote)
    assert document[start:end] != document


def test_the_span_covers_the_source_bytes_when_the_source_spells_it_differently():
    """precondition: the matched region differs from the quote byte for byte.

    The span is a highlight into the SOURCE, so it must cover the source's own
    spelling — `V4‑Pro` with U+2011 — and not the quote's ASCII. A span sliced
    out of the wrong string would come back equal to the quote, which is the
    tell this test is looking for.
    """
    document = "DeepSeek raised prices on its flagship V4‑Pro model this week."
    start, end = V.quote_span("flagship V4-Pro model", document)
    assert document[start:end] == "flagship V4‑Pro model"
    assert "‑" in document[start:end]


def test_folding_is_applied_to_the_corpus_side_too():
    """precondition: the TYPOGRAPHIC spelling is in the corpus, the ASCII in the quote.

    M6. Folding only the quote passes the mirror case and fails this one, so a
    test that puts U+2011 in the quote and ASCII in the corpus cannot see the
    mutant. Both directions are asserted; this is the one that discriminates.
    """
    document = "prices on its flagship V4‑Pro model rose"
    assert V.quote_span("flagship V4-Pro model", document) is not None
    mirror = "prices on its flagship V4-Pro model rose"
    assert V.quote_span("flagship V4‑Pro model", mirror) is not None


def test_a_quote_split_across_yaml_lines_matches_a_single_spaced_source():
    """precondition: the quote contains a newline the source does not have.

    A `quote:` written as a folded YAML scalar arrives with newlines and runs of
    indentation inside it. Without whitespace collapsing on the quote side this
    is a refusal of a quote that is verbatim present.
    """
    document = "available today in the Gemini API and AI Studio, Antigravity."
    quote = "available today in the\n   Gemini API and AI Studio"
    assert V.quote_span(quote, document) is not None


@pytest.mark.parametrize(
    "quote",
    ["…available today in the Gemini API",
     "...available today in the Gemini API",
     "available today in the Gemini API…",
     "… available today in the Gemini API …"],
    ids=["leading-U+2026", "leading-ascii", "trailing", "both-spaced"],
)
def test_an_elision_marker_at_the_edge_of_a_quote_is_not_part_of_the_quote(quote):
    """precondition: the source does not contain the dots.

    Found by running the spec's §7 example, where the `list` beat's quote is
    written `"…available today in the Gemini API and AI Studio, …"`. §8.2.1
    folds U+2026 to `...`, and then a literal search demands three full stops
    the source never wrote — so the canonical example is refused for a quote
    that is verbatim present. The leading `…` is an editorial mark meaning "the
    sentence starts earlier", which is the single most common way a human
    shortens a citation.

    No digit is involved, so this can no more admit a wrong figure than folding
    can (§8.2.1's own argument).
    """
    document = "It is available today in the Gemini API and AI Studio, Antigravity."
    span = V.quote_span(quote, document)
    assert span is not None
    assert document[span[0]:span[1]] == "available today in the Gemini API"


def test_an_elision_in_the_MIDDLE_of_a_quote_is_still_matched_literally():
    """precondition: the two halves are present but separated in the source.

    The negative half, and it is a decision rather than an oversight. Matching
    an internal `…` would mean matching two fragments in order with anything at
    all between them, and "verbatim" would stop meaning verbatim — a beat could
    quote `"prices … fell"` against a source saying prices rose before they
    fell. Refused, and the operator quotes one clause or cites twice.
    """
    document = "Prices rose sharply this week."
    # The discriminating case: an implementation treating `…` as "anything at
    # all" — or even as "a space" — matches this, and only this shape shows it.
    # The source's words are adjacent, so a wildcard reading finds them.
    assert V.quote_span("prices rose … sharply", document) is None
    assert V.quote_span("prices rose sharply", document) is not None
    # And the illustration of why that matters, where the fragments are far apart
    # and the meaning between them is the opposite of the quote's.
    torn = "Prices rose in July. Six weeks later prices fell."
    assert V.quote_span("prices rose … prices fell", torn) is None


def test_a_quote_that_is_nothing_but_an_elision_is_not_found():
    """precondition: the document contains plenty of text to match against.

    Trimming the marker must not turn into the vacuous pass it would be if the
    remainder were empty: `""` is inside every document, and a `quote: "…"`
    would then report `quote_found` with nothing checked behind it.
    """
    assert V.quote_span("…", "It is available today in the Gemini API.") is None


def test_a_quote_absent_from_the_corpus_reports_the_closest_candidate_span():
    """precondition: a LONG prefix of the quote is present and the tail is not.

    §8.2: "near-misses report as failures with the closest candidate span
    attached, so the human sees why rather than a bare red mark". If the
    implementation returned no span, or the whole document, the operator learns
    nothing. The prefix here is present verbatim, so a span that does not cover
    it is a span computed from something else.
    """
    document = "DeepSeek raised prices on its flagship V4-Pro model by up to 900%."
    result = check(
        beat("statement", text="x", quote="flagship V4-Pro model by up to 1,100%"),
        document,
    )
    assert result.quote_found is False
    assert result.closest_span is not None
    start, end = result.closest_span
    assert document[start:end].startswith("flagship V4-Pro model by up to ")


def test_the_closest_candidate_is_found_when_the_quote_diverges_at_its_START():
    """precondition: no prefix of the quote occurs in the document at all.

    The sweep's finding. A longest-PREFIX search answers "where does my quote
    stop matching" and returns nothing when the divergence is in the first word
    — which is the common case for a quote whose opening was paraphrased. The
    document below shares no leading character with the quote (it contains no
    `f`), so a prefix-only implementation reports no candidate and the operator
    gets the bare red mark §8.2 exists to avoid.
    """
    document = "Prices on the V5 model by up to 1,100% rose."
    span = V.closest_span("flagship V4-Pro model by up to 1,100%", document)
    assert span is not None
    start, end = span
    assert document[start:end].endswith("model by up to 1,100%")


# --- §8.2 point 2 — the comparison is NUMERIC (D-098) -------------------------------


@pytest.mark.parametrize(
    "rendered, quote",
    [
        ("1M", "priced per 1,000,000 input tokens"),
        ("1M", "priced per 1 million input tokens"),
        ("1M", "priced per million input tokens"),
        ("2.00", "the model costs 2 dollars"),
        ("2.0", "the model costs 2 dollars"),
        ("95B", "roughly 95 billion active parameters"),
        ("95B", "roughly 95,000,000,000 active parameters"),
        ("2.4T", "roughly 2.4 trillion parameters"),
        ("1,100%", "prices rose by up to 1100%"),
        ("1100%", "prices rose by up to 1,100%"),
        ("0.00", "no change at all: 0 across the board"),
    ],
    ids=[
        "1M-vs-separators", "1M-vs-spelled", "1M-vs-bare-magnitude",
        "trailing-zeros", "one-trailing-zero", "95B-vs-spelled",
        "95B-vs-digits", "2.4T-vs-spelled", "separator-in-claim",
        "separator-in-quote", "zero-formatted",
    ],
)
def test_a_magnitude_written_differently_on_the_two_sides_passes(rendered, quote):
    """precondition: the claim's digit string is NOT a substring of the quote.

    M1/M3 — R1's negative half, and the whole of D-098. Every row here is chosen
    so that a substring implementation answers NO: `1` is not in "1,000,000"
    as a standalone figure the way a digit-sequence compare wants it, `2.00` is
    not in "2 dollars", and `95` against "95 billion" is the case §8.2.2's
    unit-suffix rule was added to protect. If the comparison is on strings,
    every one of these is a false refusal.
    """
    result = check(beat("body", text=f"It costs {rendered} today.", quote=quote), quote)
    assert result.atoms_missing == (), result.atoms_missing
    assert result.verdict == "pass"


@pytest.mark.parametrize(
    "rendered, quote",
    [
        ("9B", "roughly 95B active parameters"),
        ("95B", "roughly 9B active parameters"),
        ("0.75", "priced at 75 cents per call"),
        ("1M", "priced per 1 billion input tokens"),
        ("1,100%", "prices rose by up to 110%"),
        ("3.7", "Gemini 3.6 Flash is our new workhorse"),
        ("0", "the score moved to 10"),
    ],
    ids=[
        "9B-vs-95B", "95B-vs-9B", "cents", "wrong-magnitude",
        "order-of-magnitude", "wrong-digit", "zero-vs-ten",
    ],
)
def test_a_different_value_still_fails_however_it_is_spelled(rendered, quote):
    """precondition: the claim states a DIFFERENT quantity from the quote's.

    M2/M4, and the proof this is a strengthening rather than a relaxation.
    Three of these rows are ones a substring implementation ACCEPTS — `9` is
    inside `95B`, the `75` of `0.75` is inside `75 cents`, and `0` is inside
    `10` — so a value comparison refuses claims a digit-sequence comparison
    cannot see at all. The rest are refused by both, and are here so the
    parametrisation covers a wrong digit as well as a wrong magnitude.
    """
    result = check(beat("body", text=f"It costs {rendered} today.", quote=quote), quote)
    assert result.verdict == "fail"
    assert result.atoms_missing != ()


def test_a_magnitude_word_expands_on_the_quote_side_without_swallowing_its_coefficient():
    """precondition: the quote contains a coefficient AND a magnitude word.

    Both readings of "95 billion" are legitimate candidates — the figure 95e9
    the sentence asserts, and the numeral 95 a beat may render bare. Emitting
    only one of them refuses a real beat; emitting a WRONG one would let 9e9
    through, which the mutant table's M2 covers.
    """
    values = V.quote_values("roughly 95 billion active parameters")
    assert Decimal(95) in values
    assert Decimal("95e9") in values
    assert Decimal("9e9") not in values


def test_a_bare_numeral_matches_a_source_that_writes_the_magnitude():
    """precondition: the source writes the suffix and the beat does not.

    The sweep's third finding, and the asymmetry it pins. `jumpChart.before` and
    `after` reach the frame as geometry and are extracted as bare numerals
    (`before: 95`), while the source writes `95B` — so the quote side must offer
    both readings or every chart drawn from a source that uses suffixes is
    refused. The negative half is the same one as everywhere else: `9` is not
    `95`, whichever way either side spells it.
    """
    quote = "with about 95B active"
    assert check(beat("body", text="Active parameters: 95.", quote=quote), quote).verdict == "pass"
    assert check(beat("body", text="Active parameters: 9.", quote=quote), quote).verdict == "fail"


def test_a_bare_magnitude_word_is_worth_its_own_magnitude():
    """precondition: the quote has no digit anywhere near the magnitude word.

    The spec's §7 example beat renders `per 1M input tokens` against a source
    that writes `per million input tokens`. English elides the coefficient 1, so
    "per million" is "per 1 million" — without this the canonical example in
    this document's own §7 is refused, which is the finding D-098 records.
    """
    assert Decimal("1e6") in V.quote_values("priced per million input tokens")
    assert Decimal("1e9") in V.quote_values("about a billion users")
    assert Decimal("1e6") not in V.quote_values("priced per token")


def test_an_identifier_digit_is_never_demanded_of_the_quote():
    """precondition: the product name's digits are absent from the quote.

    §8.2.2, carried through to the check: `V4-Pro` must not demand its `4`.
    A verifier that scanned raw digit runs instead of using the claim-number
    rule would refuse every beat that names a model.
    """
    quote = "DeepSeek raised prices on its flagship model"
    result = check(
        beat("statement", text="DeepSeek raised V4-Pro prices.", quote=quote), quote
    )
    assert result.atoms_missing == ()


def test_a_claim_number_the_record_carries_but_the_text_does_not_is_a_loud_error():
    """precondition: the atom tuple disagrees with the text it was derived from.

    The numeric check re-tokenises `text` because it needs the MAGNITUDE the
    atom string threw away (`1M` is recorded as `1`). Two walks of one string is
    the divergence D-096 is about, so the disagreement must raise rather than
    quietly check a shorter list — silently skipped is indistinguishable from
    checked.
    """
    claim = C.Claim(
        id="c-001", beat_index=0, beat_type="body",
        text="no figures here", src="local-ai-zone", quote="q",
        atoms=(C.Atom("number", "999"),),
    )
    with pytest.raises(V.VerifyError, match="999"):
        V.check_claim(claim, "q")


# --- entity presence: advisory, and deliberately not a failure ------------------------


def test_an_entity_absent_from_the_whole_document_does_not_fail_the_claim():
    """precondition: the entity is in neither the quote nor the rest of the corpus.

    M14, and the decision this task had to make. Task 1 measured the
    orthographic entity rule over-generating on roughly a third of 75 atoms on
    the real brief, and gluing multi-entity runs into strings NO corpus can
    contain. A `fail` verdict driven by that is a gate that cries wolf on almost
    every real beat (D-040). A wrong number is fabrication; a missing proper
    noun is our tokeniser, so it is recorded and not gated.
    """
    document = "prices rose sharply this week"
    result = check(
        beat("statement", text="DeepSeek raised prices.", quote="prices rose sharply"),
        document,
    )
    assert "DeepSeek" in result.entities_missing
    assert result.verdict == "pass"


def test_a_missing_number_and_a_missing_entity_are_not_the_same_outcome():
    """precondition: one claim misses only an entity, the other only a number.

    M14 stated as the comparison it is about. If both land on the same verdict
    the operator cannot tell fabrication from tokenisation, and treats both the
    same way — which means treating fabrication the way you treat noise.
    """
    document = "prices rose sharply this week"
    entity_only = check(
        beat("statement", text="DeepSeek raised prices.", quote="prices rose sharply"),
        document,
    )
    number_only = check(
        beat("body", text="prices rose 1,100%.", quote="prices rose sharply"),
        document,
    )
    assert entity_only.verdict != number_only.verdict
    assert number_only.verdict == "fail"


def test_an_entity_outside_the_quote_but_inside_the_document_is_found():
    """precondition: the entity appears in the document ONLY outside the quote span.

    §8.2 step 3 says "in `quote` or elsewhere in `sources/<src>.txt`". A checker
    that looked in the quote alone would refuse a beat whose subject is named a
    paragraph earlier, which is how sources are written.
    """
    document = "DeepSeek is a Chinese lab.\n\nIt raised prices sharply this week."
    result = check(
        beat("statement", text="DeepSeek raised prices.", quote="raised prices sharply"),
        document,
    )
    assert result.entities_missing == ()
    assert "DeepSeek" in result.atoms_in_corpus


def test_entity_presence_is_case_folded():
    """precondition: the document spells the entity in a different case.

    D-081: CSS uppercases every kicker, so a comparison that is not case-folded
    false-positives on the entire series. The fold covers the corpus side here.
    """
    document = "DEEPSEEK RAISED PRICES SHARPLY"
    result = check(
        beat("statement", text="DeepSeek raised prices.", quote="raised prices sharply"),
        document,
    )
    assert result.entities_missing == ()


# --- verdicts ------------------------------------------------------------------------


def test_a_beat_with_no_src_is_no_source_and_that_is_not_fail():
    """precondition: the beat is otherwise perfectly checkable.

    M7. "I checked and it is wrong" and "there was nothing to check against" are
    different sentences and an operator acts differently on each — one is a
    rewrite, the other is a citation. Collapsing them into `fail` loses the only
    information the verdict carries.
    """
    result = check(beat("body", text="prices rose 1,100%.", src="", quote=""), None)
    assert result.verdict == "no_source"
    assert result.verdict != "fail"


def test_a_beat_with_a_src_but_no_quote_is_no_source_not_a_silent_pass():
    """precondition: an empty quote is a substring of every document.

    The vacuous-pass trap (D-035): `"" in document` is True, so a checker that
    just searches finds it, records `quote_found: True`, has nothing to check
    the numbers against, and reports `pass` on an uncited figure. Nothing to
    check against is `no_source`, whichever half of the citation is missing.
    """
    result = check(beat("body", text="prices rose 1,100%.", quote=""), "prices rose")
    assert result.verdict == "no_source"


def test_a_src_naming_no_document_in_the_corpus_is_no_source():
    """precondition: the corpus does not contain the named key.

    A dangling citation is also "nothing to check against", not "checked and
    wrong". Both refuse at the gate; only one tells the operator to re-ingest.
    """
    result = check(beat("body", text="prices rose 1,100%.", src="nowhere"), None)
    assert result.verdict == "no_source"
    assert "nowhere" in result.reason


def test_a_custom_beat_lands_manual_with_its_attestation_and_never_passes():
    """precondition: the custom beat is well-formed and would otherwise pass.

    M8/M9 and R4 together. D-088: no mechanical check can verify arbitrary
    rendering output, so the record has to be a claim a person made, not a check
    nobody ran. `pass` on a `custom` beat is the check nobody ran.
    """
    result = check(
        beat("custom", js="const h = E('h2');", attest="Draws the price table."),
        "anything at all",
    )
    assert result.verdict == "manual"
    assert result.attest == "Draws the price table."


MINIMAL_FIELDS = {
    "statement": {"text": "prices rose"},
    "body": {"text": "prices rose"},
    "list": {"items": ["prices rose"]},
    "quote": {"text": "prices rose", "attribution": "DeepSeek"},
    "kpis": {"items": [{"value": 12, "label": "moves"}]},
    "jumpChart": {"scale": 100, "footnote": "index points",
                  "rows": [{"label": "price", "before": 0, "after": 12,
                            "shown": "<s>0</s> &rarr; 12"}]},
    "dumbbell": {"rows": [{"label": "price", "values": [0.1, 0.2]}],
                 "series": ["then", "now"], "caption": "direction only",
                 "footnote": "direction only"},
}


def test_no_type_other_than_custom_reaches_manual():
    """precondition: every extracted type in the catalogue is exercised.

    R4's negative half, and the enumeration is derived from `EXTRACTED_TYPES`
    rather than listed, so a type added later cannot quietly skip it. A `manual`
    escape hatch other types can reach is an unchecked pass with a friendlier
    name.
    """
    document = "prices rose sharply and the score is 12 today, DeepSeek said"
    assert set(MINIMAL_FIELDS) == C.EXTRACTED_TYPES, "a type has no fixture here"
    for kind in sorted(C.EXTRACTED_TYPES):
        result = check(
            beat(kind, quote="prices rose sharply", **MINIMAL_FIELDS[kind]), document
        )
        assert result.verdict != "manual", kind


def test_title_and_signoff_are_exempt_and_produce_no_verdict_at_all(tmp_path):
    """precondition: the title card carries a figure in its own text.

    M15. A title card's subtitle is series chrome — "Five stories from the last
    24 hours" — and filing `24` as a claim refuses every episode on its first
    beat. Asserted through the whole ledger, because that is where an exemption
    that leaked would show up as an extra row.
    """
    _series, ep = episode_on_disk(
        tmp_path,
        sources={"local-ai-zone": "prices rose sharply"},
        beats=[
            {"type": "title", "sub": "Five stories from the last 24 hours."},
            {"type": "statement", "text": "Prices rose.", "src": "local-ai-zone",
             "quote": "prices rose sharply"},
            {"type": "signoff", "text": "That was 2026-08-14."},
        ],
    )
    ledger = V.verify_episode(ep)
    assert [c["beat_index"] for c in ledger["claims"]] == [1]


# --- R5 — `shown` against its own row (D-094's residual) ------------------------------


def test_a_shown_cell_stating_a_figure_the_bar_does_not_draw_fails():
    """precondition: the stray figure is present in the quote, so §8.2 passes it.

    M12. This is the hole D-085 ranked first and D-094 handed to this phase.
    The corpus check cannot see it — 91.7 is in the source — and only the row
    itself knows the bar is drawn at 43.6. If the quote did not contain 91.7
    this test would pass for the wrong reason.
    """
    quote = "scores moved from 34.4 to 43.6, with a ceiling of 91.7"
    result = check(
        beat(
            "jumpChart",
            scale=100,
            rows=[{"label": "GDP", "before": 34.4, "after": 43.6,
                   "shown": "<s>34.4</s> &rarr; 91.7"}],
            quote=quote,
        ),
        quote,
    )
    assert result.verdict == "fail"
    assert any("91.7" in p or "43.6" in p for p in result.shown_problems)


def test_a_shown_cell_carrying_no_digits_is_fine():
    """precondition: the row's own values are numbers and the cell has none.

    M13 — R5's negative half. `shown` is a display override (D-081); a row that
    labels its direction rather than restating its numbers is the field working
    as designed, and refusing it makes the override unusable.
    """
    quote = "the score moved from 34.4 to 43.6"
    problems = V.shown_problems(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 34.4, "after": 43.6,
                    "shown": "<s>up</s> &rarr; down"}],
             quote=quote)
    )
    assert problems == ()


def test_a_shown_cell_restating_both_of_its_row_values_is_fine():
    """precondition: the cell's digits are the row's own, entity-escaped.

    The canonical form from the engine's own episode. If this were refused the
    check would fail every jumpChart ever written, which is the loudest possible
    version of D-040's failure mode.
    """
    problems = V.shown_problems(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 34.4, "after": 43.6,
                    "shown": "<s>34.4</s> &rarr; 43.6"}])
    )
    assert problems == ()


def test_a_shown_cell_may_carry_a_published_range_beside_the_row_value():
    """precondition: one of the cell's figures is NOT either row value.

    D-085's own example of an honest divergence: `before: 48.0` with
    `shown: "48–49 → 65.3"` is the committed episode reporting a published
    range. A rule demanding every figure in the cell be a row value refuses it,
    which is why the rule is containment — the row's values must be THERE, not
    alone. The stray 49 is still a claim number and still checked against the
    quote by §8.2, so it is not unverified, just not verified HERE.
    """
    problems = V.shown_problems(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 48.0, "after": 65.3,
                    "shown": "48 – 49 &rarr; 65.3"}])
    )
    assert problems == ()


def test_a_shown_cell_that_drops_the_before_value_while_showing_two_figures_fails():
    """precondition: `after` IS present, so only the `before` half can fail.

    Without this the check is one-sided and a cell can misstate the bar's
    starting point freely. Chosen so a mutant that only ever compares `after`
    survives everything else in this section and dies here.
    """
    problems = V.shown_problems(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 34.4, "after": 43.6,
                    "shown": "<s>99.9</s> &rarr; 43.6"}])
    )
    assert problems != ()


def test_a_shown_cell_holding_a_single_figure_need_only_be_the_after_value():
    """precondition: the cell has exactly one figure and it is `after`.

    The negative half of the rule above: a cell showing just the current value
    is a legitimate override and demanding `before` appear would refuse it.
    """
    assert V.shown_problems(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 34.4, "after": 43.6, "shown": "43.6"}])
    ) == ()


def test_a_zero_row_value_is_checked_like_any_other():
    """precondition: the row's `before` is 0 — falsy, and a real bar.

    script.py calls the benchmark that scored nothing the most interesting bar
    on the chart, and Task 1's own sweep found two live bugs of exactly this
    shape. A truthiness test on `before` skips the row and this is the only
    assertion that sees it.
    """
    assert V.shown_problems(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 0, "after": 43.6,
                    "shown": "<s>0</s> &rarr; 43.6"}])
    ) == ()
    assert V.shown_problems(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 0, "after": 43.6,
                    "shown": "<s>7</s> &rarr; 43.6"}])
    ) != ()


def test_checking_a_jumpchart_claim_without_its_beat_refuses_rather_than_skips():
    """precondition: the claim is a jumpChart and no beat is supplied.

    The sweep's second finding. `beat` is optional so the prose cases read
    cleanly, and that optionality is a hole: a caller that forgets it gets a
    chart whose `shown` cell was never compared to its own row, reported as
    `pass`. A check that silently does not run is indistinguishable from one
    that passed, which is the failure this whole phase is against.
    """
    claim = claim_of(
        beat("jumpChart", scale=100,
             rows=[{"label": "GDP", "before": 34.4, "after": 43.6, "shown": "43.6"}])
    )
    with pytest.raises(V.VerifyError, match="jumpChart"):
        V.check_claim(claim, "the score moved to 43.6")


def test_the_shown_check_needs_no_corpus_at_all():
    """precondition: the document passed in is None.

    It is an internal consistency check on one mapping. Making it depend on the
    corpus would mean an uncited chart escapes it entirely, and an uncited chart
    is exactly the one worth checking.
    """
    result = check(
        beat("jumpChart", scale=100, src="", quote="",
             rows=[{"label": "GDP", "before": 34.4, "after": 43.6,
                    "shown": "<s>34.4</s> &rarr; 91.7"}]),
        None,
    )
    assert result.shown_problems != ()
    assert result.verdict == "fail"


# --- the ledger, §8.1 -----------------------------------------------------------------


def _ledger_episode(tmp_path, **kw):
    return episode_on_disk(
        tmp_path,
        sources={
            "local-ai-zone": "DeepSeek raised prices on its flagship V4‑Pro model "
                             "by up to 1,100% this week.",
            "aireleasetracker": "GLM-5.3 was released August 14, 2026.",
        },
        beats=[
            {"type": "statement", "text": "DeepSeek raised prices by 1,100%.",
             "src": "local-ai-zone",
             "quote": "raised prices on its flagship V4-Pro model by up to 1,100%"},
            {"type": "custom", "js": "const h = E('h2');",
             "attest": "Draws the price table by hand."},
        ],
        **kw,
    )


def test_the_ledger_has_the_shape_section_8_1_specifies(tmp_path):
    """precondition: the episode has a passing claim and a manual one.

    The field SHAPE, not the example's values — §8.1's worked record pairs
    `id: c-014` with `beat_index: 7`, which no one-claim-per-beat scheme
    produces, and its `text` is fluent prose no mechanical walk emits. Both are
    recorded spec defects; the keys are still the contract Task 3 renders.
    """
    _series, ep = _ledger_episode(tmp_path)
    ledger = V.verify_episode(ep)
    assert set(ledger) >= {"episode", "checked_at", "corpus_sha", "claims"}
    record = ledger["claims"][0]
    assert set(record) >= {
        "id", "beat_index", "beat_type", "text", "src", "quote", "quote_span",
        "atoms", "mechanical", "adversarial", "override",
    }
    assert set(record["mechanical"]) >= {
        "verdict", "quote_found", "atoms_in_quote", "atoms_in_corpus", "atoms_missing",
    }
    assert record["adversarial"] is None
    assert record["mechanical"]["verdict"] == "pass"
    assert ledger["claims"][1]["mechanical"]["verdict"] == "manual"
    assert ledger["claims"][1]["mechanical"]["attest"] == "Draws the price table by hand."


def test_the_recorded_span_indexes_the_source_document_on_disk(tmp_path):
    """precondition: the corpus spells the quote with U+2011 and the beat with ASCII.

    M5 again, this time end to end: the number in `claims.json` is only useful
    if slicing the file on disk with it produces the source's words. The U+2011
    guarantees the two strings are not byte-equal, so a span taken from the
    folded text lands in the wrong place rather than accidentally in the right
    one.
    """
    _series, ep = _ledger_episode(tmp_path)
    ledger = V.verify_episode(ep)
    start, end = ledger["claims"][0]["quote_span"]
    document = (ep.sources_dir / "local-ai-zone.txt").read_bytes().decode("utf-8")
    assert document[start:end] == (
        "raised prices on its flagship V4‑Pro model by up to 1,100%"
    )


def test_corpus_sha_covers_the_documents_actually_read(tmp_path):
    """precondition: one source is cited by a beat and one is not.

    M10, both halves. A `corpus_sha` over the whole corpus directory invalidates
    a sound check whenever an unrelated document is ingested — noise that
    teaches people to ignore it. A `corpus_sha` that misses a document a claim
    was checked against is worse: the check silently survives the bytes moving
    under it.
    """
    _series, ep = _ledger_episode(tmp_path)
    before = V.verify_episode(ep)["corpus_sha"]

    corpus.write_document(ep, "GLM-5.3 was released August 15, 2026.",
                          url="https://aireleasetracker.example/x",
                          key="aireleasetracker", fetched_at="2026-08-14", replace=True)
    assert V.verify_episode(ep)["corpus_sha"] == before, "an uncited document moved"

    corpus.write_document(ep, "DeepSeek raised prices on its flagship V4‑Pro "
                              "model by up to 900% this week.",
                          url="https://local-ai-zone.example/x",
                          key="local-ai-zone", fetched_at="2026-08-14", replace=True)
    assert V.verify_episode(ep)["corpus_sha"] != before, "a cited document moved"


def test_a_changed_corpus_invalidates_a_written_ledger(tmp_path):
    """precondition: the ledger on disk was written against the earlier bytes.

    R3. Recording a hash nobody compares is a field, not a guarantee — the
    invalidation has to be something a caller can ask for, or Task 3's `check`
    and Phase 7's `approve` will each invent their own answer.
    """
    _series, ep = _ledger_episode(tmp_path)
    V.write_ledger(ep, V.verify_episode(ep))
    assert V.stale_reason(ep, V.read_ledger(ep)) is None

    corpus.write_document(ep, "DeepSeek held prices flat.",
                          url="https://local-ai-zone.example/x",
                          key="local-ai-zone", fetched_at="2026-08-14", replace=True)
    reason = V.stale_reason(ep, V.read_ledger(ep))
    assert reason is not None and "corpus" in reason


def test_re_running_an_unchanged_check_rewrites_nothing(tmp_path):
    """precondition: the first ledger is already on disk, timestamp and all.

    M11 — R3's negative half. `checked_at` is a clock reading, so the naive
    implementation produces a different file every run and `claims.json` becomes
    a diff nobody reads. Asserted over BYTES and over mtime: a file rewritten
    with identical content still churns a git index and a file watcher.
    """
    _series, ep = _ledger_episode(tmp_path)
    path = V.write_ledger(ep, V.verify_episode(ep))
    first = path.read_bytes()
    stamp = path.stat().st_mtime_ns

    V.write_ledger(ep, V.verify_episode(ep))
    assert path.read_bytes() == first
    assert path.stat().st_mtime_ns == stamp


def test_a_real_change_does_update_the_timestamp(tmp_path):
    """precondition: the previous ledger recorded a different verdict.

    The negative half of the test above. A `checked_at` that never moves is
    equally useless, and "write nothing when nothing changed" degenerates into
    "never write" if the comparison is on the wrong thing.
    """
    _series, ep = _ledger_episode(tmp_path)
    path = V.write_ledger(ep, V.verify_episode(ep))
    first = json.loads(path.read_text(encoding="utf-8"))

    corpus.write_document(ep, "DeepSeek held prices flat.",
                          url="https://local-ai-zone.example/x",
                          key="local-ai-zone", fetched_at="2026-08-14", replace=True)
    V.write_ledger(ep, V.verify_episode(ep))
    second = json.loads(path.read_text(encoding="utf-8"))
    assert second["claims"][0]["mechanical"]["verdict"] == "fail"
    assert second["checked_at"] != first["checked_at"]


def test_claim_order_follows_the_beats(tmp_path):
    """precondition: the episode has more than one claimable beat.

    M11's ordering half. An operator reads `claims.json` beside `script.yaml`;
    a set-derived or hash-derived order reshuffles on every run and makes the
    two unreadable together.
    """
    _series, ep = _ledger_episode(tmp_path)
    ledger = V.verify_episode(ep)
    assert [c["beat_index"] for c in ledger["claims"]] == [0, 1]
    assert [c["id"] for c in ledger["claims"]] == ["c-001", "c-002"]


def test_the_ledger_is_written_atomically_and_never_with_write_text(tmp_path, monkeypatch):
    """precondition: `Path.write_text` is replaced by a raise.

    CLAUDE.md: every workspace write goes through `workspace.atomic_write`
    (tempfile + `os.replace`). A partial `claims.json` is a ledger that reads as
    fewer claims than were checked, which is the one corruption this file must
    not be able to have.
    """
    _series, ep = _ledger_episode(tmp_path)
    ledger = V.verify_episode(ep)

    def blocked(*a, **kw):
        raise AssertionError("verify.py wrote with write_text")

    monkeypatch.setattr(Path, "write_text", blocked)
    monkeypatch.setattr(Path, "write_bytes", blocked)
    path = V.write_ledger(ep, ledger)
    assert path == ep.dir / "claims.json"
    assert json.loads(path.read_text(encoding="utf-8"))["claims"]


def test_verification_never_writes_the_script(tmp_path):
    """precondition: a real script.yaml is on disk and is read by the check.

    "`script.yaml` is never written by this phase" (the plan's global
    constraints). Approval is bound to `script_sha256`; a verifier that
    reformatted the file would silently invalidate an approval.
    """
    _series, ep = _ledger_episode(tmp_path)
    before = ep.script_path.read_bytes()
    V.write_ledger(ep, V.verify_episode(ep))
    assert ep.script_path.read_bytes() == before


def test_the_ledger_is_json_serialisable_exactly_as_returned(tmp_path):
    """precondition: the ledger contains spans, decimals and tuples.

    `verify_episode` returns the thing that gets written; if it holds a Decimal
    or a tuple the JSON round-trip changes shape between the object Task 3 reads
    and the file an operator reads.
    """
    _series, ep = _ledger_episode(tmp_path)
    ledger = V.verify_episode(ep)
    assert json.loads(json.dumps(ledger)) == ledger


def test_an_override_written_in_the_script_reaches_the_record(tmp_path):
    """precondition: the beat would otherwise fail.

    §8.4: the only way past the gate is a written reason with a name on it, and
    it has to survive into the artifact the gate reads. Recording it does not
    change the verdict — the verdict is what was measured; the override is what
    a human decided about it.

    The shape is §8.4's mapping of `reason` and `by` (D-103). It was a string
    when this test was written, because `script.py` validated every shared
    field with `free_text` and refused §8.4's own example at load; Phase 5 Task
    3 fixed the code to match the spec, and this fixture moved with it.
    """
    _series, ep = episode_on_disk(
        tmp_path,
        sources={"local-ai-zone": "prices rose sharply"},
        beats=[{"type": "body", "text": "Prices rose 1,100%.", "src": "local-ai-zone",
                "quote": "prices rose sharply",
                "claim_override": {"reason": "Framed as expectation, not fact.",
                                   "by": "Ali Abdukarim"}}],
    )
    record = V.verify_episode(ep)["claims"][0]
    assert record["mechanical"]["verdict"] == "fail"
    assert record["override"] == {
        "reason": "Framed as expectation, not fact.",
        "by": "Ali Abdukarim",
    }


def test_verification_opens_no_socket_and_calls_no_model(tmp_path):
    """precondition: conftest's guards are active for this test.

    R6, asserted rather than assumed. The autouse fixture raises on any socket
    and on `research.search`/`extract`; this test exists so the property is
    exercised by the verifier's own code path rather than inherited silently.
    """
    _series, ep = _ledger_episode(tmp_path)
    assert V.verify_episode(ep)["claims"]


# --- the two corpora that are not fixtures --------------------------------------------


SPEC = REPO / "docs" / "superpowers" / "specs" / "2026-08-15-agenticsocial-video-mvp-design.md"
BRIEF = REPO / "workspace" / "inbox" / "2026-08-17-ai-brief.md"

SPEC_KPI_QUOTE = (
    "priced at $0.75 per million input tokens and $3.75 per million output"
)


def test_the_specs_own_section_7_kpis_beat_verifies_clean():
    """precondition: the quote spells every magnitude the beat renders in digits.

    D-098's worked example, and the reason §8.2 point 2 was amended. The beat
    renders `$0.75`, `per 1M input tokens`, `$3.75`, `per 1M output tokens`; the
    source writes "per million". Under a digit-sequence comparison `1` is
    absent and this beat — the canonical example in the spec's own §7 — is
    refused. If this test passes with a substring implementation, the fixture
    has been softened.
    """
    result = check(
        beat(
            "kpis",
            src="venturebeat",
            quote=SPEC_KPI_QUOTE,
            items=[
                {"value": 0.75, "prefix": "$", "label": "per 1M input tokens",
                 "decimals": 2},
                {"value": 3.75, "prefix": "$", "label": "per 1M output tokens",
                 "decimals": 2},
            ],
        ),
        SPEC_KPI_QUOTE,
    )
    assert result.atoms_missing == (), result.atoms_missing
    assert result.verdict == "pass"


@pytest.mark.skipif(not SPEC.exists(), reason="spec not present")
def test_that_quote_is_still_the_specs_own_words():
    """precondition: the spec on disk still contains the quote this file pins.

    A guard on the FIXTURE, not on the code (D-035). If §7's example is ever
    rewritten, the test above silently stops being about the spec's example and
    becomes a test about a string I typed.
    """
    assert SPEC_KPI_QUOTE in SPEC.read_text(encoding="utf-8")


@pytest.mark.skipif(not BRIEF.exists(), reason="operator inbox is gitignored")
def test_beats_built_from_the_real_brief_verify_clean(tmp_path):
    """precondition: the brief on disk still contains U+2011 and real figures.

    D-071's regression fixture and this phase's exit criterion. The brief is the
    corpus; the beats quote it verbatim and render its figures in the notation a
    frame uses (`95B` where the source writes `95B`, `2.4T` where it writes
    "2.4 trillion"). Every refusal here is a false refusal an operator would
    override, and the override rate is the health signal D-040 is about.
    """
    text = BRIEF.read_text(encoding="utf-8")
    assert "‑" in text, "the fixture no longer contains a non-breaking hyphen"

    _series, ep = episode_on_disk(
        tmp_path,
        sources={"local-ai-zone": text},
        beats=[
            {"type": "statement", "act": "01",
             "kicker": "Today's headline",
             "text": "DeepSeek raised prices on its flagship V4-Pro model by up to 1,100%.",
             "src": "local-ai-zone",
             "quote": "raised prices on its flagship V4‑Pro model by up to 1,100%"},
            {"type": "kpis", "act": "01",
             "items": [
                 {"value": 1.32, "prefix": "$", "label": "per 1M input tokens",
                  "decimals": 2},
                 {"value": 3.96, "prefix": "$", "label": "per 1M output tokens",
                  "decimals": 2},
             ],
             "src": "local-ai-zone",
             "quote": "new pricing starting August 16 at about $1.32 / $3.96 per 1M tokens"},
            {"type": "body", "act": "02",
             "text": "Qwen3.8-Max is roughly 2.4T parameters with about 95B active.",
             "src": "local-ai-zone",
             "quote": "at roughly 2.4 trillion parameters with about 95B active"},
            {"type": "list", "act": "03",
             "lead": "context-mode claims up to a 98% reduction in context size.",
             "items": ["across 12 supported platforms"],
             "src": "local-ai-zone",
             "quote": "claiming up to a 98% reduction in context size across 12 "
                      "supported platforms"},
        ],
    )
    ledger = V.verify_episode(ep)
    refused = [
        (c["id"], c["mechanical"]["verdict"], c["mechanical"]["atoms_missing"])
        for c in ledger["claims"]
        if c["mechanical"]["verdict"] != "pass"
    ]
    assert refused == [], refused

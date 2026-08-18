"""Claim extraction — what a beat asserts, per spec §8.1, §8.2.1 and §8.2.2.

Every test carries a `precondition:` line: the fact that has to be true for the
assertion to be capable of failing. D-035 is the reason — a test whose own
harness performs the transformation under test cannot fail, and this file is
full of transformations (folding, tokenising) a careless harness could do for
the code.

Three habits, each because the corresponding mutant is cheap to write:

  * the fold is asserted to reach **ASCII**, never "this codepoint is gone".
    D-091: `"‑" not in normalize("NFKC", s)` answers True while
    `V4‑Pro` still fails to match `V4-Pro`. Ask about the target.
  * falsy values are real. `0` is a figure, `""` is a field the operator
    blanked, and an empty atom tuple is a legitimate outcome.
  * the prose-bearing fields are never listed here as a literal. They are read
    back out of `script.BEAT_TYPES` and out of `engine/planbuild.js`, because a
    literal list in the test is the same defect as a literal list in the code —
    it agrees with today's catalogue and stops agreeing silently.
"""
import re
import unicodedata
from pathlib import Path

import pytest
import yaml

from agenticsocial.video import claims as C
from agenticsocial.video import script as S
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

REPO = Path(__file__).resolve().parents[1]


# --- harness ---------------------------------------------------------------------


def beat(type_, index=0, src="blog-google", quote="q", kicker="", act="", **fields):
    """A `Beat` built directly, without a file.

    Direct construction, not YAML: this task is about what extraction does with
    a beat, and routing every case through `load_script` would make the schema's
    own refusals part of the fixture. The file path is exercised separately by
    the no-write test, which needs real bytes on disk.
    """
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


def numbers(text):
    return [a.value for a in C.atoms(text) if a.kind == "number"]


def entities(text):
    return [a.value for a in C.atoms(text) if a.kind == "entity"]


# --- §8.2.1 the fold ---------------------------------------------------------------

# The spec's table, retyped here ON PURPOSE. It is the one literal this file
# keeps: it is the requirement, and reading it out of the implementation would
# make every assertion below a tautology (D-035).
SPEC_FOLD = {
    "-": "‐‑‒–—―−",
    "'": "‘’‛",
    '"': "“”‟",
    " ": "    ",
    "...": "…",
}


@pytest.mark.parametrize(
    "source,target",
    [(c, t) for t, chars in SPEC_FOLD.items() for c in chars],
    ids=lambda v: f"U+{ord(v):04X}" if len(v) == 1 and ord(v) > 127 else str(v),
)
def test_every_codepoint_in_the_spec_table_folds_to_its_ascii_target(source, target):
    """precondition: `fold` implements §8.2.1's table rather than a normaliser.

    Asserted as "did the fold reach the ASCII target", which is D-091's rule.
    The comfortable question — did this codepoint disappear — passes for U+2011
    under NFKC, which maps it to U+2010 and leaves the comparison broken.
    """
    folded = C.fold(f"a{source}b")
    assert folded == f"a{target}b", f"U+{ord(source):04X} folded to {folded!r}"
    assert all(ord(ch) < 128 for ch in folded)


def test_nfkc_is_not_a_substitute_for_the_table():
    """precondition: the fold is an explicit table, not `normalize("NFKC", …)`.

    The real case from D-071, byte for byte: the source wrote V4-Pro with
    U+2011, the beat wrote it with U+002D. Two of six beats were refused for
    quotes that were genuinely present.
    """
    source = "raised prices on its flagship V4‑Pro model"
    beat_wrote = "raised prices on its flagship V4-Pro model"

    assert C.fold(source) == C.fold(beat_wrote)
    # …and the thing that makes the table necessary rather than decorative.
    assert unicodedata.normalize("NFKC", source) != unicodedata.normalize(
        "NFKC", beat_wrote
    )


@pytest.mark.parametrize("char", "‑–—−")
def test_the_hyphen_family_is_not_ascii_after_nfkc(char):
    """precondition: NFKC is available and leaves these non-ASCII.

    Pins the measurement D-091 corrected the spec with, so that "simplify the
    table to NFKC" is a red suite rather than a code review argument. U+2011 is
    the trap: it *changes* under NFKC — to U+2010, another non-ASCII hyphen.
    """
    assert any(ord(c) > 127 for c in unicodedata.normalize("NFKC", char))


def test_no_digit_is_anywhere_in_the_fold_table():
    """precondition: the table is exposed as data.

    R6, asserted over the whole table rather than trusted. This is the property
    that makes folding one-directional: it can turn a false refusal into a pass
    and never a false claim into a verified one. A full-width digit added to the
    table would break that, and it is exactly the kind of "helpful" addition a
    later reader makes.
    """
    for source, target in C.FOLD_TABLE.items():
        for ch in source + target:
            assert not ch.isdigit(), f"{ch!r} is a digit"
            assert not ch.isnumeric(), f"{ch!r} is numeric"
            assert unicodedata.category(ch) != "Nd", f"{ch!r} is a decimal digit"


def test_folding_preserves_every_digit_it_is_given():
    """precondition: `fold` is applied to text containing digits.

    The behavioural half of R6. A full-width `１` stays a full-width `１`: it is
    not ASCII `1`, and a fold that quietly made it one would let a beat's `1`
    match a source's `１` — a fold changing what a number IS.
    """
    text = "1,100% １ 0.75 ‑ 95B"
    assert re.findall(r"\d", C.fold(text)) == re.findall(r"\d", text)
    assert "１" in C.fold(text)


def test_fold_collapses_whitespace_runs_and_case_folds():
    """precondition: quotes are YAML-folded and sources are typeset.

    A `quote:` written across three indented YAML lines arrives with newlines
    and runs of spaces in it; the source has one space. And D-081: CSS
    uppercases every kicker, so a comparison that is not case-folded
    false-positives on all of them.
    """
    assert C.fold("Live   today\n   in the API") == "live today in the api"
    assert C.fold("A B") == "a b"
    assert C.fold("  padded  ") == "padded"


def test_fold_maps_the_quote_and_ellipsis_families():
    """precondition: sources emit typographic quotes; agents emit ASCII ones."""
    assert C.fold("“still cheaper”") == '"still cheaper"'
    assert C.fold("don’t") == "don't"
    assert C.fold("…available today") == "...available today"


# --- §8.2.2 claim numbers vs identifier digits -------------------------------------

# The spec's own table (§8.2.2), plus the four tokens the real brief produced
# that the spec's table never considered.
@pytest.mark.parametrize(
    "token,expected",
    [
        # §8.2.2, verbatim
        ("$1.32", "1.32"),
        ("1,100%", "1,100"),
        ("1M", "1"),
        ("95B", "95"),
        ("2.4", "2.4"),
        ("V4-Pro", None),
        ("Qwen3.8-Max", None),
        ("GPT-5.6", None),
        # the real brief, D-092
        ("2026,", "2026"),
        ("14,", "14"),
        ('60"', "60"),
        ("1.6T", "1.6"),
        ("27.8B", "27.8"),
        ("98%", "98"),
        ("$3.96", "3.96"),
        # M2 — the suffix is stripped from the END only. `M1` is a chip.
        ("M1", None),
        ("K9", None),
        ("$M", None),
        # falsy and degenerate
        ("0", "0"),
        ("0.0", "0.0"),
        ("%", None),
        ("M", None),
        ("", None),
        ("—", None),
        # markdown emphasis is punctuation around the token, not part of it
        ("**1,100%**", "1,100"),
        ("(1M)", "1"),
    ],
)
def test_the_claim_number_rule_from_the_spec_table(token, expected):
    """precondition: `claim_number` classifies one whitespace-delimited token.

    R1 and R2 together. The negative half is what earns the rule its keep: a
    naive "any letters means identifier" test exempts `1M` and `95B`, which
    would let a beat claim `95B active` against a source saying `9B`.
    """
    assert C.claim_number(token) == expected


def test_a_standalone_number_beside_a_product_name_is_still_checked():
    """precondition: extraction splits on whitespace, not on "looks like a name".

    R3. `3.7` in `Gemini 3.7 Flash` stands alone, so it is a claim: a beat
    saying 3.7 where the source says 3.6 is the error this whole pass exists to
    catch. This is the mutant that silences the check by being clever.
    """
    assert numbers("Gemini 3.7 Flash is Google's new workhorse.") == ["3.7"]


def test_digits_glued_to_letters_are_never_claim_numbers():
    """precondition: the sentence contains identifiers and no free-standing figure.

    R1's negative. If `4` shows up here, every product name in the series
    becomes a figure the operator has to override — D-040's failure mode.
    """
    text = "DeepSeek raised prices on its flagship V4-Pro model, unlike GPT-5.6."
    assert numbers(text) == []


def test_zero_is_a_figure():
    """precondition: nothing in the path tests a value for truthiness.

    "0 seconds of downtime" is a headline figure. A `if value:` anywhere between
    the beat and the atom drops it, and dropping a figure is the failure this
    task is the front half of.
    """
    assert numbers("0 seconds of downtime") == ["0"]


def test_years_and_ordinals_are_claim_numbers_and_that_is_deliberate():
    """precondition: the rule is digits-only, with no range or shape exemption.

    D-092, decided in the Task 1 report: no exemption. A year is the one part of
    a stale-date claim (§8.3) a mechanical pass can see, and any "is this a
    year?" test is a range check that would also exempt `2026 GPUs`. Pinned so
    the answer is a decision on the record rather than a default someone
    quietly special-cases at the first false refusal.
    """
    assert numbers("released August 14, 2026, per the tracker") == ["14", "2026"]


def test_atoms_are_deduplicated_in_order():
    """precondition: the same figure appears twice in one beat's text."""
    assert numbers("12 lessons and 12 more, then 200") == ["12", "200"]


# --- §8.2.2, second pass: what happens to a token the rule cannot read ---------------
#
# The boundary these tests pin, stated as a sentence with its negative half:
# once the wrapping punctuation and a leading currency symbol are off, a token
# that **begins with a digit** is a figure and is checked; a token that begins
# with a letter is an identifier and is exempt. Every identifier in §8.2.2's own
# table — `V4-Pro`, `Qwen3.8-Max`, `GPT-5.6`, and the `M1` chip the code already
# protects — begins with a letter, so the boundary costs D-071 nothing.


@pytest.mark.parametrize(
    "token,expected",
    [
        ("950bn", "950"),
        ("95mn", "95"),
        ("1.2tn", "1.2"),
        ("$1.4bn", "1.4"),
        ("50bps", "50"),
    ],
)
def test_a_two_letter_magnitude_is_parsed_rather_than_disabling_the_check(
    token, expected
):
    """precondition: the one-character suffix strip leaves a letter behind, so
    every one of these yields NO atom at all today — not a number, not a name.

    R2. `about 950bn active` against a source saying `about 95B active` was
    verified clean through the real CLI: a 10x fabrication passing, because a
    token nothing could classify was checked by nothing. The suffix set is a
    closed list either way; what must never follow from a spelling it does not
    know is that the figure becomes invisible.
    """
    assert C.claim_number(token) == expected


@pytest.mark.parametrize(
    "token",
    ["1e9", "3/4", "12:30", "0-70", "2010-2011", "1080p", "5th", "٣٠٠", "１"],
)
def test_a_numeric_looking_token_the_rule_cannot_value_is_still_a_figure(token):
    """precondition: none of these is digits-and-separators and none has a
    capital anywhere, so today each one produces no atom and is checked by
    nothing.

    R1, and the design rule of this task: *"I cannot read this figure"* and
    *"this figure is fine"* must never produce the same verdict. The atom is the
    token itself; §8.2's check then demands the quote spell it exactly, because
    there is no value to compare.
    """
    assert C.claim_number(token) == token.casefold()


@pytest.mark.parametrize(
    "token",
    ["V4-Pro", "Qwen3.8-Max", "GPT-5.6", "M1", "K9", "iPhone", "x86-64", "H100"],
)
def test_an_identifier_that_begins_with_a_letter_is_still_exempt(token):
    """precondition: R1's negative half, and it is the non-negotiable one.

    D-071's rule was validated twice against real prose. Re-introducing these
    false refusals would be a worse regression than the hole being closed — a
    gate that demands the `4` in `V4-Pro` is one an operator overrides without
    reading, taking the true refusal in the same run with it (D-040).
    """
    assert C.claim_number(token) is None


@pytest.mark.parametrize(
    "token,expected",
    [
        ("-18", "-18"),
        ("−18%", "-18"),  # U+2212 MINUS, folded to ASCII like every other dash
        ("(-18)", "-18"),
        ("-1.4bn", "-1.4"),
        ("-$18", "-18"),
    ],
)
def test_a_minus_glued_to_a_figure_is_part_of_the_figure(token, expected):
    """precondition: `-` is Unicode `Pd` and U+2212 is `Sm`, so both are
    stripped as decoration today and `_bare('-18')` is `'18'`.

    R3. A beat saying revenue fell 18% verifies against a source saying it rose
    18% — a reversal of meaning, passing. §8.2.1's safety argument ("no digit is
    ever folded") is sound and its scope is wrong: the loss happens before
    folding is consulted.
    """
    assert C.claim_number(token) == expected


def test_a_hyphen_that_is_punctuation_rather_than_a_sign_does_not_become_one():
    """precondition: the text contains a hyphen INSIDE a token and a dash
    standing alone, and neither is a minus.

    R3's negative half. A sign is glued to the digits it signs; anything else is
    punctuation and folds as it always did. `2010-2011` is a range, not minus
    two thousand and eleven.
    """
    assert numbers("the 18% figure, over 2010-2011, was flat") == ["18", "2010-2011"]
    assert numbers("revenue - 18% of it - was flat") == ["18"]


def test_a_shown_cell_puts_its_own_figure_into_the_beat_text():
    """precondition: 91.7 is neither `before` nor `after`, so no other collector
    on this row can produce it.

    F4. D-081's guarantee — the digits inside `shown` are still a claim — had no
    test that could fail: the covering test asserts that markup is ABSENT (true
    when nothing is appended) and names only figures `before`/`after` yield
    anyway, so deleting the `shown` extraction survived all 1524 tests. Textbook
    D-035: what would that test do if the code did nothing? Pass.
    """
    claim = C.extract_claims(
        script_of(
            beat(
                "jumpChart",
                scale=100,
                rows=[
                    {"label": "GPQA", "before": 34.4, "after": 43.6,
                     "shown": "<s>34.4</s> &rarr; 91.7"}
                ],
            )
        )
    )[0]
    assert "91.7" in numbers(claim.text)


def test_a_kpi_prefix_and_unit_are_part_of_what_the_frame_shows():
    """precondition: neither `$` nor ` billion` changes which DIGITS are
    extracted, so only an assertion on the rendered text can fail.

    F5. Dropping either from `_kpi_text` survived the whole suite. The rule the
    docstring states is that the extracted figure is the one the frame formats —
    `prefix + toFixed(decimals) + unit` — and the unit half is load-bearing for
    the value check: ` billion` is three orders of magnitude.
    """
    claim = C.extract_claims(
        script_of(
            beat(
                "kpis",
                items=[{"value": 98, "decimals": 0, "prefix": "$",
                        "unit": " billion", "label": "cash"}],
            )
        )
    )[0]
    assert "$98 billion" in claim.text


# --- entities (§8.2 step 3) ---------------------------------------------------------


def test_entity_runs_join_adjacent_name_tokens():
    """precondition: no NLP dependency exists; the rule is orthographic.

    The spec's own example atom is the three-token run `Gemini 3.7 Flash`, so a
    numeric token INSIDE a run belongs to the run — and is separately a claim
    number, which is R3.
    """
    got = entities("Google shipped Gemini 3.7 Flash today.")
    assert "Gemini 3.7 Flash" in got
    assert "Google" in got


def test_a_possessive_entity_is_recorded_without_its_suffix():
    """precondition: entity atoms are looked for in the corpus verbatim.

    A source says "Google" far more often than "Google's", and an atom nobody
    can find is a false refusal.
    """
    assert entities("Google's new workhorse") == ["Google"]


def test_a_sentence_opening_function_word_is_not_an_entity():
    """precondition: the text starts a sentence with a capitalised function word.

    The only concession the orthographic rule makes. Without it every beat
    beginning "The …" files a claim on the word "The".
    """
    assert entities("The rollout is widely expected to slip.") == []


def test_a_beat_can_legitimately_produce_no_atoms_at_all():
    """precondition: an empty tuple is returned, not None and not a refusal.

    A prose beat with no figures and no names is a real beat. Task 2 gives it a
    verdict; extraction must not treat "nothing to check" as an error or as an
    excuse to drop the record.
    """
    assert C.atoms("the model got faster and cheaper") == ()


# --- the catalogue: what a beat RENDERS (the §7.1 trap) ------------------------------


def test_every_catalogue_type_is_classified():
    """precondition: `BEAT_TYPES` is the catalogue and is read at call time.

    M9's first half. A type added to §7.1 must land in exactly one of the three
    buckets, or extraction refuses loudly — a type nobody classified is a card
    whose figures nobody checks.
    """
    buckets = (C.EXTRACTED_TYPES, C.EXEMPT_TYPES, C.MANUAL_TYPES)
    assert set().union(*buckets) == set(S.BEAT_TYPES)
    assert sum(len(b) for b in buckets) == len(S.BEAT_TYPES), "buckets overlap"


def test_a_new_catalogue_type_is_refused_until_someone_classifies_it(monkeypatch):
    """precondition: the new type is in `BEAT_TYPES` and in none of the buckets.

    The runtime half of the same rule. D-086: the catalogue is closed today, not
    forever, and the next type is valid before anything can draw it — which is
    exactly when it must not slip past verification unnoticed.
    """
    grown = dict(S.BEAT_TYPES)
    grown["ticker"] = {"required": {"text": S.text}, "optional": {}, "cited": True}
    monkeypatch.setattr(S, "BEAT_TYPES", grown)

    with pytest.raises(C.ClaimsError) as e:
        C.extract_claims(script_of(beat("ticker", text="Up 1,100%.")))
    assert "ticker" in str(e.value)


def test_every_catalogue_field_checker_has_a_collector():
    """precondition: collectors are keyed by the checker FUNCTION from §7.1.

    M9's second half, and the whole point of keying on the checker rather than
    on a field name: a new field declared `"tagline": text` is collected the day
    it is added, and a new field with a NEW checker fails here until someone
    decides whether it reaches the frame.
    """
    for name, spec in S.BEAT_TYPES.items():
        for field, check in {**spec["required"], **spec["optional"]}.items():
            assert check in C.COLLECTORS, f"{name}.{field} ({check.__name__})"


def test_a_new_prose_field_is_extracted_without_touching_claims_py(monkeypatch):
    """precondition: extraction reads `BEAT_TYPES` when it runs, not at import.

    The mutant this task exists to kill (M9). A hand-written list of prose
    fields is correct exactly until §7.1 grows one — D-086 records the catalogue
    as closed today, not forever — and the failure is silent: the figure ships,
    and `check` says pass.
    """
    grown = dict(S.BEAT_TYPES)
    grown["statement"] = {
        **S.BEAT_TYPES["statement"],
        "optional": {**S.BEAT_TYPES["statement"]["optional"], "tagline": S.text},
    }
    monkeypatch.setattr(S, "BEAT_TYPES", grown)

    claim = C.extract_claims(
        script_of(beat("statement", text="Prices moved.", tagline="Up 1,100% overnight"))
    )[0]
    assert "1,100" in [a.value for a in claim.atoms]


def test_a_new_field_with_an_unknown_checker_is_refused_loudly(monkeypatch):
    """precondition: no collector is registered for the new checker.

    The other side of the same door. Failing loudly is the point: a field nobody
    classified must not be silently skipped, because silently skipped is
    indistinguishable from checked.
    """

    def novel(v):
        return None

    grown = dict(S.BEAT_TYPES)
    grown["statement"] = {
        **S.BEAT_TYPES["statement"],
        "optional": {"mystery": novel},
    }
    monkeypatch.setattr(S, "BEAT_TYPES", grown)

    with pytest.raises(C.ClaimsError) as e:
        C.extract_claims(script_of(beat("statement", text="x", mystery="9")))
    assert "mystery" in str(e.value)


def test_no_field_planbuild_renders_is_unknown_to_claims_py():
    """precondition: `engine/planbuild.js` is the other answer to the same question.

    `claims.py` decides what text a beat renders; `planbuild.js` decided that
    independently, in JavaScript, when it built the DOM. Nothing makes them
    agree. If the JS reads a beat field Python has neither extracted nor
    written a reason for ignoring, figures inside it ship unchecked while
    `check` reports pass.

    What this catches: a field name the builders read that Python has never
    heard of. What it does NOT catch: a field both files know about that Python
    classifies wrongly, and any text the JS renders from somewhere other than
    a `b.`/`r.`/`it.` property access.
    """
    src = (REPO / "engine" / "planbuild.js").read_text(encoding="utf-8")
    read_by_js = set(re.findall(r"\b(?:b|it|r)\.([A-Za-z_]\w*)", src))
    assert "shown" in read_by_js, "the regex stopped matching planbuild.js"

    known = C.CLAIMED_FIELDS | set(C.IGNORED_FIELDS)
    assert read_by_js <= known, f"unclassified: {sorted(read_by_js - known)}"


def test_every_ignored_field_carries_a_written_reason():
    """precondition: `IGNORED_FIELDS` maps a name to prose, not to a bool.

    An exemption with no reason is the shape D-093 identified: a documented
    exception is not a reviewed one. The reason is what the next reader argues
    with.
    """
    for name, why in C.IGNORED_FIELDS.items():
        assert isinstance(why, str) and len(why.split()) >= 4, name


# --- per-type extraction ------------------------------------------------------------


def test_statement_extracts_text_and_kicker():
    """precondition: `kicker` is a shared field and planKicker draws it.

    The kicker in the committed episode is "And it costs half of what 3.6 Flash
    did" — a figure, on screen, in a field that is not in any type's own field
    list.
    """
    claim = C.extract_claims(
        script_of(beat("statement", kicker="Half of 3.6 Flash", text="Now $0.75."))
    )[0]
    assert numbers(claim.text) == ["3.6", "0.75"]


def test_list_extracts_lead_and_every_item():
    """precondition: planbuild's buildList draws `lead` AND every row of `items`.

    The named example of the trap: extract only `lead` and every figure inside
    `items` ships unchecked.
    """
    claim = C.extract_claims(
        script_of(
            beat(
                "list",
                lead="A model with a 1M-token context window.",
                items=["Priced at $1.32", "Up to 1,100% more", "Antigravity"],
            )
        )
    )[0]
    # `1M-token` begins with a digit, so it is a figure and not an identifier
    # (Task 4, R1) — the same silence that exempted it exempted `950bn`, and a
    # 1M-token window is a claim about quantity in a way `V4-Pro` is not. It
    # cannot be VALUED (a hyphen is not a separator inside a number), so §8.2
    # asks the quote to spell it. The display is folded, which is why it is
    # lower case: `claims.atoms` and `verify.claim_values` must walk one string.
    assert [a.value for a in claim.atoms if a.kind == "number"] == [
        "1m-token",
        "1.32",
        "1,100",
    ]
    assert "Antigravity" in [a.value for a in claim.atoms if a.kind == "entity"]


def test_kpis_extracts_the_formatted_value_the_frame_shows_plus_its_label():
    """precondition: the engine renders `prefix + toFixed(decimals) + unit`.

    The figure the viewer reads is the formatted one. `value: 0.75, decimals: 2`
    is `$0.75` on the frame; extracting the Python repr of the float instead
    would check a string the frame never shows.
    """
    claim = C.extract_claims(
        script_of(
            beat(
                "kpis",
                items=[
                    {"value": 0.75, "prefix": "$", "label": "per 1M input", "decimals": 2},
                    {"value": 0, "label": "seconds of downtime"},
                    # `0` at two decimals is `0.00` on the frame. Found by
                    # mutation: a truthiness check on `value` falls through to
                    # the string branch and still yields "0" for the row above,
                    # so a bare zero cannot see it. This row can.
                    {"value": 0, "prefix": "$", "label": "in fees", "decimals": 2},
                ],
            )
        )
    )[0]
    assert numbers(claim.text) == ["0.75", "1", "0", "0.00"]


def test_a_kpi_value_is_extracted_as_the_glyphs_the_frame_shows():
    """precondition: `decimals` makes the displayed string differ from the value.

    `value: 2, decimals: 2` is `2.00` on the frame. Found by mutation: with a
    single-decimal fixture, extracting `repr(value)` instead passes every other
    assertion in this file. Recorded as a HANDOFF: Task 2's numeric comparison
    has to treat `2.00` and `2` as the same figure, or this is itself a
    false-refusal generator.
    """
    claim = C.extract_claims(
        script_of(beat("kpis", items=[{"value": 2, "label": "x", "decimals": 2}]))
    )[0]
    assert numbers(claim.text) == ["2.00"]


def test_an_entity_run_never_crosses_a_field_boundary():
    """precondition: two fields end and begin with capitalised words.

    Fields are separate lines on the card. Joining them with a space invents an
    entity — `Gemini Flash` — that no source contains and no beat wrote, and an
    atom nobody can find is a false refusal.
    """
    claim = C.extract_claims(
        script_of(beat("statement", kicker="Gemini", text="Flash is cheap."))
    )[0]
    assert entities(claim.text) == ["Gemini", "Flash"]


def test_jumpchart_extracts_labels_shown_footnote_and_the_row_values():
    """precondition: `shown` is set as innerHTML and `before`/`after` draw the bars.

    D-081: `shown` is the one field where the frame and the script legitimately
    differ, so its markup is stripped rather than exempted — the digits inside
    it are a claim. §7.2 requires every numeric value to appear in the quote, so
    `before`/`after` are atoms even though they reach the frame as geometry.
    """
    claim = C.extract_claims(
        script_of(
            beat(
                "jumpChart",
                rows=[
                    {"label": "GPQA", "before": 34.4, "after": 43.6,
                     "shown": "<s>34.4</s> &rarr; 43.6"},
                    # No `shown`: the cell is blank on the card and the only
                    # trace of these two figures is the bar itself. Found by
                    # mutation — with only the row above, dropping `before` and
                    # `after` from extraction passes, because `shown` happens to
                    # repeat them.
                    {"label": "AIME", "before": 12.5, "after": 88.0},
                    # `before: 0` is a benchmark that scored nothing before —
                    # script.py calls it the most interesting bar on the chart,
                    # and a truthiness check anywhere on the path drops it.
                    {"label": "MMLU", "before": 0, "after": 21.0},
                ],
                scale=70.0,
                footnote="Scores as published, on a common 0-70% scale.",
            )
        )
    )[0]
    assert "<s>" not in claim.text and "&rarr;" not in claim.text
    got = numbers(claim.text)
    assert "34.4" in got and "43.6" in got
    assert "12.5" in got and "88.0" in got
    assert "0" in got and "21.0" in got
    # The footnote's scale range is one token, and it is a FIGURE: `0-70` is
    # digits the rule cannot value, so it is checked by exact spelling rather
    # than exempted (Task 4, R1). This assertion said `not in` until the gate
    # review found that the same silence covering `0-70` also covered `950bn`.
    assert "0-70" in got
    assert "70.0" not in got, "`scale` is never printed — engine.js positions with it"


def test_dumbbell_extracts_its_words_and_never_its_positions():
    """precondition: dumbbell `values` are fractions of the track, in [0, 1].

    The type renders no numbers (spec §7.2), and its values are positions an
    operator chose, not figures a source published. Demanding `0.62` appear in
    the quote is a guaranteed false refusal on every dumbbell ever written.
    Its WORDS are another matter — D-086 records that caption, footnote, note
    and label all reach the stage.
    """
    claim = C.extract_claims(
        script_of(
            beat(
                "dumbbell",
                rows=[{"label": "Accuracy", "values": [0.62, 0.81], "note": "up 4 pts"}],
                series=["AMIE", "PCPs"],
                caption="Rated on par with primary care physicians.",
                footnote="Direction only, over 159 cases.",
            )
        )
    )[0]
    assert numbers(claim.text) == ["4", "159"]
    assert "AMIE" in entities(claim.text)


def test_quote_beat_extracts_its_words_and_its_attribution():
    """precondition: buildQuote draws `text` and `attribution` on the card."""
    claim = C.extract_claims(
        script_of(beat("quote", text="Up 1,100%.", attribution="DeepSeek, 2026"))
    )[0]
    assert numbers(claim.text) == ["1,100", "2026"]


def test_title_and_signoff_produce_no_claims():
    """precondition: both types are in the catalogue and would otherwise extract.

    §8.2's exemption, and it has to be real: a title card carries the episode
    date and the series name, and filing those as claims would refuse every
    episode on its first beat.
    """
    script = script_of(
        beat("title", index=0, sub="Five stories from the last 24 hours.", src=""),
        beat("signoff", index=1, text="Same time tomorrow.", src=""),
    )
    assert C.extract_claims(script) == ()


def test_custom_is_manual_with_its_attestation_and_no_atoms():
    """precondition: `custom.js` is executed in the page and draws anything.

    D-088. Its rendered content cannot be statically extracted — that is what
    "arbitrary" means — so extraction must not pretend by scraping the source of
    the script. The record still exists, carrying the human's attestation, so
    Task 2 can land it as `manual` rather than losing the beat.
    """
    claim = C.extract_claims(
        script_of(
            beat(
                "custom",
                js="const h = E('h2', null, P('1,100% up'));",
                attest="Draws the price chart; figures are in the quote.",
                src="",
            )
        )
    )[0]
    assert claim.manual is True
    assert claim.atoms == ()
    assert claim.attest.startswith("Draws the price chart")
    assert "1,100" not in claim.text


# --- the record (R7) ------------------------------------------------------------------


def test_every_record_names_its_beat_and_carries_a_unique_id():
    """precondition: the script has more than one claimable beat.

    R7. A verdict that cannot be traced to a row of `agsoc video review` is a
    verdict an operator cannot act on.
    """
    script = script_of(
        beat("statement", index=0, text="One."),
        beat("body", index=1, text="Two."),
        beat("statement", index=2, text="Three."),
    )
    got = C.extract_claims(script)
    assert [c.beat_index for c in got] == [0, 1, 2]
    assert [c.beat_type for c in got] == ["statement", "body", "statement"]
    assert len({c.id for c in got}) == 3
    assert all(c.id for c in got)


def test_a_claimable_beat_keeps_its_index_when_an_exempt_beat_precedes_it():
    """precondition: `title` produces no record, so positions and indexes diverge.

    The off-by-one this shape invites: numbering records by their position in
    the output would report beat 0 for the beat the operator sees as beat 1.
    """
    script = script_of(
        beat("title", index=0, sub="", src=""),
        beat("statement", index=1, text="Prices moved 1,100%."),
    )
    (claim,) = C.extract_claims(script)
    assert claim.beat_index == 1


def test_a_beat_with_no_src_still_produces_a_record():
    """precondition: `src` and `quote` are empty strings, not missing keys.

    R7's negative, and M13. A beat asserting something with no source is Task
    2's `no_source` verdict — the gate refuses on it. Dropping the record here
    turns a refusal into a silent pass, which is the one outcome this phase
    exists to make impossible.
    """
    (claim,) = C.extract_claims(
        script_of(beat("statement", text="Prices rose 1,100%.", src="", quote=""))
    )
    assert claim.src == ""
    assert claim.quote == ""
    assert "1,100" in [a.value for a in claim.atoms]


def test_the_record_carries_the_quote_bytes_unfolded():
    """precondition: the quote contains a codepoint the fold would change.

    R4. The record is what Task 2 folds and what the operator reads; folding it
    on the way in would put normalised text in `claims.json` and quietly move
    the goalposts for `quote_span`, which indexes the ORIGINAL text.
    """
    (claim,) = C.extract_claims(
        script_of(beat("statement", text="x", quote="flagship V4‑Pro model"))
    )
    assert claim.quote == "flagship V4‑Pro model"


def test_extraction_cannot_write_at_all(monkeypatch):
    """precondition: every write path in reach is replaced by a raise.

    The capability, not the habit. The bytes test below can only see writes
    inside the workspace it built; this one sees any write anywhere, and it is
    the honest form of "nothing here writes a byte" — R4 is a property of the
    module, not of one fixture's directory tree.
    """
    import builtins
    from pathlib import Path

    def blocked(*a, **kw):
        raise AssertionError("claims.py touched the filesystem")

    monkeypatch.setattr(builtins, "open", blocked)
    monkeypatch.setattr(Path, "write_text", blocked)
    monkeypatch.setattr(Path, "write_bytes", blocked)
    monkeypatch.setattr(Path, "open", blocked)

    claims = C.extract_claims(
        script_of(beat("statement", text="Up 1,100% on V4‑Pro.", quote="up 1,100%"))
    )
    assert claims[0].quote == "up 1,100%"


def test_extraction_writes_nothing_to_disk(tmp_path):
    """precondition: a real episode exists on disk and the script is loaded from it.

    R4/M8, asserted over bytes rather than over intent. If folding were ever
    written back, `script_sha256` would cover different bytes than the ones the
    operator approved and §4's integrity guarantee would be gone. A test that
    only inspected the returned objects could not see it.
    """
    ws = Workspace.init(tmp_path / "workspace")
    series = scaffold_series(ws, "the-brief", name="The Brief")
    ep = create_episode(series, "2026-08-14")
    body = yaml.safe_dump(
        {
            "beats": [
                {
                    "type": "statement",
                    "text": "DeepSeek raised prices on its flagship V4‑Pro model.",
                    "src": "local-ai-zone",
                    "quote": "raised prices on its flagship V4‑Pro model",
                }
            ]
        },
        sort_keys=False,
        allow_unicode=True,
    )
    ep.script_path.write_text(
        '---\nepisode: "2026-08-14"\nseries: the-brief\nstatus: draft\n---\n' + body,
        encoding="utf-8",
    )
    before = {
        p: p.read_bytes() for p in sorted(ws.root.rglob("*")) if p.is_file()
    }

    C.extract_claims(S.load_script(load_episode(series, "2026-08-14")))

    after = {p: p.read_bytes() for p in sorted(ws.root.rglob("*")) if p.is_file()}
    assert after == before


# --- the real brief (D-071's regression fixture) ---------------------------------------

BRIEF = REPO / "workspace" / "inbox" / "2026-08-17-ai-brief.md"


@pytest.mark.skipif(not BRIEF.exists(), reason="operator inbox is gitignored")
def test_the_real_brief_yields_figures_and_no_identifier_digits():
    """precondition: the brief on disk still contains U+2011 and product names.

    D-071's own regression fixture. Synthetic fixtures contain neither
    non-breaking hyphens nor product names, and both defects in §8.2 came from
    running this file. The assertion on U+2011 is a guard on the FIXTURE: if the
    brief is ever retyped in ASCII, this test stops testing what it says.
    """
    text = BRIEF.read_text(encoding="utf-8")
    assert "‑" in text, "the fixture no longer contains a non-breaking hyphen"

    got = numbers(text)
    for figure in ("1,100", "1.32", "3.96", "1.6", "2.4", "95", "27.8", "98", "200"):
        assert figure in got, figure
    for identifier in ("4", "3.8", "5.6", "5.3"):
        assert identifier not in got, f"{identifier} is part of a product name"


# --- phase 6 task 2: one boundary, not two (D-106 + D-102) --------------------------
#
# D-106 settled where a figure ends and a name begins: a token BEGINNING WITH A
# DIGIT is a figure and gets checked by value. `_name_token` did not get the
# memo — it asks only whether the token carries a capital anywhere, so `2.4T`
# and `95B` were filed as figures AND as entities. The figure verifies; the
# entity is looked for verbatim in the corpus, does not appear there, and the
# token lands in `check`'s "names not found" list. D-102 kept that list
# ungated precisely because it must stay readable: a correctly-verified figure
# sitting in it is the noise that stops it being read.


@pytest.mark.parametrize(
    "token", ["2.4T", "95B", "1,100%", "16", "2026", "$1.32", "0.756", "1.6T"]
)
def test_a_figure_token_is_never_also_an_entity_atom(token):
    """precondition: the sentence starts lowercase, so the only capital in it is
    the figure's own magnitude suffix. Anything returned here is the defect."""
    assert entities(f"pricing moved to {token} this week") == []


def test_a_magnitude_figure_is_a_number_atom_and_nothing_else():
    """precondition: the figure half must survive the fix. Deleting the atom
    instead of re-filing it would exempt `2.4T` from verification entirely —
    D-106's failing-open, restored by its own repair."""
    got = C.atoms("about 2.4T parameters with 95B active")
    kinds = {a.kind for a in got}
    assert kinds == {"number"}
    assert [a.value for a in got] == ["2.4", "95"]


def test_a_letter_initial_name_is_still_an_entity(): 
    """precondition NEGATIVE (M4). The fix moves ONE class of token. Every
    identifier in §8.2.2's table begins with a letter and must still be
    recorded — D-102's list is ungated, not deleted."""
    got = entities("DeepSeek V4-Pro and Qwen3.8-Max beat Gemini 3.7 Flash")
    assert "DeepSeek V4-Pro" in got
    assert "Qwen3.8-Max" in got
    assert "Gemini 3.7 Flash" in got


def test_a_figure_inside_a_name_run_still_belongs_to_the_run():
    """precondition NEGATIVE: the spec's own example atom is `Gemini 3.7 Flash`.
    A digit-initial token between two names is joined to the run by the
    `pending` path, not by being a name itself — so the run must survive even
    when the numeric token carries a capital."""
    assert "Gemini 2.5B Flash" in entities("Google shipped Gemini 2.5B Flash today.")

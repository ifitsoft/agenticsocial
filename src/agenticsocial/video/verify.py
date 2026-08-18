"""Pass 1 — the mechanical check, and the ledger it writes. Spec §8.1, §8.2, §8.4.

`claims.py` answers *what does a beat assert?* This module answers *is it true
of the bytes on disk?* — and writes down the answer in a form a human can
adjudicate a year from now. No network, no LLM, no clock in the comparison.

**The comparison is numeric, not textual (D-098).** §8.2 originally specified
"normalised digit sequences" and that rule fails on this document's own §7
example: the beat renders `per 1M input tokens` while the source writes `per
million input tokens`, and there is no digit to match. Worse, the rule's own
purpose inverts — `95B` against a source writing "95 billion" fails, which is
precisely the case §8.2.2's unit-suffix rule was added to protect.

So both sides are parsed into values: the §8.2.2 claim-number rule gives the
coefficient, magnitude suffixes (`K M B T`) and spelled magnitudes (thousand,
million, billion, trillion) give the exponent, and `Decimal` compares them.
This **strengthens** the guarantee: `95B` = 95e9 ≠ 9e9 = `9B` is a distinction a
substring test cannot make at all, because `9` is a substring of `95`. What
stops causing refusals is trailing zeros, thousands separators and notation —
`75 cents` against `0.75` still fails.

Three asymmetries in it, each deliberate:

  * **The quote side emits both readings of "95 billion"** — the figure 95e9 the
    sentence asserts and the numeral 95 a beat may legitimately render bare. The
    claim side emits only the expanded value, because `95B` is unambiguous about
    what it asserts. Making the claim side lenient too would let `95B` pass
    against a source saying "95 units".
  * **A bare magnitude word is worth its own magnitude.** "per million" is "per
    1 million"; English elides the coefficient. Without this the spec's §7
    example is refused, which is the whole of D-098.
  * **Numbers gate; entities advise.** §8.2 step 3 wants "every proper noun", and
    Task 1's orthographic approximation over-generates on about a third of the
    atoms it finds on the real brief and glues multi-entity runs into strings no
    corpus can contain. A `fail` driven by that is D-040's failure mode arriving
    on day one — a gate that cries wolf until overrides are reflexive. A wrong
    number is fabrication; a missing proper noun is our tokeniser. Entity misses
    are recorded in `entities_missing` and surfaced in review; they do not fail.
    **This module therefore does not implement §8.2 step 3 as a gate, and says
    so** rather than pretending the check is stronger than it is.

**A figure this pass cannot value is checked by its spelling, never skipped.**
`3/4`, `1e9`, `12:30`, `2010-2011` and a non-ASCII digit are figures whose
arithmetic this module does not do; `claims.figure` still returns them, with no
value, and the quote must spell them exactly. The alternative was what the code
did until F1: a token that was neither digits-only nor a name yielded no atom,
so *"I cannot read this figure"* and *"this figure is fine"* produced the same
verdict. That is the one direction a component whose entire job is to notice
must never fail in.

Folding (§8.2.1) applies to the comparison only. Nothing here normalises a byte
on disk — `sha256` still covers the originals, which is what §4 rests on — and
every span recorded is an offset into the ORIGINAL document, because the fold
changes lengths in both directions (`…` grows to `...`, a run of whitespace
shrinks to one space, `ß` case-folds to `ss`).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ..workspace import atomic_write
from . import claims as claims_mod
from . import corpus as corpus_mod
from . import script as script_mod
from .claims import Claim, claim_number, figure, fold
from .models import Episode

# Two helpers reached across the module boundary rather than re-spelled here.
# `_bare` is §8.2.2's punctuation strip and `_shown_text` is D-081's tag strip;
# a second copy of either is the divergence D-096 exists to prevent, and both
# are already covered by `tests/test_video_claims.py`.
_bare = claims_mod._bare
_shown_text = claims_mod._shown_text


class VerifyError(Exception):
    pass


CLAIMS_NAME = "claims.json"

VERDICTS = ("pass", "fail", "no_source", "manual")

# §8.3's pass-2 verdicts. `unsupported` is what a refuter defaults to under
# uncertainty, so it is a refusal, not a shrug — §8.4 lists it beside `fail`.
ADVERSARIAL_VERDICTS = ("supported", "unsupported", "refuted")

# How long a pass-2 verdict is believed. Argued in the Phase 9 Task 1 report and
# in `adversarial_state` below: the corpus and the script are covered by
# digests, and the JUDGE is not.
PASS2_HORIZON_DAYS = 90


# --- §8.2.1 folding, with a map back to the original bytes ---------------------------


def fold_spans(text: str) -> tuple[str, list[tuple[int, int]]]:
    """`claims.fold(text)`, plus the original span each folded character came from.

    The join of the folded pieces is asserted equal to `claims.fold` — one rule,
    one spelling. What this adds is the index: `spans[i]` is the half-open range
    in `text` that produced folded character `i`, so a match found in folded
    coordinates can be reported in the operator's.

    The fold changes lengths in **both** directions and one example only shows
    one of them: `…` → `...` grows, a whitespace run → one space shrinks, and
    `ß` → `ss` grows for a reason that has nothing to do with the fold table.
    A span computed on the folded text and returned as an original offset is off
    by all three at once.
    """
    pieces: list[tuple[str, int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            # Every codepoint §8.2.1's space row names is already `isspace()`,
            # so the run is found on the original and folded to one space.
            j = i
            while j < n and text[j].isspace():
                j += 1
            pieces.append((" ", i, j))
            i = j
        else:
            pieces.append((claims_mod.FOLD_TABLE.get(text[i], text[i]).casefold(), i, i + 1))
            i += 1

    start, end = 0, len(pieces)
    while start < end and pieces[start][0] == " ":
        start += 1
    while end > start and pieces[end - 1][0] == " ":
        end -= 1

    folded: list[str] = []
    spans: list[tuple[int, int]] = []
    for chunk, at, to in pieces[start:end]:
        folded.append(chunk)
        spans.extend([(at, to)] * len(chunk))
    return "".join(folded), spans


def _span_of(spans: list[tuple[int, int]], at: int, length: int) -> tuple[int, int]:
    return spans[at][0], spans[at + length - 1][1]


# An elision marker at the START or END of a quote is editorial punctuation, not
# words the source wrote. §8.2.1 folds U+2026 to `...`, and a literal search then
# demands three full stops nobody typed — measured against the spec's own §7
# example, whose `list` beat quotes `"…available today in the Gemini API …"` and
# is refused for a quote that is verbatim present.
#
# Two or more dots, never one: a trailing full stop is a sentence ending and the
# source has it too, so stripping it would loosen `verbatim` for no gain. And
# the EDGES only — an internal `…` would mean "these two fragments, in order,
# with anything at all between them", and a beat could then quote "prices … fell"
# against a source saying prices rose before they fell. Same argument as
# §8.2.1's: no digit is touched, so this can turn a false refusal into a pass
# and never a false claim into a verified one.
_EDGE_ELISION = re.compile(r"^(?:\s*\.{2,}\s*)+|(?:\s*\.{2,}\s*)+$")


def _needle(quote: str) -> str:
    folded, _ = fold_spans(quote)
    return _EDGE_ELISION.sub("", folded).strip()


def quote_span(quote: str, document: str) -> tuple[int, int] | None:
    """Where `quote` sits in `document`, in the document's OWN coordinates.

    An empty quote is not found — including one that was nothing but an elision
    marker. `"" in document` is True for every document, and a checker that
    reported it as present would then have nothing to test the beat's figures
    against while reporting `pass`: the vacuous pass D-035 is about.
    """
    needle = _needle(quote)
    if not needle:
        return None
    haystack, spans = fold_spans(document)
    at = haystack.find(needle)
    if at < 0:
        return None
    return _span_of(spans, at, len(needle))


def _longest_run(needle: str, haystack: str, *, from_end: bool) -> tuple[int, int] | None:
    """The longest prefix (or suffix) of `needle` present in `haystack`.

    Binary search, because presence is monotone in length: if a prefix of length
    k is in the haystack then so is every shorter one. Linear in `log(len)`
    string searches rather than the quadratic diff a general "closest match"
    would cost, and it answers the question an operator actually has — *where
    does my quote stop matching the source?*
    """
    low, high, best = 1, len(needle), None
    while low <= high:
        mid = (low + high) // 2
        piece = needle[-mid:] if from_end else needle[:mid]
        at = haystack.find(piece)
        if at < 0:
            high = mid - 1
        else:
            best = (at, mid)
            low = mid + 1
    return best


def closest_span(quote: str, document: str) -> tuple[int, int] | None:
    """The near-miss §8.2 requires: the closest candidate region, or None.

    "Near-misses report as failures with the closest candidate span attached, so
    the human sees *why* rather than a bare red mark." A bare red mark is what
    teaches people to override without looking.
    """
    needle = _needle(quote)
    haystack, spans = fold_spans(document)
    if not needle or not haystack:
        return None
    candidates = [
        run
        for run in (
            _longest_run(needle, haystack, from_end=False),
            _longest_run(needle, haystack, from_end=True),
        )
        if run is not None
    ]
    if not candidates:
        return None
    at, length = max(candidates, key=lambda run: run[1])
    return _span_of(spans, at, length)


# --- §8.2 point 2 — values, not digit sequences (D-098) -------------------------------

_THOUSAND = Decimal(1000)

# The suffix set is §8.2.2's, plus the two-letter spellings `claims.UNIT_WORDS`
# strips. `%`, `x` and `bps` are units rather than magnitudes and multiply by
# one: `1,100%` is eleven hundred, not eleven hundred of anything, and 50 basis
# points is fifty of them. Anything absent from this mapping is worth one, which
# is safe precisely because `claims.figure` has already decided the token is a
# figure — an unreadable one arrives here with no value at all.
MAGNITUDES: dict[str, Decimal] = {
    "K": _THOUSAND,
    "M": _THOUSAND**2,
    "B": _THOUSAND**3,
    "T": _THOUSAND**4,
    "BN": _THOUSAND**3,
    "MN": _THOUSAND**2,
    "TN": _THOUSAND**4,
}

# The spelled forms §8.2 names, plus their plurals — a source writes "95 billion"
# and also "hundreds of billions". A closed list, not a suffix rule. The glued
# spellings `95bn` and `95mn` are NOT here; they are stripped as suffixes by
# `claims.UNIT_WORDS` and expanded by `MAGNITUDES` above. This comment used to
# claim they were "refused rather than guessed at" — they were neither. They
# produced no atom, and `about 950bn active` verified clean against a source
# saying `about 95B active` (F1).
MAGNITUDE_WORDS: dict[str, Decimal] = {
    word: value
    for stem, value in (
        ("thousand", MAGNITUDES["K"]),
        ("million", MAGNITUDES["M"]),
        ("billion", MAGNITUDES["B"]),
        ("trillion", MAGNITUDES["T"]),
    )
    for word in (stem, stem + "s")
} | {
    # The two-letter spellings again, this time standing on their own. A beat
    # writes `95bn` and also `95 bn`, and the second one never reaches the
    # suffix strip: the atom was the bare `95`, which a source saying "95
    # million" contains. Same defect as F1, one space away from it.
    "bn": MAGNITUDES["B"],
    "mn": MAGNITUDES["M"],
    "tn": MAGNITUDES["T"],
}


def _coefficient(token: str) -> tuple[str, Decimal | None, Decimal] | None:
    """`(display, value, suffix magnitude)` for a §8.2.2 figure, else None.

    `claims.figure` is the authority on *whether* this token is a figure and on
    what it reads as — reused, never re-derived. What the atom string throws
    away is the suffix, and the suffix is the whole magnitude: the display is
    `"1"` for `1M` and `"95"` for `95B`, so a check built on it alone cannot
    tell one million from one.

    `value` is None when the token cannot be valued: `1.2.3` satisfies §8.2.2's
    "only digits and separators" and is not a number, and `3/4`, `1e9`, `12:30`
    and `٣٠٠` are figures whose arithmetic this module does not do. None of them
    is guessed at — `check_claim` demands the quote spell them exactly, which is
    the strictest comparison available rather than a relaxation of one.
    """
    found = figure(token)
    if found is None:
        return None
    value: Decimal | None = None
    if found.digits is not None:
        try:
            value = Decimal(found.digits.replace(",", ""))
        except InvalidOperation:
            value = None
    return found.display, value, MAGNITUDES.get(found.suffix.upper(), Decimal(1))


def _magnitude_word(token: str) -> Decimal | None:
    return MAGNITUDE_WORDS.get(_bare(token))


def claim_values(text: str) -> tuple[tuple[str, Decimal | None], ...]:
    """Every figure this text ASSERTS, as `(display, value)`, in order.

    The display is `claim_number`'s, so it is the same string `claims.atoms`
    records; the value carries the magnitude that string dropped. A beat writing
    `95 billion` in words yields `("95", 95e9)` — the words are the beat's
    assertion just as much as the suffix would be.

    Only the expanded value, never the bare coefficient. `95B` says ninety-five
    billion and nothing else; admitting `95` as well would let it pass against a
    source that wrote "95 units".
    """
    tokens = fold(text).split()
    out: list[tuple[str, Decimal | None]] = []
    i = 0
    while i < len(tokens):
        parsed = _coefficient(tokens[i])
        if parsed is None:
            i += 1
            continue
        display, value, magnitude = parsed
        spelled = _magnitude_word(tokens[i + 1]) if i + 1 < len(tokens) else None
        if value is not None and spelled is not None:
            out.append((display, value * spelled))
            i += 2
            continue
        out.append((display, None if value is None else value * magnitude))
        i += 1
    return tuple(dict.fromkeys(out))


def quote_values(text: str) -> frozenset[Decimal]:
    """Every figure this text could be read as CONTAINING.

    Deliberately wider than `claim_values`, in the two ways a source is wider
    than a beat:

      * `95 billion` contributes 95e9 *and* 95. The sentence asserts the first;
        the numeral 95 is legibly on the page, and a beat rendering it bare is
        quoting the source rather than inventing. This cannot admit a wrong
        digit — 9e9 is in neither reading.
      * a magnitude word with no coefficient is worth its own magnitude. "per
        million input tokens" contains one million. Without this, the spec's own
        §7 example — the beat that started D-098 — is refused.
    """
    tokens = fold(text).split()
    values: set[Decimal] = set()
    i = 0
    while i < len(tokens):
        parsed = _coefficient(tokens[i])
        spelled = _magnitude_word(tokens[i + 1]) if i + 1 < len(tokens) else None
        if parsed is None:
            bare = _magnitude_word(tokens[i])
            if bare is not None:
                values.add(bare)
            i += 1
            continue
        _display, value, magnitude = parsed
        if value is not None:
            values.add(value * magnitude)
            if magnitude != 1:
                values.add(value)
            if spelled is not None:
                values.add(value * spelled)
                values.add(value)
                i += 2
                continue
        i += 1
    return frozenset(values)


def quote_spellings(text: str) -> frozenset[str]:
    """Every figure this text SPELLS that no arithmetic here can evaluate.

    The companion to `quote_values`, and the reason an unreadable figure is
    checked rather than refused outright. `3/4` is something a real beat writes;
    when the source spells it the same way, equality after §8.2.1's fold is the
    STRICTEST comparison available — stricter than the numeric one, which reads
    `1M` and `1,000,000` as the same claim. What it cannot do is let a wrong
    figure through, because "wrong" and "differently spelled" are the same thing
    for a token nothing can value.
    """
    return frozenset(display for display, value in claim_values(text) if value is None)


# --- R5 — `shown` against the row it labels (D-085 #1, handed over by D-094) ----------


def shown_problems(beat: script_mod.Beat) -> tuple[str, ...]:
    """Where a `jumpChart` row's `shown` cell states a figure its bar does not draw.

    No corpus, no §8.2 machinery — an internal consistency check on one mapping,
    which is what D-094 made possible by closing `shown`'s vocabulary. It
    retires the last route by which a chart asserts a number nothing verifies:
    `shown: "…&rarr; 91.7"` on a row drawn from `after: 43.6` passes the corpus
    check whenever the source happens to contain 91.7, and only the row knows.

    **The rule is containment, not equality**, and D-085 is why. `before: 48.0`
    with `shown: "48 – 49 &rarr; 65.3"` is the committed episode being honest
    about a published range; a rule demanding every figure in the cell be a row
    value refuses it. So the row's values must be *present*, not *alone* — and
    the stray figures are not unverified, because every digit in `shown` is
    already a claim number checked against the quote by §8.2. The two checks
    decompose the problem between them.

    `before` is only demanded of a cell carrying two or more figures: a cell
    showing just the current value (`shown: "43.6"`) is a legitimate override.
    The cost, stated: `shown: "43.6 (n=159)"` is refused, because the check
    cannot tell a sample size from a starting value.
    """
    if beat.type != "jumpChart":
        return ()
    rows = beat.fields.get("rows")
    if not isinstance(rows, list):
        return ()

    problems: list[str] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("shown"), str):
            continue
        # Values only: a cell carrying a figure this pass cannot read (`1.2.3`)
        # states nothing about the bar's geometry, and §8.2 already demands the
        # quote spell it. Comparing a row value against `None` would refuse the
        # row for the wrong reason.
        figures = [
            value
            for _d, value in claim_values(_shown_text(row["shown"]))
            if value is not None
        ]
        if not figures:
            # R5's negative half: a cell that labels its direction rather than
            # restating its numbers is the override working as designed.
            continue
        wanted = ["after"] + (["before"] if len(figures) >= 2 else [])
        for name in wanted:
            drawn = row.get(name)
            # `isinstance(drawn, (int, float))`, never truthiness: `before: 0` is
            # the benchmark that scored nothing, and script.py calls it the most
            # interesting bar on the chart.
            if not isinstance(drawn, (int, float)) or isinstance(drawn, bool):
                continue
            if Decimal(repr(drawn)) not in figures:
                shown_list = ", ".join(str(f) for f in figures)
                problems.append(
                    f"beat {beat.index} row {i} ({row.get('label')!r}): `shown` "
                    f"states {shown_list}, but the bar is drawn from "
                    f"`{name}: {drawn}` — the cell and the geometry disagree"
                )
    return tuple(problems)


# --- the verdict ----------------------------------------------------------------------


@dataclass(frozen=True)
class Mechanical:
    """One claim's pass-1 result — spec §8.1's `mechanical` block, plus two fields.

    `entities_missing` and `shown_problems` are not in §8.1's example record.
    The example shows a passing claim and pins no negative shape, and both of
    these are things an operator has to be able to see: one is advisory by
    decision, the other is a failure §8.1 predates.
    """

    verdict: str
    quote_found: bool | None = None
    quote_span: tuple[int, int] | None = None
    closest_span: tuple[int, int] | None = None
    atoms_in_quote: tuple[str, ...] = ()
    atoms_in_corpus: tuple[str, ...] = ()
    atoms_missing: tuple[str, ...] = ()
    entities_missing: tuple[str, ...] = ()
    shown_problems: tuple[str, ...] = ()
    reason: str = ""
    attest: str = ""


def _number_atoms(claim: Claim) -> tuple[str, ...]:
    return tuple(a.value for a in claim.atoms if a.kind == "number")


def _entity_atoms(claim: Claim) -> tuple[str, ...]:
    return tuple(a.value for a in claim.atoms if a.kind == "entity")


def check_claim(
    claim: Claim, document: str | None, *, beat: script_mod.Beat | None = None
) -> Mechanical:
    """Pass 1 for one claim. `document` is `sources/<src>.txt`, or None if absent.

    Verdicts, and the distinction that matters: `fail` is "I checked and it is
    wrong", `no_source` is "there was nothing to check against". An operator
    acts differently on each — one is a rewrite, the other is a citation — and
    collapsing them loses the only information the verdict carries. Both refuse
    at the gate (§8.4).

    `custom` is always `manual` and never `pass` (D-088): nothing can statically
    extract what arbitrary JavaScript draws, so the record is a claim a person
    made rather than a check nobody ran.
    """
    if claim.beat_type == "jumpChart" and beat is None:
        raise VerifyError(
            f"{claim.id}: a jumpChart claim needs its beat — `shown` is checked "
            "against the row's own `before`/`after`, and a check that silently "
            "does not run is indistinguishable from one that passed"
        )
    problems = shown_problems(beat) if beat is not None else ()

    if claim.manual:
        # Before anything else: no path through this function may give a
        # `custom` beat a mechanical verdict of any kind.
        return Mechanical(
            verdict="manual",
            attest=claim.attest,
            shown_problems=problems,
            reason="`custom` renders whatever its `js` draws; `attest` is the "
            "human substitute for a check no machine can make",
        )

    entities = _entity_atoms(claim)
    if not claim.src:
        return _unchecked(claim, problems, "the beat cites no `src`", entities)
    if document is None:
        return _unchecked(
            claim,
            problems,
            f"source {claim.src!r} is not in this episode's corpus",
            entities,
        )
    if not claim.quote.strip():
        return _unchecked(
            claim, problems, f"the beat cites {claim.src!r} but quotes nothing", entities
        )

    span = quote_span(claim.quote, document)
    if span is None:
        return Mechanical(
            verdict="fail",
            quote_found=False,
            closest_span=closest_span(claim.quote, document),
            atoms_missing=_number_atoms(claim),
            entities_missing=_missing_entities(entities, claim.quote, document),
            shown_problems=problems,
            reason=f"the quote is not in sources/{claim.src}.txt",
        )

    found = quote_values(claim.quote)
    spelled = quote_spellings(claim.quote)
    occurrences: dict[str, list[Decimal | None]] = {}
    for display, value in claim_values(claim.text):
        occurrences.setdefault(display, []).append(value)

    in_quote: list[str] = []
    missing: list[str] = []
    unreadable: list[str] = []
    for display in _number_atoms(claim):
        seen = occurrences.get(display)
        if seen is None:
            raise VerifyError(
                f"{claim.id}: the record carries the claim number {display!r} but "
                "re-reading `text` does not produce it. The numeric check needs "
                "the magnitude the atom string dropped (`1M` is recorded as "
                "`1`), so it walks the text a second time — and two walks that "
                "disagree mean figures are being checked that nobody extracted, "
                "or extracted that nobody checks"
            )
        if all(value is not None and value in found for value in seen):
            in_quote.append(display)
        elif all(value is None for value in seen):
            # A figure with no value. The comparison falls back to the spelling
            # — never to silence: an exemption here is how `950bn` and `3/4`
            # reached the screen as `pass` with nothing checked at all.
            (in_quote if display in spelled else unreadable).append(display)
        else:
            missing.append(display)

    entities_missing = _missing_entities(entities, claim.quote, document)
    verdict = "fail" if (missing or unreadable or problems) else "pass"
    return Mechanical(
        verdict=verdict,
        quote_found=True,
        quote_span=span,
        atoms_in_quote=tuple(in_quote),
        atoms_in_corpus=tuple(e for e in entities if e not in entities_missing),
        atoms_missing=tuple(missing + unreadable),
        entities_missing=entities_missing,
        shown_problems=problems,
        reason=_reason(missing, unreadable, problems),
    )


def _reason(
    missing: list[str], unreadable: list[str], problems: tuple[str, ...]
) -> str:
    """Why this claim failed, in the words the operator acts on.

    The two numeric refusals are deliberately different sentences, because the
    fixes are different: a wrong value is a rewrite, and a figure this pass
    cannot read is a quote that has to carry it verbatim — or a `claim_override`
    saying why it does not. A refusal that names no token is one nobody can act
    on at all.
    """
    parts = []
    if missing:
        parts.append(
            "the quote does not contain " + ", ".join(missing) + " by value"
        )
    if unreadable:
        parts.append(
            "this pass cannot read " + ", ".join(unreadable) + " as a value, and "
            "the quote does not spell it"
        )
    parts.extend(problems)
    return "; ".join(parts)


def _unchecked(
    claim: Claim, problems: tuple[str, ...], reason: str, entities: tuple[str, ...]
) -> Mechanical:
    """`no_source` — unless the row check already found something wrong.

    `shown` needs no corpus, so an uncited chart is still checked against
    itself. If that check failed, the honest verdict is `fail`: something WAS
    checked and it was wrong.
    """
    return Mechanical(
        verdict="fail" if problems else "no_source",
        quote_found=None,
        atoms_missing=_number_atoms(claim) if not claim.src else (),
        entities_missing=entities,
        shown_problems=problems,
        reason="; ".join([reason, *problems]),
    )


def _missing_entities(
    entities: tuple[str, ...], quote: str, document: str
) -> tuple[str, ...]:
    """§8.2 step 3, recorded but not gated — see this module's docstring.

    "in `quote` or elsewhere in `sources/<src>.txt`", folded on both sides
    (D-081: CSS uppercases every kicker, so an unfolded comparison
    false-positives on the whole series).
    """
    haystack = fold(quote) + "\n" + fold(document)
    return tuple(e for e in entities if fold(e) not in haystack)


# --- the ledger, §8.1 -------------------------------------------------------------------


def corpus_sha(documents: dict[str, str]) -> str:
    """One hash over exactly the documents a check READ.

    Not over the corpus directory: ingesting an unrelated source would then
    invalidate a sound check, and an invalidation nobody believes is worse than
    none. Not over the manifest either — the manifest is a record of what the
    bytes were, and this has to be a record of what they are.
    """
    digest = hashlib.sha256()
    for key in sorted(documents):
        digest.update(key.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(documents[key].encode("utf-8")).digest())
    return digest.hexdigest()


def _span(value: tuple[int, int] | None) -> list[int] | None:
    return None if value is None else [value[0], value[1]]


def _record(claim: Claim, result: Mechanical, carried: dict | None = None) -> dict:
    """§8.1's record shape. The example's VALUES are not reproduced, deliberately.

    Two defects Task 1 flagged in §8.1's worked example, neither load-bearing:
    `id: c-014` on `beat_index: 7` is unreachable under any one-claim-per-beat
    scheme, and its `text` is fluent prose no mechanical walk of a `kpis` beat
    produces. The keys are the contract; the values are not.
    """
    return {
        "id": claim.id,
        "beat_index": claim.beat_index,
        "beat_type": claim.beat_type,
        "text": claim.text,
        "src": claim.src,
        "quote": claim.quote,
        "quote_span": _span(result.quote_span),
        "atoms": [{"kind": a.kind, "value": a.value} for a in claim.atoms],
        "mechanical": {
            "verdict": result.verdict,
            "quote_found": result.quote_found,
            "atoms_in_quote": list(result.atoms_in_quote),
            "atoms_in_corpus": list(result.atoms_in_corpus),
            "atoms_missing": list(result.atoms_missing),
            "entities_missing": list(result.entities_missing),
            "shown_problems": list(result.shown_problems),
            "closest_span": _span(result.closest_span),
            "reason": result.reason,
            "attest": result.attest,
        },
        # Pass 2, §8.3. `None` rather than an absent key: "not judged yet" and
        # "judged and said nothing" must not look the same to the gate. It is
        # never computed here — this module makes no judgements — and it is
        # carried from a previous ledger only when the claim it judged has not
        # moved (`_carry_forward`).
        "adversarial": carried,
        "override": claim.override,
    }


def verify_episode(episode: Episode) -> dict:
    """Run pass 1 over an episode's script and corpus. Returns §8.1's ledger.

    Loads both itself, from the episode it was handed — D-072's standing rule in
    the weaker form this function needs. It is not a gate (it decides nothing and
    writes nothing), but a checker that accepted a pre-loaded `Script` would let
    a caller verify one thing and approve another.
    """
    script = script_mod.load_script(episode)
    beats = {b.index: b for b in script.beats}
    previous = claim_records(read_ledger(episode))

    documents: dict[str, str | None] = {}
    records: list[dict] = []
    for claim in claims_mod.extract_claims(script):
        if claim.src and claim.src not in documents:
            try:
                documents[claim.src] = corpus_mod.document_text(episode, claim.src)
            except corpus_mod.CorpusError:
                documents[claim.src] = None
        document = documents.get(claim.src) if claim.src else None
        fresh = _record(claim, check_claim(claim, document, beat=beats.get(claim.beat_index)))
        fresh["adversarial"] = _carry_forward(fresh, previous)
        records.append(fresh)

    read = {key: text for key, text in documents.items() if text is not None}
    return {
        "episode": script.episode,
        "series": script.series,
        # Microseconds, because two checks a second apart in a test are still
        # two checks. `write_ledger` keeps the previous stamp when nothing else
        # moved, so this never churns the file on its own.
        "checked_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
        "corpus_sha": corpus_sha(read),
        "claims": records,
    }


# --- §8.3's pass 2: a judgement, and everything that makes it stop counting ---------
#
# Nothing in this file makes a pass-2 judgement. The CLI contains no LLM calls
# (CLAUDE.md) and pass 2 is irreducibly a judgement pass, so the skill judges and
# this module stores, binds, expires and gates. Everything below is about the
# difference between a MEASUREMENT and a JUDGEMENT, and about making that
# difference visible to someone who never reads the spec:
#
#   * pass 1 says `checked_at`; pass 2 says `judged_at`, and `judged_by`, because
#     a judgement has an author and a measurement does not;
#   * every block carries `reproducible: false`, and a block that claims
#     otherwise is malformed rather than believed;
#   * every block carries `claim_sha256`, so a verdict about one sentence cannot
#     be read as a verdict about the sentence that replaced it;
#   * and a `supported` expires, because nothing on disk can compare the judge.


def claim_sha256(record: dict) -> str:
    """A digest of WHICH CLAIM this is — the tuple `_script_drift` compares.

    id, beat index, text, src and quote: change any of them and the beat asserts
    something else, or asserts it about other bytes, and a judgement made before
    the change is a judgement of words nobody wrote. Deliberately the same tuple
    the ledger-level drift check uses, so the per-claim rule and the whole-ledger
    rule cannot disagree about what "the same claim" means.

    The mechanical verdict is NOT in it. Pass 1 re-running and reaching the same
    answer about the same sentence does not invalidate an argument about that
    sentence — and a digest that changed with every re-check would make the
    binding fire constantly, which is how a real invalidation stops being read.
    """
    identity = [
        record.get("id"),
        record.get("beat_index"),
        record.get("text"),
        record.get("src"),
        record.get("quote"),
    ]
    return hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _carry_forward(record: dict, previous: list[dict]) -> dict | None:
    """A previous ledger's verdict for this exact claim, or None.

    **Why carry anything at all.** §8.3 runs one refuter per claim and a real
    episode has around 24. If a re-check threw every judgement away, an operator
    who fixes one beat pays for 24 fresh judgements — and a pass that expensive
    is one people stop running, which costs more than it saves.

    **Why it is safe.** The rule is the same one the gate applies, in one place:
    a block is carried only when it says it judged this exact claim
    (`claim_sha256`), and `classify` re-checks that on the file it reads rather
    than trusting this function to have been right. A malformed block is carried
    too — it refuses either way, and dropping it would turn "judged badly" into
    "not judged yet", which is the one distinction R3 asks for.
    """
    digest = claim_sha256(record)
    for old in previous:
        if old.get("id") != record.get("id"):
            continue
        block = old.get("adversarial")
        if isinstance(block, dict) and block.get("claim_sha256") == digest:
            return block
        return None
    return None


def adversarial_state(record: dict) -> tuple[str, str]:
    """(what pass 2 says about this claim, why it does not clear it).

    States: `unjudged` · `supported` · `unsupported` · `refuted` · `malformed` ·
    `stale` · `expired`. The second element is empty exactly when the state
    clears the claim, and it is the sentence the screens print.

    **`unjudged` is not a refusal.** §8.4's list is `fail`, `refuted`,
    `unsupported`, `no_source` and unattested `manual`; absence of a judgement is
    not on it, and making it one would leave the project unable to approve
    anything between this task and the skill that does the judging. Coverage is
    REPORTED instead — on both screens and in the approval record — so an
    episode signed with pass 2 never run cannot be mistaken for one pass 2
    cleared.

    **It fails closed on everything it can read badly** (D-113, D-106): an
    unknown verdict, a missing or blank `attempted_refutation`, an unparseable
    timestamp, a block that is not an object at all. A judgement nobody can read
    is not a judgement.

    **`attempted_refutation` is required and non-empty**, and that is the point
    of the whole record. A `supported` with no account of what was attacked
    records that somebody looked, which is worth nothing — and this project has
    printed a conclusion stronger than its evidence four times (D-106, D-110,
    D-112, D-118). This field is the evidence.

    **The order of the checks is an argument.** Shape, then binding, then the
    verdict, then expiry — so that an old `refuted` still reads as `refuted`.
    Age makes a `supported` less believable; it does not make a refutation less
    alarming, and "re-judge this" is the wrong remedy to print over "a refuter
    knocked this claim over".
    """
    block = record.get("adversarial")
    if block is None:
        return "unjudged", ""
    if not isinstance(block, dict):
        return "malformed", "the adversarial block is not an object"

    verdict = block.get("verdict")
    if verdict not in ADVERSARIAL_VERDICTS:
        return "malformed", (
            f"pass 2 recorded {verdict!r}, which is not one of "
            f"{' · '.join(ADVERSARIAL_VERDICTS)}"
        )
    refutation = block.get("attempted_refutation")
    if not isinstance(refutation, str) or not refutation.strip():
        return "malformed", (
            "no `attempted_refutation` — a verdict with no account of what was "
            "attacked records only that somebody looked"
        )
    if not isinstance(block.get("judged_by"), str) or not block["judged_by"].strip():
        return "malformed", (
            "no `judged_by` — pass 2 is a judgement, and a judgement with no "
            "author is not one"
        )
    if block.get("reproducible") is not False:
        return "malformed", (
            "`reproducible` must be recorded as false: pass 2 is a judgement, "
            "and a ledger that says otherwise is one nobody may act on"
        )
    risk = block.get("residual_risk")
    if risk is not None and not isinstance(risk, str):
        return "malformed", "`residual_risk` must be a sentence or absent"
    judged_at = _judged_at(block)
    if judged_at is None:
        return "malformed", (
            f"`judged_at` is {block.get('judged_at')!r}, which is not a "
            "timestamp — so nothing can say how old this judgement is"
        )

    if block.get("claim_sha256") != claim_sha256(record):
        return "stale", (
            "this judgement was made about different words: the beat, its "
            "source or its quote has changed since. Re-judge the claim"
        )
    if verdict != "supported":
        # No "pass 2 found…" prefix: the screens print this under a `pass 2`
        # label and beside a row that already says the verdict, and a sentence
        # that repeats both reads as a stutter on the one screen an operator is
        # meant to read word by word.
        return verdict, f"{verdict} — {refutation.strip()}"
    age = (datetime.now().astimezone() - judged_at).days
    if age > PASS2_HORIZON_DAYS:
        return "expired", (
            f"this judgement is {age} days old and pass 2 verdicts expire after "
            f"{PASS2_HORIZON_DAYS} days. Pass 1 re-runs to the same answer in a "
            "year; pass 2 does not, and nothing on disk can compare the judge"
        )
    return "supported", ""


def _judged_at(block: dict) -> datetime | None:
    """The judgement's timestamp, as an aware datetime, or None if unreadable.

    Naive stamps are read as local time rather than refused: `datetime.now()` is
    what wrote them, and refusing one would fail closed on a value that is
    simply less precise, not wrong.
    """
    value = block.get("judged_at")
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.astimezone()


def adversarial_clears(record: dict) -> bool:
    """Does pass 2 leave this claim approvable? Derived, never restated."""
    return adversarial_state(record)[0] in ("unjudged", "supported")


def pass2_tally(records: list[dict]) -> dict:
    """What pass 2 covered, for a screen and for the approval record.

    `reproducible` is in it because the approval artifact is read by whoever
    inherits this episode, and a count of judgements that does not say what kind
    of thing was counted is the overclaim this project keeps making.
    """
    states = [adversarial_state(r)[0] for r in records]
    return {
        "total": len(records),
        "judged": sum(1 for s in states if s != "unjudged"),
        "unjudged": states.count("unjudged"),
        "supported": states.count("supported"),
        "refuted": states.count("refuted"),
        "unsupported": states.count("unsupported"),
        "reproducible": False,
    }


def judgement(record: dict) -> dict | None:
    """What pass 2 recorded here, as a screen may show it, or None.

    **The only reader of the `adversarial` block outside this module.** Every
    screen goes through this and through `adversarial_state`, so there is no
    second place the block is interpreted — the D-059 shape, which is exactly a
    display and a gate reading one field two ways.

    Returns None for `unjudged` and for `malformed`: a block nothing can read
    must not have its `residual_risk` quoted as though the rest of it were
    sound. `stale` and `expired` blocks ARE returned, with their state, because
    an operator has to see the judgement that stopped counting.

    `expires_on` is computed here rather than stored. A stored expiry is a
    second copy of one rule, and the copy a hand-edit can push to 2099.
    """
    state, _ = adversarial_state(record)
    if state in ("unjudged", "malformed"):
        return None
    block = record.get("adversarial") or {}
    stamp = _judged_at(block)
    return {
        "state": state,
        "verdict": block.get("verdict"),
        "judged_by": block.get("judged_by"),
        "judged_at": block.get("judged_at"),
        "residual_risk": block.get("residual_risk"),
        "attempted_refutation": block.get("attempted_refutation"),
        "expires_on": (
            None
            if stamp is None
            else (stamp + timedelta(days=PASS2_HORIZON_DAYS)).date().isoformat()
        ),
    }


def record_adversarial(
    episode: Episode,
    claim_id: str,
    *,
    verdict: str,
    attempted_refutation: str,
    by: str,
    residual_risk: str | None = None,
    now: str | None = None,
) -> dict:
    """Write one pass-2 verdict into `claims.json`, or raise. Returns the block.

    Takes IDENTIFIERS and loads the ledger itself (D-072): there is no argument
    a caller can shape to record a verdict against a claim other than the one on
    disk under this id.

    It refuses, rather than storing something a later screen has to explain:

      * a ledger that is missing or stale — a judgement of a script that has
        moved is a judgement of words nobody wrote, and the remedy is `check`;
      * an unknown claim id — a verdict silently dropped on a typo means the
        skill reports 24 judgements and the file holds 23;
      * a claim pass 1 did not clear — §8.3 runs pass 2 on claims that SURVIVE
        pass 1, and two disagreeing verdicts on one claim is a screen nobody can
        read;
      * a verdict outside §8.3's three, or a blank `attempted_refutation`.

    Re-judging replaces the block. It has to: expiry and the binding both make
    "judge this again" the remedy, and a writer that refused because a verdict
    was already there would leave no way to take it.
    """
    ledger = read_ledger(episode)
    stale = stale_reason(episode, ledger)
    if stale:
        raise VerifyError(
            f"pass 2 has nothing to judge — {stale}. Run `agsoc video check` "
            "first: a judgement is recorded against a claim pass 1 has written down"
        )
    if verdict not in ADVERSARIAL_VERDICTS:
        raise VerifyError(
            f"{verdict!r} is not a pass-2 verdict — §8.3 has three: "
            f"{' · '.join(ADVERSARIAL_VERDICTS)}"
        )
    if not isinstance(attempted_refutation, str) or not attempted_refutation.strip():
        raise VerifyError(
            "a verdict needs its `attempted_refutation`: what did you attack, "
            "and what did the source say? A verdict without it records only "
            "that somebody looked"
        )
    if not (by or "").strip():
        raise VerifyError(
            "a judgement needs an author: pass `--by`. It is the only account "
            "of who — or what — made this call"
        )

    records = claim_records(ledger)
    record = next((r for r in records if r.get("id") == claim_id), None)
    if record is None:
        raise VerifyError(
            f"no claim {claim_id!r} in {CLAIMS_NAME} — it holds "
            f"{', '.join(str(r.get('id')) for r in records) or 'no claims'}"
        )
    if (record.get("mechanical") or {}).get("verdict") != "pass":
        raise VerifyError(
            f"{claim_id} did not clear pass 1 "
            f"({(record.get('mechanical') or {}).get('verdict')}), and §8.3 "
            "judges what survives pass 1. Fix the claim, then judge it"
        )

    block = {
        "verdict": verdict,
        "attempted_refutation": attempted_refutation.strip(),
        "residual_risk": residual_risk.strip() if (residual_risk or "").strip() else None,
        "judged_by": by.strip(),
        # Not `checked_at`. The word is different because the thing is: a
        # measurement's timestamp says when the bytes were read, and this says
        # when somebody argued about them.
        "judged_at": now or datetime.now().astimezone().isoformat(timespec="seconds"),
        "claim_sha256": claim_sha256(record),
        "reproducible": False,
    }
    record["adversarial"] = block
    write_ledger(episode, ledger)
    return block


def classify(record: dict) -> str:
    """`verified` · `attested` · `overridden` · `open` — one answer per claim.

    This is the single place §8.4's list is spelled out. `check`'s summary,
    `review`'s table and `approve`'s gate all derive from it, because two paths
    to one answer is the D-059 shape: the bypass that published a draft was a
    gate and a second writer that disagreed about the same episode.

    **It fails closed.** Anything this function does not recognise — a verdict
    from a phase that does not exist yet, a hand-edited ledger, a record with no
    `mechanical` block at all — is `open`. The predicate used to name the
    blocking verdicts (`fail`, `no_source`) and answer "not blocking" for
    everything else, so `verdict: supported` would have approved with nothing
    checked. That is D-106's failure exactly: a value the rule cannot read
    treated as *nothing to check* rather than *cannot be checked*.

    **The measurement is consulted before the override.** A claim that passes
    on its own is `verified` whether or not someone wrote a sentence about it,
    so nobody ever has to delete an override to make a passing claim read as
    passing — and the override that is left over is reported as stale rather
    than silently doing nothing (`stale_override`).

    Written over the ledger RECORD, not over `Mechanical`, because the record is
    what survives to the gate. A `manual` claim whose `attest` was lost between
    the check and the file is unattested to everyone who reads the file.
    """
    if not adversarial_clears(record):
        # Pass 2 VETOES, and it is checked first, because the claims it catches
        # are the ones pass 1 says are fine: right number, wrong subject. A
        # `refuted` claim whose figures are all in the quote would read
        # `verified` under the measurement-first rule below, which would put a
        # green word on the line the gate is about to refuse.
        #
        # §8.4's override still clears it — "the only way past", for every
        # refusal on the list, and a pass-2 refusal is on the list. An override
        # doing that work is not stale, because `stale_override` asks this same
        # function.
        return "overridden" if override_state(record)[0] is not None else "open"
    mechanical = record.get("mechanical") or {}
    verdict = mechanical.get("verdict")
    if verdict == "pass":
        return "verified"
    if verdict == "manual" and str(mechanical.get("attest") or "").strip():
        return "attested"
    if override_state(record)[0] is not None:
        return "overridden"
    return "open"


# --- §8.4's override ---------------------------------------------------------------


def override_state(record: dict) -> tuple[dict | None, str | None]:
    """(the override §8.4 honours, why a written one is not honoured).

    `(None, None)` means none was written, which is the normal case and the
    silent one — a screen that mentions overrides on every clean run is a
    screen whose mention gets tuned out.

    **The validity rule is `script.claim_override`, called rather than
    restated.** Two copies of "a written sentence with your name on it" drift
    the first time either is tuned, and the drifted copy is the checkbox §8.4
    says this must never be — the D-036 pattern, in the one place it would cost
    a claim.

    **Re-validated here even though the loader already refused it.**
    `claims.json` is a file on disk. A gate that trusts an earlier pass to have
    refused clears a claim on `{}` the moment anyone hand-edits the artifact, so
    this fails closed like everything else `classify` reads.
    """
    value = record.get("override")
    if value is None:
        return None, None
    fault = script_mod.claim_override(value)
    return (None, fault) if fault else (value, None)


def stale_override(record: dict) -> dict | None:
    """A written override on a claim that clears without it, or None.

    Not a refusal: the remedy for one is *delete the paragraph you wrote*, and a
    gate that demands that inverts §8.4's cost asymmetry. It is a warning
    because a sentence that bypasses nothing is how the sentences stop being
    read — and the next real one is read with them.
    """
    applied, _ = override_state(record)
    return applied if applied is not None and classify(record) != "overridden" else None


def claim_tally(records: list[dict]) -> dict[str, int]:
    """One count per state, and every claim in exactly one bucket.

    The gate's own arithmetic, so a summary cannot round toward reassurance by
    dropping a claim from the denominator (D-112). `total` minus the three named
    states is the number that is open, and it is not stored: a fourth stored
    count is a fourth thing that can be wrong on its own.
    """
    kinds = [classify(record) for record in records]
    return {
        "total": len(records),
        "verified": kinds.count("verified"),
        "attested": kinds.count("attested"),
        "overridden": kinds.count("overridden"),
    }


def is_blocking(record: dict) -> bool:
    """Would §8.4 refuse this claim? Derived from `classify`, never restated."""
    return classify(record) == "open"


def claim_records(ledger: dict | None) -> list[dict]:
    """The ledger's claim records, defensively — a ledger is a file on disk."""
    if not isinstance(ledger, dict):
        return []
    return [r for r in (ledger.get("claims") or []) if isinstance(r, dict)]


def open_claims(records: list[dict]) -> list[dict]:
    """Every claim §8.4 refuses on. `approve` gates on exactly this list."""
    return [r for r in records if is_blocking(r)]


def ledger_path(episode: Episode) -> Path:
    return episode.dir / CLAIMS_NAME


def read_ledger(episode: Episode) -> dict | None:
    path = ledger_path(episode)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        raise VerifyError(f"{path}: {CLAIMS_NAME} is unreadable — {e}")
    if not isinstance(data, dict):
        raise VerifyError(f"{path}: {CLAIMS_NAME} must be an object")
    return data


def _findings(ledger: dict) -> dict:
    return {key: value for key, value in ledger.items() if key != "checked_at"}


def write_ledger(episode: Episode, ledger: dict) -> Path:
    """Write `claims.json`, atomically, and only when something has changed.

    `checked_at` is a clock reading, so the naive version produces a different
    file on every run and turns the ledger into a diff nobody reads — at which
    point a real change is invisible in the noise. An unchanged re-check keeps
    the previous file byte for byte, mtime included.
    """
    path = ledger_path(episode)
    previous = read_ledger(episode)
    if previous is not None and _findings(previous) == _findings(ledger):
        return path
    atomic_write(path, json.dumps(ledger, indent=2, ensure_ascii=False) + "\n")
    return path


def _script_drift(episode: Episode, ledger: dict) -> str | None:
    """Has the script moved under this ledger? `corpus_sha` cannot see it.

    The corpus half answers for the bytes a claim was checked AGAINST. This is
    the other half: the beats themselves. Rewrite a figure and every verdict in
    `claims.json` still lines up by `beat_index` and is now about a sentence
    nobody wrote — the same lie as a stale corpus, arriving through the other
    door.

    Compared on the CLAIMS the script produces, not on the file's bytes: a
    reformatted comment is not a changed assertion, and a check invalidated by
    whitespace is one operators re-run without reading.
    """
    try:
        script = script_mod.load_script(episode)
    except script_mod.ScriptError as e:
        return f"the script no longer loads, so nothing can be compared — {e}"
    try:
        claims = claims_mod.extract_claims(script)
    except claims_mod.ClaimsError as e:
        return f"the script no longer yields claims to compare — {e}"
    recorded = [
        (r.get("id"), r.get("beat_index"), r.get("text"), r.get("src"), r.get("quote"))
        for r in (ledger.get("claims") or [])
        if isinstance(r, dict)
    ]
    current = [(c.id, c.beat_index, c.text, c.src, c.quote) for c in claims]
    if recorded != current:
        return "the script has changed since this check was written"
    return None


def stale_reason(episode: Episode, ledger: dict | None) -> str | None:
    """Why this ledger no longer describes what is on disk, or None.

    R3: recording `corpus_sha` and never comparing it is a field, not a
    guarantee. Task 3's `check` and Phase 7's `approve` both need this answer
    and must not each invent their own — and until F3 was found, the script
    half WAS invented separately, as a display helper in `cli.py`. An `approve`
    written to this docstring got `None` for an edited script and would have
    approved a ledger describing sentences nobody wrote. Both halves live here
    now, and both load what they compare from the episode themselves (D-072).
    """
    if ledger is None:
        return f"no {CLAIMS_NAME} — run `agsoc video check` first"
    if not isinstance(ledger.get("corpus_sha"), str):
        return f"{CLAIMS_NAME} records no corpus_sha"
    if ledger.get("episode") != episode.id:
        return (
            f"{CLAIMS_NAME} was written for episode {ledger.get('episode')!r}, "
            f"not {episode.id!r}"
        )

    documents: dict[str, str] = {}
    for record in ledger.get("claims", []) or []:
        src = record.get("src") if isinstance(record, dict) else None
        if not isinstance(src, str) or not src or src in documents:
            continue
        try:
            documents[src] = corpus_mod.document_text(episode, src)
        except corpus_mod.CorpusError:
            continue
    if corpus_sha(documents) != ledger["corpus_sha"]:
        return "the corpus has changed since this check was written — re-run it"
    return _script_drift(episode, ledger)

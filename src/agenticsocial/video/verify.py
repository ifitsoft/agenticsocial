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
from datetime import datetime
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


def _record(claim: Claim, result: Mechanical) -> dict:
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
        # Phase 9 fills this in. `None` rather than an absent key: "not run yet"
        # and "ran and said nothing" must not look the same to the gate.
        "adversarial": None,
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

    documents: dict[str, str | None] = {}
    records: list[dict] = []
    for claim in claims_mod.extract_claims(script):
        if claim.src and claim.src not in documents:
            try:
                documents[claim.src] = corpus_mod.document_text(episode, claim.src)
            except corpus_mod.CorpusError:
                documents[claim.src] = None
        document = documents.get(claim.src) if claim.src else None
        records.append(
            _record(claim, check_claim(claim, document, beat=beats.get(claim.beat_index)))
        )

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


def stale_reason(episode: Episode, ledger: dict | None) -> str | None:
    """Why this ledger no longer describes what is on disk, or None.

    R3: recording `corpus_sha` and never comparing it is a field, not a
    guarantee. Task 3's `check` and Phase 7's `approve` both need this answer
    and must not each invent their own.
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
    return None

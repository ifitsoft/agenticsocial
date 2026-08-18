"""Turning a `Script` into claim records — spec §8.1, §8.2.1, §8.2.2.

This module answers one question: **what does a beat assert?** Task 2 checks
those assertions against the corpus; Task 3 runs the command. Nothing here
reads the corpus, opens a socket or writes a byte.

Extraction is where the false-refusal rate is set. Too greedy and every product
name becomes a claim the operator must override; too shy and a figure ships
unchecked. D-040's failure mode is a gate that cries wolf until overrides are
reflexive, at which point the gate is theatre.

**The trap this module is written around.** It has to decide what text a beat
renders — and `engine/planbuild.js` already decided that, independently, in
JavaScript, when it built the DOM. Two answers to one question, with nothing
making them agree: if Python thinks a `list` renders only `lead` while the
builder renders `lead` and every item, the figures inside `items` are never
extracted, never checked, and ship while `check` reports pass.

So the prose-bearing fields are **derived from the catalogue**, never listed:
`COLLECTORS` is keyed by the CHECKER FUNCTION from `script.BEAT_TYPES`, so a
field added to §7.1 as `"tagline": text` is extracted the day it is added, and
a field with a new checker raises `ClaimsError` until someone decides whether it
reaches the frame. `tests/test_video_claims.py` holds the same enumeration
against `planbuild.js`'s own `b.`/`r.`/`it.` property reads. What that does not
catch is a field both files know about and this one classifies wrongly — see the
Task 1 report.

Four decisions that are this module's rather than the spec's:

  * **A token that begins with a digit is a figure; one that begins with a
    letter is an identifier.** That is the whole boundary (`figure`), and it is
    what keeps D-071's exemptions — `V4-Pro`, `Qwen3.8-Max`, `GPT-5.6`, `M1` —
    while refusing to let `950bn` or `3/4` be exempt for the same reason. A
    figure this module cannot value is still a figure: it is returned with no
    value, and §8.2 then demands the quote spell it. Nothing numeric-looking is
    silently dropped, because a silent drop and a clean pass are the same
    screen.

  * **Years and list ordinals stay claim numbers** (D-092). The rule is
    digits-only with no shape or range exemption. A stale date presented as
    current is a failure mode §8.3 names, and the year is the only part of it a
    mechanical pass can see; any "is this a year?" test is a range check that
    would also exempt `2026 GPUs`. Cost, stated: a beat that renders a date its
    quote does not contain is refused, and the answer is a better quote or a
    written `claim_override`.
  * **Entity atoms are orthographic** — capitalisation and internal case, with a
    function-word stoplist that applies at a sentence opening only. "Every
    proper noun" (§8.2 step 3) has no mechanical definition without an NLP
    dependency and there is none. It over-generates, which is the cheap
    direction: an entity is looked for anywhere in the source file, and the
    words it wrongly captures are common words a source contains everywhere.
  * **`shown` is tag-stripped, not exempted** (D-081). It is the one field where
    the frame and the script legitimately differ; the digits inside it are still
    a claim.
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from . import script as script_mod

# The engine's own formatter, imported rather than re-derived: `count()` renders
# `decimals ? v.toFixed(decimals) : Math.round(v)`, and script.py already owns
# the Python spelling of that (half-UP, not half-to-even). A second copy here
# would be the same divergence this module exists to prevent, in miniature.
from .script import Beat, Script, _as_displayed


class ClaimsError(Exception):
    pass


# --- §8.2.1 comparison folding ------------------------------------------------------
# Applied to the COMPARISON ONLY. The corpus keeps its bytes, the quote keeps
# its bytes, and sha256 still covers the originals — normalising on disk would
# break the integrity guarantee §4 rests on.
#
# An explicit table, not `unicodedata.normalize("NFKC", …)`. Measured (D-091):
# NFKC fixes the space family, leaves en dash, em dash and minus untouched, and
# maps U+2011 to U+2010 — *another* non-ASCII hyphen, so `V4‑Pro` still fails to
# match `V4-Pro` while a check written "is U+2011 gone?" answers yes. The
# question is whether the fold reached ASCII.
#
# No entry is a digit, and none may ever be. That is what makes folding
# one-directional: it can turn a false refusal into a pass, never a false claim
# into a verified one.
FOLD_TABLE: dict[str, str] = {
    # hyphens and dashes
    "‐": "-",
    "‑": "-",  # NON-BREAKING HYPHEN — the real case, from a real source
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
    "−": "-",
    # single quotes
    "‘": "'",
    "’": "'",
    "‛": "'",
    # double quotes
    "“": '"',
    "”": '"',
    "‟": '"',
    # spaces (runs of whitespace collapse below)
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    # ellipsis
    "…": "...",
}

_FOLD = str.maketrans(FOLD_TABLE)
_WHITESPACE = re.compile(r"\s+")


def fold(text: str) -> str:
    """§8.2.1, for comparison only. Never write the result anywhere.

    Whitespace runs collapse to one space and the ends are stripped: a `quote:`
    written across three indented YAML lines arrives with newlines inside it and
    the source has one space. Then case-fold — D-081, because CSS uppercases
    every kicker and a comparison that is not case-folded false-positives on all
    of them.
    """
    return _WHITESPACE.sub(" ", text.translate(_FOLD)).strip().casefold()


# --- §8.2.2 claim numbers vs identifier digits ---------------------------------------

# The suffix set is spec §8.2.2's, and it is stripped from the END only. `1M` is
# one million and `M1` is a chip: a rule that strips from both ends turns the
# chip into a claim on the number 1. Lowercase spellings are included because
# `95b` is the same figure as `95B` and the direction of that error is the one
# D-071 got wrong first — "any letters means identifier" exempted `1M` and
# `95B`, which would let a beat claim `95B active` against a source saying `9B`.
UNIT_SUFFIXES = frozenset("%KMBTXkmbtx")

# The same idea spelled with more than one letter, longest first. §8.2.2 strips
# exactly ONE trailing character, so `950bn` failed the digits-only test, was
# classified an identifier, was ALSO rejected as a name — and yielded no atom at
# all. A 10x fabrication verified clean on the operator's own episode, through
# the spelling the rule did not know. A closed list, not a "trailing letters"
# rule: the letters have to mean something, or the token falls to the unvaluable
# branch below rather than being guessed at.
UNIT_WORDS = ("bps", "bn", "mn", "tn")

# Digits and the two separators that appear INSIDE a written number. A `-` is
# not here on purpose: `0-70` is a range and `V4-Pro` is a name. Neither is a
# number this module can value, and neither is exempt — see `figure`.
_DIGITS_ONLY = re.compile(r"^[0-9][0-9.,]*$")

# After §8.2.1's fold, every dash in the table above is this one character, so a
# sign test needs to know exactly one codepoint. It is deliberately checked on
# FOLDED text: `claims.atoms` walks the beat and `verify.claim_values` walks the
# folded beat, and two spellings of the same figure would break the guard that
# holds those two walks together.
_MINUS = "-"


def _strippable(ch: str) -> bool:
    """Punctuation or a non-currency symbol — the stuff a token is wrapped in.

    Category-driven rather than a character list: `**1,100%**` is markdown
    emphasis, `(1M)` is a parenthesis, `200+` is a math symbol and `60"` is a
    quote mark, and all four are decoration around a figure. Currency (`Sc`) is
    deliberately excluded — §8.2.2 strips it as its own step, and it must be
    LEADING to count.
    """
    category = unicodedata.category(ch)
    return category.startswith("P") or (category.startswith("S") and category != "Sc")


def _edges(token: str) -> tuple[int, int]:
    start, end = 0, len(token)
    while start < end and _strippable(token[start]):
        start += 1
    while end > start and _strippable(token[end - 1]):
        end -= 1
    return start, end


def _bare(token: str) -> str:
    start, end = _edges(token)
    return token[start:end]


@dataclass(frozen=True)
class Figure:
    """A token that asserts a quantity — §8.2.2's claim number, plus a sign.

    `digits` is None for a figure this module cannot READ: `1e9`, `3/4`,
    `12:30`, `2010-2011`, `٣٠٠`. Those are not identifiers and they are not
    exempt; they carry no value to compare, so §8.2 checks them by the only
    honest comparison left — the quote must spell them exactly.
    """

    display: str  # what the atom records and what a refusal names
    digits: str | None  # digits and separators, sign included; None if unreadable
    suffix: str  # "" or the unit/magnitude the digits were glued to


def figure(token: str) -> Figure | None:
    """What this token asserts, or None if it is an identifier and exempt.

    **The boundary, with its negative half.** Strip the surrounding punctuation,
    a leading currency symbol and a sign; if what is left BEGINS WITH A DIGIT
    the token is a figure and something must check it. If it begins with a
    letter it is an identifier and is exempt — every name in §8.2.2's own table
    (`V4-Pro`, `Qwen3.8-Max`, `GPT-5.6`) and the `M1` chip begin with a letter,
    so D-071's rule, validated twice against real prose, costs nothing here.

    A figure whose digits and suffix the rule can read is compared by value. One
    it cannot is still returned, with `digits=None`: *"I cannot read this
    figure"* and *"this figure is fine"* must never produce the same verdict,
    and until this function returned something for `950bn` they did — the token
    was neither a number nor a name, so it yielded no atom and nothing checked
    it at all.

    The sign belongs to the figure. `-` is `Pd` and U+2212 is `Sm`, so both were
    stripped as decoration and a beat saying revenue fell 18% verified against a
    source saying it rose. A sign is GLUED to its digits; a hyphen with anything
    else on its left (`2010-2011`) is punctuation and is left where it is.
    """
    folded = fold(token)
    start, end = _edges(folded)
    body = folded[start:end]
    sign = _MINUS if start and folded[start - 1] == _MINUS else ""
    if body[:1] and unicodedata.category(body[0]) == "Sc":
        body = body[1:]
    if body[:1] == _MINUS:
        sign, body = _MINUS, body[1:]
    if not body or unicodedata.category(body[0]) != "Nd":
        return None

    suffix = ""
    for word in UNIT_WORDS:
        if len(body) > len(word) and body.endswith(word):
            suffix = word
            break
    else:
        if len(body) > 1 and body[-1] in UNIT_SUFFIXES:
            suffix = body[-1]
    digits = body[: len(body) - len(suffix)] if suffix else body

    if _DIGITS_ONLY.match(digits):
        return Figure(sign + digits, sign + digits, suffix)
    return Figure(sign + body, None, "")


def claim_number(token: str) -> str | None:
    """The figure this token asserts, or None if it is an identifier.

    §8.2.2's spelling of `figure().display`, kept because it is the question
    most callers ask. In `Gemini 3.7 Flash` the token `3.7` stands alone and is
    checked, because a beat saying 3.7 where the source says 3.6 is the error
    this pass exists to catch; the `3.8` in `Qwen3.8-Max` is not.
    """
    found = figure(token)
    return None if found is None else found.display


# --- entities (§8.2 step 3) -----------------------------------------------------------

# Applied ONLY to a token that opens a sentence, where "The rollout …" would
# otherwise file a claim on the word "The". Elsewhere a capital is evidence.
# This is a stoplist of function words and nothing else: an adjective here
# ("New") would drop "New York", and the failure would be silent.
SENTENCE_STOPWORDS = frozenset(
    """a an and as at because before both but by each every for from he her here his
    how however if in into it its meanwhile more most no not of on one only or our
    over per she so than that the their them then there these they this those to two
    under until us via we what when where which while who why with without you your
    """.split()
)

_SENTENCE_END = ".!?:;"
_CLOSERS = "\"')]}"
_POSSESSIVE = re.compile(r"['’]s$")


def _name_token(token: str) -> str | None:
    """The entity spelling of this token, or None if it does not look like a name.

    Orthographic and nothing more: a leading capital, or an internal one
    (`iPhone`, `GPT-5.6`). The possessive is dropped — a source says "Google"
    far more often than "Google's", and an atom nobody can find in the corpus is
    a false refusal.

    **A figure is never a name.** D-106 drew one boundary for the whole module —
    a token beginning with a digit is a figure, one beginning with a letter is
    an identifier — and this function did not have it: it asked only whether a
    capital appeared anywhere, so `2.4T` and `95B` were filed as figures AND as
    entities. The figure half verified by value; the entity half was looked for
    verbatim in the corpus, was absent from a source writing "2.4 trillion", and
    landed the token in `check`'s "names not found" list. D-102 left that list
    ungated on the argument that it stays worth reading, and a
    correctly-verified figure sitting in it is precisely the noise that ends
    that. One boundary, asked once, in `claim_number`.

    Note this drops the token from the NAME side only. It is still a number
    atom, still compared by value, and — via `_entity_runs`' `pending` path —
    still joins a name run it sits inside, so `Gemini 3.7 Flash` is unchanged.
    """
    bare = _POSSESSIVE.sub("", _bare(token))
    if not any(ch.isalpha() for ch in bare):
        return None
    if claim_number(token) is not None:
        return None
    if bare[0].isupper() or any(ch.isupper() for ch in bare[1:]):
        return bare
    return None


def _entity_runs(text: str) -> list[str]:
    """Maximal runs of adjacent name tokens, numbers allowed inside them.

    The spec's own example atom is `Gemini 3.7 Flash`: a numeric token between
    two names belongs to the name, and is separately a claim number (R3).
    """
    found: list[str] = []
    for line in text.split("\n"):
        run: list[str] = []
        pending: list[str] = []
        opening = True
        for token in line.split():
            name = _name_token(token)
            if name is not None and opening and name.casefold() in SENTENCE_STOPWORDS:
                name = None
            if name is not None:
                run.extend(pending)
                pending = []
                run.append(name)
            elif run and claim_number(token) is not None:
                pending.append(_bare(token))
            else:
                if run:
                    found.append(" ".join(run))
                run, pending = [], []
            stripped = token.rstrip(_CLOSERS)
            opening = bool(stripped) and stripped[-1] in _SENTENCE_END
        if run:
            found.append(" ".join(run))
    return found


# --- the atoms -------------------------------------------------------------------------


@dataclass(frozen=True)
class Atom:
    kind: str  # "number" | "entity"
    value: str


def _ordered(values) -> list[str]:
    """Deduplicated, first occurrence wins. A figure stated twice is one claim."""
    return list(dict.fromkeys(values))


def atoms(text: str) -> tuple[Atom, ...]:
    """Every claim number and every entity in a beat's rendered text.

    An empty tuple is a legitimate outcome — a prose beat with no figures and no
    names is a real beat, and Task 2 still gives it a verdict.
    """
    # Tokenised on the FOLDED text, which is what `verify.claim_values` walks.
    # Two tokenisations of one string is the divergence D-096 is about in
    # miniature: a non-breaking space between a figure and its unit makes one
    # token here and two there, and `check_claim` raises when the two walks
    # disagree about what the beat says.
    numbers = _ordered(
        value
        for value in (claim_number(token) for token in fold(text).split())
        if value is not None
    )
    entities = _ordered(_entity_runs(text))
    return tuple(
        [Atom("number", value) for value in numbers]
        + [Atom("entity", value) for value in entities]
    )


# --- what a beat renders ----------------------------------------------------------------

Collector = Callable[[Any], list[str]]


def _number_text(value: Any) -> str:
    """A number as the shortest string that round-trips it."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return str(value) if isinstance(value, int) else repr(value)


def _string(value: Any) -> list[str]:
    return [value] if isinstance(value, str) and value.strip() else []


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _kpi_text(items: Any) -> list[str]:
    """`prefix + toFixed(decimals) + unit`, then the label — what the frame shows.

    The figure the viewer reads is the FORMATTED one. Extracting the float's
    Python repr instead would check a string the frame never shows: `value: 2`
    at `decimals: 2` is `2.00` on screen.
    """
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        prefix = item.get("prefix") if isinstance(item.get("prefix"), str) else ""
        unit = item.get("unit") if isinstance(item.get("unit"), str) else ""
        value = item.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            decimals = item.get("decimals", 0)
            if not isinstance(decimals, int) or isinstance(decimals, bool):
                decimals = 0
            shown = _as_displayed(value, decimals)
        else:
            shown = str(value)
        out.append(f"{prefix}{shown}{unit}")
        out.extend(_string(item.get("label")))
    return out


def _shown_text(value: str) -> str:
    """`shown` as the viewer reads it: the tags gone, the references decoded.

    D-081 asked for "an explicit exemption or tag-stripped comparison" and this
    is the second one. Exempting the field would put its digits beyond every
    check — `shown: "… &rarr; 91.7"` on a row whose `after` is 43.6 states a
    figure the bar does not draw. The vocabulary is closed to `<s>`, `</s>` and
    character references (script.py `shown_markup`), so this needs no parser.
    """
    return html.unescape(re.sub(r"</?s>", "", value))


def _jump_text(rows: Any) -> list[str]:
    """Row labels, the `shown` cell, and the values the bars are drawn from.

    `before`/`after` reach the frame as geometry rather than as glyphs, and they
    are still claims: §7.2 is written about numbers, not about text — "every
    numeric `value` must appear inside that `quote`".
    """
    out: list[str] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.extend(_string(row.get("label")))
        if isinstance(row.get("shown"), str):
            out.append(_shown_text(row["shown"]))
        for name in ("before", "after"):
            if isinstance(row.get(name), (int, float)) and not isinstance(
                row.get(name), bool
            ):
                out.append(_number_text(row[name]))
    return out


def _dumbbell_text(rows: Any) -> list[str]:
    """Labels and notes. NOT `values` — see IGNORED_FIELDS."""
    out: list[str] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.extend(_string(row.get("label")))
        out.extend(_string(row.get("note")))
    return out


# Keyed by the CHECKER, not by the field name. That is the whole mechanism: a
# field added to §7.1 as `"tagline": text` is collected on the day it is added,
# and a field with a checker that is not here raises rather than being skipped —
# silently skipped is indistinguishable from checked.
#
# `None` means "reaches nothing a viewer reads as a claim", and every such field
# carries its reason in IGNORED_FIELDS.
COLLECTORS: dict[Callable[[Any], str | None], Collector | None] = {
    script_mod.text: _string,
    script_mod.free_text: _string,
    script_mod.text_list: _strings,
    script_mod.kpi_items: _kpi_text,
    script_mod.jump_rows: _jump_text,
    script_mod.dumbbell_rows: _dumbbell_text,
    script_mod.series_pair: _strings,
    script_mod.positive_number: None,  # `scale`
    script_mod.custom_js: None,  # executed; see MANUAL_TYPES
    script_mod.attestation: None,  # addressed to the approver, not to the frame
}

# Sub-fields of the structured collectors above. They are not in BEAT_TYPES —
# their shape lives inside `jump_rows`, `kpi_items` and `dumbbell_rows` — so
# they are named here for the enumeration the tests hold against planbuild.js.
NESTED_FIELDS = frozenset(
    {"label", "before", "after", "shown", "value", "prefix", "unit", "note"}
)

# Fields that reach the frame, or the plan, and are deliberately NOT claims.
# Each carries the reason, because a documented exception is not a reviewed one
# (D-093) and the reason is what the next reader gets to argue with.
IGNORED_FIELDS: dict[str, str] = {
    "type": "the beat's type, not anything it says about the world",
    "hold": "seconds on screen; timing is not an assertion",
    "act": "the act chip — series chrome joined from series.toml, and an act id "
    "like `01` would otherwise be a claim on the number 1",
    "act_label": "the same chip after plan.py resolves it against "
    "[[structure.acts]]; it names a section of the episode, not a fact",
    "src": "the source tag in the corner — an identifier OF a source, and the "
    "thing a claim is checked against rather than a claim itself",
    "quote": "the source's own words; folding or checking them against "
    "themselves would be circular",
    "claim_override": "the operator's written bypass, addressed to a human "
    "reading a diff (spec §8.4)",
    "attest": "the human substitute for a check a machine cannot make (D-088); "
    "read in review, never drawn on the frame",
    "js": "arbitrary code — what it draws cannot be statically extracted, which "
    "is exactly why `custom` lands as `manual`",
    "scale": "the chart's axis maximum; engine.js positions every dot at "
    "`value / scale` and prints it nowhere",
    "decimals": "display precision; the formatted value it produces is "
    "extracted instead",
    "values": "dumbbell positions — fractions of the track in [0, 1], chosen by "
    "the operator, not figures a source published. The type renders no numbers "
    "(spec §7.2), so demanding `0.62` appear in the quote would refuse every "
    "dumbbell ever written",
    "rows": "the container; its labels, notes and values are walked individually",
    "items": "the container; its rows and labels are walked individually",
}


def _claimed_fields() -> frozenset[str]:
    """Every field name whose content becomes atoms — derived, never listed."""
    names = set(NESTED_FIELDS) | {"kicker"}
    for spec in script_mod.BEAT_TYPES.values():
        for name, check in {**spec["required"], **spec["optional"]}.items():
            if COLLECTORS.get(check) is not None:
                names.add(name)
    return frozenset(names)


CLAIMED_FIELDS = _claimed_fields()


# --- the three buckets every catalogue type falls into ------------------------------------

# §8.2: `title` and `signoff` assert nothing about the world — a title card
# carries the series name and the episode date, and filing those as claims would
# refuse every episode on its first beat.
EXEMPT_TYPES = frozenset({"title", "signoff"})

# `custom` renders whatever its `js` draws. Nothing can extract that statically;
# `attest` is the human substitute (D-088).
MANUAL_TYPES = frozenset({"custom"})

EXTRACTED_TYPES = frozenset(
    {"statement", "body", "list", "kpis", "jumpChart", "dumbbell", "quote"}
)


def beat_text(beat: Beat) -> str:
    """The text this beat puts on the screen, per the catalogue.

    Field order follows the card: the kicker is the small label above
    everything, then the optional lead, then the type's own payload. Joined with
    newlines rather than spaces so that two fields never merge into one token
    and an entity run never crosses a field boundary.
    """
    spec = script_mod.BEAT_TYPES.get(beat.type)
    if spec is None:
        raise ClaimsError(f"beat {beat.index}: unknown type {beat.type!r}")

    parts: list[str] = list(_string(beat.kicker))
    for name, check in {**spec["optional"], **spec["required"]}.items():
        if name not in beat.fields:
            continue
        if check not in COLLECTORS:
            raise ClaimsError(
                f"beat {beat.index} ({beat.type}): `{name}` is checked by "
                f"{check.__name__}(), which claims.py has no collector for. A "
                "field nobody classified is a field nobody verifies — register "
                "a collector in COLLECTORS, or a reason in IGNORED_FIELDS and "
                "None here"
            )
        collect = COLLECTORS[check]
        if collect is None:
            continue
        parts.extend(collect(beat.fields[name]))
    return "\n".join(parts)


@dataclass(frozen=True)
class Claim:
    """One beat's assertions — spec §8.1's record, minus what Task 2 adds.

    `text`, `src` and `quote` are the beat's OWN BYTES, unfolded. Folding is a
    comparison-time transform (§8.2.1): the record is what an operator reads and
    what `quote_span` will index into, and normalising it here would move the
    goalposts for both.
    """

    id: str
    beat_index: int
    beat_type: str
    text: str
    src: str
    quote: str
    atoms: tuple[Atom, ...]
    manual: bool = False
    attest: str = ""
    override: Any = None


def extract_claims(script: Script) -> tuple[Claim, ...]:
    """One record per beat that can assert something. Spec §8.1.

    Every non-exempt beat produces a record, including one with no `src` and one
    with no atoms at all. A missing source is Task 2's `no_source` verdict, which
    the gate refuses on; dropping the record here would turn that refusal into a
    silent pass, which is the single outcome this phase exists to prevent.

    The id is derived from the beat index rather than from the record's position
    in this tuple, so `c-008` is always beat 8 — the row the operator is looking
    at in `agsoc video review`, exempt beats included.
    """
    out: list[Claim] = []
    for beat in script.beats:
        if beat.type in EXEMPT_TYPES:
            continue
        manual = beat.type in MANUAL_TYPES
        if not manual and beat.type not in EXTRACTED_TYPES:
            raise ClaimsError(
                f"beat {beat.index}: type {beat.type!r} is in the catalogue but "
                "claims.py does not classify it — it is neither extracted, "
                "exempt (§8.2) nor manual. A type nobody classified renders "
                "figures nobody checks"
            )
        text = "" if manual else beat_text(beat)
        out.append(
            Claim(
                id=f"c-{beat.index + 1:03d}",
                beat_index=beat.index,
                beat_type=beat.type,
                text=text,
                src=beat.src,
                quote=beat.quote,
                atoms=() if manual else atoms(text),
                manual=manual,
                attest=beat.fields.get("attest", "") if manual else "",
                override=beat.fields.get("claim_override"),
            )
        )
    return tuple(out)

"""The review console — spec §12, screens C and D, as one offline HTML file.

**What this is for.** §12: the UI exists for the one step where a graphical
surface genuinely beats a terminal — *adjudicating claims against source text*.
§12.3 names the element the screen is built around:

    "the source excerpt with the supporting quote highlighted in place. That
     highlight is the single most important element in the product."

Everything the project built since Phase 2 exists to make that highlight
trustworthy: the corpus keeps its bytes (§4), §8.2.1's fold applies to the
*comparison* only, and `verify.quote_span` reports the offset in the **original**
text. So the highlight here is a slice of the file — `document[a:b]` — and never
a re-search of anything. A span computed on the folded text is off by the fold's
own length changes in both directions, and it would look exactly as convincing.

**What it deliberately is not.**

  * It **cannot approve**, and it has no action of any kind: no form, no button,
    no script. The gate is `agsoc video approve`, it takes identifiers and loads
    from disk (D-072), and it is shaped that way because in v1 **a draft was
    published** through a second path around a gate (D-059). A second way to
    approve is precisely the defect Phase 7 spent three tasks eliminating, so
    this page *prints the command* and stops.
  * It **writes nothing** into the episode, and `cli.py` refuses any output path
    inside `workspace/`. Reading a ledger is safe; writing one makes a second
    writer, and this project has a decision about second writers (D-059, D-113).
  * It **reaches nothing off the machine**: no CDN, no webfont, no remote
    favicon, no image URL. `scene.html` already proves a page in this project
    can carry a strict CSP and make zero external requests (D-089), and the
    operator is offline on their own laptop looking at a `file://` URL.

**And every verdict word on it comes from `verify`.** A console is nothing but
summary lines, and six times now this project has shipped a summary line that
said something stronger than the data under it (D-106, D-110, D-112, D-118,
D-121, D-123) — always because a second checker was added and the screens
summarising the first were not moved. So `classify` and `binding_verdict` are
re-exported here as the SAME objects, the remedy sentences come from `cli`'s
`_next_step`, and nothing in this module compares a verdict word to a literal.
"""
from __future__ import annotations

import base64
from datetime import datetime
from html import escape as _escape
from pathlib import Path

from ..models import Status
from . import approve as approve_mod
from . import corpus as corpus_mod
from . import coverage as coverage_mod
from . import verify as verify_mod
from .models import Episode, Series
from .plan import check_runtime
from .script import load_script

# The single source of every verdict word on the page — the SAME objects the
# gate and the terminal screens use, never wrappers, for the reason `cli.py`
# gives at the same import: a wrapper is where the two would drift apart.
classify = verify_mod.classify
binding_verdict = verify_mod.binding_verdict
adversarial_state = verify_mod.adversarial_state
judgement = verify_mod.judgement
override_state = verify_mod.override_state
stale_override = verify_mod.stale_override
claim_tally = verify_mod.claim_tally
pass2_tally = verify_mod.pass2_tally

# How much source sits either side of the highlight. R2's negative half: a quote
# highlighted with nothing around it is §8.3's "verbatim but torn from context"
# failure rendered as a feature, and an operator cannot tell the two apart from
# the highlight alone. Roughly two sentences each way — enough to see who the
# sentence is about, short enough that the mark is still findable at a glance.
CONTEXT = 320

# A probe frame larger than this is described rather than embedded. R1 says one
# self-contained file; a 40 MB page is a file nobody opens, which is a different
# way to lose the same screen.
MAX_FRAME_BYTES = 4_000_000


class ConsoleError(Exception):
    pass


def esc(value: object) -> str:
    return _escape(str(value), quote=True)


def _slug(value: str) -> str:
    """A class-name-safe form of a word this module did not choose.

    Verdict words come from `verify`, so they are not this module's to enumerate
    — a state that does not exist yet must still produce valid markup rather
    than a broken attribute.
    """
    out = "".join(c if c.isalnum() else "-" for c in str(value).lower())
    return out.strip("-") or "unknown"


# --- the highlight, §12.3 -----------------------------------------------------------


def excerpt_html(document: str, span, *, element_id: str, found: bool) -> str:
    """The source, with `span` marked **in the document's own coordinates**.

    `span` is `quote_span`'s answer (the supporting quote) or `closest_span`'s
    (the near miss, §8.2). The two are labelled differently and never styled the
    same: presenting the closest candidate as the supporting quote would be the
    most convincing lie this page could tell.

    The text is sliced, not searched. `document[a:b]` is what the file says;
    anything computed here would be a second implementation of the one thing
    Phase 5 was written to make unnecessary.
    """
    if not isinstance(span, (list, tuple)) or len(span) != 2:
        return (
            f'<p class="source missing" id="{esc(element_id)}">'
            "no span was recorded for this claim — nothing can be highlighted"
            "</p>"
        )
    at, to = span
    at = max(0, min(int(at), len(document)))
    to = max(at, min(int(to), len(document)))
    lo, hi = max(0, at - CONTEXT), min(len(document), to + CONTEXT)
    lead = "…" if lo > 0 else ""
    trail = "…" if hi < len(document) else ""
    label = (
        '<span class="tag tag-quote">supporting quote, verbatim in the source</span>'
        if found
        else '<span class="tag tag-near">quote NOT FOUND — this is the closest '
        "candidate in the source, not the quote</span>"
    )
    mark_class = "hit" if found else "near"
    return (
        f'<p class="source" id="{esc(element_id)}">{label}'
        f"{esc(lead)}{esc(document[lo:at])}"
        f'<mark class="{mark_class}">{esc(document[at:to])}</mark>'
        f"{esc(document[to:hi])}{esc(trail)}</p>"
    )


def _source_for(record: dict, documents: dict) -> str:
    """The excerpt block for one claim, whichever span it has."""
    element_id = f"excerpt-{_slug(record.get('id'))}"
    src = record.get("src")
    document = documents.get(src) if isinstance(src, str) else None
    if document is None:
        why = (
            "this claim cites no source"
            if not src
            else f"the corpus has no readable document for {esc(src)}"
        )
        return f'<p class="source missing" id="{element_id}">{why}</p>'
    mechanical = record.get("mechanical") or {}
    span = record.get("quote_span")
    if isinstance(span, (list, tuple)) and len(span) == 2:
        return excerpt_html(document, span, element_id=element_id, found=True)
    return excerpt_html(
        document, mechanical.get("closest_span"), element_id=element_id, found=False
    )


# --- one claim ----------------------------------------------------------------------


def _row(label: str, value: str, *, cls: str = "") -> str:
    return (
        f'<p class="row {cls}"><span class="k">{esc(label)}</span>'
        f'<span class="v">{value}</span></p>'
    )


def _pass1_row(record: dict) -> str:
    """Pass 1's word, always labelled as pass 1's (D-123).

    Kept rather than replaced: an operator should be able to see that the
    mechanical check passed *and* that a judgement overrode it. Reported, which
    is what `binding_verdict` exists to distinguish from claimed.
    """
    mechanical = record.get("mechanical") or {}
    word = esc(mechanical.get("verdict") or "?")
    reason = mechanical.get("reason")
    tail = f" — {esc(reason)}" if reason else ""
    return _row("pass 1", f'<span class="measured">{word}</span>{tail}')


def _pass2_block(record: dict) -> str:
    """What pass 2 said, if anything — and what kind of thing it is (D-121).

    Pass 1 re-runs to the same answer in a year; pass 2 is an agent's opinion. A
    reader who cannot tell them apart trusts them equally, so this block is
    styled apart from every mechanical line on the page and says so in words.

    `residual_risk` prints on `supported` too. §8.3 calls it often the most
    useful output of the whole pass, and Phase 9 found one on a *supported*
    claim that silently ages into falsity — a risk shown only on failures is a
    risk nobody reads on the episode they are about to approve.
    """
    judged = judgement(record)
    state, why = adversarial_state(record)
    if judged is None:
        # `unjudged` is reported, not gated (D-121). Silent here and counted in
        # the header instead: a line on every claim of every episode is one
        # nobody reads on the claim that matters. `malformed` is not silent.
        if not why:
            return ""
        return (
            '<div class="judged malformed"><p class="judged-head">pass 2 · a '
            "judgement by an agent, NOT a measurement</p>"
            + _row(_slug(state), esc(why))
            + "</div>"
        )
    parts = [
        '<div class="judged">',
        '<p class="judged-head">pass 2 · <span class="j-state">'
        f'{esc(judged["state"])}</span> · a judgement by an agent, NOT a '
        "measurement: not reproducible, and it expires</p>",
        _row(
            "judged by",
            f'{esc(judged["judged_by"])} on {esc(judged["judged_at"])}, stops '
            f'standing {esc(judged["expires_on"])}',
        ),
        _row("attacked", esc(judged["attempted_refutation"])),
    ]
    if judged["residual_risk"]:
        parts.append(
            _row("residual risk", esc(judged["residual_risk"]), cls="risk")
        )
    # Only when it says something the rows above do not. For a plain pass-2
    # refusal `why` IS the verdict and the refutation, both already printed —
    # and a sentence that repeats the two lines above it reads as a stutter on
    # the one screen an operator is meant to read word by word (the same
    # argument `adversarial_state` makes about its own prefix). It earns its
    # place when the STATE differs from the verdict: stale and expired are the
    # cases where a judgement stopped counting and nothing else says why.
    if why and judged["state"] != judged["verdict"]:
        parts.append(_row("why it no longer counts", esc(why)))
    parts.append("</div>")
    return "".join(parts)


def _attest_block(record: dict, state: str) -> str:
    """A `manual` claim's sentence — the thing the approval actually rests on.

    D-088: no mechanical check can say what a `custom` beat draws, so `attest`
    is a claim a person made rather than a check nobody ran. D-121 and D-112:
    an attested claim is **attested, NOT verified**, and the screen that hides
    the difference is the screen that produced three of this project's six
    overclaims.
    """
    attest = str((record.get("mechanical") or {}).get("attest") or "").strip()
    if state != "attested":
        return ""
    return (
        '<div class="attest"><p class="attest-head">attested by hand — no '
        "machine checked this (D-088), NOT verified. You are approving the "
        f'sentence:</p><blockquote>{esc(attest)}</blockquote></div>'
    )


def _override_block(record: dict) -> str:
    """§8.4's written sentence, in the three states it can be in."""
    written, fault = override_state(record)
    if fault:
        return (
            '<div class="override broken">'
            + _row("override", f"clears nothing — it {esc(fault)}")
            + "</div>"
        )
    if written is None:
        return ""
    stale = stale_override(record) is not None
    head = (
        "STALE override — this claim clears without it. Delete it: a sentence "
        "that bypasses nothing is how the next real one stops being read"
        if stale
        else "cleared by override — §8.4, NOT verified by anything. You are "
        "approving the sentence and the name on it"
    )
    return (
        f'<div class="override{" stale" if stale else ""}">'
        f'<p class="override-head">{head}</p>'
        f'<blockquote>{esc(written.get("reason"))}'
        f'<footer>— {esc(written.get("by"))}</footer></blockquote></div>'
    )


def _claim_head(record: dict) -> str:
    """The claim's two words, both of them from `verify` (R3).

    `binding_verdict` is what the pipeline says about the claim; `classify` is
    whether §8.4 lets you approve it. Neither is re-derived, mapped or softened
    here — the count, the cell and the gate are one function or they are three
    facts (D-123).
    """
    verdict = binding_verdict(record)
    state = classify(record)
    index = record.get("beat_index")
    return (
        '<header class="claim-head">'
        f'<a class="cid" href="#beat-{esc(index)}">{esc(record.get("id"))}</a>'
        f'<span class="btype">{esc(record.get("beat_type"))} · beat {esc(index)}</span>'
        f'<span class="verdict verdict-{_slug(verdict)}">{esc(verdict)}</span>'
        f'<span class="state state-{_slug(state)}">{esc(state)}</span>'
        "</header>"
    )


def claim_card(record: dict, documents: dict) -> str:
    """Screen C's claims panel, for one claim (§12.2 C, region 3)."""
    state = classify(record)
    return "".join(
        [
            f'<article class="claim claim-{_slug(state)}" '
            f'id="claim-{_slug(record.get("id"))}">',
            _claim_head(record),
            f'<p class="assert">{esc(record.get("text"))}</p>',
            _row(
                "cited",
                f'{esc(record.get("src") or "nothing")} · '
                f'“{esc(record.get("quote") or "")}”',
            ),
            _source_for(record, documents),
            _pass1_row(record),
            _pass2_block(record),
            _attest_block(record, state),
            _override_block(record),
            "</article>",
        ]
    )


# --- screen D, the adjudication view -------------------------------------------------


def _needs_adjudication(record: dict) -> bool:
    """Which claims screen D opens one at a time.

    Everything the gate refuses, plus everything it lets through on a *person's*
    word rather than on a measurement: an attested `manual`, a written override,
    and any pass-2 judgement. Those are exactly the claims where an operator is
    attaching their name to something no machine checked.
    """
    written, fault = override_state(record)
    return (
        verify_mod.is_blocking(record)
        or written is not None
        or fault is not None
        or classify(record) == "attested"
        or judgement(record) is not None
    )


def _override_diff(episode: Episode, record: dict) -> str:
    """The YAML the operator will type, shown as the diff it makes.

    §12: "it requires a typed reason and is presented as authoring an
    on-the-record statement, not clicking 'accept'. Show it will land in the
    file as a diff. This is a case where the UI should feel slightly heavier
    than necessary."

    §8.4's asymmetry is the whole design — passing verification is automatic,
    bypassing it costs you a written sentence with your name on it — so this
    page cannot make overriding a click. It cannot write the file at all. What
    it can do is show exactly what the sentence will look like in the file, and
    who it will be attributed to.
    """
    index = record.get("beat_index")
    return (
        '<div class="diff-wrap"><p class="diff-head">To override this claim you '
        "write the sentence yourself, into script.yaml, with your name on it. "
        "It is an on-the-record statement: §8.4 clears the claim on the "
        "strength of it and nothing else checks it. This is the diff it "
        "makes:</p>"
        f'<pre class="diff"><code>  # script.yaml · beat {esc(index)} '
        f'({esc(record.get("beat_type"))})\n'
        "    type: " + esc(record.get("beat_type")) + "\n"
        "<ins>+   claim_override:\n</ins>"
        "<ins>+     reason: &quot;why this claim stands anyway, in your own "
        "words&quot;\n</ins>"
        "<ins>+     by: &quot;your name&quot;\n</ins>"
        "</code></pre>"
        '<p class="diff-note">An overridden claim is <strong>NOT verified</strong>'
        " — it is cleared by §8.4 on your sentence. Re-run "
        f"<code>agsoc video check {esc(episode.id)} --series "
        f"{esc(episode.series_slug)}</code> afterwards; the ledger records the "
        "sentence, and every screen after this one prints it beside your "
        "name.</p></div>"
    )


def adjudication_card(episode: Episode, record: dict, documents: dict) -> str:
    """§12's screen D: one claim, what was asserted, what the source says, why."""
    from .cli import _next_step  # see the module docstring: the console is built
    # on the CLI's screens, not the reverse — one remedy sentence, one place, so
    # this page and `check` cannot send an operator two different ways.

    return "".join(
        [
            f'<article class="adjudicate" id="adjudicate-{_slug(record.get("id"))}">',
            _claim_head(record),
            _row("asserted", esc(record.get("text"))),
            _row(
                "checked against",
                f'{esc(record.get("src") or "nothing")} · '
                f'<code>sources/{esc(record.get("src"))}.txt</code>',
            ),
            _row("quoted", f'“{esc(record.get("quote") or "")}”'),
            _source_for(record, documents),
            _pass1_row(record),
            _pass2_block(record),
            _attest_block(record, classify(record)),
            _override_block(record),
            # Only for a claim the gate REFUSES. `_next_step` answers "what do
            # you do about this claim", and `check` calls it on blocking records
            # alone; on an attested `custom` beat it says "write `attest:` on
            # the beat" — on the screen already showing the attestation that is
            # there. Found by opening the page. A remedy printed over a problem
            # that does not exist is how the remedies stop being read, which is
            # §8.4's own argument about written sentences.
            _row("why it is here", esc(_next_step(record)), cls="fix")
            if verify_mod.is_blocking(record)
            else "",
            _override_diff(episode, record),
            "</article>",
        ]
    )


# --- screen C's left column ----------------------------------------------------------


def _beat_items(script, cells: dict) -> str:
    """Ordered beats grouped by act (§12.2 C, region 1).

    The act is the beat's own, in file order — never sorted into the series'
    declared acts, because a beat whose act nobody declared would then vanish
    from the one screen that is supposed to show the whole episode.
    """
    from .cli import beat_summary  # the same one-line summary `review` prints

    out: list[str] = []
    act = object()
    for beat in script.beats:
        if beat.act != act:
            if out:
                out.append("</ol></section>")
            act = beat.act
            out.append(
                f'<section class="act" id="act-{_slug(act) or "unassigned"}">'
                f'<h3>{esc(act or "(no act)")}</h3><ol class="beats">'
            )
        cell = cells.get(beat.index)
        out.append(
            f'<li class="beat" id="beat-{beat.index}">'
            f'<span class="bi">{beat.index}</span>'
            f'<span class="btype">{esc(beat.type)}</span>'
            f'<span class="hold">{beat.hold:.1f}s</span>'
            + (cell or "")
            + f'<span class="btext">{esc(beat_summary(beat))}</span>'
            + (
                f'<span class="bsrc">[{esc(beat.src)}]</span>'
                if beat.src
                else ""
            )
            + (
                f'<span class="bquote">“{esc(beat.quote)}”</span>'
                if beat.quote
                else ""
            )
            + "</li>"
        )
    if out:
        out.append("</ol></section>")
    return "".join(out)


# --- the header, and everything that must not be quiet -------------------------------


def _banner(kind: str, text: str) -> str:
    return f'<p class="banner {kind}">{text}</p>'


def _ledger_view(episode: Episode):
    """`(records, banner)` — what this page may show of `claims.json`.

    The same answer `review` reaches, from the same function (`stale_reason`),
    and for the same reason: **a stale ledger is worse than an absent one**,
    because it looks like verification. When it cannot be trusted, no verdict
    and no highlight reaches the page at all — the spans in a stale ledger
    describe words that are no longer in the script, so highlighting them would
    put a mark on the wrong bytes with total confidence.

    An absent ledger is not a warning: "not checked yet" is the normal state of
    a script an agent has just written, and a page that shouts about it is a
    page whose shouting gets tuned out, taking the stale case with it.
    """
    try:
        ledger = verify_mod.read_ledger(episode)
    except verify_mod.VerifyError as e:
        return [], _banner("stale", f"{esc(e)} — no verdicts are shown")
    stale = verify_mod.stale_reason(episode, ledger)
    if ledger is None:
        return [], _banner(
            "quiet",
            f"{esc(stale)} — nothing on this page has been checked against the "
            "corpus yet",
        )
    if stale:
        return [], _banner(
            "stale",
            f"<strong>claims.json is STALE</strong> — {esc(stale)}. No verdict "
            "and no highlight is shown: the spans in this ledger describe words "
            "that are no longer in the script. Re-run <code>agsoc video check "
            f"{esc(episode.id)} --series {esc(episode.series_slug)}</code>",
        )
    return verify_mod.claim_records(ledger), ""


def _drift_banner(episode: Episode) -> str:
    """§10's drift, where an operator can see it before the render refuses."""
    if approve_mod.approval_record(episode) is None:
        return ""
    drift = approve_mod.approval_drift(episode)
    if not drift:
        return ""
    return _banner(
        "stale",
        f"<strong>the approval on this episode no longer describes it</strong> "
        f"— {esc(drift)}",
    )


def _coverage_banner(series: Series, episode: Episode) -> str:
    """Phase 11's gap, on the one screen that reads both files.

    `agsoc coverage check` cannot tell *not covered* from *covered but never
    recorded*, and nothing nags after a render that an episode is missing from
    the ledger. A rendered episode absent from `coverage.json` is exactly that
    case, and it is silent everywhere else — so the series' memory quietly
    loses an episode and the next `check` calls its stories new.
    """
    if episode.status is not Status.RENDERED:
        return ""
    try:
        ledger = coverage_mod.load_ledger(series)
    except coverage_mod.CoverageError as e:
        return _banner("quiet", f"coverage ledger: {esc(e)}")
    if any(entry.get("date") == episode.id for entry in ledger["episodes"]):
        return ""
    return _banner(
        "quiet",
        "this episode is rendered and <strong>not recorded in the series "
        "coverage ledger</strong>. Until it is, <code>agsoc coverage check</code> "
        "will call its stories new — record it with <code>agsoc coverage add "
        f"{esc(episode.id)} --series {esc(series.slug)}</code>",
    )


def _probe_strip(episode: Episode) -> str:
    """The frames on disk, embedded — honest about being frames (D-116).

    §12 asks for the live `scene.html` in an iframe. What exists is
    `agsoc video probe`, and the frames it leaves in `probe/` are what this page
    can carry offline in one file. They are labelled by their own filename and
    by when they were drawn, and **not by beat**: `render.mjs` names them by
    scene, nothing in the file records which beat a frame belongs to, and a
    frame captioned with a beat it was never proved to show is exactly the kind
    of confident wrong label this whole screen exists to prevent.
    """
    frames = sorted(episode.probe_dir.glob("*.png")) if episode.probe_dir.is_dir() else []
    if not frames:
        return (
            '<p class="quiet">No probe frames on disk. Nothing here has looked '
            "at a pixel — the approval covers the beats, the pace and the "
            "design, and never this machine's fonts or Chromium (D-116). Draw "
            f"some with <code>agsoc video probe {esc(episode.id)} --series "
            f"{esc(episode.series_slug)}</code>.</p>"
        )
    script_at = (
        episode.script_path.stat().st_mtime if episode.script_path.is_file() else 0
    )
    cells = []
    for frame in frames:
        stat = frame.stat()
        when = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        old = (
            ' <span class="tag tag-near">older than script.yaml</span>'
            if stat.st_mtime < script_at
            else ""
        )
        if stat.st_size > MAX_FRAME_BYTES:
            body = f'<p class="quiet">{stat.st_size} bytes — too large to embed</p>'
        else:
            data = base64.b64encode(frame.read_bytes()).decode("ascii")
            body = f'<img alt="{esc(frame.name)}" src="data:image/png;base64,{data}">'
        cells.append(
            f'<figure class="frame">{body}<figcaption>{esc(frame.name)} · drawn '
            f"{esc(when)}{old}</figcaption></figure>"
        )
    return (
        '<p class="quiet">Frames from <code>agsoc video probe</code>, in the '
        "order the renderer sampled them — one per scene. Nothing on disk "
        "records which beat a frame belongs to, so none is captioned with "
        'one.</p><div class="frames">' + "".join(cells) + "</div>"
    )


def _counts_line(records: list[dict]) -> str:
    """The counts, over the verdict that BINDS, and the tally the gate uses.

    Both come from `verify` — `cli._counts` is the same line `check` and
    `review` print, and `claim_tally` is the gate's own arithmetic, so a summary
    here cannot round toward reassurance by dropping a claim from the
    denominator (D-112).
    """
    from .cli import _counts, _plural

    if not records:
        return '<p class="tally">no claims — this script asserts nothing about the world</p>'
    tally = claim_tally(records)
    open_count = tally["total"] - tally["verified"] - tally["attested"] - tally["overridden"]
    parts = [f"{tally['verified']} verified"]
    if tally["attested"]:
        parts.append(f"{tally['attested']} attested by hand, NOT verified (D-088)")
    if tally["overridden"]:
        parts.append(f"{tally['overridden']} cleared by override, NOT verified (§8.4)")
    if open_count:
        parts.append(f"<strong>{open_count} open</strong>")
    return (
        f'<p class="tally">{esc(_plural(tally["total"], "claim"))} · '
        f'{esc(_counts(records))}</p>'
        f'<p class="tally">{" · ".join(parts)}</p>'
    )


def _pass2_line(records: list[dict]) -> str:
    from .cli import _plural

    tally = pass2_tally(records)
    return (
        f'<p class="tally pass2">pass 2 · {tally["judged"]} of '
        f'{esc(_plural(tally["total"], "claim"))} judged — a judgement by an '
        "agent, NOT a measurement: not reproducible, and it expires</p>"
    )


def _runtime_line(script, check) -> str:
    from .cli import _pace

    held = sum(b.hold for b in script.beats)
    verdict = "within tolerance" if check.within else "OUT OF TOLERANCE"
    cls = "ok" if check.within else "warn"
    return (
        f'<p class="runtime">holds {held:.1f}s × pace {esc(_pace(script.pace))} = '
        f"runtime {check.total_sec:.1f}s · target {check.target_sec}s ± "
        f'{check.tolerance_sec}s · <span class="{cls}">{verdict} '
        f"({check.delta:+.1f}s)</span></p>"
    )


# --- the page ------------------------------------------------------------------------

STYLE = """
:root {
  color-scheme: light dark;
  --bg: #fbfbfa; --panel: #fff; --ink: #16191d; --dim: #5c646e;
  --line: #d9dde2; --hit: #ffe9a8; --hit-ink: #16191d; --near: #ffd3cf;
  --open: #a4231d; --quiet: #6b727b; --judge: #4a3fb0; --judge-bg: #f2f0ff;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14171a; --panel: #1a1e22; --ink: #e6e9ec; --dim: #9aa3ad;
    --line: #2b3138; --hit: #6b5a12; --hit-ink: #fff6d8; --near: #5c2a26;
    --open: #ff8a80; --quiet: #99a2ab; --judge: #b9b2ff; --judge-bg: #23213a;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 1500px; margin: 0 auto; padding: 20px 24px 80px; }
h1 { font-size: 16px; margin: 0 0 4px; letter-spacing: .01em; }
h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
     color: var(--dim); margin: 32px 0 10px; font-weight: 600; }
h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .09em;
     color: var(--dim); margin: 16px 0 6px; font-weight: 600; }
code, pre { font-family: var(--mono); font-size: 12.5px; }
.head { border-bottom: 1px solid var(--line); padding-bottom: 12px; }
.head .meta { color: var(--dim); font-size: 12.5px; }
.tally, .runtime { margin: 4px 0; font-size: 12.5px; }
.pass2 { color: var(--judge); }
.ok { color: var(--dim); }
.warn { color: var(--open); font-weight: 600; }
.quiet { color: var(--quiet); font-size: 12.5px; }
.banner { padding: 9px 12px; border-radius: 3px; margin: 10px 0; font-size: 13px; }
.banner.stale { background: var(--near); color: var(--ink);
                border-left: 4px solid var(--open); }
.banner.quiet { background: var(--panel); color: var(--dim);
                border-left: 4px solid var(--line); }
.cols { display: grid; grid-template-columns: minmax(320px, 2fr) 3fr; gap: 22px; }
@media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
ol.beats { list-style: none; margin: 0; padding: 0; }
li.beat { display: grid; grid-template-columns: 22px 68px 42px auto;
          gap: 4px 8px; padding: 6px 8px; border-bottom: 1px solid var(--line); }
li.beat:target { background: var(--hit); }
.bi { color: var(--dim); font-family: var(--mono); }
li.beat .verdict { justify-self: start; text-decoration: none; color: inherit; }
.btype { color: var(--dim); font-size: 12px; }
.hold { color: var(--dim); font-family: var(--mono); font-size: 12px; }
.btext { grid-column: 1 / -1; }
.bsrc, .bquote { grid-column: 1 / -1; color: var(--dim); font-size: 12px; }
.claim, .adjudicate {
  background: var(--panel); border: 1px solid var(--line); border-radius: 3px;
  padding: 12px 14px; margin: 0 0 12px;
}
.claim:target, .adjudicate:target { border-color: var(--open); }
.claim-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline;
              margin-bottom: 6px; }
.cid { font-family: var(--mono); color: inherit; text-decoration: none;
       border-bottom: 1px dotted var(--dim); }
.verdict, .state {
  font-family: var(--mono); font-size: 11.5px; padding: 1px 6px;
  border: 1px solid var(--line); border-radius: 2px;
}
.state-open { color: var(--open); border-color: var(--open); font-weight: 700; }
.state-attested, .state-overridden { color: var(--open); border-color: var(--open); }
.assert { margin: 4px 0 8px; font-size: 14.5px; }
.row { margin: 3px 0; display: flex; gap: 10px; font-size: 12.5px; }
.row .k { color: var(--dim); flex: 0 0 92px; font-family: var(--mono); }
.row .v { flex: 1 1 auto; }
.measured { font-family: var(--mono); }
.fix .v { color: var(--open); }
.source {
  white-space: pre-wrap; background: var(--bg); border: 1px solid var(--line);
  border-left: 3px solid var(--line); border-radius: 2px;
  padding: 10px 12px; margin: 8px 0; max-height: 22em; overflow: auto;
  font-size: 13px;
}
.source.missing { color: var(--dim); font-style: italic; }
mark.hit { background: var(--hit); color: var(--hit-ink); padding: 1px 0;
           box-shadow: 0 0 0 2px var(--hit); font-weight: 600; }
mark.near { background: var(--near); color: var(--ink); padding: 1px 0; }
.tag { display: block; font-size: 11px; text-transform: uppercase;
       letter-spacing: .07em; color: var(--dim); margin-bottom: 6px;
       white-space: normal; }
.tag-near { color: var(--open); font-weight: 700; }
.judged { border-left: 3px solid var(--judge); background: var(--judge-bg);
          padding: 8px 10px; margin: 8px 0; border-radius: 2px; }
.judged-head { margin: 0 0 4px; color: var(--judge); font-size: 12px;
               font-weight: 600; }
.j-state { font-family: var(--mono); }
.judged .risk .v { font-weight: 600; }
.attest, .override { border-left: 3px solid var(--open); padding: 8px 10px;
                     margin: 8px 0; }
.attest-head, .override-head { margin: 0 0 4px; font-size: 12px;
                               font-weight: 600; color: var(--open); }
blockquote { margin: 0; padding: 0; font-size: 13.5px; }
blockquote footer { color: var(--dim); font-size: 12px; margin-top: 2px; }
.diff-wrap { border-top: 1px dashed var(--line); margin-top: 12px;
             padding-top: 10px; }
.diff-head, .diff-note { font-size: 12.5px; color: var(--dim); margin: 6px 0; }
pre.diff { background: var(--bg); border: 1px solid var(--line);
           padding: 10px 12px; overflow: auto; }
pre.diff ins { text-decoration: none; background: var(--hit);
               color: var(--hit-ink); display: block; }
.frames { display: flex; gap: 10px; overflow-x: auto; }
figure.frame { margin: 0; flex: 0 0 auto; }
figure.frame img { height: 220px; width: auto; border: 1px solid var(--line); }
figcaption { color: var(--dim); font-size: 11.5px; margin-top: 4px; }
.cmd { background: var(--panel); border: 1px solid var(--line);
       border-radius: 3px; padding: 10px 12px; margin: 10px 0; font-size: 12.5px; }
.cmd code { display: block; margin-top: 4px; }
"""


def build(series: Series, episode: Episode) -> str:
    """Screens C and D of §12, as one self-contained page.

    Loads the script, the ledger and the corpus itself from the episode it was
    handed — the weaker form of D-072 that a read-only screen needs. It is not a
    gate: it decides nothing and writes nothing. But a console rendered from a
    caller-built object would be a picture of something other than the file the
    operator is about to approve, which is the whole failure it exists to catch.
    """
    from .cli import _plural

    script = load_script(episode)
    check = check_runtime(script, series)
    records, banner = _ledger_view(episode)

    documents: dict[str, str] = {}
    for record in records:
        src = record.get("src")
        if isinstance(src, str) and src and src not in documents:
            try:
                documents[src] = corpus_mod.document_text(episode, src)
            except corpus_mod.CorpusError:
                pass

    cells = {}
    for record in records:
        index = record.get("beat_index")
        if isinstance(index, int):
            verdict = binding_verdict(record)
            cells[index] = (
                f'<a class="verdict verdict-{_slug(verdict)}" '
                f'href="#claim-{_slug(record.get("id"))}">{esc(verdict)}</a>'
            )

    open_records = [r for r in records if _needs_adjudication(r)]
    title = f"{series.slug}/{episode.id} · review console"

    body = [
        '<main><header class="head">',
        f"<h1>{esc(title)}</h1>",
        f'<p class="meta">{esc(episode.status.value)} · '
        f'{esc(_plural(len(script.beats), "beat"))} · '
        f"{esc(series.name)} · generated "
        f'{esc(datetime.now().astimezone().isoformat(timespec="seconds"))}</p>',
        _runtime_line(script, check),
        _counts_line(records) if records else "",
        _pass2_line(records) if records else "",
        banner,
        _drift_banner(episode),
        _coverage_banner(series, episode),
        # R4's negative half, at the top of the page: this screen prints the
        # command, and the gate — which takes identifiers and loads from disk
        # (D-072) — is the only thing that can approve anything. There is
        # deliberately nothing here to click (D-059).
        '<div class="cmd">This console reads. It writes nothing and it cannot '
        "approve: the gate is a command you run yourself, and it re-reads every "
        "file before it decides.<code>agsoc video check "
        f"{esc(episode.id)} --series {esc(series.slug)}</code>"
        f"<code>agsoc video approve {esc(episode.id)} --series "
        f'{esc(series.slug)} --by "your name"</code></div>',
        "</header>",
        "<h2>Episode review</h2>",
        '<div class="cols"><div class="col-beats">',
        _beat_items(script, cells),
        "</div><div class=\"col-claims\">",
        "".join(claim_card(r, documents) for r in records)
        or '<p class="quiet">No verdicts are shown for this episode.</p>',
        "</div></div>",
        "<h2>Frames</h2>",
        _probe_strip(episode),
        "<h2>Claim adjudication</h2>",
        "".join(adjudication_card(episode, r, documents) for r in open_records)
        or '<p class="quiet">Nothing to adjudicate: no claim here is open, '
        "attested by hand, judged by pass 2, or cleared by a written "
        "sentence.</p>",
        "</main>",
    ]

    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        # D-089's precedent, and the reason it lives in the PAGE: this file is
        # opened by hand from `file://`, so a policy enforced anywhere else
        # leaves the path an operator actually uses open. There is no
        # `script-src` because there is no script — naming it would only permit
        # some.
        '<meta http-equiv="Content-Security-Policy" content="default-src '
        "'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; "
        "form-action 'none'\">"
        # An inline empty icon, so the browser does not go looking for one.
        '<link rel="icon" href="data:,">'
        f"<title>{esc(title)}</title><style>{STYLE}</style></head><body>"
        + "".join(body)
        + "</body></html>\n"
    )

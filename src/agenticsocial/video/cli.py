"""`agsoc series` and `agsoc video` commands."""
from __future__ import annotations

import re
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

import typer

from ..models import TransitionError
from ..workspace import Workspace, WorkspaceError, atomic_write
from . import approve as approve_mod
from . import claims as claims_mod
from . import corpus as corpus_mod
from . import coverage as coverage_mod
from . import ingest as ingest_mod
from . import plan as plan_mod
from . import render as render_mod
from . import verify as verify_mod
from .episode import create_episode, episode_ids, load_episode
from .models import EpisodeError, SeriesError
from .plan import PlanError, check_runtime
from .script import RENDERABLE, Beat, ScriptError, load_script
from .series import load_series, scaffold_series, series_slugs

series_app = typer.Typer(help="Manage video series.", no_args_is_help=True)
video_app = typer.Typer(help="Create and manage video episodes.", no_args_is_help=True)
coverage_app = typer.Typer(
    help="The per-series coverage ledger: has this story been told before?",
    no_args_is_help=True,
)

DEFAULT_SERIES = "default"


def _fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=False)
    return typer.Exit(code=1)


def _workspace() -> Workspace:
    try:
        return Workspace.locate()
    except WorkspaceError as e:
        raise _fail(str(e))


def _text(value: str, label: str) -> str:
    """Reject operator input that cannot be encoded as UTF-8.

    Python decodes sys.argv with surrogateescape, so a non-UTF-8 byte arrives as
    a lone surrogate. No escaping saves it — UTF-8 cannot encode a non-scalar
    value — so it must be refused at the boundary rather than becoming a
    UnicodeEncodeError traceback from inside atomic_write. See D-025.
    """
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _fail(
            f"{label} contains bytes that are not valid UTF-8 text. "
            "Check your terminal's encoding, or retype the value."
        )
    return value


@series_app.command("new")
def series_new(
    slug: str,
    name: Optional[str] = typer.Option(None, "--name", help="display name (default: slug)"),
) -> None:
    """Scaffold a series: series.toml, coverage.json, episodes/."""
    ws = _workspace()
    slug = _text(slug, "The series slug")
    if name is not None:
        name = _text(name, "The series name")
    try:
        s = scaffold_series(ws, slug, name=name)
    except SeriesError as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot create series {slug!r}: {e}")
    typer.echo(f"created series {s.slug} at {s.dir}/")
    typer.echo(f"next: edit {s.dir / 'series.toml'} (palette, byline, acts, runtime)")


@series_app.command("list")
def series_list() -> None:
    """List series and their key settings. Reports broken ones rather than dying."""
    ws = _workspace()
    try:
        slugs = series_slugs(ws)
    except SeriesError as e:
        raise _fail(str(e))
    if not slugs:
        typer.echo("no series yet — create one with `agsoc series new <slug>`")
        return
    for slug in slugs:
        try:
            s = load_series(ws, slug)
        except SeriesError as e:
            typer.secho(f"{slug}  [unreadable]  {e}", fg=typer.colors.YELLOW)
            continue
        try:
            n: object = len(episode_ids(s))
        except EpisodeError:
            n = "?"
        typer.echo(
            f"{s.slug}  [{s.cadence}]  {n} episodes  {s.target_sec}s  "
            f"{'/'.join(s.formats)}"
        )


def _resolve_series(ws: Workspace, slug: str, autocreate: bool):
    try:
        return load_series(ws, slug)
    except SeriesError:
        if autocreate and slug == DEFAULT_SERIES:
            return scaffold_series(ws, DEFAULT_SERIES, name="Default")
        raise


@video_app.command("new")
def video_new(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Create an episode directory with a stub script.yaml."""
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = _resolve_series(ws, series, autocreate=True)
        ep = create_episode(s, episode)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot create episode {episode!r}: {e}")
    typer.echo(f"created episode {s.slug}/{ep.id} at {ep.dir}/")
    # `--series` is in the hint because the hint is a command people run. It
    # was absent, and following it from any series other than `default` failed
    # with "no series 'default'" — D-109: an author trusts the tool over the doc.
    #
    # Same reason the mode is `--paste`. The hint led with `--research`, which
    # is the one mode the documented workflow does not use (the author has a
    # brief already) and the only one that reaches the network. The other two
    # are named on the second line because `ingest` takes exactly one of the
    # three, and a hint that shows one mode is read as the only mode.
    typer.echo(f"next: agsoc video ingest {ep.id} --series {s.slug} --paste <file>")
    typer.echo(
        '      exactly one ingest mode: --paste <file>, --research "<query>", '
        "or --from-source <id>"
    )


@video_app.command("list")
def video_list(
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """List episodes and their statuses. Reports broken ones rather than dying."""
    ws = _workspace()
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ids = episode_ids(s)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))
    if not ids:
        typer.echo(f"no episodes in {s.slug} — create one with `agsoc video new <id>`")
        return
    for ep_id in ids:
        try:
            typer.echo(f"{ep_id}  {load_episode(s, ep_id).status.value}")
        except EpisodeError as e:
            typer.secho(f"{ep_id}  [unreadable]  {e}", fg=typer.colors.YELLOW)


@video_app.command("ingest")
def video_ingest(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    research: Optional[str] = typer.Option(None, "--research", help="search query"),
    paste: Optional[Path] = typer.Option(
        None, "--paste", help="file whose text becomes the corpus"
    ),
    from_source: Optional[str] = typer.Option(
        None, "--from-source", help="an existing agsoc source id"
    ),
) -> None:
    """Build this episode's verification corpus from research, a paste, or a source."""
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")

    modes = [m for m in (research, paste, from_source) if m is not None]
    if not modes:
        raise _fail(
            "nothing to ingest — pass one of --research \"<query>\", "
            "--paste <file>, or --from-source <id>"
        )
    if len(modes) > 1:
        raise _fail("pass exactly one of --research, --paste or --from-source")

    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))

    try:
        if research is not None:
            result = ingest_mod.ingest_research(ep, _text(research, "The query"))
        elif paste is not None:
            try:
                text = paste.read_text(encoding="utf-8")
            except FileNotFoundError:
                raise _fail(f"cannot read --paste {paste}: no such file")
            except UnicodeDecodeError:
                raise _fail(
                    f"cannot read --paste {paste}: the file is not valid UTF-8. "
                    "Re-save it as UTF-8."
                )
            except OSError as e:
                raise _fail(f"cannot read --paste {paste}: {e}")
            result = ingest_mod.ingest_paste(ep, text)
        else:
            try:
                src = ws.resolve_source(from_source)
            except WorkspaceError as e:
                raise _fail(str(e))
            result = ingest_mod.ingest_source(ep, src)
    except ingest_mod.IngestError as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write the corpus: {e}")

    for url, reason in result.failures:
        typer.secho(f"  failed: {url or '(pasted)'} — {reason}", fg=typer.colors.YELLOW)

    if not result.keys:
        raise _fail(
            f"nothing was ingested ({len(result.failures)} failed) — "
            f"see {result.brief_path}"
        )

    typer.echo(
        f"ingested {len(result.keys)} source(s), {len(result.failures)} failed → "
        f"{result.brief_path}"
    )
    typer.echo(f"next: draft beats into {ep.script_path}")


# --- `agsoc video review` -------------------------------------------------------
#
# The screen an operator reads before approving anything. Its job is to make the
# episode scannable, so the display code is not decoration: a table an operator
# cannot scan is a table they approve without reading, which defeats the gate
# Phase 7 puts behind it.

# The table is budgeted to a fixed total width rather than grown to fit its
# content. The first real twelve-beat run came out 156 columns wide — every row
# wrapped, and a table whose rows wrap is not a table. Columns are capped, the
# text column absorbs whatever budget the others leave, and the whole row is one
# screen line on any terminal an operator is plausibly using.
ROW_WIDTH = 100
ACT_WIDTH = 10
TYPE_WIDTH = 9  # `statement` and `jumpChart`, the longest catalogue names
SRC_WIDTH = 16  # inside the brackets — enough for a bare domain
CLAIM_WIDTH = 11  # `unsupported`, the longest verdict either pass can record
MIN_TEXT_WIDTH = 20
LEAD = 8  # a space, the ! margin, two spaces, a two-digit index, two spaces

# C0 controls and DEL, mapped to spaces. A YAML block scalar is how an operator
# writes a long statement, and a raw newline in the text column destroys the
# alignment that makes the table readable at all.
_CONTROLS = {c: " " for c in list(range(0x20)) + [0x7F]}


def _one_line(value: object) -> str:
    return " ".join(str(value).translate(_CONTROLS).split())


def _clip(value: str, width: int) -> str:
    return value if len(value) <= width else value[: width - 1].rstrip() + "…"


def _join(parts) -> str:
    return " · ".join(p for p in (_one_line(x) for x in parts) if p)


# --- the claim ledger, read by both screens (spec §8.1, §8.4) -------------------
#
# `check` writes `claims.json` and `review` displays it, and both have to agree
# on what "blocking" means or the two screens disagree about the same episode.
# One function answers it, here, over the RECORD — the artifact Phase 7's gate
# will read — rather than over anything either command happens to hold.


# The predicate itself now lives in `verify`, next to the ledger it reads and
# where `approve` can reach it without importing the CLI. It is re-exported here
# — as the SAME object, not a wrapper — because `check`'s screen and `approve`'s
# gate answering the same question from two code paths is D-059's shape, and
# because a wrapper is where the two would drift apart.
is_blocking = verify_mod.is_blocking
classify = verify_mod.classify

# Pass 2's state, for the same reason and on the same terms: the SAME object, so
# the screen and the gate cannot disagree about what a judgement said. This is
# the only way any of this file reads the `adversarial` field — nothing here
# subscripts it, because a second reading of that block is a second place §8.4's
# list is spelled out (D-059).
adversarial_state = verify_mod.adversarial_state

# The one word every screen prints about a claim. SAME object, for the reason
# above and for one more: `_counts`, `_claim_cell` and the summary's head line
# used to answer this question in three places, and two of the three were left
# reading pass 1 when the third was converted — a screen that looks updated and
# is not (D-106, D-110, D-112, D-118, D-122's finding).
binding_verdict = verify_mod.binding_verdict

# The order the counts line prints in: pass 1's four verdicts, then §8.4's two
# pass-2 refusals, then anything a ledger holds that neither pass named — last,
# and never dropped, because a count that omits a claim is the reassurance
# D-112 was about.
COUNT_ORDER = list(verify_mod.VERDICTS) + ["refuted", "unsupported"]


def _verdict(record: dict) -> str:
    return str((record.get("mechanical") or {}).get("verdict") or "?")


def _reason(record: dict) -> str:
    return str((record.get("mechanical") or {}).get("reason") or "")


# §8.4's override, read through `verify` and never from the field. The display
# and the gate disagreeing about whether a sentence counts is the same defect as
# the summary and the gate disagreeing about a verdict (D-059), one door along —
# so this is the SAME object, not a wrapper, exactly like `is_blocking` above.
override_state = verify_mod.override_state
stale_override = verify_mod.stale_override


def _written(record: dict) -> bool:
    """Was an override written here at all — honoured or not? The table's `*`."""
    return override_state(record) != (None, None)


def _sentence(written: dict) -> str:
    """§8.4's override as one line: the sentence, then the name on it."""
    return f"“{written.get('reason')}” — {written.get('by')}"


def _applied(record: dict) -> str:
    """Did this written sentence actually clear its claim? Say so on the line.

    An override printed without this reads the same whether it did the work or
    nothing at all, and the second case is the one an operator has to see.
    """
    if stale_override(record) is None:
        return "(cleared this claim — §8.4, NOT verified)"
    return "(STALE — this claim clears without it)"


def _override_rate(overridden: int, total: int) -> str:
    """D-040's health signal, built once and printed on both screens.

    "A high rate means the checker is wrong, not the operator." Nobody can
    notice a rate that is never printed — and it is omitted entirely at zero,
    because `override rate 0%` on every clean run is the noise this line has to
    cut through the one time it matters.
    """
    percent = round(100 * overridden / total) if total else 0
    return (
        f"rate {overridden} of {_plural(total, 'claim')} ({percent}%) — D-040: a "
        "high rate means the checker is wrong, not the operator"
    )


def _kpi(item: dict) -> str:
    """One KPI, read the way the frame reads it.

    `prefix` leads, `unit` follows — the same order `planbuild.js` composes
    them in. It used to guess from a table of currency symbols, which put `$`
    in front of a value the engine would have rendered it behind: this line is
    what an operator approves, and a review that reads differently from the
    render is a review of something else.
    """
    value = item.get("value", "")
    prefix, unit = item.get("prefix", ""), item.get("unit", "")
    label = item.get("label", "")
    return f"{prefix}{value}{unit} {label}".strip()


def _jump_row(row: dict) -> str:
    """One jumpChart row, with the cell that does not follow from the bar.

    `shown` is an HTML display override, and D-081 records it as the one field
    where the frame and the script legitimately differ: the bar is drawn from
    `before`/`after` and this text is drawn from nothing else. So it is the one
    field an approver cannot reconstruct from the rest of the row, and printing
    only the label is how it stayed invisible to the only control that is a
    person rather than a check — it can carry markup, and until Phase 4 Task 5
    it could carry an inline event handler.

    Shown verbatim, as authored, because that is the string in the file they are
    about to edit.
    """
    label = row.get("label", "")
    shown = row.get("shown")
    return _join([label, shown]) if isinstance(shown, str) else _one_line(label)


# One summariser per catalogue type. A dict rather than a chain of `if`s for the
# same reason BEAT_TYPES is: adding a type in Phase 4 is a row here. There is no
# `.get(type, "")` default anywhere below — a default is how a new type silently
# gets a blank text column and stops being reviewable.
SUMMARISERS = {
    "statement": lambda b: _one_line(b.fields.get("text", "")),
    "body": lambda b: _one_line(b.fields.get("text", "")),
    "list": lambda b: _join([b.fields.get("lead", ""), *b.fields.get("items", [])]),
    "kpis": lambda b: _join(_kpi(i) for i in b.fields.get("items", [])),
    "jumpChart": lambda b: _join(_jump_row(r) for r in b.fields.get("rows", [])),
    "dumbbell": lambda b: _one_line(b.fields.get("caption", "")),
    "quote": lambda b: _one_line(
        f"“{b.fields.get('text', '')}” — {b.fields.get('attribution', '')}"
    ),
    # `title` and `signoff` are the two types whose only fields are optional, so
    # these are the two summarisers that can legitimately come back empty. They
    # do NOT carry their own fallback: one fallback, in beat_summary, is
    # reachable and therefore testable — two would leave the outer one dead.
    "title": lambda b: _one_line(b.fields.get("sub", "")),
    "signoff": lambda b: _one_line(b.fields.get("text", "")),
    # The attestation, not the code. `custom` renders whatever its `js` draws
    # and no check can say what that is, so the only thing worth putting in
    # front of an approver is the sentence in which the author says what it
    # shows and signs for it. A clipped first line of JavaScript in a 40-column
    # column tells them less than nothing; the code is in script.yaml.
    "custom": lambda b: _one_line(b.fields.get("attest", "")),
}


def beat_summary(beat: Beat) -> str:
    """One scannable line of what this beat says. Never empty."""
    summarise = SUMMARISERS.get(beat.type)
    return (summarise(beat) if summarise else "") or f"({beat.type})"


def _pace(value: float) -> str:
    """`pace: 2.0` in the file must not print as `pace 2`.

    Same rule as R1's negative on holds: every number on this screen should be
    findable in the file the operator is about to edit. `:g` drops the decimal
    point and quietly stops matching what they typed.
    """
    rendered = f"{value:g}"
    return rendered if "." in rendered else rendered + ".0"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _review_table(beats, verdicts: dict | None = None) -> list[str]:
    """One screen line per beat, inside ROW_WIDTH columns — plus its citation.

    `src` gets its own right-hand column rather than being appended after the
    text: §7.2 makes the source the thing an approver actually checks, and a
    column you scan down the page is checkable in a way a ragged tail is not.
    It only appears when some beat has one — an empty column on every row of
    a title-and-statement episode is just noise.

    **`quote` gets a second line, under the row it belongs to.** Phase 3 left
    this gap and named it: an operator could see `src` — that a citation exists
    — and never what the source actually says, which is the difference between
    "this beat is cited" and "this beat is true". It cannot go in the table:
    a quote is a sentence, and a sentence in a 30-column cell is a sentence
    nobody reads. It cannot go untruncated either — D-074's finding is that a
    table whose rows wrap is not a table — so it is clipped to the same budget.

    Driven by `b.quote`, never by `b.type`: a display keyed on type shows the
    citation for the types its author was thinking about and hides it for the
    rest, which is the worst of both (M5).
    """
    act_w = min(ACT_WIDTH, max(3, *(len(_one_line(b.act)) for b in beats)))
    type_w = min(TYPE_WIDTH, max(4, *(len(b.type) for b in beats)))
    src_cell = SRC_WIDTH + 2 if any(b.src for b in beats) else 0
    claim_cell = CLAIM_WIDTH + 2 if verdicts is not None else 0
    text_w = max(
        MIN_TEXT_WIDTH,
        ROW_WIDTH
        - LEAD
        - act_w
        - 2
        - type_w
        - 2
        - 5
        - 2
        - claim_cell
        - (src_cell + 2 if src_cell else 0),
    )

    head = f"    {'#':>2}  {'act':<{act_w}}  {'type':<{type_w}}  {'hold':>5}  "
    if claim_cell:
        head += f"{'claim':<{CLAIM_WIDTH}}  "
    head += f"{'text':<{text_w}}"
    lines = [(head + "  src" if src_cell else head).rstrip()]
    for b in beats:
        # `!` marks a beat this phase cannot draw. Not an error — see the
        # command docstring — so it is a margin mark, not a message.
        flag = " " if b.type in RENDERABLE else "!"
        src = f"[{_clip(_one_line(b.src), SRC_WIDTH)}]" if b.src else ""
        claim = (
            f"{_clip(str(verdicts.get(b.index, '')), CLAIM_WIDTH):<{CLAIM_WIDTH}}  "
            if claim_cell
            else ""
        )
        row = (
            f" {flag}  {b.index:>2}  {_clip(_one_line(b.act), act_w):<{act_w}}  "
            f"{_clip(b.type, type_w):<{type_w}}  {b.hold:>5.1f}  {claim}"
            f"{_clip(beat_summary(b), text_w):<{text_w}}"
        )
        lines.append((f"{row}  {src}" if src_cell else row).rstrip())
        if b.quote:
            lines.append(f"      “{_clip(_one_line(b.quote), ROW_WIDTH - 8)}”")
    return lines


def _ledger_state(episode):
    """`(ledger, note, warn, verdicts)` — what `review` may show of `claims.json`.

    `verdicts` is None whenever the ledger cannot be trusted, and then NO
    verdict reaches the screen. **A stale ledger is worse than an absent one**,
    because it looks like verification: the operator reads `pass` on a row and
    approves a claim that was checked against bytes that no longer exist.

    An absent ledger is not a warning. "Not checked yet" is the normal state of
    a script an agent has just written, and a screen that shouts about it is a
    screen whose shouting gets tuned out — taking the stale case with it.
    """
    try:
        ledger = verify_mod.read_ledger(episode)
    except verify_mod.VerifyError as e:
        return None, f"{e} — verdicts are not shown", True, None
    # Both halves — corpus and script — come from `stale_reason`. They used to
    # be two answers, one of them a display helper living here, and Phase 7's
    # gate would have called the shared one and got the incomplete answer (F3).
    stale = verify_mod.stale_reason(episode, ledger)
    if ledger is None:
        return None, str(stale), False, None
    if stale:
        return (
            ledger,
            f"{verify_mod.CLAIMS_NAME} is STALE — {stale}. Verdicts are not "
            "shown; re-run `agsoc video check`",
            True,
            None,
        )
    verdicts = {}
    for record in ledger.get("claims") or []:
        if isinstance(record, dict) and isinstance(record.get("beat_index"), int):
            verdicts[record["beat_index"]] = _claim_cell(record)
    return ledger, None, False, verdicts


def _claim_cell(record: dict) -> str:
    """The table's one-word answer about a claim, and it must be the BINDING one.

    Where pass 2 refuses, the pass-1 verdict is `pass` — that is what pass 2 is
    for — so a cell showing the measurement would print a green word on the row
    the gate refuses. The measurement is not lost: it is on the claim's line in
    the summary below, and in `check`'s row, which prints both.
    """
    return binding_verdict(record) + ("*" if _written(record) else "")


def _print_claim_summary(ledger: dict) -> None:
    """The count, then every claim that is not settled, with its reason.

    The table says WHICH beat; this says WHY, and the two are on one screen
    because an operator working from a verdict alone is an operator overriding
    from a verdict alone.
    """
    records = [r for r in (ledger.get("claims") or []) if isinstance(r, dict)]
    if not records:
        return
    checked = _one_line(ledger.get("checked_at", "?"))
    typer.echo(f"claims  {_counts(records)}   (checked {checked})")
    for record in records:
        written, fault = override_state(record)
        if not is_blocking(record) and not written and not fault:
            continue
        # The BINDING verdict, then pass 1's, labelled as pass 1's. A line whose
        # entire job is *this claim is open* ended with the word `pass`, because
        # it was built from the measurement — and the measurement is still worth
        # printing, as long as it is reported rather than claimed.
        binding = binding_verdict(record)
        measured = _verdict(record)
        head = (
            f"{'!' if is_blocking(record) else '*'} {record.get('id')} · "
            f"beat {record.get('beat_index')} · {binding}"
            + ("" if binding == measured else f" · pass 1 {measured}")
        )
        # No "— no reason recorded" filler: a passing claim that carries an
        # override has nothing to explain, and inventing a clause there reads
        # like the check lost something.
        why = f" — {_reason(record)}" if _reason(record) else ""
        typer.secho(
            "  " + _clip(_one_line(head + why), ROW_WIDTH - 2),
            fg=typer.colors.RED if is_blocking(record) else None,
        )
        if written:
            typer.echo(_detail("override", f"{_sentence(written)} {_applied(record)}"))
        elif fault:
            typer.echo(_detail("override", f"clears nothing — it {fault}"))
    typer.echo("")


def _echo_drift(ep) -> None:
    """Say when an approval no longer describes the script on disk (§10).

    `render` is Phase 8 and it is the command that will REFUSE; this prints the
    same answer, from the same function, where an operator can already see it.
    Without it an approval that stopped being true is visible to nothing until
    the render — the expensive, hard-to-retract step §10 wrote the rule to
    protect.

    Silent unless there is an approval to contradict: "not approved yet" is the
    normal state of a fresh script, and a banner on every draft is a banner
    nobody reads by the time one of them is true. One function, two call sites,
    for the reason `_echo_runtime` gives.
    """
    if approve_mod.approval_record(ep) is None:
        return
    drift = approve_mod.approval_drift(ep)
    if not drift:
        return
    typer.secho(
        textwrap.fill(
            f"the approval on this episode no longer describes it — {drift}",
            width=ROW_WIDTH,
        ),
        fg=typer.colors.RED,
    )


def _echo_runtime(script, check) -> None:
    """The two runtime lines, printed identically by `review` and by `check`.

    A REPORT in both places, never a refusal: spec §11 puts the gate at
    `approve`, and `check`'s exit code speaks for the claim ledger alone. It is
    in `check` because an agent that runs `check`, sees exit 0 and stops has
    been told nothing about length — and the one committed script.yaml is 82
    seconds short with a clean check (D-109 #3, #4).

    One function rather than two call sites: two commands printing one fact from
    two code paths are two facts as soon as one of them changes.
    """
    held = sum(b.hold for b in script.beats)
    typer.echo(
        f"holds {held:.1f}s × pace {_pace(script.pace)} = "
        f"runtime {check.total_sec:.1f}s"
    )
    verdict = "within tolerance" if check.within else "OUT OF TOLERANCE"
    typer.secho(
        f"target {check.target_sec}s ± {check.tolerance_sec}s · "
        f"{verdict} ({check.delta:+.1f}s)",
        fg=typer.colors.GREEN if check.within else typer.colors.YELLOW,
    )


@video_app.command("review")
def video_review(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Report what you are about to approve: beats, holds, runtime, verdict.

    A REPORT, not a gate. It exits 0 whether the runtime is in tolerance or
    out, and whether or not the script contains beats this phase cannot draw.
    Spec §11 puts the gate at `approve`; a diagnostic command that refuses to
    speak when something is wrong is the D-018 mistake in a new place — it
    takes away the one screen that would have explained the problem.

    Writes nothing: not script.yaml, not plan.json, not a derived pace. The
    script's BYTES are what `script_sha256` binds (D-026), so a command that
    ran before approval and touched them would have changed what the operator
    was approving by looking at it.

    Everything it reports is loaded fresh from disk on every invocation — see
    `plan.check_runtime` on D-063.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        script = load_script(ep)
    except (SeriesError, EpisodeError, ScriptError) as e:
        # NOT the out-of-tolerance path. An unreadable script is a report that
        # cannot be produced; printing a runtime for a file nobody parsed would
        # be worse than failing.
        raise _fail(str(e))

    check = check_runtime(script, s)
    beats = script.beats
    ledger, ledger_note, warn, verdicts = _ledger_state(ep)

    typer.echo(
        f"{s.slug}/{ep.id} · {ep.status.value} · {_plural(len(beats), 'beat')} · "
        f"pace {_pace(script.pace)}"
    )
    if ledger_note:
        typer.secho(
            textwrap.fill(_one_line(ledger_note), width=ROW_WIDTH),
            fg=typer.colors.YELLOW if warn else None,
        )
    _echo_drift(ep)
    typer.echo("")
    for line in _review_table(beats, verdicts):
        typer.echo(line)
    typer.echo("")
    if verdicts is not None:
        _print_claim_summary(ledger)
        _print_pass2(verify_mod.claim_records(ledger))

    _echo_runtime(script, check)

    # Valid beats this phase cannot draw yet. Named, counted, and NOT treated as
    # an operator error: the fix is to implement the renderer, not to edit the
    # script. Silent when there are none — a warning that fires on every healthy
    # episode is one operators learn to scroll past.
    pending: dict[str, int] = {}
    for b in beats:
        if b.type not in RENDERABLE:
            pending[b.type] = pending.get(b.type, 0) + 1
    if pending:
        listed = ", ".join(
            f"{k} ({n})" for k, n in sorted(pending.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        # Wrapped to the same budget as the table. Nine catalogue types and
        # their counts is 156 columns on one line, which is the table problem
        # again in the one place a reader is most likely to skip.
        typer.echo(
            textwrap.fill(
                f"{_plural(sum(pending.values()), 'beat')} cannot be rendered yet "
                f"— marked ! above: {listed}",
                width=ROW_WIDTH,
                subsequent_indent="    ",
            )
        )


# --- `agsoc video check` --------------------------------------------------------
#
# Task 2's pass 1 refused two fabricated figures on its first contact with real
# content. That refusal is worth nothing until a human sees it in a form they
# can act on: a verdict of `fail` with a claim id is a true statement and a
# useless one. What an operator needs, in one place, is the figure, the quote it
# was checked against, and the source it came from.

LABEL_WIDTH = 9  # "override" plus the space that keeps it off the value
EXCERPT = 2 * ROW_WIDTH  # the near-miss window, before clipping


def _detail(label: str, value: str, *, indent: int = 6) -> str:
    """One labelled line of a detail block, wrapped inside ROW_WIDTH.

    Wrapped rather than clipped: this is the part of the screen an operator
    reads word by word, and a truncated reason is a reason they have to open the
    file to finish. The TABLE is clipped because it is scanned; this is not.
    """
    pad = " " * indent
    return textwrap.fill(
        f"{label:<{LABEL_WIDTH}}{_one_line(value)}",
        width=ROW_WIDTH,
        initial_indent=pad,
        subsequent_indent=pad + " " * LABEL_WIDTH,
    )


def _next_step(record: dict) -> str:
    """What to do about this claim. The screen is worthless if it does not say.

    One sentence per verdict, naming the two honest routes — change the beat or
    widen the citation — and the third one §8.4 allows, which costs a written
    sentence with your name on it.
    """
    # Pass 2 first, and with different words, because the two refusals ask for
    # different acts. A pass-1 `fail` says the figure is not in the quote —
    # correct it or widen the citation. A `refuted` claim's figure IS in the
    # quote: nothing about the citation is wrong and widening it changes
    # nothing, so printing pass 1's remedy over a pass-2 refusal sends an
    # operator to edit the one part of the beat that was right.
    state, _ = adversarial_state(record)
    if state in ("refuted", "unsupported"):
        return (
            f"pass 2 found this claim {state} and the citation is not the "
            "problem: rewrite the beat to what the source actually supports, "
            "drop it, or write a `claim_override` (reason + by) saying why the "
            "refutation is wrong"
        )
    if state in ("stale", "expired"):
        return (
            "re-judge this claim — `agsoc video judge <ep> --claim <id>`. The "
            "judgement on record was made about other words, or too long ago "
            "to stand"
        )
    if state == "malformed":
        return (
            "the pass-2 judgement on this claim cannot be read — re-run it with "
            "`agsoc video judge <ep> --claim <id>`"
        )
    verdict = _verdict(record)
    mechanical = record.get("mechanical") or {}
    if verdict == "no_source":
        return (
            "cite the beat (`src:` + `quote:`), or say it without the claim. "
            "Nothing was checked here"
        )
    if verdict == "manual":
        return "write `attest:` on the beat — a sentence saying what it draws"
    if mechanical.get("quote_found") is False:
        return (
            "the quote is not in that source: fix `quote:` to what the source "
            "says, or cite the source that says it"
        )
    return (
        "correct the figure, widen `quote:` so it covers it, or write a "
        "`claim_override` (reason + by) in script.yaml"
    )


def _near_miss(document: str | None, record: dict) -> str:
    """What the source says where the quote stopped matching (§8.2).

    "Near-misses report as failures with the closest candidate span attached, so
    the human sees *why* rather than a bare red mark." A bare red mark is what
    teaches people to override without looking.
    """
    span = (record.get("mechanical") or {}).get("closest_span")
    if document is None or not isinstance(span, list) or len(span) != 2:
        return ""
    at, to = span
    if not all(isinstance(x, int) for x in (at, to)):
        return ""
    return _clip(_one_line(document[max(0, at - 40) : to + 40]), EXCERPT)


def _claim_row(record: dict) -> str:
    mark = "!" if is_blocking(record) else " "
    star = "*" if _written(record) else " "
    return (
        f" {mark}{star} {record.get('id', '?'):<7} beat {record.get('beat_index'):>2}  "
        f"{_clip(str(record.get('beat_type', '?')), TYPE_WIDTH):<{TYPE_WIDTH}}  "
        f"{_verdict(record)}{_pass2_mark(record)}"
    )


def _pass2_mark(record: dict) -> str:
    """What pass 2 said, on the row, or nothing at all when it has not run.

    A refuted claim's MECHANICAL verdict is `pass` — that is the whole point of
    pass 2 — so a row that prints only pass 1 puts a green word on the line the
    gate is about to refuse. Silent when unjudged: a mark on every row of every
    episode is a mark nobody reads on the one that matters.
    """
    state, _ = adversarial_state(record)
    return "" if state == "unjudged" else f" · pass 2 {state}"


def _pass2_why(record: dict) -> str:
    """Why pass 2 refuses this claim, or "". The screens never read the block."""
    return adversarial_state(record)[1]


def _cleared_summary(records: list[dict]) -> str:
    """The line printed when nothing is open — and it must not overclaim.

    It used to say "7 claims verified, none open" on a screen that also said
    *"attested by hand — no machine checked these"* about one of the seven
    (D-112, the third overclaim in two phases). A `manual` is not verified; it
    is attested, and the difference is the whole of D-088.

    Counted through `classify`, the same function `approve` gates on, so the
    denominator cannot drift from the decision. Every claim lands in exactly one
    of the three buckets, which is what stops a summary rounding toward
    reassurance by quietly dropping one.
    """
    tally = verify_mod.claim_tally(records)
    parts = [f"{tally['verified']} verified"]
    if tally["attested"]:
        parts.append(f"{tally['attested']} attested by hand, NOT verified (D-088)")
    if tally["overridden"]:
        parts.append(f"{tally['overridden']} cleared by override, NOT verified (§8.4)")
    if len(parts) == 1:
        return f"{_plural(tally['verified'], 'claim')} verified, none open"
    parts.append(f"{_plural(tally['total'], 'claim')}, none open")
    return " · ".join(parts)


def _counts(records: list[dict]) -> str:
    """The counts line on both screens — over the verdict that BINDS.

    It said `24 pass` on an episode with a claim pass 2 had refused, four lines
    above a table cell reading `unsupported`, because it tallied the
    measurement. That is the fifth instance of a number that does not say what
    it counted, and the second in one phase; the arithmetic now comes from
    `binding_verdict`, the function the cell under it uses.
    """
    tally: dict[str, int] = {}
    for record in records:
        word = binding_verdict(record)
        tally[word] = tally.get(word, 0) + 1
    return " · ".join(
        f"{tally[w]} {w}"
        for w in sorted(
            tally, key=lambda w: (COUNT_ORDER.index(w) if w in COUNT_ORDER else 99, w)
        )
    )


def _print_detail(ep, record: dict, documents: dict) -> None:
    """Everything an operator needs about one refused claim, without the file."""
    typer.secho(_claim_row(record).rstrip(), fg=typer.colors.RED)
    if _reason(record):
        typer.echo(_detail("why", _reason(record)))
    if _pass2_why(record):
        typer.echo(_detail("pass 2", _pass2_why(record)))
    if record.get("text"):
        typer.echo(_detail("beat", record["text"]))
    if record.get("quote"):
        typer.echo(_detail("quote", f"“{record['quote']}”"))
    if record.get("src"):
        typer.echo(_detail("src", f"sources/{record['src']}.txt"))
    excerpt = _near_miss(documents.get(record.get("src")), record)
    if excerpt:
        typer.echo(_detail("source", f"…{excerpt}…"))
    attest = (record.get("mechanical") or {}).get("attest")
    if attest:
        typer.echo(_detail("attest", attest))
    written, fault = override_state(record)
    if fault:
        # The one override screen that has to shout. A malformed override is a
        # sentence its author believes cleared a claim, and the claim is still
        # open — so it is printed WITH the refusal, never in the quiet block.
        typer.echo(_detail("override", f"clears nothing — it {fault}"))
    elif written:
        typer.echo(_detail("override", _sentence(written)))
    typer.echo(_detail("fix", _next_step(record)))
    typer.echo("")


def _print_attestations(records: list[dict]) -> None:
    """Every `manual` claim's sentence, whether or not it blocks (D-088).

    An attested `custom` beat passes the gate, and it passes it on a human's
    word: nothing mechanical looked at what its JavaScript draws. Printing the
    attestation only when it is MISSING would mean the one screen before
    approval never shows the sentence the approval rests on.
    """
    rows = [r for r in records if _verdict(r) == "manual" and not is_blocking(r)]
    if not rows:
        return
    typer.echo(
        "  attested by hand — no machine checked these (D-088), you are "
        "approving the sentence:"
    )
    for record in rows:
        typer.echo(
            _detail(
                str(record.get("id", "?")),
                f"“{(record.get('mechanical') or {}).get('attest', '')}”",
                indent=4,
            )
        )
    typer.echo("")


def _print_overrides(records: list[dict]) -> None:
    """§8.4's overrides, in three groups, because they mean three things.

    An override that CLEARED a claim is the sentence the approver is signing,
    and it belongs on the same screen as the attestations for the same reason
    (D-088): the one screen before approval must show what the approval rests
    on. An override on a claim that passes anyway is STALE — a written sentence
    about a problem that no longer exists, and leaving it silent is how the
    sentences stop being read. An override that clears NOTHING is a claim its
    author believes is handled and the gate still refuses; that one is printed
    with the refusal itself, and only counted here.

    The rate closes the block (D-040): the number that says the checker is
    wrong rather than the operator.
    """
    applied, stale = [], []
    for record in records:
        written, _ = override_state(record)
        if written is None:
            continue
        # `stale_override` is the predicate, not a second reading of the same
        # rule: which group a written sentence lands in is one answer, and the
        # sweep found this line restating it. Two statements of one rule is the
        # D-036 pattern, on the screen where it decides what an operator reads.
        (stale if stale_override(record) is not None else applied).append(
            (record, written)
        )
    if not applied and not stale:
        return
    if applied:
        typer.echo(
            textwrap.fill(
                "cleared by override — §8.4, NOT verified by anything. You are "
                "approving the sentence and the name on it:",
                width=ROW_WIDTH,
                initial_indent="  ",
                subsequent_indent="  ",
            )
        )
        for record, written in applied:
            # The verdict that BINDS, not the measurement. A claim pass 2
            # refuted and a human cleared printed `pass` here — beside the very
            # sentence that was needed to get past the refusal — which reads as
            # *it was fine anyway*. Sixth instance of the shape, found by
            # looking for it after the fifth (D-106, D-110, D-112, D-118, D-122).
            typer.echo(
                _detail(
                    str(record.get("id", "?")),
                    f"{binding_verdict(record)} — {_sentence(written)}",
                    indent=4,
                )
            )
        typer.echo("")
    if stale:
        typer.echo(
            textwrap.fill(
                "STALE overrides — these claims clear without them. Delete "
                "them: a sentence that bypasses nothing is how the next real "
                "one stops being read:",
                width=ROW_WIDTH,
                initial_indent="  ",
                subsequent_indent="  ",
            )
        )
        for record, written in stale:
            typer.echo(
                _detail(str(record.get("id", "?")), _sentence(written), indent=4)
            )
        typer.echo("")
    typer.echo(
        textwrap.fill(
            f"override {_override_rate(len(applied), len(records))}",
            width=ROW_WIDTH,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    typer.echo("")


def _print_pass2(records: list[dict]) -> None:
    """§8.3's pass, on both screens: what it covered, and what kind of thing it is.

    Three things this block has to do, and only the first is obvious:

      * **Say how much of the episode pass 2 reached.** §8.4 does not refuse an
        unjudged claim, so an episode can be signed with pass 2 never run — and
        that must not look like an episode pass 2 cleared. The count is printed
        even at zero, which is the one case it exists for.
      * **Say that these are judgements.** Pass 1 re-runs to the same answer in a
        year and pass 2 does not. A reader who cannot tell them apart trusts them
        equally, so the line says so and every judgement carries its author and
        the date it stops standing.
      * **Print `residual_risk` on SUPPORTED claims.** §8.3 calls it often the
        most useful output of the whole pass — "the source does not state an
        effective date" is exactly what a human should read before signing — and
        a risk shown only on failures is a risk nobody reads on the episode they
        are about to approve. Absent risks stay silent: most claims have none,
        and "no residual risk" on every line is the noise this has to cut
        through.
    """
    if not records:
        return
    tally = verify_mod.pass2_tally(records)
    typer.echo(
        textwrap.fill(
            f"pass 2  {tally['judged']} of {_plural(tally['total'], 'claim')} "
            "judged — a judgement by an agent, NOT a measurement: not "
            "reproducible, and it expires",
            width=ROW_WIDTH,
            subsequent_indent="        ",
        )
    )
    for record in records:
        judged = verify_mod.judgement(record)
        if judged is None:
            continue
        parts = [
            f"{judged['state']} — judged by {judged['judged_by']} on "
            f"{_one_line(str(judged['judged_at']))}, stops standing "
            f"{judged['expires_on']}"
        ]
        if judged["residual_risk"]:
            parts.append(f"residual risk: {judged['residual_risk']}")
        typer.echo(_detail(str(record.get("id", "?")), " · ".join(parts), indent=4))
    typer.echo("")


def _print_entities(records: list[dict]) -> None:
    """§8.2 step 3, recorded and NOT gated — D-102, said on the screen.

    35% of entity atoms on the real brief are unfindable and not one of them was
    a real entity error; gating them would refuse 5 beats of 8. Shown anyway,
    because an operator can tell a tokeniser artefact from a wrong attribution
    in a second and no rule here can. Labelled so it cannot read as a check that
    passed.
    """
    rows = [
        (record, (record.get("mechanical") or {}).get("entities_missing") or [])
        for record in records
    ]
    rows = [(record, missing) for record, missing in rows if missing]
    if not rows:
        return
    typer.echo(
        textwrap.fill(
            "names not found in the source — recorded, not gated (D-102: the "
            "extractor glues names together, so this cannot hold a gate):",
            width=ROW_WIDTH,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    for record, missing in rows:
        typer.echo(
            _detail(str(record.get("id", "?")), ", ".join(str(m) for m in missing), indent=4)
        )
    typer.echo("")


@video_app.command("check")
def video_check(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Verify every claim in the script against the corpus, and write claims.json.

    Pass 1 only — mechanical, local, no model and no network (§8.2). Pass 2 is
    Phase 9; the ledger carries `adversarial: null` until then, because "not run
    yet" and "ran and said nothing" must not look the same to the gate.

    Takes IDENTIFIERS and loads what it verifies (D-072). Every bypass this
    project has had was a caller-built object trusted by the thing checking it,
    and one of them published a draft (D-059) — so there is no argument here a
    caller can shape, and the script verified is the script on disk.

    Exits non-zero when any claim is `fail`, `no_source`, or an unattested
    `manual` — §8.4's list, minus the two adversarial verdicts that do not exist
    yet. It does NOT move the episode's status: only `approve` does that, and
    `approve` is Phase 7.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        ledger = verify_mod.verify_episode(ep)
        path = verify_mod.write_ledger(ep, ledger)
        # Loaded again, from disk, for the runtime line. `verify_episode` takes
        # identifiers and loads its own script (D-072); handing its copy out
        # here would be the caller-built object this command exists not to have.
        script = load_script(ep)
        runtime = check_runtime(script, s)
    except (
        SeriesError,
        EpisodeError,
        ScriptError,
        claims_mod.ClaimsError,
        corpus_mod.CorpusError,
        verify_mod.VerifyError,
    ) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write {verify_mod.CLAIMS_NAME}: {e}")

    records = ledger["claims"]
    documents: dict[str, str] = {}
    for record in records:
        src = record.get("src")
        if isinstance(src, str) and src and src not in documents:
            try:
                documents[src] = corpus_mod.document_text(ep, src)
            except corpus_mod.CorpusError:
                pass

    head = f"{s.slug}/{ep.id} · {_plural(len(records), 'claim')}"
    typer.echo(f"{head} · {_counts(records)}" if records else head)
    # At the TOP, with `review`'s stale-ledger banner, and not down with the
    # runtime report: the last line of this screen is a summary of the claims,
    # and a green "none open" printed under a red drift warning is the last
    # thing read (D-112's shape). A banner above the table is read first.
    _echo_drift(ep)
    typer.echo("")
    for record in records:
        line = _claim_row(record).rstrip()
        if is_blocking(record):
            typer.secho(line, fg=typer.colors.RED)
        else:
            typer.echo(line)
    typer.echo("")

    blocked = [record for record in records if is_blocking(record)]
    for record in blocked:
        _print_detail(ep, record, documents)
    _print_attestations(records)
    _print_overrides(records)
    _print_pass2(records)
    _print_entities(records)

    typer.echo(f"wrote {path}")
    _echo_runtime(script, runtime)
    if not records:
        typer.echo("no claims — this script asserts nothing about the world")
        return
    if blocked:
        raise _fail(
            f"{len(blocked)} of {_plural(len(records), 'claim')} not verified — "
            "this episode is not approvable until they clear"
        )
    typer.secho(_cleared_summary(records), fg=typer.colors.GREEN)


# A figure with no digit in front of its decimal point — what `$1.32` leaves
# behind after a shell has removed `$1` from a double-quoted argument.
_LOST_MAGNITUDE = re.compile(r"(?<![\w.])(\.\d[\d,]*)")


def _prose(inline: str | None, path: str | None, flag: str, label: str) -> str | None:
    """One prose field, from an argument or from a file — never from both.

    **The file is the byte-exact path and it exists because of a real defect.**
    `--refutation "$1.32"` records `.32`: the shell removes `$1` before this
    command is reached, the write succeeds and the verdict reads normally on
    every screen while quoting a price nobody wrote. Nothing downstream can
    detect that, because the bytes that would prove it were destroyed one
    process earlier — so the fix is a route that never passes the prose through
    a shell at all, not a checker for text that is already gone.

    Two sources for one field would be the D-059 shape at the input boundary:
    the silent winner is whichever the code reads second. So it refuses.
    """
    if inline is not None and path is not None:
        raise _fail(
            f"{label} was given twice — `{flag}` and `{flag}-file`. Pass one: "
            f"`{flag}-file` for anything a refuter wrote, because the shell "
            "cannot reach those bytes"
        )
    if path is not None:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise _fail(f"{path} is not UTF-8 text, so it cannot be recorded")
        except OSError as e:
            raise _fail(f"cannot read {path}: {e}")
        return _text(text, label)
    return None if inline is None else _text(inline, label)


def _echo_lost_magnitude(text: str, field: str, flag: str) -> None:
    """Say when an inline argument looks like it was eaten by the shell.

    A NOTE, never a refusal, and it says only what it can see. `.32` is a legal
    thing to write; this command cannot know whether a `$1` was there, and it
    does not claim to — the wording is conditional because the evidence is. It
    is also incomplete by construction: `$1M` expands to nothing at all and
    leaves no residue for anything to find. That is why the note points at the
    flag that makes the whole class impossible rather than at a fix for this
    one.
    """
    found = _LOST_MAGNITUDE.search(text)
    if found is None:
        return
    typer.secho(
        _detail(
            "warning",
            f"the {field} contains `{found.group(1)}` — a figure with no leading "
            f"digit. If it was typed inline as `${'{'}n{'}'}{found.group(1)}`, the shell "
            f"removed the `$` and the digits before it and this record now "
            f"quotes a number nobody wrote. `{flag}-file <path>` is not re-read "
            "by a shell",
            indent=2,
        ),
        fg=typer.colors.YELLOW,
    )


@video_app.command("judge")
def video_judge(
    episode: str,
    claim: str = typer.Option(..., "--claim", help="claim id, e.g. c-001"),
    verdict: str = typer.Option(
        ..., "--verdict", help="supported · unsupported · refuted"
    ),
    refutation: Optional[str] = typer.Option(
        None,
        "--refutation",
        help="what you attacked and what the source said — required, §8.3",
    ),
    refutation_file: Optional[str] = typer.Option(
        None,
        "--refutation-file",
        help="a file holding it instead — no shell touches these bytes",
    ),
    risk: Optional[str] = typer.Option(
        None, "--risk", help="residual risk, recorded even on `supported`"
    ),
    risk_file: Optional[str] = typer.Option(
        None, "--risk-file", help="a file holding the residual risk"
    ),
    by: str = typer.Option(..., "--by", help="who or what judged — required"),
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Record one pass-2 verdict into claims.json (§8.3). It makes no judgement.

    **This command stores an argument somebody else made.** The CLI contains no
    LLM calls (CLAUDE.md) and pass 2 is irreducibly a judgement pass, so the
    `verify` skill runs one blind refuter per claim and this writes down what it
    concluded. Nothing here reaches the network or a model, and nothing here
    decides anything except whether the record is well formed.

    A refutation is required and may not be blank. A `supported` with no
    account of what was attacked records only that somebody looked, which is
    worth nothing — it is the evidence for the verdict, and this project has
    printed a conclusion stronger than its evidence four times.

    **Give it as `--refutation-file <path>` whenever a refuter wrote it.**
    `--refutation "$1.32"` records `.32`: a shell removes `$1` from a
    double-quoted argument before this command exists, the write succeeds, and
    the verdict reads normally on every screen while quoting a price nobody
    wrote. A file is never re-read by a shell, so `$`, backticks and
    apostrophes land byte for byte. `--risk-file` is the same field's twin.
    Inline stays for a sentence a person is typing, and prints a note when what
    arrives looks like it lost a magnitude.

    Takes IDENTIFIERS and loads the ledger itself (D-072). It refuses on a
    missing or stale `claims.json`, on an unknown claim id, and on a claim pass
    1 did not clear.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    claim = _text(claim, "The claim id")
    refutation = _prose(refutation, refutation_file, "--refutation", "The refutation")
    risk = _prose(risk, risk_file, "--risk", "The residual risk")
    by = _text(by, "The judge")
    if refutation is None:
        raise _fail(
            "a verdict needs its refutation: what did you attack, and what did "
            "the source say back? Pass `--refutation-file <path>` — the bytes "
            "of a refuter's own reply, unread by any shell — or `--refutation` "
            "for a sentence you are typing yourself"
        )
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        block = verify_mod.record_adversarial(
            ep,
            claim,
            verdict=verdict,
            attempted_refutation=refutation,
            residual_risk=risk,
            by=by,
        )
    except (SeriesError, EpisodeError, verify_mod.VerifyError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write {verify_mod.CLAIMS_NAME}: {e}")

    typer.echo(f"{s.slug}/{ep.id} · {claim} · pass 2 {block['verdict']}")
    typer.echo(_detail("refuted", block["attempted_refutation"], indent=2))
    if block["residual_risk"]:
        typer.echo(_detail("risk", block["residual_risk"], indent=2))
    # Only for what arrived through a shell. A file cannot have lost anything.
    if refutation_file is None:
        _echo_lost_magnitude(block["attempted_refutation"], "refutation", "--refutation")
    if risk_file is None and block["residual_risk"]:
        _echo_lost_magnitude(block["residual_risk"], "residual risk", "--risk")
    # The honesty line, on the screen the agent that recorded it reads. A stored
    # judgement that looks like a stored measurement is the confusion this whole
    # record exists to prevent.
    typer.echo(
        _detail(
            "note",
            f"a judgement by {block['judged_by']}, not a measurement — not "
            f"reproducible, and it stops standing after "
            f"{verify_mod.PASS2_HORIZON_DAYS} days",
            indent=2,
        )
    )


def _print_open_claims(records: list[dict]) -> None:
    """Name every claim that refused, and say what to do about each.

    D-040: a checker that refuses without teaching trains an operator to
    override everything, including the true refusal sitting in the same run.
    """
    for record in records:
        typer.secho(_claim_row(record).rstrip(), fg=typer.colors.RED)
        if _reason(record):
            typer.echo(_detail("why", _reason(record)))
        if _pass2_why(record):
            typer.echo(_detail("pass 2", _pass2_why(record)))
        typer.echo(_detail("fix", _next_step(record)))


@video_app.command("approve")
def video_approve(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    by: str = typer.Option(
        ...,
        "--by",
        help="who is approving — recorded in script.yaml, required",
    ),
) -> None:
    """THE GATE (§8.4). Move an episode `in_review → approved`.

    Refuses while any claim is `fail`, `no_source` or an unattested `manual`,
    and refuses on a stale or absent `claims.json` — approving against a ledger
    that no longer describes the script is the same defect as never checking.

    Takes IDENTIFIERS and loads what it gates (D-072). It does not re-run
    `check`: the ledger on disk is the artifact of record and the screen a human
    read before signing, and computing a second set of verdicts in here would be
    two paths to one answer with only one of them on the screen.

    `--by` is required and is never inferred. The series `byline` is a display
    credit on the frame, not an account of who spent this gate, and an OS
    username is whoever's laptop the command ran on.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    approver = _text(by, "The approver")
    try:
        record = approve_mod.approve_episode(ws, series, episode, by=approver)
    except approve_mod.ApprovalRefused as e:
        head = f"{series}/{episode} · NOT approved"
        if e.kind == "claims":
            typer.secho(f"{head} — {e}", fg=typer.colors.RED)
            typer.echo("")
            _print_open_claims(e.claims)
            typer.echo("")
            raise _fail(
                f"run `agsoc video check {episode} --series {series}` for the "
                "full detail. Nothing moved; the episode is still in_review"
            )
        if e.kind == "ledger":
            typer.secho(f"{head} — {e}", fg=typer.colors.RED)
            typer.echo(_detail("why", str(e)))
            raise _fail(
                _detail(
                    "fix",
                    f"run `agsoc video check {episode} --series {series}`, read "
                    "it, then approve",
                )
            )
        raise _fail(f"{head} — {e}")
    except TransitionError as e:
        raise _fail(
            f"{series}/{episode} · NOT approved — {e}. Only a script an agent "
            "has finished and marked `status: in_review` can be approved"
        )
    except (SeriesError, EpisodeError, verify_mod.VerifyError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write script.yaml: {e}")

    typer.secho(f"{series}/{episode} · approved", fg=typer.colors.GREEN)
    typer.echo(_detail("by", record["by"]))
    typer.echo(_detail("at", record["at"]))
    typer.echo(_detail("script", f"sha256 {record['script_sha256']} (the beats document)"))
    counted = record["claims"]
    if counted["total"]:
        tail = ""
        if counted["attested"]:
            tail += f" · {counted['attested']} attested by hand, not verified (D-088)"
        if counted["overridden"]:
            tail += (
                f" · {counted['overridden']} cleared by override, not verified (§8.4)"
            )
        typer.echo(
            _detail(
                "claims",
                f"{counted['verified']} of {counted['total']} verified{tail}, "
                f"checked {record['claims_checked_at']}",
            )
        )
        # Every claim that is standing on a person rather than on a source, on
        # the screen of the person it is standing on, at the moment they sign —
        # and the rate beside it (D-040). Reading these off the RECORD, not off
        # the ledger a second time: the screen and the file must be one answer.
        for entry in record.get("overrides", []):
            typer.echo(
                _detail("override", f"{entry['id']}  “{entry['reason']}” — {entry['by']}")
            )
        if counted["overridden"]:
            typer.echo(
                _detail(
                    "override",
                    _override_rate(counted["overridden"], counted["total"]),
                )
            )
    else:
        typer.echo(
            _detail("claims", "none — this script asserts nothing about the world")
        )
    # The other half of what was just signed, and the half an operator does not
    # expect to have signed: `series.toml` paints every frame and is a different
    # file from the one they were reading. Said on the screen because a
    # guarantee nobody knows they have is one nobody notices losing — and
    # because the next person to change the accent should have been told, once,
    # that it is covered.
    inputs = record.get("series_inputs") or {}
    if inputs:
        typer.echo(_detail("design", _covered_inputs(inputs)))
    typer.echo(
        _detail(
            "next",
            "edit the beats and this approval no longer describes them — "
            "`script_sha256` is what says so; the same goes for the design, "
            "and `agsoc video check` says so on both",
        )
    )


def _covered_inputs(inputs: dict) -> str:
    """What of `series.toml` this approval binds, counted off the record itself.

    Derived from the record, never re-listed here: the screen and the file are
    one answer, and a hand-written summary is where they would stop being one.
    """
    labels = {"design": "design", "acts": "act labels"}
    parts = []
    for key in sorted(inputs):
        value = inputs[key]
        label = labels.get(key, key)
        if isinstance(value, dict):
            parts.append(f"{label} ({len(value)})")
        else:
            parts.append(label)
    return (
        f"series.toml is covered too — {', '.join(parts)}. Change any of them "
        "and this approval no longer describes the frame"
    )


@video_app.command("preview")
def video_preview(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Render an episode to video WITHOUT the gate. Changes no status.

    It carried a `--probe` flag until Phase 8. `probe` is its own command now:
    the cheap operation must not be a flag on the fourteen-minute one.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        out = render_mod.preview(s, ep)
    except (SeriesError, EpisodeError, PlanError, render_mod.RenderError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write output: {e}")
    typer.echo(f"wrote {out}")


@video_app.command("probe")
def video_probe(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    at: float = typer.Option(
        None, "--at", help="one frame at t=T seconds, instead of one per beat"
    ),
    fmt: str = typer.Option("vertical", "--format", help="output format"),
) -> None:
    """Look at the frames — one per beat, or one at `--at T`. No encode (§6).

    This is the honest answer to what an approval does not cover (D-116). The
    beats, `pace` and the design are signed; `engine.js`, `scene.html`'s CSS,
    the font this machine resolved, Chromium and ffmpeg are not, and a font
    substitution changes every frame with every check green. Nothing can extend
    the approval over the pixels, so looking at them is made cheap instead.

    It moves no status and works at any status: probing is how you decide
    whether to approve.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        out = render_mod.probe(s, ep, fmt=fmt, at=at)
    except (SeriesError, EpisodeError, PlanError, render_mod.RenderError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write output: {e}")
    frames = sorted(out.glob("*.png")) if out.is_dir() else [out]
    typer.secho(f"{series}/{episode} · {len(frames)} frame(s)", fg=typer.colors.GREEN)
    typer.echo(f"      {'at' if at is not None else 'in':<{LABEL_WIDTH}}{out}")
    typer.echo(_detail("format", _format_line(fmt)))
    typer.echo(
        _detail(
            "note",
            "nothing moved — a probe reads the script and draws frames. What "
            "you are looking at is this machine's fonts and this machine's "
            "Chromium, which is exactly the part no approval covers",
        )
    )


@video_app.command("render")
def video_render(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    fmt: str = typer.Option(
        None,
        "--format",
        help="one format; the default is every enabled format in series.toml",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="re-render a format whose file is already in out/, overwriting it",
    ),
    restart: bool = typer.Option(
        False,
        "--restart",
        help="an earlier render was killed: mark it failed and start over",
    ),
) -> None:
    """Render an APPROVED episode to an MP4, in every enabled format (§9, §10).

    Three checks, and they stay three so you are told which thing moved
    (D-115): the status, the approval against what you authored, and the claim
    ledger against the corpus. It does not re-run `check` — the ledger on disk
    is the artifact of record, and a second set of verdicts computed here would
    be verdicts nobody displayed.

    One approval covers every format, because the format is not part of what was
    signed. What it does not cover is a file you already have: a format already
    in `out/` is kept, and `--replace` is how you say otherwise.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    head = f"{series}/{episode} · NOT rendered"
    try:
        run = render_mod.render_episode(
            ws, series, episode, fmt=fmt, replace=replace, restart=restart
        )
    except TransitionError as e:
        # `rendered` no longer arrives here: §9's second format is `rendered →
        # rendering` and it is a supported move. What is left is an episode
        # nobody has approved, which is one message and one remedy.
        raise _fail(
            f"{head} — {e}. Only an episode a human has approved renders: "
            f"`agsoc video approve {episode} --series {series} --by \"Your Name\"`"
        )
    except render_mod.RenderRefused as e:
        raise _fail(_refusal(head, e, episode, series))
    except (SeriesError, EpisodeError, PlanError, verify_mod.VerifyError,
            render_mod.RenderError) as e:
        raise _fail(f"{head} — {e}")
    except OSError as e:
        raise _fail(f"{head} — cannot write output: {e}")
    _echo_rendered(series, episode, run)


def _refusal(head: str, e: render_mod.RenderRefused, episode: str, series: str) -> str:
    """One screen per kind. Three answers, three files to open (D-115)."""
    if e.kind == "interrupted":
        typer.secho(f"{head} — {e}", fg=typer.colors.RED)
        return _detail(
            "fix",
            "if nothing is running, `agsoc video render "
            f"{episode} --series {series} --restart` marks the abandoned run "
            "failed and starts over. A partial render is discarded, not "
            "resumed: frames are reproducible, so there is nothing in them to "
            "salvage",
        )
    if e.kind == "drift":
        typer.secho(
            f"{head} — the approval no longer describes this episode", fg=typer.colors.RED
        )
        typer.echo(_detail("why", str(e)))
        return _detail(
            "fix",
            "put the change back, or run `agsoc video check "
            f"{episode} --series {series}` and approve again",
        )
    if e.kind == "exists":
        # Not a gate refusal: the approval, the beats and the ledger all just
        # passed. It is a refusal to spend an artifact the operator already has,
        # and the screen has to say which of the two it is — otherwise they go
        # looking for a problem with the episode that is not there.
        typer.secho(f"{head} — {e}", fg=typer.colors.RED)
        return _detail(
            "fix",
            "nothing was rendered and nothing was replaced. The three checks "
            "all passed — this is only about the file(s) above. `agsoc video "
            f"render {episode} --series {series} --replace` re-renders and "
            "overwrites them; add `--format F` to replace one",
        )
    typer.secho(f"{head} — the check does not describe this script", fg=typer.colors.RED)
    typer.echo(_detail("why", str(e)))
    return _detail(
        "fix", f"run `agsoc video check {episode} --series {series}`, read it, then approve"
    )


def _format_line(*formats: str) -> str:
    """R5, said where an operator reads it rather than in a docstring.

    `approve` binds what the operator authored — the beats, `pace`, and the
    series.toml values that reach the frame. The FORMAT is typed on a command
    line minutes or days later, and one approval can render both. A screen that
    listed it beside the things that were signed would be claiming a human
    looked at this shape of the card, and nobody has: a 9:16 headline set across
    16:9 is the same words in a layout no approver saw.
    """
    named = []
    for f in formats:
        geometry = plan_mod.FORMATS.get(f)
        named.append(f"{f} · {geometry['w']}x{geometry['h']}" if geometry else f)
    return (
        f"{' and '.join(named)} · chosen at render time and NOT part of the "
        "approval — one approval renders every format, and the approver saw "
        "none of them"
    )


def _size(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB" if n >= 100_000 else f"{n / 1000:.0f} kB"


def _echo_rendered(series: str, episode: str, run) -> None:
    """The success screen, written deliberately (D-116).

    It may say the episode was approved and that nothing the operator authored
    has changed, because all three checks just passed. It may **not** say or
    imply that this is what the approver saw: `engine.js`, `planbuild.js`,
    `scene.html`'s CSS, the resolved font, Chromium and ffmpeg are all outside
    the approval, and a font substitution changes every frame with every check
    green.

    This project has overclaimed on the summary line four times (D-106, D-110,
    D-112, D-113) — always here, always because the summary is written last by
    someone who already knows the answer. So the last line is not a flourish; it
    is the part that makes the rest of the screen true.
    """
    records = [r.record for r in run.rendered]
    typer.secho(
        f"{series}/{episode} · rendered {_plural(len(records), 'format')}",
        fg=typer.colors.GREEN,
    )
    for result in run.rendered:
        record = result.record
        # Not through `_detail`: a wrapped path is a path you cannot copy out of
        # a terminal, and this is the one line an operator will select and paste.
        typer.echo(f"      {'file':<{LABEL_WIDTH}}{result.path}")
        typer.echo(
            _detail(
                "",
                f"{_size(record['bytes'])} · {record['runtime_sec']:.1f}s · "
                f"{record['width']}x{record['height']} · {record['frames']} "
                f"frames @ {record['fps']}fps",
            )
        )
    # What this invocation did NOT do, said as plainly as what it did. A run
    # that quietly skips the format already on disk and prints a heading saying
    # `rendered` is the overclaim pattern (D-123) pointed at the operator's own
    # artifacts — and the skip is the common case, because the vertical cut is
    # normally rendered days before anyone wants the wide one.
    for path in run.kept:
        typer.echo(
            _detail(
                "kept",
                f"{path.name} was already in out/ and was NOT re-rendered — "
                "`--replace` re-renders it",
            )
        )
    for path in run.replaced:
        typer.echo(
            _detail("replaced", f"{path.name} — the file that was there is gone")
        )
    typer.echo(_detail("format", _format_line(*(r["format"] for r in records))))
    approval = records[-1].get("approval") or {}
    typer.echo(
        _detail(
            "approved",
            f"{approval.get('by')} at {approval.get('at')} — and nothing you "
            "authored has changed since: the beats, `pace` and series.toml's "
            "design are the ones that were signed",
        )
    )
    typer.echo(
        _detail(
            "scope",
            "the approval does NOT cover what drew these frames — engine.js, "
            "planbuild.js, scene.html's CSS, the font this machine resolved, "
            "Chromium and ffmpeg are all outside the approval, and the font is "
            "the one that differs between machines. Nobody has looked at this "
            f"video: `agsoc video probe {episode} --series {series}` puts one "
            "frame per beat on disk in seconds",
        )
    )


# --- `agsoc video console` ------------------------------------------------------
#
# Spec §12's screens C and D, as one offline HTML file. The one step where a
# graphical surface genuinely beats a terminal is adjudicating claims against
# source text with the supporting quote highlighted in place, and a terminal
# cannot highlight a span inside a paragraph of the operator's own source.
#
# The console module imports this one — `beat_summary`, `_next_step`, `_counts`
# — rather than the reverse: the page is built ON these screens, so one remedy
# sentence and one counts line serve both, and the console cannot send an
# operator somewhere `check` would not. The import below is therefore local to
# the command, and that is the only reason it is not at the top of the file.


@video_app.command("console")
def video_console(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    out: Optional[Path] = typer.Option(
        None, "--out", help="where to write the HTML (default: a temp directory)"
    ),
) -> None:
    """Write the review console: the claims, the source, and the quote in place.

    A READ-ONLY screen. It cannot approve anything and it writes nothing into
    the episode — not the ledger, not the script, not a derived file. §8.4's
    gate is `agsoc video approve`; it takes identifiers and loads from disk
    (D-072) because in v1 a draft was published through a second path around a
    gate (D-059), and a second way to approve is exactly the defect Phase 7
    spent three tasks eliminating. This page prints the command.

    The file lands OUTSIDE `workspace/` by default and any `--out` inside it is
    refused. It is derived — regenerate it in a second — and `workspace/` holds
    the operator's authored content, which nothing derived should be mixed into.
    """
    from . import console as console_mod

    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))

    target = (
        Path(tempfile.gettempdir()) / "agsoc-console" / f"{s.slug}-{ep.id}.html"
        if out is None
        else Path(out)
    )
    # Resolved before the comparison and before anything is built: a relative
    # path, a symlink or a `..` that lands back inside the workspace is the same
    # write, and a refusal that can be spelled around is not one.
    resolved = target.resolve()
    root = ws.root.resolve()
    if resolved == root or root in resolved.parents:
        raise _fail(
            f"{resolved} is inside the workspace. The console is derived and "
            "read-only; `workspace/` holds the content itself, and this command "
            "writes nothing there — least of all into an episode directory, "
            "where it would be a second writer beside `check` (D-059, D-113). "
            "Pass a path outside it, or none at all."
        )

    try:
        html = console_mod.build(s, ep)
    except (
        SeriesError,
        EpisodeError,
        ScriptError,
        PlanError,
        claims_mod.ClaimsError,
        corpus_mod.CorpusError,
        verify_mod.VerifyError,
        console_mod.ConsoleError,
    ) as e:
        # Nothing is written on this path. A console built from a file nobody
        # parsed is worse than no console: it would be a confident picture of
        # an episode that does not load.
        raise _fail(str(e))

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(resolved, html)
    except OSError as e:
        raise _fail(f"cannot write the console: {e}")

    typer.secho(f"{s.slug}/{ep.id} · review console", fg=typer.colors.GREEN)
    typer.echo(f"      {'wrote':<{LABEL_WIDTH}}{resolved}")
    # NOT wrapped: `_detail` folds at ROW_WIDTH, and a URL folded across two
    # lines is one an operator cannot copy — the single thing this line is for.
    typer.echo(f"      {'open':<{LABEL_WIDTH}}file://{resolved}")
    typer.echo(
        _detail(
            "note",
            "read-only. It writes nothing into the episode, makes no network "
            "request, and cannot approve anything — the gate is `agsoc video "
            f"approve {ep.id} --series {s.slug} --by \"<name>\"`, which "
            "re-reads every file before it decides",
        )
    )


# --- coverage ---------------------------------------------------------------------------
#
# `agsoc coverage`, replacing `node engine/coverage.mjs` (D-112, retired in
# Phase 11). The ledger is per-series now: `engine/coverage.json` was one file
# shared by every series, and two series sharing one ledger means one series'
# history suppresses the other's stories.


def _coverage_series(ws: Workspace, slug: str):
    try:
        return load_series(ws, slug)
    except SeriesError as e:
        raise _fail(str(e))


def _coverage_ledger(series):
    try:
        return coverage_mod.load_ledger(series)
    except coverage_mod.CoverageError as e:
        raise _fail(str(e))


def _other_ledgers(ws: Workspace, series) -> dict:
    """Every OTHER series' ledger, for the pointer below a miss.

    Read defensively: this walks files the series being checked does not own,
    and one unreadable neighbour must not take the check down (D-018).
    """
    out = {}
    for slug in series_slugs(ws):
        if slug == series.slug:
            continue
        try:
            out[slug] = coverage_mod.load_ledger(load_series(ws, slug))
        except (SeriesError, coverage_mod.CoverageError, OSError):
            continue
    return out


def _scope(ledger, series) -> str:
    stories, episodes = coverage_mod.counts(ledger)
    return (
        f"{stories} stories across {episodes} episodes in series "
        f"`{series.slug}` (id, title, note, entities, sources), separators ignored"
    )


@coverage_app.command("check")
def coverage_check(
    terms: list[str] = typer.Argument(..., help="one or more candidate story keywords"),
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Has this series already told this story?

    Pass two terms per story — the vendor and the thing. Separators are ignored
    in both directions, so `gemini-3.7` finds `Gemini 3.7 Flash`: the matcher
    strips every non-alphanumeric character from both sides and asks for
    containment, which can only ever ADD a match (D-112). Its cost is false
    positives, and that is the direction to be wrong in for a check whose
    failure mode is re-telling a story as new.

    A hit is not automatically a veto — it means: drop the story, or cover it as
    an explicit update and say what changed.
    """
    ws = _workspace()
    series = _text(series, "The series slug")
    s = _coverage_series(ws, series)
    ledger = _coverage_ledger(s)
    results = coverage_mod.check_terms(ledger, [_text(t, "A term") for t in terms],
                                       _other_ledgers(ws, s))
    scope = _scope(ledger, s)
    hits = 0
    for result in results:
        if result.found:
            hits += len(result.found)
            typer.echo(f'\n  "{result.term}"  — {len(result.found)} prior mention(s):')
            for story in result.found:
                label = story.get("angle") or story.get("beat") or ""
                typer.echo(f"     {story['date']}  [{story.get('id', '?')}]  {label}")
                typer.echo(f"       {story.get('title', '')}")
                if story.get("note"):
                    typer.echo(f"       note: {story['note']}")
        else:
            # What a miss is allowed to say. The old line was "NOT COVERED. Safe
            # to run as new." — a claim about the world a string search cannot
            # support, and the exact sentence a blind runner acted on to clear a
            # story this series had run three days earlier.
            typer.echo(f'\n  "{result.term}"  — no entry matches this string.')
            typer.echo(f"     searched {scope}.")
            typer.echo(
                "     That is all it proves. It does not mean the story is new: the ledger"
            )
            typer.echo(
                "     holds only what was written into it after an episode shipped."
            )
            if result.related:
                pointer = ", ".join(
                    f'"{w}" appears in {n} story(ies)' for w, n in result.related
                )
                typer.echo(
                    f"     Related, and not a hit: {pointer}. Run those terms and read the titles"
                )
                typer.echo("     before you decide this story is a different one.")
        if result.elsewhere:
            # R3's other half. Coverage is per-series — another series' history
            # must never suppress this one's story, so this is never counted —
            # but an author is told the story exists rather than left to find
            # out from a viewer.
            other = ", ".join(
                f"`{slug}` ({n} story(ies))" for slug, n in result.elsewhere
            )
            typer.echo(f"     Told in another series, and not counted here: {other}.")
            typer.echo(
                "     Coverage is per-series: this series has not told it. Read those "
                "entries before you decide how to tell it."
            )
    if hits:
        typer.echo(
            f"\n  → {hits} hit(s). Cover these as updates (state what is new) "
            "or drop them.\n"
        )
    else:
        typer.echo(f"\n  → 0 matches in {scope}.")
        typer.echo("    Nothing in the ledger contains these strings. Whether the stories are")
        typer.echo("    new is a judgement this check cannot make for you.\n")


@coverage_app.command("add")
def coverage_add(
    episode: str = typer.Argument(..., help="episode id, e.g. 2026-08-20"),
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    note: str = typer.Option("", "--note", help="what this episode did with the stories"),
    replace: bool = typer.Option(False, "--replace", help="re-record an episode already in the ledger"),
    dry_run: bool = typer.Option(False, "--dry-run", help="print the entry; write nothing"),
) -> None:
    """Record a rendered episode's stories in the series ledger (§6).

    Deliberately NOT a side effect of `render`. An automatic `add` records what
    was *rendered*, and a render that is discarded and never posted would then
    suppress a story the series never told — a silent drop, which is the failure
    this ledger exists to prevent, pointing the other way. The operator runs
    this when the episode is out.

    What it records is what the episode put on screen: one entry per beat that
    asserts something, with the entities `agsoc video check` extracted and the
    source the beat cited. Chrome beats (`title`, `signoff`) assert nothing and
    are skipped, exactly as they are exempt from citation.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    note = _text(note, "The note")
    s = _coverage_series(ws, series)
    try:
        ep = load_episode(s, episode)
        coverage_mod.assert_recordable(ep)
        script = load_script(ep)
        ledger = coverage_mod.load_ledger(s)
        entry = coverage_mod.episode_entry(ep, script, note=note)
        merged = coverage_mod.add_entry(ledger, entry, replace=replace)
    except (
        SeriesError,
        EpisodeError,
        ScriptError,
        claims_mod.ClaimsError,
        coverage_mod.CoverageError,
    ) as e:
        raise _fail(str(e))

    typer.echo(f"\n  {s.slug}/{entry['date']} · {len(entry['stories'])} story(ies) recorded")
    for story in entry["stories"]:
        typer.echo(f"     [{story['id']}]  {story['title']}")
    if dry_run:
        typer.echo("\n  --dry-run: nothing written.\n")
        return
    try:
        coverage_mod.save_ledger(s, merged)
    except OSError as e:
        raise _fail(f"cannot write {coverage_mod.LEDGER_NAME}: {e}")
    stories, episodes = coverage_mod.counts(merged)
    typer.echo(f"\n  recorded in {coverage_mod.ledger_path(s)}")
    typer.echo(f"  the ledger now holds {stories} stories across {episodes} episodes.")
    typer.echo(
        "  what it records is what was RENDERED. If this episode is never "
        "posted, remove\n  the entry — an entry for an episode nobody saw "
        "suppresses a story you never told.\n"
    )


@coverage_app.command("list")
def coverage_list(
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    ids: bool = typer.Option(False, "--ids", help="print story ids only"),
) -> None:
    """Everything this series has covered, newest first."""
    ws = _workspace()
    series = _text(series, "The series slug")
    s = _coverage_series(ws, series)
    ledger = _coverage_ledger(s)
    stories = coverage_mod.all_stories(ledger)
    if ids:
        for story in stories:
            typer.echo(story.get("id", ""))
        return
    day = ""
    for story in stories:
        if story["date"] != day:
            day = story["date"]
            typer.echo(f"\n  {day}")
        flag = "UPDATE " if story.get("update") else ""
        typer.echo(f"    {flag}[{story.get('id', '?')}]  {story.get('title', '')}")
    stories_n, episodes_n = coverage_mod.counts(ledger)
    typer.echo(f"\n  {stories_n} stories across {episodes_n} episodes in `{s.slug}`.\n")


@coverage_app.command("episode")
def coverage_episode(
    date: str = typer.Argument(..., help="episode date, e.g. 2026-08-14"),
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """One episode's rundown, as the ledger holds it."""
    ws = _workspace()
    date = _text(date, "The episode date")
    series = _text(series, "The series slug")
    s = _coverage_series(ws, series)
    ledger = _coverage_ledger(s)
    found = [e for e in ledger["episodes"] if e.get("date") == date]
    if not found:
        known = ", ".join(e.get("date", "?") for e in ledger["episodes"]) or "none"
        raise _fail(f"no episode for {date} in `{s.slug}`. Known: {known}")
    ep = found[0]
    head = f"\n  {ep.get('date')}"
    if ep.get("video"):
        head += f" · {ep['video']}"
    if ep.get("runtimeSec") is not None:
        head += f" · {ep['runtimeSec']}s"
    typer.echo(head)
    if ep.get("note"):
        typer.echo(f"  {ep['note']}")
    for story in ep.get("stories", []):
        label = story.get("angle") or story.get("beat") or ""
        typer.echo(f"\n   [{story.get('id', '?')}]  {story.get('act', '')}  ({label})")
        typer.echo(f"   {story.get('title', '')}")
        typer.echo(f"   sources: {', '.join(story.get('sources') or [])}")
    typer.echo("")


@coverage_app.command("migrate")
def coverage_migrate(
    source: Path = typer.Argument(..., help="a ledger to merge in, e.g. engine/coverage.json"),
    series: str = typer.Option(..., "--series", help="the series that produced those episodes"),
    dry_run: bool = typer.Option(False, "--dry-run", help="report; write nothing"),
) -> None:
    """Merge a ledger written before Phase 11 into the series that produced it.

    `--series` is required and takes exactly one slug: copying one shared
    ledger into every series would suppress, in each of them, stories that
    series never told. Idempotent — an episode already present with identical
    content is skipped, so an operator unsure whether it ran can just run it.
    An episode present with DIFFERENT content is refused by name: picking a
    winner would lose the entry that was not picked.
    """
    ws = _workspace()
    series = _text(series, "The series slug")
    s = _coverage_series(ws, series)
    try:
        legacy = coverage_mod.load_legacy(Path(source))
        ledger = coverage_mod.load_ledger(s)
        merged, report = coverage_mod.migrate(ledger, legacy)
    except coverage_mod.CoverageError as e:
        raise _fail(str(e))

    typer.echo(f"\n  {source} → {coverage_mod.ledger_path(s)}")
    typer.echo(
        f"  source holds {report.stories_source} stories across "
        f"{len(legacy['episodes'])} episodes"
    )
    typer.echo(
        f"  moved {len(report.episodes_moved)} episode(s): "
        f"{', '.join(report.episodes_moved) or 'none'}"
    )
    if report.episodes_skipped:
        typer.echo(
            f"  already present, unchanged: {', '.join(report.episodes_skipped)}"
        )
    typer.echo(f"  stories {report.stories_before} → {report.stories_after}")
    if dry_run:
        typer.echo("\n  --dry-run: nothing written.\n")
        return
    try:
        coverage_mod.save_ledger(s, merged)
    except OSError as e:
        raise _fail(f"cannot write {coverage_mod.LEDGER_NAME}: {e}")
    typer.echo(
        f"\n  the source file is not modified — it stays as the record of what "
        f"was migrated.\n  Check it reads back: `agsoc coverage list --series {s.slug}`\n"
    )

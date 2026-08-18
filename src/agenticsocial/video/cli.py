"""`agsoc series` and `agsoc video` commands."""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

import typer

from ..models import Status, TransitionError
from ..workspace import Workspace, WorkspaceError
from . import approve as approve_mod
from . import claims as claims_mod
from . import corpus as corpus_mod
from . import ingest as ingest_mod
from . import render as render_mod
from . import verify as verify_mod
from .episode import create_episode, episode_ids, load_episode
from .models import EpisodeError, SeriesError
from .plan import PlanError, check_runtime
from .script import RENDERABLE, Beat, ScriptError, load_script
from .series import load_series, scaffold_series, series_slugs

series_app = typer.Typer(help="Manage video series.", no_args_is_help=True)
video_app = typer.Typer(help="Create and manage video episodes.", no_args_is_help=True)

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
CLAIM_WIDTH = 9  # `no_source`, the longest verdict
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
            verdicts[record["beat_index"]] = _verdict(record) + (
                "*" if _written(record) else ""
            )
    return ledger, None, False, verdicts


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
        head = (
            f"{'!' if is_blocking(record) else '*'} {record.get('id')} · "
            f"beat {record.get('beat_index')} · {_verdict(record)}"
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
        f"{_verdict(record)}"
    )


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
    order = list(verify_mod.VERDICTS)
    tally: dict[str, int] = {}
    for record in records:
        tally[_verdict(record)] = tally.get(_verdict(record), 0) + 1
    return " · ".join(
        f"{tally[v]} {v}"
        for v in sorted(tally, key=lambda v: (order.index(v) if v in order else 99, v))
    )


def _print_detail(ep, record: dict, documents: dict) -> None:
    """Everything an operator needs about one refused claim, without the file."""
    typer.secho(_claim_row(record).rstrip(), fg=typer.colors.RED)
    if _reason(record):
        typer.echo(_detail("why", _reason(record)))
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
            typer.echo(
                _detail(
                    str(record.get("id", "?")),
                    f"{_verdict(record)} — {_sentence(written)}",
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


def _print_open_claims(records: list[dict]) -> None:
    """Name every claim that refused, and say what to do about each.

    D-040: a checker that refuses without teaching trains an operator to
    override everything, including the true refusal sitting in the same run.
    """
    for record in records:
        typer.secho(_claim_row(record).rstrip(), fg=typer.colors.RED)
        if _reason(record):
            typer.echo(_detail("why", _reason(record)))
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
            typer.secho(f"{head} — the check does not describe this script", fg=typer.colors.RED)
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
    probe: bool = typer.Option(False, "--probe", help="one frame per beat, no video"),
) -> None:
    """Render an episode to video. Does NOT change its status — the gated
    `render` command arrives with the approval workflow."""
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
        out = render_mod.preview(s, ep, probe=probe)
    except (SeriesError, EpisodeError, PlanError, render_mod.RenderError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write output: {e}")
    typer.echo(f"wrote {out}")


@video_app.command("render")
def video_render(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    fmt: str = typer.Option("vertical", "--format", help="output format"),
    restart: bool = typer.Option(
        False,
        "--restart",
        help="an earlier render was killed: mark it failed and start over",
    ),
) -> None:
    """Render an APPROVED episode to an MP4 (§9, §10).

    Three checks, and they stay three so you are told which thing moved
    (D-115): the status, the approval against what you authored, and the claim
    ledger against the corpus. It does not re-run `check` — the ledger on disk
    is the artifact of record, and a second set of verdicts computed here would
    be verdicts nobody displayed.
    """
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    head = f"{series}/{episode} · NOT rendered"
    try:
        result = render_mod.render_episode(
            ws, series, episode, fmt=fmt, restart=restart
        )
    except TransitionError as e:
        # Branching on the state, because one message cannot be right for both.
        # `rendered` is terminal (D-006) and pointing that operator at `approve`
        # sends them to a command that will refuse them for a second reason.
        if e.current is Status.RENDERED:
            raise _fail(
                f"{head} — {e}. `rendered` is terminal in the MVP (D-006): the "
                "file in `out/` is this episode's render, and there is no "
                "supported way back. A changed story is a new episode"
            )
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
    _echo_rendered(series, episode, result)


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
    typer.secho(f"{head} — the check does not describe this script", fg=typer.colors.RED)
    typer.echo(_detail("why", str(e)))
    return _detail(
        "fix", f"run `agsoc video check {episode} --series {series}`, read it, then approve"
    )


def _size(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB" if n >= 100_000 else f"{n / 1000:.0f} kB"


def _echo_rendered(series: str, episode: str, result) -> None:
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
    record = result.record
    typer.secho(f"{series}/{episode} · rendered", fg=typer.colors.GREEN)
    # Not through `_detail`: a wrapped path is a path you cannot copy out of a
    # terminal, and this is the one line an operator will select and paste.
    typer.echo(f"      {'file':<{LABEL_WIDTH}}{result.path}")
    typer.echo(
        _detail(
            "",
            f"{_size(record['bytes'])} · {record['runtime_sec']:.1f}s · "
            f"{record['width']}x{record['height']} · {record['frames']} frames "
            f"@ {record['fps']}fps",
        )
    )
    approval = record.get("approval") or {}
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
            f"video: `agsoc video preview {episode} --series {series} --probe` "
            "puts one frame per beat on disk",
        )
    )

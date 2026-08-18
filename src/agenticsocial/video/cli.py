"""`agsoc series` and `agsoc video` commands."""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

import typer

from ..workspace import Workspace, WorkspaceError
from . import claims as claims_mod
from . import corpus as corpus_mod
from . import ingest as ingest_mod
from . import render as render_mod
from . import verify as verify_mod
from .episode import create_episode, episode_ids, load_episode
from .models import EpisodeError, SeriesError
from .plan import PlanError, check_runtime
from .script import RENDERABLE, Beat, Script, ScriptError, load_script
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
    typer.echo(f'next: agsoc video ingest {ep.id} --research "<query>"')


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


def is_blocking(record: dict) -> bool:
    """Would §8.4 refuse this claim? `fail`, `no_source`, or an unattested `manual`.

    An override does NOT clear it. §8.4 puts the override in front of `approve`,
    not in front of the measurement: `check` reports what was measured, and a
    check that went quiet because someone wrote a sentence would be reporting
    the sentence. Phase 7 is what consumes `override`; this is not that gate.

    Written over the ledger record, not over `Mechanical`, because the record is
    what survives to the gate. A `manual` claim whose `attest` was lost between
    the check and the file is unattested to everyone who reads the file.
    """
    mechanical = record.get("mechanical") or {}
    verdict = mechanical.get("verdict")
    if verdict == "manual":
        return not str(mechanical.get("attest") or "").strip()
    return verdict in ("fail", "no_source")


def _verdict(record: dict) -> str:
    return str((record.get("mechanical") or {}).get("verdict") or "?")


def _reason(record: dict) -> str:
    return str((record.get("mechanical") or {}).get("reason") or "")


def _override(record: dict) -> dict | None:
    value = record.get("override")
    return value if isinstance(value, dict) else None


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


def _script_drift(script: Script, ledger: dict) -> str | None:
    """Has the script moved under this ledger? `corpus_sha` cannot see it.

    Task 2's `stale_reason` answers the corpus half — the bytes a claim was
    checked against. The other half is the beats themselves: rewrite a figure,
    and every verdict in `claims.json` still lines up by `beat_index` and is
    now about a sentence nobody wrote. That is the same lie as a stale corpus
    arriving through the other door, and the display must not tell it.

    Compared on the CLAIMS the script produces, not on the file's bytes: a
    reformatted comment is not a changed assertion, and a check invalidated by
    whitespace is one operators re-run without reading.
    """
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


def _ledger_state(episode, script: Script):
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
    stale = verify_mod.stale_reason(episode, ledger) or (
        _script_drift(script, ledger) if ledger is not None else None
    )
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
                "*" if _override(record) else ""
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
        override = _override(record)
        if not is_blocking(record) and not override:
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
        if override:
            typer.echo(
                _detail(
                    "override",
                    f"“{override.get('reason')}” — {override.get('by')} "
                    "(recorded; `approve` is what reads it)",
                )
            )
    typer.echo("")


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
    ledger, ledger_note, warn, verdicts = _ledger_state(ep, script)

    typer.echo(
        f"{s.slug}/{ep.id} · {ep.status.value} · {_plural(len(beats), 'beat')} · "
        f"pace {_pace(script.pace)}"
    )
    if ledger_note:
        typer.secho(
            textwrap.fill(_one_line(ledger_note), width=ROW_WIDTH),
            fg=typer.colors.YELLOW if warn else None,
        )
    typer.echo("")
    for line in _review_table(beats, verdicts):
        typer.echo(line)
    typer.echo("")
    if verdicts is not None:
        _print_claim_summary(ledger)

    held = sum(b.hold for b in beats)
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
    star = "*" if _override(record) else " "
    return (
        f" {mark}{star} {record.get('id', '?'):<7} beat {record.get('beat_index'):>2}  "
        f"{_clip(str(record.get('beat_type', '?')), TYPE_WIDTH):<{TYPE_WIDTH}}  "
        f"{_verdict(record)}"
    )


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
    override = _override(record)
    if override:
        typer.echo(
            _detail("override", f"“{override.get('reason')}” — {override.get('by')}")
        )
        typer.echo(
            _detail(
                "",
                "recorded, not applied: `check` reports the measurement. "
                "`approve` is what reads an override",
            )
        )
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
    _print_entities(records)

    typer.echo(f"wrote {path}")
    if not records:
        typer.echo("no claims — this script asserts nothing about the world")
        return
    if blocked:
        raise _fail(
            f"{len(blocked)} of {_plural(len(records), 'claim')} not verified — "
            "this episode is not approvable until they clear"
        )
    typer.secho(
        f"{_plural(len(records), 'claim')} verified, none open",
        fg=typer.colors.GREEN,
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

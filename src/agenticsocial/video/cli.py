"""`agsoc series` and `agsoc video` commands."""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

import typer

from ..workspace import Workspace, WorkspaceError
from . import ingest as ingest_mod
from . import render as render_mod
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


# One summariser per catalogue type. A dict rather than a chain of `if`s for the
# same reason BEAT_TYPES is: adding a type in Phase 4 is a row here. There is no
# `.get(type, "")` default anywhere below — a default is how a new type silently
# gets a blank text column and stops being reviewable.
SUMMARISERS = {
    "statement": lambda b: _one_line(b.fields.get("text", "")),
    "body": lambda b: _one_line(b.fields.get("text", "")),
    "list": lambda b: _join([b.fields.get("lead", ""), *b.fields.get("items", [])]),
    "kpis": lambda b: _join(_kpi(i) for i in b.fields.get("items", [])),
    "jumpChart": lambda b: _join(r.get("label", "") for r in b.fields.get("rows", [])),
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


def _review_table(beats) -> list[str]:
    """One screen line per beat, inside ROW_WIDTH columns.

    `src` gets its own right-hand column rather than being appended after the
    text: §7.2 makes the source the thing an approver actually checks, and a
    column you scan down the page is checkable in a way a ragged tail is not.
    It only appears when some beat has one — an empty column on every row of
    a title-and-statement episode is just noise.
    """
    act_w = min(ACT_WIDTH, max(3, *(len(_one_line(b.act)) for b in beats)))
    type_w = min(TYPE_WIDTH, max(4, *(len(b.type) for b in beats)))
    src_cell = SRC_WIDTH + 2 if any(b.src for b in beats) else 0
    text_w = max(
        MIN_TEXT_WIDTH,
        ROW_WIDTH - LEAD - act_w - 2 - type_w - 2 - 5 - 2 - (src_cell + 2 if src_cell else 0),
    )

    head = f"    {'#':>2}  {'act':<{act_w}}  {'type':<{type_w}}  {'hold':>5}  {'text':<{text_w}}"
    lines = [(head + "  src" if src_cell else head).rstrip()]
    for b in beats:
        # `!` marks a beat this phase cannot draw. Not an error — see the
        # command docstring — so it is a margin mark, not a message.
        flag = " " if b.type in RENDERABLE else "!"
        src = f"[{_clip(_one_line(b.src), SRC_WIDTH)}]" if b.src else ""
        row = (
            f" {flag}  {b.index:>2}  {_clip(_one_line(b.act), act_w):<{act_w}}  "
            f"{_clip(b.type, type_w):<{type_w}}  {b.hold:>5.1f}  "
            f"{_clip(beat_summary(b), text_w):<{text_w}}"
        )
        lines.append((f"{row}  {src}" if src_cell else row).rstrip())
    return lines


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

    typer.echo(
        f"{s.slug}/{ep.id} · {ep.status.value} · {_plural(len(beats), 'beat')} · "
        f"pace {_pace(script.pace)}"
    )
    typer.echo("")
    for line in _review_table(beats):
        typer.echo(line)
    typer.echo("")

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

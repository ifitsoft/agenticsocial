"""agsoc — local-first content pipeline CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .models import Status, TransitionError
from .textutils import split_thread
from .workspace import Workspace, WorkspaceError, load_config
from .x import auth as x_auth
from .x.publish import ValidationError, format_review, validate_thread

app = typer.Typer(
    help="Capture sources, research, review drafts, and post to X. The agent drafts; you approve.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Capture sources, research, review drafts, and post to X."""


def _fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=False)
    return typer.Exit(code=1)


def _workspace() -> Workspace:
    try:
        return Workspace.locate()
    except WorkspaceError as e:
        raise _fail(str(e))


@app.command()
def version() -> None:
    """Print the agsoc version."""
    typer.echo(__version__)


@app.command()
def init(path: Path = typer.Argument(Path("workspace"))) -> None:
    """Scaffold a content workspace (sources/, voice.md, config.toml)."""
    ws = Workspace.init(path)
    typer.echo(f"workspace ready at {ws.root}/")
    typer.echo("next: edit voice.md (your voice profile) and config.toml (X client_id)")


@app.command()
def new(
    title: str,
    url: Optional[str] = typer.Option(None, "--url", help="origin URL (sets type=url)"),
    file: Optional[Path] = typer.Option(None, "--file", help="file whose text becomes the source body (sets type=transcript)"),
    type: Optional[str] = typer.Option(None, "--type", help="idea | url | transcript"),
) -> None:
    """Create a source from a title/idea, a URL, or a transcript file."""
    ws = _workspace()
    body = ""
    inferred = "idea"
    if url:
        inferred = "url"
    if file:
        inferred = "transcript"
        try:
            body = file.read_text(encoding="utf-8")
        except OSError as e:
            raise _fail(f"cannot read --file {file}: {e}")
    try:
        src = ws.create_source(title, type=type or inferred, origin_url=url, body=body)
    except WorkspaceError as e:
        raise _fail(str(e))
    typer.echo(f"created source {src.id}")


@app.command("list")
def list_(
    status: Optional[str] = typer.Option(None, "--status", help="only sources with a variant in this status"),
) -> None:
    """List sources and their variant statuses."""
    ws = _workspace()
    wanted = None
    if status:
        try:
            wanted = Status(status)
        except ValueError:
            raise _fail(f"unknown status '{status}' — one of: {', '.join(s.value for s in Status)}")
    for src in ws.list_sources():
        variants = ws.variants(src)
        if wanted and not any(v.status is wanted for v in variants):
            continue
        pills = " ".join(f"{v.platform}:{v.status.value}" for v in variants) or "(no variants)"
        typer.echo(f"{src.id}  [{src.type}]  {pills}")


@app.command()
def status() -> None:
    """Workspace overview: variant counts per status."""
    ws = _workspace()
    counts: dict[str, int] = {}
    for src in ws.list_sources():
        for v in ws.variants(src):
            counts[v.status.value] = counts.get(v.status.value, 0) + 1
    if not counts:
        typer.echo("workspace is empty — create a source with `agsoc new`")
        return
    for s in Status:
        if s.value in counts:
            typer.echo(f"{s.value:12} {counts[s.value]}")


def _load(ws: Workspace, source_query: str, platform: str):
    try:
        src = ws.resolve_source(source_query)
        return src, ws.load_variant(src, platform)
    except WorkspaceError as e:
        raise _fail(str(e))


@app.command()
def review(
    source: str,
    platform: str = typer.Option("x", "--platform"),
) -> None:
    """Render a variant for human review: per-tweet character counts and content."""
    ws = _workspace()
    src, v = _load(ws, source, platform)
    typer.echo(f"{src.id} · {platform} · status: {v.status.value}\n")
    typer.echo(format_review(split_thread(v.body)))
    if v.status is Status.IN_REVIEW:
        typer.echo(f"approve with: agsoc approve {src.id}")


@app.command()
def approve(
    source: str,
    platform: str = typer.Option("x", "--platform"),
) -> None:
    """Approve a variant for publishing (the human gate — agents must not run this)."""
    ws = _workspace()
    src, v = _load(ws, source, platform)
    try:
        if platform == "x":
            validate_thread(v.body)
        ws.set_status(v, Status.APPROVED)
    except (ValidationError, TransitionError) as e:
        raise _fail(str(e))
    typer.echo(f"approved {src.id} ({platform}) — post with: agsoc post {src.id}")


@app.command()
def auth(platform: str = typer.Argument("x")) -> None:
    """Connect a platform account (v1: x). One-time browser OAuth flow."""
    if platform != "x":
        raise _fail(f"unsupported platform '{platform}' — v1 supports: x")
    ws = _workspace()
    client_id = load_config(ws).get("x", {}).get("client_id", "")
    if not client_id:
        raise _fail(f"set [x] client_id in {ws.root / 'config.toml'} first (see README)")
    try:
        x_auth.authorize(client_id)
    except x_auth.AuthError as e:
        raise _fail(str(e))
    typer.echo("X account connected — token stored in your OS keychain")

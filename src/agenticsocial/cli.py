"""agsoc — local-first content pipeline CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .models import Status
from .workspace import Workspace, WorkspaceError

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
        body = file.read_text(encoding="utf-8")
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
    wanted = Status(status) if status else None
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

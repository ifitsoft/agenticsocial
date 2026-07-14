"""agsoc — local-first content pipeline CLI."""
from __future__ import annotations

import typer

from . import __version__

app = typer.Typer(
    help="Capture sources, research, review drafts, and post to X. The agent drafts; you approve.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Capture sources, research, review drafts, and post to X. The agent drafts; you approve."""


@app.command()
def version() -> None:
    """Print the agsoc version."""
    typer.echo(__version__)

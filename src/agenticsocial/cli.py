"""agsoc — local-first content pipeline CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__, research
from .models import Status, TransitionError, assert_transition
from .textutils import split_thread
from .workspace import Workspace, WorkspaceError, atomic_write, load_config
from .x import auth as x_auth
from .x.client import XApiError, XClient
from .x.publish import ValidationError, format_review, publish_variant, validate_thread

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


@app.command()
def post(
    source: str,
    platform: str = typer.Option("x", "--platform"),
    dry_run: bool = typer.Option(False, "--dry-run", help="validate and print; no network, no status change"),
    resume: bool = typer.Option(False, "--resume", help="continue a failed thread from where it stopped"),
) -> None:
    """Publish an approved variant to X. Threads post tweet-by-tweet, resumably."""
    if platform != "x":
        raise _fail(f"unsupported platform '{platform}' — v1 posts to: x")
    ws = _workspace()
    src, v = _load(ws, source, platform)
    try:
        tweets = validate_thread(v.body)
    except ValidationError as e:
        raise _fail(str(e))
    if dry_run:
        typer.echo(f"would post {len(tweets)} tweets:\n")
        typer.echo(format_review(tweets))
        return
    if v.status is Status.FAILED and not resume:
        raise _fail(
            f"{src.id} previously failed after {len(v.meta.get('posted_ids') or [])} tweets — "
            "rerun with --resume to continue the thread"
        )
    try:
        assert_transition(v.status, Status.PUBLISHING)  # gate check BEFORE touching the keyring
    except TransitionError as e:
        raise _fail(str(e))
    token = x_auth.load_token()
    if not token:
        raise _fail("no X token — connect first with `agsoc auth x`")
    client_id = load_config(ws).get("x", {}).get("client_id", "")
    if client_id and token.get("refresh_token"):
        try:
            token = x_auth.refresh(client_id, token)
        except x_auth.AuthError as e:
            raise _fail(str(e))
    try:
        url = publish_variant(ws, v, XClient(token["access_token"]))
    except TransitionError as e:
        raise _fail(str(e))
    except XApiError as e:
        raise _fail(f"posting failed mid-thread: {e}\nresume with: agsoc post {src.id} --resume")
    typer.echo(f"published: {url}")


@app.command("research")
def research_cmd(
    source: str,
    query: Optional[str] = typer.Option(None, "--query", help="search query (default: source title)"),
    max_results: int = typer.Option(8, "--max-results"),
) -> None:
    """Fetch search results (and the origin article, if any) into brief.md."""
    ws = _workspace()
    try:
        src = ws.resolve_source(source)
    except WorkspaceError as e:
        raise _fail(str(e))
    q = query or src.title
    try:
        results = research.search(q, max_results=max_results)
    except Exception as e:
        raise _fail(f"search failed: {e} — check your connection and retry")
    extracts: dict[str, str] = {}
    if src.origin_url:
        try:
            text = research.extract(src.origin_url)
        except Exception as e:
            typer.echo(f"warning: could not extract {src.origin_url}: {e}")
            text = None
        if text:
            extracts[src.origin_url] = text
    brief = research.build_brief(src.title, q, results, extracts)
    atomic_write(src.dir / "brief.md", brief)
    typer.echo(f"wrote {src.dir / 'brief.md'} ({len(results)} results, {len(extracts)} extractions)")

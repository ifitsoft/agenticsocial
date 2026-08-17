"""Fill the verification corpus from research, a paste, or an existing source.

Nothing here fetches directly: `search` and `extract` are injected so the module
is testable offline and so a future edit cannot quietly put the network inside a
unit test. Defaults resolve to `research.py`, which fetches and formats and never
summarises (CLAUDE.md).

Partial failure is the normal case. Three sources fetch and one 403s on an
ordinary day; the corpus gets the three and the record names the one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .. import research
from ..workspace import atomic_write
from . import corpus as C
from .models import Episode

PASTE_KEY = "_pasted"


class IngestError(Exception):
    pass


@dataclass(frozen=True)
class IngestResult:
    keys: list[str] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)
    brief_path: Path | None = None


def _existing_key_for_url(episode: Episode, url: str) -> str | None:
    """Reuse the key a URL already has.

    Keys are cited by claims. Re-deriving on a rebuild would hand
    `blog-google-2` to whichever article happened to be fetched second, silently
    re-pointing every citation — the one failure mode here that produces a wrong
    fact-check rather than a loud one. Matches the EXACT url, never the host.
    """
    if not url:
        return None
    for key, entry in C.read_manifest(episode).items():
        if isinstance(entry, dict) and entry.get("url") == url:
            return key
    return None


def _write(episode: Episode, text: str, *, url: str, title: str, key: str | None = None) -> str:
    existing = _existing_key_for_url(episode, url)
    if existing is not None:
        # `replace=True` or write_document suffixes it to `-2` and we hand back a
        # key the bytes were never written under. Return its value, never
        # `existing`: the key the caller reports must be the key on disk.
        return C.write_document(
            episode, text, url=url, title=title, key=existing, replace=True
        )
    return C.write_document(episode, text, url=url, title=title, key=key)


def _brief(
    episode: Episode,
    heading: str,
    query: str,
    written: list[tuple[str, str, str]],
    failures: list[tuple[str, str]],
) -> Path:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [f"# {heading}", "", f"_Query: {query} · ingested {now}_", ""]

    # The corpus accumulates but brief.md is rewritten whole by every ingest, so
    # a brief built from THIS call's writes silently drops everything earlier
    # runs fetched. The manifest already holds url/title for the whole corpus,
    # so a brief regenerated from it is correct by construction. `written` is
    # only the fallback for a manifest that cannot be read.
    try:
        manifest = C.read_manifest(episode)
    except C.CorpusError:
        manifest = {}
    entries = [
        (key, entry.get("url") or "", entry.get("title") or "")
        for key, entry in sorted(manifest.items())
    ] or list(written)

    if entries:
        lines += ["## Sources in the corpus", ""]
        for key, url, title in entries:
            lines += [f"- `{key}` — {title or '(untitled)'}", f"  <{url}>" if url else "  (pasted)"]
        lines.append("")
    else:
        lines += ["## Sources in the corpus", "", "_No sources were ingested._", ""]
    if failures:
        lines += ["## Failed to fetch", ""]
        for url, reason in failures:
            lines.append(f"- <{url}> — {reason}")
        lines.append("")
    path = episode.dir / "brief.md"
    atomic_write(path, "\n".join(lines))
    return path


def ingest_research(
    episode: Episode,
    query: str,
    *,
    max_results: int = 8,
    search=None,
    extract=None,
) -> IngestResult:
    search = search or research.search
    extract = extract or research.extract
    try:
        results = search(query, max_results=max_results)
    except Exception as e:
        raise IngestError(f"search failed: {e} — check your connection and retry")

    keys: list[str] = []
    written: list[tuple[str, str, str]] = []
    failures: list[tuple[str, str]] = []

    for r in results:
        url = (r or {}).get("href") or ""
        title = (r or {}).get("title") or ""
        if not url:
            continue
        try:
            text = extract(url)
        except Exception as e:
            failures.append((url, f"{type(e).__name__}: {e}"))
            continue
        if not text or not text.strip():
            failures.append((url, "no readable text extracted"))
            continue
        try:
            key = _write(episode, text, url=url, title=title)
        except C.CorpusError as e:
            # Partial failure is the normal case (module docstring), and a
            # result the corpus cannot key is one of them. Letting it propagate
            # aborted the whole run, recorded nothing, and left no brief.md.
            failures.append((url, str(e)))
            continue
        keys.append(key)
        written.append((key, url, title))

    return IngestResult(keys, failures, _brief(episode, "Brief", query, written, failures))


def ingest_paste(episode: Episode, text: str, *, title: str = "pasted digest") -> IngestResult:
    """Pasted text IS the corpus (D-041): the operator vouched for it by pasting."""
    if not text or not text.strip():
        return IngestResult([], [("", "pasted text was empty")], _brief(episode, "Brief", "(pasted)", [], [("", "pasted text was empty")]))
    key = C.write_document(episode, text, url="", title=title, key=PASTE_KEY)
    return IngestResult(
        [key], [], _brief(episode, "Brief", "(pasted)", [(key, "", title)], [])
    )


def ingest_source(episode: Episode, source) -> IngestResult:
    """Pull an existing agsoc source's body into the corpus (spec 11)."""
    body = ""
    try:
        from .. import frontmatter

        _, body = frontmatter.parse((source.dir / "source.md").read_text(encoding="utf-8"))
    except OSError as e:
        return IngestResult([], [(source.id, f"cannot read source: {e}")],
                            _brief(episode, "Brief", source.id, [], [(source.id, str(e))]))
    if not body.strip():
        fails = [(source.id, "source body is empty")]
        return IngestResult([], fails, _brief(episode, "Brief", source.id, [], fails))
    # source.id is a date plus a slugified title, and it becomes a filename, a
    # manifest key and a citation token. episode.py caps ids with MAX_ID_LEN for
    # exactly this reason; corpus keys were not capped.
    key = f"src-{source.id}"[:64]
    key = C.write_document(
        episode, body, url=source.origin_url or "", title=source.title, key=key
    )
    return IngestResult(
        [key], [], _brief(episode, "Brief", source.id, [(key, source.origin_url or "", source.title)], [])
    )

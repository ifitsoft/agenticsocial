"""The verification corpus: fetched text on disk, and proof it has not moved.

Spec 4: a claim is never checked against what an agent recalls reading — it is
checked against bytes on disk. This module owns those bytes and the manifest
that binds each one to its origin, so a check made today can be re-run in a year
and mean the same thing.

Order is deliberate: the document is written BEFORE the manifest. A crash
between them leaves an orphan file, which is harmless and detectable; the
reverse would leave a manifest entry pointing at nothing.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from urllib.parse import urlparse

from ..workspace import atomic_write
from .models import Episode
from ..workspace import assert_safe_name

MANIFEST_NAME = "_manifest.json"
SUFFIX = ".txt"


class CorpusError(Exception):
    pass


def key_for(url: str) -> str:
    """A stable, filesystem-safe key derived from a URL's host.

    `host.replace(".", "-")`, minus a leading `www-`. Spec 5 illustrates
    `venturebeat.txt`, but stripping the TLD needs a TLD list and gets a name
    wrong the first time someone cites a `.co.uk`. A predictable rule beats a
    pretty one.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise CorpusError(f"cannot derive a source key: {url!r} has no host")
    key = host.replace(".", "-")
    if key.startswith("www-"):
        key = key[4:]
    return key


def _manifest_path(episode: Episode):
    return episode.sources_dir / MANIFEST_NAME


def read_manifest(episode: Episode) -> dict:
    path = _manifest_path(episode)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CorpusError(f"{path}: {MANIFEST_NAME} is unreadable — {e}")
    except OSError as e:
        raise CorpusError(f"{path}: cannot read {MANIFEST_NAME} — {e}")
    if not isinstance(data, dict):
        raise CorpusError(f"{path}: {MANIFEST_NAME} must be an object")
    for key, entry in data.items():
        if not isinstance(entry, dict):
            raise CorpusError(
                f"{path}: manifest entry {key!r} must be an object, got "
                f"{type(entry).__name__}"
            )
    return data


def document_text(episode: Episode, key: str) -> str:
    assert_safe_name(key, "source key", CorpusError)
    path = episode.sources_dir / (key + SUFFIX)
    if not path.is_file():
        raise CorpusError(f"no source {key!r} in this episode's corpus")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise CorpusError(f"{path}: corpus documents must be UTF-8 — {e}")
    except OSError as e:
        raise CorpusError(f"{path}: cannot read source — {e}")


def write_document(
    episode: Episode,
    text: str,
    *,
    url: str,
    title: str = "",
    fetched_at: str | None = None,
    key: str | None = None,
) -> str:
    """Write one fetched document and record it. Returns the key used."""
    key = key if key is not None else key_for(url)
    assert_safe_name(key, "source key", CorpusError)

    manifest = read_manifest(episode)
    if key in manifest:
        base, n = key, 2
        while f"{base}-{n}" in manifest:
            n += 1
        key = f"{base}-{n}"
        assert_safe_name(key, "source key", CorpusError)

    raw = text.encode("utf-8")
    episode.sources_dir.mkdir(parents=True, exist_ok=True)
    # Document first: an orphan file is detectable, a dangling entry is not.
    atomic_write(episode.sources_dir / (key + SUFFIX), text)
    manifest[key] = {
        "url": url,
        "title": title,
        "fetched_at": fetched_at
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    atomic_write(
        _manifest_path(episode),
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return key


def verify(episode: Episode) -> list[tuple[str, str]]:
    """Check the corpus against its manifest. Empty list means sound.

    Problems: `("missing", key)` — recorded but absent; `("modified", key)` —
    bytes no longer hash to what was recorded; `("orphan", filename)` — a
    document nothing recorded.
    """
    manifest = read_manifest(episode)
    problems: list[tuple[str, str]] = []
    if not episode.sources_dir.is_dir():
        # The manifest lives in this directory, so if it is gone `manifest` is
        # already empty. This guard exists only to stop iterdir() raising.
        return problems

    for key in sorted(manifest):
        path = episode.sources_dir / (key + SUFFIX)
        if not path.is_file():
            problems.append(("missing", key))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != manifest[key].get("sha256"):
            problems.append(("modified", key))

    known = {k + SUFFIX for k in manifest}
    for entry in sorted(episode.sources_dir.iterdir()):
        if entry.name == MANIFEST_NAME or not entry.is_file():
            continue
        if entry.name not in known:
            problems.append(("orphan", entry.name))

    return sorted(problems)

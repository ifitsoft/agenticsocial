# Task 1 Brief: The corpus — files, manifest, integrity

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `e820492`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why this is the phase's centre of gravity

Spec §4: *the verification corpus is a directory of fetched text, not a memory.*
A claim is never checked against what an agent recalls reading — it is checked
against **bytes on disk**. That is what makes Phase 5's verification reproducible
months later and what lets the review console highlight an exact supporting span.

**If the corpus is not trustworthy, every fact-check built on it is theatre.**
So this task is about integrity, not convenience: a document, a manifest binding
it to its origin, and a way to prove the two still agree.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 15 of my briefs have had that defect.
- **No network, in source or tests.** This module does no fetching; it is handed
  text. Fetching arrives in Task 2.
- Do not add dependencies. Never stage anything under `docs/`.
- Report observed counts. Never adjust anything to reach a number I predicted.

## Files

- Create: `src/agenticsocial/video/corpus.py`
- Test: `tests/test_video_corpus.py`

## Interfaces

- `CorpusError(Exception)`
- `MANIFEST_NAME = "_manifest.json"`
- `key_for(url: str) -> str`
- `write_document(episode, text, *, url, title="", fetched_at=None, key=None) -> str` — returns the key used
- `read_manifest(episode) -> dict`
- `document_text(episode, key) -> str`
- `verify(episode) -> list[tuple[str, str]]` — `(problem, detail)`, empty when sound

## Design decisions you must not silently change

**Document first, manifest second.** If the process dies between them you get an
*orphan file* (harmless, detectable) rather than a *manifest entry pointing at
nothing* (a broken reference the verifier must then special-case). Order matters
and the tests pin it.

**Keys are derived from the host, mechanically.** `host.replace(".", "-")` with a
leading `www-` stripped. `blog.google` → `blog-google`; `venturebeat.com` →
`venturebeat-com`. Spec §5 illustrates `venturebeat.txt`, but that is an
illustration — matching it would require TLD knowledge, and a predictable rule
beats a pretty one. **Recorded as a deliberate deviation.**

**Keys become filenames**, so Phase 1's path-safety rules apply (D-038). A key
that is not safe is a `CorpusError`, never a write.

**The manifest records `sha256` of the exact bytes written.** That is what makes
tampering detectable and what Phase 5's `corpus_sha` will aggregate.

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_video_corpus.py`:

```python
import json

import pytest

from agenticsocial.video import corpus as C
from agenticsocial.video.episode import create_episode
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def episode(ws):
    s = scaffold_series(ws, "the-brief", name="The Brief")
    return create_episode(s, "2026-08-14")


# --- keys ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://blog.google/products/gemini/x", "blog-google"),
        ("https://venturebeat.com/ai/story", "venturebeat-com"),
        ("https://www.reuters.com/tech/", "reuters-com"),
        ("http://EXAMPLE.COM/A", "example-com"),
        ("https://sub.domain.example.org/p?q=1#f", "sub-domain-example-org"),
    ],
)
def test_key_for_derives_from_the_host(url, expected):
    assert C.key_for(url) == expected


def test_key_for_rejects_a_url_with_no_host():
    with pytest.raises(C.CorpusError, match="host"):
        C.key_for("not-a-url")


# --- writing ------------------------------------------------------------------


def test_write_document_creates_the_file_and_manifest_entry(episode):
    key = C.write_document(
        episode, "the article body", url="https://blog.google/x", title="A post"
    )
    assert key == "blog-google"
    assert (episode.sources_dir / "blog-google.txt").read_text(encoding="utf-8") == (
        "the article body"
    )
    entry = C.read_manifest(episode)["blog-google"]
    assert entry["url"] == "https://blog.google/x"
    assert entry["title"] == "A post"
    assert entry["bytes"] == len("the article body".encode())
    assert "fetched_at" in entry


def test_manifest_records_the_sha256_of_the_bytes_written(episode):
    import hashlib

    text = "the article body"
    C.write_document(episode, text, url="https://blog.google/x")
    entry = C.read_manifest(episode)["blog-google"]
    assert entry["sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_two_sources_coexist(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    C.write_document(episode, "two", url="https://venturebeat.com/y")
    assert set(C.read_manifest(episode)) == {"blog-google", "venturebeat-com"}


def test_same_host_twice_gets_a_distinct_key(episode):
    a = C.write_document(episode, "one", url="https://blog.google/x")
    b = C.write_document(episode, "two", url="https://blog.google/y")
    assert a != b
    assert C.document_text(episode, a) == "one"
    assert C.document_text(episode, b) == "two"


def test_an_explicit_key_is_used_verbatim(episode):
    key = C.write_document(episode, "pasted", url="", key="_pasted")
    assert key == "_pasted"
    assert (episode.sources_dir / "_pasted.txt").exists()


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", ".", "..", "a\\b"])
def test_an_unsafe_key_is_refused_before_any_write(episode, bad):
    with pytest.raises(C.CorpusError):
        C.write_document(episode, "x", url="", key=bad)
    assert not any(episode.sources_dir.iterdir())


def test_unicode_text_round_trips(episode):
    text = "emoji 😀 and 北京 and a \x00 null"
    C.write_document(episode, text, url="https://blog.google/x")
    assert C.document_text(episode, "blog-google") == text


def test_the_document_is_written_before_the_manifest(episode, monkeypatch):
    """A crash between the two must leave an orphan file, not a manifest entry
    pointing at nothing: an orphan is harmless and detectable, a dangling
    reference has to be special-cased everywhere."""
    real = C.atomic_write
    seen = []

    def spy(path, text):
        seen.append(path.name)
        if path.name == C.MANIFEST_NAME:
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(C, "atomic_write", spy)
    with pytest.raises(OSError):
        C.write_document(episode, "body", url="https://blog.google/x")
    assert seen == ["blog-google.txt", C.MANIFEST_NAME]
    assert (episode.sources_dir / "blog-google.txt").exists()


# --- reading ------------------------------------------------------------------


def test_read_manifest_on_an_empty_corpus(episode):
    assert C.read_manifest(episode) == {}


def test_document_text_for_an_unknown_key_is_actionable(episode):
    with pytest.raises(C.CorpusError, match="nope"):
        C.document_text(episode, "nope")


def test_a_corrupt_manifest_is_a_corpus_error(episode):
    C.write_document(episode, "body", url="https://blog.google/x")
    (episode.sources_dir / C.MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    with pytest.raises(C.CorpusError, match=C.MANIFEST_NAME):
        C.read_manifest(episode)


def test_a_non_utf8_document_is_a_corpus_error(episode):
    C.write_document(episode, "body", url="https://blog.google/x")
    (episode.sources_dir / "blog-google.txt").write_bytes(b"caf\xe9")
    with pytest.raises(C.CorpusError, match="UTF-8"):
        C.document_text(episode, "blog-google")


# --- integrity ----------------------------------------------------------------


def test_verify_is_silent_on_a_sound_corpus(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    C.write_document(episode, "two", url="https://venturebeat.com/y")
    assert C.verify(episode) == []


def test_verify_detects_a_modified_document(episode):
    """The whole point: a claim is checked against bytes, so the bytes must be
    provably the ones that were fetched."""
    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / "blog-google.txt").write_text("tampered", encoding="utf-8")
    assert C.verify(episode) == [("modified", "blog-google")]


def test_verify_detects_a_missing_document(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / "blog-google.txt").unlink()
    assert C.verify(episode) == [("missing", "blog-google")]


def test_verify_detects_an_orphan_file(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / "stray.txt").write_text("who wrote this", encoding="utf-8")
    assert C.verify(episode) == [("orphan", "stray.txt")]


def test_verify_reports_every_problem_sorted(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    C.write_document(episode, "two", url="https://venturebeat.com/y")
    (episode.sources_dir / "blog-google.txt").write_text("tampered", encoding="utf-8")
    (episode.sources_dir / "venturebeat-com.txt").unlink()
    (episode.sources_dir / "stray.txt").write_text("x", encoding="utf-8")
    assert C.verify(episode) == [
        ("missing", "venturebeat-com"),
        ("modified", "blog-google"),
        ("orphan", "stray.txt"),
    ]


def test_verify_on_an_empty_corpus(episode):
    assert C.verify(episode) == []
```

- [ ] **Step 2: Run, confirm failure, commit the tests**

```bash
uv run pytest tests/test_video_corpus.py 2>&1 | tail -12
git add tests/test_video_corpus.py
git commit -m "test: specify the verification corpus and its integrity checks"
```

- [ ] **Step 3: Implement**

Create `src/agenticsocial/video/corpus.py`:

```python
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
from .series import _assert_safe_name

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
    return data


def document_text(episode: Episode, key: str) -> str:
    _assert_safe_name(key, "source key", CorpusError)
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
    _assert_safe_name(key, "source key", CorpusError)

    manifest = read_manifest(episode)
    if key in manifest:
        base, n = key, 2
        while f"{base}-{n}" in manifest:
            n += 1
        key = f"{base}-{n}"
        _assert_safe_name(key, "source key", CorpusError)

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
        return [("missing", k) for k in sorted(manifest)]

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
```

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest tests/test_video_corpus.py -v 2>&1 | tail -35
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/corpus.py
git commit -m "feat: add the verification corpus and its integrity check

Spec 4: a claim is checked against bytes on disk, never a memory. Each
document is written with its sha256 recorded in a manifest, so tampering
is detectable and a check made today means the same thing in a year.
Documents are written before the manifest, so a crash leaves a
detectable orphan rather than a dangling reference."
```

- [ ] **Step 5: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `write_document` → write the manifest before the document
2. `write_document` → hash `text` instead of `raw` … then explain whether that
   is even a behaviour change, and if not, say so rather than reporting a kill
3. `write_document` → drop the collision suffix loop
4. `verify` → skip the orphan scan
5. `verify` → compare `bytes` instead of `sha256`
6. `key_for` → drop the `www-` strip
7. `document_text` → drop `_assert_safe_name`

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-1-report.md`:

1. **What I implemented.**
2. **TDD evidence** — RED (piped) and GREEN.
3. **Mutation results**, including your answer on mutant 2.
4. **Files changed**, both commit SHAs.
5. **Vacuity audit** — construct the mutant each test should kill and run it.
   Five implementers before you found vacuous tests of mine this way.
6. **Issues or concerns**, including:
   - `verify` reads every document fully. On a 20-source episode that is fine;
     is there a size at which it is not, and does anything cap what gets written?
   - The collision rule appends `-2`. Two *different* URLs on one host get
     `blog-google` and `blog-google-2`, and nothing in the key says which is
     which. Is that acceptable for a corpus whose job is attribution?
   - `_assert_safe_name` is imported from `series.py` — a private name from a
     module about series. Task 5 of Phase 1 flagged the same smell. Where should
     it actually live?

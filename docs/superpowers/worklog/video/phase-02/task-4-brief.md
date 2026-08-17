# Task 4 Brief: Gate fixes — the verifier must not trust its own manifest

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `cad0230`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

The phase gate returned **merge-after-fixes**. This is those fixes. When it
lands, Phase 2 merges.

## The three blockers, all leader-verified

**F1 — `verify()` trusts its own manifest.** Reproduced:

```
key      : ../../../../../../outside
resolves : /private/tmp/f1b/outside.txt   (outside workspace: True)
documents in sources/: ['_manifest.json']
verify() : SOUND — while hashing a file outside the workspace
```

A corpus containing **no documents at all** is reported sound, because the
verifier hashed a file outside the workspace to say so. `document_text` refuses
the same key. The reviewer's summary: *the corpus's integrity check trusts its
own manifest.* This is the claim Phase 5 rests on.

**F2 — a hostless href tracebacks through the real binary.** Reproduced:
`CorpusError escapes ingest_research: cannot derive a source key: 'not-a-url'
has no host`. `cli.py` catches `IngestError`, not `CorpusError`, so a single
malformed search result aborts the run, records nothing, and leaves a
half-written corpus with no `brief.md`.

**F3 — the no-network guarantee is a convention, not a mechanism.** The reviewer
instrumented a socket sentinel and measured **17 outbound attempts** to
`html.duckduckgo.com`, `blog.google` and `venturebeat.com` across three mutants;
one run took 150s against a 2s baseline. `no_network` is a non-autouse fixture in
one module patching one function, and `test_video_ingest.py` has no guard at all.

## Also in scope — corpus integrity, same family

**F4** a corpus document may be a **symlink**; `verify()` calls that sound, so
the vouched-for bytes are owned outside the corpus.
**F5** `document_text` uses `read_text()`, so a CRLF document is returned with
different bytes than its sha256 covers — the same defect `c47236b` fixed for
beats.
**F8/F9/F10** three lines whose deletion changes behaviour and changes no test:
the sha256 comparison itself (`.get("sha256", digest)` survives), padded bytes
(`sha256(raw.strip())` survives), and `disk_status`'s DRAFT fallback (defaulting
it to **APPROVED** passes all 469 tests).
**F11** `post --resume` honours `status: publishing` with `approved_at: null` —
publishing is self-granting.

**Deferred, recorded, not in this task:** F18 (a post-approval body swap can
publish different content) belongs to Phase 7, which owns the approve gate;
F6/F7/F12–F17 follow.

## The mutants this task must kill

Derive assertions from these before writing them. Assert against **state on
disk**, not a function's own report of itself.

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `verify()` without the manifest-key guard | F1 |
| M2 | `verify()` guards the key but still hashes the resolved path | F1 |
| M3 | `ingest_research` lets `CorpusError` propagate | F2 |
| M4 | `conftest` socket guard removed | F3 |
| M5 | `verify()` follows symlinks | F4 |
| M6 | `document_text` back to `read_text()` | F5 |
| M7 | `.get("sha256", digest)` — a missing hash compares equal to itself | F8 |
| M8 | `sha256(raw.strip())` | F9 |
| M9 | `disk_status` fallback → `APPROVED` | F10 |
| M10 | `post --resume` ignores `approved_at` | F11 |

## Ground rules

- **Four commits:** conftest (F3), corpus integrity (F1/F4/F5/F8/F9), ingest
  (F2), gate (F10/F11). Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 20 defects across four phases.
- Do not add dependencies. Never stage anything under `docs/`.
- **Report the mutation score as the primary metric.**

---

- [ ] **Step 1: `tests/conftest.py` — make isolation a mechanism (F3)**

An autouse, session-wide socket guard. A suite whose isolation depends on the
code being correct is not isolated.

```python
"""Test-wide guarantees that do not depend on the code under test being correct.

The suite's no-network property was previously a convention: one non-autouse
fixture in one module patching one function. A phase-gate review measured 17
outbound attempts across three mutants, one run taking 150s against a 2s
baseline. Isolation has to be a mechanism.
"""
import socket

import pytest


class NetworkUseInTest(Exception):
    pass


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def blocked(*a, **kw):
        raise NetworkUseInTest(
            "a test tried to open a socket. Tests must never reach the network — "
            "inject or patch the fetcher instead."
        )

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
```

Then **delete the `no_network` fixture in `tests/test_video_ingest.py`** and any
per-test use of it — it is superseded and leaving both invites the belief that
the weaker one is doing the work.

```bash
uv run pytest 2>&1 | tail -5
git add tests/conftest.py tests/test_video_ingest.py
git commit -m "test: block sockets suite-wide instead of trusting one fixture

The no-network property was a convention: one non-autouse fixture in one
module patching one function. A gate review measured 17 outbound attempts
across three mutants, one run taking 150s against a 2s baseline."
```

- [ ] **Step 2: corpus integrity (F1, F4, F5, F8, F9)**

Tests first. Each with a `precondition:` line.

```python
def test_verify_refuses_a_manifest_key_that_escapes_the_corpus(episode):
    """precondition: sources/ contains no documents at all. F1 — verify()
    reported SOUND while hashing a file outside the workspace."""
    import hashlib, json

    outside = episode.dir.parent.parent.parent / "outside.txt"
    outside.write_text("bytes nobody vouched for", encoding="utf-8")
    key = "/".join([".."] * 6) + "/outside"
    (episode.sources_dir / C.MANIFEST_NAME).write_text(
        json.dumps({key: {"url": "", "title": "", "fetched_at": "",
                          "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                          "bytes": outside.stat().st_size}}),
        encoding="utf-8",
    )
    problems = C.verify(episode)
    assert problems, "a traversing manifest key must never verify as sound"
    assert problems[0][0] == "unsafe"


def test_verify_flags_a_symlinked_document(episode, tmp_path):
    """precondition: blog-google is a real file. F4 — vouched-for bytes must be
    owned by the corpus, not pointed at from it."""
    C.write_document(episode, "one", url="https://blog.google/x")
    real = episode.sources_dir / "blog-google.txt"
    outside = tmp_path / "elsewhere.txt"
    outside.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    real.unlink()
    real.symlink_to(outside)
    assert ("symlink", "blog-google") in C.verify(episode)


def test_document_text_returns_the_bytes_the_hash_covers(episode):
    """precondition: the document was written with CRLF. F5 — read_text applies
    universal newline translation, so the returned text is not what sha256
    covers. Same defect c47236b fixed for beats."""
    C.write_document(episode, "x", url="https://blog.google/x")
    (episode.sources_dir / "blog-google.txt").write_bytes(b"line one\r\nline two\r\n")
    assert C.document_text(episode, "blog-google") == "line one\r\nline two\r\n"


def test_a_manifest_entry_with_no_sha256_is_not_sound(episode):
    """precondition: the document is intact. F8 — `.get("sha256", digest)`
    compares a missing hash to itself and passes."""
    import json

    C.write_document(episode, "one", url="https://blog.google/x")
    m = json.loads((episode.sources_dir / C.MANIFEST_NAME).read_text(encoding="utf-8"))
    del m["blog-google"]["sha256"]
    (episode.sources_dir / C.MANIFEST_NAME).write_text(json.dumps(m), encoding="utf-8")
    assert C.verify(episode) == [("modified", "blog-google")]


def test_padding_a_document_is_a_modification(episode):
    """precondition: the document has no surrounding whitespace. F9 —
    sha256(raw.strip()) survives every existing test."""
    C.write_document(episode, "one", url="https://blog.google/x")
    p = episode.sources_dir / "blog-google.txt"
    p.write_bytes(b"  " + p.read_bytes() + b"\n")
    assert C.verify(episode) == [("modified", "blog-google")]
```

Then in `corpus.py`:

```python
def verify(episode: Episode) -> list[tuple[str, str]]:
    manifest = read_manifest(episode)
    problems: list[tuple[str, str]] = []
    if not episode.sources_dir.is_dir():
        return problems

    for key in sorted(manifest):
        try:
            assert_safe_name(key, "source key", CorpusError)
        except CorpusError:
            # A manifest that names a path outside the corpus cannot be used to
            # vouch for anything. verify() must not resolve it -- doing so
            # reported a corpus SOUND while hashing a file outside the
            # workspace entirely.
            problems.append(("unsafe", key))
            continue
        path = episode.sources_dir / (key + SUFFIX)
        if path.is_symlink():
            problems.append(("symlink", key))
            continue
        if not path.is_file():
            problems.append(("missing", key))
            continue
        recorded = manifest[key].get("sha256")
        if recorded is None or hashlib.sha256(path.read_bytes()).hexdigest() != recorded:
            problems.append(("modified", key))
    ...
```

and `document_text` reads bytes, decoding without newline translation:

```python
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorpusError(f"{path}: corpus documents must be UTF-8 — {e}")
    except OSError as e:
        raise CorpusError(f"{path}: cannot read source — {e}")
```

- [ ] **Step 3: ingest records what it cannot key (F2)**

```python
def test_a_hostless_result_is_recorded_not_raised(episode):
    """precondition: no failures recorded. F2 — one malformed search result
    aborted the run through the real binary, leaving a half-written corpus and
    no brief.md."""
    res = I.ingest_research(
        episode, "q",
        search=fake_search([{"title": "t", "href": "not-a-url", "body": ""},
                            RESULTS[0]]),
        extract=fake_extract({"https://blog.google/a": "article a"}),
    )
    assert res.keys == ["blog-google"]
    assert any("not-a-url" in u for u, _ in res.failures)
```

In `ingest_research`, wrap the write:

```python
        try:
            key = _write(episode, text, url=url, title=title)
        except C.CorpusError as e:
            failures.append((url, str(e)))
            continue
```

- [ ] **Step 4: the gate (F10, F11)**

```python
def test_disk_status_defaults_to_draft_not_something_permissive(tmp_path):
    """precondition: the file has no status key. F10 — defaulting to APPROVED
    passes all 469 tests."""
    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("x")
    v = ws.create_variant(src, "x", body="hi")
    v.path.write_text("---\nplatform: x\n---\nhi", encoding="utf-8")
    assert ws.disk_status(v) is Status.DRAFT
```

In `cli.py::post`, require that a resumable `publishing` was actually approved:

```python
    if ws.disk_status(v) is Status.PUBLISHING and not v.meta.get("approved_at"):
        raise _fail(
            f"{src.id} is marked publishing but was never approved — "
            "publishing cannot grant itself. Reset status to in_review and approve it."
        )
```

Place it **before** the existing interrupted/resume branch, and add a test that a
legitimately approved-then-publishing variant still resumes.

- [ ] **Step 5: Kill all ten mutants**, then your own sweep. Report the score.

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-4-report.md`:

1. **What I changed**, per finding.
2. **TDD evidence** and the **mutation score**.
3. **All ten mutant results**, plus your own sweep.
4. **Files changed**, all commit SHAs.
5. **Issues or concerns**, including:
   - After the conftest guard: does **any** mutant still reach a socket? Measure,
     do not reason.
   - Does `verify()` now refuse everything it should, or is there a manifest that
     still vouches for bytes the corpus does not own?
   - Anything F11 breaks for a legitimate resume.

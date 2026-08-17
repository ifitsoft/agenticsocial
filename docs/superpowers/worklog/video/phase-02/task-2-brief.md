# Task 2 Brief: Ingestion — fill the corpus, honestly

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `742f8a5`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

**First brief written under D-064.** Mutants are specified *before* assertions,
every rule carries its negative half, and every test states a precondition. If a
test in Step 2 passes on arrival, that is a transcription and I want it counted
and reported — `passed on arrival` is the transcription rate, not a curiosity.

## What this builds

`ingest.py`: turn a research query, a pasted digest, or an existing agsoc source
into corpus documents plus a human-readable `brief.md`.

**Partial failure is the normal case**, not an edge case. Three sources fetch and
one 403s on an ordinary day. The corpus must contain the three, and the record
must name the one.

## The rules, each with its negative half

These are the contract. Assertions are derived from the mutants below, not from
the implementation.

- **R1** Every result whose extraction succeeds is written to the corpus.
  **Negative:** a result whose extraction fails or returns empty is **not**
  written, and is recorded as a failure.
- **R2** A failure never aborts the run. **Negative:** it is also never silent —
  it appears in the returned result *and* in `brief.md`.
- **R3** Ingesting a URL already in the manifest **reuses its existing key**.
  **Negative:** a *different* URL on the same host still gets a fresh `-2` key.
- **R4** Pasted text is written under the key `_pasted` with an empty `url`.
  **Negative:** it is **not** keyed by host derivation, and a second paste does
  not overwrite the first.
- **R5** `brief.md` is written last, after every document. **Negative:** if no
  document was written at all, `brief.md` is still written and says so.
- **R6** Nothing in this module fetches directly. **Negative:** `search` and
  `extract` are injected, so a test that reaches the network is a bug in the
  test.

## The mutants this task must kill

Derive your assertions from these. **Write them down before the tests.**

| # | Weaker implementation | What must notice |
|---|---|---|
| M1 | a failed `extract` propagates instead of being recorded | R1/R2 |
| M2 | failures recorded, but successful documents not written | R1 |
| M3 | `write_document` called without the manifest URL lookup | R3 |
| M4 | URL lookup matches on *host* rather than exact URL | R3 negative |
| M5 | paste keyed by `key_for(url)` instead of `_pasted` | R4 |
| M6 | `extract` returning `None` treated as success (empty document) | R1 negative |
| M7 | `brief.md` written before the documents | R5 |
| M8 | `brief.md` omits the failure list | R2 negative |
| M9 | empty search results produce a silent empty corpus | R5 negative |

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 18 defects across four phases.
- **No network anywhere.** `search` and `extract` are parameters with defaults;
  tests pass fakes. A test that touches the network is a defect.
- Do not add dependencies. `ddgs` and `trafilatura` are already declared and are
  only referenced through the injected defaults.
- Never stage anything under `docs/`. Report observed counts and the
  **passed-on-arrival count**.

## Files

- Create: `src/agenticsocial/video/ingest.py`
- Test: `tests/test_video_ingest.py`

## Interfaces

```python
class IngestError(Exception): ...

@dataclass(frozen=True)
class IngestResult:
    keys: list[str]                     # corpus keys written, in order
    failures: list[tuple[str, str]]     # (url, reason)
    brief_path: Path

def ingest_research(episode, query, *, max_results=8, search=None, extract=None) -> IngestResult
def ingest_paste(episode, text, *, title="pasted digest") -> IngestResult
def ingest_source(episode, source) -> IngestResult   # an agsoc Source
```

`search`/`extract` default to `research.search` / `research.extract`. Frozen
result, per D-062: it is a snapshot of what happened.

---

- [ ] **Step 1: Write the tests**

Create `tests/test_video_ingest.py`. Each test carries a `precondition:` line —
what the fixture must **not** already be in — because both vacuous tests found in
this phase failed for exactly that reason.

```python
import pytest

from agenticsocial.video import corpus as C
from agenticsocial.video import ingest as I
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


def fake_search(results):
    return lambda q, max_results=8: results[:max_results]


def fake_extract(mapping):
    """mapping: url -> text, or url -> Exception to raise, or absent -> None."""
    def _extract(url):
        v = mapping.get(url)
        if isinstance(v, Exception):
            raise v
        return v
    return _extract


RESULTS = [
    {"title": "Gemini ships", "href": "https://blog.google/a", "body": "snippet a"},
    {"title": "Analysis", "href": "https://venturebeat.com/b", "body": "snippet b"},
]


# --- R1/R2: partial failure is the normal case --------------------------------


def test_a_failed_extraction_does_not_lose_the_others(episode):
    """precondition: the corpus is empty. Kills M1 (failure propagates) and
    M2 (successes not written)."""
    res = I.ingest_research(
        episode, "gemini",
        search=fake_search(RESULTS),
        extract=fake_extract({
            "https://blog.google/a": "full article a",
            "https://venturebeat.com/b": RuntimeError("403 Forbidden"),
        }),
    )
    assert res.keys == ["blog-google"]
    assert C.document_text(episode, "blog-google") == "full article a"
    assert [u for u, _ in res.failures] == ["https://venturebeat.com/b"]


def test_a_failure_names_its_reason(episode):
    """precondition: no prior failures recorded. Kills M2's silent variant."""
    res = I.ingest_research(
        episode, "gemini",
        search=fake_search(RESULTS[1:]),
        extract=fake_extract({"https://venturebeat.com/b": RuntimeError("403 Forbidden")}),
    )
    assert "403" in res.failures[0][1]


def test_an_empty_extraction_is_a_failure_not_an_empty_document(episode):
    """R1 negative. precondition: corpus empty. Kills M6 — `extract` returning
    None must not write a document with no text, which would then be cited as a
    source containing nothing."""
    res = I.ingest_research(
        episode, "gemini",
        search=fake_search(RESULTS[:1]),
        extract=fake_extract({}),          # returns None
    )
    assert res.keys == []
    assert not (episode.sources_dir / "blog-google.txt").exists()
    assert res.failures and res.failures[0][0] == "https://blog.google/a"


def test_the_brief_names_what_failed(episode):
    """R2 negative. precondition: brief.md does not exist. Kills M8."""
    res = I.ingest_research(
        episode, "gemini",
        search=fake_search(RESULTS),
        extract=fake_extract({
            "https://blog.google/a": "full article a",
            "https://venturebeat.com/b": RuntimeError("403 Forbidden"),
        }),
    )
    brief = res.brief_path.read_text(encoding="utf-8")
    assert "venturebeat.com/b" in brief
    assert "403" in brief


# --- R3: a rebuilt corpus must not re-point a citation ------------------------


def test_the_same_url_twice_reuses_its_key(episode):
    """R3. precondition: blog-google already in the manifest from the first
    call. Kills M3 — without the lookup the second ingest writes
    `blog-google-2`, and any claim citing `blog-google-2` from a previous build
    now points at the OTHER article. That is the one failure here that yields a
    wrong fact-check rather than a loud one."""
    args = dict(
        search=fake_search(RESULTS[:1]),
        extract=fake_extract({"https://blog.google/a": "full article a"}),
    )
    first = I.ingest_research(episode, "gemini", **args)
    second = I.ingest_research(episode, "gemini", **args)
    assert first.keys == second.keys == ["blog-google"]
    assert set(C.read_manifest(episode)) == {"blog-google"}


def test_a_different_url_on_the_same_host_still_gets_a_new_key(episode):
    """R3 NEGATIVE. precondition: blog-google exists. Kills M4 — matching on
    host instead of exact URL would collapse two distinct articles into one."""
    I.ingest_research(
        episode, "gemini",
        search=fake_search([RESULTS[0]]),
        extract=fake_extract({"https://blog.google/a": "article a"}),
    )
    res = I.ingest_research(
        episode, "gemini",
        search=fake_search([{"title": "Other", "href": "https://blog.google/OTHER", "body": ""}]),
        extract=fake_extract({"https://blog.google/OTHER": "article other"}),
    )
    assert res.keys == ["blog-google-2"]
    assert C.document_text(episode, "blog-google") == "article a"
    assert C.document_text(episode, "blog-google-2") == "article other"


# --- R4: pasted text is ground truth ------------------------------------------


def test_paste_is_written_under_the_pasted_key(episode):
    """R4. precondition: corpus empty. Kills M5 — a paste has no URL to derive
    a host from, and D-041 makes it ground truth in its own right."""
    res = I.ingest_paste(episode, "pasted digest text")
    assert res.keys == ["_pasted"]
    assert C.document_text(episode, "_pasted") == "pasted digest text"
    assert C.read_manifest(episode)["_pasted"]["url"] == ""


def test_a_second_paste_does_not_overwrite_the_first(episode):
    """R4 NEGATIVE. precondition: _pasted already exists."""
    I.ingest_paste(episode, "first")
    res = I.ingest_paste(episode, "second")
    assert res.keys == ["_pasted-2"]
    assert C.document_text(episode, "_pasted") == "first"


# --- R5: the brief is written last, and always -------------------------------


def test_documents_are_written_before_the_brief(episode, monkeypatch):
    """R5. precondition: nothing written yet. Kills M7 — a brief that exists
    while its sources do not is a citation to nothing."""
    order = []
    real = I.atomic_write

    def spy(path, text):
        order.append(path.name)
        return real(path, text)

    monkeypatch.setattr(I, "atomic_write", spy)
    monkeypatch.setattr(C, "atomic_write", spy)
    I.ingest_research(
        episode, "gemini",
        search=fake_search(RESULTS[:1]),
        extract=fake_extract({"https://blog.google/a": "a"}),
    )
    assert order[-1] == "brief.md"
    assert "blog-google.txt" in order


def test_an_empty_search_still_writes_a_brief_that_says_so(episode):
    """R5 NEGATIVE. precondition: brief.md does not exist. Kills M9 — a silent
    empty corpus looks identical to one nobody ingested."""
    res = I.ingest_research(episode, "gemini", search=fake_search([]), extract=fake_extract({}))
    assert res.keys == []
    assert res.brief_path.exists()
    assert "no sources" in res.brief_path.read_text(encoding="utf-8").lower()


def test_the_brief_records_the_query(episode):
    """precondition: brief.md absent. A brief that does not say what was asked
    cannot be audited later."""
    res = I.ingest_research(
        episode, "gemini pricing",
        search=fake_search(RESULTS[:1]),
        extract=fake_extract({"https://blog.google/a": "a"}),
    )
    assert "gemini pricing" in res.brief_path.read_text(encoding="utf-8")


# --- from an existing agsoc source --------------------------------------------


def test_ingest_source_uses_the_source_body(ws, episode):
    """precondition: corpus empty. The text pipeline's sources are a legitimate
    input to a video (spec 11, --from-source)."""
    src = ws.create_source("Kill staging", body="the original reasoning")
    res = I.ingest_source(episode, src)
    assert res.keys and C.document_text(episode, res.keys[0]) == "the original reasoning"


def test_ingest_source_with_an_empty_body_is_a_failure(ws, episode):
    """NEGATIVE. precondition: corpus empty. An empty source must not become an
    empty document that a claim can later cite."""
    src = ws.create_source("Empty", body="")
    res = I.ingest_source(episode, src)
    assert res.keys == []
    assert res.failures


# --- R6: this module does not fetch -------------------------------------------


def test_defaults_are_the_research_module(episode):
    """R6. Not behavioural — it pins that the seam exists, so a future edit
    cannot inline a fetch and make the suite reach the network."""
    import inspect

    sig = inspect.signature(I.ingest_research)
    assert sig.parameters["search"].default is None
    assert sig.parameters["extract"].default is None
```

- [ ] **Step 2: Run, record the passed-on-arrival count, commit**

```bash
uv run pytest tests/test_video_ingest.py 2>&1 | tail -12
git add tests/test_video_ingest.py
git commit -m "test: specify ingestion, partial failure, and URL-stable keys"
```

Every test should fail at collection (`ingest` does not exist). **If any passes,
report it** — that would mean it asserts nothing about this module.

- [ ] **Step 3: Implement**

Create `src/agenticsocial/video/ingest.py`:

```python
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
        C.write_document(episode, text, url=url, title=title, key=existing)
        return existing
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
    if written:
        lines += ["## Sources in the corpus", ""]
        for key, url, title in written:
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
        key = _write(episode, text, url=url, title=title)
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
    key = C.write_document(
        episode, body, url=source.origin_url or "", title=source.title, key=f"src-{source.id}"
    )
    return IngestResult(
        [key], [], _brief(episode, "Brief", source.id, [(key, source.origin_url or "", source.title)], [])
    )
```

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest tests/test_video_ingest.py -v 2>&1 | tail -30
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/ingest.py
git commit -m "feat: fill the corpus from research, a paste, or an existing source

Partial failure is the normal case: a source that 403s is recorded, not
raised, and the others still land. A URL already in the manifest reuses
its key -- re-deriving on a rebuild would hand blog-google-2 to whichever
article was fetched second and silently re-point every citation."
```

- [ ] **Step 5: Kill the nine mutants**

Apply each from the table above, run the full suite, `git checkout` between.
Report any survivor. Then run your own sweep for anything the nine miss.

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-2-report.md`:

1. **What I implemented.**
2. **TDD evidence** — RED (piped) and GREEN, plus the **passed-on-arrival count**.
3. **Mutation results** for all nine, plus your own sweep.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - `ingest_source` keys as `src-<id>`, which is not host-derived and can exceed
     what a filename should be. Is that right?
   - Every entry point writes `brief.md`, so a second ingest overwrites the
     first's brief while the corpus accumulates. Right, or a data-loss bug?
   - **Did this brief's tests read as derived-from-mutants, or as transcriptions
     of an implementation?** You are the first to see a brief written under
     D-064; tell me whether it worked.

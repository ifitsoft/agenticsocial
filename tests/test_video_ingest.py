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

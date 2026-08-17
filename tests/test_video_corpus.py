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


def test_verify_detects_a_same_length_modification(episode):
    """The realistic tamper is changing a figure, not changing a length. The
    previous version of this test replaced 3 bytes with 8, so a verifier
    comparing only `bytes` passed it — blind to exactly what it named."""
    C.write_document(episode, "Anthropic raised $100M", url="https://blog.google/x")
    (episode.sources_dir / "blog-google.txt").write_text(
        "Anthropic raised $900M", encoding="utf-8"
    )
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


@pytest.mark.parametrize(
    "bad", ["../../../series", "../secret", "a/b", "..", ".", "", "a\\b"]
)
def test_document_text_refuses_a_traversing_key(episode, bad):
    """Each key must be refused as UNSAFE, not merely as absent. The previous
    version passed with the guard removed: every key raised CorpusError anyway
    because no such file existed."""
    with pytest.raises(C.CorpusError, match="unsafe"):
        C.document_text(episode, bad)


def test_document_text_cannot_reach_outside_the_corpus(episode):
    """Concrete: plant a file where a traversal would land and prove it stays
    unreachable."""
    series_dir = episode.dir.parent.parent
    (series_dir / "series.txt").write_text("SECRET", encoding="utf-8")
    with pytest.raises(C.CorpusError):
        C.document_text(episode, "../../../series")


def test_verify_is_silent_when_the_corpus_dir_does_not_exist(episode):
    """The manifest lives inside sources_dir, so if the directory is gone there
    is nothing recorded either. The guard exists to stop iterdir() raising, not
    to report losses — the previous version of this test recreated the directory
    and never entered the branch at all."""
    import shutil

    C.write_document(episode, "one", url="https://blog.google/x")
    shutil.rmtree(episode.sources_dir)
    assert C.verify(episode) == []


# --- the RULES, not just the outcomes -----------------------------------------
# Task 1b: 12 of 14 mutants survived because tests pinned example outputs while
# leaving the rule that produced them free to change.


def test_only_a_leading_www_is_stripped(episode):
    """`www` inside a host is part of the name. Pinning two happy examples left
    `"www" in key` passing."""
    assert C.key_for("https://www.reuters.com/x") == "reuters-com"
    assert C.key_for("https://blog.wwwfoo.com/x") == "blog-wwwfoo-com"
    assert C.key_for("https://wwwfoo.com/x") == "wwwfoo-com"


def test_the_collision_suffix_format_is_stable(episode):
    """Claims cite these keys. `a != b` left the format entirely unspecified."""
    C.write_document(episode, "one", url="https://blog.google/x")
    assert C.write_document(episode, "two", url="https://blog.google/y") == "blog-google-2"
    assert C.write_document(episode, "three", url="https://blog.google/z") == "blog-google-3"


def test_an_explicit_empty_key_is_refused_not_replaced(episode):
    """`key=""` must not silently fall back to the host key. Invisible before
    because the only test passing an explicit key also passed url=""."""
    with pytest.raises(C.CorpusError):
        C.write_document(episode, "x", url="https://blog.google/x", key="")


def test_write_creates_the_sources_dir_when_absent(episode):
    """Every fixture pre-created it, so dropping the mkdir broke nothing."""
    import shutil

    shutil.rmtree(episode.sources_dir)
    C.write_document(episode, "one", url="https://blog.google/x")
    assert (episode.sources_dir / "blog-google.txt").is_file()


def test_fetched_at_is_a_plausible_timestamp(episode):
    """Presence was asserted; plausibility was not — in the module whose reason
    to exist is provenance."""
    from datetime import datetime

    C.write_document(episode, "one", url="https://blog.google/x")
    stamp = C.read_manifest(episode)["blog-google"]["fetched_at"]
    assert datetime.fromisoformat(stamp).year >= 2020


def test_an_explicit_fetched_at_is_recorded_verbatim(episode):
    C.write_document(
        episode, "one", url="https://blog.google/x", fetched_at="2026-08-14T09:00:00+01:00"
    )
    assert C.read_manifest(episode)["blog-google"]["fetched_at"] == (
        "2026-08-14T09:00:00+01:00"
    )


def test_a_subdirectory_is_not_an_orphan(episode):
    """Dropping the is_file() skip made any directory read as a stray source."""
    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / "cache").mkdir()
    assert C.verify(episode) == []


def test_a_manifest_whose_entries_are_not_objects_is_a_corpus_error(episode):
    """`entry["url"]` would otherwise leak TypeError past the CorpusError
    contract that every caller catches."""
    import json

    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / C.MANIFEST_NAME).write_text(
        json.dumps({"blog-google": "not an object"}), encoding="utf-8"
    )
    with pytest.raises(C.CorpusError):
        C.read_manifest(episode)


def test_a_manifest_that_is_a_json_array_is_a_corpus_error(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / C.MANIFEST_NAME).write_text("[]", encoding="utf-8")
    with pytest.raises(C.CorpusError):
        C.read_manifest(episode)


# --- the verifier must not trust its own manifest (F1, F4, F5, F8, F9) --------


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

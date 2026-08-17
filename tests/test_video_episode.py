import pytest
import yaml

from agenticsocial.models import Status, TransitionError
from agenticsocial.video.episode import (
    create_episode,
    episode_ids,
    list_episodes,
    load_episode,
    resolve_episode,
    set_status,
)
from agenticsocial.video.models import EpisodeError
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


def test_create_makes_the_full_layout(series):
    ep = create_episode(series, "2026-08-14")
    assert ep.dir == series.episodes_dir / "2026-08-14"
    assert ep.script_path.exists()
    assert ep.sources_dir.is_dir()
    assert ep.out_dir.is_dir()
    assert (ep.dir / "probe").is_dir()
    assert ep.status is Status.DRAFT
    assert ep.series_slug == "the-brief"


def test_created_script_is_two_yaml_documents(series):
    ep = create_episode(series, "2026-08-14")
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert len(docs) == 2
    assert docs[0]["episode"] == "2026-08-14"
    assert docs[0]["series"] == "the-brief"
    assert docs[0]["status"] == "draft"
    assert docs[1] == {"beats": []}


def test_create_is_not_destructive(series):
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError, match="already exists"):
        create_episode(series, "2026-08-14")


def test_load_returns_status_from_disk(series):
    create_episode(series, "2026-08-14")
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_load_missing_episode_is_actionable(series):
    with pytest.raises(EpisodeError, match="agsoc video new"):
        load_episode(series, "2026-01-01")


def test_invalid_status_names_the_file_and_valid_values(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: banana\n---\nbeats: []\n",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError) as excinfo:
        load_episode(series, "2026-08-14")
    assert "banana" in str(excinfo.value)
    assert "rendering" in str(excinfo.value)


def test_load_tolerates_a_single_document_script(series):
    """A hand-edited script that lost its second document must not crash."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "episode: 2026-08-14\nseries: the-brief\nstatus: draft\n", encoding="utf-8"
    )
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_load_tolerates_an_empty_script(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text("", encoding="utf-8")
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_resolve_exact_id_wins(series):
    create_episode(series, "2026-08-14")
    assert resolve_episode(series, "2026-08-14").id == "2026-08-14"


def test_resolve_by_unique_substring(series):
    create_episode(series, "2026-08-14")
    assert resolve_episode(series, "08-14").id == "2026-08-14"


def test_resolve_ambiguous_lists_candidates(series):
    create_episode(series, "2026-08-14")
    create_episode(series, "2026-08-15")
    with pytest.raises(EpisodeError) as excinfo:
        resolve_episode(series, "2026-08")
    assert "2026-08-14" in str(excinfo.value)
    assert "2026-08-15" in str(excinfo.value)


def test_resolve_no_match_is_actionable(series):
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError, match="agsoc video list"):
        resolve_episode(series, "1999")


def test_resolve_a_healthy_episode_despite_a_corrupt_neighbour(series):
    """D-018: matching runs over ids, so only the resolved episode is loaded."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    assert resolve_episode(series, "2026-08-14").id == "2026-08-14"


def test_resolving_the_corrupt_episode_itself_still_raises(series):
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    with pytest.raises(EpisodeError, match="banana"):
        resolve_episode(series, "2026-08-15")


def test_list_episodes_is_sorted(series):
    create_episode(series, "2026-08-15")
    create_episode(series, "2026-08-14")
    assert [e.id for e in list_episodes(series)] == ["2026-08-14", "2026-08-15"]


def test_list_episodes_when_none(series):
    assert list_episodes(series) == []


def test_list_episodes_skips_dirs_without_a_script(series):
    create_episode(series, "2026-08-14")
    (series.episodes_dir / "junk").mkdir()
    assert [e.id for e in list_episodes(series)] == ["2026-08-14"]


def test_episode_ids_survives_a_corrupt_episode(series):
    """D-018: enumeration must not die over one bad member. `agsoc video list`
    is the diagnostic command — it runs precisely when something is broken."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    assert episode_ids(series) == ["2026-08-14", "2026-08-15"]


def test_list_episodes_is_strict_about_a_corrupt_episode(series):
    """The strict counterpart: loading everything fails loudly. The CLI uses
    episode_ids + per-episode load instead."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    with pytest.raises(EpisodeError, match="banana"):
        list_episodes(series)


def test_episode_ids_on_empty_series(series):
    assert episode_ids(series) == []


def test_set_status_persists_and_preserves_beats(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    assert load_episode(series, "2026-08-14").status is Status.IN_REVIEW
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert docs[1] == {"beats": []}


def test_set_status_updates_the_in_memory_episode(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    assert ep.status is Status.IN_REVIEW


def test_set_status_does_not_lose_beats_written_by_a_later_phase(series):
    """Phase 3 writes real beats into document 2. A status change must not eat them."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n"
        "---\nbeats:\n- type: statement\n  text: hello\n",
        encoding="utf-8",
    )
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert docs[1]["beats"] == [{"type": "statement", "text": "hello"}]


def test_set_status_enforces_the_video_table(series):
    ep = create_episode(series, "2026-08-14")
    with pytest.raises(TransitionError):
        set_status(ep, Status.RENDERING)


def test_set_status_allows_the_approved_render_path(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    set_status(ep, Status.APPROVED)
    set_status(ep, Status.RENDERING)
    assert load_episode(series, "2026-08-14").status is Status.RENDERING


def test_a_rejected_transition_does_not_touch_the_file(series):
    ep = create_episode(series, "2026-08-14")
    before = ep.script_path.read_text(encoding="utf-8")
    with pytest.raises(TransitionError):
        set_status(ep, Status.RENDERING)
    assert ep.script_path.read_text(encoding="utf-8") == before
    assert ep.status is Status.DRAFT


# --- document 2 is never parsed, never rewritten, never lost -------------------
# Task 3 substituted {"beats": []} for any document 2 that was not a dict, then
# wrote the substitute back on the next status change. Reproduced with a bare
# YAML sequence, which is a natural way to write beats.


def _write_script(ep, text):
    ep.script_path.write_text(text, encoding="utf-8")


def test_set_status_preserves_a_sequence_beats_document_verbatim(series):
    ep = create_episode(series, "2026-08-14")
    body = "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n---\n- type: statement\n  text: hello\n"
    _write_script(ep, body)
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    after = ep.script_path.read_text(encoding="utf-8")
    assert "- type: statement" in after
    assert "beats: []" not in after


def test_set_status_preserves_comments_and_formatting_in_beats(series):
    """The storyboard skill writes deliberate formatting. Approving must not
    reflow it, and script_sha256 drift must not fire on churn we caused."""
    ep = create_episode(series, "2026-08-14")
    beats = (
        "beats:\n"
        "  # the cold open carries the whole episode\n"
        "  - type: statement\n"
        '    text: "Google shipped its main agentic model."\n'
        "\n"
        "  - type:  kpis          # deliberate double space\n"
        "    hold:  4.6\n"
    )
    _write_script(
        ep, f"---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n---\n{beats}"
    )
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    after = ep.script_path.read_text(encoding="utf-8")
    assert after.endswith(beats)


def test_set_status_preserves_a_third_document(series):
    ep = create_episode(series, "2026-08-14")
    _write_script(
        ep,
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n"
        "---\nbeats: []\n---\nnotes: kept\n",
    )
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    assert "notes: kept" in ep.script_path.read_text(encoding="utf-8")


def test_beats_bytes_are_identical_across_a_status_change(series):
    ep = create_episode(series, "2026-08-14")
    beats = "beats:\n  - type: statement\n    text: unchanged\n"
    _write_script(
        ep, f"---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n---\n{beats}"
    )
    before = ep.script_path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    set_status(reloaded, Status.APPROVED)
    after = ep.script_path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    assert after == before


# --- a beats syntax error must not stop you reading the status -----------------


def test_status_is_readable_even_when_beats_is_unparseable(series):
    """D-018 one level down: the diagnostic path must survive broken beats."""
    ep = create_episode(series, "2026-08-14")
    _write_script(
        ep,
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: in_review\n"
        "---\nbeats: [unclosed\n  : : :\n",
    )
    assert load_episode(series, "2026-08-14").status is Status.IN_REVIEW


# --- unparseable METADATA raises EpisodeError, never a YAML exception ----------


@pytest.mark.parametrize(
    "body",
    [
        "---\n: : :\n  - broken\n---\nbeats: []\n",
        "---\nepisode: [unclosed\n---\nbeats: []\n",
        "\x00\x01 not yaml at all\n",
        '---\n"unterminated\n---\nbeats: []\n',
    ],
)
def test_unparseable_metadata_raises_episode_error(series, body):
    ep = create_episode(series, "2026-08-14")
    _write_script(ep, body)
    with pytest.raises(EpisodeError):
        load_episode(series, "2026-08-14")


def test_non_mapping_metadata_raises_episode_error(series):
    ep = create_episode(series, "2026-08-14")
    _write_script(ep, "---\n- just\n- a list\n---\nbeats: []\n")
    with pytest.raises(EpisodeError, match="metadata"):
        load_episode(series, "2026-08-14")


def test_episode_ids_survives_an_unparseable_script(series):
    """The enumerator must never parse anything. This is the D-018 guarantee
    Task 4's `except EpisodeError` will rely on."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    _write_script(bad, "\x00\x01 : : not yaml [\n")
    assert episode_ids(series) == ["2026-08-14", "2026-08-15"]


def test_resolve_a_healthy_episode_despite_an_unparseable_neighbour(series):
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    _write_script(bad, "\x00\x01 : : not yaml [\n")
    assert resolve_episode(series, "2026-08-14").id == "2026-08-14"


# --- create_episode must not leave a half-built directory ----------------------


def test_failed_create_leaves_no_partial_directory(series, monkeypatch):
    import agenticsocial.video.episode as ep_mod

    def explode(path, text):
        raise OSError("disk full")

    monkeypatch.setattr(ep_mod, "atomic_write", explode)
    with pytest.raises(OSError):
        create_episode(series, "doomed")
    assert not (series.episodes_dir / "doomed").exists()
    monkeypatch.undo()
    create_episode(series, "doomed")  # retry must work


def test_episode_ids_ignores_a_directory_where_the_script_should_be(series):
    create_episode(series, "2026-08-14")
    d = series.episodes_dir / "weird"
    (d / "script.yaml").mkdir(parents=True)
    assert episode_ids(series) == ["2026-08-14"]


# --- byte-level preservation ---------------------------------------------------
# The existing preservation tests use write_text/read_text, which apply universal
# newline translation on BOTH sides — so they pin content, not bytes, and a CRLF
# script had every byte rewritten while they stayed green. These use bytes.


def _write_bytes(ep, meta_lines, beats, nl):
    body = nl.join(meta_lines).encode() + nl.encode()
    ep.script_path.write_bytes(
        b"---" + nl.encode() + body + b"---" + nl.encode() + beats
    )


def _beats_bytes(ep, nl):
    raw = ep.script_path.read_bytes()
    return raw.split(b"---" + nl.encode(), 2)[-1]


META = ["episode: e", "series: the-brief", "status: draft"]


@pytest.mark.parametrize("nl", ["\n", "\r\n", "\r"])
def test_beats_bytes_survive_a_status_change(series, nl):
    ep = create_episode(series, "ep")
    beats = nl.join(["beats:", "  # a comment", "  - type: statement", ""]).encode()
    _write_bytes(ep, META, beats, nl)
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert _beats_bytes(ep, nl) == beats


@pytest.mark.parametrize("nl", ["\n", "\r\n"])
def test_beats_bytes_survive_repeated_status_changes(series, nl):
    """script_sha256 must not drift across a draft -> review -> approve run."""
    ep = create_episode(series, "ep")
    beats = nl.join(["beats:", "  - type: kpis", "    hold:  4.6", ""]).encode()
    _write_bytes(ep, META, beats, nl)
    for target in (Status.IN_REVIEW, Status.APPROVED, Status.IN_REVIEW):
        set_status(load_episode(series, "ep"), target)
    assert _beats_bytes(ep, nl) == beats


def test_trailing_whitespace_and_tabs_in_beats_are_preserved(series):
    ep = create_episode(series, "ep")
    beats = b"beats:\n\t- type: statement   \n\n\n  # trailing blank lines\n\n"
    _write_bytes(ep, META, beats, "\n")
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert _beats_bytes(ep, "\n") == beats


def test_beats_without_a_trailing_newline_is_preserved(series):
    ep = create_episode(series, "ep")
    beats = b"beats:\n  - type: statement"
    _write_bytes(ep, META, beats, "\n")
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert _beats_bytes(ep, "\n") == beats


# --- the error contract Task 4's `except EpisodeError` depends on --------------


def test_unreadable_episodes_dir_raises_episode_error(series):
    import os
    import stat

    create_episode(series, "2026-08-14")
    d = series.episodes_dir
    mode = d.stat().st_mode
    os.chmod(d, 0)
    try:
        if os.access(d, os.R_OK):  # running as root; the probe is meaningless
            pytest.skip("cannot revoke read permission as this user")
        with pytest.raises(EpisodeError):
            episode_ids(series)
    finally:
        os.chmod(d, stat.S_IMODE(mode))


def test_create_over_a_dangling_symlink_raises_episode_error(series):
    (series.episodes_dir).mkdir(parents=True, exist_ok=True)
    (series.episodes_dir / "ghost").symlink_to(series.episodes_dir / "nowhere")
    with pytest.raises(EpisodeError):
        create_episode(series, "ghost")


def test_empty_query_does_not_resolve_an_episode(series):
    """`agsoc video review ""` must not silently pick the only episode."""
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError):
        resolve_episode(series, "")


# --- mixed line endings, and the metadata block ---------------------------------
# `sep.end() + len(sep.group(1))` assumed the separator's trailing newline was
# the same length as its leading one. With CRLF metadata and LF beats it ate the
# first byte of the beats document, silently, leaving a file that still parses.


@pytest.mark.parametrize(
    "meta_nl,beats_nl",
    [("\r\n", "\n"), ("\n", "\r\n"), ("\r", "\n"), ("\n", "\r"), ("\r\n", "\r")],
)
def test_mixed_line_endings_preserve_beats_bytes(series, meta_nl, beats_nl):
    ep = create_episode(series, "ep")
    meta = meta_nl.join(["episode: e", "series: the-brief", "status: draft", ""])
    beats = beats_nl.join(["beats:", "  - type: statement", ""])
    ep.script_path.write_bytes(
        f"---{meta_nl}{meta}---{beats_nl}{beats}".encode()
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert beats.encode() in ep.script_path.read_bytes()


def test_first_byte_of_beats_is_never_eaten(series):
    """The specific corruption: b'beats:' became b'eats:'."""
    ep = create_episode(series, "ep")
    ep.script_path.write_bytes(
        b"---\r\nepisode: e\r\nseries: the-brief\r\nstatus: draft\r\n"
        b"---\nbeats:\n  - type: statement\n"
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    raw = ep.script_path.read_bytes()
    assert b"beats:" in raw
    assert b"eats:\n" not in raw.replace(b"beats:", b"")


def test_an_all_crlf_script_stays_all_crlf(series):
    """Kills the 3c survivor: dropping head.replace() emits LF metadata lines
    inside CRLF fences, and no byte test looked at the metadata block."""
    ep = create_episode(series, "ep")
    ep.script_path.write_bytes(
        b"---\r\nepisode: e\r\nseries: the-brief\r\nstatus: draft\r\n"
        b"---\r\nbeats:\r\n  - type: statement\r\n"
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    raw = ep.script_path.read_bytes()
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0


def test_an_all_lf_script_stays_all_lf(series):
    ep = create_episode(series, "ep")
    ep.script_path.write_bytes(
        b"---\nepisode: e\nseries: the-brief\nstatus: draft\n"
        b"---\nbeats:\n  - type: statement\n"
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert b"\r" not in ep.script_path.read_bytes()

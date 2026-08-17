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

import pytest

from agenticsocial.models import Status, TransitionError
from agenticsocial.workspace import Workspace, WorkspaceError, load_config


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


def test_init_scaffolds_workspace(tmp_path):
    ws = Workspace.init(tmp_path / "workspace")
    assert ws.sources_dir.is_dir()
    assert (ws.root / "voice.md").exists()
    assert (ws.root / "config.toml").exists()
    assert load_config(ws) == {"x": {"client_id": ""}}


def test_init_is_idempotent_and_preserves_edits(tmp_path):
    ws = Workspace.init(tmp_path / "workspace")
    (ws.root / "voice.md").write_text("MY VOICE", encoding="utf-8")
    Workspace.init(tmp_path / "workspace")
    assert (ws.root / "voice.md").read_text(encoding="utf-8") == "MY VOICE"


def test_locate_uses_env_var(tmp_path, monkeypatch):
    Workspace.init(tmp_path / "elsewhere")
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "elsewhere"))
    assert Workspace.locate().root == tmp_path / "elsewhere"


def test_locate_missing_workspace_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "nope"))
    with pytest.raises(WorkspaceError, match="agsoc init"):
        Workspace.locate()


def test_create_source_writes_source_md(ws):
    src = ws.create_source("Kill Staging!", type="idea", created="2026-07-13")
    assert src.id == "2026-07-13-kill-staging"
    assert (ws.sources_dir / src.id / "source.md").exists()


def test_create_source_rejects_duplicate(ws):
    ws.create_source("Same title", created="2026-07-13")
    with pytest.raises(WorkspaceError, match="already exists"):
        ws.create_source("Same title", created="2026-07-13")


def test_list_sources_roundtrip(ws):
    ws.create_source("B idea", created="2026-07-14")
    ws.create_source("A idea", type="url", origin_url="https://ex.com/a", created="2026-07-13")
    sources = ws.list_sources()
    assert [s.id for s in sources] == ["2026-07-13-a-idea", "2026-07-14-b-idea"]
    assert sources[0].origin_url == "https://ex.com/a"
    assert sources[0].type == "url"
    assert sources[0].title == "A idea"


def test_resolve_source_by_substring(ws):
    ws.create_source("Kill staging", created="2026-07-13")
    ws.create_source("Queues gotchas", created="2026-07-13")
    assert ws.resolve_source("staging").id == "2026-07-13-kill-staging"


def test_resolve_source_ambiguous_or_missing(ws):
    ws.create_source("Idea one", created="2026-07-13")
    ws.create_source("Idea two", created="2026-07-13")
    with pytest.raises(WorkspaceError, match="matches multiple"):
        ws.resolve_source("idea")
    with pytest.raises(WorkspaceError, match="no source"):
        ws.resolve_source("zzz")


@pytest.fixture()
def src(ws):
    return ws.create_source("Kill staging", created="2026-07-13")


def test_create_and_load_variant(ws, src):
    ws.create_variant(src, "x", body="Tweet one\n\n---tweet---\n\nTweet two\n")
    v = ws.load_variant(src, "x")
    assert v.platform == "x"
    assert v.status == Status.DRAFT
    assert v.meta["posted_ids"] == []
    assert "Tweet two" in v.body
    assert v.path == src.dir / "x.md"


def test_load_missing_variant_raises(ws, src):
    with pytest.raises(WorkspaceError, match="no x variant"):
        ws.load_variant(src, "x")


def test_variants_lists_only_platform_files(ws, src):
    ws.create_variant(src, "x")
    (src.dir / "brief.md").write_text("notes", encoding="utf-8")
    assert [v.platform for v in ws.variants(src)] == ["x"]


def test_set_status_persists_and_stamps_approved_at(ws, src):
    ws.create_variant(src, "x", body="hi")
    v = ws.load_variant(src, "x")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    v2 = ws.load_variant(src, "x")
    assert v2.status == Status.APPROVED
    assert v2.meta["approved_at"]  # stamped


def test_set_status_enforces_gate(ws, src):
    ws.create_variant(src, "x", body="hi")
    v = ws.load_variant(src, "x")
    with pytest.raises(TransitionError):
        ws.set_status(v, Status.APPROVED)  # draft -> approved is forbidden
    assert ws.load_variant(src, "x").status == Status.DRAFT  # nothing saved


def test_save_variant_roundtrips_body_edits(ws, src):
    ws.create_variant(src, "x", body="old")
    v = ws.load_variant(src, "x")
    v.body = "new body"
    ws.save_variant(v)
    assert ws.load_variant(src, "x").body == "new body"


def test_load_variant_invalid_status_raises_workspace_error(ws, src):
    ws.create_variant(src, "x", body="hi")
    path = src.dir / "x.md"
    path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: aproved"), encoding="utf-8")
    with pytest.raises(WorkspaceError, match="invalid status 'aproved'"):
        ws.load_variant(src, "x")


def test_source_md_without_id_falls_back_to_dirname(ws):
    src = ws.create_source("Has id", created="2026-07-13")
    (src.dir / "source.md").write_text("---\ntitle: Has id\n---\n", encoding="utf-8")
    assert ws.list_sources()[0].id == src.dir.name

from typer.testing import CliRunner

from agenticsocial import __version__
from agenticsocial.cli import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


import pytest

from agenticsocial.models import Status
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


def test_init_creates_workspace(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path / "ws")])
    assert result.exit_code == 0
    assert (tmp_path / "ws" / "voice.md").exists()
    assert "voice.md" in result.output


def test_new_creates_source_and_prints_id(ws):
    result = runner.invoke(app, ["new", "Kill staging"])
    assert result.exit_code == 0
    assert "-kill-staging" in result.output
    assert len(ws.list_sources()) == 1


def test_new_with_url_sets_type(ws):
    runner.invoke(app, ["new", "Some post", "--url", "https://ex.com/p"])
    src = ws.list_sources()[0]
    assert src.type == "url"
    assert src.origin_url == "https://ex.com/p"


def test_new_without_workspace_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "missing"))
    result = runner.invoke(app, ["new", "x"])
    assert result.exit_code == 1
    assert "agsoc init" in result.output


def test_list_shows_sources_and_variant_statuses(ws):
    src = ws.create_source("Kill staging", created="2026-07-13")
    ws.create_variant(src, "x", body="hi")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "2026-07-13-kill-staging" in result.output
    assert "x:draft" in result.output


def test_list_filters_by_status(ws):
    a = ws.create_source("Aaa", created="2026-07-13")
    ws.create_variant(a, "x", body="hi")
    b = ws.create_source("Bbb", created="2026-07-13")
    v = ws.create_variant(b, "x", body="hi")
    ws.set_status(v, Status.IN_REVIEW)
    result = runner.invoke(app, ["list", "--status", "in_review"])
    assert "bbb" in result.output
    assert "aaa" not in result.output


def test_status_overview(ws):
    src = ws.create_source("Kill staging", created="2026-07-13")
    v = ws.create_variant(src, "x", body="hi")
    ws.set_status(v, Status.IN_REVIEW)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "in_review" in result.output
    assert "1" in result.output

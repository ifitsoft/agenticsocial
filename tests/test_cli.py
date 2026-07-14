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


def test_list_rejects_unknown_status(ws):
    result = runner.invoke(app, ["list", "--status", "bogus"])
    assert result.exit_code == 1
    assert "unknown status" in result.output


def test_new_with_missing_file_fails_cleanly(ws):
    result = runner.invoke(app, ["new", "T", "--file", "/nonexistent/x.txt"])
    assert result.exit_code == 1
    assert "cannot read" in result.output


def test_status_overview(ws):
    src = ws.create_source("Kill staging", created="2026-07-13")
    v = ws.create_variant(src, "x", body="hi")
    ws.set_status(v, Status.IN_REVIEW)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "in_review" in result.output
    assert "1" in result.output


@pytest.fixture()
def reviewable(ws):
    src = ws.create_source("Kill staging", created="2026-07-13")
    v = ws.create_variant(src, "x", body="Tweet one\n\n---tweet---\n\nTweet two")
    ws.set_status(v, Status.IN_REVIEW)
    return ws, src


def test_review_renders_thread_with_counts(reviewable):
    result = runner.invoke(app, ["review", "staging"])
    assert result.exit_code == 0
    assert "tweet 1/2" in result.output
    assert "Tweet two" in result.output
    assert "in_review" in result.output


def test_approve_moves_status(reviewable):
    ws, src = reviewable
    result = runner.invoke(app, ["approve", "staging"])
    assert result.exit_code == 0
    assert ws.load_variant(src, "x").status == Status.APPROVED


def test_approve_rejects_overlong_tweet(ws):
    src = ws.create_source("Long one", created="2026-07-13")
    v = ws.create_variant(src, "x", body="y" * 300)
    ws.set_status(v, Status.IN_REVIEW)
    result = runner.invoke(app, ["approve", "long"])
    assert result.exit_code == 1
    assert "300" in result.output
    assert ws.load_variant(src, "x").status == Status.IN_REVIEW


def test_approve_from_draft_fails_with_transition_message(ws):
    src = ws.create_source("Draft one", created="2026-07-13")
    ws.create_variant(src, "x", body="hi")
    result = runner.invoke(app, ["approve", "draft-one"])
    assert result.exit_code == 1
    assert "allowed next" in result.output


@pytest.fixture()
def approved(ws):
    src = ws.create_source("Ready", created="2026-07-13")
    v = ws.create_variant(src, "x", body="One\n\n---tweet---\n\nTwo")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    return ws, src


def test_post_dry_run_prints_without_posting(approved):
    ws, src = approved
    result = runner.invoke(app, ["post", "ready", "--dry-run"])
    assert result.exit_code == 0
    assert "would post 2 tweets" in result.output
    assert ws.load_variant(src, "x").status == Status.APPROVED  # unchanged


def test_post_requires_auth_token(approved, monkeypatch):
    from agenticsocial.x import auth as x_auth
    monkeypatch.setattr(x_auth, "load_token", lambda: None)
    result = runner.invoke(app, ["post", "ready"])
    assert result.exit_code == 1
    assert "agsoc auth x" in result.output


def test_post_publishes_and_prints_url(approved, monkeypatch):
    ws, src = approved
    from agenticsocial.x import auth as x_auth
    monkeypatch.setattr(x_auth, "load_token", lambda: {"access_token": "tok", "refresh_token": "r"})

    class FakeClient:
        def __init__(self, *a, **k):
            self.n = 0
        def post_tweet(self, text, in_reply_to=None):
            self.n += 1
            return f"id{self.n}"

    import agenticsocial.cli as cli_mod
    monkeypatch.setattr(cli_mod, "XClient", FakeClient)
    result = runner.invoke(app, ["post", "ready"])
    assert result.exit_code == 0
    assert "https://x.com/i/web/status/id1" in result.output
    assert ws.load_variant(src, "x").status == Status.PUBLISHED


def test_post_unapproved_fails_loudly(ws):
    src = ws.create_source("Unready", created="2026-07-13")
    ws.create_variant(src, "x", body="hi")
    result = runner.invoke(app, ["post", "unready"])
    assert result.exit_code == 1
    assert "allowed next" in result.output


def test_research_writes_brief(ws, monkeypatch):
    src = ws.create_source("Kill staging", created="2026-07-13")
    import agenticsocial.cli as cli_mod
    monkeypatch.setattr(
        cli_mod.research, "search",
        lambda query, max_results=8: [{"title": "T1", "href": "https://ex.com/a", "body": "snippet"}],
    )
    monkeypatch.setattr(cli_mod.research, "extract", lambda url: "article text")
    result = runner.invoke(app, ["research", "staging"])
    assert result.exit_code == 0
    brief = (src.dir / "brief.md").read_text(encoding="utf-8")
    assert "https://ex.com/a" in brief
    assert "brief.md" in result.output


def test_research_search_failure_fails_cleanly(ws, monkeypatch):
    ws.create_source("Net down", created="2026-07-13")
    import agenticsocial.cli as cli_mod

    def boom(query, max_results=8):
        raise RuntimeError("dns exploded")

    monkeypatch.setattr(cli_mod.research, "search", boom)
    result = runner.invoke(app, ["research", "net-down"])
    assert result.exit_code == 1
    assert "search failed" in result.output


def test_research_extract_failure_degrades_to_warning(ws, monkeypatch):
    src = ws.create_source("Half up", type="url", origin_url="https://ex.com/p", created="2026-07-13")
    import agenticsocial.cli as cli_mod
    monkeypatch.setattr(
        cli_mod.research, "search",
        lambda query, max_results=8: [{"title": "T", "href": "https://ex.com/a", "body": "s"}],
    )

    def boom(url):
        raise RuntimeError("timeout")

    monkeypatch.setattr(cli_mod.research, "extract", boom)
    result = runner.invoke(app, ["research", "half-up"])
    assert result.exit_code == 0
    assert "warning: could not extract" in result.output
    assert (src.dir / "brief.md").exists()

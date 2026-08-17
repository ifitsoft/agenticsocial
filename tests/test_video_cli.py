import pytest
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.workspace import Workspace

runner = CliRunner()


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


# --- series --------------------------------------------------------------------


def test_series_new_creates_and_reports(ws):
    result = runner.invoke(app, ["series", "new", "the-brief", "--name", "The Brief"])
    assert result.exit_code == 0
    assert "the-brief" in result.output
    assert (ws.series_dir / "the-brief" / "series.toml").exists()


def test_series_new_rejects_a_bad_slug(ws):
    result = runner.invoke(app, ["series", "new", "../escape"])
    assert result.exit_code == 1
    assert "slug" in result.output


def test_series_new_twice_fails_cleanly(ws):
    runner.invoke(app, ["series", "new", "the-brief"])
    result = runner.invoke(app, ["series", "new", "the-brief"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_series_list_shows_runtime_and_formats(ws):
    runner.invoke(app, ["series", "new", "the-brief", "--name", "The Brief"])
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 0
    assert "the-brief" in result.output
    assert "120s" in result.output
    assert "vertical" in result.output


def test_series_list_when_empty(ws):
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 0
    assert "no series" in result.output


def test_series_list_survives_one_broken_series(ws):
    """D-018: `list` is the diagnostic command. One bad file must not silence
    it — a ten-series workspace cannot become unlistable over one typo."""
    runner.invoke(app, ["series", "new", "good-one"])
    d = ws.series_dir / "broken-one"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text("[series\nname =", encoding="utf-8")
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 0
    assert "good-one" in result.output
    assert "broken-one" in result.output


# --- video ---------------------------------------------------------------------


def test_video_new_autocreates_the_default_series(ws):
    result = runner.invoke(app, ["video", "new", "2026-08-14"])
    assert result.exit_code == 0
    assert (ws.series_dir / "default" / "episodes" / "2026-08-14" / "script.yaml").exists()


def test_video_new_into_a_named_series(ws):
    runner.invoke(app, ["series", "new", "the-brief"])
    result = runner.invoke(app, ["video", "new", "2026-08-14", "--series", "the-brief"])
    assert result.exit_code == 0
    assert (ws.series_dir / "the-brief" / "episodes" / "2026-08-14").is_dir()


def test_video_new_into_missing_named_series_fails(ws):
    result = runner.invoke(app, ["video", "new", "2026-08-14", "--series", "nope"])
    assert result.exit_code == 1
    assert "agsoc series new" in result.output


def test_video_new_rejects_a_bad_id(ws):
    result = runner.invoke(app, ["video", "new", "../escape"])
    assert result.exit_code == 1
    assert "episode id" in result.output


def test_video_new_twice_fails_cleanly(ws):
    runner.invoke(app, ["video", "new", "2026-08-14"])
    result = runner.invoke(app, ["video", "new", "2026-08-14"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_video_list_shows_status(ws):
    runner.invoke(app, ["video", "new", "2026-08-14"])
    result = runner.invoke(app, ["video", "list"])
    assert result.exit_code == 0
    assert "2026-08-14" in result.output
    assert "draft" in result.output


def test_video_list_when_empty(ws):
    runner.invoke(app, ["series", "new", "the-brief"])
    result = runner.invoke(app, ["video", "list", "--series", "the-brief"])
    assert result.exit_code == 0
    assert "no episodes" in result.output


def test_video_list_survives_an_unparseable_episode(ws):
    runner.invoke(app, ["video", "new", "2026-08-14"])
    runner.invoke(app, ["video", "new", "2026-08-15"])
    bad = ws.series_dir / "default" / "episodes" / "2026-08-15" / "script.yaml"
    bad.write_bytes(b"\x00\x01 : : not yaml [\n")
    result = runner.invoke(app, ["video", "list"])
    assert result.exit_code == 0
    assert "2026-08-14" in result.output
    assert "2026-08-15" in result.output


def test_video_list_survives_an_undecodable_episode(ws):
    """The Step 0 fix, exercised through the CLI it exists for."""
    runner.invoke(app, ["video", "new", "2026-08-14"])
    runner.invoke(app, ["video", "new", "2026-08-15"])
    bad = ws.series_dir / "default" / "episodes" / "2026-08-15" / "script.yaml"
    bad.write_bytes(b"---\nepisode: e\nname: caf\xe9\n---\nbeats: []\n")
    result = runner.invoke(app, ["video", "list"])
    assert result.exit_code == 0
    assert "2026-08-14" in result.output


# --- the operator input boundary ------------------------------------------------


def test_a_name_that_cannot_be_encoded_is_rejected_cleanly(ws):
    """Python decodes sys.argv with surrogateescape, so a non-UTF-8 byte in an
    argument arrives as U+DC80-U+DCFF. UTF-8 cannot encode a lone surrogate, so
    this must fail as a clean CLI error rather than a UnicodeEncodeError
    traceback from inside atomic_write. See D-025."""
    result = runner.invoke(app, ["series", "new", "cafe", "--name", "caf\udce9"])
    assert result.exit_code == 1
    assert "traceback" not in result.output.lower()
    assert not (ws.series_dir / "cafe").exists()


# --- shared ---------------------------------------------------------------------


def test_commands_without_a_workspace_fail_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "missing"))
    result = runner.invoke(app, ["series", "list"])
    assert result.exit_code == 1
    assert "agsoc init" in result.output


def test_existing_text_commands_still_work(ws):
    result = runner.invoke(app, ["new", "Kill staging"])
    assert result.exit_code == 0
    assert "-kill-staging" in result.output

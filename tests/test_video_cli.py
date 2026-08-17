import pytest
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.workspace import Workspace

runner = CliRunner()


def run(*args):
    """Invoke the CLI with exceptions propagating.

    CliRunner catches exceptions by default and reports exit_code 1 with empty
    output — identical to a clean _fail — so an uncaught traceback passes every
    assertion a test would naturally write. See D-035.
    """
    return runner.invoke(app, list(args), catch_exceptions=False)


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


# --- series --------------------------------------------------------------------


def test_series_new_creates_and_reports(ws):
    result = run("series", "new", "the-brief", "--name", "The Brief")
    assert result.exit_code == 0
    assert "the-brief" in result.output
    assert (ws.series_dir / "the-brief" / "series.toml").exists()


def test_series_new_rejects_a_bad_slug(ws):
    result = run("series", "new", "../escape")
    assert result.exit_code == 1
    assert "slug" in result.output


def test_series_new_twice_fails_cleanly(ws):
    run("series", "new", "the-brief")
    result = run("series", "new", "the-brief")
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_series_list_shows_runtime_and_formats(ws):
    run("series", "new", "the-brief", "--name", "The Brief")
    result = run("series", "list")
    assert result.exit_code == 0
    assert "the-brief" in result.output
    assert "120s" in result.output
    assert "vertical" in result.output


def test_series_list_when_empty(ws):
    result = run("series", "list")
    assert result.exit_code == 0
    assert "no series" in result.output


def test_series_list_survives_one_broken_series(ws):
    """D-018: `list` is the diagnostic command. One bad file must not silence
    it — a ten-series workspace cannot become unlistable over one typo."""
    run("series", "new", "good-one")
    d = ws.series_dir / "broken-one"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text("[series\nname =", encoding="utf-8")
    result = run("series", "list")
    assert result.exit_code == 0
    assert "good-one" in result.output
    assert "broken-one" in result.output


# --- video ---------------------------------------------------------------------


def test_video_new_autocreates_the_default_series(ws):
    result = run("video", "new", "2026-08-14")
    assert result.exit_code == 0
    assert (ws.series_dir / "default" / "episodes" / "2026-08-14" / "script.yaml").exists()


def test_video_new_into_a_named_series(ws):
    run("series", "new", "the-brief")
    result = run("video", "new", "2026-08-14", "--series", "the-brief")
    assert result.exit_code == 0
    assert (ws.series_dir / "the-brief" / "episodes" / "2026-08-14").is_dir()


def test_video_new_into_missing_named_series_fails(ws):
    result = run("video", "new", "2026-08-14", "--series", "nope")
    assert result.exit_code == 1
    assert "agsoc series new" in result.output


def test_video_new_rejects_a_bad_id(ws):
    result = run("video", "new", "../escape")
    assert result.exit_code == 1
    assert "episode id" in result.output


def test_video_new_twice_fails_cleanly(ws):
    run("video", "new", "2026-08-14")
    result = run("video", "new", "2026-08-14")
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_video_list_shows_status(ws):
    run("video", "new", "2026-08-14")
    result = run("video", "list")
    assert result.exit_code == 0
    assert "2026-08-14" in result.output
    assert "draft" in result.output


def test_video_list_when_empty(ws):
    run("series", "new", "the-brief")
    result = run("video", "list", "--series", "the-brief")
    assert result.exit_code == 0
    assert "no episodes" in result.output


def test_video_list_survives_an_unparseable_episode(ws):
    run("video", "new", "2026-08-14")
    run("video", "new", "2026-08-15")
    bad = ws.series_dir / "default" / "episodes" / "2026-08-15" / "script.yaml"
    bad.write_bytes(b"\x00\x01 : : not yaml [\n")
    result = run("video", "list")
    assert result.exit_code == 0
    assert "2026-08-14" in result.output
    assert "2026-08-15" in result.output


def test_video_list_survives_an_undecodable_episode(ws):
    """The Step 0 fix, exercised through the CLI it exists for."""
    run("video", "new", "2026-08-14")
    run("video", "new", "2026-08-15")
    bad = ws.series_dir / "default" / "episodes" / "2026-08-15" / "script.yaml"
    bad.write_bytes(b"---\nepisode: e\nname: caf\xe9\n---\nbeats: []\n")
    result = run("video", "list")
    assert result.exit_code == 0
    assert "2026-08-14" in result.output


# --- the operator input boundary ------------------------------------------------


def test_a_name_that_cannot_be_encoded_is_rejected_cleanly(ws):
    """Python decodes sys.argv with surrogateescape, so a non-UTF-8 byte in an
    argument arrives as U+DC80-U+DCFF. UTF-8 cannot encode a lone surrogate, so
    this must fail as a clean CLI error rather than a UnicodeEncodeError
    traceback from inside atomic_write. See D-025."""
    result = run("series", "new", "cafe", "--name", "caf\udce9")
    assert result.exit_code == 1
    assert "traceback" not in result.output.lower()
    assert not (ws.series_dir / "cafe").exists()


# --- shared ---------------------------------------------------------------------


def test_commands_without_a_workspace_fail_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "missing"))
    result = run("series", "list")
    assert result.exit_code == 1
    assert "agsoc init" in result.output


def test_existing_text_commands_still_work(ws):
    result = run("new", "Kill staging")
    assert result.exit_code == 0
    assert "-kill-staging" in result.output


# --- every operator-typable input must fail cleanly, never traceback -----------


@pytest.mark.parametrize("cmd", [("series", "new"), ("video", "new")])
def test_over_long_name_fails_cleanly(ws, cmd):
    """Reachable by pasting a URL. The regexes constrain the alphabet but not
    the length, and mkdir raises OSError: File name too long at NAME_MAX + 1."""
    result = run(*cmd, "a" * 300)
    assert result.exit_code == 1
    assert "too long" in result.output.lower() or "length" in result.output.lower()


def test_series_list_survives_a_non_utf8_series_toml(ws):
    """The D-018 failure mode: one file saved by a cp1252-defaulting editor
    currently kills the entire listing with a raw UnicodeDecodeError."""
    run("series", "new", "good-one")
    d = ws.series_dir / "latin1"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_bytes(b'[series]\nname = "caf\xe9"\n')
    result = run("series", "list")
    assert result.exit_code == 0
    assert "good-one" in result.output
    assert "latin1" in result.output


def test_load_series_on_non_utf8_raises_series_error(ws):
    from agenticsocial.video.models import SeriesError
    from agenticsocial.video.series import load_series

    d = ws.series_dir / "latin1"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_bytes(b'[series]\nname = "caf\xe9"\n')
    with pytest.raises(SeriesError, match="UTF-8"):
        load_series(ws, "latin1")


def test_series_list_survives_an_unreadable_series_dir(ws):
    import os
    import stat

    run("series", "new", "the-brief")
    mode = ws.series_dir.stat().st_mode
    os.chmod(ws.series_dir, 0)
    try:
        if os.access(ws.series_dir, os.R_OK):
            pytest.skip("cannot revoke read permission as this user")
        result = run("series", "list")
        assert result.exit_code == 1
        assert "cannot list" in result.output.lower()
    finally:
        os.chmod(ws.series_dir, stat.S_IMODE(mode))


def test_series_new_into_a_read_only_workspace_fails_cleanly(ws):
    import os
    import stat

    ws.series_dir.mkdir(parents=True, exist_ok=True)
    mode = ws.series_dir.stat().st_mode
    os.chmod(ws.series_dir, stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(ws.series_dir, os.W_OK):
            pytest.skip("cannot revoke write permission as this user")
        result = run("series", "new", "the-brief")
        assert result.exit_code == 1
        assert "cannot create" in result.output.lower()
    finally:
        os.chmod(ws.series_dir, stat.S_IMODE(mode))


def test_series_list_reports_an_unknown_episode_count_rather_than_zero(ws):
    """`0 episodes` is a claim. When the count cannot be read, say so."""
    import os
    import stat

    run("series", "new", "the-brief")
    run("video", "new", "2026-08-14", "--series", "the-brief")
    eps = ws.series_dir / "the-brief" / "episodes"
    mode = eps.stat().st_mode
    os.chmod(eps, 0)
    try:
        if os.access(eps, os.R_OK):
            pytest.skip("cannot revoke read permission as this user")
        result = run("series", "list")
        assert result.exit_code == 0
        assert "? episodes" in result.output
        assert "0 episodes" not in result.output
    finally:
        os.chmod(eps, stat.S_IMODE(mode))

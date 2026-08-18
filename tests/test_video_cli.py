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
    assert "limit 64" in result.output


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


def test_video_new_cannot_escape_the_workspace(ws, tmp_path):
    """Verified escape: --series ../../outside wrote a real episode outside the
    workspace whenever the traversal target was itself a valid series."""
    outside = tmp_path / "outside"
    (outside / "episodes").mkdir(parents=True)
    (outside / "series.toml").write_text('[series]\nname = "O"\n', encoding="utf-8")
    depth = len(ws.series_dir.parts) - len(tmp_path.parts)
    traversal = "/".join([".."] * depth) + "/outside"
    result = run("video", "new", "2026-08-14", "--series", traversal)
    assert result.exit_code == 1
    assert not (outside / "episodes" / "2026-08-14").exists()


def test_series_option_with_undecodable_text_fails_cleanly(ws):
    """F1: --series was the one operator input never passed through _text()."""
    result = run("video", "new", "2026-08-14", "--series", "caf\udce9")
    assert result.exit_code == 1
    assert "UTF-8" in result.output


# --- preview -------------------------------------------------------------------


def test_video_preview_reports_the_output_path(ws, monkeypatch):
    import agenticsocial.video.render as R

    run("series", "new", "the-brief")
    run("video", "new", "2026-08-14", "--series", "the-brief")
    ep_dir = ws.series_dir / "the-brief" / "episodes" / "2026-08-14"
    (ep_dir / "script.yaml").write_text(
        "---\nstatus: draft\n---\nbeats:\n  - type: statement\n    text: hi\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(R, "preview", lambda *a, **k: ep_dir / "out" / "x.mp4")
    result = run("video", "preview", "2026-08-14", "--series", "the-brief")
    assert result.exit_code == 0
    assert "x.mp4" in result.output


def test_video_preview_render_failure_is_a_clean_error(ws, monkeypatch):
    import agenticsocial.video.render as R

    run("series", "new", "the-brief")
    run("video", "new", "2026-08-14", "--series", "the-brief")

    def boom(*a, **k):
        raise R.RenderError("ffmpeg not found on PATH")

    monkeypatch.setattr(R, "preview", boom)
    result = run("video", "preview", "2026-08-14", "--series", "the-brief")
    assert result.exit_code == 1
    assert "ffmpeg" in result.output


# --- agsoc video ingest --------------------------------------------------------


def _fake_ingest(keys, failures):
    """A stand-in for ingest.ingest_research. Patched at the module boundary so
    no test can reach the network — the CLI must never be the thing that
    fetches in a unit test."""
    from agenticsocial.video import ingest as I

    def fake(episode, query, **kw):
        return I.IngestResult(list(keys), list(failures), episode.dir / "brief.md")

    return fake


@pytest.fixture()
def prepared(ws):
    """An episode ready to ingest into. precondition for every test below:
    the corpus is empty and brief.md does not exist."""
    run("series", "new", "the-brief", "--name", "The Brief")
    run("video", "new", "2026-08-17", "--series", "the-brief")
    return ws.series_dir / "the-brief" / "episodes" / "2026-08-17"


def test_ingest_requires_an_input_mode(prepared):
    """R1 negative. Kills M2 — doing nothing and exiting 0 is
    indistinguishable from success."""
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 1
    for flag in ("--research", "--paste", "--from-source"):
        assert flag in result.output


def test_ingest_refuses_two_input_modes(prepared, tmp_path):
    """R1 negative. Kills M1 — silently preferring one hides which source the
    corpus actually came from, which is the one thing this phase exists to
    record."""
    f = tmp_path / "p.md"
    f.write_text("pasted", encoding="utf-8")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--paste", str(f), "--research", "gemini",
    )
    assert result.exit_code == 1
    assert "one" in result.output.lower()


def test_ingest_refuses_the_other_pair_of_input_modes(prepared, tmp_path):
    """R1 negative, own sweep. M1 restated: a guard written as `if research and
    paste` passes the brief's test and lets --paste --from-source through, and
    the corpus would then silently come from whichever branch is written first.
    precondition: the source exists, so the accepted branch would succeed."""
    ws_src = tmp_path  # only the paste file lives here
    f = ws_src / "p.md"
    f.write_text("pasted", encoding="utf-8")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--paste", str(f), "--from-source", "kill-staging",
    )
    assert result.exit_code == 1
    assert not list((prepared / "sources").glob("*.txt"))


def test_ingest_refuses_all_three_input_modes(prepared, tmp_path):
    """R1 negative, own sweep. `len(modes) > 1` and `len(modes) == 2` are not
    the same rule and only one of them is right."""
    f = tmp_path / "p.md"
    f.write_text("pasted", encoding="utf-8")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--paste", str(f), "--research", "gemini", "--from-source", "x",
    )
    assert result.exit_code == 1
    assert not list((prepared / "sources").glob("*.txt"))


def test_ingest_paste_writes_the_corpus(prepared, tmp_path):
    """precondition: corpus empty."""
    f = tmp_path / "p.md"
    f.write_text("the pasted digest", encoding="utf-8")
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--paste", str(f))
    assert result.exit_code == 0
    assert (prepared / "sources" / "_pasted.txt").read_text(encoding="utf-8") == (
        "the pasted digest"
    )
    assert (prepared / "brief.md").exists()


def test_ingest_paste_on_a_missing_file_is_a_clean_error(prepared, tmp_path):
    """R3. Kills M3."""
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--paste", str(tmp_path / "nope.md"),
    )
    assert result.exit_code == 1
    assert "nope.md" in result.output
    # The generic OSError arm also names the file, so without this the specific
    # arm can be deleted and the operator gets an errno string instead.
    assert "no such file" in result.output.lower()


def test_ingest_paste_on_a_non_utf8_file_is_a_clean_error(prepared, tmp_path):
    """R3 negative. Kills M4 — a cp1252-saved digest is the likeliest real
    input here, and it must not traceback."""
    f = tmp_path / "p.md"
    f.write_bytes(b"caf\xe9 pricing")
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--paste", str(f))
    assert result.exit_code == 1
    assert "UTF-8" in result.output


def test_ingest_paste_on_a_directory_is_a_clean_error(prepared, tmp_path):
    """R3, own sweep. Tab-completion hands you a directory as readily as a
    file; read_text raises IsADirectoryError, which is an OSError and not one
    of the two the brief's mutant table names. precondition: the path exists
    and is a directory."""
    d = tmp_path / "adir"
    d.mkdir()
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--paste", str(d))
    assert result.exit_code == 1
    assert "adir" in result.output
    # "cannot write the corpus" for a paste that could not be READ sends the
    # operator to check permissions on the wrong directory.
    assert "read" in result.output.lower()


def test_ingest_reports_partial_failure_and_still_succeeds(prepared, monkeypatch):
    """R2. Kills M8 — a corpus with three of four sources is usable, and
    failing the command would throw the three away."""
    from agenticsocial.video import ingest as I

    monkeypatch.setattr(
        I, "ingest_research",
        _fake_ingest(["blog-google"], [("https://venturebeat.com/b", "403 Forbidden")]),
    )
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 0
    assert "venturebeat.com/b" in result.output      # R4: failures are visible
    assert "403" in result.output


def test_ingest_does_not_invent_failures_when_there_were_none(prepared, monkeypatch):
    """R4's other half, own sweep. The failure report must be driven by the
    failures. An unconditional block, or one printed from the wrong list, is
    as misleading as printing nothing. precondition: a run with two keys and
    an empty failure list."""
    from agenticsocial.video import ingest as I

    monkeypatch.setattr(I, "ingest_research", _fake_ingest(["blog-google", "arstechnica"], []))
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 0
    assert "venturebeat" not in result.output
    assert "http" not in result.output


def test_ingest_reports_how_many_sources_landed(prepared, monkeypatch):
    """R4. Kills M6's counting variant: reporting `1 source` for a three-source
    ingest is a false record of what the corpus contains."""
    from agenticsocial.video import ingest as I

    monkeypatch.setattr(
        I, "ingest_research",
        _fake_ingest(["a-com", "b-com", "c-com"], [("https://d.com/x", "timeout")]),
    )
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 0
    # A bare "3" also matches a digit in the tmp path in the same output, so it
    # asserts nothing; the count has to be read next to what it counts.
    assert "3 source" in result.output
    assert "d.com/x" in result.output
    assert "timeout" in result.output


def test_ingest_fails_when_nothing_was_ingested(prepared, monkeypatch):
    """R2 negative. Kills M7 — an empty corpus that exits 0 looks exactly like
    a successful run to any script that checks the exit code."""
    from agenticsocial.video import ingest as I

    monkeypatch.setattr(I, "ingest_research", _fake_ingest([], [("https://x/y", "403")]))
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 1


def test_ingest_fails_when_nothing_was_ingested_and_nothing_failed(prepared, monkeypatch):
    """R2 negative, own sweep. M7's matched half: a search that returned no
    results at all yields keys == [] AND failures == [], and a guard written as
    `if not keys and failures` exits 0 on it — the silent empty corpus R2
    exists to forbid."""
    from agenticsocial.video import ingest as I

    monkeypatch.setattr(I, "ingest_research", _fake_ingest([], []))
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 1
    assert "nothing" in result.output.lower()


def test_ingest_surfaces_a_search_failure_cleanly(prepared, monkeypatch):
    """R3. Kills M5."""
    from agenticsocial.video import ingest as I

    def boom(episode, query, **kw):
        raise I.IngestError("search failed: connection refused")

    monkeypatch.setattr(I, "ingest_research", boom)
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 1
    assert "connection refused" in result.output


def test_ingest_from_an_unknown_source_is_a_clean_error(prepared):
    """R3. Kills M9."""
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief", "--from-source", "nope"
    )
    assert result.exit_code == 1
    assert "nope" in result.output


def test_ingest_from_an_ambiguous_source_is_a_clean_error(prepared, ws):
    """R3, own sweep. resolve_source raises WorkspaceError for an ambiguous
    prefix as well as an unknown one, and a handler that only special-cases
    'not found' tracebacks here. precondition: two sources share a substring."""
    ws.create_source("Kill staging", body="a", created="2026-08-14")
    ws.create_source("Kill staging again", body="b", created="2026-08-15")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--from-source", "kill-staging",
    )
    assert result.exit_code == 1
    assert "multiple" in result.output.lower()


def test_ingest_from_an_existing_source(prepared, ws):
    """precondition: corpus empty; the source exists with a non-empty body."""
    ws.create_source("Kill staging", body="the original reasoning", created="2026-08-14")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--from-source", "kill-staging",
    )
    assert result.exit_code == 0
    assert any((prepared / "sources").glob("*.txt"))


def test_ingest_from_an_empty_source_fails_rather_than_citing_nothing(prepared, ws):
    """R2 negative through the CLI, own sweep. ingest_source returns keys == []
    for an empty body; the command must treat that as the empty corpus it is.
    precondition: the source exists and its body is blank."""
    ws.create_source("Empty one", body="   \n", created="2026-08-14")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--from-source", "empty-one",
    )
    assert result.exit_code == 1


def test_ingest_into_an_unknown_episode_is_a_clean_error(ws):
    run("series", "new", "the-brief")
    result = run(
        "video", "ingest", "1999-01-01", "--series", "the-brief", "--research", "x"
    )
    assert result.exit_code == 1
    assert "agsoc video new" in result.output


def test_ingest_into_an_unknown_series_is_a_clean_error(ws):
    """R3, own sweep. The series is as typable as the episode."""
    result = run(
        "video", "ingest", "2026-08-17", "--series", "nope", "--research", "x"
    )
    assert result.exit_code == 1
    assert "nope" in result.output


def test_ingest_into_an_unwritable_episode_is_a_clean_error(prepared, tmp_path):
    """R3 negative — 'an unreadable output directory', named in the rule and in
    no mutant. precondition: the paste file is valid, so the only thing that can
    fail is the write."""
    import os
    import stat

    f = tmp_path / "p.md"
    f.write_text("the pasted digest", encoding="utf-8")
    mode = prepared.stat().st_mode
    os.chmod(prepared, stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(prepared, os.W_OK):
            pytest.skip("cannot revoke write permission as this user")
        result = run(
            "video", "ingest", "2026-08-17", "--series", "the-brief", "--paste", str(f)
        )
        assert result.exit_code == 1
        assert "cannot" in result.output.lower()
    finally:
        os.chmod(prepared, stat.S_IMODE(mode))


def test_ingest_with_an_undecodable_query_fails_cleanly(prepared):
    """R3 negative, own sweep. D-025: sys.argv is decoded with surrogateescape,
    so a non-UTF-8 byte in --research arrives as a lone surrogate and reaches
    brief.md, where atomic_write cannot encode it. --research was the newest
    operator input and the one most likely to be pasted from a terminal."""
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "caf\udce9"
    )
    assert result.exit_code == 1
    assert "UTF-8" in result.output


def test_ingest_with_an_undecodable_episode_id_fails_cleanly(prepared):
    """R3 negative, own sweep. F1 was `--series` skipping _text() on one
    command; every new command re-opens that hole on every argument."""
    result = run(
        "video", "ingest", "caf\udce9", "--series", "the-brief", "--research", "x"
    )
    assert result.exit_code == 1
    assert "UTF-8" in result.output


# --- phase 6 task 2: the hint a command prints must be a command that runs ----------
#
# D-109: an author trusts the tool over the doc. `video new`'s "next" line
# omitted `--series`, so following it inside any series other than `default`
# fails — and the skill telling you to pass `--series` loses the argument
# against the CLI's own suggestion.


def test_video_new_hints_the_next_command_with_its_series(ws):
    run("series", "new", "the-brief")
    result = run("video", "new", "2026-08-14", "--series", "the-brief")
    assert result.exit_code == 0
    hint = [ln for ln in result.output.splitlines() if ln.startswith("next:")]
    assert hint, result.output
    assert "--series the-brief" in hint[0]


def test_the_next_command_video_new_prints_actually_runs(ws, tmp_path):
    """precondition: the hint is executed, not pattern-matched. `--research`
    would need the network, so only that one flag is swapped for the offline
    `--paste`; the command name, the episode id and the series all come from
    the hint's own bytes."""
    run("series", "new", "the-brief")
    result = run("video", "new", "2026-08-14", "--series", "the-brief")
    hint = next(ln for ln in result.output.splitlines() if ln.startswith("next:"))
    brief = tmp_path / "brief.md"
    brief.write_text("DeepSeek raised prices.", encoding="utf-8")
    argv = hint[len("next:"):].split()
    assert argv[0] == "agsoc"
    argv = argv[1:argv.index("--research")] + ["--paste", str(brief)]
    ingested = run(*argv)
    assert ingested.exit_code == 0, ingested.output
    assert (
        ws.series_dir / "the-brief" / "episodes" / "2026-08-14" / "sources" / "_pasted.txt"
    ).exists()

import json

import pytest

from agenticsocial.video.models import SeriesError
from agenticsocial.video.series import list_series, load_series, scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


def _write_series(ws, slug, body):
    d = ws.series_dir / slug
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(body, encoding="utf-8")


def test_scaffold_creates_the_layout(ws):
    s = scaffold_series(ws, "the-brief", name="The Brief")
    assert (s.dir / "series.toml").exists()
    assert (s.dir / "coverage.json").exists()
    assert (s.dir / "episodes").is_dir()
    assert s.dir == ws.series_dir / "the-brief"


def test_scaffold_is_not_destructive(ws):
    scaffold_series(ws, "the-brief")
    with pytest.raises(SeriesError, match="already exists"):
        scaffold_series(ws, "the-brief")


def test_scaffolded_series_loads_with_expected_defaults(ws):
    scaffold_series(ws, "the-brief", name="The Brief")
    s = load_series(ws, "the-brief")
    assert s.slug == "the-brief"
    assert s.name == "The Brief"
    assert s.target_sec == 120
    assert s.tolerance_sec == 8
    assert s.formats == ["vertical", "wide"]
    assert s.cadence == "daily"
    assert s.register == "reported"


def test_scaffold_defaults_name_to_slug(ws):
    scaffold_series(ws, "cardio-weekly")
    assert load_series(ws, "cardio-weekly").name == "cardio-weekly"


def test_scaffolded_coverage_json_is_valid_and_empty(ws):
    import json

    s = scaffold_series(ws, "the-brief", name="The Brief")
    data = json.loads((s.dir / "coverage.json").read_text(encoding="utf-8"))
    assert data["series"] == "The Brief"
    assert data["episodes"] == []
    assert "conventions" in data


def test_minimal_config_loads_with_defaults(ws):
    _write_series(ws, "minimal", '[series]\nname = "Minimal"\n')
    s = load_series(ws, "minimal")
    assert s.name == "Minimal"
    assert s.target_sec == 120
    assert s.formats == ["vertical", "wide"]
    assert s.acts == []
    assert s.byline == ""


def test_design_tokens_are_loaded(ws):
    scaffold_series(ws, "the-brief")
    s = load_series(ws, "the-brief")
    assert s.design["accent"] == "#2E6BFF"
    assert s.design["surface"] == "#F2F5F8"


def test_acts_are_loaded_in_order(ws):
    d = ws.series_dir / "acted"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Acted"\n\n'
        '[[structure.acts]]\nid = "01"\nlabel = "One"\nbeats = 6\n\n'
        '[[structure.acts]]\nid = "02"\nlabel = "Two"\nbeats = 4\n',
        encoding="utf-8",
    )
    s = load_series(ws, "acted")
    assert [a["id"] for a in s.acts] == ["01", "02"]
    assert s.acts[0]["beats"] == 6


def test_unknown_format_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[formats]\nenabled = ["square"]\n', encoding="utf-8"
    )
    with pytest.raises(SeriesError, match="square"):
        load_series(ws, "bad")


def test_empty_format_list_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[formats]\nenabled = []\n', encoding="utf-8"
    )
    with pytest.raises(SeriesError, match="at least one"):
        load_series(ws, "bad")


def test_non_positive_runtime_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[runtime]\ntarget_sec = 0\n', encoding="utf-8"
    )
    with pytest.raises(SeriesError, match="target_sec"):
        load_series(ws, "bad")


def test_non_integer_runtime_is_rejected(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text(
        '[series]\nname = "Bad"\n\n[runtime]\ntarget_sec = "two minutes"\n',
        encoding="utf-8",
    )
    with pytest.raises(SeriesError, match="target_sec"):
        load_series(ws, "bad")


def test_missing_series_is_actionable(ws):
    with pytest.raises(SeriesError, match="agsoc series new"):
        load_series(ws, "nope")


def test_malformed_toml_names_the_file(ws):
    d = ws.series_dir / "broken"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text("[series\nname =", encoding="utf-8")
    with pytest.raises(SeriesError, match="series.toml"):
        load_series(ws, "broken")


def test_list_series_is_sorted_and_skips_non_series_dirs(ws):
    scaffold_series(ws, "zulu")
    scaffold_series(ws, "alpha")
    (ws.series_dir / "not-a-series").mkdir()
    assert [s.slug for s in list_series(ws)] == ["alpha", "zulu"]


def test_list_series_on_empty_workspace(ws):
    assert list_series(ws) == []


def test_scaffold_does_not_disturb_the_text_pipeline(ws):
    """series/ is additive; v1 workspaces have no series/ and must still work."""
    scaffold_series(ws, "the-brief")
    assert ws.sources_dir.is_dir()
    assert (ws.root / "voice.md").exists()


# --- F1: hostile names must not corrupt the files they are written into -------


@pytest.mark.parametrize(
    "hostile",
    [
        'He said "hi"',
        "back\\slash",
        "line\nbreak",
        "tab\there",
        'both "quotes" and \\slashes\\',
    ],
)
def test_hostile_series_name_round_trips(ws, hostile):
    """A name is operator input. It must survive scaffold -> load unchanged."""
    scaffold_series(ws, "hostile", name=hostile)
    assert load_series(ws, "hostile").name == hostile


@pytest.mark.parametrize("hostile", ['He said "hi"', "back\\slash", "line\nbreak"])
def test_hostile_series_name_leaves_valid_coverage_json(ws, hostile):
    s = scaffold_series(ws, "hostile", name=hostile)
    data = json.loads((s.dir / "coverage.json").read_text(encoding="utf-8"))
    assert data["series"] == hostile
    assert data["episodes"] == []


def test_failed_scaffold_leaves_no_partial_directory(ws, monkeypatch):
    """If writing fails midway, the operator must be able to simply retry."""
    import agenticsocial.video.series as series_mod

    real = series_mod.atomic_write
    calls = {"n": 0}

    def explode(path, text):
        calls["n"] += 1
        if calls["n"] == 2:  # fail on coverage.json, after series.toml succeeded
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(series_mod, "atomic_write", explode)
    with pytest.raises(OSError):
        scaffold_series(ws, "doomed", name="Doomed")
    assert not (ws.series_dir / "doomed").exists()
    scaffold_series(ws, "doomed", name="Doomed")  # retry must now work


# --- F6: slugs become filesystem paths ---------------------------------------


@pytest.mark.parametrize(
    "bad", ["../escape", "a/b", "", ".", "..", "Upper", "has space", "-leading"]
)
def test_invalid_slug_is_rejected(ws, bad):
    with pytest.raises(SeriesError, match="slug"):
        scaffold_series(ws, bad)


def test_slug_rejection_happens_before_any_write(ws):
    with pytest.raises(SeriesError):
        scaffold_series(ws, "../escape")
    assert not (ws.root.parent / "escape").exists()


# --- F2: the strictly-validated path must raise SeriesError, never TypeError --


def test_non_string_format_entries_raise_series_error(ws):
    _write_series(ws, "bad", '[series]\nname = "B"\n\n[formats]\nenabled = [1, 2]\n')
    with pytest.raises(SeriesError, match="list of strings"):
        load_series(ws, "bad")


def test_string_instead_of_format_list_raises_series_error(ws):
    """`enabled = "vertical"` must not be iterated character by character."""
    _write_series(ws, "bad", '[series]\nname = "B"\n\n[formats]\nenabled = "vertical"\n')
    with pytest.raises(SeriesError, match="list of strings"):
        load_series(ws, "bad")


# --- F3: wrong-typed sections must raise SeriesError, not AttributeError ------


@pytest.mark.parametrize(
    "body",
    [
        'series = "hello"\n',
        'runtime = 5\n\n[series]\nname = "B"\n',
        'design = "blue"\n\n[series]\nname = "B"\n',
        'structure = true\n\n[series]\nname = "B"\n',
        'formats = 1\n\n[series]\nname = "B"\n',
    ],
)
def test_wrong_typed_section_raises_series_error(ws, body):
    _write_series(ws, "bad", body)
    with pytest.raises(SeriesError, match="must be a table"):
        load_series(ws, "bad")


def test_unreadable_series_toml_raises_series_error(ws):
    d = ws.series_dir / "bad"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").mkdir()  # a directory where a file belongs
    with pytest.raises(SeriesError):
        load_series(ws, "bad")


# --- F7: bool is a subclass of int ---------------------------------------------


def test_boolean_target_sec_is_rejected(ws):
    """`target_sec = true` would otherwise load as a 1-second episode."""
    _write_series(ws, "bad", '[series]\nname = "B"\n\n[runtime]\ntarget_sec = true\n')
    with pytest.raises(SeriesError, match="target_sec"):
        load_series(ws, "bad")


# --- F4: pin the loader defaults the scaffold-first tests never reach ---------


def test_minimal_config_reaches_every_loader_default(ws):
    """QA mutated cadence, register, tolerance_sec and the name fallback; all
    four survived, because the only test touching them asserts none of them."""
    _write_series(ws, "minimal2", "[series]\n")
    s = load_series(ws, "minimal2")
    assert s.name == "minimal2"  # falls back to slug
    assert s.cadence == "daily"
    assert s.register == "reported"
    assert s.tolerance_sec == 8
    assert s.byline == ""
    assert s.design == {}
    assert s.warm_acts == []


# --- F4/mutant 6: pin the on-disk directory name that spec §5 fixes -----------


def test_series_dir_is_literally_named_series(ws):
    """`ws.series_dir / slug` compares an attribute to itself. Spec §5 fixes the
    on-disk name; renaming it to `shows/` passed all 130 tests."""
    assert ws.series_dir == ws.root / "series"
    s = scaffold_series(ws, "the-brief")
    assert s.dir == ws.root / "series" / "the-brief"
    assert (ws.root / "series" / "the-brief" / "series.toml").is_file()


# --- F5: warm_acts was written by the scaffold and dropped by the loader ------


def test_warm_acts_is_loaded(ws):
    _write_series(
        ws, "warm", '[series]\nname = "W"\n\n[structure]\nwarm_acts = ["03"]\n'
    )
    assert load_series(ws, "warm").warm_acts == ["03"]


# --- TOML basic-string escaping ------------------------------------------------
# json.dumps was wrong: ensure_ascii=True emits UTF-16 surrogate pairs for
# non-BMP characters, and TOML requires \uXXXX escapes to be Unicode scalar
# values. ensure_ascii=False is also wrong: it emits raw U+007F, which TOML
# forbids in a basic string. Hence an explicit escaper.


@pytest.mark.parametrize(
    "hostile",
    [
        "The Brief 😀",            # non-BMP: emoji
        "北京 𠀋",                  # non-BMP: CJK extension B
        "Ünïcödé BMP",             # BMP non-ASCII
        "Ω≈ç√∫",                   # BMP symbols
        "del\x7fhere",             # U+007F, forbidden raw in TOML
        "bell\x07here",            # C0 control with no short escape
        "null\x00byte",            # U+0000
        "esc\x1bseq",              # U+001B
        'quote" and \\slash',
        "line\nbreak\ttab\r\n",
        "\x0c formfeed \x08 backspace",
        "mixed 😀 \x07 \"q\" \\s ünïcödé",
    ],
)
def test_any_name_round_trips_through_toml(ws, hostile):
    """A name is operator input. Every string must survive scaffold -> load."""
    scaffold_series(ws, "hostile", name=hostile)
    assert load_series(ws, "hostile").name == hostile


def test_every_codepoint_below_0x100_round_trips(ws):
    """Sweep the whole C0/C1 + Latin-1 range rather than sampling it."""
    name = "".join(chr(c) for c in range(1, 0x100))
    scaffold_series(ws, "sweep", name=name)
    assert load_series(ws, "sweep").name == name


def test_non_bmp_name_produces_a_literal_utf8_file(ws):
    """The escaper must pass non-ASCII through literally, not escape it.
    TOML files are UTF-8; escaping is only for what UTF-8 cannot carry safely."""
    s = scaffold_series(ws, "emoji", name="The Brief 😀")
    raw = (s.dir / "series.toml").read_text(encoding="utf-8")
    assert "😀" in raw
    assert "\\ud83d" not in raw


def test_del_and_control_chars_are_escaped_not_literal(ws):
    s = scaffold_series(ws, "ctrl", name="del\x7fhere")
    raw = (s.dir / "series.toml").read_text(encoding="utf-8")
    assert "\x7f" not in raw
    assert "\\u007F" in raw or "\\u007f" in raw


def test_hostile_name_round_trips_through_coverage_json_too(ws):
    import json as _json

    name = "😀 \"q\" \\s \x07"
    s = scaffold_series(ws, "both", name=name)
    data = _json.loads((s.dir / "coverage.json").read_text(encoding="utf-8"))
    assert data["series"] == name


# --- acts / warm_acts were the last unvalidated fields -------------------------


@pytest.mark.parametrize("bad", ['"not a list"', "5", "{a = 1}", '["a", "b"]'])
def test_wrong_shaped_acts_is_rejected(ws, bad):
    _write_series(ws, "bad", f'[series]\nname = "B"\n\n[structure]\nacts = {bad}\n')
    with pytest.raises(SeriesError, match="acts"):
        load_series(ws, "bad")


def test_wellformed_acts_still_loads(ws):
    _write_series(
        ws,
        "good",
        '[series]\nname = "G"\n\n'
        '[[structure.acts]]\nid = "01"\nlabel = "One"\nbeats = 6\n',
    )
    assert load_series(ws, "good").acts == [{"id": "01", "label": "One", "beats": 6}]


@pytest.mark.parametrize("bad", ['"03"', "[3]", "5"])
def test_wrong_shaped_warm_acts_is_rejected(ws, bad):
    _write_series(
        ws, "bad", f'[series]\nname = "B"\n\n[structure]\nwarm_acts = {bad}\n'
    )
    with pytest.raises(SeriesError, match="warm_acts"):
        load_series(ws, "bad")

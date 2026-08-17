import json
import re
import warnings

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


def _write_series_overwrite(ws, slug, body):
    d = ws.series_dir / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "episodes").mkdir(exist_ok=True)
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


# --- path safety: what agsoc will TOUCH, distinct from what it will CREATE -----

UNSAFE = ["../../outside", "..", ".", "", "a/b", "a\\b", "/abs", "sub/dir"]


@pytest.mark.parametrize("bad", UNSAFE)
def test_load_series_refuses_unsafe_names(ws, bad):
    """scaffold_series validated its slug; load_series did not, and
    `video new --series ../../outside` reaches create_episode through it."""
    with pytest.raises(SeriesError, match="unsafe"):
        load_series(ws, bad)


@pytest.mark.parametrize("bad", UNSAFE)
def test_scaffold_series_refuses_unsafe_names(ws, bad):
    with pytest.raises(SeriesError):
        scaffold_series(ws, bad)


def test_load_series_still_accepts_a_hand_made_directory_name(ws):
    """Path safety is not a naming rule. A directory a human called `My-Show`
    must stay loadable even though agsoc would not have created it."""
    d = ws.series_dir / "My-Show"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text('[series]\nname = "Mine"\n', encoding="utf-8")
    assert load_series(ws, "My-Show").name == "Mine"


def test_scaffold_series_detects_a_dangling_symlink(ws):
    """create_episode checks is_symlink(); its sibling did not, so Path.exists()
    followed the link and mkdir reported [Errno 17] instead of a clean error."""
    ws.series_dir.mkdir(parents=True, exist_ok=True)
    (ws.series_dir / "ghost").symlink_to(ws.series_dir / "nowhere")
    with pytest.raises(SeriesError, match="already exists"):
        scaffold_series(ws, "ghost")


def test_series_runtime_targets_cannot_be_assigned(ws):
    """Phase 3 gates duration on target_sec/tolerance_sec. A writable value that
    a gate reads is exactly what caused three bypasses in the status field."""
    import dataclasses

    s = scaffold_series(ws, "the-brief")
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.target_sec = 9999
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.tolerance_sec = 9999


# --- fields that become gate inputs this phase (D-025, D-063) ------------------


@pytest.mark.parametrize("bad", ['"eight"', "-1", "true", "1.5"])
def test_bad_tolerance_sec_is_rejected(ws, bad):
    """precondition: no other field is invalid, so only tolerance_sec can fail.
    Phase 3 gates runtime on this value; target_sec one line above is strictly
    validated for exactly this reason."""
    _write_series(ws, "bad", f'[series]\nname = "B"\n\n[runtime]\ntolerance_sec = {bad}\n')
    with pytest.raises(SeriesError, match="tolerance_sec"):
        load_series(ws, "bad")


def test_zero_tolerance_is_valid(ws):
    """R1 NEGATIVE: a series demanding an exact runtime is legitimate, and a
    naive `> 0` check would reject it."""
    _write_series(ws, "exact", '[series]\nname = "E"\n\n[runtime]\ntolerance_sec = 0\n')
    assert load_series(ws, "exact").tolerance_sec == 0


@pytest.mark.parametrize("bad", ['"shouty"', "5", "true"])
def test_unknown_register_is_rejected(ws, bad):
    """precondition: register is the only invalid field. Phase 4 BRANCHES on
    this; a typo must not silently select a default."""
    _write_series(ws, "bad", f'[series]\nname = "B"\n\n[series]\n')  # placeholder
    _write_series_overwrite(ws, "bad", f'[series]\nname = "B"\nregister = {bad}\n')
    with pytest.raises(SeriesError, match="register"):
        load_series(ws, "bad")


def test_both_registers_in_the_spec_are_accepted(ws):
    for value in ("reported", "first-person"):
        slug = "r-" + value.replace("-", "")
        _write_series(ws, slug, f'[series]\nname = "R"\nregister = "{value}"\n')
        assert load_series(ws, slug).register == value


def test_cadence_stays_free_form(ws):
    """R2 NEGATIVE: cadence is explicitly advisory (spec 6) — nothing branches
    on it, so validating it would reject a legitimate 'fortnightly'."""
    _write_series(ws, "c", '[series]\nname = "C"\ncadence = "fortnightly"\n')
    assert load_series(ws, "c").cadence == "fortnightly"


@pytest.mark.parametrize("field", ["name", "byline"])
@pytest.mark.parametrize("bad", ["5", "[\"a\"]", "true"])
def test_non_string_text_fields_are_rejected(ws, field, bad):
    """precondition: the field is present. A non-string name reaches _toml_str
    on the next scaffold and raises TypeError far from here."""
    _write_series(ws, "bad", f'[series]\n{field} = {bad}\n')
    with pytest.raises(SeriesError, match=field):
        load_series(ws, "bad")


def test_absent_text_fields_still_default(ws):
    """R3 NEGATIVE: absent is not the same as wrong-typed."""
    _write_series(ws, "min", "[series]\n")
    s = load_series(ws, "min")
    assert s.name == "min" and s.byline == ""


def test_one_length_limit_shared_by_both_modules(ws):
    """R4. Two separate 64s will drift exactly as D-036 predicts — that pattern
    has produced five defects in this project."""
    from agenticsocial.video import episode as E
    from agenticsocial.video import series as S

    assert S.MAX_NAME_LEN is E.MAX_ID_LEN


def test_episode_does_not_redeclare_the_length_limit():
    """R4, structurally. `S.MAX_NAME_LEN is E.MAX_ID_LEN` cannot detect a
    duplicated definition: CPython interns small ints, so `64 is 64` is True
    and two independent `= 64` literals satisfy it. Only the absence of a
    second definition actually pins one constant."""
    from pathlib import Path

    from agenticsocial.video import episode as E

    src = Path(E.__file__).read_text(encoding="utf-8")
    assert "from .series import MAX_NAME_LEN as MAX_ID_LEN" in src
    assert not re.search(r"^MAX_ID_LEN\s*=", src, re.MULTILINE)


@pytest.mark.parametrize("field", ["name", "byline"])
@pytest.mark.parametrize("bad", ["0", "false", "[]", "0.0"])
def test_falsy_non_string_text_fields_are_rejected(ws, field, bad):
    """Mutation sweep: `if value:` in place of `if value is not None:` survived
    the brief's cases, because every one of them is truthy. `name = 0` would
    then load and reach _toml_str on the next scaffold — the exact TypeError
    the check exists to prevent."""
    _write_series(ws, "bad", f'[series]\n{field} = {bad}\n')
    with pytest.raises(SeriesError, match=field):
        load_series(ws, "bad")


# --- design.* becomes a CSS custom property (Phase 4 Task 0) -------------------
#
# The failure this closes: `accent = 5` reaches `--blue` in planbuild.js, CSS
# silently DISCARDS the invalid declaration, and the render comes out
# correct-looking with the wrong palette and no error anywhere. Every check
# below therefore runs at LOAD time, in Python, long before a frame exists.

COLOUR_TOKENS = ["surface", "ink", "ink_muted", "accent", "accent_alt", "accent_warm"]

# Every entry is written as a TOML literal. The first four are FALSY on purpose:
# three tasks running, mutants survived because every bad value chosen was
# truthy, and `if value and not COLOUR_RE.match(value)` passes all of them.
BAD_COLOURS = [
    "5",  # M2 — an int reaches CSS as `--blue:5` and is discarded
    '""',  # M3 — falsy, and `--blue:` is a discarded declaration too
    "true",  # falsy-adjacent: bool is an int subclass, so `isinstance(v, int)` lies
    "0",  # falsy int
    "false",  # falsy bool
    "[]",  # falsy list
    "0.0",  # falsy float
    '"blue"',  # M4 — valid CSS, wrong format for this palette
    '"rgb(0,0,255)"',  # valid CSS, wrong format
    '"#12345"',  # five digits is neither #RGB nor #RRGGBB
    '"#GGGGGG"',  # right length, not hex
    '"2E6BFF"',  # the hash is not optional
    '"#2E6BFF "',  # trailing space; CSS would tolerate it, our scaffold never writes it
]


@pytest.mark.parametrize("token", COLOUR_TOKENS)
@pytest.mark.parametrize("bad", BAD_COLOURS)
def test_non_colour_design_token_is_rejected(ws, token, bad):
    """precondition: every other field is absent or valid, so `token` is the
    only thing that can fail — the error naming `token` proves the check found
    it rather than tripping over something else.

    R1. Six of the eight design tokens become CSS custom properties in
    planbuild.js. CSS discards an invalid declaration in silence, so a value
    that is not a colour produces a wrong render and no error."""
    _write_series(ws, "bad", f'[series]\nname = "B"\n\n[design]\n{token} = {bad}\n')
    with pytest.raises(SeriesError, match=token):
        load_series(ws, "bad")


@pytest.mark.parametrize(
    "good", ['"#fff"', '"#FFF"', '"#FFFFFF"', '"#ffffff"', '"#2E6BFF"', '"#aBcDeF"']
)
@pytest.mark.parametrize("token", COLOUR_TOKENS)
def test_hex_colours_in_both_lengths_and_either_case_are_accepted(ws, token, good):
    """#RGB and #RRGGBB, case-insensitive — the two forms the scaffold and both
    committed episodes actually write."""
    _write_series(ws, "ok", f'[series]\nname = "O"\n\n[design]\n{token} = {good}\n')
    assert load_series(ws, "ok").design[token] == good.strip('"')


def test_the_scaffolded_palette_still_loads(ws):
    """The check must accept the file agsoc itself writes. A rule the scaffold
    violates is a rule that gets deleted."""
    s = scaffold_series(ws, "the-brief", name="The Brief")
    assert s.design["accent"] == "#2E6BFF"
    assert s.design["accent_warm"] == "#FF6B4A"


@pytest.mark.parametrize("token", ["type_family", "type_scale"])
@pytest.mark.parametrize(
    "value",
    [
        '"SF Pro Display, Helvetica Neue, system-ui"',
        '"default"',
        '"compact"',
        '"blue"',
        '""',
    ],
)
def test_typography_tokens_are_not_colour_checked(ws, token, value):
    """R1 NEGATIVE (M5). `type_family` and `type_scale` are not colours. A
    colour check applied to the whole [design] table rejects the scaffold's own
    font stack — the rule would be strictly worse than no rule."""
    _write_series(ws, "ok", f'[series]\nname = "O"\n\n[design]\n{token} = {value}\n')
    assert load_series(ws, "ok").design[token] == value.strip('"')


def test_a_design_token_nobody_maps_is_left_alone(ws):
    """Only the six tokens PLAN_TOKENS maps become CSS. An unknown key is an
    operator's note to themselves, not a colour."""
    _write_series(ws, "ok", '[series]\nname = "O"\n\n[design]\nnote = "wip"\n')
    assert load_series(ws, "ok").design["note"] == "wip"


def test_the_error_says_why_a_valid_css_colour_is_refused(ws):
    """`"blue"` IS valid CSS. Refusing it without saying why reads as a bug in
    agsoc; the reason is palette drift, and the message has to carry it."""
    _write_series(ws, "bad", '[series]\nname = "B"\n\n[design]\naccent = "blue"\n')
    with pytest.raises(SeriesError) as e:
        load_series(ws, "bad")
    msg = str(e.value)
    assert "accent" in msg
    assert "#" in msg  # shows the form it wants
    assert re.search(r"named colour|rgb\(", msg)


# --- warm_acts joins on act id, and a miss is a WARNING (D-070) ----------------


def test_warm_acts_naming_an_undeclared_act_warns_and_still_loads(ws):
    """R4 (M9). D-070 keeps this soft: the operator is told, and the series
    loads. Silence is the failure — nothing else in the pipeline will ever
    mention that `accent_warm` is wired to an act that does not exist."""
    _write_series(
        ws,
        "warm",
        '[series]\nname = "W"\n\n'
        '[structure]\nwarm_acts = ["99"]\n\n'
        '[[structure.acts]]\nid = "01"\nlabel = "One"\n',
    )
    with pytest.warns(UserWarning, match="warm_acts"):
        s = load_series(ws, "warm")
    assert s.warm_acts == ["99"]
    assert s.acts == [{"id": "01", "label": "One"}]


def test_warm_acts_mismatch_names_the_offending_id(ws):
    _write_series(
        ws,
        "warm",
        '[series]\nname = "W"\n\n'
        '[structure]\nwarm_acts = ["99"]\n\n'
        '[[structure.acts]]\nid = "01"\n',
    )
    with pytest.warns(UserWarning, match="99"):
        load_series(ws, "warm")


def test_warm_acts_mismatch_does_not_raise(ws):
    """R4 NEGATIVE (M8). Hardening the warning into a refusal turns a soft
    problem hard on the wrong side: it would refuse to load a series whose
    only fault is an act renamed in a file the loader cannot see."""
    _write_series(
        ws,
        "warm",
        '[series]\nname = "W"\n\n[structure]\nwarm_acts = ["99", "98"]\n',
    )
    with pytest.warns(UserWarning):
        s = load_series(ws, "warm")
    assert s.warm_acts == ["99", "98"]


def test_warm_acts_naming_a_declared_act_is_silent(ws):
    """A warning that fires on every healthy series is one operators learn to
    scroll past."""
    _write_series(
        ws,
        "warm",
        '[series]\nname = "W"\n\n'
        '[structure]\nwarm_acts = ["03"]\n\n'
        '[[structure.acts]]\nid = "03"\nlabel = "03 — Agents"\n',
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert load_series(ws, "warm").warm_acts == ["03"]


def test_warm_acts_joins_on_id_not_label(ws):
    """The decision this task was asked to make. `2026-08-12.js` carries
    `warmActs:['03 — Agents']` — a LABEL — because content/*.js had no
    series.toml to join against. An id is stable under rewording; a label is
    display text an operator edits, and joining on it silently unwires every
    reference the moment an act is renamed."""
    _write_series(
        ws,
        "warm",
        '[series]\nname = "W"\n\n'
        '[structure]\nwarm_acts = ["03 — Agents"]\n\n'
        '[[structure.acts]]\nid = "03"\nlabel = "03 — Agents"\n',
    )
    with pytest.warns(UserWarning, match="03 — Agents"):
        load_series(ws, "warm")


def test_an_empty_warm_acts_is_silent(ws):
    """The scaffold writes `warm_acts = []`. Every new series must be quiet."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        scaffold_series(ws, "the-brief")

import pytest

from agenticsocial.video.models import SeriesError
from agenticsocial.video.series import list_series, load_series, scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


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
    d = ws.series_dir / "minimal"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text('[series]\nname = "Minimal"\n', encoding="utf-8")
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

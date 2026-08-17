import json

import pytest

from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.plan import (
    FPS,
    SUPPORTED_BEATS,
    PlanError,
    build_plan,
    write_plan,
)
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


def _script(ep, beats_yaml, pace=None):
    meta = "episode: e\nseries: the-brief\nstatus: draft\n"
    if pace is not None:
        meta += f"pace: {pace}\n"
    ep.script_path.write_text(f"---\n{meta}---\n{beats_yaml}", encoding="utf-8")


THREE = """beats:
  - type: statement
    act: "01"
    hold: 3.5
    kicker: Today's headline
    text: Google shipped its main agentic model.
    src: blog.google
  - type: statement
    hold: 3.0
    text: And it costs half of what the last one did.
  - type: statement
    hold: 4.0
    text: That is the whole story.
"""


def test_plan_has_the_documented_shape(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["episode"] == "2026-08-14"
    assert plan["series"] == "the-brief"
    assert plan["format"] == {"name": "vertical", "w": 1080, "h": 1920}
    assert plan["fps"] == FPS
    assert len(plan["beats"]) == 3


def test_first_beat_carries_every_field(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert b == {
        "type": "statement",
        "act": "01",
        "hold": 3.5,
        "kicker": "Today's headline",
        "text": "Google shipped its main agentic model.",
        "src": "blog.google",
    }


def test_optional_fields_default_rather_than_vanish(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][1]
    assert b["act"] == "" and b["kicker"] == "" and b["src"] == ""


def test_missing_hold_defaults_to_three_seconds(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: no hold here\n")
    assert build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]["hold"] == 3.0


def test_total_sec_is_the_sum_of_holds_times_pace(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["pace"] == 1.0
    assert plan["total_sec"] == 10.5


def test_pace_scales_total_but_not_holds(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.5)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["pace"] == 1.5
    assert plan["total_sec"] == 15.75
    assert plan["beats"][0]["hold"] == 3.5  # unscaled; the engine applies pace


def test_design_tokens_come_from_the_series(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["design"]["accent"] == "#2E6BFF"
    assert plan["design"]["surface"] == "#F2F5F8"


def test_unsupported_beat_type_is_refused_by_name(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: jumpChart\n    text: x\n")
    with pytest.raises(PlanError) as e:
        build_plan(series, load_episode(series, "2026-08-14"))
    assert "jumpChart" in str(e.value)
    assert "statement" in str(e.value)


def test_beat_without_a_type_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - text: typeless\n")
    with pytest.raises(PlanError, match="type"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_statement_without_text_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    kicker: only a kicker\n")
    with pytest.raises(PlanError, match="text"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_non_positive_hold_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: x\n    hold: 0\n")
    with pytest.raises(PlanError, match="hold"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_empty_beats_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats: []\n")
    with pytest.raises(PlanError, match="no beats"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_beats_not_a_list_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats: just a string\n")
    with pytest.raises(PlanError, match="list"):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_unparseable_beats_raises_plan_error(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats: [unclosed\n  : : :\n")
    with pytest.raises(PlanError):
        build_plan(series, load_episode(series, "2026-08-14"))


def test_unknown_format_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    with pytest.raises(PlanError, match="wide"):
        build_plan(series, load_episode(series, "2026-08-14"), fmt="wide")


def test_write_plan_lands_in_out_dir_and_is_valid_json(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    path = write_plan(series, load_episode(series, "2026-08-14"))
    assert path == ep.out_dir / "plan.json"
    assert json.loads(path.read_text(encoding="utf-8"))["episode"] == "2026-08-14"


def test_write_plan_is_byte_stable_across_runs(series):
    """plan.json is a build artifact — it must be diffable, so key order and
    formatting cannot wobble between runs."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    e = load_episode(series, "2026-08-14")
    first = write_plan(series, e).read_bytes()
    second = write_plan(series, e).read_bytes()
    assert first == second


def test_building_a_plan_never_rewrites_the_script(series):
    """D-026: script.yaml bytes are load-bearing for script_sha256. This task
    reads the beats document; it must never write it."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    before = ep.script_path.read_bytes()
    write_plan(series, load_episode(series, "2026-08-14"))
    assert ep.script_path.read_bytes() == before


def test_supported_beats_is_exactly_statement_for_this_phase():
    assert SUPPORTED_BEATS == frozenset({"statement"})


# --- added by the implementer: vacuity fixes, see report section 5 -----------


def test_top_level_keys_are_exactly_the_documented_ones_in_order(series):
    """The brief documents a key ORDER, and byte-stability alone cannot pin it:
    any fixed order is stable run to run. Without this, `sort_keys=True` in
    write_plan is an undetected change to the format Phase 4 inherits."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert list(plan) == [
        "episode",
        "series",
        "byline",
        "format",
        "fps",
        "pace",
        "total_sec",
        "design",
        "beats",
    ]


def test_beat_keys_are_emitted_in_the_documented_order(series):
    """`==` on a dict ignores order, so test_first_beat_carries_every_field
    cannot see a reordering."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert list(b) == ["type", "act", "hold", "kicker", "text", "src"]


def test_written_json_preserves_the_documented_key_order(series):
    """The order has to survive serialisation, not just live in the dict."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    path = write_plan(series, load_episode(series, "2026-08-14"))
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert list(loaded)[:2] == ["episode", "series"]
    assert list(loaded["beats"][0]) == [
        "type",
        "act",
        "hold",
        "kicker",
        "text",
        "src",
    ]


def test_a_comment_bearing_script_survives_plan_building_byte_for_byte(series):
    """test_building_a_plan_never_rewrites_the_script uses a script whose
    metadata round-trips through safe_dump unchanged, so a `_compose`-based
    re-emission leaves it byte-identical and the guard stays green. D-026 is
    about the scripts that DON'T round-trip: comments, quoting, blank lines.
    """
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\n# storyboard: do not reflow\nepisode: e\nseries: the-brief\n"
        'status: "draft"\n\n---\n' + THREE,
        encoding="utf-8",
    )
    before = ep.script_path.read_bytes()
    write_plan(series, load_episode(series, "2026-08-14"))
    assert ep.script_path.read_bytes() == before


def test_beat_without_a_type_names_the_missing_key_not_an_unsupported_one(series):
    """`match="type"` also matches the unsupported-type message, so dropping the
    missing-`type` branch would leave that test green."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - text: typeless\n")
    with pytest.raises(PlanError) as e:
        build_plan(series, load_episode(series, "2026-08-14"))
    assert "no `type`" in str(e.value)
    assert "unsupported" not in str(e.value)

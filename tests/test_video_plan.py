import hashlib
import json
import shutil

import pytest

from agenticsocial.video import plan as plan_mod
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.plan import (
    FPS,
    SUPPORTED_BEATS,
    PlanError,
    build_plan,
    write_plan,
)
from agenticsocial.video.script import BEAT_TYPES
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
        "act_label": "01",
        "hold": 3.5,
        "start": 0.0,
        "end": 3.5,
        "start_frame": 0,
        "end_frame": 105,
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
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["beats"][0]["hold"] == 3.0
    assert plan["total_sec"] == 3.0


def test_total_sec_is_the_sum_of_holds_times_pace(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["pace"] == 1.0
    assert plan["total_sec"] == 10.5


def test_pace_scales_holds_and_total(series):
    """Renamed from test_pace_scales_total_but_not_holds: the plan is now fully
    resolved, so pace is applied in Python and the engine does no arithmetic."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.5)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["pace"] == 1.5
    assert plan["total_sec"] == 15.75
    assert plan["beats"][0]["hold"] == 5.25     # 3.5 * 1.5, scaled here
    assert plan["beats"][0]["end"] == 5.25


def test_design_tokens_come_from_the_series(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["design"]["accent"] == "#2E6BFF"
    assert plan["design"]["surface"] == "#F2F5F8"


def test_unsupported_beat_type_is_refused_by_name(series, monkeypatch):
    """Phase 3 split the schema (script.py) from resolution (plan.py), so a
    valid-but-unrenderable type reaches plan.py and is refused THERE.

    Phase 4 Task 3 drew the last two types, so no catalogue type is
    unrenderable today and the narrower gate has to be injected. The gate is
    kept, and kept tested, because the next type spec §7.1 grows will be valid
    before its builder exists — and a beat that validates, resolves, reaches the
    stage and silently draws nothing is the failure this refusal exists for."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: custom\n    js: x\n    attest: draws x. — A.\n")
    monkeypatch.setattr(plan_mod, "RENDERABLE", frozenset({"statement"}))
    with pytest.raises(PlanError) as e:
        build_plan(series, load_episode(series, "2026-08-14"))
    assert "custom" in str(e.value)
    assert "statement" in str(e.value)
    # Without this line the edit is vacuous: the pre-split message already
    # named both types, so the test would pass on the unsplit tree.
    assert "cannot be rendered yet" in str(e.value)


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
    assert path == ep.out_dir / "plan-vertical.json"
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


def test_supported_beats_is_exactly_this_phases_types():
    """Phase 4 widens the gate from one type to the whole catalogue — its exit
    criterion. Pinned against BEAT_TYPES rather than a literal list so that the
    day a new type is added, this line says whether plan.py may emit it."""
    assert SUPPORTED_BEATS == set(BEAT_TYPES)


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
        # Phase 4: the title and signoff cards render the display name, so it
        # travels next to the slug it belongs to rather than at the end.
        "series_name",
        "byline",
        "script_file_sha256",
        "format",
        "fps",
        "pace",
        "total_sec",
        "total_frames",
        "design",
        "beats",
    ]


def test_beat_keys_are_emitted_in_the_documented_order(series):
    """`==` on a dict ignores order, so test_first_beat_carries_every_field
    cannot see a reordering."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert list(b) == [
        "type",
        "act",
        "act_label",
        "hold",
        "start",
        "end",
        "start_frame",
        "end_frame",
        "kicker",
        "text",
        "src",
    ]


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
        "act_label",
        "hold",
        "start",
        "end",
        "start_frame",
        "end_frame",
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


# --- the plan is fully resolved: the engine does no timing arithmetic ---------


def test_beats_are_contiguous_and_start_at_zero(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    beats = build_plan(series, load_episode(series, "2026-08-14"))["beats"]
    assert beats[0]["start"] == 0.0
    for a, b in zip(beats, beats[1:]):
        assert b["start"] == a["end"], (a, b)


def test_total_sec_is_the_last_end_not_a_sum(series):
    """Documents shape, and cannot currently fail.

    While beats are contiguous and non-overlapping, `sum(hold)` and
    `beats[-1]["end"]` are provably equal, so no mutant distinguishes them. It
    is kept because deriving the total from the last end is what lets tracks be
    added later without changing the timing contract — see the Phase 1.5 plan.
    """
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["total_sec"] == plan["beats"][-1]["end"]


def test_frames_are_integers_and_sum_to_the_total(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.1)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    for b in plan["beats"]:
        assert isinstance(b["start_frame"], int)
        assert isinstance(b["end_frame"], int)
    assert plan["beats"][0]["start_frame"] == 0
    assert plan["total_frames"] == plan["beats"][-1]["end_frame"]
    for a, b in zip(plan["beats"], plan["beats"][1:]):
        assert b["start_frame"] == a["end_frame"]


def test_fractional_frames_are_resolved_in_python(series):
    """3.5s at pace 1.1 is 115.5 frames. Somebody must own that half-frame, and
    it is not the renderer."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: x\n    hold: 3.5\n", pace=1.1)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["beats"][0]["end_frame"] == 116          # round(115.5) -> banker's
    assert plan["total_frames"] == 116


# --- identity: the plan is bound to the exact script it came from -------------


def test_plan_carries_the_script_file_sha256(series):
    """Named `script_file_sha256` since Phase 7 Task 2: this is the WHOLE FILE,
    metadata document included, and the approval's `script_sha256` is the beats
    document alone. One key with two meanings in two files is the D-036 pattern
    waiting for someone to compare them."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    expected = hashlib.sha256(ep.script_path.read_bytes()).hexdigest()
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["script_file_sha256"] == expected


def test_editing_the_script_changes_the_hash(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    first = build_plan(series, load_episode(series, "2026-08-14"))["script_file_sha256"]
    _script(ep, THREE.replace("That is the whole story.", "Something else."))
    second = build_plan(series, load_episode(series, "2026-08-14"))["script_file_sha256"]
    assert first != second


# --- one read: two reads of one file is two sources of truth ------------------


def test_metadata_and_beats_come_from_the_same_read(series, monkeypatch):
    """build_plan read pace from episode.meta (in memory) and beats from a fresh
    file read. A script saved between the two produced a plan mixing versions."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.0)
    loaded = load_episode(series, "2026-08-14")
    _script(ep, THREE, pace=2.0)          # disk now disagrees with the stale object
    plan = build_plan(series, loaded)
    assert plan["pace"] == 2.0            # disk wins; one read, one truth
    assert plan["script_file_sha256"] == hashlib.sha256(
        ep.script_path.read_bytes()
    ).hexdigest()


# --- formats do not overwrite each other -------------------------------------


def test_write_plan_names_the_file_after_the_format(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    path = write_plan(series, load_episode(series, "2026-08-14"))
    assert path == ep.out_dir / "plan-vertical.json"


def test_resolved_times_are_rounded_not_raw_floats(series):
    """0.1 + 0.2 arithmetic must not reach a file whose purpose is diffability.
    Kills the mutant that drops round(start/end, 3)."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.1)
    for b in build_plan(series, load_episode(series, "2026-08-14"))["beats"]:
        for key in ("hold", "start", "end"):
            assert b[key] == round(b[key], 3), (key, b[key])


def test_resolved_times_are_rounded_under_an_accumulating_pace(series):
    """The sibling above is VACUOUS at pace 1.1: `hold` is itself rounded, and
    0.0 + 3.85 + 3.3 + 4.4 happens to land on exactly representable sums, so
    dropping round(start/end, 3) leaves it green (verified by mutant). Noise only
    escapes when the running total is not representable — pace 1.15 gives
    7.4750000000000005. This is the test that kills that mutant.
    """
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.15)
    for b in build_plan(series, load_episode(series, "2026-08-14"))["beats"]:
        for key in ("hold", "start", "end"):
            assert b[key] == round(b[key], 3), (key, b[key])


def test_a_beat_shorter_than_one_frame_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: blink\n    hold: 0.01\n")
    with pytest.raises(PlanError, match="one frame"):
        build_plan(series, load_episode(series, "2026-08-14"))


# --- Phase 4 Task 0: nothing the renderer interpolates may go unvalidated ------


def _series_with(series, **overrides):
    """A Series carrying values load_series would now refuse. build_plan must
    not trust its caller: `write_plan` is the last gate before plan.json exists
    on disk and Node is started."""
    import dataclasses

    return dataclasses.replace(series, **overrides)


def _with_acts(ws, series, acts_toml):
    """Append [[structure.acts]] blocks to the scaffolded series.toml and
    reload, so the acts under test came through the real loader."""
    from agenticsocial.video.series import load_series

    path = series.dir / "series.toml"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + acts_toml, encoding="utf-8"
    )
    return load_series(ws, series.slug)


@pytest.mark.parametrize("token", ["surface", "ink", "ink_muted", "accent", "accent_alt", "accent_warm"])
@pytest.mark.parametrize("bad", [5, "", True, False, 0, [], 0.0, "blue", "#12345"])
def test_write_plan_refuses_a_non_colour_before_the_file_exists(series, token, bad):
    """R2 (M6). Validation must happen BEFORE plan.json is written — not in
    planbuild.js, where the operator has already waited for a render, and not
    in CSS, which discards the declaration without saying anything.

    precondition: the script and every other design token are valid, so `token`
    is the only thing that can fail."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    s = _series_with(series, design={**series.design, token: bad})
    path = ep.out_dir / "plan-vertical.json"
    assert not path.exists()
    with pytest.raises(PlanError, match=token):
        write_plan(s, load_episode(series, "2026-08-14"))
    assert not path.exists(), "plan.json was written despite an invalid palette"


@pytest.mark.parametrize("bad", [5, "", True, [], "blue"])
def test_build_plan_refuses_a_non_colour(series, bad):
    """The check lives in build_plan, so every caller inherits it — write_plan
    today, and whatever Phase 8's gated `render` becomes."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    s = _series_with(series, design={**series.design, "accent": bad})
    with pytest.raises(PlanError, match="accent"):
        build_plan(s, load_episode(series, "2026-08-14"))


def test_typography_tokens_reach_the_plan_untouched(series):
    """R1 NEGATIVE (M5). planbuild.js maps six tokens; these two are not among
    them and are not colours."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["design"]["type_scale"] == "default"
    assert "SF Pro Display" in plan["design"]["type_family"]


# --- act id -> label resolution happens in Python (R3) -------------------------

ACTS = (
    '[[structure.acts]]\nid = "01"\nlabel = "01 — The headline"\nbeats = 6\n\n'
    '[[structure.acts]]\nid = "03"\nlabel = "03 — Agents"\nbeats = 4\n'
)


def test_a_beat_resolves_its_act_id_to_the_declared_label(ws, series):
    """R3. A beat names its act by ID. The label is display text, resolved once
    here so planbuild.js does no lookup — and so renaming an act in series.toml
    does not silently unwire every beat pointing at it."""
    s = _with_acts(ws, series, ACTS)
    ep = create_episode(s, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(s, load_episode(s, "2026-08-14"))["beats"][0]
    assert b["act"] == "01"
    assert b["act_label"] == "01 — The headline"


def test_an_undeclared_act_id_renders_as_the_raw_string(ws, series):
    """R3 NEGATIVE (M7). A script written before its series declared acts must
    still render — spec §6 marks act `beats` counts advisory, and refusing here
    would make a soft rule hard. The raw value falls through to the chip."""
    s = _with_acts(ws, series, '[[structure.acts]]\nid = "01"\nlabel = "One"\n')
    ep = create_episode(s, "2026-08-14")
    _script(
        ep,
        "beats:\n  - type: statement\n    act: 07 — Nowhere\n    text: still renders\n",
    )
    b = build_plan(s, load_episode(s, "2026-08-14"))["beats"][0]
    assert b["act"] == "07 — Nowhere"
    assert b["act_label"] == "07 — Nowhere"


def test_a_beat_with_no_act_stays_empty_on_both_keys(ws, series):
    """A cold open has no act chip. `""` must not resolve to anything."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][1]
    assert b["act"] == "" and b["act_label"] == ""


def test_no_acts_declared_at_all_falls_back_rather_than_failing(series):
    """The scaffold declares no acts. Every episode written against it must
    still build."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert b["act"] == "01" and b["act_label"] == "01"


def test_an_act_declared_without_a_label_falls_back_to_its_id(ws, series):
    """`label` is optional in spec §6 and validate_acts does not require it."""
    s = _with_acts(ws, series, '[[structure.acts]]\nid = "01"\n')
    ep = create_episode(s, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(s, load_episode(s, "2026-08-14"))["beats"][0]
    assert b["act_label"] == "01"


def test_an_act_declared_with_an_empty_label_keeps_it_empty(ws, series):
    """R3 NEGATIVE, falsy edge. The spec's own cold-open row carries
    `label = ""`. Falling back on falsiness rather than on absence would print
    the id on a chip the operator deliberately blanked."""
    s = _with_acts(ws, series, '[[structure.acts]]\nid = "01"\nlabel = ""\n')
    ep = create_episode(s, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(s, load_episode(s, "2026-08-14"))["beats"][0]
    assert b["act"] == "01"
    assert b["act_label"] == ""


def test_a_non_string_label_falls_back_instead_of_reaching_json(ws, series):
    """validate_acts checks `id`, not `label`. A number here would land in
    plan.json and be interpolated into the chip as `5`."""
    s = _series_with(series, acts=[{"id": "01", "label": 5}])
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    b = build_plan(s, load_episode(series, "2026-08-14"))["beats"][0]
    assert b["act_label"] == "01"


def test_the_resolved_label_survives_serialisation(ws, series):
    """The resolution is only useful if it reaches Node."""
    s = _with_acts(ws, series, ACTS)
    ep = create_episode(s, "2026-08-14")
    _script(ep, THREE)
    path = write_plan(s, load_episode(s, "2026-08-14"))
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["beats"][0]["act_label"] == "01 — The headline"


def _planbuild_path():
    from pathlib import Path

    import agenticsocial

    return Path(agenticsocial.__file__).resolve().parents[2] / "engine" / "planbuild.js"


def _planbuild_src():
    return _planbuild_path().read_text(encoding="utf-8")


def test_planbuild_consumes_the_resolved_label_and_does_no_lookup():
    """R2, structurally. If planbuild.js still passed `b.act`, the resolution
    would be dead weight and the chip would print a bare id.

    The PRECEDENCE is what this pins, not the mere presence of the identifier.
    A mutation sweep found that `b.act || b.act_label` — which prints the id and
    ignores the label — survived an `"act_label" in src` assertion untouched."""
    src = _planbuild_src()
    assert "b.act_label || b.act || ''" in src


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_planbuild_actually_passes_the_label_to_scene():
    """The structural test above pins the source text; this one runs it.

    planbuild.js is a classic script with no exports, so it is evaluated with
    the handful of globals `scene`/`meta`/`E`/`P`/`rise` that scene.html
    provides, and the act argument every `scene()` call receives is captured.
    """
    import json as _json
    import subprocess
    import textwrap

    plan = {
        "episode": "2026-08-16",
        "byline": "",
        "design": {},
        "beats": [
            {"type": "statement", "act": "01", "act_label": "01 — The headline",
             "hold": 3.0, "kicker": "", "text": "t", "src": ""},
            {"type": "statement", "act": "07", "act_label": "07",
             "hold": 3.0, "kicker": "", "text": "t", "src": ""},
            {"type": "statement", "act": "", "act_label": "",
             "hold": 3.0, "kicker": "", "text": "t", "src": ""},
        ],
    }
    harness = textwrap.dedent(
        """
        const fs = require('fs');
        const vm = require('vm');
        const seen = [];
        const ctx = {
          document: { documentElement: { style: { setProperty() {} } } },
          scene: (act) => seen.push(act),
          meta: () => {},
          E: () => ({}), P: (x) => x, rise: () => {},
        };
        vm.createContext(ctx);
        vm.runInContext(fs.readFileSync(process.env.PLANBUILD, 'utf8'), ctx);
        vm.runInContext('buildFromPlan(' + process.env.PLAN + ')', ctx);
        console.log(JSON.stringify(seen));
        """
    )
    import os

    proc = subprocess.run(
        ["node", "-e", harness],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PLANBUILD": str(_planbuild_path()),
            "PLAN": _json.dumps(plan),
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert _json.loads(proc.stdout) == ["01 — The headline", "07", ""]


# --- Phase 4: the plan carries every renderable type's own fields ---------------
#
# Until this phase every renderable beat was a `statement`, so `plan.json` could
# emit one hard-coded `text` key. A `list` has `items`, a `quote` has an
# `attribution`, a `title` has neither — and a field that never reaches
# plan.json is a field the renderer cannot draw, however well the schema
# validates it.

FIVE_TYPES = """beats:
  - type: title
    hold: 3.0
    sub: Five stories from the last 24 hours.
  - type: body
    hold: 3.0
    text: It costs **half** of what 3.6 Flash did.
  - type: list
    hold: 3.0
    lead: Live today in
    items:
      - Gemini API & AI Studio
      - Antigravity
  - type: quote
    hold: 3.0
    text: Gemini 3.7 Flash is our new workhorse model
    attribution: Google
  - type: signoff
    hold: 3.0
    text: Same time tomorrow.
"""


def _beats_by_type(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, FIVE_TYPES)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    return {b["type"]: b for b in plan["beats"]}


def test_a_list_beat_carries_its_items_and_lead(series):
    """M6/M7 upstream of Node: a builder cannot render a field the plan dropped."""
    b = _beats_by_type(series)["list"]
    assert b["items"] == ["Gemini API & AI Studio", "Antigravity"]
    assert b["lead"] == "Live today in"


def test_a_quote_beat_carries_its_attribution(series):
    """M8 upstream of Node."""
    b = _beats_by_type(series)["quote"]
    assert b["text"] == "Gemini 3.7 Flash is our new workhorse model"
    assert b["attribution"] == "Google"


def test_a_title_beat_carries_its_sub_and_no_text_key(series):
    """`title` has no `text` field at all. Emitting one — empty, or copied from
    somewhere — would invent content the operator did not write, which is the
    same divergence as dropping it."""
    b = _beats_by_type(series)["title"]
    assert b["sub"] == "Five stories from the last 24 hours."
    assert "text" not in b


def test_a_signoff_beat_carries_its_optional_text(series):
    assert _beats_by_type(series)["signoff"]["text"] == "Same time tomorrow."


def test_an_omitted_optional_field_is_omitted_not_blanked(series):
    """`sub: ""` is a title card with a deliberately blank subtitle; a missing
    `sub` is a card that has none. script.py keeps them distinct on purpose and
    plan.json must not collapse them."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: title\n    hold: 3.0\n")
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert "sub" not in b


def test_bold_markers_reach_the_plan_unaltered(series):
    """`**` is markup the ENGINE resolves. Python touching it would put the
    conversion in two places, and script.yaml's bytes are what Phase 5 verifies."""
    assert _beats_by_type(series)["body"]["text"] == (
        "It costs **half** of what 3.6 Flash did."
    )


def test_type_fields_sit_between_kicker_and_src(series):
    """The documented order is prefix, kicker, the type's own fields, src —
    `==` on a dict cannot see a reordering."""
    b = _beats_by_type(series)["list"]
    assert list(b) == [
        "type",
        "act",
        "act_label",
        "hold",
        "start",
        "end",
        "start_frame",
        "end_frame",
        "kicker",
        "items",
        "lead",
        "src",
    ]


def test_claim_override_does_not_leak_into_the_plan(series):
    """`claim_override` rides in `Beat.fields` because the dataclass has no slot
    for it, but it is Phase 5's verification input, not content. The renderer
    must not be able to draw it."""
    ep = create_episode(series, "2026-08-14")
    _script(
        ep,
        "beats:\n  - type: body\n    hold: 3.0\n    text: t\n"
        "    claim_override:\n"
        "      reason: Framed as expectation, not fact.\n"
        "      by: Ali Abdukarim\n",
    )
    b = build_plan(series, load_episode(series, "2026-08-14"))["beats"][0]
    assert "claim_override" not in b


def test_the_plan_carries_the_series_display_name(series):
    """The title and signoff cards put the series NAME on screen at 150px. The
    slug is a filesystem key — `the-brief` is not what the brand card says."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    assert plan["series"] == "the-brief"
    assert plan["series_name"] == "The Brief"


# --- Phase 4 Task 2: the chart types reach the renderer whole -------------------
#
# A chart beat carries numbers, and spec §7.2 says there is no path to rendering
# a number that isn't in a source. `planbuild.js` enforces that at the far end —
# a plan can reach the page without passing through Python at all, which is
# exactly what `determinism.test.mjs` does when it writes its own `.plan.js`. A
# gate the renderer cannot see is a gate on the honest path only, so `quote` has
# to travel with the beat it licences.

CHARTS = """beats:
  - type: kpis
    hold: 4.6
    kicker: And it costs half of what 3.6 Flash did
    items:
      - { value: 0.75, prefix: "$", label: per 1M input tokens, decimals: 2 }
      - { value: 3.75, prefix: "$", label: per 1M output tokens, decimals: 2 }
    src: venturebeat
    quote: priced at $0.75 per million input tokens and $3.75 per million output
  - type: jumpChart
    hold: 5.4
    rows:
      - { label: FrontierCode 1.1, before: 34.4, after: 43.6, shown: "<s>34.4</s> &rarr; 43.6" }
      - { label: GDP.pdf, before: 22.0, after: 34.0, shown: "<s>22.0</s> &rarr; 34.0" }
    scale: 70
    footnote: Scores as published by Google, on a common 0-70% scale.
    src: deepmind
    quote: FrontierCode 1.1 rises from 34.4 to 43.6
"""


def _charts(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, CHARTS)
    plan = build_plan(series, load_episode(series, "2026-08-14"))
    return {b["type"]: b for b in plan["beats"]}


def test_a_kpis_beat_carries_its_items(series):
    """M1 upstream of Node: a builder cannot render a field the plan dropped,
    and `items` is the whole beat."""
    b = _charts(series)["kpis"]
    assert b["items"] == [
        {"value": 0.75, "prefix": "$", "label": "per 1M input tokens", "decimals": 2},
        {"value": 3.75, "prefix": "$", "label": "per 1M output tokens", "decimals": 2},
    ]


def test_a_jumpchart_beat_carries_its_rows_scale_and_footnote(series):
    """M10 upstream of Node. `scale` is not decoration — the renderer positions
    every dot as `value / scale`, so a plan that dropped it would draw NaN%."""
    b = _charts(series)["jumpChart"]
    assert [r["label"] for r in b["rows"]] == ["FrontierCode 1.1", "GDP.pdf"]
    assert b["rows"][0]["shown"] == "<s>34.4</s> &rarr; 43.6"
    assert b["scale"] == 70
    assert b["footnote"] == "Scores as published by Google, on a common 0-70% scale."


@pytest.mark.parametrize("kind", ["kpis", "jumpChart"])
def test_a_cited_beat_carries_its_quote_to_the_renderer(series, kind):
    """R1. `planbuild.js` refuses to draw a chart without `src` AND `quote`, and
    it can only refuse on what the plan hands it. Without this the renderer's
    gate is decoration: every chart would arrive quoteless and either all of
    them fail or the check gets written against `src` alone."""
    b = _charts(series)[kind]
    assert b["src"] and b["quote"]


def test_an_uncited_type_gains_no_quote_key(series):
    """R1 NEGATIVE. `quote` travels because the type may not render without it;
    a `statement` may, so a `quote` key on one is a field the renderer has no
    business seeing — and `test_first_beat_carries_every_field` pins the exact
    key set for precisely this reason."""
    b = _beats_by_type(series)["body"]
    assert "quote" not in b


def test_the_quote_sits_beside_the_src_it_belongs_to(series):
    """The documented key order, extended. `src` and `quote` are one citation in
    two fields; splitting them across the beat makes a diff read as unrelated."""
    b = _charts(series)["kpis"]
    assert list(b)[-2:] == ["src", "quote"]

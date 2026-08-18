"""The beat catalogue: what a beat IS, per type, independent of rendering.

Every test carries a `precondition:` line — the fact about the world that makes
the assertion the right one.

Two habits this file is deliberate about, because both classes of mutant
survived earlier tasks:

  * every "wrong type" case includes FALSY values (0, False, "", []). A check
    written `if value:` accepts nothing and rejects everything falsy, so a
    parametrisation of only truthy bad values cannot see it.
  * `sub: ""` is valid and `hold: 0` is not. Absent, empty and invalid are
    three different states and the tests keep them apart.
"""
import re
from pathlib import Path

import pytest
import yaml

from agenticsocial.video import script as S
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.plan import PlanError, build_plan
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


def _write(ep, beats, meta_extra=""):
    """Write script.yaml with `beats` (a list of dicts) as document 2."""
    body = yaml.safe_dump({"beats": beats}, sort_keys=False, allow_unicode=True)
    meta = "episode: e\nseries: the-brief\nstatus: draft\n" + meta_extra
    ep.script_path.write_text(f"---\n{meta}---\n{body}", encoding="utf-8")


def _load(series, beats, meta_extra=""):
    ep = create_episode(series, "2026-08-14")
    _write(ep, beats, meta_extra)
    return S.load_script(load_episode(series, "2026-08-14"))


# --- exemplars -----------------------------------------------------------------
# One valid beat per catalogue type, with the fields spec §7.1 names for it.
# These are the fixtures every required-field and wrong-type case mutates.

VALID = {
    "statement": {
        "type": "statement",
        "text": "Gemini 3.7 Flash is Google's new workhorse.",
    },
    "body": {
        "type": "body",
        "text": "A natively multimodal reasoning model tuned for **coding**.",
    },
    "list": {
        "type": "list",
        "lead": "Tuned for coding, agentic workflows and knowledge work.",
        "items": ["Gemini API & AI Studio", "Antigravity", "The Spark agent"],
    },
    "kpis": {
        "type": "kpis",
        "items": [
            {"value": 0.75, "unit": "$", "label": "per 1M input tokens", "decimals": 2},
            {"value": 50, "unit": "%", "label": "cheaper than 3.6 Flash"},
        ],
        "src": "venturebeat",
        "quote": "priced at $0.75 per million input tokens and $3.75 per million output",
    },
    # The real four rows from engine/content/2026-08-14.js, transcribed into the
    # schema D-068 corrected §7.1 to. `jumpChart(rows, max, d0, parent)` takes a
    # LIST of bars; the single-bar shape the spec first described cannot express
    # the only jumpChart that has ever rendered.
    "jumpChart": {
        "type": "jumpChart",
        "rows": [
            {"label": "FrontierCode 1.1", "before": 34.4, "after": 43.6,
             "shown": "<s>34.4</s> &rarr; 43.6"},
            {"label": "DeepSWE v1.1", "before": 48.0, "after": 65.3,
             "shown": "<s>48–49</s> &rarr; 65.3"},
            {"label": "AutomationBench", "before": 17.0, "after": 30.4,
             "shown": "<s>17.0</s> &rarr; 30.4"},
            {"label": "GDP.pdf", "before": 22.0, "after": 34.0,
             "shown": "<s>22.0</s> &rarr; 34.0"},
        ],
        "scale": 70,
        "footnote": "Scores as published by Google, on a common 0-70% scale.",
        "src": "deepmind",
        "quote": "FrontierCode 1.1 rises from 34.4 to 43.6",
    },
    "dumbbell": {
        "type": "dumbbell",
        # `values` is a pair, positionally aligned with `series` — see
        # test_the_dumbbell_exemplar_is_the_chart_that_actually_rendered.
        "rows": [
            {"label": "History-taking", "values": [0.72, 0.72], "note": "on par"},
            {
                "label": "Eliciting physical signs",
                "values": [0.82, 0.58],
                "note": "rated higher",
            },
        ],
        "series": ["AMIE (video)", "Primary care physician"],
        "caption": "Evaluator ratings, AMIE against primary care physicians",
        "footnote": "Direction only — the source reports evaluator ratings.",
    },
    "quote": {
        "type": "quote",
        "text": "Gemini 3.7 Flash is our new workhorse model",
        "attribution": "Google",
    },
    "title": {"type": "title", "sub": "Five stories from the last 24 hours."},
    "signoff": {"type": "signoff", "text": "Same time tomorrow."},
    "custom": {
        "type": "custom",
        "js": "const h = E('h2', null, P('x'));\nrise(h, .15);\n",
    },
}


# --- the catalogue itself -------------------------------------------------------


def test_the_catalogue_covers_the_committed_episodes():
    """precondition: engine/content/*.js are the two episodes that really
    rendered. A catalogue that cannot describe them is describing something
    else."""
    used = set()
    for p in Path("engine/content").glob("*.js"):
        used |= set(
            re.findall(r"\b(kpis|jumpChart|rise|fade|draw|count)\s*\(", p.read_text())
        )
    assert used, "no engine primitives found — the evidence files moved"
    # engine primitives map to beat types; assert the ones the spec names exist
    for t in (
        "statement",
        "body",
        "list",
        "kpis",
        "jumpChart",
        "quote",
        "title",
        "signoff",
        "custom",
    ):
        assert t in S.BEAT_TYPES, t


def test_the_catalogue_is_exactly_the_ten_types_the_spec_lists():
    """precondition: spec §7.1 is a closed table of ten rows. An eleventh entry
    is something somebody invented after the spec was written."""
    assert set(S.BEAT_TYPES) == {
        "statement",
        "body",
        "list",
        "kpis",
        "jumpChart",
        "dumbbell",
        "quote",
        "title",
        "signoff",
        "custom",
    }


def test_every_exemplar_in_this_file_is_a_catalogue_type():
    """precondition: the exemplars are the fixtures for every other test here.
    If one names a type the catalogue does not have, those tests are vacuous."""
    assert set(VALID) == set(S.BEAT_TYPES)


def test_renderable_is_a_subset_of_the_catalogue():
    """precondition: renderability is a narrower gate than validity, never a
    wider one — a type plan.py can emit that script.py cannot describe would be
    unreachable."""
    assert S.RENDERABLE <= set(S.BEAT_TYPES)


def test_renderable_is_exactly_this_phases_types():
    """precondition: Phase 4 Task 3 draws the dumbbell, so nine of the ten
    catalogue types render. This pins the gate so that widening it is a
    deliberate edit — `custom` still has no builder in planbuild.js."""
    assert S.RENDERABLE == frozenset(
        {
            "statement",
            "body",
            "list",
            "quote",
            "title",
            "signoff",
            "kpis",
            "jumpChart",
            "dumbbell",
        }
    )


# --- D-068: jumpChart is a list of bars, not one bar ----------------------------
#
# Spec §7.1 originally gave jumpChart `before`/`after` at the top level. The
# engine's signature is `jumpChart(rows, max, d0, parent)` and the only episode
# that has ever drawn one passes four rows. The schema now follows the code.


def _engine_jump_rows():
    """The literal rows from engine/content/2026-08-14.js, read from the file.

    Read rather than retyped: a hand-copied fixture stops being evidence the
    moment the episode changes, which is exactly when we need it to complain.
    """
    src = Path("engine/content/2026-08-14.js").read_text(encoding="utf-8")
    call = re.search(r"jumpChart\(\[(.*?)\]\s*,\s*(\d+)\s*,", src, re.S)
    assert call, "the jumpChart call moved out of 2026-08-14.js"
    rows = re.findall(
        r"\[\s*'([^']*)'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*'([^']*)'\s*\]",
        call.group(1),
    )
    return [
        {"label": lab, "before": float(a), "after": float(b), "shown": shown}
        for lab, a, b, shown in rows
    ], int(call.group(2))


def test_the_exemplar_is_the_episode_that_actually_rendered():
    """precondition: D-068 was found by comparing the schema to the committed
    episode. If the exemplar drifts from that call, every jumpChart test below
    is testing a shape nothing renders."""
    rows, scale = _engine_jump_rows()
    assert len(rows) == 4, rows
    assert VALID["jumpChart"]["rows"] == rows
    assert VALID["jumpChart"]["scale"] == scale


def test_the_real_four_row_jumpchart_validates(series):
    """precondition: D-068. The schema's job is to describe the chart the engine
    draws; four rows is what it draws."""
    rows, scale = _engine_jump_rows()
    beat = dict(VALID["jumpChart"], rows=rows, scale=scale)
    script = _load(series, [beat])
    assert [r["label"] for r in script.beats[0].fields["rows"]] == [
        "FrontierCode 1.1",
        "DeepSWE v1.1",
        "AutomationBench",
        "GDP.pdf",
    ]


def test_jumpchart_no_longer_has_a_top_level_before_or_after():
    """precondition: D-068. Leaving the single-bar fields required alongside
    `rows` would make every real chart unwritable; leaving them optional would
    leave two ways to say the same thing and let a renderer pick the wrong
    one."""
    required = S.BEAT_TYPES["jumpChart"]["required"]
    optional = S.BEAT_TYPES["jumpChart"]["optional"]
    assert set(required) == {"rows", "scale", "footnote"}
    assert "before" not in optional and "after" not in optional


def test_a_jumpchart_row_may_omit_shown(series):
    """precondition: the engine does `E('div','jval',{html:shown})` — an
    undefined `shown` renders an empty value cell, not a crash. It is a display
    override, not data."""
    beat = dict(VALID["jumpChart"], rows=[{"label": "x", "before": 1, "after": 2}])
    script = _load(series, [beat])
    assert "shown" not in script.beats[0].fields["rows"][0]


def test_a_jumpchart_row_may_move_to_zero_or_from_zero(series):
    """precondition: falsy is not invalid. A benchmark that scored 0 before is a
    real bar, and `if before:` cannot draw it."""
    beat = dict(
        VALID["jumpChart"],
        rows=[
            {"label": "from nothing", "before": 0, "after": 30.4},
            {"label": "to nothing", "before": 12.0, "after": 0},
        ],
    )
    script = _load(series, [beat])
    assert [r["after"] for r in script.beats[0].fields["rows"]] == [30.4, 0]


def test_a_jumpchart_row_may_carry_an_empty_shown(series):
    """precondition: `shown: ""` deliberately blanks the value cell. Empty is a
    choice here, the way `sub: ""` is on a title card."""
    beat = dict(
        VALID["jumpChart"],
        rows=[{"label": "x", "before": 1, "after": 2, "shown": ""}],
    )
    script = _load(series, [beat])
    assert script.beats[0].fields["rows"][0]["shown"] == ""


def test_a_bad_jumpchart_row_names_its_index(series):
    """precondition: a twelve-bar chart with one bad row must say WHICH row.
    "rows is invalid" sends an operator reading all twelve."""
    beat = dict(
        VALID["jumpChart"],
        rows=[
            {"label": "ok", "before": 1, "after": 2},
            {"label": "ok too", "before": 1, "after": 2},
            {"label": "bad", "before": "1", "after": 2},
        ],
    )
    with pytest.raises(S.ScriptError) as e:
        _load(series, [beat])
    assert "[2]" in str(e.value)


# --- Phase 4 Task 2, R2: every number the frame shows is a number the plan
# --- carried ---------------------------------------------------------------------
#
# `src` and `quote` are not sufficient. The engine's `count()` takes `decimals`
# and formats with `toFixed`, so `value: 0.756, decimals: 1` puts `0.8` on the
# screen — a figure that is in no source, in no quote and in no plan. Phase 5
# would verify 0.756 against the quote, pass, and ship a video showing a number
# nobody checked. Display rounding is a number-inventing machine.
#
# The rule: refuse the beat when rounding to `decimals` would change the value.
# If an author wants 0.8 on screen the script says 0.8, because the script is
# what gets verified.


def _kpis(*items, **over):
    return dict(VALID["kpis"], items=list(items), **over)


def test_a_kpi_value_display_rounding_would_change_is_refused(series):
    """precondition: R2, and the whole reason this task exists. `count()` does
    `v.toFixed(1)` — 0.756 reaches the frame as `0.8`."""
    with pytest.raises(S.ScriptError) as e:
        _load(series, [_kpis({"value": 0.756, "label": "per 1M tokens", "decimals": 1})])
    msg = str(e.value)
    assert "0.756" in msg and "0.8" in msg
    assert "decimals" in msg


def test_a_kpi_value_exact_at_its_decimals_is_accepted(series):
    """precondition: R2 negative. The real 2026-08-14 pricing figures. Refusing
    these would refuse the only kpis beat that has ever rendered."""
    script = _load(
        series,
        [
            _kpis(
                {"value": 0.75, "label": "per 1M input tokens", "decimals": 2},
                {"value": 3.75, "label": "per 1M output tokens", "decimals": 2},
            )
        ],
    )
    assert [i["value"] for i in script.beats[0].fields["items"]] == [0.75, 3.75]


def test_a_kpi_value_with_no_decimals_must_already_be_whole(series):
    """precondition: R2, at the field the brief does not mention. `decimals` is
    OPTIONAL, and the engine treats absent exactly like 0 — `decimals ?
    v.toFixed(decimals) : Math.round(v)`. So an omitted `decimals` is not "no
    rounding", it is rounding to the nearest integer, and `value: 0.75` with no
    `decimals` reaches the frame as `1`. Absent must be checked as 0 or the rule
    has a hole the size of the default."""
    with pytest.raises(S.ScriptError) as e:
        _load(series, [_kpis({"value": 0.75, "label": "per 1M input tokens"})])
    assert "0.75" in str(e.value)


@pytest.mark.parametrize("value", [50, 2000, 1048576, 0])
def test_a_whole_kpi_value_needs_no_decimals(series, value):
    """precondition: R2 negative + the falsy rule. `0` is a legitimate KPI —
    "0 seconds of downtime" is a headline figure — and a check written
    `if value:` cannot draw it. `Math.round(0)` is `0`, so nothing is
    invented."""
    script = _load(series, [_kpis({"value": value, "label": "things"})])
    assert script.beats[0].fields["items"][0]["value"] == value


@pytest.mark.parametrize("value", [0, 0.0])
def test_zero_is_a_legitimate_kpi_value_at_any_decimals(series, value):
    """precondition: the falsy rule again, this time against a rounding check
    written `if round(v, d) != v` with a truthiness shortcut in front of it."""
    script = _load(series, [_kpis({"value": value, "label": "downtime", "decimals": 2})])
    assert script.beats[0].fields["items"][0]["value"] == value


def test_a_string_kpi_value_is_not_subject_to_rounding(series):
    """precondition: R2's scope. `kpis()` prints a non-numeric value verbatim
    rather than counting up to it — no `toFixed`, so no rounding, so nothing to
    invent. A rounding check that calls `round()` on it would crash instead."""
    script = _load(
        series, [_kpis({"value": "half", "label": "the price", "decimals": 1})]
    )
    assert script.beats[0].fields["items"][0]["value"] == "half"


def test_a_prefix_and_a_unit_are_presentation_not_invention(series):
    """precondition: R2 NEGATIVE, and the half of the pair that is easy to get
    backwards. A currency symbol changes how 0.75 READS, not what it IS: `$0.75`
    and `0.75` are the same figure. Rounding invents a number; a symbol does
    not."""
    script = _load(
        series,
        [
            _kpis(
                {"value": 0.75, "prefix": "$", "label": "in", "decimals": 2},
                {"value": 50, "unit": "%", "label": "cheaper"},
            )
        ],
    )
    items = script.beats[0].fields["items"]
    assert items[0]["prefix"] == "$"
    assert items[1]["unit"] == "%"


@pytest.mark.parametrize("bad", [0, False, [], {}, None, 1.5])
def test_a_non_string_prefix_is_refused(series, bad):
    """precondition: M4 on the new field. `prefix: 0` would be interpolated into
    the figure as the character `0`."""
    with pytest.raises(S.ScriptError) as e:
        _load(series, [_kpis({"value": 1, "label": "x", "prefix": bad})])
    assert "prefix" in str(e.value)


def test_the_refused_item_names_its_index(series):
    """precondition: the same reason a bad jumpChart row names its index — a
    six-figure KPI stack with one bad value must say which one."""
    with pytest.raises(S.ScriptError) as e:
        _load(
            series,
            [
                _kpis(
                    {"value": 1, "label": "ok"},
                    {"value": 2, "label": "ok too"},
                    {"value": 0.756, "label": "bad", "decimals": 1},
                )
            ],
        )
    assert "[2]" in str(e.value)


# --- Phase 4 Task 2, R4: a row outside the scale is refused, not clipped ---------
#
# `jumpChart` positions every dot as `from / max * 100 + '%'`. A row above the
# scale is drawn past the right edge of its track — off the card, or clipped by
# overflow — and a negative one is drawn to the left of zero. Either way the bar
# on screen no longer encodes the number in the plan, which is R2's failure
# wearing a geometry costume. Refuse it: silently clipping to the scale would
# show a full-length bar for a value that is not the maximum.


def _jump(*rows, **over):
    return dict(VALID["jumpChart"], rows=list(rows), **over)


@pytest.mark.parametrize("field", ["before", "after"])
def test_a_row_value_above_the_scale_is_refused(series, field):
    """precondition: R4 + M7. Both ends are drawn on the same track, so both
    have to be checked — a rule written against `after` alone leaves the
    baseline dot free to land off the card."""
    row = {"label": "FrontierCode 1.1", "before": 34.4, "after": 43.6}
    row[field] = 82.0
    with pytest.raises(S.ScriptError) as e:
        _load(series, [_jump(row, scale=70)])
    msg = str(e.value)
    assert "82" in msg and "70" in msg and field in msg


@pytest.mark.parametrize("field", ["before", "after"])
def test_a_row_value_equal_to_the_scale_is_accepted(series, field):
    """precondition: R4 NEGATIVE. The bound is inclusive: a benchmark that hits
    the top of the published scale is exactly the chart worth drawing, and it is
    drawn at 100% of the track, which is on the card."""
    row = {"label": "at the top", "before": 34.4, "after": 43.6}
    row[field] = 70
    script = _load(series, [_jump(row, scale=70)])
    assert script.beats[0].fields["rows"][0][field] == 70


@pytest.mark.parametrize("field", ["before", "after"])
def test_a_negative_row_value_is_refused(series, field):
    """precondition: R4's other end. `-4 / 70 * 100` is `-5.7%`, drawn off the
    left of the track. The interval is [0, scale], not (-inf, scale]."""
    row = {"label": "below zero", "before": 34.4, "after": 43.6}
    row[field] = -4.0
    with pytest.raises(S.ScriptError):
        _load(series, [_jump(row, scale=70)])


def test_zero_is_still_a_legitimate_row_value(series):
    """precondition: the falsy rule inside R4. A range check written
    `if not (0 < v <= scale)` refuses a benchmark that scored 0 before, which is
    the most interesting bar on the chart."""
    script = _load(
        series, [_jump({"label": "from nothing", "before": 0, "after": 30.4}, scale=70)]
    )
    assert script.beats[0].fields["rows"][0]["before"] == 0


def test_the_out_of_scale_refusal_names_the_row(series):
    """precondition: same as the bad-row-index test — twelve bars, one bad."""
    with pytest.raises(S.ScriptError) as e:
        _load(
            series,
            [
                _jump(
                    {"label": "ok", "before": 1, "after": 2},
                    {"label": "ok too", "before": 1, "after": 2},
                    {"label": "off the track", "before": 1, "after": 999},
                    scale=70,
                )
            ],
        )
    assert "[2]" in str(e.value)


def test_the_scale_is_read_from_the_beat_not_from_the_rows(series):
    """precondition: R4 negative at the other end — a chart whose scale is
    larger than any of its bars is the normal case (70 for a 65.3 maximum), and
    a check that derived the scale from the rows would make every chart
    full-width and this rule unfalsifiable."""
    script = _load(series, [_jump({"label": "small", "before": 1, "after": 2}, scale=70)])
    assert script.beats[0].fields["scale"] == 70


# --- Phase 4 Task 3: dumbbell rows ----------------------------------------------
#
# Spec §7.1 gives `dumbbell` an unconstrained `rows[]`, and Phase 3 left it that
# way on purpose: the only chart that has ever been drawn builds its rows inline
# in engine/content/2026-08-12.js and the spec does not name their columns. The
# builder arrives in this task, so the columns have to be named now — and they
# are named after that episode, because it is the only evidence there is.
#
# `values` is a PAIR aligned with `series[2]`, not two keys. The two numbers are
# the same measurement of two entities; naming them `a` and `b` would leave the
# reader to remember which entity is which, and `series` already says.


def _engine_dumbbell_rows():
    """The literal rows from engine/content/2026-08-12.js, read from the file.

    Same rule as `_engine_jump_rows`: retyped evidence stops being evidence the
    moment the episode changes, which is exactly when it should complain. The
    episode's fifth column is a boolean `up` flag, and it is deliberately NOT a
    field here — see test_the_gap_is_derived_from_the_values_not_declared.
    """
    src = Path("engine/content/2026-08-12.js").read_text(encoding="utf-8")
    rows = re.findall(
        r"\[\s*'([^']*)'\s*,\s*(\.[\d]+)\s*,\s*(\.[\d]+)\s*,\s*'([^']*)'\s*,"
        r"\s*(true|false)\s*\]",
        src,
    )
    assert rows, "the AMIE dumbbell rows moved out of 2026-08-12.js"
    return [
        {"label": lab, "values": [float(a), float(b)], "note": note}
        for lab, a, b, note, _up in rows
    ]


def test_the_dumbbell_exemplar_is_the_chart_that_actually_rendered():
    """precondition: the AMIE chart is the only dumbbell that exists. If the
    exemplar drifts from it, every test below describes a shape nothing draws."""
    rows = _engine_dumbbell_rows()
    assert len(rows) == 5, rows
    assert VALID["dumbbell"]["rows"][0] == rows[0]
    assert VALID["dumbbell"]["rows"][1] == rows[-1]


def test_the_real_amie_dumbbell_validates(series):
    """precondition: the schema's job is to describe the chart the engine draws,
    all five rows of it — the four that coincide and the one that separates."""
    beat = dict(VALID["dumbbell"], rows=_engine_dumbbell_rows())
    script = _load(series, [beat])
    assert [r["label"] for r in script.beats[0].fields["rows"]][0] == "History-taking"
    assert len(script.beats[0].fields["rows"]) == 5


def test_the_gap_is_derived_from_the_values_not_declared(series):
    """precondition: R3. The episode's row spec carries an `up` boolean saying
    whether the two markers separate, and it is exactly `a !== b` — a second
    source of truth for something the numbers already state. Declared, it can
    disagree with them: `up: false` on a row whose values differ would draw one
    merged marker over two different ratings, which is the hidden-series failure
    R3 exists to prevent, with the schema's blessing."""
    assert "up" not in str(S.BEAT_TYPES["dumbbell"]["required"])
    assert "up" not in S.BEAT_TYPES["dumbbell"]["optional"]
    script = _load(series, [VALID["dumbbell"]])
    assert set(script.beats[0].fields["rows"][0]) == {"label", "values", "note"}


def _dumb(*rows, **over):
    return dict(VALID["dumbbell"], rows=list(rows), **over)


def test_a_dumbbell_row_may_omit_its_note(series):
    """precondition: the note is the row's finding in words ("on par"). Not
    every row has one, and an absent note is an empty cell, not a crash."""
    script = _load(series, [_dumb({"label": "x", "values": [0.4, 0.6]})])
    assert "note" not in script.beats[0].fields["rows"][0]


@pytest.mark.parametrize("index", [0, 1])
def test_a_row_value_above_the_track_is_refused(series, index):
    """precondition: R2's geometry half. A dumbbell has no `scale` field —
    spec §7.1 gives it none — because it has no numeric axis at all: a value IS
    a fraction of the track, and the engine positions each marker at
    `v * 100 + '%'`. 1.4 is drawn 40% past the right edge, off the card. Both
    ends are drawn on the same track, so both have to be checked."""
    values = [0.72, 0.72]
    values[index] = 1.4
    with pytest.raises(S.ScriptError) as e:
        _load(series, [_dumb({"label": "off the track", "values": values})])
    assert "1.4" in str(e.value)


@pytest.mark.parametrize("value", [0, 1])
def test_the_ends_of_the_track_are_legitimate_positions(series, value):
    """precondition: R2 NEGATIVE, and the falsy rule. The interval is [0, 1]
    inclusive: a marker at 0 is drawn at the left end of the track, which is on
    the card, and `if not v` would refuse it."""
    script = _load(series, [_dumb({"label": "at an end", "values": [value, 0.5]})])
    assert script.beats[0].fields["rows"][0]["values"][0] == value


def test_a_negative_position_is_refused(series):
    """precondition: the other end. `-0.2 * 100` is `-20%`, off the left."""
    with pytest.raises(S.ScriptError):
        _load(series, [_dumb({"label": "below zero", "values": [-0.2, 0.5]})])


def test_the_off_track_refusal_names_the_row(series):
    """precondition: same as the jumpChart case — five rows, one bad."""
    with pytest.raises(S.ScriptError) as e:
        _load(
            series,
            [
                _dumb(
                    {"label": "ok", "values": [0.2, 0.2]},
                    {"label": "ok too", "values": [0.3, 0.3]},
                    {"label": "off", "values": [0.3, 9.0]},
                )
            ],
        )
    assert "[2]" in str(e.value)


def test_the_footnote_is_required_on_a_dumbbell(series):
    """precondition: R2 NEGATIVE (M5). Spec §7.2: a dumbbell "encodes direction
    only and must carry a `footnote` saying so". The type renders no numbers, so
    the footnote is the only place the reader is told what the dots mean — an
    optional one makes the chart claim a precision it does not have."""
    assert "footnote" in S.BEAT_TYPES["dumbbell"]["required"]
    beat = {k: v for k, v in VALID["dumbbell"].items() if k != "footnote"}
    with pytest.raises(S.ScriptError) as e:
        _load(series, [beat])
    assert "footnote" in str(e.value)


@pytest.mark.parametrize("kind", sorted(VALID))
def test_each_catalogue_type_validates_with_its_documented_fields(series, kind):
    """precondition: spec §7.1 lists the content fields per type. A beat carrying
    exactly those must load."""
    script = _load(series, [VALID[kind]])
    assert script.beats[0].type == kind
    assert script.beats[0].index == 0


# --- R1: type is drawn from the catalogue --------------------------------------


def test_unknown_type_is_rejected_by_name_and_lists_the_known_ones(series):
    """precondition: R1. An operator who typo'd a type needs to see both what
    they wrote and what was available."""
    with pytest.raises(S.ScriptError) as e:
        _load(series, [{"type": "sparkline", "text": "x"}])
    msg = str(e.value)
    assert "sparkline" in msg
    for known in S.BEAT_TYPES:
        assert known in msg, known


@pytest.mark.parametrize("bad", [0, False, "", [], {}, None, 3.5])
def test_a_non_string_or_missing_type_is_refused(series, bad):
    """precondition: R1 + M4. `type: 0` and `type: ""` are falsy, so a check
    written `if not raw.get("type")` conflates them with an absent key — and a
    check written `raw.get("type") not in BEAT_TYPES` accepts neither. Either
    way the beat must not load."""
    with pytest.raises(S.ScriptError):
        _load(series, [{"type": bad, "text": "x"}])


@pytest.mark.parametrize("bad", [0, False, "", [], {}, 3.5])
def test_a_present_but_falsy_type_is_unknown_not_missing(series, bad):
    """precondition: M4 applied to `type` itself. Added after the mutation
    sweep: `if not kind:` in place of `if kind is None:` still raised, so the
    sibling test above could not see it — and it tells an operator who wrote
    `type: 0` to add a `type` key that is already on the line in front of
    them. Refusing for the wrong reason is its own defect."""
    with pytest.raises(S.ScriptError) as e:
        _load(series, [{"type": bad, "text": "x"}])
    msg = str(e.value)
    assert "unknown type" in msg
    assert "no `type`" not in msg


def test_a_beat_with_no_type_key_says_so(series):
    """precondition: R1/R3. "unknown type None" is a worse message than "no
    type"; the two failures have different fixes."""
    with pytest.raises(S.ScriptError) as e:
        _load(series, [{"text": "typeless"}])
    assert "no `type`" in str(e.value)
    assert "unknown type" not in str(e.value)


@pytest.mark.parametrize("kind", sorted(set(VALID) - {"statement"}))
def test_a_known_but_unrenderable_type_still_loads(series, kind):
    """precondition: R1 negative. Validation and rendering are different gates.
    Every catalogue type must be describable now, whatever Phase 4 can draw."""
    script = _load(series, [VALID[kind]])
    assert script.beats[0].type == kind


def test_plan_refuses_an_unrenderable_type_with_a_different_message(series):
    """precondition: R1 negative + M2. `custom` is a valid beat and an
    unrenderable one. The two failures must not read the same, or an operator
    cannot tell a typo from a not-yet-built feature.

    Phase 4 draws `title`, which this test used to use. The exemplar moved to
    `custom` rather than the assertion being deleted: the gate has to keep
    saying two different things while ANY catalogue type is still unbuilt."""
    ep = create_episode(series, "2026-08-14")
    _write(ep, [VALID["custom"]])
    e = load_episode(series, "2026-08-14")

    S.load_script(e)  # the schema accepts it

    with pytest.raises(PlanError) as err:
        build_plan(series, e)
    msg = str(err.value)
    assert "custom" in msg
    assert "cannot be rendered yet" in msg
    assert "statement" in msg          # what this phase CAN render
    assert "unknown type" not in msg   # the other failure, with the other fix


def test_plan_still_refuses_a_genuinely_unknown_type(series):
    """precondition: M2's mirror. Widening the unrenderable path must not
    swallow the unknown-type path."""
    ep = create_episode(series, "2026-08-14")
    _write(ep, [{"type": "sparkline", "text": "x"}])
    with pytest.raises(PlanError) as err:
        build_plan(series, load_episode(series, "2026-08-14"))
    msg = str(err.value)
    assert "sparkline" in msg
    assert "cannot be rendered yet" not in msg


# --- R2: required fields, present and correctly typed ---------------------------

REQUIRED = [
    ("statement", "text"),
    ("body", "text"),
    ("list", "items"),
    ("kpis", "items"),
    ("jumpChart", "rows"),
    ("jumpChart", "scale"),
    ("jumpChart", "footnote"),
    ("dumbbell", "rows"),
    ("dumbbell", "series"),
    ("dumbbell", "caption"),
    ("dumbbell", "footnote"),
    ("quote", "text"),
    ("quote", "attribution"),
    ("custom", "js"),
]


@pytest.mark.parametrize("kind,field", REQUIRED, ids=[f"{k}.{f}" for k, f in REQUIRED])
def test_a_required_field_is_required(series, kind, field):
    """precondition: R2 + M3. Dropping the check for ONE type is the mutant this
    covers; a single-type test would not see it."""
    beat = {k: v for k, v in VALID[kind].items() if k != field}
    with pytest.raises(S.ScriptError) as e:
        _load(series, [beat])
    assert field in str(e.value)


def test_every_catalogue_type_with_required_fields_is_covered_above():
    """precondition: M3 is 'required-field check dropped for ONE type'. The
    parametrisation above only kills it if it enumerates every type that has
    required fields."""
    declared = {
        (kind, f)
        for kind, spec in S.BEAT_TYPES.items()
        for f in spec["required"]
    }
    assert declared == set(REQUIRED)


OPTIONAL_ONLY = ["title", "signoff"]


@pytest.mark.parametrize("kind", OPTIONAL_ONLY)
def test_a_type_whose_fields_are_all_optional_loads_bare(series, kind):
    """precondition: R2 negative. `title` and `signoff` assert nothing; a bare
    one is a legitimate card, not an incomplete beat."""
    script = _load(series, [{"type": kind}])
    assert script.beats[0].type == kind


# Every wrong-type case below includes falsy values, because a check written
# `if value:` passes on every truthy one.
WRONG_TYPE = [
    ("statement", "text", 0),
    ("statement", "text", False),
    ("statement", "text", ""),
    ("statement", "text", []),
    ("statement", "text", ["a", "b"]),
    ("body", "text", 0),
    ("body", "text", ""),
    ("list", "items", []),          # present, a list, and useless
    ("list", "items", ""),
    ("list", "items", 0),
    ("list", "items", "one item"),  # a string is iterable; it is not a list
    ("list", "items", [""]),
    ("list", "items", [0, False]),
    ("list", "lead", 0),
    ("list", "lead", False),
    ("kpis", "items", []),
    ("kpis", "items", 0),
    ("kpis", "items", [{"value": 1}]),                 # no label
    ("kpis", "items", [{"label": "x"}]),               # no value
    ("kpis", "items", [{"value": 1, "label": ""}]),
    ("kpis", "items", [{"value": 1, "label": "x", "decimals": -1}]),
    ("kpis", "items", [{"value": 1, "label": "x", "decimals": "two"}]),
    ("kpis", "items", [{"value": 1, "label": "x", "decimals": True}]),
    ("kpis", "items", [{"value": 1, "label": "x", "unit": 0}]),
    ("kpis", "items", [{"value": [], "label": "x"}]),
    ("kpis", "items", ["not a mapping"]),
    ("jumpChart", "rows", []),                       # present, a list, no bars
    ("jumpChart", "rows", 0),
    ("jumpChart", "rows", ""),
    ("jumpChart", "rows", False),
    # the pre-D-068 single-bar shape, and the engine's own positional tuple —
    # both are the wrong thing to hand `rows`, and both are truthy
    ("jumpChart", "rows", [{"before": 34.4, "after": 43.6}]),        # no label
    ("jumpChart", "rows", [{"label": "", "before": 34.4, "after": 43.6}]),
    ("jumpChart", "rows", [{"label": 0, "before": 34.4, "after": 43.6}]),
    ("jumpChart", "rows", [{"label": "x", "after": 43.6}]),          # no before
    ("jumpChart", "rows", [{"label": "x", "before": 34.4}]),         # no after
    ("jumpChart", "rows", [{"label": "x", "before": "34.4", "after": 43.6}]),
    ("jumpChart", "rows", [{"label": "x", "before": False, "after": 43.6}]),
    ("jumpChart", "rows", [{"label": "x", "before": 34.4, "after": True}]),
    ("jumpChart", "rows", [{"label": "x", "before": 34.4, "after": ""}]),
    ("jumpChart", "rows", [{"label": "x", "before": 0, "after": 1, "shown": 0}]),
    ("jumpChart", "rows", [["FrontierCode 1.1", 34.4, 43.6, "…"]]),  # engine tuple
    ("jumpChart", "scale", 0),
    ("jumpChart", "scale", False),
    ("jumpChart", "scale", -70),
    ("jumpChart", "footnote", 0),
    ("jumpChart", "footnote", ""),
    ("dumbbell", "rows", []),
    ("dumbbell", "rows", 0),
    ("dumbbell", "rows", ""),
    # the engine's own positional tuple: readable to the renderer, unreadable to
    # the operator who has to notice a swapped pair
    ("dumbbell", "rows", [["History-taking", 0.72, 0.72, "on par"]]),
    ("dumbbell", "rows", [{"values": [0.72, 0.72]}]),               # no label
    ("dumbbell", "rows", [{"label": "", "values": [0.72, 0.72]}]),
    ("dumbbell", "rows", [{"label": 0, "values": [0.72, 0.72]}]),
    ("dumbbell", "rows", [{"label": "x"}]),                         # no values
    ("dumbbell", "rows", [{"label": "x", "values": [0.72]}]),       # only one
    ("dumbbell", "rows", [{"label": "x", "values": [0.7, 0.7, 0.7]}]),
    ("dumbbell", "rows", [{"label": "x", "values": "0.7"}]),
    ("dumbbell", "rows", [{"label": "x", "values": [0.7, "0.7"]}]),
    ("dumbbell", "rows", [{"label": "x", "values": [0.7, True]}]),
    ("dumbbell", "rows", [{"label": "x", "values": [False, 0.7]}]),
    ("dumbbell", "rows", [{"label": "x", "values": [0.7, 0.7], "note": 0}]),
    ("dumbbell", "series", []),
    ("dumbbell", "series", ["only one"]),
    ("dumbbell", "series", ["a", "b", "c"]),
    ("dumbbell", "series", [0, False]),
    ("dumbbell", "caption", 0),
    ("dumbbell", "footnote", ""),
    ("quote", "text", ""),
    ("quote", "text", 0),
    ("quote", "attribution", False),
    ("quote", "attribution", ""),
    ("title", "sub", 0),
    ("title", "sub", False),
    ("title", "sub", []),
    ("signoff", "text", 0),
    ("signoff", "text", False),
    ("custom", "js", ""),
    ("custom", "js", 0),
    ("custom", "js", False),
]


@pytest.mark.parametrize(
    "kind,field,bad", WRONG_TYPE, ids=[f"{k}.{f}={v!r}" for k, f, v in WRONG_TYPE]
)
def test_a_wrongly_typed_field_is_refused(series, kind, field, bad):
    """precondition: R2 + M4. Present-but-wrong-typed is an error, and falsy is
    not the same as absent."""
    beat = dict(VALID[kind])
    beat[field] = bad
    with pytest.raises(S.ScriptError) as e:
        _load(series, [beat])
    assert field in str(e.value)


def test_the_wrong_type_table_contains_falsy_values_for_every_field_it_covers():
    """precondition: Task 0's sweep survived because every bad value chosen was
    truthy. This is the guard that stops that recurring silently."""
    falsy = {(k, f) for k, f, v in WRONG_TYPE if not v}
    covered = {(k, f) for k, f, v in WRONG_TYPE}
    assert falsy == covered, sorted(covered - falsy)


def test_an_empty_string_is_valid_where_the_field_is_decorative(series):
    """precondition: R2. `sub: ""` is a title card with no subtitle — a real
    thing an operator writes. It must not be conflated with a missing field or
    with an invalid one."""
    script = _load(series, [{"type": "title", "sub": ""}])
    assert script.beats[0].fields["sub"] == ""


def test_an_absent_optional_field_is_absent_not_empty(series):
    """precondition: R2. Phase 5 has to tell "the operator wrote nothing" from
    "the operator wrote an empty subtitle"; collapsing both to "" destroys
    that."""
    script = _load(series, [{"type": "title"}])
    assert "sub" not in script.beats[0].fields


def test_a_beat_that_is_not_a_mapping_is_refused(series):
    """precondition: `- statement` under `beats:` is a plausible typo."""
    with pytest.raises(S.ScriptError, match="mapping"):
        _load(series, ["statement"])


# --- shared optional fields (spec §7.1, "shared optional fields on every type")


SHARED_WRONG = [
    ("act", 0),
    ("act", False),
    ("act", []),
    ("kicker", 0),
    ("kicker", False),
    ("kicker", []),
    ("src", 0),
    ("src", False),
    ("quote", 0),
    ("quote", []),
    ("claim_override", 0),
    ("claim_override", False),
    ("hold", 0),
    ("hold", 0.0),
    ("hold", False),
    ("hold", ""),
    ("hold", -3.0),
    ("hold", "3.0"),
]


@pytest.mark.parametrize(
    "field,bad", SHARED_WRONG, ids=[f"{f}={v!r}" for f, v in SHARED_WRONG]
)
def test_a_wrongly_typed_shared_field_is_refused(series, field, bad):
    """precondition: R2. The shared fields are on every type, so a missed check
    here is missed ten times over. `hold: 0` is invalid even though `kicker: ""`
    is fine — falsy is not one rule."""
    beat = dict(VALID["statement"])
    beat[field] = bad
    with pytest.raises(S.ScriptError) as e:
        _load(series, [beat])
    assert field in str(e.value)


@pytest.mark.parametrize("field", ["act", "kicker", "src", "quote", "claim_override"])
def test_an_empty_shared_string_field_is_accepted(series, field):
    """precondition: R2 negative + M4. These are decorative or advisory; `""`
    is a legitimate value and only an `is not None` check accepts it."""
    beat = dict(VALID["statement"])
    beat[field] = ""
    script = _load(series, [beat])
    assert script.beats[0].type == "statement"


def test_hold_defaults_and_is_not_invented_when_present(series):
    """precondition: plan.py has defaulted an absent hold to 3.0 since Phase 1;
    moving the schema must not move that number."""
    script = _load(series, [VALID["statement"], dict(VALID["body"], hold=4.5)])
    assert script.beats[0].hold == S.DEFAULT_HOLD == 3.0
    assert script.beats[1].hold == 4.5


def test_shared_fields_land_on_the_beat_not_in_the_payload(series):
    """precondition: the Beat dataclass names act/kicker/src/quote, so Phase 5
    can walk them without knowing the type. Absent ones default to ""."""
    beat = dict(VALID["statement"], act="01", kicker="Today's headline", src="blog.google", quote="q")
    script = _load(series, [beat, VALID["body"]])
    b0, b1 = script.beats
    assert (b0.act, b0.kicker, b0.src, b0.quote) == (
        "01",
        "Today's headline",
        "blog.google",
        "q",
    )
    assert (b1.act, b1.kicker, b1.src, b1.quote) == ("", "", "", "")


# --- R3: errors name the beat index AND the type --------------------------------


def test_an_error_names_the_beat_index_and_the_type(series):
    """precondition: R3. "text is required" against a twelve-beat script does
    not tell an operator which line to open."""
    beats = [dict(VALID["statement"]) for _ in range(12)]
    beats[9] = {"type": "quote", "text": "x"}   # missing `attribution`
    with pytest.raises(S.ScriptError) as e:
        _load(series, beats)
    msg = str(e.value)
    assert "beat 9" in msg
    assert "quote" in msg
    assert "attribution" in msg


def test_the_index_in_the_message_is_the_beat_position_not_a_constant(series):
    """precondition: M5's subtler form — a message that always says "beat 0"
    contains an index and is still useless."""
    beats = [dict(VALID["statement"]) for _ in range(4)]
    beats[3] = {"type": "statement"}
    with pytest.raises(S.ScriptError) as e:
        _load(series, beats)
    assert "beat 3" in str(e.value)
    assert "beat 0" not in str(e.value)


def test_the_unknown_type_error_also_names_the_index(series):
    """precondition: R3 applies to every beat-level failure, not just field
    ones."""
    beats = [dict(VALID["statement"]), {"type": "sparkline"}]
    with pytest.raises(S.ScriptError) as e:
        _load(series, beats)
    assert "beat 1" in str(e.value)


def test_beats_are_indexed_in_file_order(series):
    """precondition: the index in the message and the index on the Beat must be
    the same number, or Phase 5's claim anchors point at the wrong beat."""
    script = _load(series, [VALID["statement"], VALID["body"], VALID["title"]])
    assert [b.index for b in script.beats] == [0, 1, 2]
    assert [b.type for b in script.beats] == ["statement", "body", "title"]


# --- R4: charts must cite (spec §7.2) -------------------------------------------


CITED = ["kpis", "jumpChart"]


@pytest.mark.parametrize("kind", CITED)
@pytest.mark.parametrize("field", ["src", "quote"])
def test_a_chart_without_a_source_is_refused(series, kind, field):
    """precondition: spec §7.2 — "there is no path to rendering a number that
    isn't in a source"."""
    beat = {k: v for k, v in VALID[kind].items() if k != field}
    with pytest.raises(S.ScriptError) as e:
        _load(series, [beat])
    assert field in str(e.value)


@pytest.mark.parametrize("kind", CITED)
@pytest.mark.parametrize("field", ["src", "quote"])
@pytest.mark.parametrize("bad", ["", 0, False, []])
def test_a_chart_whose_source_is_empty_is_refused(series, kind, field, bad):
    """precondition: R4 + M4. `src: ""` satisfies "the key is present" and cites
    nothing. A citation that is falsy is not a citation."""
    beat = dict(VALID[kind])
    beat[field] = bad
    with pytest.raises(S.ScriptError) as e:
        _load(series, [beat])
    assert field in str(e.value)


UNCITED = ["statement", "body", "list", "quote", "title", "signoff", "custom", "dumbbell"]


@pytest.mark.parametrize("kind", UNCITED)
def test_a_non_chart_type_needs_no_citation(series, kind):
    """precondition: R4 negative + M7. `title` asserts nothing about the world;
    demanding a source for it would make the requirement noise, and operators
    would start pasting a source in to shut it up."""
    beat = {k: v for k, v in VALID[kind].items() if k not in ("src", "quote")}
    script = _load(series, [beat])
    assert script.beats[0].src == ""
    assert script.beats[0].quote == ""


def test_the_cited_types_are_exactly_the_two_the_spec_names():
    """precondition: R4 names kpis and jumpChart. If a third type quietly joined
    them, test_a_non_chart_type_needs_no_citation would be the thing to update,
    not this — so pin the set directly."""
    cited = {k for k, spec in S.BEAT_TYPES.items() if spec["cited"]}
    assert cited == {"kpis", "jumpChart"}
    assert set(UNCITED) == set(S.BEAT_TYPES) - cited


# --- R5: acts[] in series.toml --------------------------------------------------


def test_wellformed_acts_validate():
    """precondition: R5, and spec §6's own example."""
    S.validate_acts(
        [
            {"id": "cold-open", "label": "", "beats": 2},
            {"id": "01", "label": "01 — The headline", "beats": 6},
            {"id": "02"},
        ],
        "series.toml",
    )


def test_no_acts_at_all_is_fine():
    """precondition: the scaffold writes `acts` commented out — a brand new
    series has none and must still load."""
    S.validate_acts([], "series.toml")


@pytest.mark.parametrize("bad", [0, False, [], {}, None, 3.5, ["01"]])
def test_an_act_with_a_non_string_id_is_refused(bad):
    """precondition: R5 + M4/M8. Falsy ids (0, False, []) are the ones a
    truthiness check silently rejects for the wrong reason and a missing check
    accepts. `""` is deliberately NOT in this list — it is a string, R5 asks for
    a string, and it is the falsy-but-valid case that separates
    `isinstance(id, str)` from `if id:` (see the sibling test below). Having it
    in both lists was a contradiction in the RED commit; this is the fix."""
    with pytest.raises(S.ScriptError) as e:
        S.validate_acts([{"id": bad}], "series.toml")
    assert "id" in str(e.value)


def test_an_act_with_no_id_is_refused():
    """precondition: R5. An act with no id cannot be referenced by a beat."""
    with pytest.raises(S.ScriptError) as e:
        S.validate_acts([{"label": "01 — The headline", "beats": 6}], "series.toml")
    assert "id" in str(e.value)


def test_an_empty_string_id_is_accepted():
    """precondition: R5's letter — "each needs a string `id`". Both committed
    episodes open with `scene('', ...)`: the cold open genuinely has no act
    name. This is the falsy-but-valid case that distinguishes
    `isinstance(id, str)` from `if id`."""
    S.validate_acts([{"id": ""}], "series.toml")


BAD_BEATS = ["six", -1, 0, True, False, 1.5, "", [], {}, None, "6"]


@pytest.mark.parametrize("bad", BAD_BEATS, ids=[repr(b) for b in BAD_BEATS])
def test_an_act_beats_count_must_be_a_positive_integer(bad):
    """precondition: R5 + M9. `beats = 0` and `beats = -1` are the arithmetic
    ones; `True` is an int in Python and is not a beat count; "6" is what you
    get from quoting a number in TOML."""
    with pytest.raises(S.ScriptError) as e:
        S.validate_acts([{"id": "01", "beats": bad}], "series.toml")
    assert "beats" in str(e.value)


def test_an_act_without_beats_is_fine():
    """precondition: R5 negative — spec §6 calls beats counts advisory."""
    S.validate_acts([{"id": "01", "label": "One"}], "series.toml")


def test_a_label_is_optional_and_free_form():
    """precondition: R5 negative. `label = ""` is what the spec's own cold-open
    row carries."""
    S.validate_acts([{"id": "01"}], "series.toml")
    S.validate_acts([{"id": "01", "label": ""}], "series.toml")
    S.validate_acts([{"id": "01", "label": "01 — The headline"}], "series.toml")


@pytest.mark.parametrize("bad", ["", 0, False, [], None, ["01"]])
def test_an_act_that_is_not_a_mapping_is_refused(bad):
    """precondition: R5/M8. `acts = ["01", "02"]` is the shape somebody writes
    when they forget [[structure.acts]]."""
    with pytest.raises(S.ScriptError):
        S.validate_acts([bad], "series.toml")


def test_the_act_error_names_the_position_and_the_file():
    """precondition: R3's spirit applied to acts — a series.toml with five acts
    needs to say which one."""
    with pytest.raises(S.ScriptError) as e:
        S.validate_acts(
            [{"id": "01"}, {"id": "02"}, {"id": 3}], "/tmp/the-brief/series.toml"
        )
    msg = str(e.value)
    assert "2" in msg
    assert "/tmp/the-brief/series.toml" in msg


def test_a_malformed_act_stops_plan_building(series):
    """precondition: R5 is only enforced if somebody calls it. build_plan is the
    consumer that holds both the series and the episode, and it is the last gate
    before bytes reach Node."""
    from dataclasses import replace

    ep = create_episode(series, "2026-08-14")
    _write(ep, [VALID["statement"]])
    bad_series = replace(series, acts=[{"label": "no id here", "beats": 6}])
    with pytest.raises(PlanError, match="id"):
        build_plan(bad_series, load_episode(series, "2026-08-14"))


def test_wellformed_acts_do_not_stop_plan_building(series):
    """precondition: the mirror of the above — validating acts must not make a
    healthy series unrenderable."""
    from dataclasses import replace

    ep = create_episode(series, "2026-08-14")
    _write(ep, [VALID["statement"]])
    ok = replace(series, acts=[{"id": "01", "label": "One", "beats": 6}])
    assert build_plan(ok, load_episode(series, "2026-08-14"))["beats"]


# --- R6: validation never writes ------------------------------------------------


def test_load_script_leaves_the_file_byte_identical(series):
    """precondition: D-026 — script.yaml's bytes are load-bearing for
    script_sha256. A script with comments, quoting and blank lines is the case
    that a `_compose`-based rewrite would visibly damage; one that round-trips
    through safe_dump unchanged would hide it."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\n# storyboard: do not reflow\nepisode: e\nseries: the-brief\n"
        'status: "draft"\npace: 1.293\n\n---\n'
        "beats:\n"
        "  # the cold open\n"
        "  - type: statement\n"
        "    hold:   3.0\n"
        "    text: 'Google shipped its main agentic model.'\n"
        "\n"
        "  - type: title\n"
        '    sub: ""\n',
        encoding="utf-8",
    )
    before = ep.script_path.read_bytes()
    script = S.load_script(load_episode(series, "2026-08-14"))
    assert len(script.beats) == 2
    assert ep.script_path.read_bytes() == before


def test_loading_a_script_twice_is_stable(series):
    """precondition: R6. A validator that normalised on read would produce a
    different file the second time round, and the hash would drift on nothing."""
    ep = create_episode(series, "2026-08-14")
    _write(ep, [VALID["statement"], VALID["kpis"]])
    first = ep.script_path.read_bytes()
    S.load_script(load_episode(series, "2026-08-14"))
    S.load_script(load_episode(series, "2026-08-14"))
    assert ep.script_path.read_bytes() == first


def test_a_failed_validation_leaves_the_file_alone(series):
    """precondition: R6. The tempting place to "fix up" a script is exactly
    where it failed."""
    ep = create_episode(series, "2026-08-14")
    _write(ep, [{"type": "statement"}])
    before = ep.script_path.read_bytes()
    with pytest.raises(S.ScriptError):
        S.load_script(load_episode(series, "2026-08-14"))
    assert ep.script_path.read_bytes() == before


# --- the Script envelope --------------------------------------------------------


def test_script_carries_the_metadata_from_the_file(series):
    """precondition: the metadata document is document 1; Phase 5 reads status
    and pace off the Script rather than re-parsing."""
    script = _load(series, [VALID["statement"]], meta_extra="pace: 1.293\n")
    assert script.episode == "e"
    assert script.series == "the-brief"
    assert script.status == "draft"
    assert script.pace == 1.293


def test_pace_defaults_to_one(series):
    """precondition: pace is written by `agsoc video review`, so a script that
    has not been reviewed yet has none."""
    assert _load(series, [VALID["statement"]]).pace == 1.0


@pytest.mark.parametrize("bad", [0, 0.0, False, "", -1, "1.2", [], None])
def test_a_non_positive_pace_is_refused(series, bad):
    """precondition: pace multiplies every hold. A zero or negative pace is a
    zero-length video, not a fast one."""
    with pytest.raises(S.ScriptError, match="pace"):
        _load(series, [VALID["statement"]], meta_extra=f"pace: {bad!r}\n")


def test_an_empty_beats_document_is_refused(series):
    """precondition: an episode with no beats renders nothing; that is a script
    error, not an empty video."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: e\nseries: the-brief\nstatus: draft\n---\nbeats: []\n",
        encoding="utf-8",
    )
    with pytest.raises(S.ScriptError, match="no beats"):
        S.load_script(load_episode(series, "2026-08-14"))


def test_beats_must_be_a_list(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: e\nseries: the-brief\nstatus: draft\n---\nbeats: a string\n",
        encoding="utf-8",
    )
    with pytest.raises(S.ScriptError, match="list"):
        S.load_script(load_episode(series, "2026-08-14"))


def test_a_missing_beats_document_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "episode: e\nseries: the-brief\nstatus: draft\n", encoding="utf-8"
    )
    with pytest.raises(S.ScriptError):
        S.load_script(load_episode(series, "2026-08-14"))


def test_unparseable_beats_raise_script_error(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: e\nseries: the-brief\nstatus: draft\n---\nbeats: [unclosed\n  : : :\n",
        encoding="utf-8",
    )
    with pytest.raises(S.ScriptError):
        S.load_script(load_episode(series, "2026-08-14"))


# --- D-062: a snapshot that mutates lies about its file -------------------------


def test_beat_is_frozen(series):
    script = _load(series, [VALID["statement"]])
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        script.beats[0].hold = 99.0


def test_script_is_frozen(series):
    script = _load(series, [VALID["statement"]])
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        script.pace = 99.0


def test_beats_is_a_tuple(series):
    """precondition: D-062. A frozen dataclass holding a list is not frozen."""
    script = _load(series, [VALID["statement"]])
    assert isinstance(script.beats, tuple)


# --- the payload Phase 5 walks --------------------------------------------------


def test_the_payload_carries_the_type_specific_fields(series):
    """precondition: Phase 5 walks beats as data. `fields` is the type-specific
    half, already validated."""
    script = _load(series, [VALID["kpis"]])
    items = script.beats[0].fields["items"]
    assert items[0]["value"] == 0.75
    assert items[0]["label"] == "per 1M input tokens"


def test_the_payload_does_not_repeat_the_shared_fields(series):
    """precondition: two homes for `src` is two answers when they disagree."""
    beat = dict(VALID["statement"], act="01", kicker="k", src="s", quote="q", hold=4.0)
    fields = _load(series, [beat]).beats[0].fields
    for shared in ("act", "kicker", "src", "quote", "hold", "type"):
        assert shared not in fields, shared
    assert fields["text"] == VALID["statement"]["text"]

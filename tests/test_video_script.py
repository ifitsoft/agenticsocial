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
    "jumpChart": {
        "type": "jumpChart",
        "before": 34.4,
        "after": 43.6,
        "scale": 70,
        "footnote": "Scores as published by Google, on a common 0-70% scale.",
        "src": "deepmind",
        "quote": "FrontierCode 1.1 rises from 34.4 to 43.6",
    },
    "dumbbell": {
        "type": "dumbbell",
        "rows": [
            ["History-taking", 0.72, 0.72, "on par"],
            ["Eliciting physical signs", 0.82, 0.58, "rated higher"],
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


def test_renderable_is_exactly_statement_for_this_phase():
    """precondition: Phase 3 renders one beat type. This pins the gate so that
    widening it is a deliberate edit."""
    assert S.RENDERABLE == frozenset({"statement"})


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
    """precondition: R1 negative + M2. `title` is a valid beat and an
    unrenderable one. The two failures must not read the same, or an operator
    cannot tell a typo from a not-yet-built feature."""
    ep = create_episode(series, "2026-08-14")
    _write(ep, [VALID["title"]])
    e = load_episode(series, "2026-08-14")

    S.load_script(e)  # the schema accepts it

    with pytest.raises(PlanError) as err:
        build_plan(series, e)
    msg = str(err.value)
    assert "title" in msg
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
    ("jumpChart", "before"),
    ("jumpChart", "after"),
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
    ("jumpChart", "before", ""),
    ("jumpChart", "before", False),
    ("jumpChart", "before", []),
    ("jumpChart", "before", "34.4"),
    ("jumpChart", "after", False),
    ("jumpChart", "scale", 0),
    ("jumpChart", "scale", False),
    ("jumpChart", "scale", -70),
    ("jumpChart", "footnote", 0),
    ("jumpChart", "footnote", ""),
    ("dumbbell", "rows", []),
    ("dumbbell", "rows", 0),
    ("dumbbell", "rows", ""),
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


@pytest.mark.parametrize("bad", [0, False, "", [], {}, None, 3.5, ["01"]])
def test_an_act_with_a_non_string_id_is_refused(bad):
    """precondition: R5 + M4/M8. Falsy ids (0, False, []) are the ones a
    truthiness check silently rejects for the wrong reason and a missing check
    accepts."""
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

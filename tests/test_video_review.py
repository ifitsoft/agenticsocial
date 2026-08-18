"""`check_runtime` and `agsoc video review` — spec §11's report, not its gate.

Two things this file is deliberate about:

  * `review` is a REPORT. It exits 0 whether the runtime is in tolerance or
    out. A diagnostic command that refuses to speak when something is wrong is
    the D-018 mistake wearing a new hat, and the operator loses the one screen
    that was going to tell them what is wrong.
  * the gate reads the FILE (D-063). Every earlier bypass in this project was a
    trusted in-memory object; the predicted next one is a gate reading a stale
    `series.target_sec`. The stale-object test here is written at the CLI level
    because that is where "callers load fresh" is either true or a story.

Every "wrong value" case includes falsy values (0, False, "", []). `tolerance_sec:
0` is the one that matters most: it is a legitimate setting meaning "match
target_sec exactly", and an implementation written `if tolerance:` reads it as
"no limit" — the most permissive possible misreading of the strictest possible
setting.
"""
import itertools
import re

import pytest
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import cli as video_cli
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.plan import RuntimeCheck, check_runtime
from agenticsocial.video.script import BEAT_TYPES, RENDERABLE, load_script
from agenticsocial.video.series import load_series, scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()


def run(*args):
    """Invoke the CLI with exceptions propagating — see D-035."""
    return runner.invoke(app, list(args), catch_exceptions=False)


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


# --- fixtures ------------------------------------------------------------------


def statements(holds):
    return [
        {"type": "statement", "hold": h, "text": f"Beat {i} of the episode."}
        for i, h in enumerate(holds)
    ]


def write(ep, beats, pace=None, status="draft"):
    # The id is QUOTED. `episode: 2026-08-17` unquoted is a YAML date, not a
    # string, and script.py refuses it — which is what `agsoc video new` avoids
    # by writing the metadata through yaml.safe_dump.
    meta = f"episode: '{ep.id}'\nseries: the-brief\nstatus: {status}\n"
    if pace is not None:
        meta += f"pace: {pace}\n"
    body = yaml.safe_dump({"beats": beats}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(f"---\n{meta}---\n{body}", encoding="utf-8")


def episode(series, beats, pace=None, ep_id="2026-08-17", status="draft"):
    ep = create_episode(series, ep_id)
    write(ep, beats, pace=pace, status=status)
    return load_episode(series, ep_id)


_seq = itertools.count(1)


def runtime(series, ws, beats, pace=None, **toml):
    """Build an episode, retune series.toml, and check — reloading the series
    from disk so the fixture cannot hand the check a value the file disagrees
    with. Episode ids are unique so one test can build several."""
    ep = episode(series, beats, pace=pace, ep_id=f"2026-08-{next(_seq):02d}")
    if toml:
        retune(series, **toml)
    return check_runtime(load_script(ep), load_series(ws, series.slug))


def retune(series, **runtime_keys):
    """Rewrite [runtime] in series.toml. The file is the authority (D-063), so
    tests change the file, never the object."""
    path = series.dir / "series.toml"
    text = path.read_text(encoding="utf-8")
    for key, value in runtime_keys.items():
        text = re.sub(rf"(?m)^{key}\s*=.*$", f"{key} = {value}", text)
    path.write_text(text, encoding="utf-8")


TWELVE = statements([10.0] * 12)  # 120.0s at pace 1.0 — exactly the default target


# --- R1: total runtime is sum(hold) * pace -------------------------------------


def test_the_total_is_the_sum_of_the_holds(series, ws):
    """precondition: R1. At pace 1.0 the total is just the arithmetic."""
    check = runtime(series, ws, statements([3.5, 3.0, 4.0]))
    assert check.total_sec == pytest.approx(10.5)


def test_the_total_is_scaled_by_pace(series, ws):
    """precondition: R1 + M1. `pace` is the whole point of the field — a total
    that ignores it reports a 60s episode as a 120s one and an operator
    approves a render that is half the length they asked for."""
    check = runtime(series, ws, statements([3.5, 3.0, 4.0]), pace=2.0)
    assert check.total_sec == pytest.approx(21.0)


def test_a_pace_below_one_shortens_the_total(series, ws):
    """precondition: R1 + M1's mirror. A total computed as `sum(hold) + pace`
    or `sum(hold)` survives a pace of 2.0 being wrong in only one direction;
    0.5 pins the operation as multiplication."""
    check = runtime(series, ws, statements([4.0, 4.0]), pace=0.5)
    assert check.total_sec == pytest.approx(4.0)


def test_the_default_hold_counts_toward_the_total(series, ws):
    """precondition: R1. A beat with no `hold` still occupies DEFAULT_HOLD
    seconds of the runtime; skipping it under-reports the episode."""
    check = runtime(series, ws, [{"type": "statement", "text": "No hold written."}])
    assert check.total_sec == pytest.approx(3.0)


# --- R2: tolerance is inclusive, and 0 means exact -------------------------------


def test_dead_on_target_is_within_tolerance(series, ws):
    """precondition: R2."""
    check = runtime(series, ws, TWELVE, target_sec=120, tolerance_sec=8)
    assert check.total_sec == pytest.approx(120.0)
    assert check.delta == pytest.approx(0.0)
    assert check.within is True


def test_exactly_at_the_upper_bound_is_within_tolerance(series, ws):
    """precondition: R2 negative + M3. `abs(delta) <= tolerance`, inclusive. A
    `<` here fails an episode that hits the documented bound exactly, and the
    operator's fix is to edit a script that was already correct."""
    check = runtime(series, ws, statements([16.0] * 8), target_sec=120, tolerance_sec=8)
    assert check.total_sec == pytest.approx(128.0)
    assert check.delta == pytest.approx(8.0)
    assert check.within is True


def test_exactly_at_the_lower_bound_is_within_tolerance(series, ws):
    """precondition: R2 negative + M3, on the other side. A `<` written as
    `delta < tolerance` and a `>` written `-delta > -tolerance` fail
    differently; both bounds get pinned."""
    check = runtime(series, ws, statements([14.0] * 8), target_sec=120, tolerance_sec=8)
    assert check.delta == pytest.approx(-8.0)
    assert check.within is True


def test_one_tick_over_the_bound_is_out_of_tolerance(series, ws):
    """precondition: R2 + M4. `within` hardcoded True survives every test that
    only ever checks in-tolerance scripts."""
    check = runtime(series, ws, statements([16.1] * 8), target_sec=120, tolerance_sec=8)
    assert check.total_sec == pytest.approx(128.8)
    assert check.within is False


def test_far_out_of_tolerance_is_out_of_tolerance(series, ws):
    """precondition: M4. The unmissable case, so that a failure here says the
    comparison is broken rather than the rounding."""
    check = runtime(series, ws, statements([30.0] * 12), target_sec=120, tolerance_sec=8)
    assert check.within is False
    assert check.delta == pytest.approx(240.0)


def test_a_zero_tolerance_demands_exactness(series, ws):
    """precondition: R2 negative + M5. `tolerance_sec = 0` is legitimate and
    means "match target_sec exactly". An implementation written `if tolerance:`
    or `tolerance or DEFAULT` reads the strictest setting in the file as the
    most permissive one — and series.py deliberately allows 0, so this reaches
    the check."""
    check = runtime(series, ws, statements([10.0] * 12), target_sec=120, tolerance_sec=0)
    assert check.tolerance_sec == 0
    assert check.within is True


def test_a_zero_tolerance_refuses_a_near_miss(series, ws):
    """precondition: M5. 121.2s against a 120s target with tolerance 0 is out.
    Treating 0 as "no limit" passes it."""
    check = runtime(series, ws, statements([10.1] * 12), target_sec=120, tolerance_sec=0)
    assert check.total_sec == pytest.approx(121.2)
    assert check.within is False


def test_the_delta_is_signed(series, ws):
    """precondition: the interface says "total - target, signed". An operator
    needs to know whether to cut or to add; `abs()` here loses that."""
    short = runtime(series, ws, statements([5.0] * 12), target_sec=120)
    assert short.delta == pytest.approx(-60.0)
    over = runtime(series, ws, statements([15.0] * 12), target_sec=120)
    assert over.delta == pytest.approx(60.0)


def test_the_check_reports_the_target_and_tolerance_it_used(series, ws):
    """precondition: R3. The verdict is unreadable without the numbers behind
    it — "out of tolerance" against an unstated target is not a report."""
    check = runtime(series, ws, TWELVE, target_sec=90, tolerance_sec=3)
    assert check.target_sec == 90
    assert check.tolerance_sec == 3


def test_runtimecheck_is_frozen():
    """precondition: D-062. A check result that can be edited after the fact is
    not a check result; Phase 7 refuses on this object."""
    check = RuntimeCheck(
        total_sec=1.0, target_sec=1, tolerance_sec=0, within=True, delta=0.0
    )
    with pytest.raises(Exception):
        check.within = False  # type: ignore[misc]


# --- R6 / D-063: the check follows the file, not a cached object -----------------


def test_check_runtime_does_not_cache_the_series(series, ws):
    """precondition: R6 + M10. Two calls with two different series must give
    two different answers. A module-level cache keyed on anything — slug, path,
    nothing at all — makes the second call report the first call's target."""
    ep = episode(series, TWELVE)
    script = load_script(ep)

    retune(series, target_sec=120, tolerance_sec=8)
    first = check_runtime(script, load_series(ws, "the-brief"))

    retune(series, target_sec=60, tolerance_sec=1)
    second = check_runtime(script, load_series(ws, "the-brief"))

    assert first.target_sec == 120 and first.within is True
    assert second.target_sec == 60 and second.within is False


def test_review_follows_series_toml_between_two_invocations(ws):
    """precondition: D-063, at the level where it is either true or a story.

    The Phase 2 prediction was: "the next bypass will be a Phase 3 gate that
    reads a stale `series.target_sec` instead of re-reading disk". This changes
    the file between two `review` runs and asserts the second answer is the
    file's, not the first run's.
    """
    run("series", "new", "the-brief")
    run("video", "new", "2026-08-17", "--series", "the-brief")
    s = load_series(ws, "the-brief")
    write(load_episode(s, "2026-08-17"), TWELVE)

    retune(s, target_sec=120, tolerance_sec=8)
    first = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert first.exit_code == 0
    assert "120s" in first.output
    assert "within tolerance" in first.output.lower()

    retune(s, target_sec=60, tolerance_sec=1)
    second = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert second.exit_code == 0
    assert "60s" in second.output
    assert "out of tolerance" in second.output.lower()
    assert "within tolerance" not in second.output.lower()


def test_review_follows_the_script_between_two_invocations(ws):
    """precondition: R6's other half. The script is a file too, and a cached
    Script is the same bug with a different noun."""
    run("series", "new", "the-brief")
    run("video", "new", "2026-08-17", "--series", "the-brief")
    s = load_series(ws, "the-brief")
    ep = load_episode(s, "2026-08-17")

    write(ep, TWELVE)
    first = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert "12 beats" in first.output

    write(ep, statements([10.0] * 3))
    second = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert "3 beats" in second.output
    assert "12 beats" not in second.output


# --- R3: review reports, and exits 0 either way ---------------------------------


def test_review_reports_the_numbers(ws, series):
    """precondition: R3. beats, holds, total, target, tolerance, verdict — the
    information is not optional."""
    episode(series, statements([3.5, 3.0, 4.0]))
    retune(series, target_sec=11, tolerance_sec=2)
    result = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 0
    out = result.output
    assert "the-brief/2026-08-17" in out
    assert "draft" in out
    assert "3 beats" in out
    for hold in ("3.5", "3.0", "4.0"):
        assert hold in out
    assert "10.5" in out          # the total
    assert "11s" in out           # the target
    assert "2s" in out            # the tolerance
    assert "within tolerance" in out.lower()


def test_review_exits_zero_when_out_of_tolerance(ws, series):
    """precondition: R3 negative + M6. This is THE rule of this command. An
    exit 1 here turns the one screen that explains the problem into a screen
    the operator's shell treats as a failure — and Phase 7's `approve` is where
    the refusal belongs."""
    episode(series, statements([30.0] * 12))
    result = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 0
    assert "out of tolerance" in result.output.lower()


def test_review_says_out_of_tolerance_rather_than_staying_silent(ws, series):
    """precondition: M4 at the CLI. Exiting 0 must not be achieved by not
    noticing."""
    episode(series, statements([30.0] * 12))
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output.lower()
    assert "within tolerance" not in out


def test_review_shows_the_signed_delta(ws, series):
    """precondition: R3. "out of tolerance" without "by how much" sends the
    operator to a calculator."""
    episode(series, statements([30.0] * 12))          # 360s against 120s
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "+240" in out


def test_review_shows_the_pace_it_applied(ws, series):
    """precondition: R1 + R3. The holds shown are unscaled, so without the pace
    on screen the arithmetic in front of the operator does not add up."""
    episode(series, statements([5.0] * 12), pace=2.0)
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "2.0" in out
    assert "120" in out


# --- R1 negative: the displayed holds are the AUTHORED ones ----------------------


def test_review_displays_unscaled_holds(ws, series):
    """precondition: R1 negative + M2. The operator edits `hold: 3.5` in
    script.yaml. Showing them 7.0 because pace is 2.0 means the number on
    screen appears nowhere in the file they are about to edit."""
    episode(series, statements([3.5, 3.0, 4.0]), pace=2.0)
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    table = out.split("runtime")[0]
    assert "3.5" in table
    assert "7.0" not in table
    assert "6.0" not in table
    assert "8.0" not in table


def test_review_still_reports_the_scaled_total(ws, series):
    """precondition: R1 negative's other half. Unscaled per-beat, scaled total —
    the display must not "fix" the inconsistency by unscaling the total too."""
    episode(series, statements([3.5, 3.0, 4.0]), pace=2.0)
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "21.0" in out


# --- R4: beats that validate but cannot render ----------------------------------


# Phase 4 Task 3's exit criterion, asserted where the operator's screen is
# tested: there is nothing left in the catalogue that cannot be drawn. The
# `!` margin, the footer and their tests survive by injecting a narrower gate —
# see test_review_names_the_unrenderable_beats on why they are not deleted.
def test_every_catalogue_type_can_be_rendered():
    """precondition: RENDERABLE == set(BEAT_TYPES) is what closes Phase 4."""
    assert set(BEAT_TYPES) - set(RENDERABLE) == set()


def test_review_names_the_unrenderable_beats(ws, series, monkeypatch):
    """precondition: R4 + M7. An operator who approves a script full of beats
    the renderer cannot draw gets a render missing most of the episode, and the
    only place they could have found out is here.

    Phase 4 Task 3 drew the last two types, so `BEAT_TYPES - RENDERABLE` is
    empty and no real script can reach this warning today. The warning is not
    dead — the next type added to spec §7.1 is valid before anyone writes its
    builder, which is precisely when an operator needs to be told — so the
    narrower gate is injected. Deleting the test would mean rediscovering the
    warning is broken on the day it next matters."""
    beats = statements([3.0]) + [
        {"type": "custom", "hold": 4.0, "js": "const h = E('h2', null, P('x'));\n",
         "attest": "Draws the headline 'x'. — A. B."}
    ]
    episode(series, beats)
    monkeypatch.setattr(video_cli, "RENDERABLE", RENDERABLE - {"custom"})
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "custom" in out
    assert "cannot" in out.lower() and "render" in out.lower()


def test_review_exits_zero_with_unrenderable_beats(ws, series, monkeypatch):
    """precondition: R4 negative + M8. A valid beat no builder exists for is
    fixed by implementing the renderer, not by editing the script — so it is not
    an operator error and must not be reported as one. Gate injected, as above.
    """
    beats = statements([3.0]) + [
        {
            "type": "dumbbell",
            "hold": 4.0,
            "rows": [
                {"label": "History-taking", "values": [0.72, 0.72], "note": "on par"}
            ],
            "series": ["AMIE (video)", "Primary care physician"],
            "caption": "Evaluator ratings, AMIE against primary care physicians",
            "footnote": "Direction only.",
        }
    ]
    episode(series, beats)
    monkeypatch.setattr(video_cli, "RENDERABLE", RENDERABLE - {"dumbbell"})
    result = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 0
    assert "dumbbell" in result.output
    assert "error" not in result.output.lower()
    assert "invalid" not in result.output.lower()


def test_review_counts_the_unrenderable_beats_by_type(ws, series, monkeypatch):
    """precondition: R4. "some beats cannot render" is not actionable; which
    types, and how many of each, is."""
    beats = statements([3.0, 3.0]) + [
        {"type": "custom", "hold": 3.0, "js": "x\n", "attest": "draws x. — A."},
        {"type": "custom", "hold": 3.0, "js": "y\n", "attest": "draws y. — A."},
        {"type": "quote", "hold": 3.0, "text": "a", "attribution": "b"},
    ]
    episode(series, beats)
    monkeypatch.setattr(video_cli, "RENDERABLE", RENDERABLE - {"custom", "quote"})
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "3 beats" in out and "cannot" in out.lower()
    assert "custom (2)" in out
    assert "quote (1)" in out


def test_review_says_nothing_about_rendering_when_everything_renders(ws, series):
    """precondition: R4 negative. A warning that fires on every healthy episode
    is a warning operators learn to scroll past."""
    episode(series, statements([3.0] * 3))
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "cannot" not in out.lower()


def test_an_unrenderable_beat_still_counts_toward_the_runtime(ws, series):
    """precondition: R1 + R4 together. The beat will exist in the finished
    episode, so excluding its hold reports a runtime for an episode nobody is
    making."""
    beats = statements([3.0]) + [
        {"type": "quote", "hold": 7.0, "text": "a", "attribution": "b"}
    ]
    check = check_runtime(load_script(episode(series, beats)), load_series(ws, "the-brief"))
    assert check.total_sec == pytest.approx(10.0)


# One valid beat per catalogue type, so the display is exercised over the whole
# catalogue rather than over `statement` ten times.
EXEMPLARS = {
    "statement": {"text": "Google shipped its main agentic model today."},
    "body": {"text": "A natively multimodal reasoning model tuned for coding."},
    "list": {
        "lead": "Where it landed",
        "items": ["Gemini API & AI Studio", "Antigravity", "The Spark agent"],
    },
    "kpis": {
        # `decimals: 2`, and not optional decoration: with `decimals` absent the
        # engine's count-up is `Math.round(v)`, so this exemplar rendered `1`
        # for a value of 0.75. Phase 4 Task 2's R2 check refuses it — the first
        # thing that rule caught was a fixture already in the tree.
        "items": [
            {"value": 0.75, "prefix": "$", "label": "per 1M input tokens",
             "decimals": 2}
        ],
        "src": "venturebeat",
        "quote": "priced at $0.75 per million input tokens",
    },
    "jumpChart": {
        "rows": [
            {"label": "FrontierCode 1.1", "before": 34.4, "after": 43.6},
            {"label": "DeepSWE v1.1", "before": 48.0, "after": 65.3},
        ],
        "scale": 70,
        "footnote": "Scores as published by Google, on a common 0-70% scale.",
        "src": "deepmind",
        "quote": "FrontierCode 1.1 rises from 34.4 to 43.6",
    },
    "dumbbell": {
        "rows": [
            {"label": "History-taking", "values": [0.72, 0.72], "note": "on par"}
        ],
        "series": ["AMIE (video)", "Primary care physician"],
        "caption": "Evaluator ratings, AMIE against primary care physicians",
        "footnote": "Direction only.",
    },
    "quote": {
        "text": "Gemini 3.7 Flash is our new workhorse model",
        "attribution": "Google",
    },
    "title": {"sub": "Five stories from the last 24 hours."},
    "signoff": {"text": "Same time tomorrow."},
    "custom": {
        "js": "const h = E('h2', null, P('x'));\n",
        "attest": "Draws the headline 'x' and nothing else. — A. B.",
    },
}


def one_of_each():
    return [
        {"type": kind, "hold": 3.0, **fields} for kind, fields in EXEMPLARS.items()
    ]


def test_the_exemplars_cover_the_whole_catalogue():
    """precondition: the display tests below are only as wide as this table."""
    assert set(EXEMPLARS) == set(BEAT_TYPES)


@pytest.mark.parametrize("kind", sorted(BEAT_TYPES))
def test_every_unrenderable_type_is_named_in_the_display(ws, series, monkeypatch, kind):
    """precondition: M7 dropped for ONE type is the mutant a single-type test
    cannot see. With nothing renderable, every catalogue type must reach the
    operator's screen — which is the widest this assertion has ever been, and
    the reason it is worth injecting an empty gate rather than deleting it."""
    episode(series, one_of_each())
    monkeypatch.setattr(video_cli, "RENDERABLE", frozenset())
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert f"{kind} (1)" in out


def test_a_full_catalogue_script_still_exits_zero(ws, series):
    """precondition: R4 negative, at maximum breadth — and now also Phase 4's
    exit criterion, read off the operator's screen. Every one of the ten
    catalogue types renders, so a script containing all of them says nothing
    about anything being undrawable."""
    episode(series, one_of_each())
    result = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 0
    assert "cannot" not in result.output.lower()


# --- R5: review never writes ----------------------------------------------------


def snapshot(root):
    return {
        p.relative_to(root): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_review_writes_nothing(ws, series):
    """precondition: R5 + M9. `review` runs before approval, and the script's
    BYTES are what `script_sha256` binds (D-026). A command that touches them —
    or drops a plan.json beside them — has changed what the operator is about
    to approve by looking at it."""
    episode(series, statements([3.0] * 3))
    before = snapshot(ws.root)
    result = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 0
    assert snapshot(ws.root) == before


def test_review_writes_nothing_when_out_of_tolerance(ws, series):
    """precondition: R5 + M9. The failure path is where a "helpfully write the
    plan so they can see it" side effect gets added."""
    episode(series, statements([30.0] * 12))
    before = snapshot(ws.root)
    run("video", "review", "2026-08-17", "--series", "the-brief")
    assert snapshot(ws.root) == before


def test_review_does_not_create_a_plan_json(ws, series):
    """precondition: M9, named. plan.json is the specific artefact the
    temptation produces."""
    ep = episode(series, statements([3.0] * 3))
    run("video", "review", "2026-08-17", "--series", "the-brief")
    assert list(ep.out_dir.glob("*.json")) == []


def test_review_does_not_change_the_status(ws, series):
    """precondition: R5. `review` is not a transition — spec §11 puts the gate
    at `approve`."""
    episode(series, statements([3.0] * 3))
    run("video", "review", "2026-08-17", "--series", "the-brief")
    assert load_episode(load_series(ws, "the-brief"), "2026-08-17").status.value == "draft"


# --- the display itself ---------------------------------------------------------


def test_review_prints_one_line_per_beat(ws, series):
    """precondition: readability. Twelve beats is the real case; a table that
    wraps or re-orders is a table an operator approves without reading."""
    episode(series, TWELVE)
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    rows = [ln for ln in out.splitlines() if re.match(r"^\s*!?\s+\d+\s", ln)]
    assert len(rows) == 12
    assert [int(ln.split()[0].lstrip("!").strip() or 0) for ln in rows] == list(range(12))


def test_review_keeps_a_multiline_beat_on_one_row(ws, series):
    """precondition: readability. YAML block scalars are how an operator writes
    a long statement; a raw newline in the text column destroys the table."""
    episode(series, [{"type": "statement", "hold": 3.0, "text": "one\ntwo\nthree"}])
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    rows = [ln for ln in out.splitlines() if re.match(r"^\s*!?\s+\d+\s", ln)]
    assert len(rows) == 1
    assert "two" in rows[0]


MAX_COLS = 100


def test_review_truncates_a_very_long_beat(ws, series):
    """precondition: readability. A 600-character body must not wrap the table
    into unreadability."""
    episode(series, [{"type": "statement", "hold": 3.0, "text": "x" * 600}])
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert max(len(ln) for ln in out.splitlines()) <= MAX_COLS


def test_a_long_source_cannot_widen_the_table(ws, series):
    """precondition: readability, found by running Step 5 for real. The first
    twelve-beat output was 156 columns wide because `[src: ...]` was appended
    AFTER an already-full text column. Every row is one screen line or the
    table stops being a table — which is the whole reason it exists."""
    episode(
        series,
        [
            {
                "type": "statement",
                "act": "cold-open",
                "hold": 3.0,
                "text": "x" * 600,
                "src": "www.example.com/a/very/long/path/to/an/article?utm=1",
            }
        ],
    )
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert max(len(ln) for ln in out.splitlines()) <= MAX_COLS


@pytest.mark.parametrize("beat", [{"type": "title"}, {"type": "signoff", "text": ""}])
def test_a_beat_with_nothing_to_say_still_names_itself(ws, series, beat):
    """precondition: `title` and `signoff` are the two types whose fields are
    all optional, so they are the two that can summarise to nothing. A blank
    text column reads as a broken row; the type name reads as a card. Found by
    the sweep: with per-summariser fallbacks the generic one was unreachable,
    and unreachable code is code no test can be wrong about."""
    episode(series, [{"hold": 3.0, **beat}])
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    row = [ln for ln in out.splitlines() if re.match(r"^\s*!?\s+0\s", ln)][0]
    assert f"({beat['type']})" in row


def test_the_total_is_scaled_once_not_per_beat(ws, series):
    """precondition: R1 says `sum(hold) * pace`, and that is deliberately NOT
    how build_plan computes total_sec — the plan rounds every beat to 3dp
    because frame numbers come off it. Twelve 1.0s holds at pace 0.3333 is
    3.996s the plan's way and 4.0s this way. The duration rule is written
    against this one, so Phase 7 must gate on this one.

    Found by the sweep: every other test in this file uses holds whose product
    is exact to 3dp, so both formulas agreed and the difference was invisible.
    """
    check = runtime(series, ws, statements([1.0] * 12), pace=0.3333)
    assert check.total_sec == pytest.approx(4.0)


def test_the_margin_marks_only_the_unrenderable_rows(ws, series, monkeypatch):
    """precondition: R4 + M7. The footer counts them; the margin says WHICH.
    A `!` on every row, or on none, is the same amount of information."""
    episode(
        series,
        [
            {"type": "statement", "hold": 3.0, "text": "this one renders"},
            {"type": "custom", "hold": 3.0, "js": "this one does not\n",
             "attest": "draws nothing yet. — A. B."},
        ],
    )
    monkeypatch.setattr(video_cli, "RENDERABLE", RENDERABLE - {"custom"})
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    rows = [ln for ln in out.splitlines() if re.match(r"^\s*!?\s+\d+\s", ln)]
    assert len(rows) == 2
    assert "!" not in rows[0]
    assert rows[1].lstrip().startswith("!")


def test_the_whole_report_respects_the_width(ws, series):
    """precondition: readability, and the second thing the real Step 5 run
    found. Fixing the table left the "cannot be rendered yet" footer at 156
    columns — nine type names and their counts on one line. Every line of the
    report is a line, not just the table's."""
    episode(series, one_of_each())
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    widest = max(out.splitlines(), key=len)
    assert len(widest) <= MAX_COLS, widest


def test_the_source_column_aligns_across_rows(ws, series):
    """precondition: readability. An approver scans the src column down the
    page; a ragged one has to be read row by row."""
    episode(
        series,
        [
            {"type": "statement", "hold": 3.0, "text": "short", "src": "blog.google"},
            {"type": "statement", "hold": 3.0, "text": "x" * 200, "src": "reuters"},
        ],
    )
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    rows = [ln for ln in out.splitlines() if re.match(r"^\s*!?\s+\d+\s", ln)]
    assert len(rows) == 2
    assert rows[0].index("[blog.google]") == rows[1].index("[reuters]")


def test_review_shows_the_act_of_each_beat(ws, series):
    """precondition: R3. Acts are how the operator navigates the script; a beat
    in the wrong act is the most common structural error."""
    episode(
        series,
        [
            {"type": "statement", "act": "cold-open", "hold": 3.0, "text": "a"},
            {"type": "statement", "act": "01", "hold": 3.0, "text": "b"},
        ],
    )
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "cold-open" in out
    assert "01" in out


def test_review_shows_the_source_of_a_cited_beat(ws, series):
    """precondition: R3. §7.2 makes `src` the thing an approver checks; a chart
    whose source they cannot see is a chart they cannot approve."""
    episode(
        series,
        [
            {
                "type": "kpis",
                "hold": 4.0,
                "items": [
                    {"value": 0.75, "prefix": "$", "label": "per 1M input tokens",
                     "decimals": 2}
                ],
                "src": "venturebeat",
                "quote": "priced at $0.75 per million input tokens",
            }
        ],
    )
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "venturebeat" in out


def test_every_catalogue_type_has_a_summariser():
    """precondition: a blank text column tells the operator nothing about a
    beat they are approving. Adding a type in Phase 4 must not produce a blank
    row, and a `.get(type, "")` default is exactly how it would."""
    assert set(video_cli.SUMMARISERS) == set(BEAT_TYPES)


def test_a_custom_beat_shows_its_attestation_not_its_source(ws, series):
    """precondition: R5. The attestation is only worth requiring if the person
    who approves the episode reads it — an attestation nobody sees is a field an
    author fills in for the schema. This row is the whole delivery mechanism.

    It replaces the `js` in the text column rather than joining it: the column
    is ~40 characters, and a truncated first line of code tells an approver less
    than nothing about what the beat draws. The code is in script.yaml; the
    claim about what it renders is only here."""
    episode(
        series,
        [{"type": "custom", "hold": 3.0,
          "js": "const h = E('h2', null, P('x'));\n",
          "attest": "Draws the headline and no figures. — A. B."}],
    )
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "Draws the headline" in out
    assert "E('h2'" not in out


@pytest.mark.parametrize("kind", sorted(BEAT_TYPES))
def test_every_catalogue_type_summarises_to_something_readable(ws, series, kind):
    """precondition: the summariser existing is not the same as it producing
    text. A row whose text column is empty is a beat the operator skims past."""
    episode(series, [{"type": kind, "hold": 3.0, **EXEMPLARS[kind]}])
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    row = [ln for ln in out.splitlines() if re.match(r"^\s*!?\s+0\s", ln)]
    assert len(row) == 1, out
    # everything after the hold column must carry something
    assert row[0].split("3.0", 1)[1].strip()


# --- failure paths --------------------------------------------------------------


def test_review_of_an_unparseable_script_fails_loudly(ws, series):
    """precondition: this is NOT the R3 exit-0 case. An out-of-tolerance
    runtime is a finding to report; a script that will not parse is a report
    that cannot be produced, and pretending otherwise prints a runtime for a
    file nobody has read."""
    ep = create_episode(series, "2026-08-17")
    ep.script_path.write_text("---\nstatus: draft\n---\nbeats:\n  - type: nope\n", "utf-8")
    result = run("video", "review", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 1
    assert "nope" in result.output


def test_review_of_a_missing_episode_fails(ws, series):
    result = run("video", "review", "nothing-here", "--series", "the-brief")
    assert result.exit_code == 1


def test_review_of_a_missing_series_fails(ws):
    result = run("video", "review", "2026-08-17", "--series", "nope")
    assert result.exit_code == 1
    assert "agsoc series new" in result.output


def test_a_kpi_reads_on_the_review_line_the_way_it_reads_on_the_frame(ws, series):
    """precondition: found by this task's sweep. `_kpi` positioned the symbol
    from a table of currency characters — `$` in front, everything else
    behind — while `planbuild.js` composes `prefix + value + unit` in the order
    the script names them. A `unit: "$"` therefore read as `$0.75` here and
    rendered as `0.75$` there. This line is what the operator approves, and a
    review that reads differently from the render is a review of a different
    video."""
    episode(
        series,
        [
            {
                "type": "kpis",
                "hold": 4.0,
                "items": [
                    {"value": 0.75, "prefix": "$", "label": "in", "decimals": 2},
                    {"value": 50, "unit": "%", "label": "cheaper"},
                ],
                "src": "venturebeat",
                "quote": "priced at $0.75 per million input tokens, 50% cheaper",
            }
        ],
    )
    out = run("video", "review", "2026-08-17", "--series", "the-brief").output
    assert "$0.75" in out
    assert "50%" in out

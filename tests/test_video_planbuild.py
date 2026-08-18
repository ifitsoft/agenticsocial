"""What `planbuild.js` actually puts on the stage.

`planbuild.js` is the only file that turns operator-authored bytes into DOM, so
it is the only place where "what the script says" can stop being "what the frame
shows". Phase 5 verifies a claim against `script.yaml`'s bytes; if the renderer
silently drops or decodes part of them, a claim passes verification while the
video displays something else, and nothing errors.

These tests run the real file. `planbuild.js` and `engine.js` are classic
scripts with no exports — the same constraint that makes `scene.html` use
`document.write` — so they are evaluated in a `node:vm` context holding a
recording DOM. That gives exact assertions on the tree a builder produces
(`<div class="body">` and the html it was handed), which a browser test can only
observe after Chromium has re-serialised it.

The browser half of the story lives in `engine/determinism.test.mjs`: a real
page, every renderable type, asserting the beat's words reach `innerText`. The
two halves catch different failures — this one catches "the builder built the
wrong thing", that one catches "the builder built nothing at all".
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

import agenticsocial

ENGINE = Path(agenticsocial.__file__).resolve().parents[2] / "engine"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

# A recording DOM. `E()` only ever sets className / innerHTML / textContent /
# style and appends, so that is all a node has to be; anything else E touches
# would surface here as a TypeError rather than as a silently missing element.
#
# `rise`, `fade`, `draw` and `an` are replaced with recorders AFTER engine.js is
# evaluated, so a builder that forgets to animate its element is visible. They
# are still invoked at p=0 and p=1 so a broken animation callback throws here
# instead of in the browser.
HARNESS = textwrap.dedent(
    """
    const fs = require('fs');
    const vm = require('vm');

    function node(tag) {
      return {
        tag, className: '', innerHTML: null, textContent: null,
        style: {}, kids: [],
        appendChild(c) { this.kids.push(c); return c; },
      };
    }
    const dump = (n) => ({
      tag: n.tag, cls: n.className, html: n.innerHTML, text: n.textContent,
      css: n.style, kids: n.kids.map(dump),
    });

    const ctx = {
      console,
      document: {
        createElement: node,
        documentElement: { style: { setProperty(k, v) { tokens[k] = v; } } },
      },
    };
    const tokens = {};
    vm.createContext(ctx);
    vm.runInContext(fs.readFileSync(process.env.ENGINE + '/engine.js', 'utf8'), ctx);
    vm.runInContext('globalThis.__setSC = (x) => { SC = x; }', ctx);
    vm.runInContext(
      `globalThis.__anims = [];
       const rec = (kind) => (el, d0, o) => {
         __anims.push({ kind, cls: el && el.className, d0 });
         return d0;
       };
       rise = rec('rise'); fade = rec('fade');
       draw = (el, d0) => { __anims.push({ kind: 'draw', cls: el.className, d0 }); };
       an = (d0, dur, ez, fn) => {
         __anims.push({ kind: 'an', d0 });
         fn(0); fn(1);
       };`,
      ctx,
    );
    vm.runInContext(fs.readFileSync(process.env.ENGINE + '/planbuild.js', 'utf8'), ctx);
    const out = {};
    if (process.env.PLAN) {
      vm.runInContext('buildFromPlan(' + process.env.PLAN + ')', ctx);
      // Build through engine.js's own SCENES rather than a stub `scene()`:
      // engine.js declares `function scene(...)`, so a stub installed before it
      // is silently overwritten — and the resulting empty scene list looks
      // exactly like a builder that appended nothing.
      out.scenes = vm.runInContext('SCENES', ctx).map((s) => {
        const root = node('div');
        root.className = 'sc';
        ctx.__setSC(root);
        s.build(root);
        return {
          act: s.act, dur: s.base, tag: s.tag,
          anims: ctx.__anims.splice(0), tree: dump(root),
        };
      });
      out.meta = vm.runInContext('META', ctx);
      out.tokens = tokens;
    }
    if (process.env.EVAL) {
      out.value = vm.runInContext(process.env.EVAL, ctx);
    }
    console.log(JSON.stringify(out));
    """
)


def _run(plan: dict | None = None, expr: str | None = None, engine: Path | None = None):
    env = {**os.environ, "ENGINE": str(engine or ENGINE)}
    if plan is not None:
        env["PLAN"] = json.dumps(plan)
    if expr is not None:
        env["EVAL"] = expr
    return subprocess.run(["node", "-e", HARNESS], capture_output=True, text=True, env=env)


def _node(
    plan: dict | None = None, expr: str | None = None, engine: Path | None = None
) -> dict:
    proc = _run(plan, expr, engine)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def engine_with(tmp_path: Path, old: str, new: str) -> Path:
    """A copy of the engine with one animation constant changed.

    The only way a test can tell "derived from engine.js's constant" from "the
    same number typed again in planbuild.js" is to move the constant and watch
    whether the requirement follows. Reading the constant and recomputing the
    formula in Python cannot: both implementations agree while the numbers do.
    """
    out = tmp_path / "engine"
    out.mkdir(exist_ok=True)
    src = (ENGINE / "engine.js").read_text()
    assert old in src, f"{old!r} is no longer in engine.js — the evidence moved"
    (out / "engine.js").write_text(src.replace(old, new))
    (out / "planbuild.js").write_text((ENGINE / "planbuild.js").read_text())
    return out


def refuses(beats: list[dict], **plan) -> str:
    """`buildFromPlan` alone must throw — the message, or an assertion failure.

    Calling `buildFromPlan` and nothing else is the point: the check has to run
    EAGERLY, while the plan is being walked, not inside the closure `seek()`
    calls. A throw from inside a build closure happens at the frame that scene
    first appears on, which for beat 14 of an 88-second video is thirty seconds
    into a render that has already written nine hundred frames — and
    `render.mjs` only inspects page errors after `goto`, which is `seek(0)`.
    """
    base = {"episode": "2026-08-16", "series": "the-brief", "byline": "A. B."}
    payload = json.dumps({**base, **plan, "beats": beats})
    msg = _node(
        expr=(
            "(() => { try { buildFromPlan(" + payload + "); }"
            " catch (e) { return e.message } return null; })()"
        )
    )["value"]
    assert msg, "buildFromPlan accepted the beat"
    return msg


def prose_html(raw: str) -> str:
    """What `planbuild.js` would set as innerHTML for a prose field."""
    return _node(expr="proseHTML(" + json.dumps(raw) + ")")["value"]


def build(beats: list[dict], **plan) -> list[dict]:
    base = {"episode": "2026-08-16", "series": "the-brief", "byline": "A. B."}
    return _node(plan={**base, **plan, "beats": beats})["scenes"]


def beat(kind: str = "statement", **fields) -> dict:
    return {
        "type": kind,
        "act": "",
        "act_label": "",
        "hold": 3.0,
        "kicker": "",
        "src": "",
        **fields,
    }


def flatten(tree: dict) -> list[dict]:
    return [tree] + [n for kid in tree["kids"] for n in flatten(kid)]


def find(tree: dict, cls: str) -> list[dict]:
    return [n for n in flatten(tree) if n["cls"] == cls]


def shown(node: dict) -> str:
    """The text this node puts on the screen, however it was set."""
    return node["html"] if node["html"] is not None else (node["text"] or "")


# --- Step 0: the rendered bytes are the verified bytes ---------------------------
# Leader-verified in a real browser before this fix: the script said
# "The model is <thinking> about it" and the screen said "The model is  about it".
# The word was not mangled, it was GONE — Chromium parsed it as an unknown tag.


@needs_node
def test_a_tag_like_word_survives_as_text():
    """R2 (M1, M2). The failure that opened this task, at the unit level."""
    assert prose_html("The model is <thinking> about it") == (
        "The model is &lt;thinking&gt; about it"
    )


@needs_node
def test_an_ampersand_is_escaped_too():
    """R2 NEGATIVE (M4). `AT&T` is the common case and `<`/`>` alone miss it:
    `&T` happens to be harmless, but `&amp;` in the script would decode to a
    bare `&` on screen — the script's bytes and the frame's would differ with
    no tag in sight."""
    assert prose_html("AT&T raised prices") == "AT&amp;T raised prices"


@needs_node
def test_an_entity_in_the_script_stays_five_characters():
    """R2 NEGATIVE. An operator who writes `&amp;` gets `&amp;`. Entities do not
    decode: the script is prose, not markup."""
    assert prose_html("write &amp; read") == "write &amp;amp; read"


@needs_node
def test_bold_still_bolds():
    """R1 NEGATIVE (M1). Escaping everything is not the answer either — spec
    §7.1 gives `body` the field `text` (bold via `**`), and that vocabulary has
    to survive."""
    assert prose_html("tuned for **coding and agents**, plus more") == (
        "tuned for <b>coding and agents</b>, plus more"
    )


@needs_node
def test_bold_is_converted_after_escaping_not_before():
    """M3. The order is the whole trick. Convert first and the escape pass eats
    the `<b>` you just made, so the reader sees the tag as literal text."""
    assert prose_html("**AT&T** wins") == "<b>AT&amp;T</b> wins"


@needs_node
def test_two_bold_runs_stay_two():
    """Found by the mutation sweep: a GREEDY `**…**` passed every other
    assertion here. It joins the first opener to the LAST closer, so
    "**A** and **B**" renders as one bold run with the connective swallowed —
    emphasis the operator did not write, on words they did not choose."""
    assert prose_html("**A** and **B**") == "<b>A</b> and <b>B</b>"


@needs_node
def test_accent_produces_an_em():
    """D-080. `<em>` and `warm-t` are "a second emphasis that speaks in colour
    rather than weight, used exactly where each episode pivots", and nothing in
    the vocabulary reached them. scene.html already styles `em` (colour, not
    italics), so this adds a token, not CSS."""
    assert prose_html("it *doubles* in 2027") == "it <em>doubles</em> in 2027"


@needs_node
def test_bold_and_accent_in_one_string_stay_one_of_each():
    """The greedy-regex failure the sweep found in `**…**` applies here too, and
    a single-asterisk pass is also the one that can eat the FIRST `*` of a `**`
    opener. Both markers in one sentence, with the connective intact, is the
    assertion that sees either mistake."""
    assert prose_html("**half** the price, *twice* the speed") == (
        "<b>half</b> the price, <em>twice</em> the speed"
    )


@needs_node
def test_bold_markers_do_not_leak_when_unpaired():
    """A lone `**` is prose, not an unterminated tag. It must render as itself
    rather than swallowing the rest of the sentence."""
    assert prose_html("a ** b") == "a ** b"


@needs_node
def test_bold_spans_a_wrapped_line():
    """YAML folds long strings, so a `**…**` written by an agent routinely
    arrives with a newline inside it."""
    assert prose_html("tuned for **coding,\nagentic work** today") == (
        "tuned for <b>coding,\nagentic work</b> today"
    )


@needs_node
def test_statement_text_and_kicker_are_both_prose():
    """M1, at the beat level: the helper existing is not the same as the
    builders using it. A kicker is authored text like any other."""
    scenes = build([beat(text="1 < 2 & **true**", kicker="R&D <today>")])
    tree = scenes[0]["tree"]
    assert shown(find(tree, "kicker")[0]) == "R&amp;D &lt;today&gt;"
    assert shown([n for n in flatten(tree) if n["tag"] == "h1"][0]) == (
        "1 &lt; 2 &amp; <b>true</b>"
    )


# --- Step 1: the five new builders ----------------------------------------------
# One mutant per assertion, from the table in the brief. The recurring failure
# these are written against is not a crash: it is a builder that renders SOME of
# its beat and drops the rest, which looks like a design choice on screen.


@needs_node
def test_every_renderable_type_has_a_builder():
    """precondition (M10, and the D-036 drift pattern). `RENDERABLE` is Python's
    promise that plan.py may emit a type; `BUILDERS` is Node's promise that it
    can draw one. Two lists, one meaning: the phase they diverge in is the phase
    where a beat reaches the stage and silently renders nothing."""
    from agenticsocial.video.script import RENDERABLE

    builders = _node(expr="Object.keys(BUILDERS)")["value"]
    assert set(builders) == set(RENDERABLE)


KPIS = {
    "items": [
        {"value": 0.75, "prefix": "$", "label": "per 1M input tokens", "decimals": 2},
        {"value": 3.75, "prefix": "$", "label": "per 1M output tokens", "decimals": 2},
    ],
    "src": "venturebeat",
    "quote": "priced at $0.75 per million input tokens and $3.75 per million output",
}

JUMP = {
    "rows": [
        {"label": "FrontierCode 1.1", "before": 34.4, "after": 43.6,
         "shown": "<s>34.4</s> &rarr; 43.6"},
        {"label": "GDP.pdf", "before": 22.0, "after": 34.0,
         "shown": "<s>22.0</s> &rarr; 34.0"},
    ],
    "scale": 70,
    "footnote": "Scores as published by Google, on a common 0-70% scale.",
    "src": "deepmind",
    "quote": "FrontierCode 1.1 rises from 34.4 to 43.6",
}

DUMBBELL = {
    "rows": [
        {"label": "History-taking", "values": [0.72, 0.72], "note": "on par"},
        {"label": "Eliciting physical signs", "values": [0.82, 0.58],
         "note": "rated higher"},
    ],
    "series": ["AMIE (video)", "Primary care physician"],
    "caption": "Evaluator ratings, AMIE against primary care physicians",
    "footnote": "Direction only — the source reports evaluator ratings, not scores.",
}

CUSTOM = {
    "js": "const h = E('h2', null, P('x'));\nrise(h, .15);\n",
    "attest": "Draws the headline 'x' and nothing else. — A. B.",
}


RENDERABLE_BEATS = {
    "statement": {"text": "a statement"},
    "body": {"text": "a body line"},
    "list": {"items": ["one", "two"]},
    "quote": {"text": "a quoted sentence", "attribution": "Someone"},
    "title": {},
    "signoff": {},
    "kpis": KPIS,
    "jumpChart": JUMP,
    "dumbbell": DUMBBELL,
    "custom": CUSTOM,
}


@needs_node
@pytest.mark.parametrize("kind", sorted(RENDERABLE_BEATS))
def test_every_type_renders_visible_content(kind):
    """R3 (M10). The minimal legal beat of every type puts something on the
    stage and animates it. A builder that returns before appending, or appends
    without registering an animation, leaves a card that is blank or frozen at
    opacity 0 — and `__seek(t)` still returns cleanly."""
    scene = build([beat(kind, **RENDERABLE_BEATS[kind])])[0]
    assert scene["tree"]["kids"], f"{kind} appended nothing"
    assert scene["anims"], f"{kind} animated nothing"


@needs_node
def test_body_renders_its_text_as_prose():
    """M1. `.body` is the class both committed episodes use for a paragraph,
    and `.body b` is styled there — which is what makes `**bold**` land."""
    tree = build([beat("body", text="costs **half** of 3.6 & rising")])[0]["tree"]
    assert shown(find(tree, "body")[0]) == "costs <b>half</b> of 3.6 &amp; rising"


@needs_node
def test_body_renders_its_kicker_too():
    """M1 again, on the SHARED kicker path. Also found by the sweep: only
    `statement` builds its own kicker, so a `P()` left in the helper every other
    type calls survived a fixture whose kicker had nothing to escape. A kicker
    is authored text and carries the same risk as any other field."""
    tree = build([beat("body", text="t", kicker="R&D on <tools>")])[0]["tree"]
    assert shown(find(tree, "kicker")[0]) == "R&amp;D on &lt;tools&gt;"


@needs_node
def test_list_renders_every_item():
    """M6. `lead` is optional and `items` is the required field — a builder that
    draws the lead and stops renders the introduction to a list that is not
    there."""
    tree = build([beat("list", lead="Live today in", items=["A", "B", "C"])])[0]["tree"]
    assert [shown(n) for n in flatten(tree) if n["tag"] == "span"] == ["A", "B", "C"]


@needs_node
def test_list_renders_its_lead_when_items_exist():
    """M7. The mirror image: the items arrive and the sentence that framed them
    is gone, which reads on screen as a list with no subject."""
    tree = build([beat("list", lead="Tuned for **agents** & code", items=["A"])])[0][
        "tree"
    ]
    assert shown(find(tree, "body")[0]) == "Tuned for <b>agents</b> &amp; code"


@needs_node
def test_list_items_are_prose_not_markup():
    """M2, inside a list. The items are the field most likely to carry a raw
    `<tag>` — they are names of things."""
    tree = build([beat("list", items=["<think> mode", "AT&T"])])[0]["tree"]
    assert [shown(n) for n in flatten(tree) if n["tag"] == "span"] == [
        "&lt;think&gt; mode",
        "AT&amp;T",
    ]


@needs_node
def test_a_list_without_a_lead_still_renders_its_items():
    """R3 NEGATIVE. `lead` is optional in the catalogue; its absence must not
    take the items with it."""
    tree = build([beat("list", items=["only"])])[0]["tree"]
    assert [shown(n) for n in flatten(tree) if n["tag"] == "span"] == ["only"]
    assert not find(tree, "body")


@needs_node
def test_list_uses_the_stack_classes_the_stage_already_styles():
    """`.stack`/`.item` carry the bullet and the slide-in geometry. A div with
    the right text and the wrong class renders as unstyled 16px text."""
    tree = build([beat("list", items=["A", "B"])])[0]["tree"]
    assert find(tree, "stack sm"), "no .stack"
    assert len(find(tree, "item")) == 2
    assert [n["tag"] for n in flatten(tree) if n["tag"] == "i"] == ["i", "i"]


@needs_node
def test_quote_renders_both_the_words_and_the_attribution():
    """M8. Spec §7.1 marks `quote` verifiable VERBATIM — an unattributed
    verbatim quotation is the one thing this beat exists to prevent."""
    scene = build(
        [beat("quote", text="It is a **workhorse** model", attribution="Sundar Pichai")]
    )[0]
    rendered = [shown(n) for n in flatten(scene["tree"])]
    assert "It is a <b>workhorse</b> model" in rendered
    assert "Sundar Pichai" in rendered


@needs_node
def test_quote_draws_a_rule_between_the_words_and_the_name():
    """Spec §7.1 gives `quote` the motion "fade + rule draw"."""
    scene = build([beat("quote", text="t", attribution="A")])[0]
    assert any(a["kind"] == "draw" for a in scene["anims"])
    assert find(scene["tree"], "rule blue")


@needs_node
def test_a_bare_title_still_renders_a_card():
    """M9, R3 NEGATIVE. `title` has NO required fields — `sub` is optional and
    the spec's own cold-open title beat carries only a `hold`. A builder keyed
    off its text renders an empty stage for a legal beat."""
    tree = build([beat("title")], series_name="The Brief")[0]["tree"]
    assert shown(find(tree, "big-title")[0]) == "THE BRIEF"
    assert find(tree, "byline")


@needs_node
def test_title_renders_its_subtitle_when_it_has_one():
    tree = build([beat("title", sub="Five stories from **24 hours**")], series_name="X")[
        0
    ]["tree"]
    assert shown(find(tree, "body")[0]) == "Five stories from <b>24 hours</b>"


@needs_node
def test_a_bare_signoff_still_renders_a_card():
    """M9's other half — `signoff`'s only field is optional too."""
    tree = build([beat("signoff")], series_name="The Brief")[0]["tree"]
    assert shown(find(tree, "big-title")[0]) == "THE BRIEF"


@needs_node
def test_signoff_renders_its_closing_line():
    tree = build([beat("signoff", text="Same time & place")], series_name="X")[0]["tree"]
    assert "Same time &amp; place" in [shown(n) for n in flatten(tree["kids"][0])] + [
        shown(n) for n in flatten(tree)
    ]


@needs_node
def test_the_title_card_falls_back_to_the_slug_when_there_is_no_name():
    """A plan written before `series_name` existed still renders a title card
    rather than a blank one."""
    tree = build([beat("title")])[0]["tree"]
    assert shown(find(tree, "big-title")[0]) == "THE-BRIEF"


# --- Task 2: the two strictly verifiable types ----------------------------------
#
# Spec §7.2: "there is no path to rendering a number that isn't in a source."
# The schema already requires `src` and `quote`, and that is NOT sufficient —
# the renderer can manufacture a number the plan never carried. These tests are
# the renderer's own half of the rule, and they matter because a plan can reach
# the page without passing through Python at all: `render.mjs --plan` reads any
# JSON file, and determinism.test.mjs writes its own `.plan.js` by hand.


@needs_node
@pytest.mark.parametrize("kind", ["kpis", "jumpChart"])
@pytest.mark.parametrize("field", ["src", "quote"])
def test_a_chart_refuses_to_render_without_a_citation(kind, field):
    """R1 (M1). The schema's `cited` gate is on the Python path only. A chart
    that reached the page uncited would draw numbers with nothing behind
    them — which is the one thing spec §7.2 says there is no path to."""
    fields = {k: v for k, v in RENDERABLE_BEATS[kind].items() if k != field}
    msg = refuses([beat(kind, **fields)])
    assert field in msg and kind in msg


@needs_node
@pytest.mark.parametrize("kind", ["kpis", "jumpChart"])
@pytest.mark.parametrize("empty", ["", "   "])
def test_a_citation_that_is_blank_is_not_a_citation(kind, empty):
    """R1 + the falsy rule from the other direction: present-and-empty passes
    `'src' in b` and cites nothing. `"   "` passes a truthiness check too."""
    assert refuses([beat(kind, **{**RENDERABLE_BEATS[kind], "src": empty})])


@needs_node
@pytest.mark.parametrize("kind", ["title", "signoff", "statement", "body", "list"])
def test_an_uncited_type_still_renders_without_src_or_quote(kind):
    """R1 NEGATIVE (M2). `title` asserts nothing about the world. Making every
    type demand a citation turns the rule into noise operators route around by
    pasting a source in — and these beats never carry one."""
    scene = build([beat(kind, **RENDERABLE_BEATS[kind])])[0]
    assert scene["tree"]["kids"], f"{kind} appended nothing"


@needs_node
def test_the_kpi_figures_that_reach_the_screen_are_the_plan_s_own():
    """R2, positive. The recorder runs every animation callback at p=1, so the
    `.n` node holds the string the count-up ends on — the actual glyphs, not the
    arguments. `$0.75` is `0.75` with a symbol in front of it; that is the same
    figure, differently read."""
    tree = build([beat("kpis", **KPIS)])[0]["tree"]
    assert [shown(n) for n in find(tree, "n")] == ["$0.75", "$3.75"]


@needs_node
def test_a_kpi_value_display_rounding_would_change_is_refused():
    """R2 (M3), and the heart of the task. `0.756` at `decimals: 1` reaches the
    frame as `0.8` — a figure in no source, no quote and no plan. Phase 5 would
    verify 0.756 against the quote, pass, and ship a video showing a number
    nobody checked."""
    msg = refuses(
        [beat("kpis", **{**KPIS, "items": [
            {"value": 0.756, "label": "per 1M tokens", "decimals": 1}
        ]})]
    )
    assert "0.756" in msg and "0.8" in msg


@needs_node
def test_a_kpi_value_is_refused_when_decimals_are_absent_and_it_is_not_whole():
    """R2 through the DEFAULT. `count()` is `decimals ? v.toFixed(decimals) :
    Math.round(v)`, so an omitted `decimals` is not "print it as written", it is
    rounding to the nearest integer: `0.75` reaches the frame as `1`. A rule
    written only against a present `decimals` has a hole the size of the
    default."""
    msg = refuses(
        [beat("kpis", **{**KPIS, "items": [{"value": 0.75, "label": "per 1M"}]})]
    )
    assert "0.75" in msg


@needs_node
def test_a_prefix_a_suffix_and_a_thousands_separator_are_not_inventions():
    """R2 NEGATIVE (M4), the half of the pair that is easy to get backwards.
    Rounding invents a number; a currency symbol does not. `2,000` and `2000`
    are the same figure — the separator is how English writes it — and the
    committed episode renders `~2,000` and `50%` exactly this way."""
    tree = build([beat("kpis", **{**KPIS, "items": [
        {"value": 2000, "prefix": "~", "label": "stories since May"},
        {"value": 50, "unit": "%", "label": "cheaper than 3.6 Flash"},
    ]})])[0]["tree"]
    assert [shown(n) for n in find(tree, "n")] == ["~2,000", "50%"]


@needs_node
def test_a_zero_kpi_value_still_draws_a_row():
    """The falsy rule. `0` is a legitimate headline figure and a truthiness
    check on `value` drops the row entirely — or, worse, counts up to
    `undefined` and prints `NaN`."""
    tree = build([beat("kpis", **{**KPIS, "items": [
        {"value": 0, "label": "seconds of downtime"},
    ]})])[0]["tree"]
    assert [shown(n) for n in find(tree, "n")] == ["0"]


@needs_node
def test_a_kpi_label_is_set_as_text_not_html():
    """R3 (M6). The label is authored text like any other and is the field most
    likely to carry an ampersand. Set through `innerHTML` a `<tag>` in it
    vanishes from the frame while script.yaml still says it — the exact defect
    Task 1 closed for prose."""
    tree = build([beat("kpis", **{**KPIS, "items": [
        {"value": 1, "label": "R&D on <tools>"},
    ]})])[0]["tree"]
    label = find(tree, "u")[0]
    assert label["html"] is None, "the label went through innerHTML"
    assert label["text"] == "R&D on <tools>"


@needs_node
def test_a_string_kpi_value_keeps_its_prefix_and_suffix():
    """`kpis()` prints a non-numeric value verbatim and its own signature drops
    prefix and suffix on that branch — it only reads them inside `count()`. A
    builder that passes them anyway loses the symbol silently, which is R3's
    failure (the plan carried something the frame does not show) rather than
    R2's."""
    tree = build([beat("kpis", **{**KPIS, "items": [
        {"value": "half", "prefix": "~", "unit": " the price", "label": "vs 3.6"},
    ]})])[0]["tree"]
    assert [shown(n) for n in find(tree, "n")] == ["~half the price"]


@needs_node
def test_a_kpis_beat_renders_its_kicker_as_prose():
    """The shared kicker path, on a type that did not exist when it was
    written."""
    tree = build([beat("kpis", **{**KPIS, "kicker": "R&D on **cost**"})])[0]["tree"]
    assert shown(find(tree, "kicker")[0]) == "R&amp;D on <b>cost</b>"


# --- jumpChart -------------------------------------------------------------------


@needs_node
def test_jumpchart_rows_render_in_the_order_they_were_authored():
    """M9. The rows are a ranking as often as not, and a chart that reorders
    them tells a different story with the same numbers. Nothing about the
    rendered output makes a reordering look wrong."""
    rows = [
        {"label": "first", "before": 1, "after": 2},
        {"label": "second", "before": 3, "after": 4},
        {"label": "third", "before": 5, "after": 6},
    ]
    tree = build([beat("jumpChart", **{**JUMP, "rows": rows})])[0]["tree"]
    assert [n["text"] for n in find(tree, "jlab")] == ["first", "second", "third"]


@needs_node
def test_jumpchart_shown_reaches_the_value_cell_as_html():
    """R3 (M5). `shown` is the ONE field rendered as HTML — a documented display
    override. The committed 2026-08-14 episode depends on both the
    strikethrough and the entity: escaped, the tags land on screen."""
    tree = build([beat("jumpChart", **JUMP)])[0]["tree"]
    assert [n["html"] for n in find(tree, "jval")] == [
        "<s>34.4</s> &rarr; 43.6",
        "<s>22.0</s> &rarr; 34.0",
    ]


@needs_node
def test_a_jumpchart_label_is_set_as_text_not_html():
    """R3 NEGATIVE (M6). `shown` is the exemption, and an exemption that spread
    to the labels would be the innerHTML defect again."""
    tree = build([beat("jumpChart", **{**JUMP, "rows": [
        {"label": "AT&T <legacy>", "before": 1, "after": 2},
    ]})])[0]["tree"]
    lab = find(tree, "jlab")[0]
    assert lab["html"] is None and lab["text"] == "AT&T <legacy>"


@needs_node
def test_the_footnote_reaches_the_stage_as_text():
    """M10. `footnote` is REQUIRED on a jumpChart — it is where "scores as
    published, on a common 0-70% scale" lives, and it is what stops the chart
    being read as something the series measured itself. Dropping it changes what
    the chart claims."""
    tree = build([beat("jumpChart", **JUMP)])[0]["tree"]
    foot = find(tree, "foot")
    assert foot, "the footnote never reached the stage"
    assert foot[0]["html"] is None
    assert foot[0]["text"] == JUMP["footnote"]


@needs_node
def test_the_footnote_is_animated_rather_than_left_at_opacity_zero():
    """M10's quieter half: `.foot` is faded in, so a footnote that is appended
    and never animated sits at whatever opacity the fade starts from. Appended
    is not the same as visible."""
    scene = build([beat("jumpChart", **JUMP)])[0]
    assert scene["anims"], "nothing animated"


@needs_node
@pytest.mark.parametrize("field", ["before", "after"])
def test_a_row_above_the_scale_is_refused_not_clipped(field):
    """R4 (M7). Every dot is positioned as `value / max * 100 + '%'`, so a row
    above the scale is drawn past the end of its track. Clipping it to the scale
    would be worse than refusing: the bar would sit at 100% and read as the
    maximum, which is a number the plan did not carry."""
    row = {"label": "off the track", "before": 34.4, "after": 43.6}
    row[field] = 82.0
    msg = refuses([beat("jumpChart", **{**JUMP, "rows": [row], "scale": 70})])
    assert "82" in msg and "70" in msg


@needs_node
@pytest.mark.parametrize("field", ["before", "after"])
def test_a_row_equal_to_the_scale_renders(field):
    """R4 NEGATIVE (M8). The bound is inclusive — a bar at 100% of the track is
    on the card, and a benchmark that reaches the top of the published scale is
    exactly the chart worth drawing."""
    row = {"label": "at the top", "before": 34.4, "after": 43.6}
    row[field] = 70
    tree = build([beat("jumpChart", **{**JUMP, "rows": [row], "scale": 70})])[0]["tree"]
    assert [n["text"] for n in find(tree, "jlab")] == ["at the top"]


@needs_node
def test_a_row_at_zero_still_renders():
    """The falsy rule inside R4: a range check written `if (!v || v > scale)`
    refuses a benchmark that scored 0 before, which is the most interesting bar
    on the chart."""
    tree = build([beat("jumpChart", **{**JUMP, "rows": [
        {"label": "from nothing", "before": 0, "after": 30.4},
    ]})])[0]["tree"]
    assert [n["text"] for n in find(tree, "jlab")] == ["from nothing"]


@needs_node
def test_the_chart_is_drawn_into_the_class_the_stage_styles():
    """`.chart` is what gives the rows their width and the footnote its top
    margin. `jumpChart(rows, max, d0, parent)` takes its parent explicitly and
    has no default — passing the wrong one puts four absolutely-positioned
    tracks on top of each other."""
    tree = build([beat("jumpChart", **JUMP)])[0]["tree"]
    chart = find(tree, "chart")
    assert chart, "no .chart"
    assert len([n for n in flatten(chart[0]) if n["cls"] == "jrow"]) == 2


@needs_node
def test_the_scale_reaches_the_engine_as_the_track_maximum():
    """The dot positions are the only place `scale` is used, and they are
    percentages of it. A builder that dropped it would pass `undefined` and
    every `left` would be the string `NaN%` — which CSS ignores, so all four
    dots would silently stack at the left edge."""
    tree = build([beat("jumpChart", **{**JUMP, "rows": [
        {"label": "half way", "before": 0, "after": 35},
    ], "scale": 70})])[0]["tree"]
    dots = [n for n in flatten(tree) if n["cls"] == "dot to"]
    assert dots and dots[0]["css"].get("left") == "50%"


# --- Task 3: `custom`, the beat that executes ------------------------------------
#
# Every other builder turns fields into DOM. This one hands the page a string
# the operator wrote and runs it. The tests below are about what that means:
# it must actually run (an escape hatch that silently draws nothing is worse
# than no escape hatch), it must run EAGERLY enough that a broken one is a build
# failure rather than a blank card thirty seconds into a render, and it must
# reach the same primitives every committed episode uses — `js` is written by
# someone reading content/2026-08-14.js, not a new dialect.

@needs_node
def test_a_custom_beat_runs_its_javascript():
    """R4. The whole type. A builder that stores `js` and never calls it leaves
    a legal beat rendering an empty card, and nothing errors."""
    tree = build([beat("custom", **CUSTOM)])[0]["tree"]
    assert [n["tag"] for n in flatten(tree) if n["tag"] == "h2"] == ["h2"]


@needs_node
def test_the_custom_javascript_sees_the_engine_primitives():
    """R4. `js` is authored by someone reading the committed episodes, which
    call E, P, rise, fade, draw, an, EZ, clamp and lerp as bare globals. A beat
    evaluated in a scope without them is a different language that happens to
    look the same."""
    js = (
        "const b = E('div', 'body', P('hi'));\n"
        "fade(b, .1);\n"
        "an(0, 1, EZ.out, p => { b.style.opacity = clamp(lerp(0, 1, p)); });\n"
    )
    scene = build([beat("custom", **{**CUSTOM, "js": js})])[0]
    assert find(scene["tree"], "body")
    assert scene["anims"]


@needs_node
def test_the_custom_javascript_is_handed_the_scene_root():
    """R4. Both episodes write `scene(act, dur, tag, s => { … })` and the `s`
    parameter is the card. An escape hatch that does not pass it forces every
    custom beat to reach for a global the engine does not promise.

    The assertion READS `s` rather than passing it to `E({p: s})`, which is the
    version my mutation sweep killed: `E()` falls back to `opts.p || SC`, and
    inside a build closure SC is the same node — so a builder that dropped the
    argument entirely produced an identical tree and the test passed."""
    js = (
        "const cls = s.className;\n"
        "E('div', 'kicker', {text: 'root class ' + cls});\n"
    )
    tree = build([beat("custom", **{**CUSTOM, "js": js})])[0]["tree"]
    assert find(tree, "kicker")[0]["text"] == "root class sc"


@needs_node
def test_a_custom_beat_with_a_syntax_error_is_refused_while_the_plan_is_walked():
    """R4's timing, and the same argument as requireCitation's. A throw from
    inside a build closure fires at the frame that scene first appears on:
    beat 14 of an 88-second video is thirty seconds into a render that has
    already written nine hundred frames, and render.mjs only inspects page
    errors after goto (which is seek(0)) and again at the end."""
    msg = refuses([beat("custom", **{**CUSTOM, "js": "const h = ;\n"})])
    assert "custom" in msg and "0" in msg


@needs_node
def test_the_attestation_is_not_drawn_on_the_card():
    """R5's scope. The attestation is a claim made to the APPROVER, in `agsoc
    video review`. Rendering it would put an internal note in the video, and —
    worse — would make a beat that displays its own sign-off look verified."""
    tree = build([beat("custom", **{**CUSTOM, "attest": "SIGNED-BY-THE-AUTHOR"})])[0][
        "tree"
    ]
    assert "SIGNED-BY-THE-AUTHOR" not in rendered_text(tree)


@needs_node
def test_a_custom_beat_needs_no_citation():
    """R1 NEGATIVE from Task 2. `custom` is not one of the two cited types: what
    it renders is unknown to the schema, so a `src` on it would be a citation
    for nothing in particular. That is exactly why it carries an attestation
    instead."""
    scene = build([beat("custom", **CUSTOM)])[0]
    assert scene["tree"]["kids"]


# --- Task 3: the dumbbell --------------------------------------------------------
#
# Extracted from engine/content/2026-08-12.js, which is the only dumbbell that
# has ever rendered. Two properties are the reason the type exists at all, and
# both are load-bearing:
#
#   1. direction only, no numeric axis — spec §7.2 says this is the correct type
#      when a source publishes RATINGS rather than scores;
#   2. where two values coincide, ONE two-tone marker. The episode's own comment
#      says why: "no gap: one two-tone marker rather than two dots stacked
#      invisibly". A stacked pair hides a series, and a chart that silently omits
#      a series is worse than one that refuses to draw.


def rendered_text(tree: dict) -> str:
    return " ".join(shown(n) for n in flatten(tree))


@needs_node
def test_a_dumbbell_renders_no_numbers():
    """R2 (M4). The type exists BECAUSE the source published ratings rather than
    scores: 0.72 is a position on an unlabelled track, not a figure anyone
    measured. Printing it beside the label would manufacture the precision the
    footnote exists to deny — the same failure as display rounding, arrived at
    by putting a number on screen that no source ever stated."""
    tree = build([beat("dumbbell", **DUMBBELL)])[0]["tree"]
    text = rendered_text(tree)
    for glyph in ["0.72", "0.82", "0.58", "72", "82", "58"]:
        assert glyph not in text, f"{glyph!r} reached the screen: {text}"


@needs_node
def test_the_positions_reach_the_markers_as_geometry_not_as_text():
    """R2's positive half. The numbers do their whole job through `left`, which
    is the difference between a chart and a table."""
    tree = build([beat("dumbbell", **DUMBBELL)])[0]["tree"]
    lefts = [n["css"].get("left") for n in flatten(tree) if n["cls"].startswith("dot")]
    assert "72%" in lefts


@needs_node
def test_coincident_values_draw_one_two_tone_marker():
    """R3 (M6), and the reason this type has its own CSS. Two dots at the same
    position stack, the second hides the first, and the chart shows one series
    while claiming to compare two. `.dot.merged` is the two-tone marker
    scene.html already styles for exactly this."""
    tree = build([beat("dumbbell", **{**DUMBBELL, "rows": [
        {"label": "History-taking", "values": [0.72, 0.72], "note": "on par"},
    ]})])[0]["tree"]
    assert len(find(tree, "dot merged")) == 1
    assert not find(tree, "dot a") and not find(tree, "dot b")


@needs_node
def test_distinct_values_draw_two_separate_dots():
    """R3 NEGATIVE (M7). Merging unconditionally is the same defect pointed the
    other way: one marker where the two series disagree hides the gap, which on
    this chart IS the finding."""
    tree = build([beat("dumbbell", **{**DUMBBELL, "rows": [
        {"label": "Eliciting physical signs", "values": [0.82, 0.58]},
    ]})])[0]["tree"]
    assert not find(tree, "dot merged")
    assert len(find(tree, "dot a")) == 1 and len(find(tree, "dot b")) == 1


@needs_node
def test_the_merged_marker_is_decided_per_row_not_per_chart():
    """R3 + R3 NEGATIVE in one chart, which is the real AMIE shape: four rows
    that coincide and one that separates. A decision taken once for the whole
    beat draws the wrong marker on one half of it either way."""
    tree = build([beat("dumbbell", **DUMBBELL)])[0]["tree"]
    assert len(find(tree, "dot merged")) == 1
    assert len(find(tree, "dot a")) == 1 and len(find(tree, "dot b")) == 1


@needs_node
def test_a_row_where_the_second_series_is_higher_also_separates():
    """R3 NEGATIVE, and a hole my own mutation sweep found: every fixture in
    this file put the FIRST series ahead, so `a !== b` and `a > b` were
    indistinguishable. Under `a > b` a row where the second entity rates higher
    merges — the chart draws "on par" over a real gap, hides a series and
    reverses the finding, which is the exact failure R3 exists to prevent."""
    tree = build([beat("dumbbell", **{**DUMBBELL, "rows": [
        {"label": "the other way round", "values": [0.4, 0.8]},
    ]})])[0]["tree"]
    assert not find(tree, "dot merged")
    assert len(find(tree, "dot a")) == 1 and len(find(tree, "dot b")) == 1


@needs_node
def test_two_markers_at_zero_still_merge():
    """The falsy rule inside R3. `0` is a legitimate position — "neither series
    was rated on this at all" — and a merge test written `if (a && a === b)`
    stacks two invisible dots at the left edge instead."""
    tree = build([beat("dumbbell", **{**DUMBBELL, "rows": [
        {"label": "at zero", "values": [0, 0]},
    ]})])[0]["tree"]
    merged = find(tree, "dot merged")
    assert len(merged) == 1
    assert merged[0]["css"].get("left") == "0%"


@needs_node
def test_the_footnote_reaches_the_stage_as_text_and_is_animated():
    """R2 NEGATIVE (M5). "Renders no numbers" must not become "renders nothing
    that explains itself". Spec §7.2 requires the footnote precisely because the
    chart has no axis: it is where "direction only" is said out loud, and the
    reader has nothing else to go on."""
    scene = build([beat("dumbbell", **DUMBBELL)])[0]
    foot = find(scene["tree"], "foot")
    assert foot, "the footnote never reached the stage"
    assert foot[0]["html"] is None
    assert foot[0]["text"] == DUMBBELL["footnote"]
    assert any(a["cls"] == "foot" for a in scene["anims"] if a.get("cls"))


@needs_node
def test_both_series_are_named_on_the_card():
    """`series[2]` is the only thing that says which colour is which entity. On
    a chart with no numeric axis and a two-tone marker, an unlabelled colour is
    not a series — it is a dot."""
    tree = build([beat("dumbbell", **DUMBBELL)])[0]["tree"]
    text = rendered_text(tree)
    assert "AMIE (video)" in text and "Primary care physician" in text


@needs_node
def test_the_caption_is_rendered_as_prose():
    """The caption is the sentence the chart illustrates, and it is authored
    text like every other prose field — the innerHTML defect Task 1 closed
    applies to it in full."""
    tree = build([beat("dumbbell", **{**DUMBBELL,
                                      "caption": "R&D on **video** <consults>"})])[0]["tree"]
    assert "R&amp;D on <b>video</b> &lt;consults&gt;" in rendered_text(tree)


@needs_node
def test_a_dumbbell_row_label_is_set_as_text_not_html():
    """R3's sibling from Task 2, on the new type. A `<tag>` in a row label set
    through innerHTML vanishes from the frame while script.yaml still says it."""
    tree = build([beat("dumbbell", **{**DUMBBELL, "rows": [
        {"label": "AT&T <legacy>", "values": [0.4, 0.4]},
    ]})])[0]["tree"]
    lab = find(tree, "lab")[0]
    assert lab["html"] is None and lab["text"] == "AT&T <legacy>"


@needs_node
def test_the_rows_keep_the_order_they_were_authored_in():
    """Same rule as jumpChart: the rows are a reading order, and a chart that
    reorders them tells a different story with the same dots."""
    rows = [{"label": n, "values": [0.5, 0.5]} for n in ["first", "second", "third"]]
    tree = build([beat("dumbbell", **{**DUMBBELL, "rows": rows})])[0]["tree"]
    assert [n["text"] for n in find(tree, "lab")] == ["first", "second", "third"]


@needs_node
def test_a_dumbbell_whose_markers_cannot_finish_separating_is_refused():
    """R1 on the new type. A row whose values differ animates one marker OUT of
    the other; cut off early it is drawn part-way, and a gap drawn at half its
    authored width is the "on par" finding on a row that is not on par. The
    figure this beat can get wrong is its direction."""
    rows = [{"label": f"row {i}", "values": [0.8, 0.4]} for i in range(4)]
    msg = refuses([beat("dumbbell", hold=1.0, **{**DUMBBELL, "rows": rows})])
    assert "dumbbell" in msg


@needs_node
def test_a_dumbbell_whose_rows_all_coincide_is_unaffected_by_the_hold():
    """R1 NEGATIVE on the new type. A merged marker does not travel: it is
    placed at its position and revealed. There is nothing to finish, so there is
    no hold it can fail to fit."""
    rows = [{"label": f"row {i}", "values": [0.5, 0.5]} for i in range(4)]
    scene = build([beat("dumbbell", hold=0.2, **{**DUMBBELL, "rows": rows})])[0]
    assert scene["tree"]["kids"]


@needs_node
def test_a_dumbbell_needs_no_citation():
    """R1 NEGATIVE from Task 2. `dumbbell` is not in the spec's cited pair, and
    for a reason that is the whole design of the type: it renders no numbers, so
    there is no number that has to be in a source."""
    scene = build([beat("dumbbell", **DUMBBELL)])[0]
    assert scene["tree"]["kids"]


# --- Task 3 Step 0: a beat that runs out of time --------------------------------
#
# Leader-verified against the real renderer, sampling the LAST frame render.mjs
# writes for a three-row kpis beat:
#
#     hold 2.0s -> last rendered frame: $0.75 in  $3.75 out  40% cheaper
#     hold 3.0s -> last rendered frame: $0.75 in  $3.75 out  50% cheaper
#
# At a 2-second hold the video's final frame reads 40% for an authored 50%. R2
# is defeated not by rounding but by running out of time: the mid-count value
# BECOMES the terminal value. D-083 allowed mid-count frames because such a
# value is unstable, bounded and derived — all three properties fail the moment
# the count cannot finish.

KPI_COUNTS_3 = {
    **KPIS,
    "items": [
        {"value": 0.75, "prefix": "$", "label": "per 1M input tokens", "decimals": 2},
        {"value": 3.75, "prefix": "$", "label": "per 1M output tokens", "decimals": 2},
        {"value": 50, "unit": "%", "label": "cheaper than 3.6 Flash"},
    ],
}


def required_hold(b: dict, engine: Path | None = None) -> float:
    return _node(expr="requiredHold(" + json.dumps(b) + ")", engine=engine)["value"]


@needs_node
def test_a_kpis_beat_whose_count_cannot_finish_in_its_hold_is_refused():
    """R1 (M1). The exact defect, at the exact hold the leader verified. The
    third row starts counting at 1.59s and takes 1.35s, so a 2s hold ends the
    beat — and, if it is the last beat, the video — at 40%."""
    msg = refuses([beat("kpis", hold=2.0, **KPI_COUNTS_3)])
    assert "2.94" in msg, msg
    assert "2" in msg and "kpis" in msg


@needs_node
def test_the_refusal_names_the_beat_the_hold_it_has_and_the_hold_it_needs():
    """R1. An operator fixes this by typing a number into script.yaml. A message
    that says "too short" and not "2.94" makes them binary-search it."""
    msg = refuses([beat("statement", text="a"), beat("kpis", hold=2.0, **KPI_COUNTS_3)])
    assert "beat 1" in msg
    assert "kpis" in msg
    assert "2.0" in msg or "2s" in msg
    assert "2.94" in msg


@needs_node
def test_a_hold_exactly_equal_to_the_requirement_renders():
    """R1's boundary, inclusive. The eased count is a quint: 1/30s before the
    end it is within 1e-8 of its target and rounds to the authored figure, so a
    hold that exactly contains the animation shows the authored number on the
    last frame. Exclusive here would refuse the beat the fix produces."""
    scene = build([beat("kpis", hold=2.94, **KPI_COUNTS_3)])[0]
    assert scene["tree"]["kids"]


@needs_node
def test_a_jumpchart_whose_bars_cannot_finish_growing_is_refused():
    """R1 on the other chart. jumpChart staggers by .34 and its gain segment
    starts .5 in and takes .8 — different constants, same failure: the last
    frame freezes a bar short of the value the row's own label states."""
    rows = [{"label": f"row {i}", "before": 1, "after": 2} for i in range(4)]
    msg = refuses([beat("jumpChart", hold=2.0, **{**JUMP, "rows": rows})])
    assert "2.62" in msg, msg
    assert "jumpChart" in msg


@needs_node
@pytest.mark.parametrize("kind", ["statement", "body", "list", "quote", "title", "signoff"])
def test_a_beat_with_no_count_is_unaffected_however_short_it_is(kind):
    """R1 NEGATIVE (M2). Nothing on these cards counts up to a figure, so a
    short one is a fast cut, not a false number. A check applied to every type
    would refuse the entire text vocabulary at any brisk pace."""
    scene = build([beat(kind, hold=0.1, **RENDERABLE_BEATS[kind])])[0]
    assert scene["tree"]["kids"]


@needs_node
def test_a_kpis_beat_whose_values_are_all_strings_is_unaffected():
    """R1 NEGATIVE (M2), where it is easy to get wrong. `kpis()` only calls
    `count()` for a numeric value; a string one is printed verbatim at p>0. A
    check keyed on the beat TYPE rather than on what actually counts refuses a
    legal card that has nothing to finish."""
    scene = build([beat("kpis", hold=0.1, **{**KPIS, "items": [
        {"value": "half", "label": "the price of 3.6"},
    ]})])[0]
    assert scene["tree"]["kids"]


@needs_node
def test_the_requirement_ends_with_the_last_item_that_actually_counts():
    """R1 NEGATIVE, finer. A trailing string item is drawn but never counts, so
    it must not extend the hold the beat demands — `items.length` is the wrong
    number to stagger from."""
    numeric_last = {**KPIS, "items": [
        {"value": 1, "label": "a"},
        {"value": 2, "label": "b"},
    ]}
    string_last = {**KPIS, "items": [
        {"value": 1, "label": "a"},
        {"value": 2, "label": "b"},
        {"value": "and rising", "label": "c"},
    ]}
    assert required_hold(beat("kpis", **numeric_last)) == required_hold(
        beat("kpis", **string_last)
    )


@needs_node
def test_the_requirement_moves_when_the_engines_stagger_does(tmp_path):
    """R1 (M3). The requirement must be COMPUTED from the constants the
    animation uses, not typed a second time in planbuild.js. Two copies of
    `.62` agree until somebody retimes the stack, and then the check silently
    passes beats that end mid-count again — which is this defect returning with
    a test that still says ok.

    So move the constant and watch the requirement follow."""
    b = beat("kpis", **KPI_COUNTS_3)
    slower = engine_with(tmp_path, "KPI_STAGGER=.62", "KPI_STAGGER=1.62")
    assert required_hold(b, slower) == pytest.approx(required_hold(b) + 2.0)


@needs_node
def test_the_requirement_moves_when_the_engines_count_duration_does(tmp_path):
    """M3's other half: the stagger is only one of the two constants, and a
    formula that derives one and hardcodes the other is half-fixed."""
    b = beat("kpis", **KPI_COUNTS_3)
    slower = engine_with(tmp_path, "KPI_COUNT_DUR=1.35", "KPI_COUNT_DUR=3.35")
    assert required_hold(b, slower) == pytest.approx(required_hold(b) + 2.0)


@needs_node
def test_the_jumpchart_requirement_moves_with_the_engines_growth_duration(tmp_path):
    """M3 on the type that staggers differently. jumpChart's bars grow from
    `JUMP_GROW_D0` for `JUMP_GROW_DUR`, and both are the engine's numbers."""
    rows = [{"label": f"row {i}", "before": 1, "after": 2} for i in range(4)]
    b = beat("jumpChart", **{**JUMP, "rows": rows})
    slower = engine_with(tmp_path, "JUMP_GROW_DUR=.8", "JUMP_GROW_DUR=2.8")
    assert required_hold(b, slower) == pytest.approx(required_hold(b) + 2.0)


# --- R1 negative: the documented HTML override stays HTML ------------------------


@needs_node
def test_jumpchart_shown_is_still_rendered_as_html():
    """M5. `shown` is a documented display override, not prose: the committed
    2026-08-14 episode renders `<s>34.4</s> &rarr; 43.6` through it and depends
    on both the strikethrough and the entity. Escaping every string in the
    engine would put the tags on screen."""
    out = _node(
        expr=(
            "(() => { const p = document.createElement('div');"
            " jumpChart([['FrontierCode 1.1', 34.4, 43.6,"
            " '<s>34.4</s> &rarr; 43.6']], 70, 0.5, p);"
            " const walk = (n) => [n, ...n.kids.flatMap(walk)];"
            " return walk(p).filter((n) => n.className === 'jval')"
            "   .map((n) => n.innerHTML); })()"
        )
    )["value"]
    assert out == ["<s>34.4</s> &rarr; 43.6"]


# --- R4: the engine does no timing arithmetic ------------------------------------


@needs_node
def test_meta_pace_stays_one_however_the_plan_is_paced():
    """M11, R4 NEGATIVE. `hold` in plan.json is ALREADY scaled by pace in
    Python. Passing the plan's pace to META would scale it a second time, and
    the render would silently disagree with the plan's own total_sec — which is
    what `agsoc video review` showed the operator before they approved."""
    meta = _node(
        plan={
            "episode": "2026-08-16",
            "series": "the-brief",
            "byline": "",
            "pace": 2.5,
            "beats": [beat(text="t")],
        }
    )["meta"]
    assert meta["pace"] == 1


@needs_node
def test_a_type_with_no_builder_still_fails_loudly():
    """R3's guard. Widening the builder table must not turn the gate into a
    silent skip: a beat that reaches Node with no builder is a plan.py bug, and
    a beat quietly missing from the video is the hardest kind to notice.

    Task 3 fills the table, so the exemplar can no longer be a catalogue type —
    every one of them draws now. It moves outside the catalogue instead, which
    narrows what this proves without making it dead: `render.mjs --plan` reads
    any JSON file and determinism.test.mjs writes its own, so a handwritten
    plan with a mistyped type is exactly where this fires."""
    proc = subprocess.run(
        ["node", "-e", HARNESS],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ENGINE": str(ENGINE),
            "PLAN": json.dumps(
                {
                    "episode": "e",
                    "series": "s",
                    "byline": "",
                    "beats": [beat("sparkline")],
                }
            ),
        },
    )
    assert proc.returncode != 0
    assert "sparkline" in proc.stderr

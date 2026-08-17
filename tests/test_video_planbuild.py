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


def _node(plan: dict | None = None, expr: str | None = None) -> dict:
    env = {**os.environ, "ENGINE": str(ENGINE)}
    if plan is not None:
        env["PLAN"] = json.dumps(plan)
    if expr is not None:
        env["EVAL"] = expr
    proc = subprocess.run(
        ["node", "-e", HARNESS], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


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


RENDERABLE_BEATS = {
    "statement": {"text": "a statement"},
    "body": {"text": "a body line"},
    "list": {"items": ["one", "two"]},
    "quote": {"text": "a quoted sentence", "attribution": "Someone"},
    "title": {},
    "signoff": {},
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
    tree = build([beat("body", text="t", kicker="Why it matters")])[0]["tree"]
    assert shown(find(tree, "kicker")[0]) == "Why it matters"


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
def test_an_unrenderable_type_still_fails_loudly():
    """R3's guard. Widening the builder table must not turn the gate into a
    silent skip: a `kpis` beat that reaches Node is a plan.py bug, and a beat
    quietly missing from the video is the hardest kind to notice."""
    proc = subprocess.run(
        ["node", "-e", HARNESS],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ENGINE": str(ENGINE),
            "PLAN": json.dumps(
                {"episode": "e", "series": "s", "byline": "", "beats": [beat("kpis")]}
            ),
        },
    )
    assert proc.returncode != 0
    assert "kpis" in proc.stderr

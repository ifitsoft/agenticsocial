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

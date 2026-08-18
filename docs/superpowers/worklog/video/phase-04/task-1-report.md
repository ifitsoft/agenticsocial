# Phase 4 · Task 1 report — the text beats, and closing the innerHTML divergence

**Branch:** `feat/video-phase-04-engine` · **Follows:** `5205a23`
**Commits:** `309c628`, `6ea6d19`, `d6219b2`, `8be15e7`, `64e53d0`

**MUTATION SCORE: 23/23** — 11/11 on the brief's table, 12/12 on my own sweep
(two of mine survived the first pass and are now killed; see §3).

---

## 1. What I implemented

### Step 0 — prose is text, not markup (`309c628`)

`escapeHTML` then `proseHTML` in `planbuild.js`, in that order, and `prose(t)`
as the drop-in for `P(t)` on every operator-authored field:

```js
function escapeHTML(t) {
  return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function proseHTML(t) {
  return escapeHTML(t).replace(/\*\*([\s\S]+?)\*\*/g, '<b>$1</b>');
}
```

`[\s\S]` rather than `.` because YAML folds long strings and a `**…**` an agent
wrote routinely arrives with a newline inside it. Lazy rather than greedy —
that one was a live mutant, see §3.

**One flag.** §"The markup vocabulary is closed" says the mechanism is already
there because `E` supports `opts.text`, and then gives a three-step rule ending
"set `innerHTML` with the result". Those are two different implementations and
they cannot both hold: `opts.text` cannot produce `<b>`. I followed the numbered
rule (code-block-shaped, and the only one that keeps `**bold**` working). I used
`opts.text` where the brief's reasoning does apply — the brand name, the date
and the byline on the title/signoff cards, which take no markup at all and where
`textContent` is a stronger guarantee than escaping.

### Step 2 — the five builders (`d6219b2`)

All six types compose from primitives and classes that already exist. **No CSS
was added.** `RENDERABLE` widens from `{statement}` to
`{statement, body, list, quote, title, signoff}`, and `BUILDERS` in
`planbuild.js` is held to that set by a test, so the D-036 two-lists drift
cannot happen silently.

| type | composition (all existing classes) |
|---|---|
| `body` | `.kicker` (fade) + `.body` (fade .9s) — 2026-08-14's paragraph card, verbatim |
| `list` | `.kicker` + optional `lead` as `.body` + `.stack sm` of `.item`(`<i>` + `<span>`), staggered slide-from-left |
| `quote` | `.lede` (fade) + `.rule blue` (draw) + `.kicker` for the name — **my design, see below** |
| `title` | `.big-title` (rise) + `.rule blue` (draw) + `.lede` date + optional `sub` as `.body` + `.byline` |
| `signoff` | `.big-title` + `.rule blue` + optional `text` as `.lede` + `.byline` |

`plan.json` changes, both necessary rather than opportunistic:

- beats now carry **their own type's fields**, driven off `BEAT_TYPES`
  (required then optional, only the keys the operator wrote) instead of one
  hard-coded `"text"`. A `title` beat has no `text` at all and would have
  `KeyError`d. Driving it off the catalogue rather than dumping `beat.fields`
  also keeps `claim_override` — Phase 5's input, not content — out of the
  renderer's reach.
- a top-level **`series_name`**. The title and signoff cards put the series name
  on screen at 150px and `the-brief` is a filesystem key. `planbuild` falls back
  to the slug, so a plan written before this key still renders a card.

### `quote` — which decisions were mine

Neither committed episode has one (D-069), so everything below is invented and
should be treated as *proposed*, not settled, by the storyboard skill:

1. **`.lede` (50px/600) for the words.** It is the largest class in the system
   that sets a *sentence* rather than a headline, and a quotation is someone
   else's sentence. `h1`/`h2` would make the speaker's words read as the
   episode's own claim.
2. **`.rule blue` drawn between the words and the name.** Spec §7.1 gives
   `quote` the motion "fade + rule draw" and this is the only thing on the card
   there is to draw. It is also the "named thing" idiom both episodes use
   (Gemini Spark, RuntimeWire).
3. **`.kicker` for the attribution**, with an inline `marginTop`.
4. **Explicitly NOT `.byline`**, though its `:before` dash suits an attribution
   perfectly. `seek()` does `SC.querySelector('.byline')` to suppress the
   persistent corner byline — so a quote beat would have silently hidden the
   episode's author. That is a chrome side effect a content beat must not have,
   and it is the reason `.byline` appears only on the title and signoff cards,
   where hiding the corner byline is exactly right.
5. **Considered and rejected: `.para`.** It is the closest thing to a
   pull-quote (left rule, 36px, ink-2), but in 2026-08-12 it is the watermark
   motif's own class — it carries the `.scan` overlay and reads as a passage of
   *machine* text. Wrong connotation for a human being's words.

**Consequence to be aware of:** `.kicker` carries `text-transform:uppercase`,
so an attribution renders as `GOOGLE DEEPMIND`. That is consistent with the
system (every small label in it is uppercase, including `.byline`), but it is a
design call, not a neutral one. If the storyboard skill wants mixed-case
attributions this needs a class and therefore a `scene.html` decision.

### Steps 3–4 — verification (`8be15e7`, `64e53d0`)

`determinism.test.mjs` gains a **plan-path case with one beat of every
renderable type** — the existing pixel and page-state checks run over it
unchanged, plus a per-beat assertion that the beat's words reach the stage's
`innerText`. No pixel golden files. The fixture is written to `.plan.js` and
whatever was there is restored afterwards.

---

## 2. TDD evidence

| step | RED | GREEN |
|---|---|---|
| 0 | 8 failed — `ReferenceError: proseHTML is not defined`, and the one beat-level test that could run reported `'R&D <today>' == 'R&amp;D &lt;today&gt;'` failing on the real file | 8 passed |
| 1+2 | **32 failed, 1040 passed** — 20 in the new harness, 11 in plan.py's per-type emission, 1 on the widened gate | 1067 passed |
| 3 | the new content check failed 2/6 on first run (`Live today in`, `Google DeepMind`) — a real finding, see §6 | deterministic |

**Final Python suite: 1068 passed, 1 warning in 5.66s.**

The harness (`tests/test_video_planbuild.py`) runs the real `engine.js` and
`planbuild.js` in a `node:vm` with a recording DOM — they are classic scripts
with no exports, the same constraint that makes `scene.html` use
`document.write`. One trap worth recording: `engine.js` declares
`function scene(...)`, so a stub `scene` installed before it is silently
overwritten and every scene list comes back empty — which looks exactly like a
builder that appended nothing. The harness builds through engine's own `SCENES`.

---

## 3. The mutation results

Method: apply one weakening to the real file, run
`tests/test_video_planbuild.py` (JS mutants) or the plan/script/review suites
(Python mutants), restore, record. Script and raw log kept at
`/tmp/p4t1/mutate.py`, `/tmp/p4t1/mutants.txt`.

### The brief's eleven — 11/11 killed

| # | mutant | killed by |
|---|---|---|
| M1 | prose back to `P()` / innerHTML | 6 tests |
| M2 | escape skipped | 9 tests |
| M3 | `**bold**` converted before escaping | 8 tests |
| M4 | `&` not escaped (only `<`, `>`) | 8 tests |
| M5 | `jumpChart.shown` escaped too | 1 test |
| M6 | `list` renders `lead`, drops `items` | 5 tests |
| M7 | `list` drops `lead` when items exist | 1 test |
| M8 | `quote` drops `attribution` | 1 test |
| M9 | a bare `title` renders nothing | 3 tests |
| M10 | a builder returns without appending | 3 tests |
| M11 | `META.pace` set from the plan | 1 test |

### My own sweep — 12/12 killed, **two only after adding tests**

| # | mutant | outcome |
|---|---|---|
| S1 | bold regex greedy, not lazy | **SURVIVED** → fixed |
| S2 | `>` not escaped (only `&`, `<`) | killed |
| S3 | list loses its `<i>` bullet | killed |
| S4 | list rows never animate in | killed |
| S5 | shared kicker helper uses `P()` | **SURVIVED** → fixed |
| S6 | title shows the slug, not the name | killed |
| S7 | signoff drops its closing line | killed |
| S8 | title drops its subtitle | killed |
| S9 | brand card not uppercased | killed |
| S10 | plan emits required fields only (drops `lead`, `sub`) | killed |
| S11 | plan spreads every field, `claim_override` included | killed |
| S12 | plan drops `series_name` | killed |

**S1** is the interesting one. A greedy `\*\*([\s\S]+)\*\*` passed every other
assertion in the file: it joins the first opener to the *last* closer, so
`**A** and **B**` becomes one bold run with the connective swallowed —
emphasis the operator never wrote, on words they did not choose. **S5**
survived because only `statement` builds its own kicker; the shared helper
every other type calls was tested with a kicker that had nothing to escape.
Both now have tests.

### And the browser half is not vacuous either

I re-ran a subset against **only** `determinism.test.mjs`, to check the new
content assertions can actually fail:

```
killed   M1  prose back to P()          FAIL beat 0 (statement) missing [...] · `**` reached the screen
killed   M2  escape skipped             FAIL beat 1 (body) missing ["AT&T raised prices &amp; nobody noticed"]
killed   M6  list drops items           FAIL beat 2 (list) missing ["Gemini API & AI Studio",...]
killed   M7  list drops lead            FAIL beat 2 (list) missing ["Tuned for coding & agents"]
killed   M8  quote drops attribution    FAIL beat 3 (quote) missing ["Google DeepMind"]
killed   M9  bare title renders nothing FAIL beat 5 (title) missing ["THE BRIEF","2026-08-16"]
killed   M10 builder appends nothing    FAIL beat 1 (body) missing [...]
killed   M11 META.pace from the plan    FAIL beat 3 (quote) missing [...]
```

**M9 and M11 survived the browser check on the first pass, and both were holes
in my test, not in the engine** (`64e53d0`):

- the content check read `#stage`, whose *chrome* carries the brand chip
  ("THE BRIEF") and the date — so a title card that rendered **nothing** still
  satisfied both of its expectations. It now reads `#scenes`, and the fixture
  has a bare `title` beat, which is R3's negative in the browser.
- the fixture had `pace: 1`, which makes double-scaling arithmetically
  invisible. It is now `1.293`, the real 2026-08-14 value.

---

## 4. Step 5 — a real render

A six-beat script, one of every renderable type, through the CLI. Workspace
under `/tmp` (nothing was written to the repo's `workspace/`).

```
the-brief/2026-08-17 · draft · 6 beats · pace 1.0

     #  act  type        hold  text                                               src
     0       title        3.6  Six beats, one of **every type** this phase can…
     1  01   statement    3.2  The model is <thinking> about it.
     2  01   body         4.2  AT&T raised prices, and the release notes still…
     3  01   list         4.2  A natively multimodal model tuned for **coding,…
     4  01   quote        4.0  “Gemini 3.7 Flash is our new workhorse model.” —…  [blog.google]
     5       signoff      3.8  Same time tomorrow.

holds 23.0s × pace 1.0 = runtime 23.0s
target 120s ± 8s · OUT OF TOLERANCE (-97.0s)
```

`agsoc video preview 2026-08-17 --series the-brief --probe` → 6 probe frames.
The page text at each probe frame's exact `t`:

```
─── s00.png  t=2.59s  (title) ───
THE BRIEF
2026-08-17
THE BRIEF
2026-08-17
Six beats, one of every type this phase can draw.
ALI ABDUKARIM
ALI ABDUKARIM

─── s01.png  t=5.90s  (statement) ───
THE BRIEF
2026-08-17
01 — THE HEADLINE
TODAY'S HEADLINE
The model is <thinking> about it.
ALI ABDUKARIM

─── s02.png  t=9.82s  (body) ───
THE BRIEF
2026-08-17
01 — THE HEADLINE
AT&T raised prices, and the release notes still say &amp; more to come — five characters, not one.
ALI ABDUKARIM

─── s03.png  t=14.02s  (list) ───
THE BRIEF
2026-08-17
01 — THE HEADLINE
LIVE TODAY IN
A natively multimodal model tuned for coding, agentic workflows and knowledge work.
Gemini API & AI Studio
Antigravity
<script> tags, rendered as text
The Spark agent
ALI ABDUKARIM

─── s04.png  t=18.08s  (quote) ───
THE BRIEF
2026-08-17
01 — THE HEADLINE
Gemini 3.7 Flash is our new workhorse model.
GOOGLE DEEPMIND
blog.google
ALI ABDUKARIM

─── s05.png  t=21.94s  (signoff) ───
THE BRIEF
2026-08-17
THE BRIEF
Same time tomorrow.
ALI ABDUKARIM
ALI ABDUKARIM
```

`<thinking>` is on screen. `AT&T` is on screen. `&amp;` is five characters. A
literal `<script>` renders as text. No `**` survived anywhere. Reading these
lines: the duplicated `THE BRIEF` / `ALI ABDUKARIM` on the title and signoff
cards is the chrome chip plus the card's own mark — the same doubling both
committed episodes have, and `seek()` drives the corner byline to opacity 0 when
a card draws its own (`innerText` still reads it; the frame does not show it).

**Regression, the hand-written path:**
`node render.mjs --day 2026-08-14 --probe` → `119.99s · 3600 frames`, 25 probe
frames, no page errors.

**Determinism:** `deterministic`, 0 failures — 3 day-path times, 7 plan-path
times, pixel + chrome-text + content for all 7 beats.

---

## 5. Files changed

| file | change |
|---|---|
| `engine/planbuild.js` | `escapeHTML`/`proseHTML`/`prose`; five builders + `planKicker`/`slideIn`/`planBrand`/`planByline`; `BUILDERS` dispatch; `META.title` |
| `engine/determinism.test.mjs` | all-types plan-path case, per-beat content assertions, `.plan.js` write+restore |
| `src/agenticsocial/video/script.py` | `RENDERABLE` widened to six |
| `src/agenticsocial/video/plan.py` | per-type field payload; `series_name` |
| `tests/test_video_planbuild.py` | **new** — 33 tests, the vm harness |
| `tests/test_video_plan.py` | 9 new tests; 3 pins updated (`SUPPORTED_BEATS`, key order, unrenderable exemplar → `custom`) |
| `tests/test_video_script.py` | 2 pins updated |
| `tests/test_video_review.py` | 4 tests re-pointed from `quote`/`title` to `custom`/`dumbbell` |

Commits, in order:

| sha | |
|---|---|
| `309c628` | fix: render prose as text, so the frame shows the verified bytes |
| `6ea6d19` | test: specify the five remaining text beats, from the mutant table |
| `d6219b2` | feat: draw body, list, quote, title and signoff beats |
| `8be15e7` | test: every renderable beat type puts its own words on the stage |
| `64e53d0` | test: close the four holes the mutation sweep found |

**Flag: five commits, not four.** The four are the four steps. The fifth holds
the two tests and the two determinism fixes the Step 4 sweep produced; folding
them into `d6219b2` or `8be15e7` would have been a rewrite of history, and
leaving them uncommitted was not an option. (The brief's ground rules say
"Three commits" while its checklist lists four commit points — I followed the
checklist and your instruction.)

`git status --porcelain -- src tests engine` is clean.

---

## 6. Issues and concerns

### 6a. Did any type need CSS that does not exist?

**No — nothing was added to `scene.html`.** Two near-misses worth recording:

- `quote` has no class of its own, and the honest answer is that the system has
  never been asked to set a quotation. `.lede` + `.rule blue` + `.kicker` is a
  composition, not a design. If quotes turn out to be frequent, a `.quote` class
  (a hanging quotation mark, or a left rule in `--blue` rather than `.para`'s
  grey `#C6D3E2`) is the right conversation to have — with `scene.html` open.
- attributions inherit `.kicker`'s `text-transform:uppercase`. Deliberate, but
  it is the one place where a *name* is being transformed by CSS.

### 6b. Is `**bold**` enough? — counted from the two committed episodes

49 scenes, and this is every piece of markup in them:

| markup | uses | covered by `**`? |
|---|---|---|
| `<b>` | **20** (11 + 9) | **yes** — this is what `**` is |
| `<br>` | 4 | **not needed.** Every one is inside `.big-title` on the title/signoff cards (`THE<br>BRIEF`), and those cards are now built by the *engine* from `series_name`, which wraps on its own. A script never authors them. |
| `<span class="warm-t">` | 2 | **no** |
| `<em>` | 1 | **no** |
| `<s>`, `&rarr;` | 5 | n/a — all inside `jumpChart.shown`, the documented exemption |

So: `**` covers 20 of the 23 script-authored markup uses, `<br>` is absorbed by
the builders, and **three uses across two episodes are a second, different
emphasis** — `<em>` (`em{font-style:normal;color:var(--blue)}`) and
`warm-t` (`color:var(--warm)`). Both mean the same thing: *this phrase is the
story*, said in colour rather than in weight. `<b>` in this system is
"important"; the accent is "this is the line the episode turns on", and
2026-08-12 and 2026-08-14 each used it exactly where the act pivots.

**My recommendation: widen by exactly one token now — `*accent*` → `<em>`.**
It is one line in `proseHTML`, the CSS already exists, it is the only markup in
the corpus that neither `**` nor the builders cover, and adding it later means
either a storyboard skill that cannot write the sentence both real episodes
needed, or an agent smuggling raw `<em>` through a field that would then have to
stop escaping. I did **not** implement it — the brief states the vocabulary is
closed at `**` and that is a spec decision, not mine. Say the word and it is a
one-line change with two tests.

I would **not** add `<br>` (nothing left to use it), and I would not add
`warm-t`: warm is act-level colour policy, and `series.toml` already has
`[structure] warm_acts` for exactly that — which is a separate finding, below.

### 6c. Anything still reaching `innerHTML` that a script can influence?

I audited every sink. Three answers:

1. **`jumpChart.shown` — yes, by design, and Phase 5 must know.** It is the
   documented exemption and 2026-08-14 depends on `<s>34.4</s> &rarr; 43.6`. But
   `shown` is an operator-authored *script* field once `jumpChart` becomes
   renderable (next task): it is the one field where a byte comparison between
   `script.yaml` and the frame will legitimately disagree, because `<s>` and
   `&rarr;` are markup that renders as a strikethrough and an arrow. Phase 5
   either exempts `shown` explicitly or verifies its *text after tag removal*.
   Silence here is a false failure at best and a hole at worst.
2. **`text-transform` is a second, quieter divergence.** `.kicker` and
   `.byline` uppercase their content in CSS, so a kicker written
   `Live today in` reads back from `innerText` as `LIVE TODAY IN`. The DOM
   holds the authored bytes; only the glyphs change. This cost me two failures
   in Step 3 and it will cost Phase 5 a false positive on *every kicker in the
   series* unless it folds case or reads `textContent`. It is commented in
   `determinism.test.mjs`.
3. **Everything else is clean.** `act_label`, `src`, the byline and the date all
   go through `textContent` in `seek()`/`init()`; the brand name goes through
   `opts.text`; design tokens go through `style.setProperty` and are validated
   in Python (Phase 3). `render.mjs` writes the plan to `.plan.js` loaded via
   `<script src>`, not inline, so a beat containing `</script>` cannot break
   out. The only remaining arbitrary-HTML path is the `custom` beat's `js`,
   which is unrenderable and, per spec §7.1, requires manual attestation.

### 6d. Two things the render surfaced that are out of this task's scope

- **`date_long` never reaches the screen.** The title card renders
  `2026-08-17`, where both committed episodes render `Friday, 14 August 2026`.
  Spec §7's script metadata *has* `date_long`, but `script.py` does not read it
  and `plan.json` does not carry it, so `planbuild` sets
  `dateLong: plan.episode`. Three lines to fix (parse it in `script.py`, emit
  it, prefer it in `planbuild`), and I deliberately did not: the brief scopes
  `title` to `sub?` and the metadata schema is not mine to widen. It should be
  fixed before anyone ships a title card.
- **`warm_acts` is declared in `series.toml` and dropped on the floor.**
  `planbuild` hard-codes `warmActs: []`, so an operator can configure a warm act
  and the chip stays blue. Same shape of defect as `date_long`; also out of
  scope here.

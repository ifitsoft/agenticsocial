# Phase 10 · Task 1 — wide format, a declared context

**Branch:** `feat/video-phase-10-wide` · **Spec:** §9 · **Baseline:** 1888 tests
**At HEAD:** 1900 Python tests, 4 Node suites green, **26/26 mutants**

---

## 1. How overflow is detected, and where

**Page-time, measured, once at init — and the plan-time alternative was
considered and rejected on the phase's own terms.**

`engine.js:checkFit()` walks every beat before the first frame:

1. builds the beat into the real `#scenes` box (the same box `seek()` builds
   into, so it is measured in the geometry it will be drawn in);
2. runs every registered animation at **p = 1** — the settled card, which is
   what a viewer reads. At p = 0 a risen word sits 115% below its line and every
   beat in the series "overflows";
3. compares the union of the scene column's children against the column's own
   rect for the vertical axis, and `scrollWidth − clientWidth` for the
   horizontal one. Both are needed and neither substitutes: `.sc` centres its
   column, so an overflowing card spills off **both** ends and `scrollHeight`
   only ever sees the bottom one; a block's own rect stays the width of its
   container however far the glyphs run past it;
4. restores `CUR = -1` and clears the stage, so nothing measured can survive
   into a frame;
5. on failure **throws**, naming every offending beat, its type, the overflow in
   px and the format it was measured in.

Two audiences, the way the CSP refusal already has two: the operator scrubbing
the slider reads `#fit` (inside `#ui`, which the render hides, so it can never
reach a frame), and the renderer gets an uncaught error — `render.mjs`'s
existing `pageerror` collector, which prints and exits **before frame 0** rather
than after nine hundred. That exit is now tested as a process, not as a promise:

```
  ok   vertical: render.mjs EXITS on an overflowing beat, before any frame
  ok   wide: render.mjs EXITS on an overflowing beat, before any frame
```

**Why not plan time.** How tall a paragraph sets is a property of the font this
machine resolved and of Chromium's line breaking — precisely the half D-116 says
no approval covers. Python could *estimate* it, and an estimate is a second
answer to a question the page already answers: D-007's rule (Python resolves
timing, Node does no arithmetic) pointed at layout instead of timing, and the
two answers disagree exactly at the boundary where it matters. The geometry that
*can* be computed without a font — the stage, the band, the measure — already is
computed in Python, and it is what the page measures against.

The cost of page-time is one browser launch (~1 s), not fourteen minutes. The
brief's preference for plan time was about not paying for a render before
finding out; this pays for a page load.

**It found a true positive on its first run**, in a fixture nobody had looked at
in that light: `determinism.test.mjs`'s hostile `shown` cell, escaped to text in
a `white-space:nowrap` `.jval`, ran **625 px past the measure**. Safely inert
and off the card. The injection was respelled shorter (`this.after(Date.now())`
inserts the timestamp exactly as the old spelling did, so the cross-load purity
check is still a real reproduction).

**Not crying wolf (R3 negative, D-040).** A card composed to within 18 px of its
safe area — computed from the format's own band, so it is the same card in both
formats — renders unremarked. Three real operator episodes and both committed
ones pass with nothing said.

---

## 2. `type_family` / `type_scale` — wired one, deleted the other

**`type_scale` is wired. `type_family` is retired.** This is D-077's split
(a human decision, adopted, never implemented) carried out in the phase that
owns layout.

**Why `type_scale` could be wired honestly.** It has three enumerated values, so
it validates like `register` does, and this phase gave it something real to
mean: it is the multiplier **on the format's scale**, so `compact` sets the type
smaller *and moves the measure with it* — more copy per card, not merely smaller
words. It is validated in Python at load (an unknown value is refused with the
list) and again in the renderer (a hand-written plan reaches the page without
passing through Python — `render.mjs --plan` reads any JSON). "Wired" is
measured, not grepped:

```
  ok   type_scale actually scales the type (compact < default < large)
  ok   an unknown type_scale is refused rather than silently defaulted
```

**Why `type_family` had to go.** It is the one design value that **cannot be
checked**: whether `"SF Pro Display"` resolves is a property of the render host,
not of the string, so a stack naming a family this machine lacks falls back
silently — the same silent-wrong-render class the hex-colour rule exists to
close. Making it honest means embedding fonts as data URIs and validating
against the embedded set, which is a feature, not a knob. Wiring it would have
been worse than deleting it: an operator would then believe a knob that fails
silently on someone else's machine.

**Retired, not refused.** It is a line in a file the operator owns; every
`series.toml` this tool has scaffolded contains it, including the one behind the
three real episodes. Refusing to load over a key that now does nothing would
cost them every command in the tool. So: the scaffold stops writing it, a load
warns once (moved out of `validate_design`, which runs twice per command by
design — a refusal raised twice costs nothing, an advisory printed twice reads
like a fault), and the series still loads.

**The approval stays honest, which was the other half of D-116.** `plan.json`
now copies `[design]` through `series.render_design()`, and
`_SERIES_RESOLVERS["design"]` resolves through the *same function* — so the
approval binds exactly what reaches the frame. That closes the false positive
in drift (an operator editing a font stack no longer invalidates an approval
over a value no pixel depends on) without narrowing coverage: neither function
enumerates the keys it keeps, so a `[design]` token added tomorrow is still
covered with no edit anywhere (D-116's property, preserved).

Verified by grep, the way the gap was found: `type_scale` appears in `engine/`,
`type_family` appears nowhere in it — and that grep is now a test.

---

## 3. TDD evidence and the mutation score

**Tests first.** `6830f26` commits `tests/test_video_format.py` and
`engine/format.test.mjs` failing: **14 of 15** Python tests failed and **12**
Node checks failed (the fifteenth — "type_scale reaches the plan" — passed
already, because `[design]` was copied whole; that is the half of D-116 that was
never the problem).

```
FAILED tests/test_video_format.py::test_the_plan_carries_the_format_it_was_built_for
  - agenticsocial.video.plan.PlanError: unsupported format 'wide' — this phase ...
FAIL vertical: a beat that does not fit its safe area is refused, naming the beat
  — (no page error at all — it was clipped silently)
FAIL type_scale actually scales the type (compact < default < large)
  — compact=212.15625 default=212.15625 large=212.15625
```

**Mutation sweep — 26 mutants, `PYTHONDONTWRITEBYTECODE=1` (D-100), exit codes
read unpiped (D-105).** Harness: `mutants.sh` (in the job's scratch directory;
each mutant is a one-line source edit, applied, run, reverted).

```
M7a  KILLED    wide declares the vertical stage (1080x1920)
M7b  KILLED    the plan drops the format it was built for
M7c  KILLED    render.mjs ignores plan.format and hardcodes the viewport
M2a  KILLED    wide runs at a different pace
M8a  KILLED    vertical's safe area silently moves to §9's numbers
M8b  KILLED    every format writes plan-vertical.json
M1a  KILLED    the stage never declares its measure
M1b  KILLED    the scale is declared and never applied
M1c  KILLED    planbuild stops handing the format over
M4a  KILLED    overflow is measured and never refused
M4b  KILLED    the fit check runs in the narrow context only
M4c  KILLED    only the bottom overflow is looked for
M4d  KILLED    a word past the measure is not overflow
M4e  KILLED    the tolerance is widened until nothing overflows
M4f  KILLED    the refusal never reaches the runner (it is only drawn in #ui)
M6a  KILLED    fit is measured before the animations land (p=0)
M3a  KILLED    the fit check leaves its last scene on the stage
M9a  KILLED    the format line stops saying it was not approved
M9b  KILLED    the probe screen never names the format
M9c  KILLED    the render screen never names the format
M10a  KILLED    the retired token is copied into the plan again
M10b  KILLED    the approval binds a token that reaches no frame
M10c  KILLED    an unknown type_scale is accepted in Python
M10d  KILLED    an unknown type_scale is accepted in the renderer
M10e  KILLED    type_scale is read and ignored
M10f  KILLED    a series that still declares type_family is refused
----- 26 mutants · 26 killed · 0 survived
```

**The first sweep was 24/26, and both survivors were gaps in my tests** (D-118's
lesson: a test written to kill a mutant is not the same as a test that kills it).

* **M4c — the top of the card was never checked.** `.sc` centres its column, so
  every overflowing fixture also spilled downward and the `below` half caught
  all of them on its own. Fixed with a `custom` beat pushed off the top — the
  escape hatch is the one builder that can position its own element. It needed
  `position:relative` rather than a negative margin: a centring flex column
  absorbs the margin into its free space and puts the card back on screen.
* **M6a — nothing pinned *when* the fit is measured.** Every fitting fixture was
  small enough that `fade`'s 26 px entrance offset did not push it off, so
  measuring at p = 0 survived. Fixed with the card composed to within 18 px of
  its safe area, which is also R3's negative half stated as a test.

**Regression evidence for R4's negative half — vertical does not move.** Not
asserted, measured, and not as committed golden files (Phase 4's ruling stands):

* the two committed episodes, 51 probe-style frames, SHA-256 of every PNG plus
  the page text at each: **identical before and after** the whole change;
* the three real operator episodes in a *copy* of `workspace/`, 71 probe frames
  via `agsoc video probe`: **every PNG hash identical**. Only `plan-*.json`
  changed, as intended (the format record grew, `type_family` left).

`determinism.test.mjs` now runs the plan path in **both** contexts — same beats,
same seek times, two stages — and shipped green in the same commit as the engine
change. `network.test.mjs` and `coverage.test.mjs` green. Full suite: **1900
passed** (`pytest exit 0`, unpiped).

---

## 4. Step 6 — looking at it

### The same episode, the same instant, both formats

`the-brief/2026-08-17b`, `t = 42.9` (spec §9's own example), page text of
`#stage` read out of the live page:

```
--- vertical · t=42.9 · stage 1080x1920 · scene column 888x1180 at (96,400)
THE BRIEF
2026-08-17B
02
2.4T
total parameters
95B
active parameters
_pasted
--- wide · t=42.9 · stage 1920x1080 · scene column 1178x700 at (120,200)
THE BRIEF
2026-08-17B
02
2.4T
total parameters
95B
active parameters
_pasted
```

Same words, same instant, different geometry — R2 exactly. The two PNGs were
opened and looked at: vertical stacks the two figures with their rules; wide
puts them in a single row (§9's table), chrome inset to the margins, no clipping
and no overlap.

The plans agree on everything that is not layout:

```
vertical format: {"name":"vertical","w":1080,"h":1920,"safe_top":400,"safe_bottom":1580,"measure":"narrow","scale":1.0}
wide     format: {"name":"wide","w":1920,"h":1080,"safe_top":200,"safe_bottom":900,"measure":"wide","scale":0.62}
timing equal   : True   119.996s / 3600 frames
beats equal    : True
```

### A wide render, end to end, through the gate

A short (10 s) episode built in a throwaway workspace, taken through the real
commands — `check` → `approve --by` → `render --format wide`:

```
the-brief/2026-08-18 · rendered
      file     …/out/wide-1920x1080.mp4
               1.1 MB · 10.0s · 1920x1080 · 300 frames @ 30fps
      format   wide · 1920x1080 · chosen at render time and NOT part of the approval — one approval
               renders every format, and the approver saw none of them
      approved Phase 10 harness at 2026-08-18T15:20:08-05:00 — and nothing you authored has changed
               since: the beats, `pace` and series.toml's design are the ones that were signed
      scope    the approval does NOT cover what drew these frames — …
```

`ffprobe`:

```
codec_name=h264
width=1920
height=1080
pix_fmt=yuv420p
r_frame_rate=30/1
nb_frames=300
format_name=mov,mp4,m4a,3gp,3g2,mj2
duration=10.000000
size=1063228
```

A frame was extracted from that mp4 at t = 5.5 s and looked at — see §6.1, which
is the visual finding it produced.

---

## 5. Files changed and commits

```
6830f26  test: pin the wide format as a declared context, and overflow as loud
95b964d  feat: one layout system, two declared contexts — and overflow is loud
97aec06  feat: --format wide end to end, and the type knobs resolved
9ebb969  test: the two survivors the sweep found, and the advisory said once
```

```
 engine/determinism.test.mjs       |  65 +++-      both formats, one plan
 engine/engine.js                  | 169 ++++-     format context, fit check, kpi cells
 engine/format.test.mjs            | 419 +++++     new
 engine/network.test.mjs           |  16 +-        whole format in its plans
 engine/planbuild.js               |  10 +-        hands over format + type_scale
 engine/render.mjs                 |  20 +-        viewport from plan.format
 engine/scene.html                 |  65 +++-      one stylesheet, two contexts
 src/agenticsocial/video/cli.py    |  21 ++        the format line on both screens
 src/agenticsocial/video/plan.py   |  62 +++-      FORMATS, render_design
 src/agenticsocial/video/series.py |  77 ++++-     TYPE_SCALES, RETIRED_DESIGN_TOKENS
 tests/test_video_format.py        | 323 +++++     new
 tests/test_video_plan.py          |  41 +-
 tests/test_video_render_cmd.py    |   9 +-
 tests/test_video_series.py        |  23 +-
```

`git status --porcelain -- src tests engine` is clean. `workspace/` is
byte-identical to the backup taken before this task (`diff -r`); everything that
needed a real episode ran against a **copy** at
`…/jobs/9a014c11/tmp/workspace-sandbox`, so the three real episodes were never
loaded for writing, never approved and never edited.

---

## 6. Issues, concerns, and what is still wrong

### 6.1 What can still be visually wrong with every check green

**Be specific, so:**

1. **A beat with little content reads as lost in 16:9.** The frame extracted
   from the wide mp4 is one `body` line — 25 device px of type on a 1920×1080
   frame with ~1500 px of empty space around it. It is not a *bug*: relative to
   frame **height** the type is actually marginally larger than vertical's
   (2.3% vs 2.1%), which is the right ratio for legibility. It is a
   **composition** failure, and no check in this project can see it: the words
   match the source, nothing drifted, the frame equals itself and nothing
   overflows. Sparse cards want a different treatment at 16:9 (a larger scale
   for short beats, or a second column), and that is a design decision, not a
   layout-system one.
2. **The right third of the wide frame is empty by construction.** `measure` is
   1900 layout px = 1178 device px of a 1680 px band, left-aligned. That is a
   deliberate typographic choice (0.62 scale across the full width would give
   ~110-character lines) and it is *mine*, not the operator's and not the
   approver's. It looks intentional at a glance and nobody signed it.
3. **Only two things were looked at.** Both formats at one `t` of one episode,
   and one frame of one 10 s render. Fourteen beats × two formats × three real
   episodes is roughly 150 cards nobody has opened. `probe --format wide` makes
   that cheap; this task did not do it.
4. **The fit check measures the settled state only.** A card that fits at p = 1
   can still be off the card mid-entrance — `fade`'s 26 px, `slideIn`'s 30 px —
   for a fraction of a second. That is by design (a moving element arriving is
   not an overflow), but it means an animation retimed to a large offset could
   put words briefly outside the safe area with everything green.
5. **Left overflow is not detected.** `scrollWidth` sees the inline end only, so
   an element pushed off the *left* of the card is invisible to the check. It
   was left that way deliberately: a symmetric check over all descendants
   flagged the dumbbell's markers, which legitimately hang 14.5 px into the
   padding — crying wolf on a committed episode is worse than the gap (D-040).
   Worth closing properly with a per-element rule that knows about markers.

### 6.2 Does one script legitimately produce both formats?

**Mostly, and the exceptions are real.** Everything measurable came out clean:
the same words, the same DOM, the same instant, nothing overflowing, three real
episodes and two committed ones. Because the wide band is 700 px at 0.62 scale
= **1129 layout px** against vertical's 1180, a beat that fits one very nearly
fits the other — that near-equality is what makes the claim true, and it is why
§9's own 120…960 was not copied (see 6.3).

What does **not** survive the rotation is anything the author composed *for* the
shape: a headline broken to land on three lines at 9:16 lands on two at 16:9, a
sparse card reads as empty (6.1.1), and a nine-word `statement` that fills a
phone screen is a caption on a laptop.

**That is a schema change and it is out of this task**, deliberately and stated
rather than discovered: per-format text means a beat field that varies by
format, which changes what `approve` signs (an approval would then bind text the
operator may not have read in both shapes) and what Phase 5 verifies (two texts,
one claim). It should be its own task, and my recommendation is to resist it —
the cheaper answer is a format-aware *scale* for sparse beats, which is layout
and needs no schema.

### 6.3 Flags against the brief and the spec

1. **The safe-area numbers in §9 are not the ones I shipped, in both formats.**
   §9 gives vertical `safeTop:430, safeBottom:1560`. `scene.html` has shipped
   `400…1580` since Phase 1.5; it is what both committed episodes and three real
   ones were composed against, and R4's negative half requires vertical to be
   byte-identical. **The code wins and this is the flag.** Wide's band was then
   derived rather than copied: §9's `120…960` leaves a card ending at 960 with
   no margin above a source tag, and 200…900 both clears the chrome and gives
   the two formats near-equal room in layout units (the property 6.2 rests on).
   The arithmetic is in `plan.py`'s comment. If the leader prefers §9's numbers
   literally, vertical cannot stay byte-identical and that trade should be made
   explicitly.
2. **`agsoc video render <ep>` "every enabled format" (§9's CLI block) is not
   implemented.** `--format` takes one name and defaults to `vertical`. Neither
   the brief's R4 nor the plan's Task 3 asked for the all-formats form, so it is
   out of scope — but §9 shows it and it does not exist.
3. **`[formats] enabled` in `series.toml` is still read by nothing but the
   `series list` screen.** `render --format wide` works on a series whose
   `enabled` list omits `wide`. I did not wire it: a per-series format gate is a
   *policy* decision that interacts with R5 (the format is outside the
   approval), and inventing it mid-task is how a knob nobody asked for arrives.
   It is either a real gate or it should stop being a config key.
4. **`agsoc video preview` still has no `--format`**, although
   `render.preview()` takes one. Out of R4's scope (which names `render` and
   `probe`), but it is now the only path that cannot ask for a format.
5. **`type_scale`'s multipliers are mine.** §6 documents the three names and no
   numbers; I chose `compact 0.88` / `large 1.12` because they are visibly
   different without breaking any committed layout. Nothing outside `engine.js`
   depends on the values.
6. **The brief's preference for plan-time overflow refusal was not followed**,
   with the argument in §1. Flagging it as a deliberate divergence rather than
   an oversight.
7. **`engine/` is still unpackaged (D-056 / D-120), carried.** `ENGINE_DIR` is
   still a `parents[3]` count, so `render` works from a source checkout and
   nowhere else. Untouched by this task.

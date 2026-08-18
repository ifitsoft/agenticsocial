# Task 2 Report: The chart beats — `kpis` and `jumpChart`

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Follows:** `9830fc5`

**Mutation score: 20/20** (11 from the brief's table, 9 from my own sweep).
Python suite: **1137 passed**. `determinism.test.mjs`: **deterministic**.
`node render.mjs --day 2026-08-14 --probe`: **25 probe frames, exit 0**.
`git status --porcelain -- src tests engine`: **clean**.

---

## 1. What I implemented

### Step 0 — one more prose token (`180ae8b`)

`*accent*` → `<em>`, alongside `**bold**`, in `proseHTML`. Escape first, then
`**`, then `*`. The second ordering matters for the same reason as the first in
miniature: a single-asterisk pass run before the double one takes the **first
`*` of every `**` opener** and emphasises from there — `**half**` becomes
`<em>*half</em>*`. No CSS: `scene.html:79` already styles `em` as colour rather
than italics, which is what D-080 asked for.

Not `<br>`, not `warm-t`.

### R1 — the renderer's own citation gate

`planbuild.js` refuses to build a `kpis` or `jumpChart` beat without a non-blank
`src` **and** `quote`. The schema already refuses one (`cited: True`), and that
is not sufficient: **a plan can reach the page without passing through Python at
all.** `render.mjs --plan` reads any JSON file, and `determinism.test.mjs` writes
its own `.plan.js` by hand. A gate the renderer cannot see is a gate on the
honest path.

For the renderer to enforce it, the citation has to reach it, so `plan.json` now
carries `quote` — for the cited types **only**, driven off `BEAT_TYPES[...]
["cited"]`. On an uncited type there is nothing to enforce and a `quote` key in
front of the renderer is one more field it has no business drawing.

The check runs **eagerly**, inside `buildKpis(b)` before the closure is returned,
not inside the closure `seek()` calls. A throw from inside a build closure fires
at the frame that scene first appears on, and `render.mjs` inspects page errors
only after `goto` (which is `seek(0)`) and again at the end — a bad beat 14 would
be reported after nine hundred frames had been written. `refuses()` in the test
file calls `buildFromPlan` and nothing else, so eagerness is pinned, not assumed.

### R2 — every number the frame displays is a number the plan carried

A kpi value is refused when rounding to `decimals` would change it, in **both**
languages: `script.py::kpi_items` (the authored gate, with the good message) and
`planbuild.js::requireExactAtDecimals` (the renderer gate, for the same
plan-can-bypass-Python reason).

Two things worth reading twice:

**`decimals` is optional, and its absence is not "print it as written".**
`count()` is `decimals ? v.toFixed(decimals) : Math.round(v).toLocaleString()`,
so an omitted `decimals` takes the `Math.round` branch. `value: 0.75` with no
`decimals` reaches the frame as **`1`**. Absent is therefore checked as `0`. That
is where the hole was widest, and the first thing the rule caught was a fixture
already in the tree: `test_video_review.py`'s `kpis` exemplar was
`{"value": 0.75, "unit": "$", "label": "per 1M input tokens"}` — it would have
rendered `1` and nothing would have said so.

**The negative half is enforced just as hard.** Prefix, suffix and thousands
separators are presentation: `$0.75`, `50%` and `~2,000` are how figures *read*,
not what they *are*. The builder additionally **composes** prefix and suffix onto
non-numeric values, because `kpis()` reads them only inside `count()` and would
silently drop them on the string branch — dropping an authored symbol is the same
divergence as inventing one, pointed the other way.

The message reports the glyphs the engine would actually draw, which needs
`ROUND_HALF_UP` on a `Decimal(repr(value))`: Python's `round`/`format` are
half-to-even, so `format(0.75, '.0f')` is `0` where the engine renders `1`, and
an error naming a number the frame never shows sends the operator hunting.

### R3 — one field is HTML, everything else is text

`jumpChart.shown` is set through `html:` (the documented override the committed
episode depends on for `<s>34.4</s> &rarr; 43.6`). Every label, the footnote and
every `.u` unit line is set through `text:`.

### R4 — outside `[0, scale]` is refused, not clipped

Cross-field, so `BEAT_TYPES` grew a `cross` hook — a callable over the validated
payload — rather than a branch inside `_beat`. The engine positions every dot at
`value / max * 100 + '%'`; a row above the scale lands off its track. **Clipping
would be worse than refusing:** the bar would sit at 100% and read as the
maximum, which is a number nothing in the script says. Inclusive at both ends.

### R5 — no timing arithmetic

`META.pace` still hard-coded to 1. The footnote's fade offset is per-**row**
layout (`0.3 + rows.length * 0.34 + 0.6`); `hold`, `start`, `end` and the plan's
`pace` are never read by a builder.

### One thing outside the brief, found by the sweep

`cli.py::_kpi` — the `agsoc video review` summariser — positioned the symbol from
a table of currency characters (`$ £ € ¥` before the number, everything else
after). That is the review line an operator approves, and with `unit: "$"` it
read `$0.75` while the frame would have rendered `0.75$`. Now `prefix + value +
unit`, the same order `planbuild.js` composes, with a test.

---

## 2. TDD evidence

Four commits, RED before GREEN in each pair.

**Step 0 RED** (reverting only the new `.replace`, `/tmp/step0-red.txt`):

```
FAILED tests/test_video_planbuild.py::test_accent_produces_an_em - AssertionError: assert 'it *doubles* in 2027' == 'it <em>doubles</em> in 2027'
FAILED tests/test_video_planbuild.py::test_bold_and_accent_in_one_string_stay_one_of_each
E         - <b>half</b> the price, <em>twice</em> the speed
E         + <b>half</b> the price, *twice* the speed
2 failed, 33 deselected
```

**Task RED** at `e61d9b3` — **48 failed, 1090 passed**:

| file | failures |
|---|---|
| `tests/test_video_planbuild.py` | 26 |
| `tests/test_video_script.py` | 15 |
| `tests/test_video_plan.py` | 6 |
| `tests/test_video_review.py` | 1 |

**GREEN** at `2344932`, and after the determinism commit:

```
1137 passed, 1 warning in 7.84s
```

No network in the Python suite (`tests/test_no_network.py`: 3 passed). No new
dependencies; `decimal` is stdlib.

---

## 3. Mutation score — 20/20

Each mutant was applied to the working tree, the four affected test files run,
and the tree restored. Script and raw output: `/tmp/sweep.py`.

### The brief's eleven

| # | Mutant | Result | First test to fail |
|---|---|---|---|
| M1 | `kpis` renders without `src`/`quote` | KILLED | `test_a_chart_refuses_to_render_without_a_citation[src-kpis]` |
| M2 | `title` made to require `src`/`quote` | KILLED | `test_every_type_renders_visible_content[title]` |
| M3a | `round(value, decimals) != value` accepted (renderer) | KILLED | `test_a_kpi_value_display_rounding_would_change_is_refused` (planbuild) |
| M3b | `round(value, decimals) != value` accepted (schema) | KILLED | `test_a_kpi_value_display_rounding_would_change_is_refused` (script) |
| M4 | prefix/suffix refused as "invented" | KILLED | `test_every_type_renders_visible_content[kpis]` |
| M5 | `shown` escaped like prose | KILLED | `test_jumpchart_shown_reaches_the_value_cell_as_html` |
| M6 | a `kpis` label rendered via `innerHTML` | KILLED | `test_a_kpi_label_is_set_as_text_not_html` |
| M7 | a row value above `scale` clipped silently | KILLED | `test_a_row_above_the_scale_is_refused_not_clipped[before]` |
| M8 | a row value equal to `scale` refused | KILLED | `test_a_row_equal_to_the_scale_renders[before]` |
| M9 | rows rendered in a different order than authored | KILLED | `test_jumpchart_rows_render_in_the_order_they_were_authored` |
| M10 | `footnote` dropped | KILLED | `test_the_footnote_reaches_the_stage_as_text` |
| M11 | `META.pace` set from the plan | KILLED | `test_meta_pace_stays_one_however_the_plan_is_paced` |

M3 was split because the rule lives in two languages and a single mutant would
have let either half be vacuous. Both halves die on their own.

### My own sweep

| # | Mutant | Result | First test to fail |
|---|---|---|---|
| S1 | absent `decimals` treated as "no rounding" (renderer) | KILLED | `test_a_kpi_value_is_refused_when_decimals_are_absent_and_it_is_not_whole` |
| S1b | absent `decimals` treated as "no rounding" (schema) | KILLED | `test_a_kpi_value_with_no_decimals_must_already_be_whole` |
| S2 | citation check reads `src` twice and forgets `quote` | KILLED | `test_a_chart_refuses_to_render_without_a_citation[quote-kpis]` |
| S3 | truthiness on `value` drops the zero row | KILLED | `test_a_zero_kpi_value_still_draws_a_row` |
| S4 | `plan.json` stops carrying `quote` | KILLED | `test_a_cited_beat_carries_its_quote_to_the_renderer[kpis]` |
| S5 | `unit` composed as a prefix instead of a suffix | KILLED | `test_the_kpi_figures_that_reach_the_screen_are_the_plan_s_own` |
| S6 | `*accent*` converted before `**bold**` | KILLED | `test_bold_still_bolds` |
| S7 | footnote set through `innerHTML` | KILLED | `test_the_footnote_reaches_the_stage_as_text` |

### Non-vacuity of the browser half

The Python harness and the browser test catch different failures, so the
determinism extension was mutation-checked separately:

```
# footnote dropped from buildJumpChart
  FAIL beat 8 (jumpChart) missing ["Scores as published by Google"]
  1 FAILURES

# decimals + 1 on every numeric kpi
  FAIL beat 7 (kpis) missing ["50%"]
  1 FAILURES
```

---

## 4. Step 5 — a real render, and the page text

A real workspace, a real series, a five-beat `script.yaml` with the real
`$0.75 / $3.75` figures and the real four `jumpChart` rows, through
`build_plan` → `render.mjs --plan --probe`.

```
$ agsoc video review 2026-08-14 --series the-brief
the-brief/2026-08-14 · draft · 5 beats · pace 1.0

     #  act  type        hold  text                                               src
     0       title        4.0  Two charts, and every number in them from a sour…
     1  01   kpis         4.6  $0.75 per 1M input tokens · $3.75 per 1M output…   [venturebeat]
     2  01   body         3.4  That is introductory pricing. It holds through 2…
     3  01   jumpChart    5.4  FrontierCode 1.1 · DeepSWE v1.1 · AutomationBenc…  [deepmind]
     4       signoff      3.0  Same time tomorrow.

$ node render.mjs --plan .../plan-vertical.json --probe --out /tmp/step5/probe
2026-08-17 · 20.40s · 612 frames @ 30fps
5 probe frames → /tmp/step5/probe
```

### `kpis` — page text of the probe frame (`#scenes` innerText, t = 7.31s)

```
AND IT COSTS HALF OF WHAT 3.6 FLASH DID
$0.75
per 1M input tokens
$3.75
per 1M output tokens
50%
cheaper than 3.6 Flash
```

### `jumpChart` — page text of the probe frame (t = 15.89s)

```
BENCHMARKS AGAINST 3.6 FLASH
FrontierCode 1.1
34.4 → 43.6
DeepSWE v1.1
48–49 → 65.3
AutomationBench
17.0 → 30.4
GDP.pdf
22.0 → 34.0
Scores as published by Google, on a common 0–70% scale. The DeepSWE v1.1 baseline is reported as a 48–49% range.
```

Every digit on both frames is a digit in `script.yaml`. `$`, `%` and the arrow
are the only glyphs the renderer added, and none of them is a number. `&rarr;`
reached the frame as an arrow rather than as six characters; `<s>` muted the old
score rather than printing as a tag. I looked at the PNGs: both cards sit inside
the safe area, the KPI rules draw under each row, and the four dumbbells land at
the right fractions of their tracks.

---

## 5. Files changed, and the commits

| Commit | Message |
|---|---|
| `180ae8b` | feat: widen the prose vocabulary by one token, `*accent*` -> `<em>` |
| `e61d9b3` | test: pin the two strictly verifiable beat types, R1 through R5 |
| `2344932` | feat: draw the kpis and jumpChart beats, and refuse the numbers they invent |
| `8f62cfa` | test: both chart types on a real page, read as numbers rather than as pixels |

- `engine/planbuild.js` — `*accent*`; `requireCitation`, `requireExactAtDecimals`,
  `planKpiItems`, `buildKpis`, `planJumpRows`, `buildJumpChart`; two `BUILDERS` rows.
- `engine/determinism.test.mjs` — two fixtures, and a per-fixture sample fraction.
- `src/agenticsocial/video/script.py` — `RENDERABLE` +2; `prefix` and the R2 check
  in `kpi_items`; `jump_rows_within_scale` and the `cross` hook; `_as_displayed`.
- `src/agenticsocial/video/plan.py` — `quote` for the cited types.
- `src/agenticsocial/video/cli.py` — `_kpi` reads the way the frame reads.
- `tests/test_video_planbuild.py`, `tests/test_video_script.py`,
  `tests/test_video_plan.py`, `tests/test_video_review.py`.

No new CSS, no new dependencies, no engine.js change.

Consequential test edits, all of them because behaviour genuinely changed:

- `test_renderable_is_exactly_this_phases_types` / `test_supported_beats_...`:
  six → eight.
- `test_a_full_catalogue_script_still_exits_zero`: "4 beats" → "2 beats".
- two `kpis` exemplars gained `decimals: 2` — **they were latent defects**, see §1.
- `test_an_unrenderable_type_still_fails_loudly` now uses `dumbbell`. With `kpis`
  it would have kept passing on the *citation* gate rather than the
  unsupported-type one, i.e. gone vacuous.

---

## 6. Issues and concerns

### 6.1 Is R2 sufficient? — the mid-count frame

**No, and this is the most important thing in the report.** But not for the
reason the question suggests, and the fix is not to abandon count-up.

`__seek(t)` samples mid-count. Here is the real Step 5 beat, read frame by frame
off the page:

```
t=4.40  ["$0.13","$0.00","0%"]
t=4.80  ["$0.65","$0.00","0%"]
t=5.20  ["$0.74","$2.28","0%"]
t=5.60  ["$0.75","$3.59","2%"]
t=6.00  ["$0.75","$3.75","42%"]
t=6.50  ["$0.75","$3.75","50%"]   ← and stable to the end of the hold
```

`$0.74`, `$2.28` and `42%` are in no source, in no quote and in no plan. Roughly
2.9 seconds of a 4.6-second beat contains at least one such figure. So the
premise is correct: **most frames of a `kpis` beat show numbers nobody
authored.**

I argue that this does not defeat R2, on three grounds, and that the distinction
is not a rationalisation but a structural one.

1. **A mid-count value is never stable, and a claim is a reading.** The count-up
   is a convention with a settled meaning — "this number is arriving". Nothing on
   a moving counter is offered as a figure; the figure is what it stops on, and
   what it stops on is the plan's. `0.756 → $0.8` is the opposite in every
   respect: it is stable, it is the only reading available, and it is therefore
   the number a viewer takes away and repeats.

2. **Every intermediate is bounded by, and monotone toward, the authored value.**
   `count()` is `v = to * EZ.quint(p)`, and `EZ.quint` is monotone increasing on
   `[0,1]` with no overshoot (the one easing that overshoots, `EZ.back`, is used
   for dot scale and never for a number). So every intermediate lies in
   `[0, to]`. The animation **cannot display a figure larger than the source
   supports** — it can only under-claim on the way. Display rounding can
   over-claim, by an amount nothing bounds, and it is the arithmetic that
   produces it, not a viewer's misreading.

3. **Every intermediate is a function of the authored value alone.** The frame at
   `t=5.2` is a lossy rendering *of 0.75*; it carries strictly less information
   than the plan, never different information. `0.8` is not derivable from any
   function of the timeline — it is a **replacement** for 0.75.

So: count-up animation is compatible with a verified-numbers guarantee, under a
*terminal-value* reading of the guarantee. That reading needs one companion rule
that does not exist yet, and its absence is a live defect:

> **The count must finish inside the hold.** If it does not, the mid-count value
> *is* the terminal value, and every argument above collapses — the number the
> viewer reads is stable, wrong, and under-stated.

This is not hypothetical. I hit it building the determinism fixture: a three-row
`kpis` beat with a **3.0s hold** has its last row start counting at 1.59s and
finish at 2.94s, while the scene's exit blur begins at 2.66s. The frame a viewer
reads shows **47%** for an authored 50%, and it fades out that way. That is why
those two fixtures sample at 0.95 of the hold rather than 0.72, and I want that
recorded as a workaround, not as a fix.

The rule is computable — `0.35 + (n-1)*0.62 + 1.35 + 0.34` for `kpis`,
`0.3 + n*0.34 + 1.3 + 0.5` for `jumpChart` — but the constants live in
`engine.js` and the `hold` lives in Python, and duplicating them is exactly the
D-036 drift pattern. **Recommendation:** the renderer computes a `minimum hold`
per beat (it owns both numbers) and `buildFromPlan` refuses a beat whose `hold`
is shorter, the same way it refuses an uncited chart. Spec §12 already gestures
at this ("if an entrance animation exceeds its scaled hold, the engine must
clamp") — clamping is the wrong verb; refusing is the R4 argument again, because
a truncated count reads as a figure the same way a clipped bar reads as the
maximum.

A second consequence, for Phase 5: **any verifier that reads a rendered frame
must sample past the count**, or it will check `47%` against a quote saying 50%
and report a failure that is not there — or check `$0.13` against nothing at all.

### 6.2 Other routes to a number the plan did not carry

Ranked by how much they worry me.

**`jumpChart.shown` is unconstrained, and it is the only thing a viewer reads.**
The digits on the chart come from `shown`, free HTML; `before`/`after` only drive
geometry. Nothing enforces any relationship between them. A beat with
`before: 1, after: 2, shown: "<s>12.0</s> → 99.9"` validates, renders, and shows
two figures the plan never carried, with bars that agree with neither. And this
**cannot be closed mechanically**, because the committed episode proves the
mismatch is sometimes correct: `before: 48.0` with `shown: "<s>48–49</s> → 65.3"`
is a published range rendered honestly. Recommendation: Phase 5 must verify
`shown`'s *text content* against the quote — it is what the viewer reads — and
treat `before`/`after` as geometry, and `shown` should probably be flagged for
manual attestation the way `custom` is.

**The bar geometry is itself a claim, and `scale` is unverifiable.** Drawing
0–70% scores on `scale: 100` shifts every bar without a single wrong digit.
Only the footnote guards it, and the footnote is free text that nothing checks.

**The `gain` segment is a computed delta.** `(to - from) / max` is rendered as a
length — "the improvement is this big" — derived, never authored, and Phase 5 has
no way to verify a length.

**`value` is never checked against `quote`.** Spec §7.2 says "every numeric
`value` must appear inside that `quote`". R1 only checks that a quote *exists*.
The actual containment check is unimplemented anywhere in the tree. That is
Phase 5's job by design, but it is worth saying plainly: today a `kpis` beat can
cite a quote that says nothing about its numbers, and everything passes.

### 6.3 `kpis` takes a 5-tuple positionally; the schema names fields

**The mapping was ambiguous, and I had to make a decision to remove the
ambiguity. This is a spec defect and it should be recorded.**

`engine.js:107` documents `item = [value, unit, suffix, decimals, prefix,
sizeClass]`. Spec §7.1 names `items[{value, unit, label, decimals}]`. The
resolved mapping:

| schema field | tuple slot | notes |
|---|---|---|
| `value` | `[0]` | numeric counts up; a string prints verbatim |
| `label` | `[1]` | the `.u` element — **which the engine's own comment calls "unit"** |
| `unit` | `[2]` | the **suffix** |
| `decimals` | `[3]` | absent = 0 = `Math.round` + thousands separators |
| `prefix` | `[4]` | **not in the spec; added by this task** |
| — | `[5]` | `sizeClass` — no schema field reaches it |

Two collisions:

1. **The names cross.** The engine's `[1]` is called `unit` in its own signature
   and holds what the schema calls `label` ("per 1M input tokens"). Anyone
   mapping by name rather than by meaning wires them backwards.
2. **`unit` alone cannot express the committed episode.** `2026-08-14.js` renders
   `$0.75` (prefix) and `50%` (suffix) from the same `kpis()` call, and the
   spec's own example writes `unit: "$"` meaning a prefix. One field, two
   positions, both live in one beat. I resolved it as **`unit` = suffix,
   `prefix` = new optional field.**

   I explicitly rejected the alternative — a closed table of "symbols that lead",
   which is what `cli.py::_kpi` had. A symbol table is a mutable global that
   *retroactively changes what past episodes render* the day someone adds `₹` to
   it, and that is the exact class of failure this phase exists to close.

   **Consequence to flag: the spec's own kpis example, transcribed literally,
   renders `0.75$`.** It should be rewritten as `prefix: "$"`. Nothing errors —
   it is a visibly wrong frame at review time, not a silent one, which is why I
   chose loud-and-visible over a hidden rule.

**Absent fields:** `label` is required and refused if absent. `unit`/`prefix`
absent is identical to `""` (checked by `typeof`, not truthiness — an empty
symbol and no symbol are the same glyphs, deliberately, unlike `value: 0` which
`typeof` also protects). `decimals` absent is `0`, discussed at length above.
`sizeClass` is unreachable, so every KPI renders at 132px; I checked the largest
value the series has ever shown — `1,048,576` measures 888px inside an 880px
column and does not clip — but there is no test for overflow and no schema field
to shrink a longer one, where the committed episode used `sm`.

### 6.4 Smaller notes

- **`*accent*` inherits `**bold**`'s weakness.** `"2 * 3 * 4"` becomes
  `"2 <em> 3 </em> 4"` — emphasis nobody wrote, on characters nobody chose. I
  implemented the marker exactly as the brief specified (mirroring `**`, same
  order, no extra rules) rather than adding markdown's non-whitespace-adjacency
  guard, because diverging behaviour between the two markers is its own surprise
  and the brief scoped this to one token. But single `*` is far more common in
  prose than `**`, so this is a live exposure and a `/\*(?=\S)…(?<=\S)\*/` guard
  is the obvious follow-up.
- **`prefix` widens the schema.** Unavoidable to render Step 5's `$0.75` at all,
  and R2's negative half explicitly licenses symbols. Flagged because it is a
  field the spec does not list.
- **Two languages hold the R2 rule.** That is duplication and therefore a drift
  risk. It is deliberate — the Python side is the only one with a good message
  and the Node side is the only one on the `--plan` path — but the two are held
  together only by both being tested, not by a shared definition. If a third
  consumer appears, this should become a single fixture both read.
- **The footnote's fade offset is a compromise.** `0.3 + rows.length * 0.34 +
  0.6` scales with the chart but is still guesswork against an unknown `hold`;
  it is the same problem §6.1's completion rule would solve properly.

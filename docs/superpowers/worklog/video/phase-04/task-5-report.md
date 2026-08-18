# Task 5 report — `shown` is data, not a script

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Follows:** `e3f9830`
**Commits:** `ef96c16` (tests) · `315bb87` (vocabulary) · `16d2b9d` (review) ·
`66182fc` (ride-alongs)

All four suites green at `66182fc`:

```
uv run pytest -q                       1312 passed, 1 warning in 12.73s
node determinism.test.mjs              deterministic
node network.test.mjs                  no request escapes the page
node render.mjs --day 2026-08-14 …     2026-08-14 · 119.99s · 3600 frames @ 30fps
node render.mjs --day 2026-08-12 …     2026-08-12 · 119.97s · 3599 frames @ 30fps
```

---

## 1. The vocabulary, and the evidence for every token in it

**`<s>`, `</s>`, and character references. Nothing else.**

Counted, not chosen — the D-080 method. Every `shown` cell that has ever been
committed lives in `engine/content/2026-08-14.js`:

```
['FrontierCode 1.1', 34.4, 43.6, '<s>34.4</s> &rarr; 43.6'],
['DeepSWE v1.1',     48.0, 65.3, '<s>48–49</s> &rarr; 65.3'],
['AutomationBench',  17.0, 30.4, '<s>17.0</s> &rarr; 30.4'],
['GDP.pdf',          22.0, 34.0, '<s>22.0</s> &rarr; 34.0']
```

| Token | Uses in a committed `shown` | Verdict |
|---|---|---|
| `<s>` / `</s>` | 4 | in — the strikethrough is what the field exists for |
| `&rarr;` | 4 | in, as the class "character reference" |
| `<b>`, `<em>` | **0** | **out, and flagged rather than added quietly** |
| `<span>`, `<i>`, `<br>`, `<svg>` | 0 in `shown` (they appear in hand-written episode JS) | out |

`<b>` and `<em>` are the tags `proseHTML` produces from `**` and `*`, so
allowing them in `shown` would not have widened the *project's* markup surface —
but no `shown` has ever used either, and the brief is explicit: a tag the
episodes do not use gets flagged, not added. **Flagging it here:** if a
storyboard ever needs bold inside a `shown` cell, the vocabulary should be
widened by counting again, in the open, rather than by someone hitting the
refusal and reaching for the constant.

Two properties do the actual work:

- **Attribute-free, enforced by matching the tags verbatim rather than parsing
  them.** `<s onclick="…">` is not the string `<s>`, so it never becomes an
  element. That is why the spelling of the handler — `onpointerenter`,
  `OnErRoR`, a tab before the name — is not a question this code has to get
  right. A blocklist would have been D-088's `window['Ma'+'th']` again.
- **Character references are allowed as a class, because the class is safe.** A
  reference decodes to a *character*, and the parser never re-reads that
  character as markup: `&lt;s&gt;` is three characters on the frame, not a tag.

Order, and it only works one way round (the same trick as `proseHTML`'s, pointed
the other way): **escape → restore tags → restore references.** References first
would turn an authored `&lt;s&gt;` into the element the author asked *not* to
have. That inversion is mutant S1 below, and it is caught.

Two gates, deliberately different in kind:

- **`script.py` refuses** (R3). The plan is the contract, and a human approves
  a script by reading it; a script that validates and then needs the renderer to
  defuse it has already been signed off.
- **`planbuild.js` escapes** (R1), because a plan reaches the page without
  Python at all — `render.mjs --plan` reads any JSON, and both node suites write
  their own — and because D-089 records that a `custom` beat can reassign
  `escapeHTML` from inside a `script.yaml`. The conversion therefore happens in
  `planJumpRows`, **eagerly, while the plan is walked**, before any authored
  `js` has run.

The refusal, in full (R3's negative half — beat, row and fragment):

```
script.yaml: beat 1 (jumpChart): `rows` [2] `shown` carries markup outside the
closed vocabulary: '<img src=x onerror="pwn()">'. `shown` is set as innerHTML,
and innerHTML grants attributes as well as tags — every inline event handler is
an attribute, so this field can run JavaScript and break `__seek(t)` purity. It
may contain `<s>` and `</s>`, written exactly and with no attributes, and
character references such as `&rarr;` — that is what the committed episodes use.
Write a literal `<` as `&lt;`
```

The negative half of the rule matters as much as the positive one: **a bare `&`
is an ampersand and a bare `>` is a greater-than.** Neither can open a tag, both
render as themselves, and refusing them would be a ban on punctuation dressed as
a security rule. `AT&T` and `43.6 > 34.4` are accepted and pinned.

---

## 2. The cross-page-load reproducibility test, before and after

`determinism.test.mjs` seeks twice inside one page, which is structurally blind
to this: `<img src=x onerror="…">` fires when the element is *inserted*, so both
seeks in one page see the same timestamp and agree with each other. The new
check loads the plan twice.

**Before** (`node determinism.test.mjs` at `ef96c16`, tests only):

```
  FAIL plan path t=35.85  fd3ab35cd6f7 9b1e7911ba4b
  FAIL plan path t=35.85  chrome text differs when reached via t=2.16
  FAIL beat 11 (jumpChart) missing ["onerror","Date.now()"]
  FAIL beat 11 (jumpChart) t=35.85 renders the same frame on a second page load
       load 1: THE BRIEF 2026-08-16 FrontierCode 1.1 34.4 → 43.6 GDP.pdf 1787016621268 …
       load 2: THE BRIEF 2026-08-16 FrontierCode 1.1 34.4 → 43.6 GDP.pdf 1787016621630 …
4 FAILURES
```

Better than the brief predicted: the same-page screenshot hash and the
chrome-text sweep failed too, because the injected node persists across the
detour seeks. The cross-load line is the one that names the defect.

**After** (`66182fc`):

```
  ok   plan path t=35.85  e4a30ed4a7e7 e4a30ed4a7e7
  ok   plan path t=35.85  chrome text stable from every predecessor
  ok   beat 11 (jumpChart) renders its text
  ok   beat 11 (jumpChart) t=35.85 renders the same frame on a second page load
deterministic
```

### Step 6 — pinned where it will be noticed

`network.test.mjs` had ten vectors and every one was a `custom` beat, which is
precisely why this surface was invisible to it. Two new cases, driven from a
plain `jumpChart`.

**Before:**

```
  FAIL shown (jumpChart)    nothing reached the sink — RECEIVED ["GET /shown?d=The%20Brief"]
  FAIL shown (jumpChart)    the handler is text, not code — window.__PWNED is set
       — 1 live <img> on the stage — the escaped handler is not on the frame
2 FAILURES
```

**After:**

```
  ok   shown (jumpChart)    nothing reached the sink (never even asked)
  ok   shown (jumpChart)    the handler is text, not code
no request escapes the page
```

> **Brief defect — flagged, per the ground rules.** The brief says "the network
> exfiltration half is ALREADY CLOSED by the CSP added in Task 4… Do not re-fix
> it." That is true of `fetch` and every other sub-resource channel, and it is
> **not true in general**: the line above is real bytes at a real loopback
> socket, from a plain `jumpChart` beat, at `ef96c16`. The vector is
> `location.href`, which D-090 already records as the one channel CSP cannot
> close — the leader's non-reproduction used `fetch`, which `connect-src`
> refuses. I did not re-fix the CSP; the closed vocabulary is what shuts this
> one, and the network assertion is kept because it is the property an operator
> cares about.

---

## 3. TDD evidence and the mutation score

Tests first, derived from the mutant table, committed failing at `ef96c16`:

```
51 failed, 1261 passed, 1 warning in 12.30s      # uv run pytest -q
4 FAILURES                                       # node determinism.test.mjs
2 FAILURES                                       # node network.test.mjs
```

Nothing "passed on arrival" except the deliberate regression guards — the four
real `shown` strings, `dumbbellGaps` (F4 is a coverage finding, not a live bug),
and the digit-free dumbbell card. Those exist to *fail under mutation*, and they
do; see S4 and S5.

### Mutation score: **18 / 18 killed.**

Nine from the brief's table, plus a nine-mutant sweep of my own. Each mutant was
applied to the real file and every suite run to completion with its exit code
read directly (not through a pipe — the gate review's own warning).

| # | Mutant | Caught by |
|---|---|---|
| M1 | `shown` back to raw innerHTML | pytest, determinism, network |
| M2 | attributes stripped from `<img>` but kept on `<s>` | pytest |
| M3 | blocklist of `on*` handlers instead of a whitelist | pytest |
| M4 | `<s>` dropped, `shown` rendered as text | pytest, determinism, network |
| M5 | named entities escaped, `&rarr;` shows literally | pytest, determinism |
| M6 | validation permits it, the renderer sanitises | pytest |
| M7 | refusal names neither beat nor row | pytest |
| M8 | `shown` still absent from `review` | pytest |
| M9 | the `NONDETERMINISTIC` lint over `shown` instead of validating | pytest |
| M9b | …**and** the renderer sanitiser removed (M9 as fully stated) | pytest, determinism, network |
| S1 | `shownHTML` restores references *before* tags | pytest |
| S2 | `shownHTML` allows any bare tag name | pytest |
| S3 | F7: the accent run may begin on whitespace again | pytest |
| S4 | F4: `dumbbellGaps`'s `!==` becomes `>` | pytest |
| S5 | F3: `planDumbbellRows` appends `v[0].toFixed(1)` to every note | pytest |
| S6 | F3: the conditional citation is dropped | pytest |
| S7 | F5: the `decimals` upper bound is removed | pytest |
| S8 | F6: the exponential refusal is removed | pytest |

**No survivors.** Two results worth reading rather than counting:

- **S4 and S5 are the gate review's own two survivors** (its M7 and M1). Both
  are now caught: `dumbbellGaps` is tested through `planbuild`'s own function in
  both directions, and the dumbbell card is asserted with `\d` over the whole
  rendered text on a digit-free fixture instead of six literal fixture glyphs.
  Asked the D-035 question of the old assertion: a builder that printed a
  *rounded* position passed it.
- **M9 is caught by pytest alone, and correctly so.** In the mutant as literally
  stated in the brief's table, the lint replaces the *validation* and the
  renderer still escapes, so no frame ever changes and the node suites are
  honestly green. M9b — the lint replacing *both* halves — is the version that
  reaches the page, and all three suites see it.

---

## 4. Decision on F3

**"A dumbbell renders no numbers at all" is now enforced, as a conditional
citation rather than as a digit ban.**

A dumbbell whose own words carry a digit — `caption`, `footnote`, `kicker`, a
row `label` or a row `note` — must carry `src` and `quote`. A digit-free one
needs neither, exactly as today.

Why not the two obvious options:

- **Striking the claim from the docstrings** leaves the hole the claim was
  covering. The `cited: False` exemption exists *because* the type renders no
  numbers; deleting the sentence would leave the exemption standing on nothing,
  and `+18 pts` on a card with no source anywhere in the pipeline.
- **Making `dumbbell` `cited: True`** (the gate review's own alternative) is a
  spec change wearing a bugfix: spec §7.1 names `kpis` and `jumpChart` as the
  cited pair, and the AMIE chart the type exists for carries no figure at all.
- **Refusing digits outright** buys the property by making the footnote worse.
  `n=159 cases, 2026` is a real footnote from a real study; a rule that bans it
  pushes an operator into writing something vaguer, which is a verification loss
  dressed as a verification win.

The rule that survives all three is the one spec §7.2 already states, read
literally: *"there is no path to rendering a number that isn't in a source."*
That sentence is about **numbers**, not about types. A dumbbell that prints one
is on the path it says does not exist. So the exemption is kept and made
conditional on the property that justifies it.

It reads `raw` rather than the validated payload, because `kicker` is a *shared*
field and reaches the stage through `planKicker` like everything else — a scan
of the type-specific payload alone would have left the same hole one field over.

The renderer half is a separate pin, not the same check twice: the rendered-text
assertion (S5) is what stops `planbuild.js` printing a position the script never
carried, which no schema rule can see.

---

## 5. Files changed

| File | What |
|---|---|
| `engine/planbuild.js` | `shownHTML` (new), `planJumpRows` routes `shown` through it, `proseHTML` accent flanking (F7), comment on `escapeHTML` |
| `src/agenticsocial/video/script.py` | `shown_markup` + `_shown_markup` + `SHOWN_TAGS`, wired into `jump_rows`; `MAX_DECIMALS`/`EXPONENTIAL_AT` in `kpi_items` (F5/F6); `dumbbell_prints_a_figure` + `cited_when` in `_beat` (F3) |
| `src/agenticsocial/video/cli.py` | `_jump_row`, so `review` shows `shown` (R4) |
| `tests/test_video_script.py` | validation: vocabulary, refusal message, negatives, F5, F6, F3 |
| `tests/test_video_planbuild.py` | renderer: `shownHTML` behaviour, eager sanitisation, F4, F3, F7 |
| `tests/test_video_review.py` | `shown` on the review line, and the label without it |
| `engine/determinism.test.mjs` | hostile-`shown` fixture + the cross-page-load check |
| `engine/network.test.mjs` | two non-`custom` vectors, sink and execution |

Commits: `ef96c16` → `315bb87` → `16d2b9d` → `66182fc`. Not squashed.
`git status --porcelain -- src tests engine` is clean.

`RENDERABLE == set(BEAT_TYPES)` still holds — `test_every_renderable_type_has_a_builder`
and `every builder has a fixture (10)` are both green. No new CSS, no new
dependency.

---

## 6. Issues and concerns

### Is any other field on any type reaching `innerHTML`?

Enumerated from the code, not from the brief. There are exactly **three**
`innerHTML` sinks in the engine:

```
engine.js:26   const P=(t)=>({html:t});          → the {html:…} option
engine.js:40   if(opts.html!=null)e.innerHTML=opts.html;   ← the only real sink
engine.js:236  stageScenes.innerHTML='';         ← clearing, no authored data
```

Every `{html: …}` reaching that sink from a **plan**, exhaustively:

| Site | Source | Gate |
|---|---|---|
| `planbuild.js:91` `prose()` | `statement.text`/`kicker`, `body.text`, `list.lead`, `quote.text`/`attribution`, `title.sub`, `signoff.text`, `dumbbell.caption`, every `kicker` | `proseHTML` — closed since D-078/D-080 |
| `planbuild.js:190` | `list.items[]` | `proseHTML` |
| `engine.js:139` `jval` | `jumpChart.rows[].shown` | `shownHTML` — closed by this task |
| `buildCustom` | `custom.js` | none — it is *code*, disclosed, attested (D-088) and CSP-bounded on the network (D-089) |

Nothing else. Every other authored value is set with `text:` (labels, footnotes,
legend names, KPI labels, the dumbbell axis) or as geometry (`left`, `width`).
`plan.design` reaches CSS custom properties rather than markup, and `series.py`
already refuses anything that is not a 3- or 6-digit hex colour.

So the enumeration finds **no second `shown`**. Worth saying plainly, though:
the reason `shown` was missed was not that the list was long, it was that the
field was *documented as an exemption* and nobody re-asked what an exemption
grants. `custom` is now the only unbounded markup path, and it is the one that
says so in its own name.

**Outside the boundary, by design:** `engine/content/*.js` — the two hand-written
episodes — call `jumpChart()` and `P()` directly with raw strings and never pass
through `planbuild.js`. They are author JavaScript in the same sense `custom` is,
so `--day 2026-08-14` is a regression test for the *engine*, not a demonstration
that the sanitiser ran. Anything script-driven goes through the plan path.

### What can `shown` still do that nothing prevents?

1. **State a figure the bar does not draw** — gate review F2, and untouched by
   this task. `shown: "<s>34.4</s> &rarr; 91.7"` renders beside dots positioned
   at 34.4 and 43.6. The markup is now safe and the *claim* is not, and Phase 5
   will verify `before`/`after` while the viewer reads `shown`. D-081 already
   carries this field to Phase 5 as an explicit exemption; it now needs to carry
   the stronger version: **`shown`'s digits should be checked against the row's
   own numbers**, since both are in the same mapping. The same channel exists
   more mildly on `kpis.unit`/`prefix`, which are deliberately free.
2. **Blank the cell.** `shown: ""` is legal and renders nothing, by design
   (`sub: ""`'s rule). An operator can hide a bar's value silently.
3. **Overflow the cell.** No length bound; a 400-character `shown` will lay out
   badly. Not a verification defect, and no episode has ever come close.
4. **Unbalanced tags.** `shown: "<s>34.4"` is accepted; Chromium closes the
   element at the end of `.jval`. It cannot escape the cell, because the parser
   closes open elements at the fragment boundary.

### Smaller notes

- **F7 is fixed for `*` only.** `**bold**` keeps its old shape — no committed
  scene has ever lost a character to it, and the failing cases the gate review
  found are all single-asterisk. The improper nesting it also noted
  (`***x***` → `<b><em>x</b></em>`) is gone as a side effect: the pass now emits
  `<b><em>x</em></b>*`, and the leftover `*` is an authored character preserved
  rather than deleted, which is the property F7 asked for.
- **F6's bound is absolute value.** `-1e21` is refused too; the notation is the
  problem, not the sign.
- **The review row is now longer.** A `jumpChart` with four rows and four
  `shown` cells will clip in the ~40-column text column. That is the right
  trade — a clipped `shown` is visible and an absent one is not — but if it
  becomes a real nuisance the fix is a second line per chart beat, not dropping
  the field again.

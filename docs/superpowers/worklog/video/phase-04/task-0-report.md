# Task 0 Report: Validate what the renderer interpolates

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine`
**Commits:** `f449e13` (tests, RED) · `c6d451e` (implementation, GREEN) · `c92a9d4` (test hardening after the sweep)
**Mutation score: 18/18.** Full suite: **1031 passed**.

---

## 1. What I changed

### `src/agenticsocial/video/series.py`

- `COLOUR_TOKENS` — the six `[design]` keys that become CSS custom properties,
  named to mirror `PLAN_TOKENS` in `planbuild.js` one for one. `type_family` and
  `type_scale` are deliberately absent (R1 negative).
- `HEX_COLOUR_RE = ^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$` — `#RGB` and `#RRGGBB`,
  either case. Anchored at both ends.
- `validate_design(design, where)` — raises `SeriesError` naming the token,
  showing the wanted form, and saying **why** a valid CSS colour is refused
  (palette drift) and **why it matters** (CSS discards the declaration silently).
- `check_warm_acts(acts, warm_acts, where)` — `warnings.warn(UserWarning)` naming
  every `warm_acts` id no `[[structure.acts]]` declares. Never raises (D-070).
- Both are called from `load_series` after the existing shape checks.

### `src/agenticsocial/video/plan.py`

- `act_labels(series)` — `act id -> label`, first declaration wins. Falls back to
  the id when the act declares no *string* `label`; an explicit `label = ""` is
  kept, because the spec's own cold-open row carries one.
- `build_plan` calls `validate_design` again and re-raises as `PlanError`, so the
  module keeps its single error type and every caller of `build_plan` inherits
  the gate — not just `load_series`. This is the last point before `plan.json`
  exists on disk and Node is started.
- Beats gain `"act_label"`, emitted immediately after `"act"`.

### `engine/planbuild.js`

- `scene(b.act_label || b.act || '', …)`. `b.act` remains as the fallback for a
  plan written before `act_label` existed. No lookup here: this file has no
  `series.toml`, and a second join is a second place to drift.

### Tests

`tests/test_video_series.py` +12 test functions (78 + 36 parametrised cases),
`tests/test_video_plan.py` +16, and three existing key-order tests updated for
`act_label`.

---

## 2. TDD evidence

Commit `f449e13` — tests only, run before any source change:

```
154 failed, 200 passed in 3.09s
```

Every failure is the absence of the feature, not a broken test:

```
  78  test_video_series.py::test_non_colour_design_token_is_rejected      DID NOT RAISE SeriesError
  54  test_video_plan.py::test_write_plan_refuses_a_non_colour_before_the_file_exists   DID NOT RAISE PlanError
   5  test_video_plan.py::test_build_plan_refuses_a_non_colour            DID NOT RAISE PlanError
   4  test_video_series.py::test_warm_acts_*                              DID NOT WARN
   1  test_video_series.py::test_the_error_says_why_a_valid_css_colour_is_refused
   9  test_video_plan.py  (act resolution)                                KeyError: 'act_label'
   1  test_video_plan.py::test_planbuild_consumes_the_resolved_label_and_does_no_lookup
   3  test_video_plan.py  (documented key order, updated for act_label)
```

Commit `c6d451e` — implementation:

```
1030 passed, 1 warning in 4.81s
```

The one warning is the pre-existing `test_warm_acts_is_loaded`, which sets
`warm_acts = ["03"]` with no acts declared. That is the new warning firing
correctly on a fixture that always had the mismatch.

Commit `c92a9d4` — test hardening found by the sweep (see §3):

```
1031 passed, 1 warning in 3.73s
```

**Deviation flagged:** the brief said two commits. There are three. The third
adds no production code — it replaces a test the mutation sweep proved too weak.
I chose an extra commit over amending, so the record shows the sweep did work.

---

## 3. Mutation score — 18/18

Each mutant was applied to a clean tree, the **whole** suite run, then
`git checkout -- src engine`. Output pasted from `/tmp/mutants-final.txt`.

### The brief's nine

| # | Mutant | Result | Suite |
|---|--------|--------|-------|
| M1 | colour check dropped (`for token in ()`) | **KILLED** | 1 failed, 327 passed |
| M2 | `accent = 5` accepted (`isinstance(value, int) or …`) | **KILLED** | 1 failed, 327 passed |
| M3 | falsy values accepted (`if not value or …`) | **KILLED** | 1 failed, 333 passed |
| M4 | named colours accepted (`^#?[0-9a-zA-Z]{3,7}$`) | **KILLED** | 1 failed, 369 passed |
| M5 | `type_family`/`type_scale` added to `COLOUR_TOKENS` | **KILLED** | 1 failed, 79 passed |
| M6 | validation moved to render time (`render.preview`, after `write_plan`) | **KILLED** | 1 failed, 327 passed |
| M7 | undeclared act id raises (`labels[beat.act]`) | **KILLED** | 1 failed, 292 passed |
| M8 | `warm_acts` mismatch raises `SeriesError` | **KILLED** | 1 failed, 778 passed |
| M9 | `warm_acts` mismatch silently ignored (early `return`) | **KILLED** | 1 failed, 976 passed |

M5 is worth noting: it dies at **79 passed** — collection barely gets going,
because `scaffold_series` itself stops loading. A colour rule applied to the
whole `[design]` table rejects the file agsoc writes.

### My own sweep

| # | Mutant | Result | Suite |
|---|--------|--------|-------|
| S1 | label falls back on falsiness (`label or act_id`) — kills `label = ""` | **KILLED** | 1 failed, 392 passed |
| S2 | non-string label passed straight through (`act.get("label", act_id)`) | **KILLED** | 1 failed, 393 passed |
| S3 | hex regex unanchored at the end (`…{6}` without `$`) | **KILLED** | 1 failed, 375 passed |
| S4 | `plan.json` written first, validated after | **KILLED** | 1 failed, 327 passed |
| S5 | `planbuild.js` prefers the raw id (`b.act \|\| b.act_label`) | **KILLED** | 1 failed, 395 passed |
| S6 | `warm_acts` checked only when some act is declared | **KILLED** | 1 failed, 978 passed |
| S7 | only `accent` colour-checked | **KILLED** | 1 failed, 327 passed |
| S8 | design validated at load only, not in `build_plan` | **KILLED** | 1 failed, 327 passed |
| S9 | `act_label` emitted but always equal to the id | **KILLED** | 1 failed, 387 passed |

**S5 survived the first sweep — 1030 passed, no failure.** My structural test
asserted `"act_label" in src`, which `scene(b.act || b.act_label || '')`
satisfies while doing exactly the wrong thing: printing the bare id and ignoring
the label, i.e. the defect the whole resolution exists to prevent. That is the
same class of weak assertion the brief warns about, applied to a string instead
of a falsy value. Fixed in `c92a9d4` with two tests: the source assertion now
pins the **precedence** (`b.act_label || b.act || ''`), and a `skipif(node)` test
evaluates `planbuild.js` in a `vm` with stub globals and asserts the act argument
every `scene()` call actually receives — declared label, undeclared fallback,
empty. A follow-up mutant S5b (`scene('')`, act dropped entirely) also dies.

---

## 4. Step 5 — the failure mode, in a real workspace

Real workspace at `/tmp/step5ws`, real `agsoc`, real `node` and `ffmpeg` on PATH.
`accent = 5` set in `series.toml` by hand.

```
$ agsoc video preview 2026-08-16 --series the-brief
/tmp/step5ws/series/the-brief/series.toml: [design] accent must be a hex colour — "#RRGGBB" or "#RGB", either case — got 5. Named colours, rgb() and other CSS forms are refused even though CSS accepts them: agsoc writes one format, and a second silently-accepted one is how a palette drifts. This value becomes a CSS custom property, and CSS discards an invalid declaration without an error — the render would come out wrong and say nothing.
exit=1

$ ls of the episode out/ dir:
total 8
drwxr-xr-x@ 6 aabdukarim  wheel  192 Aug 17 17:19 .
drwxr-xr-x@ 3 aabdukarim  wheel   96 Aug 17 17:19 ..
drwxr-xr-x@ 2 aabdukarim  wheel   64 Aug 17 17:19 out
drwxr-xr-x@ 2 aabdukarim  wheel   64 Aug 17 17:19 probe
-rw-------@ 1 aabdukarim  wheel  221 Aug 17 17:19 script.yaml
drwxr-xr-x@ 2 aabdukarim  wheel   64 Aug 17 17:19 sources

total 0
drwxr-xr-x@ 2 aabdukarim  wheel   64 Aug 17 17:19 .
drwxr-xr-x@ 2 aabdukarim  wheel   64 Aug 17 17:19 ..
```

`out/` is empty. No `plan-vertical.json`, no frames, no mp4 — the failure lands
before Playwright is ever started, and it names the field.

Control run, same episode, `accent` restored:

```
$ agsoc video preview 2026-08-16 --series the-brief   # same episode, accent restored
wrote /tmp/step5ws/series/the-brief/episodes/2026-08-16/out/vertical-1080x1920.mp4
exit=0

--- plan-vertical.json, act resolution and palette ---
19:    "accent": "#2E6BFF",
28:      "act": "01",
29:      "act_label": "01",
```

Then `[[structure.acts]] id = "01" label = "01 — The headline"` added and
`warm_acts = ["03"]` (which nothing declares):

```
$ agsoc video preview 2026-08-16 --series the-brief --probe
.../video/cli.py:444: UserWarning: /tmp/step5ws/series/the-brief/series.toml: [structure] warm_acts names '03', which no [[structure.acts]] declares. warm_acts entries are act ids (the `id` field), not labels. Loading anyway — those acts simply will not get the accent_warm treatment.
  s = load_series(ws, series)
wrote /tmp/step5ws/series/the-brief/episodes/2026-08-16/out/probe
exit=0

28:      "act": "01",
29:      "act_label": "01 — The headline",
```

The warning is visible on a real CLI run, and the mismatch does not stop the
render — R4 and its negative half, both in one invocation.

---

## 5. Files changed

| File | Commit |
|------|--------|
| `tests/test_video_series.py` | `f449e13` |
| `tests/test_video_plan.py` | `f449e13`, `c92a9d4` |
| `src/agenticsocial/video/series.py` | `c6d451e` |
| `src/agenticsocial/video/plan.py` | `c6d451e` |
| `engine/planbuild.js` | `c6d451e` |

`git status --porcelain -- src tests engine` is clean. No dependencies added, no
network, nothing under `docs/` staged, `PROGRESS.md` and `DECISIONS.md`
untouched.

---

## 6. Issues and concerns

### Do you agree beats should reference acts by `id`?

**Yes, and more strongly than the brief argues it.** I implemented it as
specified.

The brief's argument is that an id is stable under rewording. That is correct but
it undersells the case, because it frames the label join as *fragile*. It is
worse than fragile — it is **silently** fragile, and silence is the failure mode
this entire task exists to close. Rename `03 — Agents` to `03 — Agents & tools`
and a label join produces: every beat still renders, the act chip still shows a
string, `warm_acts` simply stops matching, and the warm treatment quietly
vanishes from a third of the episode. Nothing errors. That is `accent = 5`
wearing different clothes.

Two further reasons the brief does not make:

1. **Phase 5 inherits the join.** A claim is anchored to a beat. If claims are
   anchored through display text, then editing a label invalidates anchors that
   have nothing to do with the edit — and an operator will edit labels, because
   labels are the thing they see. Ids are the only key in this schema that an
   operator has no reason to touch.
2. **`validate_acts` already made the choice.** It requires `id` and refuses a
   non-string one; it does not require `label` at all, and its own error message
   reads *"has no `id` — a beat names its act by id"*. Choosing labels now would
   mean joining on the one field the validator treats as optional and free-form,
   against the field it treats as mandatory. The label option was already closed
   in Phase 3; this task is ratifying it, not deciding it.

The counter-argument — that the only committed episode uses labels — I do not
find load-bearing, and the brief's own reading of it is right. `2026-08-12.js`
passes `'03 — Agents'` because `content/*.js` is a standalone script with no
`series.toml` to join against; the string is simultaneously the key and the
display value because there was nothing else for it to be. That is not evidence
for labels, it is evidence that the question had not been asked yet.

**One caveat, which is why the fallback matters.** Under an id join, an operator
who writes `act: "01 — The headline"` in a script gets a chip reading
`01 — The headline` — visually identical to a correct render, but joining against
nothing, so `warm_acts` will never match it. The fallback makes this *look* fine.
That is the reason `check_warm_acts` names the offending value rather than just
counting mismatches: the message `warm_acts names '03 — Agents', which no
[[structure.acts]] declares … entries are act ids, not labels` is the only signal
an operator gets, so it has to say what the right key is. There is a test pinning
exactly that case (`test_warm_acts_joins_on_id_not_label`).

The residual gap: a **beat** naming an act by label gets no warning at all,
because R3's negative half requires it to render. If Phase 4 wants that visible,
`agsoc video review` is the place — it already prints a per-beat table and
already has a precedent for a non-fatal "cannot render yet" note. I did not add
it; it is outside this task and it belongs next to the other advisory output, not
in the loader.

### `type_family` / `type_scale`: wire them or drop them?

**Wire `type_scale`. Drop `type_family`.** They look like a pair and they are
not.

`type_scale` has three documented values (`default | compact | large`), no
current effect, and an obvious cheap implementation: one more `PLAN_TOKENS`-style
mapping to a root font-size multiplier, or a class on `<html>`. It is a real knob
an operator will want the first time a headline overflows — which is a per-series
property, exactly where it is declared. It is also *validatable*: three values,
enumerated, same shape as the `register` check. Wiring it is maybe fifteen lines
across `planbuild.js` and `scene.html`.

`type_family` is a different animal and I would delete it. The engine renders in
a headless browser with no network — an artifact-style CSP is not the constraint,
but `file://` plus no font loading is. A font stack naming a family the render
host does not have falls back silently, which means the knob's failure mode is
*the render looks subtly different on someone else's machine and nothing says
so*. That is the same defect class as `accent = 5`, and unlike `accent` it cannot
be closed by validation: whether `SF Pro Display` resolves is a property of the
machine, not of the string. Making it safe means embedding fonts as data URIs and
validating against the embedded set — a real feature, not a knob. Until someone
wants that feature, a documented setting that silently does nothing is worse than
no setting.

If you would rather not delete a documented knob: the cheap middle path is to
leave `type_family` in the template as a comment rather than a live key, so the
intent is recorded and nothing reads it. I did not do either — both are decisions
above this task's line.

### Anything else the renderer interpolates that nothing validates?

**Yes, and it is the biggest one left.** `engine/engine.js` line 26:

```js
const P=(t)=>({html:t});
```

and line 40:

```js
if(opts.html!=null)e.innerHTML=opts.html;
```

`planbuild.js` builds every statement with `P(b.kicker)` and `P(b.text)`. So a
beat's **`text` and `kicker` go through `innerHTML`, unescaped**, straight from
`script.yaml` via `plan.json`. `script.py` validates that `text` is a non-empty
string and nothing more.

The consequence is not a security one — the operator authors their own scripts —
it is the *silent wrong render* again, and it is easier to hit than `accent = 5`:

- `text: "Anthropic's <200k context window"` — the browser starts parsing a tag
  at `<200k` and swallows the rest of the sentence. The frame renders. It is
  short. Nothing errors.
- `rise()` (line 56) then splits `c.textContent` into words for the stagger
  animation, so any surviving markup is flattened into the animation in a way
  neither the author nor the determinism test can predict.
- `&` alone is fine; `&amp;`, `&lt;` and friends silently decode, so a source
  quoted verbatim from HTML renders differently from what the script says — and
  Phase 5 verifies claims against the *script*, not against the rendered frame.
  That is a real divergence between what is checked and what ships.

Two candidate fixes, both above this task's line: escape in `planbuild.js`
(`{text: …}` instead of `{html: …}`, losing intentional inline markup), or
validate in Python that `text`/`kicker` contain no `<` and no `&`-entity unless
the beat opts in. I would take the second — the engine's `html` path is used
deliberately elsewhere (`jumpChart`'s `shown` is documented as an HTML override
in `script.py`), so removing it wholesale would break a documented field.
**Recommend this becomes a Phase 4 task in its own right**; it is the same defect
class as the one this task closed, and it is currently wide open.

Smaller items, for the record:

- **`byline`** reaches `document.getElementById('by').textContent` — `textContent`,
  so it is safe. Same for `b.src` and the act chip. Those three are fine.
- **`custom` beat type** carries a `js` field that the engine is expected to
  *execute*. It is not in `RENDERABLE` so nothing runs it today, but the moment
  it is added, an unvalidated string becomes executed code inside the render
  context — and its failure mode includes breaking `window.__seek(t)` purity,
  which would make renders non-reproducible. Whatever phase widens `RENDERABLE`
  to include `custom` needs the determinism test green in the same commit, per
  `CLAUDE.md`.
- **`warm_acts` is not wired at all.** `planbuild.js` hardcodes `warmActs: []`,
  and `plan.json` does not carry the list. So today the setting is validated,
  warned about, and then ignored by the renderer. I did not wire it: the brief's
  Step 2 code block specifies `act`/`act_label` and nothing else, the plan's
  top-level key order is pinned by a test as documented, and adding a key is a
  format decision. Note that wiring it needs a *label* list, since `engine.js`
  line 191 compares `META.warmActs` against `S.act`, which is now the resolved
  label — so the plan should carry `warm_act_labels`, resolved by the same
  `act_labels()` map. That is a five-line follow-up and I would do it in the task
  that draws the warm treatment.

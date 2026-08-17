# Task 2 Report: The engine renders a plan

**Branch:** `feat/video-phase-1.5-vertical-slice` · **Base:** `3a603b0`

| # | SHA | Subject |
|---|-----|---------|
| 1 | `d1a91ed` | fix: refuse sub-frame beats, pin rounded times |
| 2 | `069d0db` | feat: render a resolved plan.json through the existing engine |
| 3 | `9c3defe` | test: pin __seek(t) purity, including independence from seek order |

**Headline:** both exit criteria pass and the pipeline produced a real 10.000s
1080x1920 MP4 from a `script.yaml`. **The determinism test committed in step 4 is
RED** — 1 of 3 day-path times. That is a real finding about `engine.js`, not a
broken test; root cause and a validated remedy are in section 5.

---

## 1. What I changed

**Step 0 — Python (`d1a91ed`)**

- `plan.py::build_plan`: added the sub-frame guard immediately after `hold` is
  computed, exactly as briefed. A beat whose *scaled* hold rounds to zero frames
  used to vanish from the render with no error.
- `tests/test_video_plan.py`: added the brief's two tests verbatim, rewrote the
  `test_total_sec_is_the_last_end_not_a_sum` docstring to the honest version, and
  **added one test the brief did not specify** because the brief's own version is
  vacuous — see section 4.

**Step 2 — engine (`069d0db`)**

- `.gitignore`: `engine/.plan.js`.
- `engine/planbuild.js`: new, verbatim from the brief. No timing arithmetic.
- `engine/scene.html`: loader blocks replaced; `?plan=1` vs `?day=<date>`.
- `engine/render.mjs`: `--plan` and `--out`; plan is `JSON.parse`d in Node and
  written as `.plan.js`; `no scenes` error names the right input. I also added
  three lines to the top-of-file usage comment documenting `--plan`/`--out`
  (documentation only, not specified by the brief).

**Step 4 — determinism (`9c3defe`)**

- `engine/determinism.test.mjs`: new, verbatim from the brief.

Nothing under `docs/` was staged. No dependency was added to `pyproject.toml` or
`engine/package.json` — `--plan` uses `node:fs/promises` and `JSON.parse`, the
determinism test uses `node:crypto` and the already-present `playwright`.

---

## 2. Evidence

### Python suite (354 passed)

```
tests/test_video_status.py .....................                          [ 94%]
tests/test_workspace.py ..................                                [ 98%]
tests/test_x_client.py .....                                              [100%]

============================= 354 passed in 0.93s ==============================
```

`tests/test_video_plan.py` alone: **35 passed** (was 32 at `3a603b0`; +3 from this task).

### Exit criterion — the existing `?day=` path still renders the committed episode

```
$ node render.mjs --day 2026-08-14 --probe
2026-08-14 · 119.99s · 3600 frames @ 30fps
25 probe frames → /Users/aabdukarim/Documents/Code/agenticsocial/engine/probe
exit=0
```

### The new `--plan` path

```
$ node render.mjs --plan /tmp/slice/workspace/series/the-brief/episodes/2026-08-14/out/plan-vertical.json --probe
2026-08-17 · 10.00s · 300 frames @ 30fps
3 probe frames → /Users/aabdukarim/Documents/Code/agenticsocial/engine/probe
exit=0
```

10.00s = 3.5 + 3.0 + 3.5 at pace 1.0, i.e. exactly what the `script.yaml` asked for.
`s00.png` shows the kicker "THE VERTICAL SLICE", act chip "01", headline "This came
out of a script.yaml.", source tag "agsoc" — every one of them sourced from YAML.

### End-to-end: a file a human can actually watch

```
$ node render.mjs --plan …/plan-vertical.json --out /tmp/t2/frames
2026-08-17 · 10.00s · 300 frames @ 30fps
  50%  (150/300)  eta 34s
done in 68s
$ ls /tmp/t2/frames | wc -l
     300
$ ffmpeg -framerate 30 -i /tmp/t2/frames/%05d.png -c:v libx264 -pix_fmt yuv420p -crf 18 /tmp/t2/slice.mp4
$ ffprobe … /tmp/t2/slice.mp4
width=1080
height=1920
nb_frames=300
duration=10.000000
size=2476562
```

`--out` works; 300 frames in, 300 frames out, duration exactly `total_sec`.

### Determinism test

```
$ node determinism.test.mjs --plan
  ok   day path t=0.5  81af9c119a6c 81af9c119a6c
  FAIL day path t=3.7  132b45f48b9d a9fc6922636a
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
  ok   plan path t=0.5  0c14296f6a30 0c14296f6a30
  ok   plan path t=3.7  dc60ecf6ab7a dc60ecf6ab7a
  ok   plan path t=8  bf5c8479e3be bf5c8479e3be
1 FAILURES
exit=1
```

**The plan path — everything this task built — is clean on all three times.** The
failure is in pre-existing `engine.js` behaviour on the hand-written episode. It
reproduces byte-for-byte across 5 consecutive runs (identical hashes every time),
so it is order-dependence, not flake.

---

## 3. Files changed

| File | Commit |
|---|---|
| `src/agenticsocial/video/plan.py` | 1 |
| `tests/test_video_plan.py` | 1 |
| `.gitignore` | 2 |
| `engine/planbuild.js` (new) | 2 |
| `engine/scene.html` | 2 |
| `engine/render.mjs` | 2 |
| `engine/determinism.test.mjs` (new) | 3 |

---

## 4. Vacuity audit

I wrote a mutant for each test rather than reasoning about it.

### `test_a_beat_shorter_than_one_frame_is_refused` — NOT vacuous ✅

Mutant: delete the `if round(hold * FPS) < 1:` block.

```
=== MUTANT 2 (no sub-frame guard) ===
E       Failed: DID NOT RAISE PlanError
FAILED tests/test_video_plan.py::test_a_beat_shorter_than_one_frame_is_refused
1 failed, 34 passed
```

Kills the mutant, and nothing else in the suite does.

### `test_resolved_times_are_rounded_not_raw_floats` — **VACUOUS AS BRIEFED** ❌

Mutant: `start, end = round(at, 3), round(at + hold, 3)` → `start, end = at, at + hold`.

```
=== MUTANT 1, brief's test only ===
34 passed in 0.33s
```

**The mutant survives the brief's own test.** The reason is arithmetic, not
oversight: `hold` is *itself* rounded before it is accumulated, so the running
total is a sum of already-clean 3-decimal values. With the `THREE` fixture at the
briefed `pace=1.1` those sums happen to be exactly representable:

```
hold=3.85 start=0.0  end=3.85   start_rounded_eq=True end_rounded_eq=True
hold=3.3  start=3.85 end=7.15   start_rounded_eq=True end_rounded_eq=True
hold=4.4  start=7.15 end=11.55  start_rounded_eq=True end_rounded_eq=True
```

There is no `11.550000000000002` at pace 1.1. The brief's prose states the intent
correctly ("Kills the mutant that drops round(start/end, 3)"); the code block does
not achieve it. **Per the ground rules I kept the code block verbatim and flagged
it**, then added the test that does the job:

`test_resolved_times_are_rounded_under_an_accumulating_pace` — same assertions,
`pace=1.15`, where `4.025 + 3.45 = 7.4750000000000005`:

```
=== MUTANT 1 (no round on start/end), with the sibling ===
E                +  where 7.475 = round(7.4750000000000005, 3)
FAILED tests/test_video_plan.py::test_resolved_times_are_rounded_under_an_accumulating_pace
 - AssertionError: ('end', 7.4750000000000005)
1 failed, 34 passed
```

Its docstring records that the sibling above it is vacuous and why, so nobody
later mistakes the pair for redundancy and deletes the wrong one.

### `determinism.test.mjs` — NOT vacuous ✅

Proven in section 5 below. It failed on real code the first time it was run.

---

## 5. Issues and concerns

### 5.1 Does the determinism test actually catch impurity? **Yes — proven twice.**

Baseline (unmodified `engine.js`): 1 of 3 day-path times fails.

**Mutant A — `Math.random()` in the background transform** (`engine.js:156`):

```js
`translate(${120+Math.sin(t*.21)*180+Math.random()*40}px,${180+Math.cos(t*.17)*220}px)`
```

```
  FAIL day path t=0.5  46549b8d64b5 43344c9c7f56
  FAIL day path t=3.7  8f37c13cff88 873447d8d033
  FAIL day path t=42.9  350c6bac2b58 869bc610ea79
3 FAILURES
exit=1
```

**Mutant B — `Date.now()` in the progress bar** (`engine.js:161`):

```js
progEl.style.transform=`scaleX(${t/TOTAL+(Date.now()%1000)/100000})`;
```

```
  FAIL day path t=0.5  78f9eca212ef b3b32542ecae
  FAIL day path t=3.7  2da9d6e1715c 16078dce4bc0
  FAIL day path t=42.9  ac68cb16a853 d2edc3bf13ac
3 FAILURES
exit=1
```

Both go from 1/3 to **3/3 FAIL**. Both reverted; `git diff --stat engine/engine.js`
is empty. The test is not theatre.

### 5.2 The pre-existing failure it found (t=3.7, day path)

This is the more interesting result, so here is the full investigation.

t=3.7 sits inside scene 0 (0 → 3.879) during its 0.34s blur-out tail. The test's
sequence is: arrive at 3.7 **from t=0.5** (same scene → `if(i!==CUR)` is false, the
scene DOM is *reused*), hash it; then detour 0 → 99 and arrive at 3.7 again (scene
index changed → the scene is *rebuilt from scratch*), hash it.

I dumped both PNGs and diffed them with ffmpeg:

- `YMAX=9` — max per-pixel delta 9/255.
- ~1.4% of pixels differ.
- The binarised diff mask shows the difference is confined **entirely to the
  blurred `<h1>` glyphs** ("Google shipped its main…"). Nothing else in the frame
  moves.

I then snapshotted every element under `#stage` with its computed `transform`,
`opacity`, `filter` and text for both arrivals. The only differences were:

```
DIFF  DIV#act  A: transform none  opacity 0  text ""
               B: transform matrix(1,0,0,1,0,0)  opacity 0  text "04 — In the wild"
DIFF  DIV#tag  A: opacity 0  text ""
               B: opacity 0  text "wired"
```

So there are **two separate defects**, and they must not be conflated:

**(a) A genuine state leak in `seek()`, currently invisible.** `engine.js:189-206`:

```js
if(S.act){ actEl.textContent=S.act; … } else { actEl.style.opacity='0'; }
if(S.tag){ tagEl.textContent=S.tag; … } else { tagEl.style.opacity='0'; }
```

When a scene has no act (or no source tag), the *previous* scene's text and
transform are left in the DOM and merely hidden with `opacity:0`. `__seek(t)` is
therefore not a pure function of `t` — the DOM it produces depends on where you
came from. It is pixel-invisible today only because the opacity is exactly `0`.
Any future change that fades the act chip rather than snapping it to 0, or any
tooling that reads `#act.textContent`, turns this into a visible wrong-label bug.
Cheap fix: clear `textContent` and reset the transform in both `else` branches.
**This is not what makes the test red** — I verified the PNGs are byte-identical
when only this differs.

**(b) The actual pixel difference: Chromium blur-layer rasterisation.** With DOM
and computed styles otherwise identical, a *reused* `.sc` element and a *freshly
built* one rasterise `filter: blur(3.58px)` slightly differently — the reused one
has a warm composited layer (`.sc { will-change: opacity,transform,filter }`).
This is below the engine's abstraction level; no amount of care in `seek()`
removes it while the scene DOM is conditionally reused.

**Validated remedy.** Forcing a rebuild on every seek makes the frame a function
of `t` by construction:

```js
if(i!==CUR){   →   if(true){
```

```
  ok   day path t=0.5  81af9c119a6c 81af9c119a6c
  ok   day path t=3.7  a9fc6922636a a9fc6922636a
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
deterministic
exit=0
```

Green, and the surviving hash is the fresh-build one. **I did not commit this** —
it is an unbriefed change to the engine's hot path with a real cost (the 120s
episode would rebuild the DOM and re-run `rise()`'s DOM walk 3600 times instead of
25, likely a large multiple on the 68s-per-300-frames render budget). That
trade-off is yours to make, not mine to slip into a task about plan rendering.

**Why I committed a red test rather than weakening it.** The alternatives were to
narrow the sampled times until it passed, or to make an unbriefed engine change.
Both would have produced exactly the class of test this project has already
shipped four of. The commit message says the test is red and points here.

**Practical severity:** low today. A full render walks `t` forward monotonically,
so every tail frame is rendered once from a consistent state; the committed
`.mp4`s are fine, and a 9/255 delta on blurred glyphs does not survive H.264
anyway. It matters for the *stated* promise — "any single frame re-creatable for
inspection months later" — which is currently true to within 9/255 on ~1.4% of
pixels, in exit tails only.

### 5.3 `.plan.js` races between concurrent renders

Real, and not yet worth fixing. `render.mjs` writes `engine/.plan.js` at a fixed
path and `scene.html` loads it by that fixed name, so two `--plan` renders in
parallel would have the second clobber the first's plan mid-flight — and the
failure mode is *silent*: you get a correct-looking video of the wrong episode.

It does not matter yet because the only caller is one operator running one render,
and Phase 1.5 has no scheduler or queue. It starts mattering the moment anything
renders two formats (`vertical` + `wide` are both already in `series.toml`) or two
episodes concurrently.

The right fix, cheapest first:
1. **Unique filename**, e.g. `.plan-<pid>.js` or a hash of the plan path, passed to
   the page as `?plan=<name>`. `scene.html` would need to whitelist the shape
   (`/^[\w.-]+$/`) rather than interpolate freely into `document.write`. Removes
   the race, keeps one directory.
2. **Per-render temp dir** containing a symlink/copy of `scene.html`, `engine.js`,
   `planbuild.js` — fully isolated but duplicates the stage.

I'd take (1) when the second concurrent caller appears, not before.

### 5.4 `type_family` and `type_scale` are dropped silently

`PLAN_TOKENS` maps six of the eight `[design]` keys. Confirmed from the generated
plan — `design` carries all eight:

```json
{ "surface": "#F2F5F8", "ink": "#0B1B2B", "ink_muted": "#5A6B7C",
  "accent": "#2E6BFF", "accent_alt": "#00C2D7", "accent_warm": "#FF6B4A",
  "type_family": "SF Pro Display, Helvetica Neue, system-ui",
  "type_scale": "default" }
```

`applyPlanDesign` iterates `PLAN_TOKENS`, not `design`, so the two type keys are
read from `series.toml`, validated, serialised into `plan.json`, shipped to the
page — and then ignored with no warning. The rendered frame uses `#stage`'s
hardcoded `font-family` and the hardcoded `h1 { font-size: 104px }`.

**Is dropping them silently acceptable? No.** The colours prove the mechanism
works, which is the trap: an operator who edits `accent` sees it take effect, and
therefore reasonably concludes `type_family` does too. Silence here is worse than
having no `[design]` block at all, because the block teaches a rule that two of
its keys break.

`type_family` is also the cheaper of the two and has no natural CSS-variable home
today — `#stage` sets `font-family` directly rather than through a custom property.
Three honest options:

1. **Wire `type_family`** (small): add `--type-family` to `:root`, have `#stage`
   use `font-family: var(--type-family, "SF Pro Display", …)`, add the mapping.
   Note the font must exist locally — Playwright over `file://` cannot fetch a
   webfont, so this is a *selection* knob among installed families, not a
   font-delivery feature, and it will silently fall back if the family is absent.
   That fallback is its own quiet failure and should be documented where the
   operator writes the value.
2. **Wire `type_scale`** (larger): it is an enum (`default | compact | large`), so
   it wants a multiplier applied to the type ramp — `h1`, `h2`, `.lede`, `.body`,
   `.kicker`, `.big-title`, `.kpi .n` are all hardcoded px today. That is a real
   typography pass, not a token map.
3. **Make the drop loud now, wire later** (cheapest, and my recommendation for
   this phase): in `applyPlanDesign`, `console.warn` any `design` key that is not
   in `PLAN_TOKENS`. `render.mjs` already collects page errors; a matching warn
   collector would surface it in the render log. The operator then learns from the
   tool instead of from a video that looks wrong.

Either way it should be written down: a `[design]` key that is parsed, validated
and then ignored is a promise the pipeline does not keep.

### 5.5 Smaller notes

- **`--plan` prints the wrong day in the header.** `console.log(`${day} · …`)` uses
  the `--day` default (today) even on the plan path — the probe output above reads
  `2026-08-17` for the `2026-08-14` episode. Cosmetic, but confusing in a log. The
  plan carries `episode`; the header should prefer it.
- **`--out` only affects the full-render branch**, per the brief's code block.
  `--probe` and `--at` still hardcode `engine/probe`. Worth knowing before anyone
  scripts parallel probes.
- **`--pace` would double-scale on the plan path.** `render.mjs` sets
  `qs.set('pace', …)` regardless of path, and `init()` lets the URL win over
  `META.pace`. Since `planbuild.js` deliberately sets `META.pace = 1` because holds
  are pre-scaled in Python, `--plan … --pace 1.2` would apply 1.2 *on top of* the
  pace already baked into the plan — quietly contradicting `plan.total_sec` and
  `total_frames`. Nothing does this today; it should probably be refused outright
  rather than fixed, since the plan is meant to be the resolved truth.
- **`series.byline` defaults to `""`**, so the bottom-right byline slot renders
  empty on the plan path. Correct behaviour for an unconfigured series, just noting
  it so the blank corner in `s00.png` isn't mistaken for a bug.

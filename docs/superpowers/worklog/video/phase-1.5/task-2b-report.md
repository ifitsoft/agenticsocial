# Task 2b Report: the determinism test is green, cheaply

**Branch:** `feat/video-phase-1.5-vertical-slice` · **Base:** `ccfe142` (docs) / `9c3defe` (code)

| # | SHA | Subject |
|---|-----|---------|
| 1 | `874f291` | fix: rasterise the scene from a fresh layer on every seek |
| 2 | `728af8b` | fix: clear the act chip and source tag, don't just hide them |

**Headline:** fix B landed on **rung 3** of the ladder — one `appendChild()` of the
existing scene node at the end of `seek()`. No DOM rebuild, no `rise()` re-walk,
**no measurable cost**: 300 frames in 68.96s against 68.98s at `9c3defe`. The
authorised fallback (rebuild every frame) was measured for comparison and buys
nothing — it produces byte-identical output for 69.42s. It is not in the tree.

Fix A is fixed on its own terms and the test grew a page-state check. The check
**as written in the brief was vacuous** and had to be strengthened before it bit;
that is section 3.

---

## 1. Fix B — the full ladder

Every rung was measured with `node determinism.test.mjs --plan`. Baseline for
comparison, at `9c3defe`:

```
  ok   day path t=0.5  81af9c119a6c 81af9c119a6c
  FAIL day path t=3.7  132b45f48b9d a9fc6922636a
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
  ok   plan path t=0.5  0c14296f6a30 0c14296f6a30
  ok   plan path t=3.7  dc60ecf6ab7a dc60ecf6ab7a
  ok   plan path t=8  bf5c8479e3be bf5c8479e3be
1 FAILURES
exit=1
```

| # | Attempt | Result |
|---|---------|--------|
| 1a | `.sc` `will-change: opacity,transform,filter` → `opacity,transform` | **FAIL** — every hash byte-identical to baseline |
| 1b | `.sc` `will-change` removed entirely | **FAIL** — t=3.7 still `132b…` vs `a9fc…` |
| 2 | `.wi` (the promoted glyph layers) `will-change: transform` removed | **FAIL** — t=3.7 `a5b6c2746371` vs `cccdc113bdf5` |
| 3a | Permanent render surface: `filter: 'blur(0px)'` instead of `'none'` | **FAIL** — byte-identical to baseline |
| 3b | **`stageScenes.appendChild(SC)` at the end of `seek()`** | **GREEN** ✅ adopted |
| 4 | `if(i!==CUR)` → `if(true)` (the authorised fallback) | green, but slower and more invasive — **not committed** |

Notes on the failures, because they are the informative part:

- **`transform: translateZ(0)` on `.sc` in CSS is inert here** and was not tried as
  its own rung. `seek()` writes an inline `transform` (`'none'`, or
  `translateY(…)`) on every call, and an inline style beats a stylesheet rule.
  Rungs 1b and 3a cover the same ground from the other direction.
- **1a and 3a produced byte-identical hashes to the baseline** — Chromium ignored
  both. `blur(0px)` in particular is collapsed to no filter, so it does not force
  a permanent render surface the way the idea assumed.
- **1b and 2 did change rendering** (other frames' hashes moved: t=42.9 went
  `7494…` → `0bf84d059c95` under 1b; t=0.5 went `81af…` → `d791cafce59d` under 2).
  They were effective changes that simply did not touch the defect. This rules out
  layer promotion via `will-change` as the cause.

### What the diagnostic actually showed

Before rung 3 I stopped guessing and reproduced the difference in isolation. The
result reframes the diagnosis in task 2:

```
from   0.5 -> 3.7  a9fc6922636a
from     3 -> 3.7  a9fc6922636a
from   3.6 -> 3.7  a9fc6922636a
from  3.69 -> 3.7  a9fc6922636a
from  42.9 -> 3.7  a9fc6922636a
from    99 -> 3.7  a9fc6922636a
```

Arriving at t=3.7 from **any** predecessor gives the same frame — *provided no
screenshot was taken in between*. Insert a screenshot at the previous t and the
hash becomes `132b45f48b9d`. So the trigger is not "reused vs freshly-built DOM";
it is **"a layer that has already been painted vs one that has not"**. It is a
raster-cache reuse, one level below anything a style declaration can reach — which
is exactly why rungs 1, 2 and 3a all missed, and why the only thing that worked
was throwing the layer away.

`appendChild()` of a node that is already a child is defined as a remove followed
by an insert, so it discards the paint layer while leaving the DOM subtree, the
inline styles and the registered `ANIMS` closures untouched. The scene is still
built once per scene.

Adopted result, stable across 4 consecutive runs:

```
  ok   day path t=0.5  81af9c119a6c 81af9c119a6c
  ok   day path t=3.7  a9fc6922636a a9fc6922636a
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
  ok   plan path t=0.5  0c14296f6a30 0c14296f6a30
  ok   plan path t=3.7  dc60ecf6ab7a dc60ecf6ab7a
  ok   plan path t=8  bf5c8479e3be bf5c8479e3be
deterministic
exit=0
```

The surviving hash at t=3.7 is `a9fc6922636a` — the fresh-layer frame, the same
one rung 4 converges on.

---

## 2. Cost

`node render.mjs --day 2026-08-14 --probe`, three runs each, plus a 300-frame
monotonic seek+screenshot benchmark on the same episode (probe only renders 25
frames, so it is dominated by browser startup and cannot see per-frame cost).

| Variant | probe wall time (3 runs) | 300 frames |
|---|---|---|
| `9c3defe` baseline | 6.898s / 6.825s / 6.801s | 68.98s — **229.94 ms/frame** |
| **rung 3 (adopted)** | 6.887s / 6.757s / 6.778s | 68.96s — **229.86 ms/frame** |
| rung 4 (rejected) | 6.594s / 6.839s / 6.779s | 69.42s — 231.39 ms/frame |

Rung 3 is free within noise. Both `--probe` paths still work and print the same
header:

```
2026-08-14 · 119.99s · 3600 frames @ 30fps
25 probe frames → /Users/aabdukarim/Documents/Code/agenticsocial/engine/probe
```

The `--plan` path is exercised by the `--plan` half of the determinism test above.
The Python suite is untouched and still **354 passed**.

---

## 3. Fix A — the real impurity

`seek()` left the previous scene's act label and source tag in the DOM whenever
the current scene had none, hidden with `opacity: 0`. Both `else` branches now
clear the text (and, for `#act`, the class and the transform) rather than hiding
it. The element ids in the brief were `act` / `src`; the real ones are **`#act`
and `#tag`** (`scene.html:186,188`).

**Before** (`9c3defe` `engine.js`):

```
direct   ["",""]
via 42.9 ["01 — The headline","github.blog"]
IMPURE
```

**After:**

```
direct   ["",""]
via 42.9 ["",""]
PURE
```

A full `#stage.outerHTML` diff between the two arrivals at t=3.7 confirms this was
the *only* DOM difference, and that it is now gone (`IDENTICAL_DOM true`):

```
<   <div id="act" style="opacity: 0;"></div>
>   <div id="act" style="opacity: 0; transform: translateY(0px);" class="">04 — In the wild</div>
<   <div id="tag" style="opacity: 0;"></div>
>   <div id="tag" style="opacity: 0;">wired</div>
```

Fix A is pixel-neutral, as task 2 predicted: all six hashes before and after are
identical, and all 25 probe frames are byte-identical.

### The brief's page-state check was vacuous — I had to strengthen it

The snippet in the brief compares `chrome(t)` reached via one detour to
`chrome(t)` reached via `__seek(99)`. Applied literally, with fix A reverted and
fix B in place, it reports:

```
  ok   day path t=0.5  chrome text stable
  ok   day path t=3.7  chrome text stable
  ...
deterministic
exit=0
```

It passes on the broken engine. The reason: both arms of that comparison arrive at
t from a scene that *also* has no act of its own, so both inherit the same stale
label and agree. A single detour cannot detect the leak.

The committed version sweeps predecessors instead — it reaches `t` from `0`, `99`
and every other sampled time, and requires all of them to produce the same
`#stage.innerText`. Some scene in the episode carries an act chip and some does
not, so one of those arrivals always disagrees when the leak is present. With fix
A reverted and this version in place:

```
  ok   day path t=0.5  81af9c119a6c 81af9c119a6c
  FAIL day path t=0.5  chrome text differs when reached via t=42.9
  ok   day path t=3.7  a9fc6922636a a9fc6922636a
  FAIL day path t=3.7  chrome text differs when reached via t=42.9
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
  ok   day path t=42.9  chrome text stable from every predecessor
  ...
2 FAILURES
exit=1
```

Note the pixel lines stay `ok` throughout — this is precisely the class of bug a
screenshot cannot see. Restoring fix A returns it to green.

---

## 4. Proof the test still catches impurity

Mutant: `Math.random()*40` added to the `#b1` background translate
(`engine.js:156`), the same injection task 2 used.

```
  FAIL day path t=0.5  75f71459221a 7b84e92f97f4
  ok   day path t=0.5  chrome text stable from every predecessor
  FAIL day path t=3.7  1427263f01c0 c7adfc0e3a9f
  ok   day path t=3.7  chrome text stable from every predecessor
  FAIL day path t=42.9  812712484ceb 834b7af17140
  ok   day path t=42.9  chrome text stable from every predecessor
  FAIL plan path t=0.5  bf2d0635c2b4 64a7e339f02f
  ok   plan path t=0.5  chrome text stable from every predecessor
  FAIL plan path t=3.7  01db3bcc0f66 e6eb40df9a9d
  ok   plan path t=3.7  chrome text stable from every predecessor
  FAIL plan path t=8  8d6fa6b50bc3 665374260090
  ok   plan path t=8  chrome text stable from every predecessor
6 FAILURES
exit=1
```

**6 of 6 pixel checks fail.** The chrome checks correctly stay green — the mutant
moves a background blob, not any text, and a check that fired on it would be
reporting the wrong thing.

Reverted; `git diff --stat engine/engine.js` prints nothing, `git status
--porcelain` shows no modified files, and both the `--plan` and the plain runs are
green:

```
$ node determinism.test.mjs 2>&1 | tail -10
  ok   day path t=0.5  81af9c119a6c 81af9c119a6c
  ok   day path t=0.5  chrome text stable from every predecessor
  ok   day path t=3.7  a9fc6922636a a9fc6922636a
  ok   day path t=3.7  chrome text stable from every predecessor
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
  ok   day path t=42.9  chrome text stable from every predecessor
deterministic
exit=0
```

The chrome check's own mutant is in section 3: reverting fix A turns it red while
the pixel checks stay green. Neither half is theatre.

---

## 5. Visual comparison

**Probe frames: 25 of 25 byte-identical**, `9c3defe` vs `874f291` vs `728af8b`.
Probe samples 72% into each scene, which is outside the exit tails, so this shows
the design is untouched but says nothing about the tails.

For the tails I rendered frames 100–116 (t=3.333–3.867) **monotonically from t=0**,
exactly as a real full render does, on `9c3defe` and on the fix:

| frame | t | max delta | mean delta | pixels >64/255 |
|---|---|---|---|---|
| 00100 | 3.333 | 83/255 | 0.113 | 0.047% |
| 00104 | 3.467 | 83/255 | 0.113 | — |
| 00106 | 3.533 | 83/255 | 0.113 | — |
| 00107 | 3.567 | 139/255 | 0.202 | 0.135% |
| 00110 | 3.667 | 20/255 | 0.153 | 0.000% |
| 00113 | 3.767 | 3/255 | 0.024 | — |
| 00115 | 3.833 | 1/255 | 0.002 | — |
| 00116 | 3.867 | 0 | 0 | byte-identical |

**Two things here are worth stating plainly.**

1. The change is **not confined to the tails**. The tail starts at t=3.539 (frame
   107), yet frames 100–106 differ too. Re-inserting the node re-rasterises the
   headline from a fresh layer every frame, and fresh-layer glyph antialiasing
   differs slightly from warm-layer glyph antialiasing. The task-2 diagnosis
   ("confined to blurred `<h1>` glyphs in exit tails") described the *symptom the
   test sampled*, not the full extent.
2. **None of it is visible.** The amplified difference mask is a pure outline of
   every letter — edge antialiasing, nothing else, no geometry and no colour
   shift. Side-by-side crops of the headline at frame 100 are indistinguishable.
   Mean delta across the frame is 0.11–0.20 out of 255.

I also checked the obvious risk — that re-rastering text every frame introduces
shimmer on static type. It does not. Frame-to-frame delta within the headline
crop, frames 100 vs 101:

```
tail-base   YAVG=0.185245 YMAX=6
tail-fixB   YAVG=0.185257 YMAX=6
```

Identical, and that residual comes from the background grid drifting 0.13px per
frame. The type is as stable as it was.

---

## 6. Issues and concerns

### 6.1 Did I end at option 4, and is 3,600 rebuilds acceptable?

No — I stopped at rung 3, so the question is moot in practice. But the measurement
is worth recording because it contradicts the premise of the whole task: **rung 4
would have been acceptable on wall-time grounds.** 300 frames took 69.42s with a
rebuild every frame against 68.98s without — **0.6%**. The 144× increase in DOM
work is invisible because rendering is dominated by `page.screenshot()` and PNG
encoding, at ~230 ms/frame; `S.build()` plus `rise()`'s walk is somewhere in the
sub-millisecond noise beneath that.

So the real objection to rung 4 was never speed. It is that `if(true)` deletes the
scene-caching mechanism and leaves a dead `CUR` variable and a misleading
structure behind — a maintenance cost, not a runtime one. Rung 3 keeps the
mechanism, states its reason in a comment, and is a single line. That is why I
prefer it, and the human's speed concern turns out not to have been the deciding
factor either way.

If a future episode ever does make per-frame build cost matter (a scene building
thousands of nodes), rung 3 remains the cheaper of the two.

### 6.2 Is this pinned to a Chromium version? Yes.

The behaviour is Chromium's raster-cache reuse, which is an implementation detail
with no specification behind it. Measured on:

```
chromium 151.0.7922.34      (playwright ^1.62.1)
```

Two distinct exposures, and they should be handled differently:

- **The fix is not version-fragile.** Discarding the layer is correct against any
  rasteriser; it removes the dependency rather than compensating for it. A
  Chromium upgrade cannot make `appendChild()` stop discarding a paint layer.
- **The hashes are version-fragile** — but the test never asserts a hash value. It
  asserts that two hashes taken in the same browser session agree. A Chromium
  upgrade changes both sides identically, so the test survives. What an upgrade
  *can* do is surface a *new* order-dependence the current version does not have,
  which is the test doing its job.

My recommendation: **pin `playwright` to an exact version** in
`engine/package.json` (it is `^1.62.1` today) and treat the determinism test as a
required gate when that pin is bumped. The pin matters less for this test than for
render reproducibility in general — the same `^` range would let two operators
produce visibly different MP4s from the same `script.yaml`, which is a larger
problem than this one and is not addressed by anything in this task.

Worth writing into the README's render workflow rather than leaving as folklore:
**the committed frames are only reproducible against the pinned Chromium.** The
engine's invariant is "any frame is re-creatable"; that promise quietly carries
"…with this browser".

### 6.3 The chrome check does not exercise the plan path

`chrome text stable` passes on all three plan-path times, but the vacuity test in
section 3 shows it only *bites* on the day path — the plan episode's scenes all
carry an act, so nothing is ever inherited. That is a property of the fixture, not
a hole in the check, and it will start covering the plan path the moment a
`script.yaml` has a beat with no act. Worth knowing before someone reads six green
lines as six independent proofs.

### 6.4 The pixel check and the chrome check now diverge in what they can see

Section 4 shows this explicitly: the `Math.random()` mutant fails 6 pixel checks
and 0 chrome checks; the fix-A mutant fails 2 chrome checks and 0 pixel checks.
That is the intended design — they are complementary, not redundant — but it means
neither can be dropped as "covered by the other" later.

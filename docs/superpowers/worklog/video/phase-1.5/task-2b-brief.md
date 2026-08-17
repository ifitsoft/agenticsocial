# Task 2b Brief: Make the determinism test green — cheaply if possible

**Phase:** 1.5 · **Branch:** `feat/video-phase-1.5-vertical-slice` · **Follows:** `9c3defe`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

`engine/determinism.test.mjs` is committed **red**: `day path t=3.7` fails. The
Task 2 implementer diagnosed it carefully and refused to hide it, which was
right. Two distinct defects sit behind that one red line and **they must not be
conflated**:

**A. A genuine `__seek(t)` impurity.** When a scene has no `act`/`src`, the
previous scene's text and transform stay in the DOM, hidden only by
`opacity: 0`. So `__seek(t)` is not purely a function of `t`. Verified invisible
today (byte-identical PNGs) but it becomes a visible wrong-label bug the moment
the act chip fades rather than snapping to 0. `CLAUDE.md` calls this invariant
load-bearing.

**B. Chromium rasterises `filter: blur()` differently on a reused `.sc` layer
versus a freshly built one.** Max delta 9/255 across ~1.4% of pixels, confined to
blurred `<h1>` glyphs in exit tails. **This is what makes the test red.**

## The decision, and the constraint

The human chose **determinism over render speed**. The validated remedy —
`if (i !== CUR)` → `if (true)`, rebuilding the scene every frame — turns the test
green but trades 25 DOM rebuilds for 3,600 on the 120s episode.

**Do not reach for that first.** The cause is a layer-promotion inconsistency,
not something that inherently needs a rebuild. If forcing consistent compositing
makes reused and fresh layers rasterise identically, we get determinism at
near-zero cost.

**Your job is to find the cheapest fix that makes the test genuinely green, and
to prove which one you used and why.** A 144× increase in DOM work is acceptable
if it is genuinely required. It is not acceptable if a CSS hint would have done.

## Ground rules

- Commit only when the test is green. Separate commits for A and B.
- **Pipe command output to a file and paste from it.**
- Do not add dependencies. Never stage anything under `docs/`.
- `node render.mjs --day 2026-08-14 --probe` must still work, and the rendered
  output must still look right — compare probe frames before and after.
- Report observed numbers. Never adjust the test to make a fix look better.

---

- [ ] **Step 1: Fix B — try these in order, stop at the first that works**

Measure each against `node determinism.test.mjs`. Record the result of every
attempt, including the ones that fail — the failures are as informative as the
fix.

1. **Force consistent layer promotion.** Add `will-change: transform, opacity`
   (or `transform: translateZ(0)`) to `.sc` in `scene.html`, so a reused layer
   and a fresh one are composited the same way.
2. **Promote only what is blurred.** If (1) is too broad, try it on the blurred
   element rather than the scene container.
3. **Force a repaint without a rebuild.** Toggling a property that invalidates
   the raster cache on seek may be enough.
4. **Rebuild every frame** — `if (i !== CUR)` → `if (true)`. The fallback the
   human authorised. Only if 1–3 fail.

For whichever works, measure the cost honestly:

```bash
cd engine
time node render.mjs --day 2026-08-14 --probe
```

Compare against the same command on `9c3defe`. Report both wall times.

- [ ] **Step 2: Fix A — the real impurity**

Independent of B, and worth fixing on its own terms: `seek()` leaves the previous
scene's act/source text in the DOM when the current scene has none. Make the
chrome a pure function of the current scene — an empty `act` or `tag` must clear
the element's text, not merely hide it.

Verify with a page-level assertion rather than a screenshot, since the bug is
currently invisible in pixels:

```bash
node -e "
import('playwright').then(async ({chromium}) => {
  const b = await chromium.launch();
  const p = await b.newPage({viewport:{width:1080,height:1920}});
  await p.goto('file://$PWD/scene.html?day=2026-08-14');
  const read = async t => { await p.evaluate(tt => window.__seek(tt), t);
    return p.evaluate(() => [document.getElementById('act')?.textContent,
                            document.getElementById('src')?.textContent]); };
  const direct = await read(3.7);
  await read(42.9); const viaOther = await read(3.7);
  console.log('direct  ', JSON.stringify(direct));
  console.log('via 42.9', JSON.stringify(viaOther));
  console.log(JSON.stringify(direct) === JSON.stringify(viaOther) ? 'PURE' : 'IMPURE');
  await b.close();
});"
```

Check the actual element ids in `scene.html` before running this — the ids above
are a guess and may be wrong.

Then extend `determinism.test.mjs` so a page-state check runs alongside the
pixel check, because pixels alone cannot see this class of bug:

```js
  // chrome must be a pure function of t, even where pixels agree
  const chrome = async (t) => {
    await page.evaluate((tt) => window.__seek(tt), t);
    return page.evaluate(() => document.getElementById('stage').innerText);
  };
  const c1 = await chrome(t);
  await page.evaluate(() => window.__seek(99));
  const c2 = await chrome(t);
  if (c1 !== c2) { failures++; console.log(`  FAIL ${c.label} t=${t} chrome text differs`); }
```

Adjust the selector to whatever actually holds the act/source chrome.

- [ ] **Step 3: Green, and prove it still catches impurity**

```bash
node determinism.test.mjs 2>&1 | tail -10          # must print "deterministic", exit 0
node determinism.test.mjs --plan 2>&1 | tail -10   # plan path too, if a plan exists
```

Then re-run the theatre check: inject `Math.random()` into `engine.js`, confirm
the test fails, revert, confirm `git diff --stat engine/engine.js` is empty. A
green determinism test that no longer detects non-determinism is worse than a red
one.

- [ ] **Step 4: Confirm the render still looks right**

Probe frames before and after must be visually equivalent — the fix must not
change the design. Render `--day 2026-08-14 --probe` on both `9c3defe` and your
HEAD, and compare a few frames pixel-for-pixel. Some difference is expected for
fix B (that is the point); report the magnitude, and say plainly whether any of
it is visible rather than sub-perceptual.

---

## Your report

`docs/superpowers/worklog/video/phase-1.5/task-2b-report.md`:

1. **Which fix you used for B, and the full ladder** — every attempt, its result,
   and why you stopped where you did.
2. **Cost** — wall time before and after, both paths.
3. **Fix A** — the impurity, the page-state proof before and after.
4. **Proof the test still catches impurity.**
5. **Visual comparison** — magnitude of pixel change and whether it is visible.
6. **Issues or concerns**, including:
   - If you ended up at option 4, say plainly whether 3,600 rebuilds is
     acceptable for a 120s episode or whether this needs a different approach
     entirely.
   - Is the blur difference a Chromium version dependency? If so, the test is
     pinned to whatever Playwright ships and will break on upgrade — how should
     that be handled?

# Phase 1.5 — Vertical slice: `script.yaml` → MP4

Renders a hand-written script to a watchable vertical video, proving the whole
pipeline connects — and settling the Python↔Node format that Phase 4 inherits
against a real render rather than in the abstract.

**Plan:** `docs/superpowers/plans/2026-08-17-phase-1.5-vertical-slice.md`
**Roadmap:** `docs/superpowers/plans/2026-08-16-video-mvp-roadmap.md` §5

---

## What you can do

```bash
agsoc series new the-brief --name "The Brief"
agsoc video new 2026-08-14 --series the-brief
# write beats into episodes/2026-08-14/script.yaml
agsoc video preview 2026-08-14 --series the-brief
```

Verified end to end: `duration=10.000000`, 1080×1920, and the MP4's `comment`
metadata carries `script_sha256`, byte-identical to `shasum -a 256` of the
`script.yaml` that produced it. No frames survive; ~2.5 GB of intermediate PNGs
are always cleaned up.

## The architecture this settles

**Python parses YAML and emits `plan.json`; Node consumes it.** `scene.html`
loads scripts via `document.write` because `fetch` and ES modules are both
CORS-blocked over `file://` — so the plan arrives as a classic script, and Node
gains no YAML dependency.

**The plan is fully resolved.** Scaled holds, absolute `start`/`end`, integer
frame numbers. `render.mjs` performs **no timing arithmetic** — it looks values
up. That is what keeps `window.__seek(t)` policeable, and it removed a real class
of bug: the pace formula previously lived on both sides of the boundary and could
silently disagree with the plan's own total.

`total_sec` derives from the last beat's `end` rather than a sum, so the schema
stays neutral about overlap — adding tracks later (TTS spans beats by nature)
will not change the timing contract.

## Why `preview` and not `render`

Spec §11 names this `agsoc video render`, and **Phase 8 will ship that.** This
does not.

`render` is gated: spec §10 makes `RENDERING` reachable only from `APPROVED`.
There is no `approve` command until Phase 7, so a `render` today would either be
blocked for every episode or bypass the gate it is named after. Shipping a
gate-bypassing command under the name the gated one will later take is how a gate
quietly stops meaning anything.

`preview` never touches status — two tests pin that — and says so in its help.

## Determinism

`engine/determinism.test.mjs` is new and green. It seeks **away and back** rather
than twice at the same `t`, so it catches state accumulating across calls, and it
checks **page state alongside pixels**, because the impurity it found was
invisible in pixels.

Two defects fixed:

- **A real `__seek(t)` impurity** — the act chip and source tag were hidden at
  `opacity: 0` rather than cleared, so the previous scene's label survived. Byte-
  identical output today; a visible wrong-label bug the moment that chip fades.
- **Chromium rasterising `filter: blur()` differently** on a reused layer versus
  a fresh one. Fixed by re-inserting the scene node to discard its paint layer —
  229.86 ms/frame vs 229.94 baseline, free within noise.

The test was proved to actually detect impurity: injecting `Math.random()` fails
6 of 6 checks. A determinism test that cannot detect non-determinism would have
been this project's fifth test that could not fail.

**Playwright is now pinned exactly.** Chromium's blur rasterisation is
version-dependent, so a caret range let two operators produce different MP4s from
one `script.yaml` — and the determinism test structurally cannot catch that,
since it compares two hashes within one session.

## Known gaps, recorded not hidden

- **`engine/` is not in the wheel.** `pyproject.toml` packages only
  `src/agenticsocial`, so a pip-installed `agsoc video preview` fails with a
  clean but useless error. No `parents[N]` fixes this — the engine has to ship
  inside the package and be anchored with `importlib.resources`. **Required
  before Phase 8** (D-056).
- Two error tests pass only because the toolchain check raises first; remove it
  and they launch real Chromium (D-057). Phase 2 cleanup.
- One beat type (`statement`), vertical only. That is the slice, by design.

## Test plan

`uv run pytest` — **372 passed in ~1.0s**, offline, no new Python dependencies.
No test invokes Playwright or ffmpeg.

`cd engine && node determinism.test.mjs` — green, exit 0.

`node render.mjs --day 2026-08-14 --probe` — the existing hand-written path still
renders the committed episode unchanged.

## Note on review

No whole-branch adversarial review ran on this phase — merging at the author's
direction. Each task carried its own mutation audit (17 mutants on Task 3 alone,
22 of 23 mutant/test pairs killed), and every finding above came from those.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

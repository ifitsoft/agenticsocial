# The Brief — daily 9:16 news video

A vertical animated-typography brief, one episode per day. 1080×1920, 30fps,
H.264 / yuv420p, silent, ~120s.

Two episodes were made here by hand before the pipeline existed, and they are
kept as regression fixtures rather than as a workflow:

| Episode | Fixture | Runtime |
|---|---|---|
| Wed 12 Aug 2026 | `content/2026-08-12.js` | 120s |
| Fri 14 Aug 2026 | `content/2026-08-14.js` | 120s |

Bylined "Ali Abdukarim" — persistently at bottom-right, and full-size on the title
and sign-off cards. The date appears in the filename, in the top-right chip on
every frame, on the title card, and in the file's embedded metadata.

## Layout

```
scene.html            the stage — styles + markup only, never changes per day
engine.js             the render engine — seek(t), animation primitives, charts
planbuild.js          builds a scene from a plan.json beat
content/YYYY-MM-DD.js the two hand-written fixture episodes
coverage.json         the ledger of what has been covered
coverage.mjs          query the ledger
render.mjs            Playwright frame renderer — takes a plan.json
determinism.test.mjs  __seek(t) is pure, and every builder draws its text
network.test.mjs      the render page cannot reach the network
coverage.test.mjs     the ledger check cannot be talked past
```

`window.__seek(t)` positions **every** element purely as a function of `t` — no CSS
keyframes, no `Date.now()`, no randomness. So the render is reproducible and any
single frame can be re-created for inspection.

## The supported path

**`agsoc video render <episode>` is how a video gets made.** It is the only path
that passes the approval gate, and nothing in this directory is a shortcut around
it. The pipeline is:

```
agsoc video new / ingest      the episode and its verification corpus
   → the storyboard skill     writes script.yaml, stops at in_review
agsoc video check             two-pass verification → claims.json
agsoc video approve --by …    THE GATE — a named human
agsoc video render            approved + undrifted + fresh ledger → out/*.mp4
agsoc video probe   [--at T]  one frame per beat, or one at T — no encode
```

`render` resolves every time in the episode into a `plan.json` (Python does the
arithmetic, D-007) and hands that to `render.mjs`, which renders frames and knows
nothing about pacing, dates or content files. Then ffmpeg encodes, the frames are
deleted, and the MP4 lands in the episode's `out/`.

`render.mjs` refuses to run without `--plan`. Run it by hand only when you are
debugging the renderer itself:

```sh
node render.mjs --plan <plan.json> --out <dir>            # every frame
node render.mjs --plan <plan.json> --out <dir> --probe    # one frame per beat
node render.mjs --plan <plan.json> --out <dir> --at 34    # one frame at t=34s
```

### What retired, and what did not

`render.mjs --day <date>` used to render `content/<date>.js` straight to
frames. **That path is gone.** It was a second route from an episode to an MP4,
and it passed neither `check` nor `approve` — nothing it produced had been
verified against a corpus or signed by a human.

**`content/2026-08-12.js` and `content/2026-08-14.js` stay**, and stay exercised.
They are the engine's only realistic regression fixtures — two complete episodes,
every builder, both chart forms — and `determinism.test.mjs` drives them through
`scene.html?day=2026-08-14`, which is also how you scrub the slider in a browser
while working on layout. They are fixtures now, not a way to publish.

## Coverage

The series must never re-tell a story as if it were new. `coverage.json` is the
ledger, and it is checked before an episode is written, not after:

```sh
node coverage.mjs check gemini "supply chain" copilot
```

A hit means: drop the story, or cover it as an explicit **update** that says what
changed — same `id`, plus `"update": true` and `"updateOf": "<earlier date>"`.
Record one entry per story after a render.

## Working on the engine

Open `scene.html?day=2026-08-14` in a browser and drag the slider: no render, no
Playwright, instant feedback on layout and copy. `scene.html?plan=1` does the same
for the plan written by the last `agsoc video render` or `probe`.

Three tests, all offline, all run by hand:

```sh
node determinism.test.mjs   # __seek(t) is pure — the load-bearing invariant
node network.test.mjs       # the page cannot reach the network
node coverage.test.mjs      # the ledger check cannot be talked past
```

`determinism.test.mjs` ships green in the same commit as any engine change. That
is not a style rule: a frame that depends on anything but `t` cannot be
re-created for inspection, and inspection is the only thing that covers the
pixels (D-116).

## Reproducibility

Playwright is pinned to an exact version, not a caret range. Chromium's
rasterisation of `filter: blur()` is version-dependent, so a different Chromium
produces different bytes from the same `script.yaml`. Frames are only
reproducible against the pinned build.

Before bumping Playwright, run `node determinism.test.mjs` on the new version
and re-render a committed episode to see what moved.

## Pacing

`pace` in the episode's `meta({...})` is the read-speed knob. It multiplies every
beat's duration without touching entrance animations — text arrives at the same
speed, it just holds longer before cutting. Pick it so the total lands near 120s:

```
pace ≈ 120 / (sum of the episode's scene durations)
```

`agsoc video review` writes the derived `pace` into the episode, and it is one of
the values the approval covers (D-116). `scene.html?pace=1.05` scrubs it in a
browser without rendering anything.

## Adding music or voiceover

Silent by design — most vertical video is watched muted. To mux a track in:

```sh
ffmpeg -y -i the-brief-2026-08-14.mp4 -i track.m4a \
  -c:v copy -c:a aac -b:a 192k -shortest the-brief-2026-08-14-audio.mp4
```

## Voice

Reported-brief register: third person, present tense, one fact per beat. No first
person, no hype adjectives. Analysis beats are labelled as such ("Why it matters")
rather than voiced as personal opinion.

## Charts

Two forms, both driven only by what the source actually publishes.

- **`jumpChart`** — before→after on a common scale, for a metric with real numbers
  (e.g. Gemini 3.6 → 3.7 benchmarks). Both values direct-labelled; the footnote
  names the scale and any reported range.
- **Dumbbell** (12 Aug, AMIE) — two entities on one track. It has **no numeric
  axis**, because that source publishes ratings rather than scores; it encodes
  direction only and says so. Where two values coincide it draws a single two-tone
  marker rather than stacking two dots, which would hide one series entirely.

Never invent a number the source does not give. If there is no number, say what the
source did report and chart direction only — or do not chart it.

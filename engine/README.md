# The Brief — daily 9:16 news video

A vertical animated-typography brief, one episode per day. 1080×1920, 30fps,
H.264 / yuv420p, silent, ~120s.

| Episode | File | Runtime |
|---|---|---|
| Wed 12 Aug 2026 | `the-brief-2026-08-12.mp4` | 120s |
| Fri 14 Aug 2026 | `the-brief-2026-08-14.mp4` | 120s |

Bylined "Ali Abdukarim" — persistently at bottom-right, and full-size on the title
and sign-off cards. The date appears in the filename, in the top-right chip on
every frame, on the title card, and in the file's embedded metadata.

## Layout

```
scene.html            the stage — styles + markup only, never changes per day
engine.js             the render engine — seek(t), animation primitives, charts
content/YYYY-MM-DD.js one file per episode: meta() + one scene() per beat
coverage.json         the ledger of what has been covered
coverage.mjs          query the ledger
render.mjs            Playwright frame renderer
```

`window.__seek(t)` positions **every** element purely as a function of `t` — no CSS
keyframes, no `Date.now()`, no randomness. So the render is reproducible and any
single frame can be re-created for inspection.

## Making a new day

**1. Check for repeats first.** This is the point of the ledger — the series should
never re-tell a story as if it were new.

```sh
node coverage.mjs check gemini "supply chain" copilot
```

A hit means: drop it, or cover it as an explicit **update** that says what changed.
When you do run an update, add the entry with the *same* `id`, plus
`"update": true` and `"updateOf": "<earlier date>"`.

**2. Write `content/<YYYY-MM-DD>.js`.** Copy the previous day as a skeleton. It sets
`meta({...})` then calls `scene(act, duration, sourceTag, build)` once per beat.
Available inside `build`: `E` (create element), `rise` (masked word rise), `fade`,
`draw` (rule), `count`, `kpis` (headline figures), `jumpChart` (before→after), and
`an` for anything custom.

**3. Preview without rendering.** Open `scene.html?day=2026-08-14` and drag the
slider. This is the fast way to check copy and layout.

**4. Probe, then render.**

```sh
node render.mjs --day 2026-08-14 --probe     # one frame per scene into probe/
node render.mjs --day 2026-08-14             # all frames into frames/
ffmpeg -y -framerate 30 -i frames/%05d.png \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart \
  -metadata title="The Brief — 14 August 2026" \
  -metadata artist="Ali Abdukarim" \
  -metadata date="2026-08-14" \
  -metadata comment="Stories: <story ids from coverage.json>" \
  the-brief-2026-08-14.mp4
rm -rf frames                                 # ~2.5 GB of intermediate PNGs
```

`node render.mjs --day 2026-08-14 --at 42.9` renders a single frame for inspection.

**5. Record it in `coverage.json`** — one entry per story, with a stable `id`.

## Pacing

`pace` in the episode's `meta({...})` is the read-speed knob. It multiplies every
beat's duration without touching entrance animations — text arrives at the same
speed, it just holds longer before cutting. Pick it so the total lands near 120s:

```
pace ≈ 120 / (sum of the episode's scene durations)
```

`render.mjs --pace 1.05` overrides it for one render, and `scene.html?pace=1.05`
scrubs it in a browser without rendering anything.

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

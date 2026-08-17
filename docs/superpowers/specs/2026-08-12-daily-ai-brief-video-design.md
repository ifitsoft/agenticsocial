# Daily AI Brief — 9:16 animated-text video

Date: 2026-08-12

## Goal

A vertical (1080×1920) silent video that reads today's AI digest in the author's
own voice, as animated typography. Modern, light, cool. ~80 seconds.

## Pipeline

Deterministic frame rendering — no screen capture.

1. `scene.html` — self-contained page, 1080×1920. Exposes `window.__seek(t)`
   which positions every element purely as a function of `t`. No CSS keyframes,
   no `Date.now()`, no randomness. System fonts only, so nothing loads from the
   network.
2. `render.mjs` — Playwright/Chromium drives `__seek(i/30)` and screenshots each
   frame to `frames/%05d.png`.
3. `ffmpeg` — frames → `daily-ai-brief.mp4`, H.264, yuv420p, CRF 18, no audio.

Because seek is a pure function of time, any single frame can be re-rendered for
inspection and the output is reproducible.

## Visual system

- Surface `#F2F5F8`, cool vignette, 1px parallax grid.
- Ink `#0B1B2B`, secondary ink `#5A6B7C`.
- Accents: blue `#2E6BFF`, cyan `#00C2D7`; warm `#FF6B4A` **reserved** for the
  security story only.
- Type: SF Pro Display / Helvetica Neue. Statements 96–108px/700 at -0.035em
  tracking; body 40px/400; kickers 26px uppercase at 0.28em.
- Four motion primitives, reused throughout: masked word rise, blur-to-sharp
  fade, left-to-right rule draw, eased count-up.
- Persistent chrome across all cuts (progress bar, brand mark, act label, source
  tag) so the acts read as one piece.
- Safe area: content confined to y 430–1560 to clear platform UI.

## Structure

| Act | Beats | Content |
|---|---|---|
| Cold open | 2 | Hook + title card |
| 01 The headline | 6 | Anthropic watermarking: text watermark motif, C2PA stamp, take, caveat |
| 02 Models | 6 | Grok 4.6; Google AMIE + comparison chart; Dyna-2 / MiniMax H3 |
| 03 Agents | 5 | Novo Nordisk × AWS; LiteLLM blast-radius counters; attack-surface line |
| 04 The human one | 5 | ChatTJB; sign-off |

## Charts

Both derived only from the source text. No invented figures.

**AMIE comparison** — dumbbell. Five rows: history-taking, diagnostic accuracy,
management appropriateness, communication quality (all "on par"), then eliciting
physical signs ("rated higher"). Two series, direct-labelled, blue/cyan
(validated: CVD ΔE 22.7 deutan, normal-vision ΔE 25.0; cyan's sub-3:1 contrast is
relieved by visible direct labels). The dots animate apart → together; the absent
gap *is* the finding. No numeric axis — the source publishes no scores — only a
direction caption and a footnote saying so.

**LiteLLM blast radius** — a KPI stack, not a chart: 2,500 organisations /
434,000 CI/CD pipelines / 40 minutes. Eased count-up in the warm accent.

## Voice

First person, present tense, one idea per beat. No hype adjectives.

## Deliverables

`workspace/brief-video/` — `daily-ai-brief.mp4`, `scene.html` (scrub in a browser
to preview), `render.mjs`, `README.md` with re-render and audio-mux commands.

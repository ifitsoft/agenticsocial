# Task 1 Brief: The text beats, and closing the innerHTML divergence

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Follows:** `c92a9d4`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Step 0 comes first: the rendered bytes must be the verified bytes

Leader-verified in a real browser:

```
script: "The model is <thinking> about it"
screen: "The model is  about it"          <- the word is GONE
script: "AT&amp;T raised prices"      →  "AT&T raised prices"
```

`planbuild.js` builds statements with `P(b.text)`, and `P=(t)=>({html:t})` sets
`innerHTML`. **This is a verification defect, not a rendering one.** Phase 5
checks the script's bytes; the frame shows something else, so a claim can pass
verification while the video displays different text. Nothing errors.

**The mechanism is already there.** `E` supports `opts.text`
(`e.textContent=opts.text`), and `rise()` walks the DOM rather than reading
`innerHTML`, so word-rise works unchanged on a text-set element — its own comment
says *"Walks the DOM so inline tags survive."*

### The markup vocabulary is closed, not absent

Spec §7.1 gives `body` the field **`text` (bold via `**`)**. That is the whole
vocabulary for the declarative path: **`**bold**` and nothing else.** The
committed episodes write `<b>` and `<br>` directly, but those are hand-written JS
where the author is the engine's author. A `script.yaml` is written by an agent
against a source, so its markup surface must be closed.

Rule, in this order, and the order is the point:

1. **Escape** the raw text (`&` `<` `>` — `&` first or you double-escape).
2. **Then** convert `**…**` → `<b>…</b>`.
3. Set `innerHTML` with the result.

Doing it the other way round escapes the `<b>` you just made. **`jumpChart.shown`
is exempt** — it is a documented HTML override and `2026-08-14.js` relies on
`<s>34.4</s> &rarr; 43.6`.

Which fields are prose (escaped, `**` allowed): `text`, `kicker`, `lead`,
`label`, `caption`, `footnote`, `attribution`, `sub`.

## What this task renders

`body`, `list`, `quote`, `title`, `signoff`. **`quote` is spec-only** — neither
committed episode has one (D-069), so its design is your judgement. Say in the
report which decisions were yours.

Build each from what the episodes already do (`E` + `rise`/`fade`/`draw` and the
existing CSS classes — `kicker`, `body`, `lede`, `stack`, `item`, `big-title`,
`byline`, `rule`, `foot`). **Do not invent CSS**; if a type needs a class that
does not exist, that is a finding worth reporting before you add one.

## Rules, each with its negative half

- **R1** Prose renders as text. **Negative:** `**bold**` still bolds, and
  `jumpChart.shown` still renders as HTML.
- **R2** What the script says is what the frame shows, for every prose field.
  **Negative:** entities do not decode — `&amp;` renders as the five characters.
- **R3** Every type in this task renders visible content. **Negative:** a beat
  with only optional fields still renders (a bare `title` is legal).
- **R4** No timing arithmetic in the engine. **Negative:** `META.pace` stays 1.
- **R5** `__seek(t)` stays pure. **Negative:** including after the new builders.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | prose back to `P()` / `innerHTML` | R1, R2 |
| M2 | escape skipped | R2 |
| M3 | `**bold**` converted **before** escaping | R1 negative |
| M4 | `&` not escaped (only `<` and `>`) | R2 |
| M5 | `jumpChart.shown` escaped too | R1 negative |
| M6 | `list` renders `lead` but drops `items` | R3 |
| M7 | `list` drops `lead` when items exist | R3 |
| M8 | `quote` drops `attribution` | R3 |
| M9 | a bare `title` renders nothing | R3 negative |
| M10 | a builder returns without appending | R3 |
| M11 | `META.pace` set from the plan | R4 |

## Verification, not golden pixels

**Do not add pixel golden files.** They are Chromium-version-bound and this
project already pins Playwright for that reason; a hash file would add
maintenance without adding a guarantee the determinism test does not already
give.

Instead extend `engine/determinism.test.mjs`: a plan exercising **every type this
task renders**, asserting per beat that the stage's `innerText` contains the
beat's text — which catches "the builder silently did nothing", the failure a
pixel hash would report as a mystery. Keep the existing pixel and page-state
checks. It must stay green.

## Ground rules

- **Three commits:** Step 0 (the text fix), the builders, the determinism
  extension. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 23 defects across five phases.
- No new dependencies. No network in the Python suite.
- `node render.mjs --day 2026-08-14 --probe` must still render the committed
  episode. **It is the regression test for the hand-written path.**
- **Report the mutation score.**

---

- [ ] **Step 0** — the escape/bold helper in `planbuild.js`, prose fields moved
      off `P()`, `RENDERABLE` unchanged. Commit.
- [ ] **Step 1** — tests, derived from the mutant table. Commit.
- [ ] **Step 2** — the five builders; `RENDERABLE` widens. Commit.
- [ ] **Step 3** — determinism extension. Commit.
- [ ] **Step 4** — kill all eleven mutants, plus your own sweep.
- [ ] **Step 5** — a real render: a script with all six now-renderable types,
      `agsoc video preview`, and **paste a probe frame's page text** so I can see
      what actually reached the screen.

---

## Your report

`docs/superpowers/worklog/video/phase-04/task-1-report.md`:

1. **What I implemented**, and for `quote`, which design decisions were mine.
2. **TDD evidence** and the **mutation score**.
3. **All eleven mutants** plus your own sweep.
4. **Step 5's output**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - Did any type need CSS that does not exist? Adding a class is a bigger
     decision than it looks — `scene.html` is the shared visual system.
   - `**bold**` is the whole vocabulary. Is that enough for a real brief, or will
     the storyboard skill immediately want `<br>` or italics? Argue from the two
     committed episodes, which are the only real scripts that exist.
   - Anything still reaching `innerHTML` that a script can influence.

---
name: storyboard
description: Use when the user wants to turn a news brief into an agenticsocial video episode — reads series.toml, voice.md and the ingested corpus, writes script.yaml beat by beat with a source and a verbatim quote on every claim, and stops at in_review for human approval.
---

# Storyboard: brief + corpus → `script.yaml`

You are writing one episode of a vertical news video series. The script is data:
you own content, order, emphasis and attribution. The engine owns layout,
timing curves and chrome — you never touch it.

Everything you write gets checked against the episode's corpus by
`agsoc video check`. Your goal is **a first `check` that passes with no
overrides.** That is achievable on the first try; the rules below are the ones
that make it so.

## Hard rules

- **NEVER run `agsoc video approve`, `agsoc video render`, `agsoc video preview`,
  or `agsoc post`.** Your job ends at `status: in_review`. A human approves and
  renders.
- **Write every figure exactly as the source writes it.** The number in the
  script is the number that gets verified and the number that reaches the
  screen. If the source says `0.756`, the script says `0.756`.
- **Every beat except `title` and `signoff` carries a non-empty `src` and a
  non-empty `quote`.** This is not "every beat that makes a claim" — a plain
  prose `statement` with no figures in it still needs both, or `check` reports
  `no_source` and refuses the episode.
- **Copy a `quote`; never retype it.** Read the bytes out of
  `sources/<src>.txt` and paste them. A quote must be verbatim present in that
  file.
- **Say only what a source says.** If your source gives a direction rather than
  a magnitude, say the direction — with `dumbbell`, which renders no digits at
  all — rather than reaching for a number to make the card feel finished.
- **Check coverage before you write** (below). The series must never re-tell a
  story as if it were new.

## Workflow

### 0. Where you run things

Run every `agsoc` command **from the repo root**, and in this repo the CLI is
run through uv:

```
uv run agsoc <command>
```

Anywhere else you get `Failed to spawn: agsoc`. The workspace it reads is
`$AGSOC_WORKSPACE`, defaulting to `./workspace` — so all the paths below are
relative to the repo root too.

### 1. Read the series before you read the news

- `workspace/voice.md` — the operator's voice. Follow it.
- `workspace/series/<slug>/series.toml` — you need three things from it:
  - `[runtime] target_sec` and `tolerance_sec` (the episode's length budget),
  - `[[structure.acts]]` blocks, if any: each has an `id`, and a beat names its
    act by that **`id`**, not by its label. If the file declares no acts (they
    are commented out by default), use `"01"`, `"02"`, `"03"`, `"04"` — the act
    string is free text and the chip prints whatever you write.
  - `[series] register` — `reported` means third person, no "I".

Find the slug with `uv run agsoc series list` if you were not told it. Every command
below takes `--series <slug>`; without it the CLI looks for a series called
`default` and fails.

### 2. Check coverage

```
node engine/coverage.mjs check <keyword> [keyword...]
```

One keyword per candidate story — a product name, a company, a slug. It prints
either `NOT COVERED. Safe to run as new.` or the prior episodes that told it.
**A hit is not a veto:** it means drop that story, or cover it as an explicit
update and say in the beat what has changed since.

(This ledger lives in `engine/coverage.json` today and moves behind an
`agsoc coverage check` command later. The rule does not move: check before you
write.)

### 3. Make the corpus

The corpus is the set of `.txt` files everything you write is checked against.
Nothing verifies against the raw brief you were handed — it verifies against
these files.

```
uv run agsoc video new <episode-id> --series <slug>
uv run agsoc video ingest <episode-id> --series <slug> --paste <path/to/brief.md>
```

`--paste <file>` ingests a file you already have. Use `--research "<query>"` to
fetch and format search results instead, or `--from-source <id>` to pull in an
existing `agsoc` source. Pass exactly one.

Episode ids are lowercase letters, digits, dots and hyphens — use the date,
`2026-08-17`.

**If `agsoc video new` says the episode already exists, do not try again.** You
are re-drafting an episode that is already there: run
`uv run agsoc video list --series <slug>`, confirm its status is `draft` or
`in_review`, skip `ingest` if `sources/` is already populated, and go to step 4.

Then learn the source keys:

```
ls workspace/series/<slug>/episodes/<episode-id>/sources/
```

Every `<key>.txt` is one source. **`src:` is that key without the `.txt`** — a
pasted brief lands as `_pasted`, so `src: _pasted`. `sources/_manifest.json`
gives each key's title and URL.

### 4. Plan the episode: acts, beats, holds, pace

Pick the 4–6 strongest stories out of the corpus, group them into the acts, and
sketch the beats before writing YAML.

**One beat, one contiguous quote.** A `quote` has to be a single unbroken span
of one source file — you cannot stitch two bullets or two paragraphs into one
citation. So a card that wants to say two things a source says in two places is
two beats. Decide this while you are outlining, not after `check` refuses it.

**The arithmetic, which you can do before writing a word:**

- Aim for **22–26 beats**: two cold-open beats, then 4–6 beats per act.
- Give each beat a `hold` between **2.6 and 5.6 seconds** — short for a single
  sentence, long for a card the viewer has to read (a list, a chart, KPIs).
- Sum your holds. **Aim for a total between 80 and 95 seconds.**
- Then set `pace` in the metadata so the runtime lands on target:

  ```
  pace = target_sec / sum(holds)      rounded to 3 decimals
  ```

  `pace` is a single global multiplier: runtime is `sum(holds) × pace`. Holds
  summing to 86.6s against a 120s target give `pace: 1.386`, and `review` then
  reports a runtime of 120.0s — dead centre of a ±8s tolerance, with nothing
  hand-tuned. Both shipped episodes of *The Brief* are built exactly this way
  (24 beats / 83.6s / `pace 1.435`, and 25 beats / 92.8s / `pace 1.293`).

  Keeping the hold total in the 80–95s band is what keeps `pace` near 1.3. Far
  fewer beats gives you a large `pace`, and the card animations do not stretch
  with it — you get a still frame held for eight seconds. Add beats instead.

- **Give every `kpis`, `jumpChart` and `dumbbell` beat a hold of at least 4.0
  seconds.** Their numbers count up and their bars grow over a fixed real-time
  duration, so a beat that cuts before the animation lands leaves the *final*
  frame showing a value nobody wrote — at a 2-second hold an authored `50%`
  ended the beat reading `40%`. 4.0s of authored hold clears every case in the
  catalogue at any sane pace.

### 5. Write `script.yaml`

The file is two YAML documents, and it already exists with the first one filled
in. **Keep the metadata document; replace `beats: []`.**

```yaml
---
episode: '2026-08-17'
series: the-brief
status: draft
date_long: ''
pace: 1.435
---
beats:
  - type: title
    act: ""
    hold: 3.6
    sub: Five stories from the last 24 hours.

  - type: statement
    act: "01"
    hold: 3.2
    kicker: Today's headline
    text: DeepSeek just raised the price of its flagship model.
    src: _pasted
    quote: raised prices on its flagship V4-Pro model by up to 1,100%
```

**Set `pace` in the metadata**, to `target_sec / sum(holds)` at 3 decimals —
the number you computed in step 4. It ships as `1.0`, and left at `1.0` your
episode runs at a third of its target and `review` says OUT OF TOLERANCE. Leave
`status: draft` for now, and leave `episode`, `series` and `date_long` exactly
as `agsoc video new` wrote them.

The cold open — the first two beats, before act 01 — carries `act: ""`. The
act chip is simply blank on those cards.

**Three YAML mistakes that will cost you a run:**

- **Quote every act id: `act: "01"`.** Unquoted, YAML reads `01` as the integer
  1 and the schema refuses it — `act` must be a string.
- Quote any `text:` that contains a colon followed by a space, or a leading
  `%`, `&`, `*` or `@`.
- Write a quote that runs past the end of a line as a **folded block scalar**,
  so punctuation inside it needs no escaping:

  ```yaml
    quote: >-
      Alibaba's Qwen3.8-Max, at roughly 2.4 trillion parameters with about 95B
      active, is being positioned as the largest open-weight release so far
  ```

  The line breaks you introduce are collapsed to single spaces before the
  comparison, so this still matches a source that has it all on one line.

### 6. Get the figures right

This is where a first draft usually fails, and all of it is avoidable.

**What counts as a figure.** A token that **begins with a digit** is a figure
and must be justified by the quote. A token that begins with a letter is a name
and is not checked as a number — so `V4-Pro`, `Qwen3.8-Max`, `GPT-5.6` and `M1`
cost you nothing, while `1,100%`, `2.4`, `95B`, `2026` and the `2.0` in
`Apache 2.0` are all figures. **Years and list positions are figures too**: a
beat that renders `August 16` needs `16` in its quote.

**Every figure the beat displays must appear inside that beat's own `quote`.**
The comparison is by value, not by spelling, and it is generous in the ways that
matter: `95B` matches a source writing `95 billion`, `1M` matches `1,000,000`,
and `per 1M input tokens` matches `per million input tokens`. It is not generous
about magnitude — `95B` against `9B` is a refusal, which is the whole point.

**So write the quote to cover the whole sentence you are rendering, not just its
subject.** The cheapest fix for a refused figure is a wider quote — extend it
left and right in the source file until it contains every number on the card.
A quote may span several lines of YAML; whitespace is folded before comparison.

**Which fields are read as claims.** Everything a viewer reads:
`kicker`; `text`; a list's `lead` and `items`; a quote beat's `attribution`; a
KPI's rendered value, `prefix`, `unit` and `label`; a chart row's `label`,
`shown`, `before` and `after`; a dumbbell's `caption`, `footnote`, `series`
names and row `note`. `src` and `quote` themselves are not claims, and neither
are `hold`, `act`, `scale` or `decimals`.

**Figures nothing can evaluate — `3/4`, `1e9`, `12:30`, `2010-2011` — are not
exempt.** They are checked by spelling instead: the quote has to contain them
character for character. Prefer writing them the way the source does.

**Write the number you want on screen.** A KPI's `value` is formatted with
`decimals` (default `0`, which means "round to a whole number"), and a value
that changes under that formatting is refused: `value: 0.756` with
`decimals: 1` would put `0.8` on the frame, and `0.8` is in no source. Either
`decimals: 3`, or write `value: 0.8`. Same for `value: 0.75` with no `decimals`
at all — the default rounds it to `1`.

**Proper nouns are recorded, not gated.** `check` lists names it could not find
in the source under "names not found" and does not fail on them; the name
extractor glues adjacent capitalised words together. Read the list, ignore the
artefacts, and fix anything that is a genuinely wrong attribution.

### 7. Beat types, and every field each one needs

Shared optional fields on **every** type: `act`, `hold`, `kicker`, `src`,
`quote`. `hold` defaults to `3.0`; write it anyway.

| Type | Required | Optional | Citation |
|---|---|---|---|
| `statement` | `text` | — | `src` + `quote` |
| `body` | `text` | — | `src` + `quote` |
| `list` | `items` (list of non-empty strings) | `lead` | `src` + `quote` |
| `quote` | `text`, `attribution` | — | `src` + `quote` |
| `kpis` | `items[{value, label}]` | per item: `prefix`, `unit`, `decimals` | `src` + `quote` |
| `jumpChart` | `rows[{label, before, after}]`, `scale`, `footnote` | per row: `shown` | `src` + `quote` |
| `dumbbell` | `rows[{label, values}]`, `series`, `caption`, `footnote` | per row: `note` | `src` + `quote` |
| `title` | — | `sub` | none |
| `signoff` | — | `text` | none |
| `custom` | `js`, `attest` | — | attested by hand |

Notes that are each one refusal you will otherwise hit:

- **`title` and `signoff` are the only types that may omit `src` and `quote`.**
  They assert nothing about the world. Use them for the cold open and the last
  card, and nowhere else.
- **`kpis`** — `value` is a number (or a string, printed verbatim, if you
  genuinely have no number). `unit` is the **suffix** (`"%"`) and `prefix` the
  **leading symbol** (`"$"`); `$0.75` needs `prefix: "$"`, and `unit: "$"`
  renders `0.75$`. Two or three items per card.
- **`jumpChart`** — `rows` is a **list** of bars, one per benchmark. **Every
  `before` and `after` is itself a claim** and must appear in the quote, even
  `before: 0`; the bars are drawn from them, so they are numbers on the screen.
  Only build this chart when one source states both ends of every bar — if it
  publishes only the "after", you are one step away from inventing the "before",
  which is the single mistake this pipeline was built to catch. Every value must
  also lie inside `[0, scale]`; one outside it is refused rather than clipped,
  because a clipped bar reads as the maximum and that is a number your script
  never said. `footnote` is required and must not be empty.
  - `shown` is the display cell for a row. It may contain `<s>` and `</s>`,
    written exactly and with no attributes, and character references like
    `&rarr;` and `&lt;` — and nothing else, because the engine sets it as HTML
    and any attribute there could run JavaScript. **A literal `<` must be
    written `&lt;`**: a real cell reading `<1% → 3%` is
    `shown: "&lt;1% &rarr; 3%"`.
  - Every digit inside `shown` is a claim too, and the cell has to agree with
    its own bar: a `shown` carrying two or more figures must contain the row's
    `after` **and** its `before`; one carrying a single figure must contain
    `after`. `shown: "&lt;1% &rarr; 98"` on a row drawn from `before: 0` is
    refused twice over — for the `1` the bar does not draw, and for the `0` and
    `1` the quote does not contain.
- **`dumbbell`** — the type for a source that published **ratings or a
  direction, not scores**. It renders no digits at all, by design, which is why
  adding a numeric axis is not an option. Each row's
  `values` is a pair of positions **on the track, `0.0` to `1.0`**, aligned with
  the two names in `series` — not the source's own numbers. `caption` and
  `footnote` are both required, and the footnote is where you tell the viewer
  the chart encodes direction only.
  - **Cite it like anything else.** The schema will accept a `dumbbell` with no
    `src`, and then `check` reports `no_source` and refuses the episode — so
    give it a `src` and a `quote` covering the comparison it draws.
  - **Its digit rule is stricter than everywhere else, and it fires at load.**
    If `caption`, `footnote`, `kicker`, a row `label` or a row `note` contains
    **any digit at all** — including one inside a product name, so `V4-Pro` and
    `Qwen3.8-Max` both count — the script will not even parse without `src` and
    `quote` on that beat.
- **`custom` is a last resort — do not reach for it.** It is the one type that
  is executed rather than drawn, so nothing can check what it puts on the
  screen; `attest` is a sentence in which a person states what the beat
  displays and signs for it, and it lands in the ledger as `manual`, never as
  `pass`. Almost everything a `custom` beat is written for is a `statement`, a
  `body` or a `signoff`. If you write one anyway, `js` must position everything
  from the animation's own progress — `Date.now()`, `Math.random()` and
  `performance.now()` are refused — and `attest` must be a real sentence with
  the author's name, e.g. `Draws the words "Same story tomorrow." and nothing
  else. — Ali Abdukarim`.

### 8. Check, then read the report

```
uv run agsoc video check <episode-id> --series <slug>
uv run agsoc video review <episode-id> --series <slug>
```

`check` writes `claims.json` and exits non-zero while any claim is unresolved.
Every failure it prints comes with the beat, the quote, the span of the source
where the quote stopped matching, and a `fix` line. Work them one at a time:

- `no_source` — the beat cites nothing. Add `src` and `quote`, or drop the
  claim.
- `fail` + *the quote is not in `sources/<src>.txt`* — you retyped instead of
  copying, or you are quoting a different source. The `source` line under it
  shows the surrounding text with your near-miss in it; paste those bytes over
  your `quote` and reword the **beat** if it no longer reads well. (This is the
  single most common first-draft failure. It is usually one word: a source
  saying *pointing to a future* against a quote saying *points to a future*.)
- `fail` + *the quote does not contain N by value* — widen the quote until it
  covers `N`, or change the beat to a figure the source states.
- `manual` — a `custom` beat. It passes on your attestation alone.

**Fix the script, never the source.** Editing a corpus file to make a quote
match is fabrication with extra steps.

**Re-run `check` after any edit that changes what a beat says or cites.** The
ledger is compared against the claims the script produces now, and once it no
longer matches, `review` calls it STALE and shows no verdicts at all.
(Reformatting, and setting `status:` in step 9, do not invalidate it.)

`review` then shows the whole episode as the approver will see it — every beat,
its verdict, its quote, and the runtime line:

```
holds 86.6s × pace 1.386 = runtime 120.0s
target 120s ± 8s · within tolerance (+0.0s)
```

If it says `OUT OF TOLERANCE`, recompute `pace` from your actual hold total
(step 4) rather than nudging individual holds.

### 9. Hand it over

When `check` exits 0 and `review` says *within tolerance*, edit the metadata
document of `script.yaml` and set:

```yaml
status: in_review
```

Then stop, and tell the user:

- which stories the episode covers, and any coverage hits you treated as
  updates;
- the runtime and beat count;
- any beat that landed `manual`, and the sentence they are being asked to
  approve;
- that they review it with
  `uv run agsoc video review <episode-id> --series <slug>`, and that approving and
  rendering are theirs to do, not yours.

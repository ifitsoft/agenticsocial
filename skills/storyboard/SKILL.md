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
- **Copy a `quote`; never retype it — and know why the rule is not "be
  careful".** A quote is compared against the source *word for word*. The
  comparison folds away every difference you can see (case, spacing, `—` vs
  `-`, curly quotes, `…`) and forgives none of the differences you cannot: one
  word changed, dropped or added is a refusal. An author writing prose and its
  citation in the same breath smooths the citation without noticing — that is
  the single most common first-draft failure, and it happened to this skill's
  own author with this rule in front of them. **Extract the span with step 3.5
  and paste it. Do not read the source and then write the quote.**
- **Never edit an episode you did not create in this run**, unless the user
  named that episode and asked you to re-draft it. A day can hold more than one
  episode (step 3); an overwritten `script.yaml` is gone, because `workspace/`
  is not version controlled.
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

- `workspace/voice.md` — the operator's voice. **It ships as an unfilled
  template** (`Describe who you are online: …`) and has no video section at
  all: its rules are about X, LinkedIn and YouTube posts. If the headings are
  still the placeholder text, there is nothing there to follow — take the voice
  from `[series] register` in `series.toml` and from the committed episodes
  under `engine/content/*.js`, and say in your handoff that `voice.md` is
  unfilled. Do not invent a persona to fill the gap, and do not apply the X
  rules (hook-first, no hashtags, 280 characters) to a video script.
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

It prints either `NOT COVERED. Safe to run as new.` or the prior episodes that
told the story.

**Granularity: pass two terms per story — the vendor and the thing.**
`deepseek v4-pro`, `alibaba qwen3.8-max`. A term is matched as a
case-insensitive **substring** of each prior story's id, title, note, entities
and sources, so a short term over-hits (`gemini` finds every Google story ever
run) and a long one under-hits (`qwen3.8-max pricing` finds nothing, always).
The vendor term is the safety net; the product term is the answer. Then **read
the printed title and angle** — a prior *DeepSeek* story about a benchmark is
not a prior story about DeepSeek's prices.

**A hit is not a veto, and "cover it as an update" is not free.** There is no
`coverage.mjs add`: the ledger is written by hand after an episode ships, so
you cannot record that you treated a hit as an update. Today's supported branch
is therefore: **drop the story.** If the user tells you to run it as an update
anyway, the beat itself must say what has changed since — a date, a number, a
reversal — and your handoff must name the prior episode id you are updating, so
the human can put it in the ledger.

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

**If `agsoc video new` says the episode already exists, it is somebody else's
episode until you are told otherwise.** That directory holds a script a person
may have written, reviewed or approved; overwriting its beats destroys work
nothing in this pipeline can give back, and `workspace/` is not version
controlled. Two branches, and only two:

- **You are re-drafting an episode you were explicitly asked to re-draft** — the
  user named that id, or you created it earlier in this same run. Then run
  `uv run agsoc video list --series <slug>`, confirm its status is `draft` or
  `in_review` (**stop and ask if it is anything else**), skip `ingest` if
  `sources/` is already populated, and go to step 4.
- **Otherwise the day already has a different episode and yours is a second
  one.** Do not touch it. **Mint a new id by appending a lowercase letter to
  the date: `2026-08-17b`, then `2026-08-17c`.** The id is free text within its
  character set and nothing derives meaning from it; the suffix just keeps a
  day's episodes sorted together. Say in your handoff which id you created and
  which one you left alone.

Never `rm`, `mv` or overwrite anything under `episodes/`, and never edit a
`script.yaml` whose `episode:` is not the id you are working on.

Then learn the source keys:

```
ls workspace/series/<slug>/episodes/<episode-id>/sources/
```

Every `<key>.txt` is one source. **`src:` is that key without the `.txt`** — a
pasted brief lands as `_pasted`, so `src: _pasted`. `sources/_manifest.json`
gives each key's title and URL.

### 3.5 Read the bytes before you quote them

Every quote you write has to be a span of one of those `.txt` files. **Print
the span and copy it; do not read the source and then type the sentence.**

```
uv run python - <<'PY'
from pathlib import Path
p = Path('workspace/series/<slug>/episodes/<episode-id>/sources/_pasted.txt')
t = p.read_text(encoding='utf-8')
i = t.index('raised prices')          # an anchor of plain words, see below
print(repr(t[i - 40:i + 240]))
PY
```

`repr()` is the point: it shows you `\u2011` where the file holds a
non-breaking hyphen and `\u2019` where it holds a curly apostrophe, so you can
see for yourself that the bytes are not what the terminal draws. **Pick your
anchor out of ordinary words** — `t.index('open-weight')` raises `ValueError`
against a file holding `open‑weight`, and so does `grep`, because your search
string is hand-typed too.

**What the comparison forgives, verified against the checker:**

| Difference between your quote and the file | Verdict |
|---|---|
| case, runs of spaces, tabs, non-breaking spaces, a line break inside the quote | forgiven |
| `—` `–` `‑` written as `-`, either direction | forgiven |
| `’` `“` `”` written as `'` and `"` | forgiven |
| `…` written as `...`, and a leading or trailing `…` on your quote | forgiven |
| an em dash written as `--` | **refused** |
| any word added, dropped or changed — *points to* for *pointing to* | **refused** |
| an internal `…` standing in for words you skipped | **refused**: quote less, or write two beats |

So typography is not the trap. **Paraphrase is**, and the fix is mechanical:
paste the span.

Two things about the corpus itself: it keeps the brief's markdown, so a span
crossing `**bold**` has to include the asterisks — pick a span inside the prose
instead — and a quote is one contiguous run of one file, which is the
constraint that decides how many beats you have (step 4).

### 4. Plan the episode: acts, beats, holds, pace

Pick the 4–6 strongest stories out of the corpus, group them into the acts, and
sketch the beats before writing YAML.

**One beat, one contiguous quote.** A `quote` has to be a single unbroken span
of one source file — you cannot stitch two bullets or two paragraphs into one
citation. So a card that wants to say two things a source says in two places is
two beats. Decide this while you are outlining, not after `check` refuses it.

**The arithmetic, which you can do before writing a word:**

- Aim for **22–26 beats**, laid out as **two cold-open beats + four acts of 4–6
  beats + one signoff**. The cold open and the signoff sit *outside* the acts —
  that is what makes the arithmetic work, and it is why the per-act count is 4–6
  rather than 5–7.
- **If `series.toml` declares no acts** (they ship commented out), use four:
  `"01"`, `"02"`, `"03"`, `"04"`. The act string is free text, the chip prints
  whatever you write, and four is the shape both committed episodes use. One
  story per act, or two short ones.
- Give each beat a `hold` between **2.6 and 5.6 seconds** — short for a single
  sentence, long for a card the viewer has to read (a list, a chart, KPIs).
- Sum your holds. **Aim for a total between 80 and 95 seconds.**
- Then set `pace` in the metadata so the runtime lands on target:

  ```
  pace = target_sec / sum(holds)      rounded to AT MOST 3 decimals
  ```

  At most: `1.31` is what 91.6s against 120s rounds to, and YAML has no way to
  write `1.310` as a number. Do not pad it, and do not go past three — the
  runtime moves by a hundredth of a second and `review` prints one decimal.

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

**Set `pace` in the metadata**, to `target_sec / sum(holds)` at up to 3
decimals — the number you computed in step 4. It ships as `1.0`, and left at
`1.0` your episode runs at a third of its target: `check` and `review` both
print the runtime, and both will say OUT OF TOLERANCE. Leave `status: draft`
for now, and leave `episode` and `series` exactly as `agsoc video new` wrote
them.

**`date_long: ''` is correct — leave it empty.** It is a spec field nothing
reads yet: the loader does not parse it and the renderer prints the episode id
on the title card regardless, so a prettier date there changes no frame. It is
an authoring hole, not a field you are expected to fill.

The cold open — the first two beats, before act 01 — carries `act: ""`, and so
does the signoff: the act chip is simply blank on the bookend cards. (`act` is
free text and purely cosmetic, so the committed `2026-08-17` writing `act: "04"`
on its signoff is equally valid. Pick one and be consistent within an episode.)

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

**A KPI's `unit` carries magnitude, and it is checked by value.** The token the
checker reads is `prefix + value + unit` glued together, so `value: 2.4` with
`unit: T` is the figure `2.4T` — 2.4 trillion — and it verifies against a source
saying *2.4 trillion parameters*. That is a real check, not a spelling one:
`9.4T` and `2.4B` both fail against the same quote. `K M B T` (and `bn mn tn`)
are magnitudes; `%`, `x` and `bps` are units and multiply by one. So write the
magnitude in `unit` rather than in the label, and never write a value already
expanded (`value: 2400000000000`) — the frame would show it.

**Proper nouns are recorded, not gated.** `check` lists names it could not find
in the source under "names not found" and does not fail on them; the name
extractor glues adjacent capitalised words together, so `DeepSeek V4-Pro Alibaba`
is one "name" and no corpus contains it. Figures are not in that list — `2.4T`
is a number, checked by value, and it appears there only if something is wrong.
Read the list, ignore the glued runs, and fix anything that is a genuinely wrong
attribution.

### 7. Beat types, and every field each one needs

Shared optional fields on **every** type: `act`, `hold`, `kicker`, `src`,
`quote`. `hold` defaults to `3.0`; write it anyway.

| Type | Required | Optional | Citation |
|---|---|---|---|
| `statement` | `text` | — | `src` + `quote` |
| `body` | `text` | — | `src` + `quote` |
| `list` | `items` (list of non-empty strings) | `lead` | `src` + `quote` |
| `quote` | `text`, `attribution` | — | `src` + `quote` |
| `kpis` | `items[{value, label}]`, `src`, `quote` | per item: `prefix`, `unit`, `decimals` | required at load |
| `jumpChart` | `rows[{label, before, after}]`, `scale`, `footnote`, `src`, `quote` | per row: `shown` | required at load |
| `dumbbell` | `rows[{label, values}]`, `series`, `caption`, `footnote`, `src`, `quote` | per row: `note` | required at load |
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
  direction, not scores**. Its *chart* draws no digits, by design, which is why
  adding a numeric axis is not an option; its caption, footnote, series names
  and row labels are words a viewer reads and the checker checks. Each row's
  `values` is a pair of positions **on the track, `0.0` to `1.0`**, aligned with
  the two names in `series` — not the source's own numbers. `caption` and
  `footnote` are both required, and the footnote is where you tell the viewer
  the chart encodes direction only.
  - **It cites like every other chart, always.** `src` and `quote` are required
    at load — a dumbbell with neither will not parse, digits or no digits —
    because its `caption`, `footnote`, `series` names and row labels are all
    claims the checker reads. Quote the comparison the chart draws.
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

`check` writes `claims.json`, prints the runtime, and exits non-zero while any
claim is unresolved. **The runtime line is not part of the exit code** — a green
`check` on a 37-second episode is a real thing that happens, so read the last
two lines as well as the first:

```
holds 86.6s × pace 1.386 = runtime 120.0s
target 120s ± 8s · within tolerance (+0.0s)
```

If it says OUT OF TOLERANCE, recompute `pace` from your actual hold total (step
4) rather than nudging individual holds, and re-run.

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
its verdict, its quote, and the same two runtime lines.

### 8.5 The commands, in order

Every command this skill tells you to run, in the order you run them, all from
the repo root. There are no others; if you find yourself inventing one, re-read
the step.

```
uv run agsoc series list
node engine/coverage.mjs check <term> [term...]
uv run agsoc video new <episode-id> --series <slug>
uv run agsoc video ingest <episode-id> --series <slug> --paste <file>
uv run agsoc video list --series <slug>
uv run agsoc video check <episode-id> --series <slug>
uv run agsoc video review <episode-id> --series <slug>
```

`agsoc video new` prints its own `next:` hint and the hint is correct — it
carries `--series`. **`approve`, `render`, `preview` and `post` are not on this
list and are not yours to run.**

### 9. Hand it over

When `check` exits 0 and `review` says *within tolerance*, edit the metadata
document of `script.yaml` and set:

```yaml
status: in_review
```

Then stop, and tell the user:

- which episode id you wrote, and — if the day already had one — which episode
  you left untouched;
- which stories the episode covers, and any coverage hits you treated as
  updates (naming the prior episode id);
- the runtime and beat count;
- whether `workspace/voice.md` was still an unfilled template, if it was;
- any beat that landed `manual`, and the sentence they are being asked to
  approve;
- that they review it with
  `uv run agsoc video review <episode-id> --series <slug>`, and that approving and
  rendering are theirs to do, not yours.

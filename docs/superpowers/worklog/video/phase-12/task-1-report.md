# Phase 12 · Task 1 — `agsoc video console`

**Branch:** `feat/video-phase-12-console` · **Baseline:** 1980 tests → **2025**
**Mutation:** **45 of 46 killed**, the survivor argued equivalent, harness committed
**Scope:** §12 screens **C** and **D**. Not A, not B, and **not E**.

```
agsoc video console <ep> [--series <slug>] [--out PATH]
```

One self-contained HTML file. It reads. It writes nothing into the episode, it
makes no network request, and it cannot approve anything.

---

## 1. How the highlight is computed, and whether the span landed

**It is a slice, not a search:** `document[a:b]`, where `[a, b]` is the ledger's
`quote_span` — the offset Phase 5 recorded **in the original text rather than
the folded text**, specifically so a screen could mark the real bytes. The
excerpt is `document[a-320 : a]` + `<mark>document[a:b]</mark>` +
`document[b : b+320]`, escaped in three pieces and rendered `white-space:
pre-wrap`, so the paragraph breaks an operator sees are the file's own.

Nothing in `console.py` searches the corpus for anything. When `quote_span` is
absent (a `fail`), it marks `closest_span` instead — in a different colour,
under a label that says in words that this is **not** the quote:

> QUOTE NOT FOUND — THIS IS THE CLOSEST CANDIDATE IN THE SOURCE, NOT THE QUOTE

**On real data the span landed on every claim that has one.** Measured against
the operator's own `2026-08-17`, comparing each `<mark>`'s text in the live DOM
with `sources/_pasted.txt[a:b]` read independently:

```
marks on page: 6
  c-002: span [110, 165]   highlighted=True  'AI pricing snapped sharply in both directions yesterday'
  c-003: span [283, 341]   highlighted=True  'raised prices on its flagship V4‑Pro model by up to 1,100%'
  c-004: span [1451, 1528] highlighted=True  'announced new pricing starting August 16 at about $1.32 / $3'
  c-005: span [1832, 1951] highlighted=True  'at roughly 2.4 trillion parameters with about 95B active, is'
  c-006: span [2270, 2440] highlighted=True  'Qwen3.8‑27B is a 27.8B dense model under Apache 2.0 that ben'
  c-007: span [4726, 4802] highlighted=True  'claiming up to a 98% reduction in context size across 12 sup'
  c-008: no span (manual)

6 spans landed, 0 did not
```

Two things worth noting from that run:

- **c-003 and c-006 contain U+2011 non-breaking hyphens** (`V4‑Pro`,
  `Qwen3.8‑27B`) and the operator's `quote:` is typed with ASCII `-`. The
  highlight covers the *source's* bytes; the `cited` row above it shows what the
  operator typed. D-110's "which differences are forgiven" is visible on the
  screen, side by side, rather than being something an author has to know.
- The fixture in the test suite is built so the folded and original coordinates
  **disagree** (NBSP, a `…`, a whitespace run and a `\n\n` before the quote), and
  one test asserts the fixture itself still has that property. Without it, M2 —
  "the highlight computed by searching the folded text" — would be undetectable
  and nothing would say so. With it, M2 dies.

## 2. Where the file goes, and whether it is gitignored

**Default:** `<tmpdir>/agsoc-console/<series>-<episode>.html`. Not `workspace/`,
not the episode directory. `--out` accepts anywhere **except** inside the
workspace, and the path is `resolve()`d before the comparison, so a symlink or a
`..` cannot spell around it (a test uses a symlink; M9c pins it).

The question "is it gitignored" therefore does not arise: nothing is written
inside the repo at all. That is the stronger answer than adding a
`.gitignore` line, and it follows from the phase's own rule — the console is
**derived** (regenerate it in a second), it contains the operator's content, and
writing it into the episode would make a second writer beside `check` in the
directory whose single-writer property is the reason Phase 7 exists (D-059,
D-113).

## 3. TDD evidence and the mutation score

**Commits, in order, unsquashed:**

| SHA | |
|---|---|
| `040f15d` | tests first — 38 tests from the mutant table, **failing at import** |
| `0bbc336` | `console.py` + `agsoc video console` (screens C and D) |
| `9759544` | tests that kill the sweep's eight survivors; **harness committed** |
| `5e2f2d0` | four defects found by opening the page |
| `b256e81` | a fifth: the remedy line printed over a solved problem |

RED, before any implementation existed:

```
ImportError: cannot import name 'console' from 'agenticsocial.video'
1 error in 0.12s
```

**Mutation sweep** — `docs/superpowers/worklog/video/phase-12/task-1-mutants.py`,
run with `PYTHONDONTWRITEBYTECODE=1` (D-100). The harness refuses to run at all
if any anchor does not match exactly once: a mutant that does not apply is not a
measurement.

```
baseline: PASS (2025 passed, 6 warnings in 20.14s)
  M1a   killed    a remote favicon
  M1b   killed    a webfont imported from the stylesheet
  M1c   killed    the CSP is dropped from the page
  M1d   killed    the CSP permits inline script
  M2    killed    the highlight is found by searching the folded text
  M2b   SURVIVED  the marked text is tidied before it is shown
  M2c   killed    the near miss is shown as the supporting quote
  M3    killed    the quote is shown with no context around it
  M3b   killed    only a few characters of context
  M4a   killed    the claim's word is read from the mechanical block
  M4b   killed    the gate state is re-derived from the verdict
  M4c   killed    the beat-list cell shows the measurement
  M4d   killed    pass 1's word loses its label
  M5a   killed    an attested claim is labelled verified
  M5b   killed    the attestation sentence is not shown
  M5c   killed    attested drops the NOT verified caveat
  M6a   killed    the judgement is presented as a measurement
  M6b   killed    the judgement block is styled like every other row
  M6c   killed    the judgement's author and expiry are dropped
  M7a   killed    the risk is shown only where the judgement refuses
  M7b   killed    the risk is never shown
  M8a   killed    a stale ledger shows its verdicts anyway
  M8b   killed    the staleness banner stops shouting
  M8c   killed    staleness is decided here rather than by `stale_reason`
  M9a   killed    any --out is accepted, including inside the episode
  M9b   killed    the default lands beside the script
  M9c   killed    the guard compares unresolved paths
  M10a  killed    a button appears beside the command
  M10b  killed    an event handler reaches the page
  S1    killed    nothing is escaped
  S2    killed    the near miss is labelled as the quote
  S3    killed    the open count is dropped from the header
  S4    killed    pass-2 coverage is only reported when pass 2 ran
  S5    killed    screen D opens only the claims the gate refuses
  S6    killed    the override diff loses its diff
  S7    killed    the override is presented as a small formality
  S8    killed    the refuter's reasoning is not shown
  S9    killed    beats are not grouped by act
  S10   killed    an unrecorded render is not mentioned
  S11   killed    a probe frame is linked rather than embedded
  S12   killed    with no frames the page says nothing about looking
  S13   killed    the approve command is not printed
  S14   killed    the drift banner is silent
  S15   killed    an unparseable script still produces a page
  S17   killed    the fix line is printed on claims that are not open
  S16   killed    the runtime is reported without the target

45 killed, 1 survived, 46 total
SURVIVOR M2b: the marked text is tidied before it is shown
```

**The first run was 34/45.** The eight survivors are recorded in `9759544`; the
two worth repeating here, because both were the *test* being weaker than it
looked:

- **M4c** — the beat-list cell built from the measurement. Every verdict test
  read the claims panel; the column an operator actually **scans** was
  unasserted, so `pass` could sit on the row the gate refuses. D-123's defect,
  one column across, in the screen written to prevent it.
- **M6b** — the pass-2 wrapper renamed. The assertion was "a judged claim has
  *some* class a measured one does not", which any wrapper satisfies. It now
  names `.judged`, requires its CSS rule to paint something, and requires a
  claim pass 2 never touched **not** to wear it.

**M2b is equivalent, and the argument is the finding.** `.strip()` on the marked
slice can never change it: `_needle` strips before searching, so the first and
last folded characters are non-space, and only a whitespace *run* folds to a
shared origin span — a non-space folded character maps to exactly one non-space
original character. Measured as well as argued, over a document seeded with
NBSP, tabs, CRLF, `…`, `ß` and U+2011:

```
spans checked: 38586 · spans with edge whitespace: 0
```

So: **45/45 non-equivalent.**

## 4. Step 5 — what I saw, and how zero requests was verified

The console for the operator's real `2026-08-17`, opened in Chromium over
`file://`. **The workspace was never modified** — the console writes to a temp
directory — and that is not an argument, it is a diff:

```
find workspace -type f -exec shasum {} \;   # before and after every run
WORKSPACE UNCHANGED (final)
```

**Zero network requests, verified two ways** — and the second is the one that
counts, per D-089:

```
requests the page made:
   file://…/the-brief-2026-08-17.html
bytes arriving at 127.0.0.1:8799 : []
CSP violations logged          : 0
script/iframe/form/button/input elements: 0
```

The first line is Chromium's own request log: **the page fetched itself and
nothing else.** The second line is the D-089 oracle — a real HTTP server on
`127.0.0.1:8799` listening for the duration — because a CSP-refused request
still fires Chromium's `request` event, so that event alone reports a *working*
policy as a leak. Nothing arrived at the socket. Zero CSP violations logged is
the third leg: nothing was even attempted and blocked. The page's own policy is

```
default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'
```

with **no `script-src` at all**, because there is no script — naming it would
only permit some. It is in the page rather than in the generator for D-089's
reason exactly: this file is opened by hand from `file://`, which is the path a
runner-side check would leave open.

**The marks in the live DOM** (not in the source string — read back out of the
rendered page):

```
    hit :: AI pricing snapped sharply in both directions yesterday
    hit :: raised prices on its flagship V4‑Pro model by up to 1,100%
    hit :: announced new pricing starting August 16 at about $1.32 / $3.96 per 1M tokens
    hit :: at roughly 2.4 trillion parameters with about 95B active, is being positioned as the largest open‑weigh
    hit :: Qwen3.8‑27B is a 27.8B dense model under Apache 2.0 that benchmarks near proprietary frontiers on agent
    hit :: claiming up to a 98% reduction in context size across 12 supported platforms
```

Page text, top of the real episode:

```
the-brief/2026-08-17 · review console
draft · 9 beats · The Brief · generated 2026-08-18T17:09:57-05:00
holds 37.5s × pace 1.0 = runtime 37.5s · target 120s ± 8s · OUT OF TOLERANCE (-82.5s)
7 claims · 6 pass · 1 manual
6 verified · 1 attested by hand, NOT verified (D-088)
pass 2 · 0 of 7 claims judged — a judgement by an agent, NOT a measurement: not reproducible, and it expires
This console reads. It writes nothing and it cannot approve: the gate is a command you run yourself, and it re-reads every file before it decides.
agsoc video check 2026-08-17 --series the-brief
agsoc video approve 2026-08-17 --series the-brief --by "your name"
```

**A `residual_risk` on a `supported` claim**, and the refuted case, needed a
pass-2 ledger that no real episode has, so a synthetic episode was built in a
**separate** temp workspace (the operator's three episodes were not touched).
What the page shows for a claim pass 2 supported:

```
c-002  statement · beat 1   pass   verified
DeepSeek announced new pricing starting August 16.
cited     local-ai-zone · “announced new pricing starting August 16”
[source paragraph, with the quote highlighted in the middle of it]
pass 1    pass
pass 2 · supported · a judgement by an agent, NOT a measurement: not reproducible, and it expires
judged by       Ali Abdukarim on 2026-08-18T17:02:39-05:00, stops standing 2026-11-16
attacked        Checked the date against the two other price notices in the corpus; both agree.
residual risk   The source does not state an effective date, so this is true on the day it was
                written and may not be on the render date.
```

That block is purple-bordered on both themes and is the only element on the page
styled that way; every mechanical row is grey. The refuted claim reads
`refuted · open` at the top with `pass 1  pass` underneath it, labelled.

And the stale case, which I also looked at rather than trusting the test:

```
claims.json is STALE — the script has changed since this check was written. No verdict and
no highlight is shown: the spans in this ledger describe words that are no longer in the
script. Re-run agsoc video check 2026-08-18 --series the-brief
…
No verdicts are shown for this episode.
```

**Five defects came out of looking, and none of them came out of the suite:**

1. the verdict pill in the beat list stretched its grid cell and read as an
   empty input box — on a page whose whole claim is that it has no inputs;
2. the `file://` line the command prints was wrapped at 100 columns by
   `_detail`, so the URL could not be copied;
3. the pass-2 block printed the refutation twice, as `attacked` and again as
   `why it does not clear`;
4. the override diff had a blank line between every added line (`<ins>` is a
   block, and the newline sat outside it);
5. **the adjudication card told an attested claim to attest itself.**

The fifth is the one worth keeping. `cli._next_step` answers *what do you do
about this claim*, and `check` calls it on **blocking** records only. Screen D
called it on every card, so above the `custom` beat's own attestation it printed
`write `attest:` on the beat`. Reused code, correct function, wrong population —
and the result is a remedy for a problem that does not exist, three lines under
the sentence that solved it. It is gated on `is_blocking` now, pinned in both
directions, and S17 in the sweep.

## 5. Files changed

| File | |
|---|---|
| `src/agenticsocial/video/console.py` | new — the page (≈700 lines with its argument) |
| `src/agenticsocial/video/cli.py` | `agsoc video console`; `tempfile` + `atomic_write` imports |
| `tests/test_video_console.py` | new — 45 tests |
| `docs/superpowers/worklog/video/phase-12/task-1-mutants.py` | new — the harness |

Commits: `040f15d`, `0bbc336`, `9759544`, `5e2f2d0`, `b256e81`.
`git status --porcelain -- src tests engine skills` is clean.

## 6. Issues and concerns

### What can an operator misread on this screen?

Six things, in the order I would worry about them.

1. **`pass 1  pass` sits under every claim, including refuted ones.** It is
   labelled, and D-123 argues for keeping it — an operator should be able to see
   that the mechanical check passed *and* that a judgement overrode it. But it
   is the word `pass` on the card of a claim the gate refuses, and it is there on
   every card, which is exactly how a caveat becomes wallpaper. The binding
   verdict is first, larger and pill-shaped; that is the mitigation, and I do not
   think it is a complete one.

2. **A `verified` claim is verified *against a quote the operator chose*.**
   The screen shows the quote highlighted in its source, which is what makes the
   "torn from context" failure visible — but only if the operator reads the
   surrounding 320 characters. A quote that is verbatim, in context, and cited
   from a source that is itself wrong reads exactly like a good one. Nothing on
   this page can fix that; it is §8.2's stated bound, and the page does not
   claim otherwise, but a green pill is persuasive.

3. **`0 of 7 claims judged` can read as "nothing found" rather than "nothing
   looked".** The sentence after it says what pass 2 is, but the number leads.

4. **The near-miss highlight is a highlight.** On a `fail`, the pink mark is
   visually similar to the yellow one at a glance, and the difference between
   "this is your quote" and "this is the nearest thing to it" is carried by the
   colour and a line of small caps. I chose to mark it anyway because §8.2's
   whole argument is that a bare red mark teaches people to override without
   looking — but somebody skimming can mistake one for the other.

5. **The probe strip does not say which beat a frame is.** `render.mjs` names
   frames by scene; nothing on disk records the mapping. Captioning a frame with
   a beat would be a confident wrong label, so the page says so instead. The cost
   is that the frames are less useful than they look.

6. **`generated <timestamp>` is the console's own clock, not the ledger's.**
   The ledger's `checked_at` is not on the page. A console generated today from a
   check run last week is *not* stale in `stale_reason`'s sense (nothing moved),
   and I think that is right — but the operator sees only today's date.

### Phase 11's gap — is the console the place to surface it?

**Partly, and it is in.** A `rendered` episode absent from the series
`coverage.json` now gets a banner naming `agsoc coverage add`. That is the
*covered but never recorded* half, and the console is the natural place for it
because it is the one screen that reads the episode and the series ledger
together.

The other half is not fixed and cannot be fixed here: `agsoc coverage check`
still cannot distinguish *not covered* from *covered but never recorded*,
because the console is read by whoever opens it, and `check` is read by the
agent writing the next episode. The nag belongs where the omission causes harm —
in `coverage check`'s own output, at the moment a story is about to be re-told
as new — and that is a change to `coverage.py`, not to a page.

### Deviations, stated

- **Screens C and D landed in one commit** (`0bbc336`) rather than two. The
  adjudication card is the claim card plus the remedy, the reasoning and the
  diff; splitting it would have meant writing the shared blocks, committing, and
  rewriting them. Tests-first and no-squash held.
- **`console.py` imports `cli.py`**, not the reverse: `beat_summary`,
  `_next_step`, `_counts`, `_plural`, `_pace`. The page is built *on* the
  terminal screens so that one remedy sentence and one counts line serve both —
  the alternative was a second set, which is the shape of every overclaim this
  project has recorded. The command's import of `console` is therefore local to
  the function, and that is the only reason it is not at the top of the file.
- **No live preview.** §12 asks for `scene.html` in an iframe. The page embeds
  `probe/*.png` when they exist and prints `agsoc video probe` when they do not,
  with D-116's sentence about what an approval does not cover. No real episode
  has probe frames on disk, so on the operator's own episodes this region is the
  command and the caveat.

### Carried

Screens A, B and E, by the phase's decision. The live iframe. D-124
(`skills/verify` has never had a blind acceptance run). D-056/D-120 (`engine/`
runs only from a source checkout).

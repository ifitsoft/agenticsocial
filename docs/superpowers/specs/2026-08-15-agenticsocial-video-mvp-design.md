# agenticsocial — Video MVP Design

Date: 2026-08-15
Status: design approved (architecture); spec pending review
Supersedes nothing. Extends `2026-08-12-daily-ai-brief-video-design.md`, which
described a single hand-built episode; this describes the product around it.

---

## 1. What this is

A local-first pipeline that takes a domain expert from **raw input** (a research
query, or a pile of news text they paste in) to a **fact-checked, rendered video**
in both vertical and horizontal formats — with a human approval gate that cannot
be bypassed and a verification layer that blocks unverified claims from ever
reaching a render.

The agent (Claude Code, via skills) does everything judgment-based: gathering,
selecting, structuring, writing. The CLI (`agsoc`) does everything mechanical:
storage, status, verification arithmetic, rendering, publishing. This split is
inherited from the existing product and is not negotiable — it is what makes the
output auditable.

### 1.1 Who it is for

An engineer or subject-matter expert who has genuine domain knowledge, a point of
view, and no time to operate a video production workflow. They can read a script
faster than they can write one; they can spot a wrong claim instantly but will not
notice a fabricated number in a slick render. The product is designed around both
of those facts.

Concretely: someone running a recurring brief in their field — AI, cardiology,
semiconductors, tax law — who needs each episode to be *correct* more than they
need it to be beautiful, and who will personally be blamed if it isn't.

### 1.2 The job to be done

> "Turn what I already know and what just happened into a video I'm willing to put
> my name on, without me having to check every number myself."

### 1.3 Non-goals for the MVP

- Not a video editor. There is no timeline UI, no keyframe editing, no asset library.
- Not a general-purpose motion graphics tool. The visual system is opinionated.
- Not multi-user. One operator, one machine, files on disk.
- Not a scheduler. Nothing runs on a cron.
- Not a CMS. No database.

---

## 2. What already exists

This matters because the MVP is mostly connective tissue, not greenfield.

**`engine/` — a working deterministic render engine.**
*(Relocated 2026-08-16 from `workspace/brief-video/`, which was gitignored — the
engine source had no version history and Phase 4 modifies it on a branch.)*
`scene.html` exposes `window.__seek(t)` which positions every element purely as a
function of `t`: no CSS keyframes, no `Date.now()`, no randomness. `render.mjs`
drives Playwright to screenshot each frame; ffmpeg encodes. Two full 120s episodes
have been produced this way. It already has a motion primitive vocabulary
(`rise`, `fade`, `draw`, `count`, `kpis`, `jumpChart`), persistent chrome, a
9:16 safe area, a `pace` read-speed knob, per-beat source tags, and
`coverage.json` — a ledger that prevents the series re-telling a story as new.

**`src/agenticsocial/` — a working publishing spine.**
Workspace-as-filesystem, YAML frontmatter, a status machine with a deliberate
approval gate, atomic writes, OS-keychain OAuth, and resumable thread posting that
persists progress after every single tweet.

**The determinism property is the load-bearing one.** Because `__seek(t)` is pure,
any frame can be re-created for inspection months later, and a render is
reproducible. Every design decision below preserves it.

---

## 3. Locked decisions

These were settled during brainstorming. Recorded with rationale so they aren't
relitigated.

| # | Decision | Rationale |
|---|---|---|
| 1 | **Series-first; a one-off is a series of one** | The recurring brief is the real use case, and the dedup ledger only makes sense in a series. Modelling a standalone video as a degenerate series avoids a second code path. |
| 2 | **Declarative beats + a `custom` JS escape hatch** | Makes 9:16 → 16:9 a render flag instead of a re-authoring job, and gives the verifier structured data to walk. The escape hatch survives because existing episodes genuinely use bespoke `an()` animations. |
| 3 | **Two-pass verification with a hard gate** | Pass 1 mechanical (free, deterministic) kills fabricated figures. Pass 2 adversarial catches what pass 1 structurally cannot: right number/wrong subject, stale date, quote out of context. |
| 4 | **Pasted text is ground truth; web corroboration opt-in** | When the operator pastes a digest, they have vouched for it. The video still may not claim anything the paste doesn't say. |
| 5 | **MVP ships 9:16 and 16:9** | Both formats now. TTS, image generation, and video-to-X are staged. |
| 6 | **Series identity = tokens + structure over one design system** | A new operator changes palette, type scale, byline, acts, runtime. Everyone inherits the same grid, motion primitives, chrome and safe areas. One layout engine to maintain; no series looks templated. |
| 7 | **`agsoc` (Python) orchestrates; Node stays a pure renderer** | Playwright needs Node; everything else already works in Python. The handoff is a directory, which is this project's existing notion of state. |

### 3.1 Explicitly staged (not MVP)

| Feature | Why it's deferred | What it will disturb when added |
|---|---|---|
| TTS voiceover | Makes timing authoritative: beat durations stop being the `pace` knob and start being dictated by speech length | The engine must retime scenes *to* audio rather than the reverse — a real inversion |
| AI image / b-roll | Cuts against a deliberately typographic, deterministic, verifiable visual system | Generated imagery is neither reproducible nor fact-checkable |
| Publish video to X | Requires X's chunked media upload (INIT/APPEND/FINALIZE + status polling) | A genuinely different client from the current one-shot tweet POST |
| Web UI as a control surface | MVP UI is review-and-approve only (§12) | — |

---

## 4. Architecture and data flow

Six stages. The first four are cheap and reversible. The expensive one is gated
behind a human.

```
 ① INGEST        research query ──┐
                 pasted text ─────┼──→ brief.md + sources/*.txt
                 existing source ─┘         (the verification corpus)

 ② STORYBOARD    [agent skill]  brief + sources + series.toml + voice.md
                                        ↓
                                   script.yaml   status: in_review

 ③ CHECK         pass 1 mechanical (pure Python, milliseconds, no LLM)
                 pass 2 adversarial (subagent per claim, refute-only)
                                        ↓
                                   claims.json + report

 ④ REVIEW        script, runtime estimate, per-claim verdicts

 ⑤ APPROVE       ← THE GATE. refuses while any claim is unverified.

 ⑥ RENDER        script.yaml ──→ node render.mjs --format vertical
                              └─→ node render.mjs --format wide
                                        ↓
                                out/*.mp4 + poster.png
```

Two properties are deliberate and load-bearing:

**The verification corpus is a directory of fetched text, not a memory.**
`sources/blog-google.txt` is the literal file the mechanical pass greps and the
adversarial agent reads. It is written at ingest and kept with the episode
forever. A claim is never checked against "what the agent recalls reading" — it is
checked against bytes on disk. This is what makes the check reproducible, and what
lets the UI highlight the exact supporting span.

**The gate is `approve`, not `render`.** One gate, in the place this project
already puts it. Previewing happens through `probe` (one frame per beat, ~2s, no
encode), so there is never a legitimate reason to render before approval, and
rendering stays strictly downstream of the human.

---

## 5. Workspace layout

Episodes get their own tree. An episode composes *many* sources, so it does not
fit the existing one-source-to-N-variants shape.

```
workspace/
  voice.md                          ← existing, unchanged
  config.toml                       ← existing, unchanged
  sources/                          ← existing text pipeline, untouched
    2026-08-14-kill-staging/
      source.md
      x.md

  series/
    the-brief/
      series.toml                   identity + structure + formats + cadence
      coverage.json                 dedup ledger (relocated from engine/ in Phase 11)
      episodes/
        2026-08-14/
          brief.md                  assembled input, human-readable
          sources/                  THE VERIFICATION CORPUS
            blog-google.txt
            venturebeat.txt
            _pasted.txt             when input was pasted
            _manifest.json          key → {url, fetched_at, sha256, title}
          script.yaml               declarative beats + frontmatter status
          claims.json               claim ledger with both verdicts
          out/
            vertical-1080x1920.mp4
            wide-1920x1080.mp4
            poster.png
          probe/                    single-frame inspection PNGs
    default/                        implicit series for one-offs
      series.toml
      episodes/…
```

`frames/` (~2.5 GB of intermediate PNGs per episode) is written to a temp
directory and deleted after encode. It is never inside `workspace/`.

---

## 6. Series configuration

`series.toml` is what a new operator edits to make the product theirs. It carries
design tokens and structure — never layout code.

```toml
[series]
name       = "The Brief"
slug       = "the-brief"
byline     = "Ali Abdukarim"
cadence    = "daily"              # daily | weekly | adhoc — advisory, nothing schedules
register   = "reported"           # reported | first-person — selects voice rules

[runtime]
target_sec = 120                  # pace is derived: target_sec / sum(beat holds)
tolerance_sec = 8

[formats]
enabled = ["vertical", "wide"]    # vertical 1080x1920 · wide 1920x1080

[design]
surface     = "#F2F5F8"
ink         = "#0B1B2B"
ink_muted   = "#5A6B7C"
accent      = "#2E6BFF"
accent_alt  = "#00C2D7"
accent_warm = "#FF6B4A"           # reserved; see warm_acts
type_family = "SF Pro Display, Helvetica Neue, system-ui"
type_scale  = "default"           # default | compact | large

[structure]
warm_acts = []                    # acts permitted to use accent_warm
acts = [
  { id = "cold-open", label = "",                  beats = 2 },
  { id = "01",        label = "01 — The headline", beats = 6 },
  { id = "02",        label = "02 — Models",       beats = 6 },
  { id = "03",        label = "03 — Agents",       beats = 5 },
  { id = "04",        label = "04 — The human one",beats = 5 },
]
```

`beats` counts are advisory targets handed to the storyboard skill, not validated
constraints — a story that needs seven beats should get seven.

---

## 7. The beat schema (`script.yaml`)

An episode script is data. The engine owns layout, timing curves, chrome, and
aspect-ratio adaptation; the script owns content, order, emphasis, and
attribution.

```yaml
---
episode: 2026-08-14
series: the-brief
status: in_review
date_long: "Friday, 14 August 2026"
pace: 1.293            # written by `agsoc video review`, not by the agent
---

beats:
  - type: statement
    act: cold-open
    hold: 3.0
    text: "Google shipped its main agentic model — and halved the price."

  - type: title
    act: cold-open
    hold: 3.6
    sub: "Five stories from the last 24 hours."

  - type: statement
    act: "01"
    hold: 3.2
    kicker: "Today's headline"
    text: "Gemini 3.7 Flash is Google's new workhorse."
    src: blog-google
    quote: "Gemini 3.7 Flash is our new workhorse model"

  - type: list
    act: "01"
    hold: 4.2
    kicker: "Live today in"
    lead: "A natively multimodal reasoning model tuned for **coding, agentic
           workflows and knowledge work**, with a one-million-token context window."
    items:
      - "Gemini API & AI Studio"
      - "Antigravity"
      - "Gemini Enterprise Agent Platform"
      - "The Spark agent"
    src: blog-google
    quote: "…available today in the Gemini API and AI Studio, Antigravity,
            the Gemini Enterprise Agent Platform, and Spark."

  - type: kpis
    act: "01"
    hold: 4.6
    kicker: "And it costs half of what 3.6 Flash did"
    items:
      - { value: 0.75, prefix: "$", label: "per 1M input tokens",  decimals: 2 }
      - { value: 3.75, prefix: "$", label: "per 1M output tokens", decimals: 2 }
    src: venturebeat
    quote: "priced at $0.75 per million input tokens and $3.75 per million output"

  - type: custom
    act: "04"
    hold: 5.0
    js: |
      const h = E('h2', null, P('…'));
      rise(h, .15);
```

### 7.1 Beat type catalogue

Every type below already has a working implementation in `engine.js` or is a thin
composition of existing primitives.

| Type | Content fields | Motion | Verifiable |
|---|---|---|---|
| `statement` | `text`, `kicker?` | masked word rise | yes |
| `body` | `text` (bold via `**`) | blur-to-sharp fade | yes |
| `list` | `lead?`, `items[]`, `kicker?` | staggered slide from left | yes |
| `kpis` | `items[{value,label,prefix?,unit?,decimals?}]`, `kicker?` | eased count-up | **yes, strictly** |
| `jumpChart` | `rows[{label,before,after,shown}]`, `scale`, `footnote` | value morph on a common scale | **yes, strictly** |
| `dumbbell` | `rows[]`, `series[2]`, `caption`, `footnote` | dots apart → together | direction only |
| `quote` | `text`, `attribution` | fade + rule draw | **yes, verbatim** |
| `title` | `sub?` | title card composition | no |
| `signoff` | `text?` | closing card | no |
| `custom` | `js` | arbitrary | **manual attestation required** |

Shared optional fields on every type: `act`, `hold`, `kicker`, `src`, `quote`,
`claim_override`.

### 7.2 Chart integrity rules (carried forward, now enforced)

The existing README states these as prose. They become checks:

- A `jumpChart` or `kpis` beat **must** carry `src` and `quote`, and every numeric
  `value` must appear inside that `quote`. There is no path to rendering a number
  that isn't in a source.
- `dumbbell` encodes direction only and must carry a `footnote` saying so. It is
  the correct type when a source publishes ratings rather than scores.
- **`dumbbell` requires `src` and `quote`, like the two strictly verifiable
  types.** An earlier draft exempted it on the grounds that it renders no
  numbers. That is true of its `values` and false of the *type*: its `caption`,
  `footnote`, series names and row labels are prose, they are extracted as claims,
  and they assert a comparison — "A improved more than B" is exactly the sort of
  statement a viewer believes. The exemption was also unreachable in practice:
  `claims.py` extracted the type regardless, so an uncited dumbbell answered
  `no_source` and `check` refused a beat the schema had blessed. Worse, the
  conditional version fired on a row label containing `V4-Pro` and *not* on
  "AMIE against primary care physicians" — backwards, which is the tell that the
  rule was keyed on digits rather than on assertion.
- Where two dumbbell values coincide, the engine draws a single two-tone marker
  rather than stacking two dots, which would hide one series entirely.

---

## 8. Verification: the claim ledger

This is the product's differentiator and deserves the most care.

### 8.1 The record

`claims.json` is generated by `agsoc video check` and is the artifact the human
adjudicates.

```json
{
  "episode": "2026-08-14",
  "checked_at": "2026-08-14T09:12:04+01:00",
  "corpus_sha": "…",
  "claims": [
    {
      "id": "c-014",
      "beat_index": 7,
      "beat_type": "kpis",
      "text": "Gemini 3.7 Flash costs $0.75 per 1M input tokens and $3.75 per 1M output tokens",
      "src": "venturebeat",
      "quote": "priced at $0.75 per million input tokens and $3.75 per million output",
      "quote_span": [4821, 4893],
      "atoms": [
        { "kind": "number", "value": "0.75" },
        { "kind": "number", "value": "3.75" },
        { "kind": "entity", "value": "Gemini 3.7 Flash" }
      ],
      "mechanical": {
        "verdict": "pass",
        "quote_found": true,
        "atoms_in_quote": ["0.75", "3.75"],
        "atoms_in_corpus": ["Gemini 3.7 Flash"],
        "atoms_missing": []
      },
      "adversarial": {
        "verdict": "supported",
        "attempted_refutation": "Checked whether the price applies to 3.7 Flash rather than 3.7 Pro; the source names Flash explicitly two sentences earlier. Checked whether pricing is promotional; no such qualifier appears.",
        "residual_risk": "Source does not state an effective date for the pricing."
      },
      "override": null
    }
  ]
}
```

### 8.2 Pass 1 — mechanical

Pure Python. No network, no LLM, milliseconds. Runs on every claim.

1. **Quote presence.** `quote` must occur in `sources/<src>.txt` after
   **comparison folding** (§8.2.1). Records the character span in the *original*
   text, which the UI uses to highlight.
2. **Numeric containment.** Every **claim number** (§8.2.2) the beat will
   *render* must be present in `quote` **by value, not by digit sequence.**

   This paragraph previously specified "normalised digit sequences". That was
   wrong, and it was wrong on this document's own worked example. Measured
   against the §7 `kpis` beat and its quote:

   ```
   quote: "priced at $0.75 per million input tokens and $3.75 per million output"
     1M    -> digits '1'      present? NO   (the source spells the magnitude)
     2.00  -> digits '2.00'   present? NO   (display formatting reaches the compare)
     0.75  -> digits '0.75'   present? yes
   ```

   And the rule's own purpose inverts: **`95B` against a source writing "95
   billion" fails**, which is exactly the case §8.2.2's unit-suffix rule was
   added to protect.

   **The comparison is therefore numeric.** Parse candidate numbers out of the
   folded quote using the same §8.2.2 rule; expand magnitude suffixes (`K M B T`)
   and spelled magnitudes (thousand, million, billion, trillion) on **both**
   sides; compare values, so trailing zeros and thousands separators cannot
   cause a refusal.

   This **strengthens** the guarantee rather than relaxing it: `95B` = 95e9 ≠
   9e9 = `9B`, a distinction a substring test cannot make at all. `0.75` matches
   `$0.75`; `75 cents` still does **not**.

#### 8.2.1 Comparison folding — required, and why it is safe

**Folding applies to the comparison only.** The corpus keeps its bytes, the
`quote` keeps its bytes, and `sha256` still covers the originals. Nothing on disk
is normalised — that would break the integrity guarantee §4 rests on.

Fold, in both the quote and the corpus, before matching:

| Class | From | To |
|---|---|---|
| Hyphens and dashes | U+2010, U+2011, U+2012, U+2013, U+2014, U+2015, U+2212 | `-` |
| Single quotes | U+2018, U+2019, U+201B | `'` |
| Double quotes | U+201C, U+201D, U+201F | `"` |
| Spaces | U+00A0, U+2007, U+2009, U+202F, and runs of whitespace | a single space |
| Ellipsis | U+2026 | `...` |

Then case-fold.

**This is not optional polish.** Verified against a real pasted brief: the source
wrote `V4‑Pro` with U+2011 NON-BREAKING HYPHEN while the beat wrote `V4-Pro` with
U+002D. Two of six beats were refused for quotes that were genuinely present.
An LLM authoring beats emits ASCII punctuation; real sources emit typographic
punctuation. Without folding, **the mechanical pass refuses correct claims
routinely** — and a gate that cries wolf is one operators learn to override,
which is D-040's failure mode arriving through the front door.

`unicodedata.normalize("NFKC", …)` **does not do this.** Measured, per class:

```
U+2011 NON-BREAKING HYPHEN  -> U+2010 HYPHEN      still not ASCII
U+2013 EN DASH              -> U+2013             unchanged
U+2014 EM DASH              -> U+2014             unchanged
U+2212 MINUS SIGN           -> U+2212             unchanged
U+00A0 NO-BREAK SPACE       -> U+0020 SPACE       fixed
U+202F NARROW NO-BREAK SPACE-> U+0020 SPACE       fixed
```

NFKC fixes the **space** family and leaves the **hyphen** family non-ASCII. The
real case is the trap: U+2011 *does* change under NFKC — to U+2010, another
non-ASCII hyphen — so `V4‑Pro` still fails to match `V4-Pro`, and a check written
as "is U+2011 gone after normalising?" answers **yes** while the comparison it
was standing in for still fails. Ask whether the fold reached ASCII, not whether
a particular codepoint disappeared. The fold must be an explicit table.

**Why folding cannot weaken the check:** it touches punctuation and whitespace
only. **No digit is ever folded**, so no fold can make a wrong number match a
right one. The risk is entirely one-directional — folding can only turn a false
refusal into a pass, never a false claim into a verified one.

#### 8.2.2 Claim numbers vs identifier digits

A number that is part of a **name** is not a figure being asserted. `V4-Pro`,
`Qwen3.8-Max` and `GPT-5.6` contain digits; none of them is a claim about
quantity, and demanding they appear in the `quote` produces false refusals.

**Rule:** split the beat's rendered text on whitespace. For each token, strip
surrounding punctuation, a leading currency symbol, and a trailing unit suffix
(`%`, `K`, `M`, `B`, `T`, `x`). If what remains is **only digits and separators**,
the token is a **claim number** and must appear in the quote. Otherwise it is an
identifier and is exempt.

| Token | After stripping | Verdict |
|---|---|---|
| `$1.32` | `1.32` | claim number |
| `1,100%` | `1,100` | claim number |
| `1M` | `1` | claim number |
| `95B` | `95` | claim number |
| `2.4` | `2.4` | claim number |
| `V4-Pro` | `V4-Pro` | identifier |
| `Qwen3.8-Max` | `Qwen3.8-Max` | identifier |
| `GPT-5.6` | `GPT-5.6` | identifier |

**The unit suffix matters and a naive "any letters means identifier" rule gets it
wrong.** That simpler rule was drafted first and exempted `1M` and `95B` — which
would let a beat claim `95B active` against a source saying `9B`. Caught by
running the rule against real text before writing any code.

This keeps the useful cases: in `Gemini 3.7 Flash`, the token `3.7` stands alone
and **is** checked — a beat saying 3.7 when the source says 3.6 is exactly the
error the pass exists to catch. Only digits *glued* to letters are exempt.

Both rules were found by running a real operator brief through the pipeline
before Phase 5 existed. Synthetic fixtures contain neither non-breaking hyphens
nor product names.
3. **Entity presence.** Every proper noun in the beat text must appear in `quote`
   or elsewhere in `sources/<src>.txt`.

Verdicts: `pass` · `fail` · `no_source` (a beat asserting something with no `src`).
Beats of type `title` and `signoff` are exempt. `custom` beats always land in
`manual` and require an explicit attestation, because their rendered content
cannot be statically extracted.

Deliberately strict: near-misses report as failures with the closest candidate
span attached, so the human sees *why* rather than a bare red mark.

### 8.3 Pass 2 — adversarial

One subagent per claim that survives pass 1. Each is given **only** the claim text
and the full corpus file — never the brief, never the draft rationale, never the
other claims. It is prompted to *refute*, and to default to `unsupported` when
uncertain.

It exists to catch what pass 1 structurally cannot:

- right number, wrong subject (the 3.7 Pro price attached to 3.7 Flash)
- stale date presented as current
- correlation in the source stated as causation in the beat
- a quote that is verbatim but torn from a qualifying context
- an entity that appears in the corpus but not in this relationship

Verdicts: `supported` · `unsupported` · `refuted`. A `residual_risk` note is
recorded even on `supported`, and surfaces in review — it is often the most useful
output of the whole pass.

MVP runs a single refuter per claim. If false-negative rate proves a problem, the
escalation is three refuters with majority vote; the schema already accommodates
an array.

### 8.4 The gate

`agsoc video approve` refuses while any claim is `fail`, `refuted`, `unsupported`,
`no_source`, or an unattested `manual`.

The only way past is an explicit override written into `script.yaml`:

```yaml
  - type: statement
    text: "The rollout is widely expected to slip."
    src: reuters
    claim_override:
      reason: "Framed as expectation, not fact; 'widely expected' is my read of
               three sourced analyst quotes, not a claim the article makes."
      by: "Ali Abdukarim"
```

An override is a visible diff in a file you commit — never a UI checkbox, never a
CLI flag. That asymmetry is the point: passing verification is automatic, and
bypassing it costs you a written sentence with your name on it.

---

## 9. Multi-format rendering

A format is a declared context, not a stylesheet fork:

```js
vertical = { w:1080, h:1920, safeTop:400, safeBottom:1580, measure:'narrow', scale:1.00 }
wide     = { w:1920, h:1080, safeTop:200, safeBottom: 900, measure:'wide',   scale:0.62 }
```

**Both safe bands were corrected on 2026-08-18 against the shipped engine.**
Vertical's `430…1560` was never what the engine drew — the stage has always been
`400…1580`, and that stage is pinned by 51 byte-identical probe frames of the two
committed episodes, so the spec was the thing that was wrong. Wide's `120…960`
collides with the chrome; `200…900` is derived so both formats have near-equal
room in layout units, which is what makes one script legitimately render as two.
The arithmetic lives in `plan.py::FORMATS`.

Each beat type implements layout per `measure`. The differences are real but few:

| Beat | vertical | wide |
|---|---|---|
| `statement` | 96–108px, 3–4 lines | smaller scale, wider measure, 2 lines |
| `kpis` | stacked column | single row |
| `list` | full-width rows | two columns above four items |
| `jumpChart` | vertical track | horizontal track |
| chrome | progress bar bottom, brand top-left | progress bar bottom, chrome inset to margins |

**The invariant: format changes layout, never timing.** `__seek(t)` stays pure and
both formats are frame-identical in time. Consequences worth stating — pacing is
verified once and holds for every format; `claims.json` is format-independent; and
a probe frame at `t=42.9` is directly comparable across formats.

```sh
agsoc video render 2026-08-14                        # every enabled format
agsoc video render 2026-08-14 --format wide          # one
agsoc video render 2026-08-14 --format wide --replace  # …overwriting out/
agsoc video probe  2026-08-14 --at 42.9 --format wide
```

`[formats] enabled` in `series.toml` is the list the first form renders, in the
order it declares. A format the engine supports but the series has not enabled is
refused by name — a different refusal from an unsupported format, because the two
send an operator to different files. A format already in `out/` is kept, and the
screen says so; `--replace` is how an operator spends a render they already have.

---

## 10. Status machine

Reuses the existing `Status` enum and adds two states. Text variants never enter
them; a second transition table keyed by kind keeps the two lifecycles honest.

```
draft ──→ in_review ──→ approved ──→ rendering ──→ rendered   (end of the MVP)
             ↑              │            │              │
             └──────────────┘            │              └──→ rendering  (§9: a
                                         │                    second format)
                                         └──→ failed ──→ rendering   (retry)
```

**`rendered` is where the MVP ends, and it is not a dead end.** Its only outgoing
edge is back to `rendering`, and that edge exists for §9: the formats of one
episode are rendered minutes or days apart, `render <ep> --format wide` on an
already-rendered episode is a documented command, and it was refused as a
terminal-state violation until 2026-08-19. A second format is the same story
producing a second artifact from the same signed bytes — not lifecycle progress,
which is why the only way out of `rendered` comes back to it.

The three gates are re-asked in full on every render, so the second format is
reached the same way the first was. **What protects an artifact already on disk
is not the status machine**: it is that a format whose file exists in `out/` is
never re-rendered without `--replace`. `rendered` being terminal never protected
it — `--restart` and a `failed` retry both walk around a status — and it forbade
the one operation §9 promises.

**Publishing is still unreachable.** An earlier draft of this spec drew
`rendered → published`, anticipating the staged video-publishing work. That edge
was cut on 2026-08-16 (decision D-006) because it was reachable but never
exercised, and it made `failed` ambiguous: with `failed → rendering` as the only
recovery edge, a *publish* failure could only be recovered by re-running the
expensive render of an artifact already sitting on disk. A state machine whose
only edge out of a state is the wrong one is worse than a state machine that
refuses to model the state at all. That cut stands; `rendered` having *no*
outgoing edge at all was its consequence, not its purpose.

When video publishing lands, this table gains `rendered → publishing` **and**
`failed → publishing` together, so recovery matches what actually failed.
`publishing` and `published` stay in `VIDEO_TRANSITIONS` as unreachable empty
sets purely so the table remains total.

- Only the CLI moves status. The agent writes `status: in_review` and stops.
- `approved → rendering` is gated on `claims.json` being clean (§8.4).
- Editing an approved script does **not** revoke approval automatically — the same
  per-status-not-per-content caveat the text pipeline already has. Mitigation:
  `approve` records `script_sha256`, and `render` refuses if the script has changed
  since approval, naming the drift. This is stricter than the text side and
  deliberately so, because a render is expensive and a video is harder to retract.

---

## 11. CLI surface

```sh
agsoc series new <slug>                        scaffold series.toml + coverage.json
agsoc series list

agsoc video new <date|slug> [--series S]       create the episode directory
agsoc video ingest <ep> [--research "query"]   search + fetch → sources/ corpus
                        [--paste FILE]         pasted text → _pasted.txt
                        [--from-source ID]     pull in an existing agsoc source
                        [--corroborate]        web-check a pasted digest (§3, #4)

#   → agent (skill: storyboard) writes script.yaml, stops at in_review

agsoc video check   <ep>                       two-pass verification → claims.json
agsoc video review  <ep>                       script, runtime estimate, verdicts,
                                               writes derived `pace`
agsoc video approve <ep>                       THE GATE — refuses on open claims
agsoc video render  <ep> [--format F]          blocked unless approved & unchanged
agsoc video probe   <ep> [--at T] [--format F] one frame per beat, or one frame

agsoc coverage check <terms…>                  has this story been told before?
agsoc coverage add   <ep>                      record stories after render
```

`agsoc video ingest --corroborate` is the opt-in escalation for pasted input:
searches the web for each claim in the paste, and flags contradictions. Without
it, the paste is ground truth and the video simply may not exceed it.

---

## 12. UI surface — the review console

**Read this section before mocking anything.**

The CLI runs the pipeline. The UI exists for the one step where a graphical
surface genuinely beats a terminal: **adjudicating claims against source text
while scrubbing a live preview.** It is a review-and-approve console, not a
control panel and not an editor.

### 12.1 Design brief for the mockup

- **User:** one expert operator, on their own machine, reviewing a script they did
  not write, under time pressure, about to attach their name to it.
- **Register:** a professional review instrument. Dense, quiet, keyboard-first.
  Think code review tool or a newsroom rundown — not a consumer creator app, not a
  dashboard with vanity metrics.
- **Do not** design a timeline editor, an asset browser, a template gallery, an
  onboarding flow, or an AI chat panel. None are in this product.
- **The tool's UI is not the video's design system.** The Brief's palette
  (`#F2F5F8` / `#0B1B2B` / `#2E6BFF`) belongs to the *rendered video*. The console
  needs its own neutral chrome so the preview reads as content, not as page
  background. Both light and dark.
- **The emotional target:** the operator should feel they *caught* something. The
  screen is at its best when it makes a bad claim impossible to skim past.

### 12.2 Screens

**A · Series home**
The set of series and each one's state. Per series: name, cadence, last episode
and its status, next episode due, count of episodes shipped. Primary action:
open the current episode. Secondary: new episode, series settings.
*States:* no series yet (scaffolding prompt); series with no episodes.

**B · Episode list**
Reverse-chronological episodes within a series, each a row: date, headline,
status pill, runtime, formats rendered, claim summary (`14 verified · 1 override`).
This is also the memory of the series — it should be pleasant to scroll back
through.

**C · Episode review — the primary screen**
Three regions, and the relationship between them is the whole design problem:

1. **Beat list** (left) — ordered beats grouped by act. Each shows type, a content
   excerpt, hold duration, source tag, and a claim status marker. Selecting a beat
   drives the other two regions.
2. **Preview** (centre) — the live `scene.html` at the selected beat, with a scrub
   bar across the whole episode, a format toggle (vertical / wide), and a running
   total against the series' `target_sec`. Scrubbing selects the beat under the
   playhead. This is the actual render engine in an iframe, not a mock.
3. **Claims panel** (right) — for the selected beat: claim text, both verdicts,
   and **the source excerpt with the supporting quote highlighted in place**. That
   highlight is the single most important element in the product; design the
   screen around it. Include `residual_risk` even when the verdict is `supported`.

*Consider:* vertical preview is 9:16 and tall; wide is 16:9 and short. The layout
must not collapse when the format toggles. This is worth two mockups.

**D · Claim adjudication (focused)**
A full-width mode for working through open claims one at a time — the state the
operator is in when `check` came back with five failures. Per claim: what was
asserted, what the source says, why each pass ruled as it did, near-miss
candidates for mechanical failures, and the refuter's reasoning for adversarial
ones. Actions: jump to beat, edit script, or write an override.

**Override deserves friction.** It requires a typed reason and is presented as
authoring an on-the-record statement, not clicking "accept". Show it will land in
the file as a diff. This is a case where the UI should feel slightly heavier than
necessary.

**E · Approve**
The gate. Two states worth mocking as a pair:
- *Blocked* — the open claims, why, and no path forward but resolving them. It
  must be obvious the button is unavailable because of specific facts, not because
  something is loading.
- *Clear* — a final summary (runtime, beats, claims verified, overrides written,
  formats to render, sources cited) and a deliberate confirm.

**F · Render**
Progress per format (frames rendered, encoding, done), then the outputs: poster,
file sizes, runtimes, a play affordance, and reveal-in-folder. Rendering takes
minutes, so this screen must be legible from across a room and survive being
navigated away from and back.
*States:* queued, rendering (per-format progress), encoding, complete, failed with
log excerpt.

**G · Coverage ledger**
Search across everything the series has covered: story, date, angle, whether it
was an update. Used *before* writing an episode. Entry point: a search field that
answers "have I said this already?" — with an honest empty state, since a miss is
the common and desirable answer.

**H · Series settings**
Form over `series.toml`: identity, palette with live swatches, type scale,
act structure, target runtime, enabled formats. Every change should preview
against a real beat rather than an abstract swatch grid.

### 12.3 States the mockups must cover

Beyond the happy path — these are where the product either earns trust or loses it:

- Claim **failed mechanically** (number absent from source) vs. **refuted
  adversarially** (number present, subject wrong). These are different problems and
  should not look identical.
- A `no_source` beat — an assertion with nothing behind it at all.
- A `custom` beat awaiting manual attestation.
- **Script drift**: approved, then edited, render now refusing (§10).
- Runtime over tolerance — 138s against a 120s ± 8s target.
- Empty: new series, no episodes; ingest run but no script yet.
- Corpus fetch partially failed — three sources retrieved, one 403.

---

## 13. Agent skills

Added alongside the existing `capture` / `fanout` / `repurpose`:

**`storyboard`** — brief + corpus + `series.toml` + `voice.md` → `script.yaml`.
Hard rules, in the style of `fanout`:
- NEVER run `approve` or `render`. Work ends at `status: in_review`.
- ALWAYS run `agsoc coverage check` before writing. A hit means skip it, or run it
  as an explicit update with the same `id`, `update: true`, and `updateOf`.
- EVERY beat that asserts anything carries `src` and a verbatim `quote`. A number
  that is not inside its beat's `quote` must not be written.
- Never invent a figure. If the source publishes direction rather than magnitude,
  use `dumbbell` with a footnote saying so.

**`verify`** — orchestrates pass 2: one refuter subagent per claim, each blind to
the drafting context, each defaulting to `unsupported` under uncertainty.

---

## 14. Testing

**Python** (pytest, as today; `respx` for HTTP):
- Mechanical verifier is pure functions over strings — the densest test target in
  the system. Quote normalisation, numeric containment, near-miss reporting.
- Claim extraction from `script.yaml` per beat type.
- Status transitions, the approve gate, and script-drift detection.
- Ingest with a stubbed network.

**Node engine:**
- *Determinism test:* render `t=42.9` twice, assert byte-identical PNG. This
  guards the property everything else rests on.
- *Golden frames:* one per beat type × both formats, compared with a small pixel
  tolerance.
- *Safe-area test:* no rendered content outside the format's safe box.
- *Timing test:* `__seek(t)` output is independent of the order `t` is called in —
  catches accidental state accumulation.

No network in any test.

---

## 15. Risks

| Risk | Mitigation |
|---|---|
| Mechanical pass is too strict; operators override reflexively and the gate becomes theatre | Near-miss reporting so failures are diagnosable; track override rate as a health signal — a high rate means the checker is wrong, not the operator |
| Adversarial pass returns confident nonsense | Refuter sees only claim + corpus, never the draft's reasoning; defaults to `unsupported`; `residual_risk` surfaces doubt rather than burying it |
| Declarative beats prove too rigid, everything becomes `custom` | Track the `custom` ratio. Above ~15% of beats, the type catalogue is wrong and needs extending — that's a signal, not a failure |
| 16:9 layouts quietly degrade because vertical is what gets watched | Golden-frame tests cover both; the format toggle sits in the primary review screen rather than behind a menu |
| Corpus files drift from what was actually checked | `claims.json` records `corpus_sha`; a changed corpus invalidates the check |

---

## 16. Open questions

1. **Corroboration depth.** When `--corroborate` contradicts a pasted digest, does
   it block, or annotate the claim and let the operator adjudicate? Leaning
   annotate, since the operator vouched for the paste.
2. **Coverage ledger scope.** Currently per-series. Should an operator running two
   series in adjacent fields share one ledger? Deferred — per-series until it hurts.
3. **`pace` authority.** Derived from `target_sec` at review time. If a beat's
   entrance animation exceeds its scaled hold, the engine must clamp rather than
   truncate. Needs a defined minimum hold per beat type.

---

## 17. Implementation staging

Rough order; the real plan comes from the writing-plans skill.

1. `series.toml` + episode scaffolding + the video status machine
2. Ingest: research, paste, from-source → corpus + `_manifest.json`
3. `script.yaml` schema, parser, runtime estimation
4. Engine: declarative beat renderer over existing primitives, vertical only
5. Mechanical verifier + `claims.json`
6. `storyboard` skill
7. Approve gate + script-drift detection
8. Render pipeline through the declarative script; retire the hand-written path
9. Adversarial pass + `verify` skill
10. Wide format: layout strategies, golden frames
11. Coverage ledger relocation and CLI
12. Review console (§12)

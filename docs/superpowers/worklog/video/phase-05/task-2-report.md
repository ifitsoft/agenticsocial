# Task 2 Report — the mechanical pass and the ledger

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier`
**Commits:** `20186dc` (tests) · `030dfff` (implementation) · `311c1c8` (the
sweep's findings) · `1aa295e` + `1bb2f8f` (Step 6's finding: tests, then fix) ·
`b47136c` (unused imports)
**Suite:** 1471 passed (baseline 1398 + 73 new), 12.0s, no network.
**Mutation score: 37/37 killed** — the brief's fifteen and twenty-two of my own.

---

## 1. What I implemented

`src/agenticsocial/video/verify.py` (743 lines) and
`tests/test_video_verify.py` (73 tests).

| Piece | Spec | Notes |
|---|---|---|
| `fold_spans(text)` | §8.2.1 | `claims.fold`'s output **plus** a map from every folded character back to the original bytes that produced it. |
| `quote_span` / `closest_span` | §8.2.1 | presence, in the **original** document's coordinates; near-miss reported as the longest matching prefix *or suffix*. |
| `claim_values` / `quote_values` | §8.2 pt 2 | the value comparison, below. |
| `shown_problems(beat)` | D-094 | `shown`'s digits against the row's own `before`/`after`. No corpus. |
| `check_claim(claim, document, *, beat)` | §8.2 | one verdict: `pass` · `fail` · `no_source` · `manual`. |
| `verify_episode(episode)` | §8.1 | loads script and corpus itself, returns the ledger. |
| `write_ledger` / `read_ledger` / `stale_reason` | §8.1, R3 | atomic, stable, and the invalidation R3 asks for as a function rather than a recorded string. |
| `corpus_sha(documents)` | §8.1 | over exactly the documents read. |

### The value comparison, specifically

Both sides are parsed into `Decimal`. `claims.claim_number` stays the authority
on *whether* a token is a claim number — reused, never re-derived — and what it
throws away is recovered: it returns `"1"` for `1M` and `"95"` for `95B`, so a
check built on its output alone cannot tell one million from one. The suffix
(`K M B T`, `%`/`x` = ×1) and the following word (thousand/million/billion/
trillion, singular and plural) supply the exponent.

**Three asymmetries, each deliberate and each pinned:**

1. **The quote side emits both readings of "95 billion"** — 95e9 and the numeral
   95. The claim side emits only the expanded value. A `jumpChart` row reaches
   the frame as geometry and is extracted as a bare `95`, while the source
   writes `95B`; without the wider quote side every chart drawn from a
   suffix-using source is refused. Making the *claim* side lenient too would let
   `95B` pass against a source saying "95 units", so it is not symmetric.
2. **A bare magnitude word is worth its own magnitude.** "per million" is "per
   1 million" — English elides the coefficient. Without this the spec's own §7
   example is refused, which is the whole of D-098.
3. **Numbers gate; entities advise.** §6 below, with the measurement.

An unparseable display (`1.2.3` satisfies §8.2.2's "only digits and separators"
and is not a number) is treated as unverifiable and **fails**. Guessing is the
one direction this module must not err in.

**A divergence guard, in the D-096 spirit.** Because the numeric check walks
`text` a second time, the two walks can disagree. If a number atom in the record
is not produced by re-reading the text, `check_claim` **raises** rather than
checking a shorter list — figures checked that nobody extracted, or extracted
that nobody checks, is the exact failure this phase exists to prevent.

---

## 2. Proof the value comparison is stricter, not looser

The case a substring test **cannot make at all**, because `9` is a substring of
`95`:

```
beat renders : 9B          source says : "roughly 95B active parameters"
  substring  : "9" is in "95B"                        -> ACCEPTED (wrong)
  by value   : 9e9 not in {95e9, 95}                  -> REFUSED  (right)
```

Pinned as `test_a_different_value_still_fails_however_it_is_spelled[9B-vs-95B]`,
with two more of the same shape in the same parametrisation: `0.75` against
"75 cents" (`75` is a substring) and `0` against "the score moved to 10" (`0` is
a substring). All three are accepted by digit-sequence matching and refused by
value.

What stops causing refusals is notation only — trailing zeros, thousands
separators, and the magnitude a source spells while a frame abbreviates. Eleven
rows of that in
`test_a_magnitude_written_differently_on_the_two_sides_passes`, each chosen so a
substring implementation answers **no**.

---

## 3. TDD evidence and the mutation score

Tests first, verified failing, committed alone at `20186dc`:

```
tests/test_video_verify.py:33: in <module>
    from agenticsocial.video import verify as V
E   ImportError: cannot import name 'verify' from 'agenticsocial.video'
```

Then `030dfff`. First green run: `64 passed in 3.10s`, with one defect of my
own — a span assertion that compared the original slice to the quote *byte for
byte* in a case where the source legitimately wrote a run of whitespace. Fixed
in the assertion (fold both sides), not in the code.

### Mutation harness

One source edit at a time against `verify.py` (and `claims.py` for M15),
`pytest -x -q` on `test_video_verify.py` + `test_video_claims.py`, source
restored between runs. `PYTHONDONTWRITEBYTECODE=1` — **the first run without it
reported two false survivors**: with the suite down to 0.17s, consecutive
mutants land inside one mtime second and CPython reuses a stale `.pyc`. Worth
recording: a mutation harness that gets faster can start lying.

### The brief's fifteen

| # | Mutant | Result | Killed by |
|---|---|---|---|
| M1 | substring comparison instead of value comparison | killed | `…passes[1M-vs-separators]`, `[1M-vs-spelled]`, `[trailing-zeros]` |
| M2 | value comparison loose enough that `9B` matches `95B` | killed | `…still_fails[9B-vs-95B]` — *the same mutant*, from the other side |
| M3 | `2.00` vs `2` refused (exact string compare of the values) | killed | `…passes[trailing-zeros]` |
| M4 | `75 cents` accepted for `0.75` (digits-only normalisation) | killed | `…still_fails[cents]` |
| M5 | span computed on folded text, returned as an original offset | killed | `…indexes_the_original_bytes…` ×4, and the on-disk `…recorded_span_indexes_the_source_document_on_disk` |
| M6 | folding skipped on the corpus side only | killed | `test_folding_is_applied_to_the_corpus_side_too` |
| M7 | `no_source` collapsed into `fail` | killed | `test_a_beat_with_no_src_is_no_source_and_that_is_not_fail` |
| M8 | `custom` can reach `pass` | killed | `test_a_custom_beat_lands_manual_with_its_attestation_and_never_passes` |
| M9 | `attest` not recorded | killed | same |
| M10 | `corpus_sha` absent, or not covering the documents read | killed | `test_corpus_sha_covers_the_documents_actually_read` |
| M11 | `claims.json` re-ordered or re-timestamped on an unchanged re-run | killed | `test_re_running_an_unchanged_check_rewrites_nothing`, `test_claim_order_follows_the_beats` |
| M12 | `shown` digits unchecked | killed | `test_a_shown_cell_stating_a_figure_the_bar_does_not_draw_fails` |
| M13 | a `shown` with no digits refused | killed | `test_a_shown_cell_carrying_no_digits_is_fine` |
| M14 | an entity miss produces the same verdict as a number miss | killed | `test_a_missing_number_and_a_missing_entity_are_not_the_same_outcome` |
| M15 | `title`/`signoff` verified rather than exempt | killed | `test_title_and_signoff_are_exempt_and_produce_no_verdict_at_all` |

M1 and M2 are **one source edit** — replacing the value test with
`display in fold(claim.quote)`. That is not a shortcut: the brief's own table
says M1 is noticed by R1's negative half and M2 by R1, and the run confirms both
halves fire. A substring implementation is simultaneously the false-refusal
mutant and the false-acceptance one, which is the cleanest possible statement of
why D-098 is a strengthening.

### My own sweep — 22 more

Killed: bare magnitude word contributes nothing · quote side omits the bare
coefficient · claim side admits the bare coefficient · no closest span on a near
miss · closest span searches prefixes only · entity presence looks in the quote
only · entity presence not case-folded · the record/text divergence guard skipped
instead of raised · an empty quote treated as a citation · a dangling `src`
fails instead of `no_source` · the strict `shown` rule (every figure must be a
row value) · `before` demanded of a single-figure `shown` · a falsy row value
skipped by truthiness · a jumpChart claim checked without its beat · ledger
ordered by verdict · ledger written with `write_text` · the fold not stripping
its ends · `shown` problems not reaching the verdict · a spelled magnitude
consumed but not expanded · the ledger emitting tuples and `Decimal`s · the edge
elision not trimmed · an elision anywhere becoming a wildcard · a quote that is
only an elision treated as found.

**Three survived the first run, and all three were real gaps in my tests**
(`311c1c8`, fixtures only — `verify.py` untouched):

- **closest span, prefixes only.** No test covered a quote that diverges at its
  *first* word — the common paraphrased-opening case, and precisely where a
  prefix search returns nothing at all and the operator gets the bare red mark
  §8.2 exists to avoid.
- **a jumpChart claim checked without its beat.** `beat` is optional so the
  prose cases read cleanly, and nothing pinned the refusal that makes that
  optionality safe.
- **the quote side's bare coefficient.** The asymmetry that lets a chart row's
  `before: 95` match a source writing `95B` — deliberate, and untested.

The end-strip mutant also needed a fixture change: my fold-equality sample had
no leading or trailing whitespace, so the strip was unobservable.

---

## 4. Step 6 — the false-refusal rate, as a number

Full output: `step6-final.txt`, reproduced here. Beats for (b) were written from
the brief the way a storyboard agent would write them, **before** running the
checker.

### (a) The spec's §7 example script, verbatim

```
=== (a) spec §7 example script, VERBATIM ===
c-001 beat  0 statement  no_source   <-- REFUSED BY THE GATE
        reason : the beat cites no `src`
c-003 beat  2 statement  pass
c-004 beat  3 list       pass
c-005 beat  4 kpis       fail        <-- REFUSED BY THE GATE
        reason : the quote does not contain 3.6 by value
        numbers missing : ['3.6']
c-006 beat  5 custom     manual
claims: 5   refused: 2   false-refusal rate: 2/5 = 40%
```

Note what is **no longer** refused: `c-005`'s `1M` and `2.00`-class atoms pass —
D-098's amendment works on the example that motivated it — and `c-004` passes
only after this task's own fix (below).

**The two refusals, and which side is wrong:**

1. **`c-001` — the beat.** "Google shipped its main agentic model — and halved
   the price." carries no `src`. That is a claim about the world with no
   citation; the verdict is right and the beat is an illustrative snippet, not a
   shippable cold-open. I considered exempting srcless prose beats and rejected
   it: `claims.py`'s own docstring says a missing source is Task 2's `no_source`
   and that dropping it "would turn that refusal into a silent pass, which is
   the single outcome this phase exists to prevent". Followed the code.
2. **`c-005` — the beat.** The kicker "And it costs half of what 3.6 Flash did"
   asserts a figure the cited quote does not cover. This is Task 1's §7.1
   finding surviving contact with the numeric comparison, and it is real: a
   beat's citation must cover its *framing* as well as its payload. The source
   in this fixture does say "roughly half what 3.6 Flash cost" — the operator's
   fix is one word wider in `quote:`, not an override.

With those two citations written as an operator would have to write them:

```
=== (a2) same beats, with the two citations an operator would have to write ===
c-001 pass   c-003 pass   c-004 pass   c-005 pass   c-006 manual
claims: 5   refused: 0   false-refusal rate: 0/5 = 0%
```

### The checker defect Step 6 found, and fixed

`c-004` **was** refused, and the checker was wrong. The spec's `list` beat
quotes `"…available today in the Gemini API and AI Studio, …"`. §8.2.1 folds
U+2026 to `...`, and a literal search then demands three full stops the source
never wrote:

```
quote folds to : '...available today in the gemini api and ai studio, antigra…
in source?     : False
without the leading elision marker? True
```

A leading `…` is an editorial mark meaning "the sentence starts earlier" — the
single most common way a human shortens a citation, and a **guaranteed** refusal
on every quote that uses it. Fixed in `1bb2f8f`, tests first in `1aa295e`:

- trimmed at the **edges** only, and only runs of **two or more** dots (a single
  trailing full stop stays — the source has it too, and stripping it would
  loosen "verbatim" for nothing);
- an **internal** elision stays literal. Treating it as a wildcard would let a
  beat quote `"prices … fell"` against a source saying prices rose before they
  fell. Pinned with the discriminating fixture, not the illustrative one;
- a quote that is *only* an elision is not found — otherwise the trim
  manufactures the vacuous pass;
- same one-directional argument as §8.2.1's own: no digit is touched, so it can
  turn a false refusal into a pass and never a false claim into a verified one.

### (b) The operator's real brief

Nine beats over all four acts, `workspace/inbox/2026-08-17-ai-brief.md` as the
corpus, U+2011 non-breaking hyphens throughout:

```
=== (b) beats from the operator's real brief ===
c-001 beat  0 statement  pass
c-003 beat  2 statement  pass
c-004 beat  3 kpis       pass
c-005 beat  4 body       pass
c-006 beat  5 list       pass
c-007 beat  6 statement  pass
c-008 beat  7 kpis       pass
c-009 beat  8 jumpChart  fail        <-- REFUSED BY THE GATE
        reason : the quote does not contain 0.11, 0.33 by value
        numbers missing : ['0.11', '0.33']
claims: 8   refused: 1   false-refusal rate: 1/8 = 12%
```

**The one refusal is a true refusal, and it is mine.** I drew a before/after
price chart and invented the "before" figures: the brief says DeepSeek's new
prices are "a clear upward correction after undercutting the market for months"
and **never publishes the old prices**. The checker caught two fabricated
numbers on a chart I had written without noticing I had fabricated them. That is
the sentence this phase exists to make true, arriving on the first real run.

Dropping the beat that cannot be sourced:

```
=== (b2) same, with the fabricated chart dropped ===
claims: 7   refused: 0   false-refusal rate: 0/7 = 0%
```

**Measured false-refusal rate: 0/7 on the real brief, 0/5 on the spec's §7
example.** Every refusal in the raw runs was the beat, not the checker — after
the one place where it *was* the checker, which is fixed.

The pieces that had to work for that zero, each a live generator before this
task: `V4‑Pro` (U+2011) against `V4-Pro`; `2.4T` against "2.4 trillion"; `95B`
against `95B`; `$1.32`/`$3.96` against a source writing them with a slash
between; `1M` labels against "per 1M tokens"; `1,100%`; `98%` and `12` from a
kpis card; and the whole quote folded out of a multi-line YAML scalar.

---

## 5. Files changed

| File | Commits |
|---|---|
| `src/agenticsocial/video/verify.py` (new, 743 lines) | `030dfff`, `1bb2f8f`, `b47136c` |
| `tests/test_video_verify.py` (new, 73 tests) | `20186dc`, `311c1c8`, `1aa295e` |

Nothing else is touched. `claims.py`, `script.py` and `cli.py` are unmodified —
`agsoc video check` is Task 3.

`git status --porcelain -- src tests` is clean.

**Commit count.** The brief prescribes one commit per step; there are six. Steps
2–4 are one file and one design, and splitting them after the fact would be
theatre. The extra two are products of the work rather than of the plan: the
sweep's fixture gaps (`311c1c8`) and Step 6's checker defect, which is a
test-then-fix pair because it is a behaviour change and deserved the same
ordering as everything else.

---

## 6. Issues and concerns

### 6.1 What can still ship a wrong number — Phase 9's specification

Every one of these passes pass 1 today.

1. **Right number, wrong subject.** `text: "Qwen3.8-27B is a 27.8B dense model"`
   with `quote: "at roughly 2.4 trillion parameters with about 95B active"` and
   `text` figures that happen to appear elsewhere in the quote. Concretely, from
   the real brief: a beat rendering `$1.32 / $3.96` attributed to **Qwen3.8-Max**
   rather than V4-Pro passes, because the quote contains both figures and the
   entity check is advisory. **This is the highest-value pass-2 case and the
   cheapest to construct.**
2. **Aggregation across two quotes.** A beat rendering `2.4T` and `95B` and
   `27.8B` together, cited to one quote containing all three, states a
   relationship the source does not.
3. **`scale`.** `jumpChart` bars on `scale: 100` where the published range is
   0–70 shifts every bar with no wrong digit anywhere. D-085 #2, untouched: the
   axis maximum is the operator's and appears nowhere in any quote.
4. **The `gain` segment**, a computed delta rendered as a length. D-085 #3.
5. **A figure glued to a letter.** `n=159 cases` is an identifier under §8.2.2,
   so a sample size is never checked. Likewise `1.5bn` — outside the `%KMBTx`
   suffix set, and my magnitude words are a closed list that does not contain
   `bn`.
6. **A magnitude word the beat asserts that the source only mentions.** My quote
   side treats a bare "million" as 1e6, so a beat rendering `1M users` against a
   source that says "per million tokens" passes on that atom. Bounded — it can
   only ever admit the four values 1e3/1e6/1e9/1e12 — and it is the price of the
   spec's §7 example verifying at all. Named here because it is the only place I
   knowingly widened what passes.
7. **Prose with no figures.** A `body` beat of fluent, sourced-looking prose
   whose quote is genuinely present but whose *claim* is a paraphrase the source
   does not support. Pass 1 checks that the quote exists, not that the beat
   follows from it.
8. **Stale dates.** `2026` and `14` are claim numbers (D-092/D-097), so a date
   in the beat must be in the quote — but a date that is *correct and old*,
   presented as current, is invisible. §8.3 names this explicitly.
9. **`shown` with a stray figure the quote happens to contain.** My row check is
   containment, so `shown: "34.4 &rarr; 43.6 (was 999)"` passes if 999 is
   anywhere in the quote. See 6.3.

### 6.2 Entity presence: the decision, and its error rate both ways

**Decision: entity misses are recorded, not gated.** `entities_missing` is
populated, the verdict stays `pass`, and §8.2 step 3 is therefore **not
implemented as a gate**. I would rather say that than ship a check that looks
stronger than it is.

Measured on the real brief's nine beats:

```
entity atoms: 20   not found anywhere in the source: 7 (35%)
refusals if entity misses were gated: 5/8 = 62%   (actual: 1/8)
```

The seven misses, in full: `New V4-Pro`, `Alibaba Qwen3.8-Max`, `2.4T`, `Also`,
`Tongyi Lab Qwen3.8-27B`, `Z.ai GLM-5.3`, `USD`. **Not one of them is a real
entity error.** Five are Task 1's glued runs (a kicker word fused to the
following name, or a lab name fused to its product), `2.4T` is a figure the
orthographic rule reads as a name, and `USD` is a footnote word. Every one is a
string no corpus contains *by construction*, so gating them would refuse a beat
for the tokeniser's spelling.

- **False-refusal direction: 35% of atoms, 62% of beats.** That is D-040's
  failure mode with a number on it — five overrides on a nine-beat episode, on
  day one, none of them about the world.
- **False-acceptance direction: unbounded, and I am not hiding it.** A wrongly
  attributed entity is exactly pass 2's first case (6.1 #1), and Task 1 measured
  four lowercase-styled product names in this brief (`cline`, `claude-context`,
  `context-mode`, `ml-intern`) that an orthographic rule cannot see at all.

The check that *is* gated is the one whose error rate is near zero: a wrong
number is fabrication and a missed proper noun is our tokeniser, and the two do
not belong on the same verdict.

**If entity gating is wanted before Phase 9**, the cheapest route is Task 1's
own suggestion — break entity runs on commas, dashes and em dashes — which
would close five of these seven. I did not do it: it is a change to `claims.py`,
Task 1's file, and it needs its own measurement rather than a drive-by.

### 6.3 The `shown` rule: containment, not equality — and what that costs

The plan asked for `shown`'s digits to agree with the row's `before`/`after`.
The obvious rule — *every* figure in the cell must be a row value — **refuses
D-085's own example of an honest divergence**: `before: 48.0` with
`shown: "48–49 → 65.3"` is the committed episode being accurate about a
published range.

So the rule is: **`after` must be present among the cell's figures, and `before`
too when the cell carries two or more.** The stray figures are not unverified —
every digit in `shown` is already a claim number checked against the quote by
§8.2 — so the two checks decompose the problem between them: the corpus check
asks *did anyone publish this number*, the row check asks *does the bar draw
it*.

Costs, both stated: `shown: "43.6 (n=159)"` is refused, because the check cannot
tell a sample size from a starting value; and a stray figure that *is* in the
quote passes the row check (6.1 #9). Both are pinned as tests so the next person
changing this sees what it was traded against.

### 6.4 Two conflicts, followed as the ground rules say

1. **`claim_override` is a mapping in §8.4 and a string in the code.** Spec §8.4
   writes `claim_override: {reason: …, by: …}`, but `script.py`'s shared-field
   loop validates *every* name in `SHARED_TEXT` — `claim_override` included —
   with `free_text`, so a mapping is refused at load with
   ``` `claim_override` must be a string ```. Followed the code: the override
   rides into the record as whatever string the operator wrote. **This needs a
   decision before Phase 7's gate reads it**, because §8.4's asymmetry ("a
   written sentence with your name on it") is weaker when the name is not a
   field. It is a two-line change in `script.py` and belongs to whoever owns the
   gate, not to this task.
2. **Step 6's "both must verify clean"** is not true of the §7 example verbatim,
   and §4 above says which side is wrong for each of the two refusals. One was
   the checker (fixed); one is the beat (no `src`); one is the beat (a citation
   that does not cover its own kicker).

§8.1's two example-record defects (`c-014` on `beat_index: 7`, and a `text` no
mechanical walk produces) are carried from Task 1 unchanged. I follow the field
shape; the record's `text` is the concatenation of what the card renders, and
Task 3 should not put it in front of an operator expecting prose.

### 6.5 The override rate I would expect in a month

**Roughly one override per two episodes — 2–3 a month on a daily series — and
almost all of them on `custom` and on editorial framing.** Reasoning from the
measurements rather than from feel:

- *Corpus-checkable beats: near zero.* 0/7 on a real brief with real
  typography. The generators that remain are notational and closed (§6.1 #5),
  not judgement calls.
- *Editorial kickers: the one to watch.* The spec's own §7 example fails on one
  ("And it costs half of what 3.6 Flash did"), and a kicker is where an operator
  writes the comparison that makes the story. It is not an override — it is a
  wider `quote:` — but it will *feel* like one at 6am, and the review console
  showing the near-miss span is what decides which way that goes. **Track it.**
- *`custom`: one per episode that uses one*, by design (D-088). It is an
  attestation rather than an override, so it does not touch the gate, but it
  will dominate the "things I had to write a sentence about" count and should
  not be confused with a refusal in whatever Task 3 reports.
- *Entity misses: zero, because they do not gate.* Had I gated them the answer
  would have been **five per episode**, and the gate would be theatre inside a
  fortnight.

The number worth watching is not the override count but its *shape*: overrides
concentrated on one beat type mean the checker is wrong about that type.
Overrides spread evenly mean the operator has stopped reading.

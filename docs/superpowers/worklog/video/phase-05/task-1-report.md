# Task 1 Report — claim extraction

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier`
**Commits:** `6949017` (tests) · `b7a1e9b` (implementation) · `9db7fa2` (the sweep's own findings)
**Suite:** 1398 passed (baseline 1312 + 86 new), 12.1s, no network.

---

## 1. What I implemented

`src/agenticsocial/video/claims.py`. Nothing in it reads a corpus, opens a
socket or writes a byte.

| Piece | Spec | Notes |
|---|---|---|
| `FOLD_TABLE` / `fold()` | §8.2.1 | explicit table, whitespace runs collapsed, ends stripped, then case-folded. Comparison only. |
| `claim_number(token)` | §8.2.2 | strip surrounding punctuation → leading currency → **trailing** unit suffix → digits-and-separators test. |
| `atoms(text)` | §8.2 | `number` atoms and `entity` atoms, deduplicated, first occurrence wins. |
| `beat_text(beat)` | §7.1 | what the beat renders, derived from the catalogue (§2 below). |
| `extract_claims(script)` | §8.1 | one `Claim` per non-exempt beat: `id`, `beat_index`, `beat_type`, `text`, `src`, `quote`, `atoms`, plus `manual`, `attest`, `override`. |

**Decisions that were mine, not the spec's:**

1. **Years and list ordinals stay claim numbers (D-092).** No shape or range
   exemption. Reasoning, both directions costed:
   - *Cost of exempting:* a stale date presented as current is a failure mode
     §8.3 names explicitly, and the year is the only part of it a mechanical
     pass can see at all. Exempting it hands the whole date class to pass 2.
   - *Cost of not exempting:* a beat rendering a date its quote does not contain
     is refused. Measured on the regression fixture, that cost is near zero —
     the brief's `2026` and `14` both come from "released August 14, 2026", and
     any quote covering that clause contains both.
   - *The deciding argument:* any "is this a year?" test is a range check on a
     bare integer. `2026` is a year in one beat and a GPU count in the next, and
     a rule that cannot tell them apart would exempt the figure as readily as
     the date. Pinned by
     `test_years_and_ordinals_are_claim_numbers_and_that_is_deliberate`.
2. **Unit suffixes are matched case-insensitively** (`95b` as well as `95B`).
   The spec writes `%KMBTx`. This strictly *widens* what gets checked, which is
   the direction D-071 says to err in — the naive rule's error was exempting
   `95B`, and `95b` is the same figure.
3. **`shown` is tag-stripped, not exempted** (D-081 asked for one or the other).
   `html.unescape` plus removing the two closed-vocabulary tags, so
   `<s>34.4</s> &rarr; 43.6` yields the atoms `34.4` and `43.6`.
4. **`jumpChart.before`/`after` are atoms** even though they reach the frame as
   geometry rather than glyphs. §7.2 is written about numbers, not about text.
5. **A kpi value is extracted as the glyphs the frame shows**, via script.py's
   own `_as_displayed` (imported, not re-derived). `value: 2, decimals: 2` is
   `2.00`. **This is a handoff to Task 2** — see §7.
6. **Entity atoms are orthographic** with a sentence-opening stoplist. §7 is
   honest about what that costs.
7. **`custom` claims carry an empty `text`.** `buildCustom` never draws the
   kicker, and scraping the `js` source would be extraction pretending.

---

## 2. How extraction is tied to the catalogue, and what that does not catch

`COLLECTORS` is keyed by the **checker function object** from
`script.BEAT_TYPES`, not by field name and not by a list:

```python
COLLECTORS = {script_mod.text: _string, script_mod.text_list: _strings,
              script_mod.kpi_items: _kpi_text, ..., script_mod.positive_number: None}
```

`beat_text` reads `script_mod.BEAT_TYPES` **at call time** and looks each field's
checker up. Consequences:

- a field added to §7.1 as `"tagline": text` is extracted the day it is added,
  with no edit here — pinned by
  `test_a_new_prose_field_is_extracted_without_touching_claims_py`, which grows
  the catalogue by monkeypatch and asserts the new field's figure appears;
- a field with a **new** checker raises `ClaimsError` naming the field. Loud,
  not skipped: silently skipped is indistinguishable from checked;
- a new **type** is refused until it lands in `EXTRACTED_TYPES`, `EXEMPT_TYPES`
  or `MANUAL_TYPES`, asserted both as a set identity against `BEAT_TYPES` and at
  runtime.

**The cross-check against the other answer.** `test_no_field_planbuild_renders_is_unknown_to_claims_py`
reads `engine/planbuild.js`, collects every `b.` / `r.` / `it.` property access
(27 names today), and asserts each is either in the derived `CLAIMED_FIELDS` or
in `IGNORED_FIELDS` with a written reason. `IGNORED_FIELDS` is prose, not a
bool, and a second test enforces that — D-093: a documented exception is not a
reviewed one, and the reason is what the next reader gets to argue with.

**What it does not catch, stated plainly:**

- a field **both** files know about that this module classifies **wrongly**. If
  I put `footnote` in `IGNORED_FIELDS` with a plausible sentence, both tests
  stay green. The enumeration is checked; the judgement is not.
- text the builders render from anywhere other than a `b.`/`r.`/`it.` property:
  the dumbbell's axis words (`lower`, `higher →`), the merged-marker legend
  entry (`both`), and the title/signoff cards' `META` (series name, episode
  date, byline). Those are the renderer's own words, none carry an authored
  figure, and the two card types are §8.2-exempt anyway — but a builder that
  starts printing a number of its own is invisible to this check.
- `plan.py`'s `act_label`, joined from `series.toml`. It reaches the chip; it is
  classified as ignored, and if a series ever puts a figure in an act label
  nothing here will see it.
- the regex is a regex. A builder written as `var f = b['foot'+'note']` is not
  matched — the test asserts `"shown" in read_by_js` as a canary so the regex
  silently matching nothing is a failure rather than a pass.

---

## 3. TDD evidence

Tests first, verified failing, committed alone at `6949017`:

```
tests/test_video_claims.py:28: in <module>
    from agenticsocial.video import claims as C
E   ImportError: cannot import name 'claims' from 'agenticsocial.video'
```

Then `b7a1e9b`. First green run of the new file: `83 passed in 1.95s` (one
fixture defect of my own on the first attempt — an unquoted `episode:` date in
the on-disk script, fixed in the fixture, not in the code).

The tests do not hard-code the prose-bearing fields either: they read them back
out of `BEAT_TYPES` and out of `planbuild.js`. The one literal the file keeps is
§8.2.1's fold table, retyped from the spec — reading it out of the
implementation would make every fold assertion a tautology (D-035).

---

## 4. Mutation score

**30 of 31 killed. The one survivor is equivalent, demonstrated below.**
Harness: one source edit at a time against `claims.py`, `pytest -x` on the new
test file, source restored between runs.

### The brief's thirteen

| # | Mutant | Result | Killed by |
|---|---|---|---|
| M1 | any token containing a letter is an identifier | killed | `test_the_claim_number_rule_from_the_spec_table[1M]`, `[95B]` |
| M2 | unit suffix stripped from the front as well | killed | `…[M1]`, `…[K9]` |
| M3 | `3.7` in `Gemini 3.7 Flash` exempted as part of the name | killed | `test_a_standalone_number_beside_a_product_name_is_still_checked` |
| M4 | first digit run of any token taken as a claim number (`V4-Pro` → `4`) | killed | `test_digits_glued_to_letters_are_never_claim_numbers` |
| M5 | fold table replaced by `NFKC` | killed | `test_every_codepoint_in_the_spec_table_folds_to_its_ascii_target[U+2013]` etc. |
| M6 | U+2011 dropped from the hyphen row | killed | same, `[U+2011]`, plus the real-brief test |
| M7 | a full-width digit added to the fold table | killed | `test_no_digit_is_anywhere_in_the_fold_table` |
| M8 | folding written into the record | killed | `test_the_record_carries_the_quote_bytes_unfolded` |
| M9a | a prose field omitted — `list` items | killed | `test_list_extracts_lead_and_every_item` |
| M9b | a prose field omitted — the kicker | killed | `test_statement_extracts_text_and_kicker` |
| M9c | a prose field omitted — `jumpChart` `before`/`after` | killed | `test_jumpchart_extracts_labels_shown_footnote_and_the_row_values` |
| M10 | `title`/`signoff` extracted | killed | `test_title_and_signoff_produce_no_claims` |
| M11 | `custom` extracted rather than manual | killed | `test_custom_is_manual_with_its_attestation_and_no_atoms` |
| M12a | claim id blank | killed | `test_every_record_names_its_beat_and_carries_a_unique_id` |
| M12b | beat index taken from the record's position | killed | `test_a_claimable_beat_keeps_its_index_when_an_exempt_beat_precedes_it` |
| M13 | a beat with no `src` produces no record | killed | `test_a_beat_with_no_src_still_produces_a_record` |

M8's disk half deserves a note: `claims.py` receives no path and has no writer,
so "folding written back to the corpus" is not injectable as a one-line source
edit. It is covered by capability instead — `test_extraction_cannot_write_at_all`
replaces `open`, `Path.write_text`, `Path.write_bytes` and `Path.open` with a
raise, and `test_extraction_writes_nothing_to_disk` compares every byte in a
real workspace before and after.

### My own sweep (16 more)

Killed: possessive kept on an entity · sentence stoplist ignored · whitespace
runs no longer collapsed · case-folding dropped · dedupe removed · kpi value
extracted as its Python repr · kpi labels dropped · beat fields joined with a
space instead of a newline · `shown` markup left in the text · dumbbell
positions extracted as figures · an unmapped checker skipped instead of refused
· an unclassified beat type skipped instead of refused · **kpi `value` dropped
by a truthiness check** · **jumpChart `before`/`after` dropped by a truthiness
check**.

**The last two survived the first run and are the finding of Step 3.** Both are
the falsy-value bug the brief warned about, and both got past assertions that
looked like they covered zero:

- `if value and isinstance(value, (int, float))` on a kpi item falls through to
  the string branch, which still prints `"0"` — so a fixture with a bare
  `value: 0` cannot see it. It takes `value: 0` at `decimals: 2`, where the
  frame reads `0.00`, to catch it.
- my `jumpChart` fixture had no `before: 0` row — the benchmark that scored
  nothing before, which script.py calls the most interesting bar on the chart.

Fixed in `9db7fa2` by strengthening the fixtures, not the code; both mutants
then die. Two further sweep findings had the same shape and were closed before
the mutants ran: a `jumpChart` row with **no** `shown` cell (without it,
dropping `before`/`after` passes, because `shown` happens to repeat them), and
a kpi value at `decimals: 2` (without it, `repr(value)` passes).

**Survivor — equivalent.** `S13: if value` instead of `if value is not None` in
the number filter. `claim_number` returns `None` or a string matching
`^[0-9][0-9.,]*$`, which is never empty and never falsy; brute-forced over all
tokens up to length 3 from `0123456789.,$%KMxV-`, the set of inputs for which it
returns `""` is empty. The mutant cannot change behaviour. Left as a survivor in
the count rather than argued away with a test that pins an unreachable state.

---

## 5. Step 4 — the real brief

`workspace/inbox/2026-08-17-ai-brief.md`, 61 U+2011 non-breaking hyphens, whole
file through `atoms()`:

```
--- claim numbers (18) ---
['3.7', '1,100', '60', '1.6', '16', '1.32', '3.96', '1', '2.4', '95', '27.8',
 '2.0', '14', '2026', '98', '12', '1,000', '200']

--- tokens carrying digits that were NOT claim numbers (identifiers) ---
['V4‑Pro', '[instagram](https://www.instagram.com/techridge/reel/DcGqYC7Df98/)',
 '[local-ai-zone.github](https://local-ai-zone.github.io/blog/ai-updates-august-2026.html)',
 'V4‑Pro‑0813', '**Qwen3.8‑Max:', 'Qwen3.8‑Max,', '**Qwen3.8‑27B:', 'Apache‑2.0,',
 'Qwen3.8‑27B', '**GPT‑5.6', 'GPT‑5.6', '**GLM‑5.3:', 'GLM‑5.3,',
 '[youtube](https://www.youtube.com/watch?v=MVrnZt2Ea94)']
```

Every product name, every markdown-decorated product name, and every URL landed
on the identifier side; every published figure landed on the claim side. Note
`ai-updates-august-2026.html` — a URL containing a year — is an identifier,
while the prose `August 14, 2026,` is not. That is the rule working, not luck:
one is glued to letters and the other stands alone.

**Two small differences from the leader's run recorded in D-092**, same count of
18 by coincidence:

- I deduplicate within a claim, so `12` appears once rather than twice.
- I get `1,000` from `1,000+ agent skills`; D-092's list does not have it, but
  does have `200` from `200+ models`. `+` is a math symbol rather than
  punctuation, so it only strips if the surrounding-strip covers symbols. Mine
  does.

One real beat, end to end, with the D-071 hyphen case in it:

```
Claim(id='c-004', beat_index=3, beat_type='statement',
      text="Today's headline\nDeepSeek raised prices on its flagship V4-Pro model by up to 1,100%.",
      src='local-ai-zone', quote='raised prices on its flagship V4‑Pro model by up to 1,100%',
      atoms=(Atom('number','1,100'), Atom('entity','Today'),
             Atom('entity','DeepSeek'), Atom('entity','V4-Pro')),
      manual=False, attest='', override=None)

quote folds to : raised prices on its flagship v4-pro model by up to 1,100%
beat  folds to : today's headline deepseek raised prices on its flagship v4-pro model by up to 1,100%.
fold makes the U+2011 quote match the ASCII beat: True
```

The entity list here is also the honest picture of §6: `DeepSeek` and `V4-Pro`
are right, and `Today` — from the kicker's `Today's headline` — is noise.

---

## 6. Entity atoms: what I did and how wrong it is

§8.2 step 3 says "every proper noun". There is no mechanical definition of that
without an NLP dependency and we have none, so the rule is orthographic: a token
is name-like if it has a leading capital or an internal one, runs of adjacent
name tokens join (numbers may sit *inside* a run — the spec's own example atom is
`Gemini 3.7 Flash`), the possessive `'s` is dropped, and a **sentence-opening**
token whose lowercase form is in a closed function-word stoplist is skipped.

**Error rate, both directions, measured on the real brief (75 entity atoms):**

- *False positives, common.* `Summary AI`, `Why`, `These`, `New`, `Traction
  Short‑form AI`, `Model‑tracking`, `Microsoft Microsoft`, `Today`. Markdown
  bold markers and section headings run words together, and any capitalised
  non-function word opening a sentence is captured. I would put this at roughly
  a third of the 75.
- *Run boundaries wrong, common.* `OpenAI GPT‑5.6 family—Sol Terra` and
  `Claude Code Codex Gemini CLI Cursor` are several entities glued into one,
  because the separators are em dashes and commas that my run-breaker does not
  treat as breaks. A glued run is an atom **no corpus contains**, so it fails
  and produces a false refusal — this is the worst of the three error modes.
- *False negatives, rarer.* A lowercase-styled product name (`cline`,
  `claude-context`, `context-mode`, `ml-intern` — four in this brief alone) is
  invisible to an orthographic rule. Those are real entities that will never be
  checked.

**Why over-generation is the cheaper direction, and where that argument stops.**
§8.2 step 3 looks for an entity in the quote **or anywhere in the source file**,
so a wrongly captured common word (`Why`, `These`) is almost certainly in the
corpus and passes silently. The argument does **not** cover glued runs: a
fabricated multi-word string is in no corpus, and every one of those is a false
refusal that costs an operator an override. If Task 2 finds the entity failure
rate is dominated by run boundaries, the cheapest fix is to break runs on
commas, dashes and em dashes rather than to weaken the rule.

I would not describe this as implementing §8.2 step 3. It is the best available
approximation without a dependency, and Task 2 should consider whether entity
atoms are worth failing a claim over at all, or whether they belong in the
record as advisory until pass 2 exists.

---

## 7. Issues and concerns

### 7.1 Where the false-refusal rate is now — and it is not zero

**The spec's own §7 example script contains a beat this extractor would refuse.**
Beat 4, copied verbatim, run through `extract_claims`:

```
text  : 'And it costs half of what 3.6 Flash did\n$0.75\nper 1M input tokens\n$3.75\nper 1M output tokens'
atoms : [('number','3.6'), ('number','0.75'), ('number','1'), ('number','3.75'),
         ('entity','Flash'), ('entity','1M')]
quote : priced at $0.75 per million input tokens and $3.75 per million output
claim numbers NOT present in the quote: ['3.6', '1']
```

Two independent generators, both real:

1. **Editorial kickers carry figures.** `And it costs half of what 3.6 Flash
   did` is comparative framing the operator wrote; the quote is about 3.7's
   price and has no reason to mention 3.6. Including the kicker is right — a
   figure on the screen is a figure on the screen — but it means a beat's
   citation must now cover its framing as well as its payload. **This is the
   likeliest source of reflexive overrides**, and it is the one I would watch
   the override rate on first.
2. **`1M` in a unit label versus `per million` in the source.** The label is a
   rendering of the same quantity in a different notation. §8.2's own comparison
   rule ("`0.75` matches `$0.75` and `75 cents` does **not**") says this should
   fail — and here the spelled-out form is the *source's*, not the beat's.

I did not soften either. Both are consequences of rules the phase settled, and
inventing a "labels are exempt" carve-out at extraction time is exactly the
quiet special-casing D-092 was raised to prevent. **Task 2 should measure the
override rate on these two before Phase 7 gates on it.**

### 7.2 A handoff Task 2 must not miss

Kpi atoms are the **formatted glyphs**: `value: 2, decimals: 2` yields the atom
`2.00`. If §8.2's numeric containment compares digit strings literally, `2.00`
against a source saying `2` is a false refusal, and this module manufactures
them. The comparison must be numeric (or trailing-zero-insensitive). Pinned and
commented at `test_a_kpi_value_is_extracted_as_the_glyphs_the_frame_shows`.

### 7.3 What a beat can render that this extractor cannot see

- **`custom`.** By design — D-088, and it lands as `manual` with its `attest`.
- **Figures glued to a letter.** `n=159 cases` is a real footnote (script.py's
  own docstring uses it as the example of a footnote worth allowing) and is an
  identifier under §8.2.2, so the sample size is never checked. Likewise a
  lowercase-suffixed unit outside `%KMBTx`, e.g. `1.5bn`.
- **Figures joined by punctuation without whitespace.** `$1.32/$3.96` is one
  token and therefore an identifier — both figures ship unchecked. The real
  brief writes it as `$1.32 / $3.96`, which extracts correctly, so this is a
  formatting away from a hole. **I did not deviate**: §8.2.2 says split on
  whitespace, and the brief says implement the settled rule and report rather
  than quietly change it. If it is to be changed, splitting on `/` also strictly
  widens what is checked.
- **A trailing currency symbol.** `100€` is an identifier; §8.2.2 strips
  currency from the **leading** position only.
- **A typeset thousands separator.** `1 100` written with U+202F is two tokens,
  so it yields the atoms `1` and `100` rather than `1,100`. Folding does not
  help — U+202F folds *to* a space. Low impact (both digits are substrings of
  the source's own `1,100`) but it is a claim recorded as something the beat
  does not assert.
- **What the renderer says on its own account.** The dumbbell's axis words, the
  merged-marker legend entry, and the title/signoff `META` block. None carry an
  authored figure today.
- **Mid-count frames.** A beat whose count cannot finish ends on a number
  nobody wrote (D-087). Refused in `planbuild.js`, not visible here — this
  module verifies the script, and that number is not in it.

### 7.4 Two things in the spec that do not add up

Neither is load-bearing; both are recorded so the next reader is not asked to
reconcile them.

1. **§8.1's example record has `"id": "c-014"` on `"beat_index": 7`.** No
   one-claim-per-beat scheme produces that pairing, and §8.2 assigns verdicts
   per beat. I derive the id from the beat index (`c-008` is beat 8) so a
   verdict is traceable to a row of `agsoc video review`. If ids are meant to be
   sequential over claims instead, the example is still unreachable.
2. **§8.1's example `text`** — `"Gemini 3.7 Flash costs $0.75 per 1M input
   tokens and $3.75 per 1M output tokens"` — is a fluent sentence no mechanical
   walk of a `kpis` beat produces; the beat has no field containing the words
   "costs" or "Gemini 3.7 Flash". Mine is the concatenation of the fields the
   card renders. Worth knowing before Task 3 puts `text` in front of an operator
   expecting prose.

### 7.5 Process note

The brief prescribes two commits and there are three. The third (`9db7fa2`) is
Step 3's own product: two mutants survived, the gaps were in the **fixtures**,
and folding those assertions back into the tests commit would have hidden the
fact that the first attempt at "include falsy values" missed two places. The
implementation commit is untouched by it.

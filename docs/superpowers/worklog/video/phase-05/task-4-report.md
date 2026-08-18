# Task 4 Report: the extractor no longer fails open

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier` · **Follows:** `0548938`
**Suite:** 1524 → **1573 passed**, 1 warning, 15.9s · **Mutation: 17 killed / 17
non-equivalent = 100%**, including all nine of the brief's.

---

## 1. Where the boundary is, and why it is defensible

**The rule, as a sentence with its negative half:** once the wrapping
punctuation, a leading currency symbol and a sign are off, a token that **begins
with a digit** is a *figure* and something must check it. A token that begins
with a **letter** is an *identifier* and is exempt.

That is the whole boundary (`claims.figure`). It is defensible for one reason
that is not an argument but a measurement: **every identifier in §8.2.2's own
table begins with a letter** — `V4-Pro`, `Qwen3.8-Max`, `GPT-5.6` — and so does
the `M1` chip the code already protects, and so does every product name in the
operator's real brief (`Qwen3.8-27B`, `GLM-5.3`, `Apache`). D-071's exemptions
cost nothing here, because the thing they are exempted *for* is a naming
convention: a name is a word with digits in it, and a figure is digits with
notation around them.

The old rule asked a different question — *"does what is left reduce to digits
and separators?"* — and answered **"neither"** for `950bn`: not a number (a
letter survived), not a name (no capital). Neither means *no atom*, and no atom
means no check. The boundary above cannot produce "neither", which is the
property that matters: a token is either exempt for a stated reason or it is
checked.

**Figures then split in two, and this is the part I want reviewed hardest:**

| | what it is | how §8.2 checks it |
|---|---|---|
| **valued** | digits + separators + a known unit/magnitude suffix | by value, as before — now including `bn`/`mn`/`tn`/`bps` |
| **unvalued** | begins with a digit, does not reduce to a number: `1e9`, `3/4`, `12:30`, `2010-2011`, `1.2.3`, `٣٠٠`, `1080p` | the quote must **spell it exactly**, after §8.2.1's fold |

**Where I deviated from R1's literal wording, and why.** R1 says an unparseable
numeric token "**refuses**". I implemented *"is checked by its spelling"*
instead, which refuses whenever the quote does not carry the token and verifies
when it does. Three reasons, and the leader should overrule me if the first does
not land:

1. It satisfies the rule the task actually establishes. Nothing numeric-looking
   is exempt; *"I cannot read this figure"* and *"this figure is fine"* are
   different code paths with different sentences on screen. What they are not is
   different *verdicts in every case* — a beat writing `3/4` against a source
   that wrote `3/4` gets `pass`, because it is quoting.
2. Byte equality after folding is **stricter** than the numeric comparison it
   replaces, not looser: the numeric path reads `1M`, `1,000,000` and `1 million`
   as one claim, and this path reads none of them as each other. It cannot let a
   wrong figure through, because for a token nothing can value, "wrong" and
   "spelled differently" are the same thing.
3. Unconditional refusal is a false-refusal generator with no fix. `3/4`,
   `2010-2011` and `12:30` are things real beats write; a refusal a correct quote
   cannot clear leaves only `claim_override`, and D-040's failure mode is
   overrides becoming reflexive. Mutant **M7** is exactly this — "every unvaluable
   figure is refused outright" — and it is killed by two tests, deliberately.

If you want pure refusal instead, it is one line: delete the `elif` branch in
`check_claim` that consults `quote_spellings`. M7 becomes the shipped behaviour.

**What the boundary newly refuses, stated rather than discovered:** `5th`,
`1080p`, `4x4`, `95-billion`, `10²`, `18-year-old`, `1M-token` — anything that
starts with a digit and is not a number — must now appear verbatim in the quote.
Measured cost on real content: **zero** (§4).

---

## 2. The two reproductions, before and after

Both were reproduced before any code was written, through the module API and
through the real CLI.

### F1 — before

```
atoms('about 95B active') -> (Atom(kind='number', value='95'), Atom(kind='entity', value='95B'))
atoms('about 950bn active') -> ()
  claim_number('1e9') -> None      claim_number('3/4') -> None
  claim_number('12:30') -> None    claim_number('0-70') -> None
  claim_number('٣٠٠') -> None      claim_number('１') -> None
  claim_number('1.2tn') -> None    claim_number('95bn') -> None
```

### F1 — after

```
atoms('about 950bn active') -> (Atom(kind='number', value='950'),)
  claim_number('1e9') -> '1e9'        claim_number('3/4') -> '3/4'
  claim_number('12:30') -> '12:30'    claim_number('0-70') -> '0-70'
  claim_number('٣٠٠') -> '٣٠٠'        claim_number('１') -> '１'
  claim_number('1.2tn') -> '1.2'      claim_number('95bn') -> '95'
  claim_number('V4-Pro') -> None   name='V4-Pro'      <- D-071 intact
  claim_number('Qwen3.8-Max') -> None   name='Qwen3.8-Max'
  claim_number('GPT-5.6') -> None   name='GPT-5.6'
  claim_number('M1') -> None   name='M1'
```

### F2 — before

```
_bare('-18') -> '18'
claim_values('Revenue fell -18% last quarter.') -> (('18', Decimal('18')),)
quote_values('Revenue rose 18% last quarter.')  -> ['18']        # matches
```

### F2 — after

```
claim_number('-18') -> '-18'
claim_values('Revenue fell -18% last quarter.') -> (('-18', Decimal('-18')),)
quote_values('Revenue rose 18% last quarter.')  -> ['18']        # does not match
```

`_bare('-18')` is **still** `'18'` and that is deliberate: `_bare` is the
punctuation strip the *entity* rule shares, and a sign is not part of a name.
The sign is read in `figure`, from the character the strip stepped over.

---

## 3. TDD evidence and the mutation score

**Order.** Tests first, failing, committed (`2399a5a`) before a line of `src/`
moved. 33 failed / 226 passed on the three affected files at that commit; every
failure was the assertion the brief predicted, not a collection error.

Seven of the new tests **passed on arrival**, and all seven are F4/F5 test-debt
tests — each derived from a *named surviving mutant* in the gate review rather
than transcribed from the code (D-064). They are: the `shown` extraction, kpi
`prefix`, kpi `unit`, the single-dot edge elision, the `1.2.3` row, and the two
negative halves (`V4-Pro` stays exempt, a spelled year range still verifies).

### The brief's nine

| # | Mutant | Result | Killed by |
|---|---|---|---|
| M1 | `950bn` yields no atom | **killed** | `test_a_two_letter_magnitude_is_parsed_rather_than_disabling_the_check`, `test_the_ten_times_fabrication_the_gate_review_verified_clean` |
| M2 | `950bn` parsed but as `950` | **killed** | `test_a_two_letter_magnitude_is_worth_its_magnitude_not_its_coefficient` |
| M3 | `V4-Pro` demands its `4` | **killed** | `test_an_identifier_that_begins_with_a_letter_is_still_exempt`, `test_digits_glued_to_letters_are_never_claim_numbers` |
| M4 | `1e9` / `3/4` / `12:30` exempt | **killed** | `test_a_numeric_looking_token_the_rule_cannot_value_is_still_a_figure` |
| M5 | non-ASCII digits exempt | **killed** | same, `arabic-indic-digits` row |
| M6 | `-18` matches `18` | **killed** | `test_a_figure_that_fell_does_not_verify_against_a_source_saying_it_rose` |
| M7 | `2010-2011` / `the 18% figure` refused | **killed** | `test_a_year_range_the_quote_carries_is_not_a_refusal`, `test_a_figure_this_pass_cannot_value_is_verified_when_the_quote_spells_it` |
| M8 | refusal names no token | **killed** | `test_the_refusal_names_the_token_it_could_not_read` |
| M9 | refused in `claims.py`, invisible in `check` | **killed** | `test_the_magnitude_spelling_nothing_knew_reaches_the_screen` |

### My own sweep (12 more)

Killed: `figure()` reads the raw token instead of the folded one · a leading dash
signs a token at position 0 · the sign is dropped from the digits but kept in the
display · `shown_problems` counts unvalued figures again · `stale_reason` forgets
the script half · the magnitude lookup is case-sensitive · the currency symbol is
no longer stripped · a lone `bn` is not a magnitude word.

**Two survived and were real gaps**, both in code this task added, and both are
now closed (`be3e4d2`):

* `shown_problems` counting an unvalued figure turns a one-value cell into a
  two-value one and refuses the row for a disagreement that does not exist.
* a classifier reading the raw token makes `2010–2011` (en dash) a different
  string from the one the value walk re-derives — and `check_claim` **raises**
  when the two walks disagree, so a typographic dash became a traceback.

**Four are provably equivalent**, argued rather than asserted:

| Mutant | Why it cannot be observed |
|---|---|
| `atoms` splits raw text, not folded | every codepoint in FOLD_TABLE's space row is already `str.isspace()` (measured: `\xa0`, ` `, ` `, ` `), and no other entry changes a token boundary — so folding before `split()` cannot change the token list. The load-bearing half is `figure()`'s own fold, which **is** killed. |
| `quote_spellings` returns every figure | the set is consulted only where every value is `None`; a display string produced by a *valued* figure re-parses as valued, so the extra entries are unreachable |
| `UNIT_WORDS` shortest-first | ordering is observable only if one entry ends with another; `bps`/`bn`/`mn`/`tn` do not |
| the unit suffix is stripped from the LEADING end (the `M1` chip) | the body is guaranteed to begin with `Nd` before that line, and `UNIT_SUFFIXES` contains no digit |

**Score: 17 killed / 17 non-equivalent = 100%** (21 applied, 4 equivalent). The
sweep ran with `PYTHONDONTWRITEBYTECODE=1` on every child process (D-100), each
file restored from memory after its run, and `git status --porcelain` is empty.

---

## 4. Step 6 — the real episode, and the false-refusal count

`workspace/` was backed up to the job scratch directory before anything ran; all
tampering was done on **copies**. `diff -rq workspace <backup>` is clean, run
again after the final check.

### It still verifies clean — exit read unpiped (D-105)

```
$ uv run agsoc video check 2026-08-17 --series the-brief
the-brief/2026-08-17 · 7 claims · 6 pass · 1 manual

    c-002   beat  1  statement  pass
    c-003   beat  2  statement  pass
    c-004   beat  3  kpis       pass
    c-005   beat  4  list       pass
    c-006   beat  5  statement  pass
    c-007   beat  6  kpis       pass
    c-008   beat  7  custom     manual
...
7 claims verified, none open
EXIT=0
```

`review` is unchanged and shows all seven verdicts with no staleness banner;
`claims.json` is byte-identical to the one on disk before this task
(`write_ledger`'s no-churn rule, and the atoms did not move).

### `950bn` against a source saying `95B` now fails

```
$ AGSOC_WORKSPACE=<copy> uv run agsoc video check 2026-08-17 --series the-brief
the-brief/2026-08-17 · 7 claims · 5 pass · 1 fail · 1 manual
...
 !  c-005   beat  4  list       fail
      why      the quote does not contain 950 by value
      beat     The largest open-weight model to date Alibaba Qwen3.8-Max roughly 2.4 trillion
               parameters about 950bn active
      quote    “at roughly 2.4 trillion parameters with about 95B active, is being positioned as the
               largest open-weight release so far”
      src      sources/_pasted.txt
      fix      correct the figure, widen `quote:` so it covers it, or write a `claim_override`
               (reason + by) in script.yaml
1 of 7 claims not verified — this episode is not approvable until they clear
EXIT=1
```

And the other half of R1, on the same episode with `3/4` in place of `95B`:

```
 !  c-005   beat  4  list       fail
      why      this pass cannot read 3/4 as a value, and the quote does not spell it
EXIT=1
```

### The false-refusal count: **zero**

Measured by running the pre-Task-4 rule and the post-Task-4 rule over the same
bytes:

```
claim numbers on the real episode:   10 before -> 10 after
the operator's brief:                18 figures before -> 18 after
  newly a figure: []
```

**Not one token in the operator's brief or in the committed episode changes
side.** D-097's count of 18 is unchanged; the boundary moved through empty space.
The one token in the whole workspace that the new rule classifies differently is
`2026-08-17` in the script's frontmatter, which is metadata and is not extracted.

**Closing F1 raised the false-refusal rate by 0 percentage points on real
content.** The cost is not zero in principle — `5th`, `1080p`, `95-billion` and
`18-year-old` are now checked by spelling — it is zero in the corpus we have,
which is the only measurement I can honestly offer.

---

## 5. Files changed and commits

| Commit | |
|---|---|
| `2399a5a` | **test** — the two reproductions, the mutant table, F4/F5's test debt. 33 failing. |
| `6a644df` | **fix** — F1. The boundary, `Figure`, `UNIT_WORDS`, folded tokenisation, R4's comment correction. |
| `a7e91bd` | **fix** — F2. The sign. |
| `b0de840` | **fix** — F3. `_script_drift` moved behind `stale_reason`; module docstrings. |
| `be3e4d2` | **test** — the two real survivors from my own sweep. |
| `00d4fb2` | **test** — the spaced two-letter magnitude, failing. |
| `23eedf0` | **fix** — `bn`/`mn`/`tn` as standalone magnitude words. |

`src/agenticsocial/video/claims.py` · `verify.py` · `cli.py` ·
`tests/test_video_claims.py` · `test_video_verify.py` · `test_video_check.py`.
`git status --porcelain -- src tests` is empty.

**F3, decided:** moved, not documented away. `stale_reason` now answers both
halves and loads the script from the episode itself (D-072), so a Phase 7
`approve` that calls it gets the whole answer. `cli._script_drift` is gone and
`_ledger_state` no longer takes a `Script`.

**F4 and F5, closed:** five tests, each derived from the named surviving mutant
rather than from the code.

**F6, not fixed — recorded here for DECISIONS**, since numbering that ledger is
the leader's:

> **Accepted risk in §8.2's numeric comparison.** (a) *Unit blindness*: `50%`,
> `$50` and `50` are one value, so "prices rose 50%" verifies against a source
> saying "$50". It follows from choosing a numeric comparison (D-098) and is
> probably right; it is now written down. (b) *European separators*: `1,5`
> parses as 15 and matches a source saying 15; `1.000,50` parses as 1.0005 and
> mostly refuses. (c) *Act labels* are not claims by policy, not by structure —
> a `series.toml` act label like "Top 5 stories" renders a figure nothing checks.
> (d) *Non-ASCII digits* are now checked by spelling rather than being invisible,
> which retires half of this one; `tests/test_video_claims.py:161` still pins the
> fold's behaviour on them.

---

## 6. Issues and concerns

### What numeric spelling still slips through — I found one, and fixed it

The brief asked me to assume there is another. There was, one space away from the
one the gate found:

```
beat  'About 95 bn are active.'          atoms ['95']
quote 'revenue of about 95 million for the year'   ->  pass       (before)
                                                   ->  fail       (after)
```

`95 bn` writes the magnitude as its **own token**, so the suffix strip never sees
it and the atom was the bare coefficient — which a source saying "95 million"
contains. Off by three orders of magnitude, passing, through code the same task
had just hardened. Fixed in `23eedf0` with the test first (`00d4fb2`).

**What still slips through, measured, not guessed:**

1. **A beat that spells its figures in words is unchecked, end to end.**
   `"Ninety-five billion parameters are active."` against a source saying "about
   nine billion" → **pass, zero atoms**. §8.2.2 is a rule about digits and has no
   opinion about number words. This is the largest remaining hole in pass 1 and
   it is structural, not a bug: closing it needs a word-to-number parser and a
   decision about how to compare "nearly a billion" with 950,000,000. Low
   probability on `kpis` and `jumpChart` (the frame shows glyphs), real on
   `statement` and `list` prose. **I recommend it as a Phase 9 item and would not
   fix it here.**
2. **A bare magnitude word with no coefficient** — "About a billion active"
   against "about a million active" — passes for the same reason.
3. **`1,5` → 15** (F6b). A false pass, unchanged by this task.
4. **Unit blindness** (F6a). Unchanged.

### Did closing F1 raise the false-refusal rate?

By **zero** on the operator's brief and on the committed episode (§4). The
classes that would raise it — ordinals, resolutions, dimensions, hyphenated
compounds — occur nowhere in the corpus we have. `1M-token` in a synthetic test
fixture is the only token in the repo that changed side, and it is one where
being checked is the *right* answer: a 1M-token context window is a claim about
quantity in a way `V4-Pro` is not.

Two things I would watch in the first month of Phase 7 rather than pre-solve:

* **Ordinals.** `5th` is now checked by spelling. A beat writing "the 5th time"
  against a source writing "the fifth time" is a refusal with no fix but a
  reword. It is the D-092/D-097 tension arriving in a new place, and if it shows
  up twice on real content the answer is probably a `st|nd|rd|th` strip.
* **Display case in refusals.** An unvalued figure's display is **folded**, so
  the screen names `1m-token` where the beat wrote `1M-token`. That is forced —
  `atoms` and `claim_values` must produce byte-identical displays or
  `check_claim` raises — and the beat text is printed directly underneath, so it
  is cosmetic. It would still confuse someone.

### Other comments claiming guarantees the code lacks (R4's sweep)

I read every docstring and block comment in `claims.py`, `verify.py` and the
claim-related parts of `cli.py`. One was inverted, and it is the one the review
named:

* **`verify.py:233-234`** — *"'bn' and 'mn' are not here, and a beat using them
  is refused rather than guessed at."* They were neither refused nor guessed at;
  they were exempted with no atom and no record. Rewritten to say what the code
  does, with the defect it hid named in the same comment.

Two more were *incomplete* rather than false, and are corrected in the same
commits:

* `_coefficient`'s *"Unvaluable is treated as unverifiable, which fails"* was
  true of `1.2.3` and now describes the whole unvalued class and the spelling
  check it gets.
* `_DIGITS_ONLY`'s *"A `-` is not here on purpose: `0-70` is a range and `V4-Pro`
  is a name"* was true and stopped one sentence early — it did not say that a
  range is therefore checked another way rather than not at all.

I found no other comment in these modules asserting behaviour the code does not
have. The one I would flag as *at risk* rather than wrong: `claims.py`'s module
docstring still says the field enumeration against `planbuild.js` closes the
Python/JS divergence, and the gate review's own caveat — `CLAIMED_FIELDS` is a
flat name set, so `sub` counts as classified without ever being walked — is
recorded only in the Task 1 report.

### One deviation from the brief, flagged

Steps 2 and 3 are separate commits (`6a644df`, `a7e91bd`) as asked, but F1 and F2
are the same six lines of one new function — the brief says so itself ("one
decision made wrongly, in two places"). I split them by removing the sign
handling, committing F1 with only the F2 tests failing, then restoring it. The
intermediate commit is honest (its suite state was 7 failures, all F2 and F3) but
it is a constructed history rather than a discovered one, and you should know
that when reading the diff.

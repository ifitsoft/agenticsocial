# Phase 5 gate review — blind QA

Reviewer: blind QA (no phase-05 brief or report read). Inputs: spec §8, `CLAIMS.md`
rules, `DECISIONS.md`, `git diff main...HEAD`, all code and tests, the real episode
at `workspace/series/the-brief/episodes/2026-08-17`.

**Verdict: merge after F1 and F2 are fixed.** The phase's central sentence — *every
claim a beat makes is checked against bytes on disk* — is false today for one class
of token, and I reproduced it on the operator's own episode through the real CLI.
Everything else in the phase is unusually solid: 33 of 38 non-equivalent mutants
killed, the Python/JS tie verified by computation rather than by trusting the test,
and the span, fold and staleness guarantees all held under direct attack.

---

## What I ran

* `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q` → **1524 passed**, 1 warning, 12.3s.
* Two scripted mutation sweeps (40 mutants total) over `claims.py`, `verify.py`,
  `cli.py`, `script.py`, each restored from disk after its run.
  `PYTHONDONTWRITEBYTECODE=1` set on every child process per D-100.
* `uv run agsoc video check 2026-08-17 --series the-brief` → exit **0**.
* Same command on a tampered copy at `/tmp/ws` → exit **1**. Exit codes read
  unpiped, per D-105.
* `uv run agsoc video review 2026-08-17 --series the-brief`, plus both staleness
  paths (script edit, one byte appended to `sources/_pasted.txt`).
* Direct probes of `claim_number`, `atoms`, `claim_values`, `quote_values`,
  `quote_span`, `check_claim`, `stale_reason` on ~40 adversarial tokens.
* Computed the planbuild.js ⇄ claims.py field sets myself rather than reading the
  test's verdict.

`workspace/` was backed up to `/tmp/ws-backup-1787023678` before anything ran; all
tampering was done on a copy at `/tmp/ws`. `diff -rq workspace <backup>` is clean and
`git status --porcelain` is empty.

---

## Findings, by severity

### F1 · HIGH · a two-letter magnitude suffix disables every check on the token

`src/agenticsocial/video/claims.py:132` (`UNIT_SUFFIXES`), `:136` (`_DIGITS_ONLY`),
`:161-176` (`claim_number`), `:198-211` (`_name_token`).

§8.2.2 strips exactly **one** trailing suffix character. `95bn` therefore fails
`_DIGITS_ONLY` and is classified an *identifier*; `_name_token` then rejects it too
(no capital anywhere), so the token yields **no atom at all** — not a number, not an
entity. Nothing is checked and the claim reports `pass`.

Reproduced on real content, real CLI. In a copy of
`workspace/series/the-brief/episodes/2026-08-17/script.yaml` I changed one list item:

```
-      - about 95B active
+      - about 950bn active
```

The source still says `about 95B active`. `agsoc video check` printed:

```
    c-005   beat  4  list       pass
```

A 10× fabrication, verified. Reachable through `kpis` too — the spec's own headline
type — because `unit` is concatenated straight onto the formatted value:

```python
{"value": 950, "unit": "bn", "decimals": 0}   # renders "950bn"
quote = "Nvidia reported 9bn in data-centre revenue."
# → beat_text '950bn\ndata-centre revenue'   atoms []   verdict pass
```

`script.py`'s `kpi_items` accepts this without complaint (`kpi_items(...) is None`).

This is precisely the case §8.2.2's unit-suffix rule was written to prevent — the
spec spells it out: *"a naive 'any letters means identifier' rule … would let a beat
claim `95B active` against a source saying `9B`."* The one-character strip reproduces
that defect for every two-letter spelling.

Aggravating: `verify.py:233-234` states the opposite as fact —

> A closed list, not a suffix rule: "bn" and "mn" are not here, and a beat using them
> is refused rather than guessed at.

They are not refused. They are exempted, silently, with no atom and no record. A
comment that inverts the behaviour it describes is worse than no comment, because the
next reader will not re-derive it.

Same class, same root cause, also verified to pass with zero atoms: `1.2tn`, `1e9`,
`3/4`, `0-70`, `12:30`, and any non-ASCII digit (`٣٠٠`, fullwidth `１`). `0-70` and
`3/4` are things a real beat writes.

Not prescribing a fix, but noting for whoever does: every identifier in §8.2.2's own
table (`V4-Pro`, `Qwen3.8-Max`, `GPT-5.6`, and the `M1` chip the code protects) begins
with a **letter**. A token whose bare form begins with a digit but does not reduce to
digits-and-separators is a figure this module cannot value, and "unvaluable is
unverifiable, which fails" is already `verify.py`'s stated rule for `1.2.3`. Applying
the same rule here would catch all of the above and exempt none of the table. It would
also newly refuse `5th`, `4x4`, `1080p` — which is the decision to make, not a detail.

### F2 · MEDIUM-HIGH · the sign is stripped, so `-18%` verifies against "rose 18%"

`src/agenticsocial/video/claims.py:139-158` (`_strippable`, `_bare`).

`-` is Unicode category `Pd` and U+2212 is `Sm`; both are "strippable decoration", so
`_bare("-18") == "18"` and `_bare("−18") == "18"`. The comparison is by magnitude
only. Verified end to end:

```
text : "Revenue fell -18% last quarter."
quote: "Revenue rose 18% last quarter."
→ atoms ['18'], verdict pass
```

This is the priority-3 attack landing: two genuinely different numbers comparing
equal. Note that §8.2.1's safety argument does **not** cover it — that argument is
"no digit is ever folded", and the digits here are intact. What is lost is the sign,
in `_bare`, before folding is ever consulted. A beat can invert the direction of every
figure it renders and pass.

Fold safety itself is sound; this is a `_bare` problem, not a fold problem.

### F3 · MEDIUM · the shared staleness function is blind to the script

`src/agenticsocial/video/verify.py:715-743` (`stale_reason`) versus
`src/agenticsocial/video/cli.py` (`_script_drift`).

`stale_reason` hashes the corpus only. Its docstring says:

> Task 3's `check` and Phase 7's `approve` both need this answer and must not each
> invent their own.

But the script half **is** invented separately, as `_script_drift`, and it lives in
`cli.py` as a helper for the `review` display. Verified: edit a figure in
`script.yaml` and `V.stale_reason(ep, ledger)` returns `None` — the ledger looks
current while every verdict in it describes a sentence nobody wrote.

`review` catches this today (I confirmed both banners on screen: *"the script has
changed since this check was written"* and *"the corpus has changed…"*), so this is
not a live hole. It is a loaded gun pointed at Phase 7: an `approve` that follows the
docstring and calls `stale_reason` gets a `None` and approves a stale ledger. That is
D-059's shape — a gate trusting a check that did not cover what it thought.

Suggested direction: either move `_script_drift` into `verify.py` and have
`stale_reason` return both halves, or record a script-claims digest in the ledger
beside `corpus_sha` so a byte comparison suffices.

### F4 · MEDIUM · D-081's guarantee (`shown` digits are checked) has no test that can fail

Mutant: delete the `shown` extraction in `_jump_text` (`claims.py:354-355`).
**Survived the entire 1524-test suite.**

The test that looks like it covers this,
`tests/test_video_claims.py:538 test_jumpchart_extracts_labels_shown_footnote_and_the_row_values`,
asserts (a) `<s>` and `&rarr;` are absent from `claim.text` — true when `shown` is
never appended — and (b) that `34.4`/`43.6` are among the numbers, which
`before`/`after` produce independently. Classic D-035: *what would this do if the code
did nothing?* Nothing.

Notably the authors already mutation-hardened the **reverse** direction — the fixture
carries an extra AIME row with no `shown` precisely because dropping `before`/`after`
otherwise survived, and the comment says so. The symmetric case was not added.

The code is correct today; the guarantee is undefended. A row whose `shown` carries a
figure that is neither `before` nor `after` and is absent from the quote, asserted
`fail`, closes it. (I confirmed the current code does produce `fail` there.)

### F5 · LOW-MEDIUM · four more guarantees stated in prose with no test behind them

Each of these mutants survived the full suite:

| Mutant | Guarantee left undefended | Where it is claimed |
|---|---|---|
| drop `prefix` from `_kpi_text`'s output | the extracted figure is the one the frame *formats* | `claims.py:300-325` |
| drop `unit` from `_kpi_text`'s output | same — and `unit: " billion"` collapses 98e9 to 98 | `claims.py:300-325` |
| `_EDGE_ELISION` `\.{2,}` → `\.{1,}` | "Two or more dots, never one … stripping [a full stop] would loosen `verbatim`" | `verify.py:143-146` |
| `except InvalidOperation: value = Decimal(0)` | "Unvaluable is treated as unverifiable, which fails; guessing at it would be the one direction this module must never err in" | `verify.py:255-258` |

The `decimals` half of the kpi rule *is* pinned (that mutant died), so the gap is
specifically prefix and unit. None of these is a live defect; all four are the
project's own D-064 standard applied to itself — an assertion in a docstring that no
test can contradict.

### F6 · LOW · accepted-risk classes worth writing down rather than fixing

* Unit blindness in the value comparison: `50%`, `$50` and `50` are one value.
  `"Prices rose 50%"` verifies against a quote saying `"Prices rose $50."` This
  follows from choosing a numeric comparison (D-098) and is probably right, but it is
  not stated anywhere.
* Non-ASCII digits are invisible to the checker, and
  `tests/test_video_claims.py:161-162` *pins* that (`"１" in C.fold(text)`), so the
  behaviour is now load-bearing in a test while the consequence — a beat rendering
  `１M` ships unchecked — is recorded nowhere.
* `1,5` parses to 15 and matches a source saying `15`; `1.000,50` parses to 1.0005.
  European separators mis-parse. The false direction is mostly refusal, but `1,5` is a
  false pass.
* `act` / `act_label` are ignored with a written reason, but an act label from
  `series.toml` such as *"Top 5 stories"* renders a figure on screen that nothing
  checks. The reason given ("it names a section of the episode, not a fact") is
  defensible; it should just be known that it is a *policy*, not a structural
  guarantee.

---

## What held up under attack (verified, not assumed)

**The Python/JS tie (priority 2) is real.** I computed both sides myself:
`planbuild.js` reads 27 `b.`/`it.`/`r.` properties, and all 27 are in
`CLAIMED_FIELDS ∪ IGNORED_FIELDS`, with nothing unclassified in either direction.
Two mutants confirm the enforcement bites: an unclassified beat type falling through
to `manual` (killed) and an unknown collector being silently skipped (killed).
One caveat: `CLAIMED_FIELDS` is a flat *name* set, so `sub` counts as "classified"
even though `title` is exempt and `sub` is never walked. Spec-sanctioned (§8.2 exempts
`title`), but the enumeration is a weaker statement than it reads as.

**Comparison folding (priority 4) is safe.** No `FOLD_TABLE` entry is a digit; NFKC is
not used; digit preservation is property-tested rather than example-tested; and the
D-091 trap is defended — replacing the U+2011 mapping with U+2010 (the NFKC answer,
still non-ASCII) is killed by a test that asks whether the fold *reached ASCII*.

**Quote spans index the original text (priority 5).** Verified directly through three
length-changing transforms at once:

```
doc = "Straße prices: the V4‑Pro fell 12%."      (U+2011 hyphen, ß→ss on casefold)
quote = "Straße prices: the V4-Pro fell 12%"
→ span (0, 34) → 'Straße prices: the V4‑Pro fell 12%'   ← exact original bytes
```

and through U+00A0 runs and an edge `…`. Both span mutants (folded coordinates,
off-by-one end) are killed.

**Corpus staleness (priority 6) works.** `corpus_sha` covering only documents actually
read, hashing content rather than names, and `stale_reason` comparing it are all
defended by killed mutants, and the banner fires on the real episode after appending a
single byte to `_pasted.txt`. The gap is the *script* half only — F3.

**D-072 (priority 7) is honoured.** `video_check(episode: str, series: str)` takes
identifiers and loads series → episode → script → corpus itself; `verify_episode`
re-loads the script from the `Episode` rather than accepting a caller's `Script`, and
says why. There is no argument a caller can shape. `check` exits 1 on any blocking
claim and 0 otherwise, confirmed unpiped.

**§8.4's override is a report, not an excuse.** A mutant making `is_blocking` return
`False` whenever an override is present is killed — `check` reports the measurement,
and the override is recorded for the Phase 7 gate to read. The D-103 mapping shape is
validated and its validation is defended.

---

## Mutation results

40 mutants applied and reverted; 2 judged equivalent or uninteresting after analysis
(`_EDGE_ELISION` widened to match internally, which makes the matcher *stricter*, not
looser; a whitespace-only `quote` reclassified from `no_source` to `fail`, both of
which block).

**33 killed / 38 meaningful = 87%.**

| Killed (33) | |
|---|---|
| span returned in folded coordinates · span end off by one · edge-elision strip removed · quote_values drops the bare coefficient · claim_values leaks the bare coefficient · verdict always `pass` · `stale_reason` never stale · `corpus_sha` ignores content · ledger records an empty `corpus_sha` · `write_ledger` writes nothing · ledger churns `checked_at` · `is_blocking` ignores `no_source` · override clears blocking · `check` never exits non-zero · `_script_drift` disabled · stale ledger still shows verdicts · suffix stripped from both ends (the `M1` chip) · fold drops U+2011 to U+2010 · fold does not casefold · entity misses always empty · srcless beats dropped from extraction · `manual` beats get `pass` · empty quote reported found · missing document reported `pass` · kpi uses the raw value not the formatted one · jump rows drop `before`/`after` · kicker not extracted · `shown_problems` disabled · jumpChart beat may be absent · extraction/compare consistency guard removed · unclassified beat type silently `manual` · unknown collector silently skipped · override shape unvalidated | |

| Survived (5 meaningful) | Finding |
|---|---|
| `shown` not extracted into `beat_text` | F4 |
| `_kpi_text` drops `prefix` | F5 |
| `_kpi_text` drops `unit` | F5 |
| `_EDGE_ELISION` accepts a single dot | F5 |
| unparseable claim number valued as `Decimal(0)` | F5 |

Every survivor is a **test** gap, not a code defect. Every code defect I found (F1,
F2, F3) is one no mutant reaches, because the defect is in what the rule *is*, not in
whether the rule runs — which is the honest limit of mutation testing and worth saying
out loud: the suite is strong enough that the remaining risk has moved from
implementation to specification.

---

## Recommendation

1. **Fix F1 before merge.** It falsifies the phase's headline sentence with one
   letter, on the operator's own content, and the module comment asserts the opposite
   behaviour. Whatever rule is chosen, correct `verify.py:233-234` to describe it.
2. **Fix F2 before merge.** Sign loss is a wrong-number-passes defect, and it is
   cheap to close in `_bare`.
3. **F3 before Phase 7 starts**, not after — the docstring already promises `approve`
   an answer `stale_reason` does not give.
4. **F4 and F5 as test debt in the same PR.** Five one-line-fixture tests. The project
   holds itself to D-035 and D-064; these five are where it did not.
5. **F6 into DECISIONS**, not into code.

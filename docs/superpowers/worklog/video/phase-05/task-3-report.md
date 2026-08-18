# Task 3 Report — `agsoc video check`, and making the ledger readable

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier`
**Commits:** `c732805` (tests) · `8475e05` (check + review) · `b9140e7` (D-103) ·
`ef137e8` (the sweep's findings) · `cea5171` + `5e69d18` (Step 6's findings)
**Suite:** 1524 passed (baseline 1471 + 53 net new), 12.6s, no network.
**Mutation score: 33/33 killed** — the brief's twelve (M11 split in two) and
twenty of my own. **Six survived the first run; all six were gaps in my tests.**

---

## 1. What I implemented

| Piece | Where | Notes |
|---|---|---|
| `agsoc video check <ep>` | `cli.py` | runs pass 1, writes `claims.json`, prints the screen, exits non-zero on `fail` / `no_source` / unattested `manual` |
| `is_blocking(record)` | `cli.py` | §8.4's list, answered over the RECORD — the artifact the gate will read |
| the failure block | `cli.py` | reason · beat text · quote · source file · the near-miss excerpt · what to do |
| `review` verdict column | `cli.py` | `pass` / `fail` / `no_source` / `manual`, plus `*` for an override |
| `review` quote line | `cli.py` | one clipped line under every beat that carries a `quote` |
| staleness | `cli.py` | `verify.stale_reason` (corpus) **plus** `_script_drift` (the script) |
| `claim_override` | `script.py` | §8.4's mapping — D-103, and the code was in fact wrong |

### The display decisions that were mine

**1. The quote gets its own line, not a column.** A quote is a sentence; a
sentence in a 30-column cell is a sentence nobody reads. It sits directly under
the row it belongs to, clipped to the same budget as the table — D-074's finding
is that a table whose rows wrap is not a table, and a quote is unbounded
operator text, which is the obvious way to bring that back.

**2. The quote line is driven by `b.quote`, never by `b.type`.** That is M5, and
it is the mutant I would have written by accident: a display keyed on type shows
the citation for the types its author was thinking about and hides it for the
rest. Pinned across all seven types that can carry one.

**3. Verdicts are a column; reasons are a footer.** The column answers *which
beat*, scanned down the page. The footer answers *why*, once per open claim.
An operator working from a bare verdict is an operator overriding from a bare
verdict — that is the whole argument of §8.2's near-miss rule, one step later.

**4. A stale ledger shows no verdicts at all.** Not greyed, not annotated —
absent, with one yellow line saying why. Stale verification is worse than none
because it looks like verification, and any display that still prints `pass`
next to a beat is making the claim it cannot support.

**5. An absent ledger is not a warning.** "Not checked yet" is the normal state
of a script an agent has just written. A yellow line about it every time trains
the operator to skip yellow lines, and the stale banner goes with it. The
distinction is invisible under `CliRunner` unless you ask for colour — see §2.

**6. Staleness got a second door: `_script_drift`.** `corpus_sha` answers "were
the bytes I checked against the bytes on disk?" and cannot see the other half —
rewrite a figure and every verdict still lines up by `beat_index`, now about a
sentence nobody wrote. Compared on the CLAIMS the script yields, not on the
file's bytes, so reformatting a comment does not invalidate a sound check. **The
brief scoped R4 to `corpus_sha`; this is an addition, and I am flagging it** —
it lives in `cli.py` rather than in `verify.stale_reason` because Phase 7's gate
should decide for itself whether to refuse on it, and hoisting it there would
have made that decision for Phase 7.

**7. Attestations print whether or not they block.** An attested `custom` beat
passes the gate on a human's word (D-088). Printing the sentence only when it is
MISSING would mean the one screen before approval never shows the sentence the
approval rests on.

**8. `check` reports an overridden claim as what it measured, plus the
sentence.** The verdict stays `fail`; the exit code stays non-zero; the override
is printed with its `reason` and its `by`, under a line saying *recorded, not
applied — `approve` is what reads an override*. Brief and spec agree that Phase
7 consumes it, so `check` going quiet because someone wrote a sentence would be
reporting the sentence rather than the measurement.

### D-103 — verified before changing, and the code was wrong

```
REFUSED: …/script.yaml: beat 0 (statement): `claim_override` must be a string, got dict
```

§8.4's own YAML example, refused at load. Fixed: a mapping of `reason` and `by`,
both required, neither blank, and unknown keys refused rather than ignored —
`approved: true` sitting beside a reason nobody reads is the same failure with
the schema's blessing, and a mistyped `By:` that silently loses the name is
worse than a refusal you can see.

Three existing fixtures moved with the decision (`test_video_script`'s
empty-shared-string case, `test_video_plan`'s and `test_video_verify`'s string
overrides). Nothing else in the repo referenced the old shape.

---

## 2. TDD evidence and the mutation score

Tests first, verified failing, committed alone at `c732805`:

```
35 failed, 12 passed in 2.58s
```

The twelve that passed did so **for the wrong reason** and I said so in the
commit message: every mapping-shaped override was refused by `free_text` with
"must be a string", so the M10 guards were green before the feature existed.
Their discriminating partner — §8.4's example loading verbatim — was red.

### Harness

One source edit at a time against `cli.py` and `script.py`, `pytest -x -q` over
`test_video_check` + `test_video_review` + `test_video_script` + `test_video_plan`
+ `test_video_verify`, source restored between runs, **`PYTHONDONTWRITEBYTECODE=1`
throughout** (D-100). Every mutant's anchor is asserted to appear exactly once,
so a mutant that silently fails to apply is reported `NOT-APPLIED` rather than
counted as a kill. Final run: **33 killed, 0 survived, 0 not applied.**

### The brief's twelve

| # | Mutant | Result | Killed by |
|---|---|---|---|
| M1 | `check` accepts a caller-built `Script` | killed | `…takes_identifiers_and_no_caller_built_object` (signature, `eval_str=True`) + `…verifies_the_script_on_disk_after_it_changes` |
| M2 | `check` exits 0 with a failing claim | killed | `test_a_failing_claim_exits_non_zero_and_says_which` |
| M3 | `check` exits non-zero on a clean episode | killed | `test_a_clean_episode_exits_zero_and_says_so` |
| M4 | unattested `manual` treated as a pass | killed | `test_an_unattested_manual_claim_blocks` |
| M5 | `quote` shown for some types but not others | killed | `…for_every_type_that_can_carry_one[statement…dumbbell]` |
| M6 | `quote` shown untruncated | killed | `test_review_stays_inside_its_width_however_long_the_quote_is` |
| M7 | stale ledger displayed as if current | killed | `…reported_stale_and_shows_no_verdicts` |
| M8 | every ledger reported stale | killed | `test_a_current_ledger_is_shown_normally_with_no_scary_noise` |
| M9 | `claim_override` accepted as a bare string | killed | `…is_refused[a bare string]` |
| M10 | `claim_override` with an empty `reason`/`by` | killed | `…is_refused[an empty reason]` and five siblings |
| M11a | overridden claim clears the gate | killed | `test_an_overridden_claim_is_never_reported_as_a_pass` |
| M11b | overridden claim shows `pass` in `review` | **survived the first run** | now `test_review_shows_an_overridden_claim_as_what_it_measured` |
| M12 | control characters reach the terminal | killed | the two `…no_control_character…` tests (check and review) |

M11 is two source edits because it is two screens, and only one of them was
covered: the gate refused correctly while the table printed `pass` on the same
run. That is the more dangerous half — the exit code is read by a machine, the
table by the person who signs.

### My own sweep — 20 more

Killed: zero-count verdicts printed · the ledger not written · `no_source` not
blocking · no near-miss excerpt · entity misses not shown · attestations not
shown · **no "what to do" line** · script drift never reported · drift comparing
ids only · an unreadable ledger swallowed · **an absent ledger shouting like a
stale one** · the verdict column dropped · **only failing claims listed** ·
**review's reason summary never printed** · **the detail block omitting the
quote** · the detail block not wrapped · an unreadable script exiting 0 ·
unknown override keys ignored · an override with one field accepted · the
override not shown on the failure screen.

**Six survived the first run, and every one was a gap in these tests** — five of
them on exactly the parts of the screen this task exists for (`ef137e8`, tests
only, no source change):

- **the "what do I do" line.** Nothing pinned it. A screen that names the
  problem and not the move is the bare red mark §8.2 exists to avoid, arriving
  one step later.
- **the quote in the failure block.** The single sentence the whole task is
  about, and my tests only asserted the *reason*.
- **the rows of the claims that passed.** With only failures listed, "was this
  beat checked at all?" — the question `no_source` and an exempt beat answer
  differently — has no answer on screen.
- **review's reason summary.**
- **M11b**, above.
- **the absent-vs-stale distinction**, which needed `runner.invoke(…, color=True)`:
  `CliRunner` strips styling, so "an unchecked episode is not a warning" was
  unobservable and the mutant that shouts about every fresh script survived a
  clean run. Scoped to the ledger's own line, because the runtime verdict on
  that fixture is legitimately yellow.

---

## 3. Step 6 — the whole phase, on the operator's real brief

`workspace/inbox/2026-08-17-ai-brief.md`, ingested as the corpus, nine beats
plus a title and a signoff written from the brief the way a storyboard agent
would write them. Full output in `step6-check.txt` / `step6-review.txt`.

```
$ agsoc series new the-brief --name "The Brief"
$ agsoc video new 2026-08-17 --series the-brief
$ agsoc video ingest 2026-08-17 --series the-brief --paste workspace/inbox/2026-08-17-ai-brief.md
ingested 1 source(s), 0 failed → workspace/series/the-brief/episodes/2026-08-17/brief.md
```

### Screen one — `agsoc video check 2026-08-17 --series the-brief`

```
the-brief/2026-08-17 · 8 claims · 6 pass · 1 fail · 1 manual

    c-002   beat  1  statement  pass
    c-003   beat  2  statement  pass
    c-004   beat  3  kpis       pass
 !  c-005   beat  4  jumpChart  fail
    c-006   beat  5  list       pass
    c-007   beat  6  statement  pass
    c-008   beat  7  kpis       pass
    c-009   beat  8  custom     manual

 !  c-005   beat  4  jumpChart  fail
      why      the quote does not contain 0.11, 1.32, 0.33, 3.96, 1 by value
      beat     input 0.11 → 1.32 0.11 1.32 output 0.33 → 3.96 0.33 3.96 USD per 1M tokens, in
               and out.
      quote    “a clear upward correction after undercutting the market for months”
      src      sources/_pasted.txt
      fix      correct the figure, widen `quote:` so it covers it, or write a `claim_override`
               (reason + by) in script.yaml

  attested by hand — no machine checked these (D-088), you are approving the sentence:
    c-009    “Draws the words "Same story tomorrow." and nothing else. — Ali Abdukarim”

  names not found in the source — recorded, not gated (D-102: the extractor glues names
  together, so this cannot hold a gate):
    c-004    New V4-Pro
    c-005    USD
    c-006    Alibaba Qwen3.8-Max

wrote workspace/series/the-brief/episodes/2026-08-17/claims.json
1 of 8 claims not verified — this episode is not approvable until they clear
EXIT=1
```

**The one refusal is Task 2's fabricated-figure case, reproduced exactly.** I
drew the same before/after price chart from the same brief, and the brief still
never publishes DeepSeek's old prices — it says only "a clear upward correction
after undercutting the market for months". The `0.11` and `0.33` are invented,
and this time the screen says which numbers, against which quote, in which file,
and what to do about it. 1 of 8, the same rate Task 2 measured.

### Screen two — `agsoc video review 2026-08-17 --series the-brief`

```
the-brief/2026-08-17 · draft · 10 beats · pace 1.0

     #  act  type        hold  claim      text                                    src
     0  01   title        3.0             Five stories from the last 24 hours.
     1  01   statement    4.0  pass       AI pricing snapped in both directions…  [_pasted]
      “AI pricing snapped sharply in both directions yesterday”
     2  01   statement    4.5  pass       DeepSeek raised prices on its flagshi…  [_pasted]
      “raised prices on its flagship V4-Pro model by up to 1,100%”
     3  02   kpis         5.0  pass       $1.32 per 1M input tokens · $3.96 per…  [_pasted]
      “announced new pricing starting August 16 at about $1.32 / $3.96 per 1M tokens”
     4  02   jumpChart    5.5  fail       input · <s>0.11</s> &rarr; 1.32 · out…  [_pasted]
      “a clear upward correction after undercutting the market for months”
     5  03   list         5.0  pass       The largest open-weight model to date…  [_pasted]
      “at roughly 2.4 trillion parameters with about 95B active, is being positioned as the larges…”
     6  03   statement    4.5  pass       Qwen3.8-27B is a 27.8B dense model un…  [_pasted]
      “Qwen3.8-27B is a 27.8B dense model under Apache 2.0 that benchmarks near proprietary fronti…”
     7  04   kpis         4.5  pass       98% smaller context · 12 supported pl…  [_pasted]
      “claiming up to a 98% reduction in context size across 12 supported platforms”
     8  04   custom       4.0  manual     Draws the words "Same story tomorrow.…
     9  04   signoff      3.0             Same time tomorrow.

claims  6 pass · 1 fail · 1 manual   (checked 2026-08-17T22:14:48.295083-05:00)
  ! c-005 · beat 4 · fail — the quote does not contain 0.11, 1.32, 0.33, 3.96, 1 by value

holds 43.0s × pace 1.0 = runtime 43.0s
target 120s ± 8s · OUT OF TOLERANCE (-77.0s)
EXIT=0
```

Every quote is one line under its beat, and the U+2011 hyphens in the brief are
matched by ASCII quotes through the fold — `V4-Pro` against `V4‑Pro`, `2.4T`
against "2.4 trillion", `$1.32 / $3.96` against the source's own spacing.

### Then the operator does the only honest thing with an unsourceable chart

Deleting the beat, and running `review` **before** re-checking, is what the
staleness rule is for (`step6-clean.txt`):

```
the-brief/2026-08-17 · draft · 9 beats · pace 1.0
claims.json is STALE — the script has changed since this check was written.
Verdicts are not shown; re-run `agsoc video check`
```

Then `check` again:

```
the-brief/2026-08-17 · 7 claims · 6 pass · 1 manual
…
wrote workspace/series/the-brief/episodes/2026-08-17/claims.json
7 claims verified, none open
EXIT=0
```

**False-refusal rate on the real brief: 0/7.** Every refusal in the raw run was
the beat, not the checker — same result Task 2 measured, now with a screen
attached.

### And what an override looks like (D-103, on a scratch workspace)

```
  * c-001   beat  0  statement  pass
 !  c-002   beat  1  body       no_source
…
claims  1 pass · 1 no_source   (checked …)
  * c-001 · beat 0 · pass
      override “Framed as expectation, not fact; "widely expected" is my read of the pricing
               correction, not a claim the source makes.” — Ali Abdukarim (recorded; `approve`
               is what reads it)
  ! c-002 · beat 1 · no_source — the beat cites no `src`
```

**Two display defects came out of that run** and are fixed in `5e69d18`:
`override` is exactly as long as the label column, so the value printed flush
against it (`override“Framed…`); and a passing claim carrying an override was
given a "— no reason recorded" clause, which reads as if the check had lost
something. `cea5171` is the third one Step 6 found: the stale banner came out
118 columns and wrapped, on the run where the operator is least inclined to read
carefully.

---

## 4. Files changed

| File | Commits |
|---|---|
| `src/agenticsocial/video/cli.py` (+469) | `8475e05`, `cea5171`, `5e69d18` |
| `src/agenticsocial/video/script.py` (+62/-6) | `b9140e7` |
| `tests/test_video_check.py` (new, 735 lines, 54 tests) | `c732805`, `8475e05`, `ef137e8`, `cea5171` |
| `tests/test_video_{script,plan,verify}.py` (fixtures, D-103) | `b9140e7` |

`verify.py` and `claims.py` are untouched. `git status --porcelain -- src tests`
is clean.

**Commit count.** The brief prescribes one per step and there are six. Steps 2
and 3 are one commit: one file, one display design, and splitting them after the
fact would be theatre. The extra two are products of the work rather than of the
plan — the sweep's test gaps, and Step 6's three display defects, which is where
running it for real earns its place.

---

## 5. Issues and concerns

### 5.1 Is the failure screen actionable? Mostly — with one real gap

Reading the block above knowing nothing about this codebase, you get: which beat
(number and type), which figures are missing, the exact quote they were checked
against, the file to open, and three named routes out. That is enough to act.
Three things I would still change:

1. **`beat` prints the concatenation, not prose.** `input 0.11 → 1.32 0.11 1.32
   output 0.33 → 3.96 …` is what §8.1's `text` field is (Task 1 §7.4 flagged
   this: the spec's example `text` is fluent prose no mechanical walk produces).
   It is honest — it is what the card renders — but it reads like a dump, and on
   a chart it is the least legible thing on the screen. `review`'s `_jump_row`
   summariser is better; the ledger's `text` is the wrong string to show a human
   and I used it because it is the one the record carries.
2. **The claim id is not a location.** `c-005 beat 4` is traceable, but nothing
   prints the path to `script.yaml` or a line number. On a nine-beat episode you
   count rows.
3. **`1` in the missing list is noise.** It comes from `per 1M tokens` in the
   footnote — Task 1's known handoff. It sits in the same list as the two
   genuinely fabricated figures with nothing distinguishing them, and the first
   time an operator works out that one of the five numbers is a unit label is
   the moment they start skimming the list.

**Does "recorded, not gated" read as a pass?** I think it reads correctly, and I
would not bet the product on it. It is a separate block, under a heading that
says *recorded, not gated*, with the reason in the heading and none of the
entries wearing a verdict. What it does **not** say is what the operator should
do about it — which is "glance at it, and only worry if a name is attributed to
the wrong thing". On this run the three entries were `New V4-Pro` (a kicker
fused to a product name), `USD` (a footnote word) and `Alibaba Qwen3.8-Max` (a
lab fused to its model) — all three tokeniser artefacts, exactly D-102's 35%,
and none of them a reason to touch the script. Three cosmetic entries per
episode is the dose at which people stop reading a block, so the risk is not
that it reads as a pass — it is that it stops being read at all, and pass 2's
"right number, wrong subject" case is the one thing in that block that would
ever matter.

### 5.2 What is still missing before an operator could use this unsupervised

- **`approve` does not exist.** `check` exits non-zero and nothing enforces
  that. Today an operator can ignore a red screen entirely; Phase 7 is what
  makes the exit code mean something.
- **Pass 2 does not exist.** Everything in Task 2's §6.1 list still ships:
  right number wrong subject, aggregation across quotes, `scale`, stale dates.
  The screen says `pass`, and `pass` means "pass 1 found nothing", which is a
  much weaker sentence than it looks.
- **No highlight.** §8.2 records `quote_span` into the original document and the
  terminal never uses it; the near-miss excerpt is the only place source text
  reaches the screen. That highlight is what §12 calls the single most important
  element in the product, and it is a UI, not a CLI.
- **The ledger is not bound to the script's bytes.** `_script_drift` compares
  claims, so an edit that changes nothing a claim carries — a `hold`, a
  `scale`, an act label — leaves the ledger looking current. `scale` in
  particular shifts every bar on a chart with no wrong digit anywhere (D-085
  #2). Phase 7's `script_sha256` is the right home for that, and it should be
  stricter than this display is.
- **One source per episode is the shape being tested.** The real run has one
  corpus document (`_pasted`); nothing exercises a five-source episode where
  `src` keys collide or one fetch 403'd.

### 5.3 Anything in Phase 5 I would not ship

**The `1` from `1M`.** It is a claim number by the settled rule, and every unit
label in the product manufactures one. On this episode it inflated a two-figure
fabrication into a five-figure list. I did not touch it — it is `claims.py`'s
rule and D-092 exists to stop exactly that kind of drive-by — but if the
override rate is ever measured, this is the first thing I would expect it to be
about.

**Entity atoms on screen at all.** I show them because hiding a recorded finding
is worse, and because pass 2's best case lives in that block. But D-102's own
numbers say 35% of them are artefacts, and I am showing an operator a list where
roughly one in three entries is our tokeniser's spelling. If Task 1's suggested
fix — break entity runs on commas, dashes and em dashes — lands, five of the
seven artefacts on this brief disappear and this block becomes worth reading.
Until then it is the weakest thing on the screen.

**What I am most confident about:** the numeric refusal, the quote under every
beat, and the staleness rule. What I am least confident about: that an operator
at 6am reads the difference between "recorded, not gated" and "checked".

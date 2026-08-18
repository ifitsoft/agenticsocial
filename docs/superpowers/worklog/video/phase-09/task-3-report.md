# Phase 9 · Task 3 — self-contained beats, the fifth overclaim, and a sixth

**Branch:** `feat/video-phase-09-adversarial` · **Head:** `717cc6f`
**Suite:** 1871 → **1888 passed** (17 new tests) · **Mutants: 15/15 killed**,
harness committed (`task-3-mutants.py`).
`git status --porcelain -- src tests skills` is **clean**.
`workspace/` is byte-identical to its backup and all three episodes are
unapproved and unedited.

---

## 1. The `_counts` fix — and the sixth instance, which exists

### 1.1 What was wrong

`review` printed pass 1's verdict over a pass-2 refusal in two places on one
screen, four lines under a table cell that had it right:

```
claims  24 pass   (checked 2026-08-18T00:09:04.924298-05:00)
  ! c-005 · beat 4 · pass
```

Task 1 converted `_claim_cell`. `_counts` and `_print_claim_summary`'s head line
were left tallying and printing `_verdict(record)` — the measurement.

### 1.2 The fix: one function, not three that agree

`verify.binding_verdict(record)` is new and is the only answer to *what does this
pipeline say about this claim*: pass 1's word unless pass 2 refuses;
`stale`/`expired`/`malformed` as themselves; `supported` reading as `pass`,
because the measurement is the stronger of the two statements and printing a
judgement over a measurement is the same overclaim pointing the other way.

Three call sites now derive from it and none reads the field:

- `_claim_cell` — the table cell (`binding_verdict(record) + "*"`),
- `_counts` — the counts line on **both** `review` and `check`,
- `_print_claim_summary`'s head line.

Pass 1's verdict is not dropped from the summary. It is **labelled**:

```
claims  23 pass · 1 unsupported   (checked 2026-08-18T00:09:04.924298-05:00)
  ! c-005 · beat 4 · unsupported · pass 1 pass
```

That is the distinction the whole task is about — `pass` printed bare is a claim;
`pass 1 pass` printed beside `unsupported` is a report. I also **tightened one
pre-existing assertion** that read a bare `pass` on that line: after this change
that substring is satisfied by the labelled form, so the test would have passed
for a reason its author did not intend (D-118).

### 1.3 How I proved no other call site is half-converted

I did not grep for the word `pass`; I enumerated every remaining reader of the
measurement in `cli.py` and classified each one. After the fix there are six:

| line | what it does | verdict |
|---|---|---|
| `_verdict` (322) | the accessor itself | — |
| head line (592) | prints it **labelled** `pass 1 <v>` beside the binding one | honest |
| `_next_step` (809) | branches on it — **after** every pass-2 state returns early | honest |
| `_claim_row` (851) | prints `pass · pass 2 refuted`, both words, always | honest |
| `_print_attested` (957) | a **filter** (`== "manual" and not is_blocking`) | honest |
| `_print_overrides` (1023) | **printed a verdict word about an overridden claim** | **the sixth** |

Outside `cli.py`: `approve.py` counts through `classify`, `render.py` produces no
verdicts, and the existing AST test still forbids any module but `verify.py` from
reading the `adversarial` field at all.

### 1.4 The sixth, found by looking

Five is a pattern, so I built the case the pattern predicts — a claim pass 2
**refuted** and a human cleared with §8.4's override — and read the screen:

```
  cleared by override — §8.4, NOT verified by anything. You are approving the
  sentence and the name on it:
    c-001    pass — “Framed as expectation, not fact; my read of three analyst
             quotes.” — Ali Abdukarim
```

The line whose entire job is *this claim needed a human's sentence to clear*
said **`pass`**. It is worse than the fifth in one respect: the fifth is a
summary an operator skims, and this is the line they read **while signing**, and
`pass` beside an override reads as *it was fine anyway* — which is precisely how
§8.4's sentences stop being read, and D-040's failure mode arriving at the one
place the project deliberately spends a human's attention.

Fixed in `717cc6f`, test first in `ab77f9a`, and mutant `T15` kills the
regression. It now reads `refuted — “…” — Ali Abdukarim`.

**Why the shape keeps recurring, stated so the seventh is cheaper to find.**
Every instance is the same physical situation: *a second checker was added, and
the screens that summarised the first were not moved.* It is never a wrong
computation — every one of these five lines was correct when it was written. So
the thing to search for after adding any new verdict-producing pass is not "bugs"
but **every line that prints or counts a verdict word**, and to require each of
them to derive from one function or to label its source out loud. That is now
enforced by an AST test over `_counts` and `_claim_cell` rather than by care.

---

## 2. The refutation-quoting decision, argued

**Decision: the CLI defends itself, with `--refutation-file` and `--risk-file`,
and it does not pretend to detect what it cannot see.**

The bug: `--refutation "…$1.32…"` records `.32`. The shell removes `$1` from a
double-quoted argument **one process before the CLI exists**. The write succeeds,
the verdict prints normally, and the ledger now quotes a price nobody wrote —
inside the one field that is supposed to be the *evidence* for a judgement.

Three options; I took the first and half of the third.

1. **A path the shell never touches.** `--refutation-file <path>` /
   `--risk-file <path>` read bytes off disk. `$`, backticks and apostrophes land
   byte-exact, and the class of defect is not detected but **made impossible**.
   Both fields refuse to be given twice (two sources for one value is D-059 at
   the input boundary: the silent winner is whichever the code reads second), an
   unreadable file is a named refusal rather than a traceback (D-035), and a
   missing refutation is still refused — naming both ways to supply one.
2. **Documentation only** (Task 2's `"$(cat …)"`). Correct, and it works — but it
   is a rule that depends on the reader knowing why, and Task 2's own §5.1
   prediction #3 was that the next runner types it inline anyway. D-109 is this
   project's evidence that a rule in front of someone is not a mechanism.
3. **Detect the damage.** The CLI cannot: the bytes that would prove it were
   destroyed upstream. What it *can* see is the residue — a figure with no
   leading digit, which is exactly what `$1.32` leaves behind. So it prints a
   **note, never a refusal**, conditional in its wording because the evidence is
   conditional: `.32` is a legal thing to write.

**Why the note is not a violation of "a tool must not say more than it knows".**
It says only what it observed (`the refutation contains \`.32\`, a figure with no
leading digit`), states the inference as a conditional (`if it was typed inline
as $n.32`), and points at the flag that removes the whole class rather than at a
fix for this instance. It is also **incomplete by construction and I am saying so
here rather than only in the docstring**: `--refutation "$1M"` expands to nothing
at all and leaves no residue for anything to find. A note that fired on `.32` and
silently missed `$1M` would be dangerous if it were sold as a check; it is sold
as a hint, and the file flags are the check. It is suppressed entirely when the
prose came from a file — a file cannot have been eaten by a shell, and a warning
that fires on the mandated path is a warning read on nothing but the healthy case
(that was the sweep's one survivor, and it is now pinned).

**What I did not do:** refuse an inline refutation outright. `judge` is also a
human's command, and a person typing a sentence about a beat they wrote should
not have to write a file first. The skill mandates the file flags for every
refuter reply, which is where the risk actually is.

Verified on the real episode, both paths, in one run (§5).

---

## 3. The storyboard rule, and the before/after

`skills/storyboard/SKILL.md` gains the rule in three places an author actually
reads: a **hard rule** at the top, **step 4.5** between planning the beats and
writing the YAML, and a **read-the-cards-alone pass** in step 9 before hand-off.
`title` and `signoff` assert nothing and are exempt, stated explicitly (R2's
negative half). Four worked before/afters from `2026-08-17c`; here are two:

**`c-019` — the cheapest fix there is.**

```yaml
# before                                # after
text: It was released on August 14, 2026.
text: Z.ai's GLM-5.3 was released on August 14, 2026.
quote: Z.ai's GLM‑5.3, released August 14, 2026     # unchanged — the name was
                                                    # already in the citation
```

**`c-005` — the archetype: the right price on nobody.**

```yaml
# before
  - type: kpis
    kicker: New pricing, from August 16
    items:
      - {prefix: "$", value: 1.32, label: per 1M input tokens}
      - {prefix: "$", value: 3.96, label: per 1M output tokens}
    quote: announced new pricing starting August 16 at about $1.32 / $3.96 per 1M tokens (in/out)

# after
  - type: kpis
    kicker: DeepSeek's flagship, new pricing from August 16
    items:
      - {prefix: "$", value: 1.32, label: per 1M input tokens (source says "about")}
      - {prefix: "$", value: 3.96, label: per 1M output tokens (source says "about")}
    quote: >-
      DeepSeek's 1.6T MoE flagship quietly moved from preview to general
      availability this week with upgraded agent capabilities, then announced new
      pricing starting August 16 at about $1.32 / $3.96 per 1M tokens (in/out)
```

Two moves, and the second is the one authors miss: the kicker gains the subject
**and the quote is widened left to the clause that names it**, so the subject is
inside the card's own citation. The labels carry the source's `about` — §6 is
about digits, a hedge is not a digit, and nothing upstream will ever tell you
that you dropped one. A refuter will.

`c-010` (a card whose quote already named Alibaba's Qwen3.8-Max, so only the card
changes) and `c-007` (a card that opened with `But`, and gained back the
counterweight *still substantially cheaper than many closed frontiers* it had
dropped) are worked in the file.

`skills/verify/SKILL.md` §6.5 now meets the widen-the-prompt instinct with the
reason rather than only the prohibition: widening **works**, which is the
failure — the wall disappears without one card changing and the pass thereafter
checks a story the orchestrator assembled. It names the cost of the other
alternative too (a 4-in-5 refusal rate teaches an operator to override
everything, including the true refusal in the same run) and points at
`storyboard` step 4.5 as the remedy that is already written down. Step 5 switches
to the file flags; step 6's "two lines on this screen are pass 1's" finding is
deleted, because it is fixed.

---

## 4. TDD and mutation evidence

**Tests first, committed before implementation**, skills separate, nothing
squashed. `976aacf` is thirteen failing tests:

```
FAILED …::test_the_claim_count_is_not_pass_1s_verdict_on_a_refused_claim - AssertionError: claims  3 pass
FAILED …::test_the_summary_counts_are_the_words_in_the_table_above_them - AssertionError: assert {'pass': 3} == {'refuted': 1... 1, 'pass': 1}
FAILED …::test_the_open_claims_own_line_says_the_verdict_that_binds - AssertionError: ! c-001 · beat 0 · pass
FAILED …::test_the_count_and_the_cell_come_from_one_function - AssertionError: _counts does not derive the verdict
FAILED …::test_the_screens_and_the_verdict_share_one_object - AttributeError: module 'agenticsocial.video.cli' has no attribute 'binding_...
FAILED …::test_the_binding_verdict_is_pass_2s_only_where_pass_2_refuses - AttributeError: module 'agenticsocial.video.verify' has no attribute 'bindi...
FAILED …::test_check_counts_the_binding_verdict_too - AssertionError: the-brief/2026-08-17 · 3 claims · 3 pass
FAILED …::test_a_refutation_reaches_the_ledger_byte_exact_from_a_file - AssertionError: Usage: root video judge [OPTIONS] EPISODE
FAILED …::test_the_residual_risk_can_come_from_a_file_too
FAILED …::test_the_judge_refuses_a_refutation_given_two_ways
FAILED …::test_the_judge_still_needs_a_refutation_one_way_or_the_other
FAILED …::test_an_unreadable_refutation_file_is_a_refusal_not_a_traceback
FAILED …::test_an_inline_refutation_that_lost_a_dollar_sign_says_so - AssertionError: no 'warning' line on the screen
13 failed, 64 passed
```

Every assertion names the line it means: `claims_head()` takes the line starting
`claims  `, `table_cell()` slices the claim column **by the header's own offset**,
`open_line()` takes the `! c-0NN` line, and `warning_block()` takes the warning
detail line plus its wrapped continuations — because `--refutation-file` also
appears in `--help`, and a screen-wide substring search would have passed on it.

**Mutation sweep — `PYTHONDONTWRITEBYTECODE=1`, harness committed** (D-118,
D-100). Verbatim:

```
baseline: PASS (1888 passed, 2 warnings in 19.31s)
  T1    killed    M1 — `_counts` reports pass 1's verdicts  [1 failed, 150 passed in 1.89s]
  T2    killed    M2 — the head line is converted, the table is left behind  [1 failed, 100 passed in 1.95s]
  T3    killed    M2, the other half — the table is converted, the head line is not  [1 failed, 100 passed in 1.87s]
  T4    killed    M3 — summary and table kept in sync by two code paths  [1 failed, 154 passed in 1.40s]
  T5    killed    the binding verdict is always the measurement  [1 failed, 100 passed in 1.00s]
  T6    killed    R1's positive half: a `supported` claim reads `supported`, not `pass`  [1 failed, 153 passed in 1.29s]
  T7    killed    a stale or expired judgement quietly restores `pass`  [1 failed, 156 passed in 1.57s]
  T15   killed    the sixth: the override line prints the measurement  [1 failed, 166 passed in 1.45s]
  T8    killed    M4 — the CLI sanitises the prose it was handed  [1 failed, 158 passed in 1.63s]
  T9    killed    M4 — the file is read, then the inline argument silently wins  [1 failed, 160 passed in 1.42s]
  T10   killed    an unreadable refutation file is a traceback, not a refusal  [1 failed, 162 passed in 1.59s]
  T11   killed    a verdict with no refutation at all is accepted  [1 failed, 161 passed in 1.44s]
  T12   killed    the lost-magnitude note never fires  [1 failed, 163 passed in 1.46s]
  T13   killed    the note fires on every refutation, so nobody reads it  [1 failed, 165 passed in 1.56s]
  T14   killed    the note is printed for prose that came out of a file  [1 failed, 164 passed in 1.47s]

15 killed, 0 survived, 15 total

M5 — the storyboard rule, checked as a file rather than a mutant:
  M5    ok       the rule is in the hard rules
  M5    ok       the rule has its own step
  M5    ok       `title` and `signoff` are exempt
  M5    ok       a before/after is shown
  M5    ok       c-005 is worked through
  M5    ok       c-007 is worked through
  M5    ok       c-010 is worked through
  M5    ok       c-019 is worked through
M5 ok
```

The brief's five mutants map to T1 (M1), T2/T3 (M2, both halves), T4 (M3), T8/T9
(M4) and the M5 block. **The first sweep scored 14/15 with T14 surviving** — no
test said the note stays quiet on file-sourced prose — which is committed as its
own test (`a33ee0f`) rather than quietly folded in.

---

## 5. The real episode, both fixes on one screen

`workspace/` was backed up first (`…/tmp/workspace-backup-20260818`, verified not
to exist beforehand); every command below ran against a **copy** under
`$AGSOC_WORKSPACE`, which was deleted afterwards. `diff -r workspace <backup>` at
the end: identical, and `agsoc video list` still reports `draft`, `in_review`,
`in_review`. No episode in `workspace/` was checked, judged, approved or
rendered.

`judge` with `--refutation-file`, then `review`:

```
the-brief/2026-08-17c · c-005 · pass 2 unsupported
  refuted  SUBJECT — the card names no model, product or vendor: a viewer sees "New pricing, from
           August 16" over $1.32 and $3.96 and can take it to be about any of the four models this
           document prices. CONTEXT — the source writes "at about $1.32 / $3.96 per 1M tokens
           (in/out)" and the card drops "about", asserting exact prices the source hedges. …
```

```
     4  01   kpis         4.4  unsupported  $1.32 per 1M input tokens · $3.96 p…  [_pasted]

claims  23 pass · 1 unsupported   (checked 2026-08-18T00:09:04.924298-05:00)
  ! c-005 · beat 4 · unsupported · pass 1 pass
```

The table cell, the count and the claim's own line now say the same word — and
`$1.32` reached the ledger with its dollar sign. The inline path, on the same
episode, in the same run:

```
the-brief/2026-08-17c · c-007 · pass 2 unsupported
  refuted  CONTEXT — the source writes about .32 / .96 per 1M tokens and the card drops the hedge.
  warning  the refutation contains `.32` — a figure with no leading digit. If it was typed inline as
           `${n}.32`, the shell removed the `$` and the digits before it and this record now quotes
           a number nobody wrote. `--refutation-file <path>` is not re-read by a shell
```

That is the bug reproduced and named on the screen of the command that committed
it. `approve`, `render`, `preview` and `post` were not run.

---

## 6. Files changed and commits

| commit | what |
|---|---|
| `976aacf` | **test** — 13 failing: the summary pinned to the table, a refutation pinned to its bytes |
| `57a43e6` | **fix** — `verify.binding_verdict`; `_claim_cell`, `_counts` and the head line derive from it |
| `00fee18` | **fix** — `--refutation-file` / `--risk-file`, the two refusals, the lost-magnitude note |
| `d04e4b5` | **docs(storyboard)** — the self-contained-beat rule and four worked before/afters |
| `998bc9a` | **docs(verify)** — §6.5's reason, the file flags, the fixed finding removed |
| `a33ee0f` | **test** — the sweep's survivor: the note is about the shell, not the prose |
| `ab77f9a` | **test** — the sixth instance, failing |
| `717cc6f` | **fix** — the override line names the verdict it overrode |

```
 docs/…/phase-09/task-3-mutants.py  | 163 +
 skills/storyboard/SKILL.md         | 130 +
 skills/verify/SKILL.md             |  59 +-
 src/agenticsocial/video/cli.py     | 156 +-
 src/agenticsocial/video/verify.py  |  26 +
 tests/test_video_adversarial.py    | 391 +-
```

No new dependencies, no network, no LLM in the CLI.

---

## 7. Issues and concerns

1. **The self-contained-beat rule is written but has never been executed.** Every
   before/after in §4.5 is reasoned from the real ledger and the real source, and
   **not one of them has been run through `check`.** The `c-005` "after" widens
   the quote to a span I pasted from `_pasted.txt`, and the label text
   `per 1M input tokens (source says "about")` adds no figure, so I expect both
   to pass — but expecting is not checking, and doing it properly means writing
   to a real episode. Whoever next drafts an episode is the first real test of
   this rule, and if the `c-005` "after" refuses, the skill's worked example is
   wrong in the most damaging possible place.
2. **The rule is stated for authors, and nothing enforces it.** That is
   deliberate — D-102 refused to gate entity presence at a 62% refusal rate, and
   gating "does this card name a subject" is the same arithmetic with a worse
   extractor. But it means the rule's only enforcement is pass 2, which costs 24
   subagents and runs after the script is written. A cheap **advisory** line in
   `check` — *"n asserting beats name no capitalised subject"*, reported like
   `entities_missing`, refusing nothing — would move the feedback from minutes
   to seconds. I did not build it: it is a new screen with a new false-positive
   profile and it was not in the brief.
3. **The lost-magnitude note has a known blind spot, by construction.** `$1M`,
   `$3B` and any `$<digits><letter>` expand to nothing and leave no residue. The
   note cannot see them and does not claim to; the file flags are the real fix,
   and the skill now mandates them. If a future reader upgrades that note into a
   *check*, they will have built exactly the tool this project keeps writing
   decisions about.
4. **`supported` never appears in the counts line**, because a `supported` claim
   reads as `pass`. That is the argued behaviour (§1.2) and it means the counts
   line alone does not say whether pass 2 ran — the `pass 2  n of N claims
   judged` block four lines below does, and it prints even at zero. I believe
   this is right, but it is the one place where a summary is deliberately silent
   about something, so it is worth a second opinion.
5. **The `T4` mutant is the one I would watch.** It re-implements the binding
   rule inline in `_counts` — identical output, two code paths — and it is killed
   only by the AST test. If someone later refactors `_counts` in a way that
   inlines the derivation for a good reason, that test will look like pedantry.
   It is not: it is the only thing standing between this project and a seventh
   instance, and the docstring on `binding_verdict` says so.
6. **I judged claims in a scratch copy under a `--by` that names it a replay.**
   The `c-005` refutation in §5 is my transcription of what Task 2's real refuter
   found, not a fresh blind judgement — the copy was deleted, nothing reached
   `workspace/`, and I am recording it here so no later reader mistakes that run
   for a pass-2 verdict of record.

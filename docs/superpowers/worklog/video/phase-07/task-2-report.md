# Phase 7 · Task 2 — the override applied, and drift that names itself

**Branch:** `feat/video-phase-07-approve` · **Baseline:** 1658 tests → **1705**
**Mutation score:** **23/23 killed, 0 survivors** (12 from the brief's table, 11
my own — 3 of mine survived the first run and are reported as survivors, not as
kills)
**Commits:** `165cd5e` (tests A, red) · `7783145` (the override) · `1ce8fa9`
(tests B, red) · `1fc0a90` (the digest and the drift check) · `3a941a3` (three
survivors) · `876d26f` (banner position). Not squashed.

---

## 1. The stale-override decision: **it warns, and it never refuses**

An override on a claim that now passes anyway is reported, by id, under a
heading that says to delete it — on `check`, on `review`, and nowhere in the
exit code.

**Why it is reported at all.** §8.4's whole mechanism is an asymmetry: *passing
verification is automatic; bypassing it costs you a written sentence with your
name on it.* The cost is only real while the sentences are read. A file
accumulating overrides that bypass nothing is a file where the next reader skims
the block — and the one that matters is in that block. This is the same failure
D-040 names from the other end: there, a checker that cries wolf trains an
operator to override reflexively; here, overrides that mean nothing train a
reviewer to skip them. Both end with a written sentence nobody reads.

**Why it is not a refusal.** The remedy for a stale override is *delete the
paragraph you wrote*. A gate that demands that has inverted the asymmetry it
exists to enforce: bypassing verification would still cost one sentence, and
**un**-bypassing it would cost a refused approval and an edit. It would also
punish the good case — an operator who fixed the figure and left the note
explaining why it was ever wrong is doing the right thing in the wrong order.

**The consequence in `classify`, which is the load-bearing half:** the
measurement is consulted **before** the override.

```
pass          + override  ->  verified     (the override is stale, and named)
manual+attest + override  ->  attested     (the attestation stands on its own)
fail          + override  ->  overridden
no_source     + override  ->  overridden
unknown       + override  ->  overridden
fail          + malformed ->  open
```

Ordering it the other way — override first — makes a passing claim report as
`overridden` for as long as the note sits in the file, which means the only way
to make a verified claim read as verified is to delete a sentence. That mutant
is **O1**, and it is killed.

---

## 2. `script_sha256`: one key, two meanings — the approval keeps the name

Task 1 flagged it: `plan.json` carried `script_sha256` over the **whole file**
(metadata document included) while the approval carries it over the **beats
document**. Two files, one key, two answers — the D-036 pattern, and these two
are exactly the pair someone compares.

**The approval keeps `script_sha256`. `plan.json`'s becomes
`script_file_sha256`.** Three reasons:

1. **§10 names the field for the approval.** *"`approve` records
   `script_sha256`, and `render` refuses if the script has changed since
   approval."* The spec's name belongs to the spec's mechanism.
2. **It is the one an operator reads.** It is printed on the approve screen, in
   the drift message, and it sits in the committed diff of `script.yaml`.
   `plan.json` is machine-to-machine — written by `plan.py`, read by
   `render.mjs`.
3. **The new name is more accurate than the old one.** `plan.json`'s digest was
   always over the file, never over "the script" as the approval means it.
   `script_file_sha256` says what it measures.

Renamed in `plan.py`, in `render.py`'s `-metadata comment=` (the mp4 tag — the
one place the two digests would have been put side by side and compared), and in
their tests. **Nothing compares the two**, and a mutant that puts both keys back
under one name in both files is **O11**, killed.

Why the approval's digest still covers only the beats document, in a comment
where the next reader will look (`beats_sha256`, `approval_drift`): the approval
record is written **into** the bytes a whole-file digest would cover, so it has
no fixed point, and `approved → rendering` — Phase 8's own first move — would
invalidate the approval it is acting on. The cost is that the metadata document
is outside the hash, which is why `pace` is compared separately and named
separately, and why §6 below lists what is still uncovered.

---

## 3. TDD evidence and the mutation score

**Part A: tests first, red, committed** — `165cd5e`, before any implementation:

```
18 failed, 128 passed
FAILED tests/test_video_approve.py::test_an_override_clears_the_claim_it_names
  - AssertionError: the override clears the claim on check too
FAILED tests/test_video_approve.py::test_an_overridden_claim_is_not_verified
  - AssertionError: assert 'open' == 'overridden'
FAILED tests/test_video_approve.py::test_only_verify_reads_a_claims_override
  - AssertionError: {'cli.py': 3}
```

**Part B: tests first, red, committed** — `1ce8fa9`:

```
17 failed, 209 passed
FAILED tests/test_video_approve.py::test_editing_only_a_charts_scale_is_caught
  - AttributeError: module 'agenticsocial.video.approve' has no attribute 'approval_drift'
FAILED tests/test_video_plan.py::test_metadata_and_beats_come_from_the_same_read
  - KeyError: 'script_file_sha256'
FAILED tests/test_video_render.py::test_the_mp4_records_the_script_hash
  - AssertionError: assert 'script_file_sha256=' in 'ffmpeg -y -framerate 30 -i...'
```

Two test edits made during implementation, stated rather than buried: the
"only verify reads the override field" test was narrowed from *any* `"override"`
string constant to an actual **read** of the field (`record["override"]`,
`.get("override")`), because the display label `override` is a legitimate
constant in `cli.py`; and two tests built an unattested `manual` beat by writing
`attest: "  "` into `script.yaml`, which the loader correctly refuses (D-103's
sibling rule), so they now blank it in `claims.json` — the artifact the gate
actually reads — exactly as Task 1's own unattested-manual test does.

### The sweep

`PYTHONDONTWRITEBYTECODE=1` (D-100), full suite per mutant, source restored
after each, anchors asserted unique so a mutant that fails to apply cannot be
scored as killed. Harness and raw logs:
`/Volumes/…/jobs/9a014c11/tmp/t2/mutate2.py`, `mutation-01.txt` (first run),
`mutation-final.txt`.

| # | Mutant | Result |
|---|---|---|
| M1 | override clears the whole beat (every claim of that beat type) | killed |
| M2 | override clears the episode | killed |
| M3 | blank `reason` or `by` accepted | killed |
| M4 | overridden claim reported as `verified` | killed |
| M5 | overridden claim still blocks | killed |
| M6 | drift undetected | killed |
| M7 | drift detected but not named | killed |
| M8 | `scale`-only edit undetected (claims compared, not bytes) | killed |
| M9 | digest taken over the whole file — **both halves, consistently** | killed |
| M10 | a second verdict path: the CLI reads the override itself | killed |
| M11 | override rate not reported | killed |
| M12 | re-approval after an edit impossible | killed |
| O1 | the override is consulted **before** the measurement | killed |
| O2 | a stale override is not distinguished from an applied one | **survived → fixed** |
| O3 | the approval's override list is built from the raw field | killed |
| O4 | drift reads the `Episode` it was handed, not the file | **survived → fixed** |
| O5 | drift ignores `pace`, which the digest cannot cover | killed |
| O6 | the tally counts an overridden claim as verified | killed |
| O7 | the drift banner fires on every approved episode | killed |
| O8 | drift compares only the first 8 hex characters | **survived → fixed** |
| O9 | an episode with no approval record reads as no drift | killed |
| O10 | an unhashable script reads as no drift | killed |
| O11 | the plan's whole-file digest renamed back onto the approval's key | killed |

**23/23 after the fixes; 20/23 on the first run.** The three survivors:

- **O2 was a real defect, not a missing test.** `verify.stale_override` decided
  whether a written sentence is doing any work, and `_print_overrides` decided it
  again inline. Neither was wrong. Two statements of one rule is the D-036
  pattern, sitting on the screen where the rule decides what an operator reads —
  which is where the last three overclaims have come from. The screen now asks
  the predicate (`3a941a3`).
- **O4 was a test that could not reach its own mutant.** My drift-from-disk test
  held an `Episode` loaded *after* the approval, so the snapshot and the file
  agreed and a mutant reading `episode.meta` passed it. The case that separates
  them is a **re-approval**: an object holding the old signature must not report
  drift against a file that has since been signed again. Same family as D-035 —
  the harness could not observe the dimension the bug lived in.
- **O8 was untested arithmetic.** A comparison that reads the first eight hex
  characters looks right in every test written with real digests. Pinned with a
  digest that differs nowhere else (last character flipped).

**Two honest caveats on the number.** M1 and M2 are less independent than the
table implies: with one claim per beat, "clears the beat" and "clears the claim"
are the same set, so M1 is implemented as the nearest *observable* over-reach —
an override clearing every claim of the same beat **type**. And the score is a
statement about my mutants: I still have no harness that crashes between two
writes, so "the record and the status land together" remains argued from the code
(one `atomic_write`) rather than measured.

---

## 4. Step 6 — end to end, throwaway workspace

`$AGSOC_WORKSPACE=/Volumes/…/jobs/9a014c11/tmp/t2/demo/workspace`. Five beats:
title, statement, `kpis` with one figure typed `$3.99` where the source says
`$3.96`, a `jumpChart` at `scale: 5`, signoff.

### Screen 1 — a failing claim blocks

```
$ agsoc video check 2026-08-18 --series the-brief            # EXIT=1
the-brief/2026-08-18 · 3 claims · 2 pass · 1 fail

    c-002   beat  1  statement  pass
 !  c-003   beat  2  kpis       fail
    c-004   beat  3  jumpChart  pass

 !  c-003   beat  2  kpis       fail
      why      the quote does not contain 3.99 by value
      beat     $1.32 per 1M input tokens $3.99 per 1M output tokens
      quote    “about $1.32 / $3.96 per 1M tokens”
      src      sources/_pasted.txt
      fix      correct the figure, widen `quote:` so it covers it, or write a `claim_override`
               (reason + by) in script.yaml
...
1 of 3 claims not verified — this episode is not approvable until they clear

$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"   # EXIT=1
the-brief/2026-08-18 · NOT approved — 1 of 3 claims are open

 !  c-003   beat  2  kpis       fail
      why      the quote does not contain 3.99 by value
      fix      correct the figure, widen `quote:` so it covers it, or write a `claim_override`
               (reason + by) in script.yaml

run `agsoc video check 2026-08-18 --series the-brief` for the full detail. Nothing moved; the
episode is still in_review

status on disk:  status: in_review
```

### Screen 2 — an override with a reason clears it

The whole edit is eight lines in `script.yaml`, and it is a diff you commit:

```yaml
    claim_override:
      reason: >-
        The $3.99 is our own rounded list price for the annual plan, not the
        article's per-token figure; the ladder beside it uses the article's
        numbers unchanged.
      by: Ali Abdukarim
```

```
$ agsoc video check 2026-08-18 --series the-brief             # EXIT=0
the-brief/2026-08-18 · 3 claims · 2 pass · 1 fail

    c-002   beat  1  statement  pass
  * c-003   beat  2  kpis       fail
    c-004   beat  3  jumpChart  pass

  cleared by override — §8.4, NOT verified by anything. You are approving the sentence and the name
  on it:
    c-003    fail — “The $3.99 is our own rounded list price for the annual plan, not the article's
             per-token figure; the ladder beside it uses the article's numbers unchanged.” — Ali
             Abdukarim

  override rate 1 of 3 claims (33%) — D-040: a high rate means the checker is wrong, not the
  operator
...
2 verified · 1 cleared by override, NOT verified (§8.4) · 3 claims, none open

$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"   # EXIT=0
the-brief/2026-08-18 · approved
      by       Ali Abdukarim
      at       2026-08-18T01:13:44-05:00
      script   sha256 3a2360aa16fe984413ddcda14df4397f34c64175def452314a537f0782b9cd1a (the beats
               document)
      claims   2 of 3 verified · 1 cleared by override, not verified (§8.4), checked
               2026-08-18T01:13:30.335230-05:00
      override c-003 “The $3.99 is our own rounded list price for the annual plan, not the article's
               per-token figure; the ladder beside it uses the article's numbers unchanged.” — Ali
               Abdukarim
      override rate 1 of 3 claims (33%) — D-040: a high rate means the checker is wrong, not the
               operator
      next     edit the beats and this approval no longer describes them — `script_sha256` is what
               says so
```

and in `script.yaml`, the record the bypass leaves behind:

```yaml
approval:
  by: Ali Abdukarim
  at: '2026-08-18T01:13:44-05:00'
  script_sha256: 3a2360aa16fe984413ddcda14df4397f34c64175def452314a537f0782b9cd1a
  pace: 1.0
  claims_checked_at: '2026-08-18T01:13:30.335230-05:00'
  corpus_sha: 227be06e985cf44e1887cebf9317806396dd00aa46e143c4182d8c6f9ad1d176
  claims:
    total: 3
    verified: 2
    attested: 0
    overridden: 1
  overrides:
  - id: c-003
    by: Ali Abdukarim
    reason: The $3.99 is our own rounded list price for the annual plan, not the article's
      per-token figure; the ladder beside it uses the article's numbers unchanged.
```

### Screen 3 — editing `scale` after approval is caught and named

The entire edit, and it changes no number anyone reads:

```diff
62c62
<     scale: 5
---
>     scale: 25
```

Every bar on that chart is now drawn at a fifth of its previous length. And:

```
$ agsoc video check 2026-08-18 --series the-brief             # EXIT=0
the-brief/2026-08-18 · 3 claims · 2 pass · 1 fail
the approval on this episode no longer describes it — the beats document has changed: the approval
covers sha256 3a2360aa16fe984413ddcda14df4397f34c64175def452314a537f0782b9cd1a, the file on disk is
sha256 74fa3f1effda13752b5b043718ce0069dc9381f5cad2c88adecce4d3a02e7d22 — approved by Ali Abdukarim
at 2026-08-18T01:13:44-05:00. Re-run `agsoc video check` and approve again, or put the script back

    c-002   beat  1  statement  pass
  * c-003   beat  2  kpis       fail
    c-004   beat  3  jumpChart  pass
```

`review` prints the same line from the same function, under its own head.

**What every other control said about that edit**, measured rather than asserted:

```
stale_reason           : None            <- the ledger is current, and correctly so
corpus_sha             : 227be06e985cf44e (unchanged)
verdicts               : [('c-002','pass'), ('c-003','fail'), ('c-004','pass')]   (identical)
approval_drift         : DETECTED
```

`claims.json` is byte-identical after the edit. Nothing about numbers, sources,
quotes or the corpus moved. **Only the digest can see it**, which is the sentence
Phase 5 wrote this task to make true.

### The operator's workspace

Backed up first, to a path that did not already exist and whose top level was
inspected to be `config.toml inbox series sources voice.md` — not a nested older
backup (Task 1's trap). Never approved, never edited. All three episodes still
pass, and the tree is byte-identical:

```
2026-08-17   EXIT=0  ::  6 verified · 1 attested by hand, NOT verified (D-088) · 7 claims, none open
2026-08-17b  EXIT=0  ::  22 claims verified, none open
2026-08-17c  EXIT=0  ::  24 claims verified, none open

$ diff -rq workspace …/t2/ws-backup   ->  OPERATOR WORKSPACE UNCHANGED
```

---

## 5. Files changed

| File | Change |
|---|---|
| `src/agenticsocial/video/verify.py` | `override_state`, `stale_override`, `claim_tally`; `classify` gains `overridden` |
| `src/agenticsocial/video/approve.py` | the record carries the tally and every cleared claim; **new** `approval_record`, `approval_drift` |
| `src/agenticsocial/video/cli.py` | `_print_overrides`, `_override_rate`, `_echo_drift`; `override_state`/`stale_override` re-exported as the same objects; summary and approve screen count four states |
| `src/agenticsocial/video/plan.py` | `script_sha256` → `script_file_sha256` (D-036) |
| `src/agenticsocial/video/render.py` | the mp4's `comment=` metadata follows the rename |
| `tests/test_video_approve.py` | +47 tests (73 total in file) |
| `tests/test_video_check.py` | the overridden claim no longer blocks — the display assertions get stronger, not weaker |
| `tests/test_video_plan.py`, `tests/test_video_render.py` | the rename |

Commits: `165cd5e` → `7783145` → `1ce8fa9` → `1fc0a90` → `3a941a3` → `876d26f`.
`git status --porcelain -- src tests` is clean. 1705 tests pass.

---

## 6. Issues and concerns

### 6.1 What still slips past the digest — an enumeration, not a reassurance

An approval binds **the beats document's bytes** and **`pace`**. Everything else
in the render is outside it. Named, in the order I would fix them:

1. **`series.toml`'s `design` block — and it repaints every frame.** Palette,
   accent, type family and type scale go straight into `plan.json` (`"design":
   dict(series.design)`) and are drawn on every beat. An operator can approve an
   episode, change the series accent from red to green, and render something the
   approver never saw, with a valid approval and no drift. It is a series-level
   file, so binding it to an episode approval is a design question, not a
   one-liner — but **it is the largest hole and it is bigger than the `scale`
   case that motivated this task.**
2. **`series.name` and `series.byline`.** Rendered at 150px on the title and
   signoff cards. Same file, same hole.
3. **The corpus.** `approve` records `corpus_sha` and **`approval_drift` does not
   compare it.** That is deliberate rather than forgotten: the corpus half is
   `verify.stale_reason`'s question, and duplicating it inside drift is the
   second-path shape this task spent its budget avoiding. The consequence is a
   requirement on Phase 8, stated in 6.2, not a property of `approval_drift`.
4. **The output format.** `--format wide` renders a layout no approval mentions.
   §9 argues formats are frame-identical in time, so this is the mildest of the
   four, but the approval says nothing about which of them was reviewed.
5. **The engine itself.** `engine/*.js` is code, versioned in this repo and not
   in the workspace; nothing ties a render to the engine that produced it.
6. **`claims.json` after the fact.** The approval names the counts and the check
   timestamp, so a post-approval hand edit of the ledger is *visible* by
   comparison — but nothing compares them.

### 6.2 What Phase 8's `render` must call, given the above

`approval_drift` alone is **not** the render gate. The gate is three checks, and
they answer three different questions:

```
assert_transition(disk status, RENDERING, VIDEO_TRANSITIONS)   was it ever approved?
approve.approval_drift(episode)                                is the approval still about these bytes?
verify.stale_reason(episode, verify.read_ledger(episode))      is the check still about this corpus?
```

Status alone is insufficient (an edited script still says `approved`), and drift
alone is insufficient (an episode that was never approved must not render, and
`approval_drift` says so by failing closed, but the transition table is the
authority on that). This is the same shape as Task 1's finding: the gate must
re-read every authority itself.

### 6.3 Is the override screen honest — could an overridden episode read as clean?

Adversarially, the four places an operator could be misled, and what each says:

| Where | What it says |
|---|---|
| The table row | `  * c-003   beat  2  kpis   fail` — the **measured verdict**, never `pass`, plus a `*` |
| `check`'s block | `cleared by override — §8.4, NOT verified by anything. You are approving the sentence and the name on it:` then the claim id, the verdict, the sentence, the name |
| `check`'s last line | `2 verified · 1 cleared by override, NOT verified (§8.4) · 3 claims, none open` |
| `approve`'s screen | `2 of 3 verified · 1 cleared by override, not verified (§8.4)`, then the claim and the sentence, then the rate |
| `script.yaml` | `overridden: 1` and an `overrides:` list with the id, the name and the reason |

**The exit code is the one thing that cannot distinguish them**, by design:
`check` exits 0 on an overridden episode because it is approvable, and an exit
code that disagreed with the gate would be a second verdict path. An agent that
runs `check`, reads `$?` and stops learns nothing about the override — the same
limitation §11 accepts for runtime, and the reason every count on every screen is
worded `NOT verified` rather than left to the number.

**The residual dishonesty I could not remove:** the word "approved". `agsoc video
list` shows `approved` for an episode whose claims were cleared by hand, and
`script.yaml` says `status: approved` beside `overridden: 1`. The status is
per-episode and the override is per-claim, so no status value can carry it. The
record beside it does, and it is in the diff.

### 6.4 Carried forward from Task 1, still true

- **Nothing un-approves.** `approved → in_review` exists in the table and no
  command walks it; the way to re-approve after an intentional edit is to hand
  edit `status: in_review` (tested, `test_re_approving_after_an_intentional_edit_
  clears_the_drift`). When a `revoke` lands, it must clear the `approval:` block
  in the same gated write, or a file will say `in_review` and carry a signature.
  Until then, the drift banner is what stops a stale signature from reading as a
  current one.
- **`agsoc init` ignores `$AGSOC_WORKSPACE`** — it takes a positional path. I
  passed the path explicitly rather than relying on the environment.
- **Runtime is still a report, not a gate.** The demo episode approved at 20.0s
  against 120±8s, `OUT OF TOLERANCE`, and both screens say so loudly. Unchanged
  by this task and still worth a decision before Phase 8 refuses to render one.

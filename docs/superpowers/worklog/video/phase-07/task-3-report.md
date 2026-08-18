# Phase 7 · Task 3 — an approval covers the frame, not just the script

**Branch:** `feat/video-phase-07-approve` · **Baseline:** 1705 tests → **1737**
**Mutation score:** **18/18 killed, 0 survivors** (8 from the brief's table, 10
my own; two of mine were written *before* the sweep, for survivors I predicted —
said plainly in §3)
**Commits:** `59a57d7` (tests, red) · `5ce94b2` (the derivation and the third
answer) · `e35253a` (two more tests) · `518c014` (two message defects the demo
found). Not squashed.

The hole, closed: `series.toml`'s `[design]` table is copied whole into
`plan.json` and repaints every frame of every episode in the series; `approve.py`
never read that file. Approve, change `accent`, render — and you had shipped a
frame the approver never saw, with a valid approval and no drift.

---

## 1. The scope, and what I left out on purpose

**Covered — the values `plan.py` copies out of `series.toml`:**

| Input | Where it lands | What it does to the frame |
|---|---|---|
| `[design]` (the **whole table**) | `plan["design"]` | the palette, on every frame |
| `[series] name` | `plan["series_name"]` | drawn at 150px on title and signoff |
| `[series] byline` | `plan["byline"]` | drawn beside it |
| `[[structure.acts]]` labels | every beat's `act_label` | the act chip on every beat |

**Not covered, and each for a reason, not by omission:**

- **`cadence`, `register`, `target_sec`, `tolerance_sec`, `formats.enabled`,
  `warm_acts`, act `beats` budgets.** None is copied into `plan.json`. `register`
  selects voice rules *before* the script exists; `target_sec` changes what
  `check` says about runtime and nothing about a rendered frame. Crying drift on
  these is D-040's failure from the other end: an alarm that fires on routine
  editing is one an operator has learned to ignore by the time it is true.
  Six of them are pinned as a parametrized negative test.
- **`slug` and `dir`.** `build_plan` reads both, and both are classified
  `identity`: they say *where the episode lives on this machine*, not what it
  looks like. Covering `dir` would make moving a workspace read as a change to
  the video.
- **The bytes of `series.toml`.** The record holds **values**, so a comment or a
  reordering is not an approval-invalidating event (pinned). It is also what
  lets the drift message name the token that moved instead of two digests.

**Deliberate over-coverage, stated rather than discovered later:** `act_labels`
resolves *every* declared act, so rewording the label of an act no beat uses is
drift. And `type_family`/`type_scale` are copied into `plan.json` but the engine
ignores them today (`planbuild.js`'s `PLAN_TOKENS` maps the six colours only, and
neither string appears anywhere in `engine/`) — so an approval binds two values
that currently reach no pixel. Both are the safe direction of the error, and the
second one is really a note about the *engine*: see §6.3.

**One brief/code mismatch, flagged.** The brief says "`target_sec` changes pacing
but is already visible in `review`". In the code `pace` is a `script.yaml` value;
`series.target_sec` is only the tolerance `check_runtime` reports against and
reaches no plan field. So it is out of scope for a stronger reason than the brief
gives: it is not pacing at all. `pace` itself has been covered since Task 2.

---

## 2. How a new design key stays covered — and what happens when it cannot be

**The `[design]` table is never enumerated.** `plan.py` copies it whole
(`dict(series.design)`), so the approval covers a token added tomorrow with no
edit to any list, in this task or any other. `test_a_design_token_nobody_has_
heard_of_yet_is_covered` adds `halo` to `series.toml`, approves, changes it, and
requires the drift message to name `halo`; a hardcoded token list is mutant M3
and dies on it.

**The wider set is read out of `build_plan`'s AST**, not written down:

```python
plan.series_reads()  ->  frozenset({'acts', 'byline', 'design', 'dir', 'name', 'slug'})
```

AST, not a regex: `build_plan`'s comments say "series.toml" all over, and a text
scan would invent an attribute called `toml` and then refuse to approve anything
because nobody had classified it.

**What is classified is a policy, and being unclassified is a refusal (D-096).**
`SERIES_ATTR_COVERAGE` maps each *derived* attribute to `frame` or `identity`.
The day someone adds `series.tagline` to `build_plan`, the derivation sees it,
nothing classifies it, and `approve` refuses:

```
the-brief/2026-08-18 · NOT approved — plan.py copies `series.tagline` into plan.json and
nothing says whether it reaches the frame, so an approval cannot honestly claim to cover it.
Classify it in plan.SERIES_ATTR_COVERAGE as 'frame' (an approval must bind it) or 'identity'
(it names where the episode lives, not what it looks like). Refusing rather than skipping: a
value nobody classified is not a value nobody has to think about
```

**The two ways a read could evade an AST scan are refused, not left as holes:**
binding `series` to another name (`s = series`), and handing the whole `Series`
to a helper that is not scanned. Both raise `PlanError` from `series_reads_of`,
with `_SERIES_HELPERS` naming the one helper (`act_labels`) that *is* scanned.
`test_series_is_never_aliased_or_handed_whole_inside_build_plan` runs the scanner
over two functions written to evade it.

**And a value that cannot be compared is refused too**, rather than dropped:

```
the-brief/2026-08-18 · NOT approved — series.toml: [design] refreshed = datetime.date(2026, 8, 18)
holds a value an approval cannot compare (Object of type date is not JSON serializable). Dates,
times and non-finite numbers have no comparable form here; write it as a string. Refusing rather
than dropping it: an approval that silently skips a value covers less than it says it does
```

**The residual gap, named:** the derivation is over `build_plan` and the helpers
it declares. A *different* function that wrote a series value into a plan without
going through `build_plan` would be outside the scan — as would a read reached by
an expression the AST walk does not model (`getattr(series, name)`,
`vars(series)`). `series_reads()`'s pinned value is the tripwire: any of those
changes the plan without changing the frozenset, and the test that asserts the
frozenset is the thing that fails.

**Where the record and the plan meet.** `test_the_plan_and_the_approval_carry_the_
same_design` builds a real plan and compares `plan["design"]`, `plan["series_name"]`
and `plan["byline"]` against the record on disk. If those two ever diverge, the
approval is a signature on a document nobody renders.

---

## 3. TDD evidence and the mutation score

**Tests first, red, committed** — `59a57d7`, 27 tests, before a line of
implementation:

```
24 failed, 100 passed
FAILED tests/test_video_approve.py::test_changing_an_accent_after_approval_is_drift
  - AssertionError: assert None is not None
FAILED tests/test_video_approve.py::test_the_covered_set_is_read_out_of_plan_pys_own_source
  - AttributeError: module 'agenticsocial.video.plan' has no attribute 'series_reads'
FAILED tests/test_video_approve.py::test_an_unclassified_series_read_refuses_the_approval
  - AttributeError: module 'agenticsocial.video.plan' has no attribute 'SERIES_ATTR_COVERAGE'
```

The three that passed on the red run are R1's **negative** half (the advisory
fields), which is the point of writing them: they must pass before and after.

Two test defects fixed during implementation, stated rather than buried: the
act-label test replaced the label `01 — The headline`, which is also the text of
the **commented-out example** in the scaffold's own `series.toml`, so the edit
was landing on a comment; and the stale-corpus test needed `replace=True` on
`corpus.write_document`, the same way `test_video_check.py`'s does.

### The sweep

`PYTHONDONTWRITEBYTECODE=1` (D-100), full suite per mutant, source restored after
each, every anchor asserted unique so a mutant that fails to apply cannot be
scored as a kill. Harness and raw log:
`/Volumes/…/jobs/9a014c11/tmp/t3/mutate3.py`, `mutation-final.txt`.

| # | Mutant | Result | Killed by |
|---|---|---|---|
| M1 | a design change is undetected | killed | `test_changing_an_accent_after_approval_is_drift` |
| M2 | any `series.toml` edit cries drift (bytes, not values) | killed | `test_an_approval_binds_the_bytes_it_approved` |
| M3 | the covered tokens are hardcoded, so a new one is uncovered | killed | `test_a_design_token_nobody_has_heard_of_yet_is_covered` |
| M4 | an unclassified input is skipped silently, not refused | killed | `test_an_unclassified_series_read_refuses_the_approval` |
| M5 | design drift reported as script drift | killed | `test_the_design_drift_names_the_value_that_moved` |
| M6 | design drift swallows the stale-corpus answer | killed | `test_a_stale_corpus_is_still_its_own_answer_after_a_design_change` |
| M7 | a design change permanently blocks re-approval | killed | `test_re_approving_after_a_design_change_clears_the_drift` |
| M8 | the drift check reads a cached series, not the file | killed | `test_changing_an_accent_after_approval_is_drift` |
| O1 | the alias / handed-whole guard is dropped | killed | `test_series_is_never_aliased_or_handed_whole_inside_build_plan` |
| O2 | a value that cannot be compared is hashed as nothing | killed | `test_a_design_value_that_cannot_be_compared_refuses` |
| O3 | the `[design]` tables compared whole, so nothing is named | killed | `test_the_design_drift_names_the_value_that_moved` |
| O4 | only `[design]` covered; name, byline, act labels are not | killed | `test_changing_the_series_name_after_approval_is_drift` |
| O5 | the covered set includes the identity attributes | killed | `test_an_attested_manual_approves` |
| O6 | the record keeps a digest instead of the values | killed | `test_the_design_drift_names_the_value_that_moved` |
| O7 | an unreadable `series.toml` reads as no drift | killed | `test_an_unreadable_series_toml_is_drift_not_a_traceback` |
| O8 | an approval that records no design reads as no drift | killed | `test_an_approval_that_records_no_design_is_drift` |
| O9 | the approve screen does not say the design is covered | killed | `test_the_approve_screen_says_the_design_is_covered` |
| O10 | the refusal arrives after the status has moved | killed | `test_an_approval_binds_the_bytes_it_approved` |

**18/18, zero survivors — and four honest caveats on the number:**

1. **Two of my tests were written before the sweep, for survivors I predicted**
   (`e35253a`): a comparison that walks only the keys present in both files
   cannot see a **deleted** token, and one that compares the `[design]` tables
   whole names every token on every change. O3 and the deletion case would have
   survived the sweep as written; I closed them first and am reporting them as
   predicted survivors, not as kills the sweep found. That is the same
   disclosure Task 1 made about its O5.
2. **O5 is killed by an unrelated-looking test** (`test_an_attested_manual_approves`)
   because putting `dir` into the covered set makes the record hold a `PosixPath`,
   which YAML then round-trips as a Python object tag — the failure is real and
   arrives early, but it is not the failure I designed the mutant to expose. The
   test that *states* the property is `test_the_covered_set_is_read_out_of_plan_
   pys_own_source`, and it fails under the same mutant.
3. **O10 is likewise killed obliquely.** Computing the coverage *after*
   `set_status` writes an approval with no `series_inputs`, which the very next
   drift check refuses; the "status did not move" assertion in
   `test_an_unclassified_series_read_refuses_the_approval` is the one that states
   the ordering rule.
4. **Unchanged from Task 2:** I still have no harness that crashes between two
   writes, so "the record and the status land together" remains argued from the
   code (one `atomic_write`) rather than measured.

---

## 4. Step 4 — end to end, in a throwaway workspace

`$AGSOC_WORKSPACE=/Volumes/…/jobs/9a014c11/tmp/t3/demo/workspace` — Task 2's demo
episode, five beats, one figure cleared by a written override.

### Screen 0 — an approval written before this task, read after it

Free, and the fail-closed case: the Task 2 record says nothing about `series.toml`.
**Both** drift answers are named, separately, in one message:

```
$ agsoc video check 2026-08-18 --series the-brief                    # EXIT=0
the-brief/2026-08-18 · 3 claims · 2 pass · 1 fail
the approval on this episode no longer describes it — the beats document has changed: the approval
covers sha256 3a2360aa16fe984413ddcda14df4397f34c64175def452314a537f0782b9cd1a, the file on disk is
sha256 74fa3f1effda13752b5b043718ce0069dc9381f5cad2c88adecce4d3a02e7d22; and this approval records
nothing about series.toml, so what the frame looks like — the palette, the type, the show's name,
the act labels — was never signed. Approve again and it will be — approved by Ali Abdukarim at
2026-08-18T01:13:44-05:00. Re-run `agsoc video check` and approve again, or put the change back
```

### Screen 1 — approve clean

```
$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"   # EXIT=0
the-brief/2026-08-18 · approved
      by       Ali Abdukarim
      at       2026-08-18T01:34:52-05:00
      script   sha256 74fa3f1effda13752b5b043718ce0069dc9381f5cad2c88adecce4d3a02e7d22 (the beats
               document)
      claims   2 of 3 verified · 1 cleared by override, not verified (§8.4), checked
               2026-08-18T01:13:30.335230-05:00
      override c-003 “The $3.99 is our own rounded list price for the annual plan, not the article's
               per-token figure; the ladder beside it uses the article's numbers unchanged.” — Ali
               Abdukarim
      override rate 1 of 3 claims (33%) — D-040: a high rate means the checker is wrong, not the
               operator
      design   series.toml is covered too — act labels (0), byline, design (8), name. Change any of
               them and this approval no longer describes the frame
      next     edit the beats and this approval no longer describes them — `script_sha256` is what
               says so; the same goes for the design, and `agsoc video check` says so on both
```

and in `script.yaml`, the palette in the diff a human commits:

```yaml
approval:
  by: Ali Abdukarim
  at: '2026-08-18T01:34:52-05:00'
  script_sha256: 74fa3f1effda13752b5b043718ce0069dc9381f5cad2c88adecce4d3a02e7d22
  pace: 1.0
  claims_checked_at: '2026-08-18T01:13:30.335230-05:00'
  corpus_sha: 227be06e985cf44e1887cebf9317806396dd00aa46e143c4182d8c6f9ad1d176
  claims:
    total: 3
    verified: 2
    attested: 0
    overridden: 1
  series_inputs:
    acts: {}
    byline: ''
    design:
      surface: '#F2F5F8'
      ink: '#0B1B2B'
      ink_muted: '#5A6B7C'
      accent: '#2E6BFF'
      accent_alt: '#00C2D7'
      accent_warm: '#FF6B4A'
      type_family: SF Pro Display, Helvetica Neue, system-ui
      type_scale: default
    name: The Brief
  overrides:
  - id: c-003
    ...
```

### Screen 2 — change `accent`, and the refusal

The whole edit is one line in a file the approval never used to read:

```diff
-accent      = "#2E6BFF"
+accent      = "#12A150"
```

```
$ agsoc video check 2026-08-18 --series the-brief                    # EXIT=0
the-brief/2026-08-18 · 3 claims · 2 pass · 1 fail
the approval on this episode no longer describes it — series.toml has changed: [design] accent was
'#2E6BFF', now '#12A150' — approved by Ali Abdukarim at 2026-08-18T01:34:52-05:00. Re-run `agsoc
video check` and approve again, or put the change back

$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"   # EXIT=1
the-brief/2026-08-18 · NOT approved — cannot move approved -> approved; allowed next: in_review,
rendering. Only a script an agent has finished and marked `status: in_review` can be approved
```

**What every other control said about that edit**, measured, not asserted:

```
beats sha256          : 74fa3f1effda1375 == signed 74fa3f1effda1375
stale_reason          : None
corpus_sha            : 227be06e985cf44e (unchanged)
verdicts              : [('c-002','pass'), ('c-003','fail'), ('c-004','pass')]   (identical)
approval_drift        : DETECTED
```

Every claim still verifies, the ledger is current and correctly says so, the
beats digest matches to the byte — **and every frame is a different colour.**
Only the design comparison can see it, which is the sentence this task exists to
make true.

### Screen 3 — re-approve, and it clears

```
$ (hand edit: status: in_review)
$ agsoc video check 2026-08-18 --series the-brief                          # EXIT=0
$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"   # EXIT=0
the-brief/2026-08-18 · approved
      design   series.toml is covered too — act labels (0), byline, design (8), name. Change any of
      next     edit the beats and this approval no longer describes them — `script_sha256` is what
               says so; the same goes for the design, and `agsoc video check` says so on both

$ agsoc video check 2026-08-18 --series the-brief                          # EXIT=0
the-brief/2026-08-18 · 3 claims · 2 pass · 1 fail          <- no banner
approval_drift        : None
signed accent         : #12A150
```

### Screen 4 — the loud refusal, on a real workspace

`refreshed = 2026-08-18` added to `[design]` — a value `validate_design` does not
police (it is not a colour token) and JSON cannot compare:

```
$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"   # EXIT=1
the-brief/2026-08-18 · NOT approved — series.toml: [design] refreshed = datetime.date(2026, 8, 18)
holds a value an approval cannot compare (Object of type date is not JSON serializable). Dates,
times and non-finite numbers have no comparable form here; write it as a string. Refusing rather
than dropping it: an approval that silently skips a value covers less than it says it does
```

### The operator's workspace

Backed up **first**, to a path that did not exist (the command refuses if it
does), and the backup's top level inspected — `config.toml inbox series sources
voice.md`, three episodes — so it is a workspace root, not a copy nested inside
an older backup. Never approved, never edited:

```
2026-08-17   EXIT=0  ::  6 verified · 1 attested by hand, NOT verified (D-088) · 7 claims, none open
2026-08-17b  EXIT=0  ::  22 claims verified, none open
2026-08-17c  EXIT=0  ::  24 claims verified, none open

status on disk:  draft · in_review · in_review
$ diff -rq workspace …/t3/ws-backup-t3   ->  OPERATOR WORKSPACE UNCHANGED
```

---

## 5. Files changed

| File | Change |
|---|---|
| `src/agenticsocial/video/plan.py` | **new** `SERIES_ATTR_COVERAGE`, `series_reads_of`, `series_reads`, `series_inputs`, `_culprit` — the derivation and its refusals |
| `src/agenticsocial/video/approve.py` | the record carries `series_inputs`; `approval_drift` gains `_design_drift`, `_named_changes`, `_flatten`, `_where`; `ApprovalRefused` gains the `design` kind |
| `src/agenticsocial/video/series.py` | `load_series_dir` — one reader of `series.toml`, reachable from an episode's directory |
| `src/agenticsocial/video/cli.py` | the approve screen names what of `series.toml` was covered (`_covered_inputs`, read off the record) |
| `tests/test_video_approve.py` | +32 tests (125 in the file) |

Commits: `59a57d7` → `5ce94b2` → `e35253a` → `518c014`.
`git status --porcelain -- src tests` is clean. **1737 tests pass.**

---

## 6. Issues and concerns

### 6.1 What can still change between approval and render without being named

The question Phase 8 needs answered precisely. An approval now binds **the beats
document's bytes**, **`pace`**, and **the `series.toml` values that reach
`plan.json`**. Everything below is outside it. Grouped by who owns the fix,
because they are not one problem.

**A. The renderer's own code and data — nothing ties a render to a version of it.**

1. **`engine/engine.js` and `engine/planbuild.js`.** Every pixel's position and
   every beat's drawing routine. A change here restyles every episode ever
   approved, and no approval, digest or record mentions it.
2. **`engine/scene.html`.** The stylesheet, and it is where the typography
   actually lives — sizes, weights, leading, the layout grid. Note the asymmetry:
   the approval binds `type_family` and `type_scale`, which the engine **ignores**
   (they appear nowhere in `engine/`), while the type that is really drawn is in
   a file the approval cannot see.
3. **`engine/content/*.js`** — the drawing content modules, same as 1.
4. **Fonts.** `type_family = "SF Pro Display, Helvetica Neue, system-ui"` is a
   *request*; the render machine resolves it. The same plan on a machine without
   SF Pro renders different glyphs, different metrics, different line breaks —
   and nothing records which font was used. This is the one that silently differs
   *between machines* rather than over time.
5. **Chromium (Playwright).** The rasterizer: text shaping, antialiasing,
   sub-pixel positioning. A version bump changes frames without changing a byte
   of this repo.
6. **`ffmpeg`.** Both the binary (whatever is on `PATH`) and the flags in
   `render.py` — `libx264 -preset veryfast -crf 20 -pix_fmt yuv420p`. These
   decide what the *video* looks like as opposed to what the frames look like.
   The mp4 records `script_file_sha256` in its `comment` tag and nothing about
   the encoder that made it.

**B. Choices made at render time that the approval does not constrain.**

7. **The format.** `--format vertical` and `--format wide` are different layouts
   and the approval names neither. §9 argues formats are frame-identical *in
   time*; they are not identical *in composition*, and an approver reviewed one
   of them.
8. **`--probe`.** Not an output anyone ships, but it is the same gate-free path.

**C. Values in `script.yaml`'s metadata document, outside the beats digest.**

9. **`date_long`.** `episode.py`'s docstring says it is "on screen"; in the code
   as it stands `build_plan` does not copy it and it appears nowhere in
   `engine/`, so today it reaches no frame. **If Phase 8 wires it up, it must be
   covered in the same commit** — it is exactly the shape of the hole this task
   closed. (Flagging the stale docstring rather than editing it: it is a claim
   about the future that will become true.)
10. **`status` itself, and the approval record.** Hand-editable, deliberately
    outside the digest (§10's fixed-point problem), and D-062's position applies:
    this raises the floor, it is not a boundary.

**D. Things that are somebody else's answer, on purpose.**

11. **The corpus.** `approve` records `corpus_sha`; `approval_drift` still does
    not compare it, because that is `verify.stale_reason`'s question. Two paths
    to one answer is what D-059 was. The consequence is a **requirement on Phase
    8**, restated in 6.2, not a property of `approval_drift`.
12. **`claims.json` after the fact.** The record names the counts and the check
    timestamp, so a post-approval hand edit of the ledger is *visible by
    comparison* — but nothing compares them.

**The honest one-line summary for Phase 8: the approval now covers everything the
operator authors, and nothing the renderer is.** Script, pace, palette, name,
byline, act labels — all bound. The engine, the fonts, the browser, ffmpeg and
the chosen format — all unbound. If Phase 8 needs "this mp4 is what was
approved" rather than "this plan is what was approved", the missing artifact is a
digest over `engine/` plus the resolved font, encoder and format, recorded **into
the render**, not into the approval — because those are properties of the machine
that rendered, and the approval is a statement by a person.

### 6.2 What Phase 8's `render` must call — unchanged from Task 2, plus one line

```
assert_transition(disk status, RENDERING, VIDEO_TRANSITIONS)   was it ever approved?
approve.approval_drift(episode)                                is the approval still about these
                                                               bytes AND this design?
verify.stale_reason(episode, verify.read_ledger(episode))      is the check still about this corpus?
```

`approval_drift` now answers two of the three questions in one string and names
them separately. It still does not answer the third, and a `render` that calls
only it will render against a stale ledger.

### 6.3 Two things I would put in front of a decision before Phase 8

- **`type_family` / `type_scale` are copied into `plan.json` and the engine
  ignores them.** Either the engine should apply them (in which case the approval
  is already right) or `plan.py` should stop copying them (in which case the
  approval should stop covering them, automatically, on the same commit — which
  is the derivation working). Today an operator can edit `type_scale`, be told
  the approval no longer describes the frame, and be wrong. It is the only known
  false positive in the covered set and it is caused by the plan, not by this
  check.
- **Nothing un-approves, still.** Carried from Tasks 1 and 2: `approved →
  in_review` exists in the table and no command walks it, so re-approving after
  an intentional design change means hand-editing `status: in_review` (as Screen
  3 does). When a `revoke` lands it must clear the whole `approval:` block —
  including `series_inputs` — in the same gated write.

### 6.4 A smaller one, found by the demo rather than by a test

The first version of the uncomparable-value refusal printed the entire `[design]`
table and left the operator to spot the date in it, and the first approve screen
read `acts (0)`. Both were only visible on a real screen; both are fixed in
`518c014`. Task 1's lesson holds — the display *is* the deliverable, and no test
I would have thought to write says "this message is legible".

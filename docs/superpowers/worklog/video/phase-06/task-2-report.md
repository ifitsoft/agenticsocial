# Task 2 Report: closing what the blind run found

**Phase:** 6 · **Branch:** `feat/video-phase-06-storyboard`
**Suite:** `uv run pytest -q` → `1611 passed, 1 warning`, exit 0 (baseline 1573).
**Mutants:** 12 written, **12/12 killed** — with one honest correction below.
**`workspace/` was backed up and both episodes are intact.** The only files that
changed under it are the two `claims.json` ledgers, which `check` rewrites by
design; both episodes still pass, and neither script.yaml was touched.

---

## 1. The dumbbell citation decision, argued

**Resolved towards citation.** `script.py` now has `"cited": True` on
`dumbbell`, so `src` and `quote` are required at load;
`dumbbell_prints_a_figure` and the `cited_when` mechanism are deleted.

The exemption's justification was "a dumbbell renders no numbers at all". That
sentence is true of `values` and false of the type. A dumbbell draws a
`caption`, a `footnote`, two `series` names and a label per row, and `claims.py`
has read every one of those as a claim since Phase 5 — which is why an uncited
dumbbell got `no_source` and exit 1 from the command the author is told to run.
So the schema was not granting a permission, it was describing a state the
pipeline refuses. **An exemption you cannot reach is a trap**, and between two
modules that disagree, the one that verifies is the one to keep.

The conditional version is worse than either, once you look at what it fires on:
it refused `V4-Pro` in a row label (a digit inside a product name, which asserts
nothing) and permitted `Evaluator ratings, AMIE against primary care physicians`
(a comparison about a real study). That is exactly backwards.

**The cost, stated plainly:** this is a spec change. Spec §7.1 does not put
`dumbbell` in the cited pair. Two committed test fixtures gained a `src` and a
`quote`. No episode in `workspace/` or `engine/content/` contains a dumbbell, so
nothing that has ever rendered is affected. Recorded as D-110.

The refusal message now names both fields, because they are a pair and an author
who learns about them one refusal at a time runs twice:

```
beat 2 (dumbbell): `src` is required and must not be empty — a dumbbell beat
asserts something about the world, and spec §7.2 allows no path to rendering a
claim that isn't in a source. Give it `src` and `quote`
```

---

## 2. What changed in the skill, item by item

### The wrong instruction (highest severity) — fixed

"You are re-drafting an episode that is already there" is gone. In its place:
two named branches (re-draft **only** an episode the user named or you created
in this run — and stop and ask if its status is anything but `draft`/
`in_review`; otherwise the day already holds someone else's episode), a stated
convention for the second episode of a date (**append a lowercase letter:
`2026-08-17b`, `2026-08-17c`** — exactly what the blind runner invented and had
no way to know was legal), and a **hard rule**: never edit an episode you did
not create in this run, never `rm`/`mv`/overwrite under `episodes/`, never edit
a `script.yaml` whose `episode:` is not the one you are working on. The reason
is given, once, where it lands: `workspace/` is not version controlled.

### The typography gap — the brief's diagnosis was wrong, and I followed the code

**FLAG.** The brief says the corpus's U+2011 hyphens and curly punctuation mean
"anything hand-typed with an ASCII `-` fails `check` as *quote is not in
sources*". It does not. §8.2.1's fold normalises `‑` `–` `—` → `-`, `’ “ ”` →
`' " "`, `…` → `...`, NBSP/tab → space, and case away. Verified through the real
`check_claim`:

```
pass | the model — priced at $1.32          (source has the em dash)
pass | THE   MODEL — priced                 (case + runs of spaces)
pass | …went GA on Monday…                  (edge elision, D-101)
fail | the model -- priced at $1.32         (two characters for one dash)
fail | went GA Monday                       ("on" dropped)
fail | per the vendors note                 (apostrophe dropped — a WORD change)
```

So the hazard is not the bytes, it is **paraphrase** — which is precisely what
happened to the skill's author (*points to* for *pointing to*). The blind runner
read the bytes, saw exotic codepoints, and concluded they were the danger; their
run passed, so nothing contradicted them. A precaution that works cannot tell
you whether it was needed.

What the skill now does instead of repeating "never retype":

- says **why** the rule is not "be careful": a quote is compared word for word,
  and an agent writing prose and its citation in one breath smooths the
  citation;
- gives a table of what is forgiven and what is not, verified against the
  checker, so a refusal is diagnosable;
- gives **a way to extract a span** (new step 3.5): a `uv run python - <<'PY'`
  snippet that anchors on plain words and prints `repr(t[i-40:i+240])`, so the
  author copies bytes instead of retyping a sentence — and `repr()` shows
  `\u2011` where the file holds a non-breaking hyphen, which is the honest
  version of the brief's point;
- warns that **the anchor is hand-typed too**: `t.index('open-weight')` and
  `grep` both miss a file holding `open‑weight`. Anchor on ordinary words.

### The rest of the friction log

| # | Item | What the skill now says |
|---|---|---|
| 1 | `voice.md` unfilled | It ships as a template and its rules are about tweets. If the headings are still placeholders there is nothing to follow: take register from `[series] register` and the committed episodes, do **not** invent a persona, do **not** apply the X rules to a video, and say so in the handoff. |
| 2 | episode id | above |
| 3 | `video new` hint | Fixed in the CLI; the skill's new §8.5 lists every command and says the hint is now correct. |
| 5 | coverage granularity | Pass **two terms per story, vendor + product**. Terms are case-insensitive **substrings** of id/title/note/entities/sources, so short over-hits and long under-hits; then read the printed title and angle, because a prior story about the same vendor is usually a different story. |
| 6 | "cover it as an update" | Defined by naming what does not exist: there is no `coverage.mjs add`, the ledger is hand-written after ship, so **"drop it" is today's supported branch**. If the user insists, the beat must say what changed and the handoff must name the prior episode id for the human to record. |
| 7 | `date_long: ''` | Leave it empty. Nothing reads it — the loader does not parse it and `planbuild.js` prints the episode id on the title card either way. An authoring hole, not your field to fill. |
| 8 | KPI `unit` magnitude | `prefix + value + unit` is glued into one token, so `value: 2.4` + `unit: T` **is** `2.4T` = 2.4e12 and verifies against "2.4 trillion"; `9.4T` and `2.4B` fail. `K M B T bn mn tn` are magnitudes, `% x bps` multiply by one. Plus: figures no longer appear in "names not found" (code fix). |
| 9 | beats-per-act arithmetic | Stated as **2 cold-open + four acts of 4–6 + 1 signoff**, with the bookends explicitly *outside* the acts, and "use `01`–`04` when `series.toml` declares none" (it ships with them commented out). |
| 10 | `pace` decimals | "rounded to **AT MOST** 3 decimals", with the reason: `1.31` is what 91.6s/120s gives and YAML cannot write `1.310`. |
| 11 | `act` on the signoff | `act: ""`, like the cold open — with the note that `act` is free text and purely cosmetic, so the committed `2026-08-17` writing `"04"` is equally valid; be consistent within an episode. |

Two more, not on the list, because leaving them would have made the file wrong:
the `dumbbell` bullet and the §7 table now say citation is required at load, and
§8 says `check` prints the runtime.

**Every command in the skill was run.** `agsoc series list`, `video list`,
`node engine/coverage.mjs check deepseek v4-pro`, and a full
`init → series new → video new → video ingest --paste → video check` walkthrough
in a scratch `$AGSOC_WORKSPACE`, including the step-3.5 extraction snippet
against the real corpus and the `next:` hint executed as printed.

---

## 3. TDD evidence and the mutation score

Tests first, failing, committed (`9d7adef`), then the implementation
(`508d78b`). The failing run, before any source change:

```
FAILED tests/test_video_check.py::test_check_reports_the_runtime_and_the_tolerance
FAILED tests/test_video_check.py::test_check_reports_a_runtime_that_is_within_tolerance
FAILED tests/test_video_check.py::test_check_reports_the_runtime_even_when_a_claim_fails
FAILED tests/test_video_check.py::test_check_and_review_report_the_same_runtime_lines
FAILED tests/test_video_claims.py::test_a_figure_token_is_never_also_an_entity_atom[2.4T]
FAILED tests/test_video_claims.py::test_a_figure_token_is_never_also_an_entity_atom[95B]
FAILED tests/test_video_claims.py::test_a_figure_token_is_never_also_an_entity_atom[1.6T]
FAILED tests/test_video_claims.py::test_a_magnitude_figure_is_a_number_atom_and_nothing_else
FAILED tests/test_video_cli.py::test_video_new_hints_the_next_command_with_its_series
FAILED tests/test_video_cli.py::test_the_next_command_video_new_prints_actually_runs
FAILED tests/test_video_script.py::test_a_chart_without_a_source_is_refused[src-dumbbell]
FAILED tests/test_video_script.py::test_a_chart_without_a_source_is_refused[quote-dumbbell]
FAILED tests/test_video_script.py::test_a_chart_whose_source_is_empty_is_refused[-src-dumbbell]
FAILED tests/test_video_script.py::test_a_chart_whose_source_is_empty_is_refused[-quote-dumbbell]
FAILED tests/test_video_script.py::test_the_cited_types_are_exactly_the_three_charts
FAILED tests/test_video_script.py::test_even_a_digit_free_dumbbell_must_cite[src]
FAILED tests/test_video_script.py::test_even_a_digit_free_dumbbell_must_cite[quote]
17 failed, 1593 passed
```

Note `test_the_next_command_video_new_prints_actually_runs` failed with the
production symptom, not an assertion:
`no series 'default' — create it with 'agsoc series new default'`.

### Mutation score: 12 written, **12/12 killed** — with one correction

`PYTHONDONTWRITEBYTECODE=1`, one mutant at a time, source restored after each,
unpiped exit codes (D-100, D-105).

| # | Mutant | Result |
|---|---|---|
| M1 | `dumbbell` back to `cited: False` | KILLED |
| M2 | `kpis` silently uncited | KILLED |
| M2b | `jumpChart` silently uncited | KILLED |
| M3 | digit-initial token still an entity atom | KILLED |
| M4 | every name dropped from entity atoms | KILLED |
| M5 | `check` prints no runtime | KILLED |
| M6 | `check` *refuses* out of tolerance | KILLED |
| M7 | `video new` hint omits `--series` | KILLED |
| X1 | runtime verdict hardcoded "within tolerance" | KILLED |
| X2 | `check`'s `holds` figure already scaled by pace | **survived first, then killed** |
| X3 | citation message names only the missing field | KILLED |
| X4 | entity boundary re-derived as `bare.isdigit()` instead of reusing `claim_number` | KILLED |

**The honest part.** Two survivors in the first sweep:

- **X2 was a real gap.** `held = sum(holds) * pace` is the identity at
  `pace: 1.0`, and every runtime test I had written ran at 1.0 — including the
  one comparing `check` against `review`, which would have moved together.
  `holds` is the number the skill tells an author to recompute `pace` from, so
  reporting it pre-scaled is a wrong instruction on screen. Fixed with a test at
  `pace: 1.25` (`2d0d398`), then killed.
- **My first M1 was an equivalent mutant, not a survivor.** I appended a second
  `"cited": False` key to the dumbbell dict literal; the later `"cited": True`
  in the same literal wins, so the file was unchanged in effect. Rewritten to
  mutate the real key, and killed. Reported because a sweep that quietly
  reports its own broken mutants as survivors is worse than no sweep — and
  because it is the same shape as D-105: measuring something adjacent to the
  property.

---

## 4. Both episodes, `check` and `review`

Nothing regressed. Verdicts are identical to the pre-change baseline on both;
the only diffs are the two new runtime lines and one row leaving the entity
list.

### `2026-08-17` (the operator's own, 9 beats)

```
the-brief/2026-08-17 · 7 claims · 6 pass · 1 manual

    c-002   beat  1  statement  pass
    c-003   beat  2  statement  pass
    c-004   beat  3  kpis       pass
    c-005   beat  4  list       pass
    c-006   beat  5  statement  pass
    c-007   beat  6  kpis       pass
    c-008   beat  7  custom     manual

  attested by hand — no machine checked these (D-088), you are approving the sentence:
    c-008    “Draws the words "Same story tomorrow." and nothing else. — Ali Abdukarim”

  names not found in the source — recorded, not gated (D-102: the extractor glues names together, so
  this cannot hold a gate):
    c-004    New V4-Pro
    c-005    Alibaba Qwen3.8-Max

wrote workspace/series/the-brief/episodes/2026-08-17/claims.json
holds 37.5s × pace 1.0 = runtime 37.5s
target 120s ± 8s · OUT OF TOLERANCE (-82.5s)
7 claims verified, none open
```

`review` tail:

```
claims  6 pass · 1 manual   (checked 2026-08-17T23:53:36.460291-05:00)

holds 37.5s × pace 1.0 = runtime 37.5s
target 120s ± 8s · OUT OF TOLERANCE (-82.5s)
```

### `2026-08-17b` (the blind run's, 24 beats)

```
the-brief/2026-08-17b · 22 claims · 22 pass

    c-002   beat  1  statement  pass
    c-003   beat  2  statement  pass
    c-004   beat  3  body       pass
    c-005   beat  4  kpis       pass
    c-006   beat  5  statement  pass
    c-007   beat  6  body       pass
    c-008   beat  7  statement  pass
    c-009   beat  8  kpis       pass
    c-010   beat  9  body       pass
    c-011   beat 10  statement  pass
    c-012   beat 11  body       pass
    c-013   beat 12  statement  pass
    c-014   beat 13  list       pass
    c-015   beat 14  body       pass
    c-016   beat 15  statement  pass
    c-017   beat 16  body       pass
    c-018   beat 17  statement  pass
    c-019   beat 18  body       pass
    c-020   beat 19  statement  pass
    c-021   beat 20  body       pass
    c-022   beat 21  statement  pass
    c-023   beat 22  body       pass

  names not found in the source — recorded, not gated (D-102: the extractor glues names together, so
  this cannot hold a gate):
    c-008    Alibaba Qwen3.8-Max
    c-011    Tongyi Lab Qwen3.8-27B
    c-013    OpenAI GPT-5.6, Sol Terra
    c-014    Three
    c-016    Latest, Z.ai GLM-5.3
    c-017    OpenAI Anthropic, Google Chinese
    c-020    Also

wrote workspace/series/the-brief/episodes/2026-08-17b/claims.json
holds 91.6s × pace 1.31 = runtime 120.0s
target 120s ± 8s · within tolerance (-0.0s)
22 claims verified, none open
```

`review` tail:

```
claims  22 pass   (checked 2026-08-17T23:53:36.769039-05:00)

holds 91.6s × pace 1.31 = runtime 120.0s
target 120s ± 8s · within tolerance (-0.0s)
```

**The diff against the pre-change run of `check`, in full:**

```
2026-08-17
> holds 37.5s × pace 1.0 = runtime 37.5s
> target 120s ± 8s · OUT OF TOLERANCE (-82.5s)

2026-08-17b
<     c-009    2.4T
> holds 91.6s × pace 1.31 = runtime 120.0s
> target 120s ± 8s · within tolerance (-0.0s)
```

That single removed row is R3 landing on real content: a figure that verified by
value is no longer filed as a name nobody could find.

---

## 5. Files changed, and the commits

| Commit | What |
|---|---|
| `9d7adef` | `test:` the four defects pinned, failing first |
| `508d78b` | `fix:` the four code fixes |
| `2177373` | `docs(skill):` the twelve items |
| `2d0d398` | `test:` the unscaled holds total (from the sweep) |
| `0717b7e` | `docs:` D-110 |

Files: `src/agenticsocial/video/script.py`, `src/agenticsocial/video/claims.py`,
`src/agenticsocial/video/cli.py`, `tests/test_video_script.py`,
`tests/test_video_claims.py`, `tests/test_video_check.py`,
`tests/test_video_cli.py`, `tests/test_video_review.py`,
`skills/storyboard/SKILL.md`, `docs/superpowers/worklog/video/DECISIONS.md`.

`git status --porcelain -- src tests skills` is empty.

---

## 6. Issues and concerns

### What the second blind runner will still get wrong

Ranked, as a prediction to be checked:

1. **Too few beats, and it is still invisible to every gate.** `check` and
   `review` now both report runtime, so "35 seconds" cannot slip through — but
   `pace` makes 12 beats land in tolerance just as well as 24, and nothing
   measures beats-per-minute. A runner under time pressure writes 14 beats,
   gets a green check and a 120.0s runtime, and ships eight-second static
   cards. **This is now the most likely failure and the least detectable.**
2. **A quote that is one word off.** Down, not out. Step 3.5 gives a mechanical
   route, but an agent that has already drafted the beat will reach for the
   words it just wrote. I expect at most one per run now, and `check` points
   straight at it.
3. **The second-episode convention applied when it should not be.** The rule I
   wrote is safe-by-default, which means its failure mode is a runner minting
   `2026-08-17b` when the user *did* want `2026-08-17` re-drafted. That costs a
   directory and a conversation, not work — deliberately the cheaper error.
4. **`unit` used for a magnitude the source spells differently.** `unit: T`
   against a source saying "2,400 billion" fails, correctly, and the fix
   (widen the quote / write the figure the source writes) is a step away in the
   text but not adjacent to the KPI table.

Of the last prediction's three items, two happened; I would rather over-predict
here than repeat that.

### Not fixed, and why

- **Friction item 4 does not exist.** The brief's friction log numbers 1, 2, 3,
  5, 6, 7, 8, 9, 10, 11 — there is no item 4, so "twelve" is the count of a list
  with a gap in it. Everything numbered is addressed, plus the typography item
  and the episode-id item. FLAG, in case item 4 was lost in editing rather than
  renumbered.
- **D-087's count-fits-hold refusal is still unreachable** from the author's
  half of the pipeline (D-109 #2). The skill still compensates with a 4.0s
  floor. Out of scope here; it is arithmetic over the plan and belongs in
  `check` next to the runtime line.
- **`date_long` is dead metadata.** `create_episode` writes it, nothing parses
  it, and the renderer prints the episode id on the title card. I documented it
  rather than wiring it: wiring it is a render-path change with no test that
  can see the frame, and the honest answer to "is empty intended?" is "it is a
  hole".
- **The entity list is still noisy.** `2.4T` is gone; `OpenAI Anthropic, Google
  Chinese`, `Three`, `Also` and `Latest` are not. Those are D-102's known cost
  (glued runs, and sentence-opening words outside `SENTENCE_STOPWORDS`), and
  Phase 9's territory. The fix here removed the rows that were *provably wrong*,
  not the noise.
- **`agsoc init` ignores `$AGSOC_WORKSPACE`** — it takes a positional path
  defaulting to `workspace`, so `AGSOC_WORKSPACE=/tmp/x agsoc init` scaffolds
  `./workspace` instead and every later command in that shell then fails to find
  it. Harmless here (the repo workspace already existed and `Workspace.init` is
  idempotent — `diff -r` against the backup is clean apart from the two
  regenerated `claims.json`), but it is a trap for anyone setting up a scratch
  workspace, and the skill does not mention `init` at all. Noted, not fixed.

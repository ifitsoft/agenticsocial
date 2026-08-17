# Task 2 Report: Runtime, the duration check, and `agsoc video review`

**Phase:** 3 · **Branch:** `feat/video-phase-03-script-schema`
**Commits:** `c71d4f1` (Step 0) · `34d8472` (tests) · `575664a` (implementation)
**Suite:** 742 → 828 passing. **Mutation score: 30/30.**

---

## 1. What I implemented

### Step 0 — the jumpChart catalogue (`c71d4f1`)

`script.py`'s `jumpChart` row required `before`, `after`, `scale`, `footnote` —
a single bar. `engine.js` takes `jumpChart(rows, max, d0, parent)` and
`engine/content/2026-08-14.js` passes four `[label, from, to, shown]` rows. The
schema could not describe the only jumpChart that has ever rendered.

Now: `rows` (non-empty list of mappings — string `label`, numeric
`before`/`after`, optional string `shown`), `scale` (positive number),
`footnote` (non-empty string). `src`/`quote` stay required per §7.2.

Two choices inside that, both deliberate:

- **Rows are mappings, not the engine's positional tuples.** A script is written
  by hand, and `['GDP.pdf', 22.0, 34.0, '…']` gives an operator no way to notice
  they have swapped the two numbers. Converting to the positional form is
  `render.mjs`'s job, at the far end of `plan.json`.
- **The exemplar is read out of `2026-08-14.js`, not retyped.**
  `_engine_jump_rows()` parses the real call. A hand-copied fixture stops being
  evidence the moment the episode changes, which is exactly when it should
  complain.

**Flagged (code-vs-prose):** the brief's prose says `footnote` is "a string". The
existing catalogue and the existing wrong-type table (`("jumpChart", "footnote",
"")` expects rejection) make it a *non-empty* string. I kept the stricter
existing behaviour — the brief's §7.2 sentence says the row is otherwise
unchanged, and loosening a check was not the point of Step 0. If you meant
`free_text`, it is a one-line change.

### `check_runtime` (`plan.py`)

```python
@dataclass(frozen=True)
class RuntimeCheck:
    total_sec: float; target_sec: int; tolerance_sec: int; within: bool; delta: float

def check_runtime(script: Script, series: Series) -> RuntimeCheck
```

- total is `sum(hold) * pace` — scaled **once**, at the end.
- `within = abs(delta) <= tolerance_sec`. Inclusive. `tolerance_sec: 0` reaches
  here (series.py allows it on purpose) and means *exactly*.
- `delta` is signed.
- both total and delta are rounded to 3dp **before** comparing. R2's boundary is
  inclusive, and binary floats make inclusivity accidental — eight 16.0s holds
  can sum to 128.00000000000003, and `<=` against that fails an episode that
  hits the documented bound exactly.

**A divergence you should know about:** `build_plan`'s `total_sec` rounds *each
beat* to 3dp, because frame numbers derive from it. `check_runtime` rounds only
the sum. For twelve 1.0s holds at pace 0.3333 the plan says 3.996s and the check
says 4.0s. R1 defines the duration rule as `sum(hold) * pace`, so the check is
the authority and **Phase 7 must gate on `check_runtime`, not on
`plan.json.total_sec`.** This is pinned by
`test_the_total_is_scaled_once_not_per_beat`.

### `agsoc video review <episode> [--series S]` (`cli.py`)

Exits **0** whether in tolerance or out, and whether or not beats cannot render.
Exits 1 only when the script will not load — that is a report that *cannot be
produced*, not a finding to report. Writes nothing.

The table is budgeted to a fixed 100 columns rather than grown to fit content
(see §4). `src` has its own right-hand column because §7.2 makes it the thing an
approver actually checks, and a column you scan down the page is checkable in a
way a ragged tail is not. `SUMMARISERS` is one entry per catalogue type — a
dict, not a chain of `if`s, for the same reason `BEAT_TYPES` is.

---

## 2. TDD evidence

| Step | Command | Result |
|---|---|---|
| baseline | `uv run pytest -q` | 742 passed |
| Step 0 RED | `pytest tests/test_video_script.py` | **32 failed**, 217 passed |
| Step 0 GREEN | `uv run pytest -q` | 758 passed |
| Task RED | `pytest tests/test_video_review.py` against a stub | **54 failed**, 9 passed |
| Task GREEN | `uv run pytest -q` | 828 passed |

The RED for the new module was measured against a deliberate stub
(`check_runtime` raising `NotImplementedError`, `review` echoing an empty line,
`SUMMARISERS = {}`), then the stub was reverted before committing the tests. A
bare `ImportError` at collection would have been RED but would not have told me
which tests actually bite.

**The 9 that passed vacuously**, in full, because you should see them:

```
test_runtimecheck_is_frozen
test_review_says_out_of_tolerance_rather_than_staying_silent
test_review_says_nothing_about_rendering_when_everything_renders
test_the_exemplars_cover_the_whole_catalogue
test_review_writes_nothing
test_review_writes_nothing_when_out_of_tolerance
test_review_does_not_create_a_plan_json
test_review_does_not_change_the_status
test_review_truncates_a_very_long_beat
```

Every one is a *negative* assertion, which a do-nothing stub satisfies by
construction. Each has a positive half inside the 54.

**One test bug I fixed and amended into commit 2:** the helper wrote
`episode: 2026-08-17` unquoted, which YAML parses as a `date`, so `load_script`
refused every fixture. The scaffolder avoids this because `_compose` goes
through `yaml.safe_dump`. See §6 for why I think this is also a real sharp edge.

---

## 3. Mutation score — 30/30

Harness: literal source substitution, full suite per mutant, file restored after
each. `git status --porcelain -- src tests` is clean.

### The brief's ten

| # | Mutant | Result | Killed by |
|---|---|---|---|
| M1 | total computed without `pace` | killed | `test_the_total_is_scaled_by_pace` |
| M2 | review displays scaled holds | killed | `test_review_displays_unscaled_holds` |
| M3 | tolerance uses `<` not `<=` | killed | `test_exactly_at_the_upper_bound_is_within_tolerance` |
| M4 | `within` hardcoded `True` | killed | `test_one_tick_over_the_bound_is_out_of_tolerance` |
| M5 | `tolerance_sec: 0` = "no limit" | killed | `test_a_zero_tolerance_refuses_a_near_miss` |
| M6 | review exits 1 when out of tolerance | killed | `test_review_exits_zero_when_out_of_tolerance` |
| M7 | review omits unrenderable beats | killed | `test_every_unrenderable_type_is_named_in_the_display` |
| M8 | unrenderable beat treated as an error | killed | `test_review_exits_zero_with_unrenderable_beats` |
| M9 | review writes `plan.json` | killed | `test_review_does_not_create_a_plan_json` |
| M10 | `check_runtime` caches the series | killed | `test_check_runtime_does_not_cache_the_series` |

### My own sweep — twenty more

```
     killed  S1  a beat using the default hold is left out of the total
     killed  S2  unrenderable beats left out of the total
     killed  S3  delta is unsigned
     killed  S4  target and tolerance swapped in the result
     killed  S5  jumpChart rows: empty list accepted (falsy)
     killed  S6  jumpChart before/after checked truthily
     killed  S7  jumpChart row label allowed to be empty
     killed  S8  only the first jumpChart row is checked
     killed  S9  jumpChart `shown` accepted at any type
     killed  S10 summariser table given a blank default
     killed  S11 text column not collapsed to one line
     killed  S12 text column not clipped
     killed  S13 pace printed with :g, losing the authored .0
     killed  S14 the ! margin never set
     killed  S15 the ! margin set on every row
     killed  S16 the src column dropped from the rows
     killed  S17 the act column dropped from the rows
     killed  S18 the unrenderable footer stops counting per type
     killed  S19 review reports the plan's total instead of sum(hold)*pace
     killed  S20 review truncates the beat list

MUTATION SCORE: 30/30
```

**Six are falsy-value mutants** (S5, S6, S7, M5, and the falsy branches inside
S10 and S13) — above the three you asked for.

**Two survived the first pass, and both were real, not bookkeeping:**

- **S10** — `beat_summary`'s `or f"({beat.type})"` fallback was unreachable,
  because `title` and `signoff` each carried their own inline fallback. Two
  fallbacks means the outer one is dead code, and dead code is code no test can
  be wrong about. Fixed by deleting the inline ones: a bare `title` or a
  `signoff` with `text: ""` — both legitimate — now reach the generic fallback
  and print `(title)` / `(signoff)`. New test:
  `test_a_beat_with_nothing_to_say_still_names_itself`.
- **S19** — every test in the file used holds whose product with pace was exact
  to 3dp, so per-beat rounding and end rounding agreed and the difference was
  invisible. Fixed with a pace of `0.3333`, which separates 3.996 from 4.0. This
  is the test that pins which total Phase 7 gates on.

Both fixes landed in commit 3, because step 4 of the brief runs after step 3. I
am flagging it rather than pretending the sweep found nothing.

---

## 4. Step 5 — the real run

Twelve beats, all ten catalogue types, a real four-row `jumpChart`, three
sources. Built with `agsoc series new` / `agsoc video new` in a scratch
workspace, script hand-written, output piped to a file and pasted from it.

```
$ agsoc video review 2026-08-17 --series the-brief
the-brief/2026-08-17 · draft · 12 beats · pace 1.0

     #  act        type        hold  text                                         src
 !   0  cold-open  title        2.5  Five stories from the last 24 hours.
     1  01         statement    3.5  Google shipped its main agentic model, and…  [blog.google]
 !   2  01         kpis         4.6  $0.75 per 1M input tokens · 50% cheaper th…  [venturebeat.com]
 !   3  01         body         4.0  Better tool use and multi-step reliability…
 !   4  02         jumpChart    6.2  FrontierCode 1.1 · DeepSWE v1.1 · Automati…  [deepmind.google]
 !   5  02         list         5.0  Where it landed · Gemini API and AI Studio…
 !   6  03         quote        4.5  “Gemini 3.7 Flash is our new workhorse mod…  [deepmind.google]
 !   7  03         dumbbell     6.0  Evaluator ratings, AMIE against primary ca…
     8  03         statement    3.8  The pattern is the same everywhere this we…
 !   9  04         body         4.4  What to watch is whether the cheaper tier…
 !  10  04         custom       3.0  const h = E('h2', null, P('One more thing.…
 !  11             signoff      2.5  Same time tomorrow.

holds 50.0s × pace 1.0 = runtime 50.0s
target 120s ± 8s · OUT OF TOLERANCE (-70.0s)
10 beats cannot be rendered yet — marked ! above: body (2), custom (1), dumbbell (1), jumpChart (1),
    kpis (1), list (1), quote (1), signoff (1), title (1)
exit=0

$ sed -i "" "s/pace: 1.0/pace: 2.4/" script.yaml   # nothing else changed
$ agsoc video review 2026-08-17 --series the-brief
the-brief/2026-08-17 · draft · 12 beats · pace 2.4

     #  act        type        hold  text                                         src
 !   0  cold-open  title        2.5  Five stories from the last 24 hours.
     1  01         statement    3.5  Google shipped its main agentic model, and…  [blog.google]
 !   2  01         kpis         4.6  $0.75 per 1M input tokens · 50% cheaper th…  [venturebeat.com]
 !   3  01         body         4.0  Better tool use and multi-step reliability…
 !   4  02         jumpChart    6.2  FrontierCode 1.1 · DeepSWE v1.1 · Automati…  [deepmind.google]
 !   5  02         list         5.0  Where it landed · Gemini API and AI Studio…
 !   6  03         quote        4.5  “Gemini 3.7 Flash is our new workhorse mod…  [deepmind.google]
 !   7  03         dumbbell     6.0  Evaluator ratings, AMIE against primary ca…
     8  03         statement    3.8  The pattern is the same everywhere this we…
 !   9  04         body         4.4  What to watch is whether the cheaper tier…
 !  10  04         custom       3.0  const h = E('h2', null, P('One more thing.…
 !  11             signoff      2.5  Same time tomorrow.

holds 50.0s × pace 2.4 = runtime 120.0s
target 120s ± 8s · within tolerance (+0.0s)
10 beats cannot be rendered yet — marked ! above: body (2), custom (1), dumbbell (1), jumpChart (1),
    kpis (1), list (1), quote (1), signoff (1), title (1)
exit=0
```

The second run is the same file with one character changed. The holds column is
identical in both — that is R1's negative working — and only the total moves.

**This run found two defects the green suite had not.** The first version of the
table was **156 columns wide**, because `[src: …]` was appended after an already
full text column; every row wrapped. Fixing the table left the unrenderable
footer at 156 for the same reason. Both are now pinned
(`test_a_long_source_cannot_widen_the_table`,
`test_the_whole_report_respects_the_width`) and the table is budgeted to a fixed
total width instead of grown to fit. I would not have found either without
running it.

---

## 5. Files changed

```
 src/agenticsocial/video/cli.py    | 208 +++++++++-
 src/agenticsocial/video/plan.py   |  68 ++++
 src/agenticsocial/video/script.py |  51 ++-
 tests/test_video_review.py        | 778 ++++++++++++++++++++++++++++++++++++++
 tests/test_video_script.py        | 152 +++++++-
```

- `c71d4f1` — `fix: jumpChart is a list of bars, not one bar (D-068)`
- `34d8472` — `test: specify check_runtime and agsoc video review`
- `575664a` — `feat: check_runtime and agsoc video review`

Nothing under `docs/` is staged. No dependencies added (`textwrap` is stdlib).
No network. `git status --porcelain -- src tests` is clean.

Note: a commit that is not mine — `c87a122 spec: require comparison folding and
claim-number extraction in phase 5` — landed on this branch between my commits 2
and 3. I did not touch it.

---

## 6. Issues and concerns

### 6.1 D-063 — is "callers load fresh" sufficient? No, but re-reading inside `check_runtime` is the wrong fix.

**I disagree with the framing, and here is the argument.**

Start by separating two failure modes that the phrase "reads a stale object"
runs together:

- **staleness** — the object was loaded from the real file, and the file has
  since changed.
- **forgery** — the object never corresponded to the file. `Series(slug="x",
  target_sec=1, tolerance_sec=10**9)` is one line of Python, and `frozen=True`
  stops nobody from constructing it.

All four write-shaped bypasses in this project were **forgery**, not staleness.
And that matters, because it decides what a re-read would actually buy.

Suppose `check_runtime` re-read the file. It has no `Workspace` and no slug — the
only path available to it is `series.dir / "series.toml"`, which comes from *the
same object the target_sec came from*. A caller who can hand it a forged
`target_sec` can hand it a forged `dir` pointing at a forged `series.toml`. The
re-read defends against exactly one of the two failure modes, and it is the one
that has never actually happened here. The other option — changing the signature
to `check_runtime(script, ws, slug)` — makes a pure computation do IO in order to
partially defend a boundary it is not on.

Now the second half, which is the part I want to be blunt about: **"callers load
fresh" is not a guarantee.** It is a property of today's call sites, discoverable
only by grep, and it will be true right up until the first caller that isn't a
CLI invocation — a batch `agsoc video review --all`, a Phase 7 `approve` that
prompts for confirmation between load and write, a future daemon. That is
precisely the argument that preceded the four bypasses and you are right to
refuse it.

So both halves of the usual answer are wrong. The resolution is that
**`check_runtime` is not a gate and should not try to be one.** It reads
nothing, writes nothing, and decides nothing — it returns a value. There is no
moment inside it for a stale read to be exploited, because it does not act on
what it reads. The thing that acts is `approve`, and *that* is where the
guarantee has to live.

What makes `episode.set_status` an actual guarantee is not that it re-reads. It
is that **one function performs the read of the authority and the write it
gates, with nothing in between, and accepts no pre-loaded object for the value
it checks.** Copying only the re-read into `check_runtime` copies the shape of
that guarantee without the property that makes it one.

**Concretely, for Phase 7.** `approve` must not have this signature:

```python
def approve(series: Series, episode: Episode) -> Episode:   # WRONG — this is bypass #5
```

It must have this one:

```python
def approve(ws: Workspace, series_slug: str, ep_id: str) -> Episode:
    series = load_series(ws, series_slug)          # the authority, read here
    ep = load_episode(series, ep_id)               # not passed in
    check = check_runtime(load_script(ep), series)
    if not check.within:
        raise ...                                  # refuse
    return set_status(ep, Status.APPROVED)         # ...and write, with nothing between
```

No `Series` and no `Episode` cross that boundary. Every gate-relevant value is
loaded inside the function that refuses, immediately before the transition. If
`approve` needs to prompt the operator, the prompt goes **before** the loads,
not between the loads and the write.

The standing D-063 requirement — *every new gate gets a stale-object test* — I
have satisfied at the level where it is meaningful:
`test_review_follows_series_toml_between_two_invocations` changes `series.toml`
between two real `review` invocations and asserts the second answer is the
file's. `test_review_follows_the_script_between_two_invocations` does the same
for the script, because the script is a file too and a cached `Script` is the
same bug with a different noun. `test_check_runtime_does_not_cache_the_series`
kills M10 at the unit level. Phase 7 should get the identical pair against
`approve`, plus one that changes `series.toml` *after* a confirmation prompt.

**Summary:** "callers load fresh" is insufficient as a *guarantee* and adequate
as a *fact about today*. The fix is not to make `check_runtime` do IO; it is to
forbid Phase 7's `approve` from accepting domain objects as parameters. I would
write that into DECISIONS as the standing rule, because it generalises to every
gate that follows and the re-read heuristic does not.

### 6.2 Is `review` readable with twelve beats?

**Yes — but only after two fixes it needed and the tests had not caught.** As
first written it was unreadable in the specific way that matters: 156-column
rows on an 80- or 100-column terminal, every row wrapping into two, and the
footer wrapping into three. That is precisely the failure you named — an
operator cannot scan it, so they approve without reading it.

At 100 columns it is readable now, and I do **not** think it needs paging or
truncation:

- twelve rows plus five lines of chrome is 19 lines. A 24-line terminal shows
  the whole thing without scrolling, which is the property that makes it
  scannable at all. Paging would destroy that.
- the index column means an operator who wants beat 7 in full has an
  unambiguous address for it.
- the real limit is nearer 30–35 beats, where the table stops fitting one
  screen. A 120-second episode at these hold lengths is ~20–25 beats, so there
  is headroom, but not a lot. **If Phase 4 pushes episodes past ~30 beats, act
  grouping (a blank line and an act header between acts) is the fix, not
  paging** — it keeps every beat on screen while giving the eye somewhere to
  rest.

One honest caveat about this phase specifically: with `RENDERABLE == {"statement"}`,
10 of 12 rows carry a `!`. A margin mark that fires on 83% of rows is close to
useless — it reads as decoration, not as a warning. It is correct, it is what the
phase is, and it will become informative as Phase 4 widens `RENDERABLE`. But for
Phase 3 the footer line is doing the real work and the margin is nearly noise. I
left it because inverting it (marking what *can* render) would be wrong the
moment the ratio flips.

### 6.3 What an operator needs before approving and still cannot see

Ranked by how likely I think each is to cause a bad approval:

1. **The `quote` field is invisible.** §7.2's whole mechanism is "every numeric
   value appears inside `quote`", and `review` shows `src` but not `quote`. An
   approver can see *that* a chart is cited and not *what the source says*. This
   is the largest gap. It does not fit the table — it wants a `--verbose` mode
   that prints each cited beat's `quote` under its row, or a separate
   `agsoc video claims` in Phase 5.
2. **Act structure is not checked against `[[structure.acts]]`.** `series.toml`
   declares acts with advisory `beats` counts; `review` prints each beat's act
   but never says "act 02 wants 6 beats and has 2", nor "beat 9 names act `04`,
   which is not in series.toml". A typo'd act id is invisible today.
3. **No per-act runtime subtotals.** When an episode is 40s over, the operator's
   next question is always *where*. Act subtotals answer it; the flat total does
   not.
4. **`script_sha256` is not shown.** Phase 7 binds approval to it. Showing it
   here would let an operator confirm that what they approved is what they
   reviewed.
5. **`warm_acts` and `register` are not surfaced**, so a design/voice mismatch
   is not visible at review time. Lower priority — neither is enforced (D-070).

### 6.4 Smaller things

- **An unquoted date episode id is a trap.** A hand-written `episode: 2026-08-17`
  in `script.yaml` is a YAML `date`, and the operator gets
  `` `episode` must be a string, got date ``. That is accurate and unhelpful —
  it names the type, not the fix. `agsoc video new` avoids it (safe_dump quotes),
  but every operator who hand-edits the metadata document will hit it once. A
  one-line improvement to `_meta_str`: when the value is a `date`, say "quote it
  — `episode: '2026-08-17'`". I did not do it because it is outside this task.
- **`build_plan` and `check_runtime` disagree in the third decimal.** Documented
  above and in both docstrings. Worth a DECISIONS entry so Phase 7 does not gate
  on the wrong one.
- **`dumbbell.rows` is still positional and unvalidated** while `jumpChart.rows`
  is now mappings. That inconsistency is deliberate for now — D-068's note says
  inventing `dumbbell`'s column shape would be "a wrong answer that looks
  authoritative" — but the two types now look different for a reason that is not
  visible in the file. Worth resolving when `dumbbell` gets a renderer.
- **Colour on the verdict line only.** Green in tolerance, yellow out. Not red:
  out of tolerance is a finding, not a failure, and red would contradict the
  exit code.

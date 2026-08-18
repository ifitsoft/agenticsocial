# Task 1 Report: the `storyboard` skill

**Phase:** 6 · **Branch:** `feat/video-phase-06-storyboard`
**Deliverable:** `skills/storyboard/SKILL.md` (one file, one commit)
**Baseline held:** `uv run pytest -q` → `1573 passed, 1 warning in 15.18s`, exit 0.
**`workspace/` was not modified.** Backed up first, `diff -r` clean at the end.
The whole walkthrough ran in a throwaway workspace under `$AGSOC_WORKSPACE`.

---

## 1. The decisions

### Coverage

The skill says **"check coverage before you write"** as the rule, and gives
today's spelling of it as a command that is verified to work from the repo root:

```
node engine/coverage.mjs check <keyword> [keyword...]
```

Verified (`node engine/coverage.mjs check gemini`, exit 0, 4 hits;
`… check pricing deepseek qwen`, exit 0, no overlap). `coverage.mjs` resolves
its ledger from `import.meta.url`, so it does not care about the caller's cwd —
which is why the skill can give one command instead of a `cd`.

One parenthetical says the ledger lives in `engine/coverage.json` today and
moves behind an `agsoc coverage check` command later. **The rule is the
sentence; the command is a detail in brackets.** When Phase 11 lands, the
bracket changes and nothing else does.

I did *not* say `agsoc coverage check`, per §13, because it does not exist and
an instruction an agent cannot execute is worse than none.

### Beat counts and holds

**`pace` is the answer, and it is derived, not chosen.** Runtime is
`sum(holds) × pace` (`plan.check_runtime`), so:

> Write the holds the cards deserve. Then set
> `pace = target_sec / sum(holds)`, to 3 decimals.

That makes landing in tolerance arithmetic rather than iteration. The skill's
concrete rule of thumb:

- 22–26 beats: two cold-open beats, then 4–6 per act;
- each `hold` between 2.6 and 5.6s;
- hold total between 80 and 95s (which keeps `pace` near 1.3);
- **≥ 4.0s on any `kpis` / `jumpChart` / `dumbbell` beat.**

That last one is D-087. The renderer's `requiredHold` (engine/planbuild.js) is
derived from the engine's own constants — `KPI_D0 0.35`, `KPI_STAGGER .62`,
`KPI_COUNT_DUR 1.35`, so a 3-item KPI needs 2.94s **of scaled hold** — and the
refusal only fires at render, which the author is forbidden to run. So the skill
gives a generous authored floor instead of the exact formula: 4.0s × any pace
≥ 1.25 clears every case in the catalogue. Confirmed on the walkthrough:
`build_plan` emitted KPI holds of 6.376s and 5.821s against a 2.32s requirement.

### `custom`

Discouraged in one paragraph, and not presented as a convenience. Wording:
*"a last resort — do not reach for it"*, followed by why (it is executed, so
nothing can check what it draws; `attest` is a person's signature and the ledger
records `manual`, never `pass`) and by the redirect (*"almost everything a
`custom` beat is written for is a `statement`, a `body` or a `signoff`"*). It is
still documented completely — `js`, the three refused non-determinism calls,
`attest` with an example — because an author who writes one anyway must not be
guessing.

My walkthrough episode has **no** `custom` beat, where the committed
`2026-08-17` script has one. Its signoff says the same thing.

---

## 2. The beat-count arithmetic, checked against the committed episodes

Measured, not recalled:

| episode | scenes | Σ holds | `pace` | Σ × pace |
|---|---|---|---|---|
| `engine/content/2026-08-12.js` | 24 | 83.6s | 1.435 | **119.97s** |
| `engine/content/2026-08-14.js` | 25 | 92.8s | 1.293 | **119.99s** |
| my walkthrough (§3) | 24 | 86.6s | 1.386 | **120.0s** |

All three land within 0.03s of a 120s target with an ±8s tolerance. Individual
holds in the two committed episodes run 2.2–5.6s, mean 3.48s and 3.71s — which
is where the skill's 2.6–5.6s band and 80–95s total came from. Act shape is
theirs too: two cold-open beats on a blank act, then four acts of 4–6 beats.

`review` on my walkthrough:

```
holds 86.6s × pace 1.386 = runtime 120.0s
target 120s ± 8s · within tolerance (+0.0s)
```

**Worth flagging: the one real committed `script.yaml` does not meet the phase's
own runtime exit criterion.** `workspace/series/the-brief/episodes/2026-08-17`
is 9 beats, 37.5s of holds at `pace 1.0`:

```
holds 37.5s × pace 1.0 = runtime 37.5s
target 120s ± 8s · OUT OF TOLERANCE (-82.5s)
```

It passes `check` (6 pass · 1 manual) and always has. So the best artefact an
author has to copy from is 82 seconds short, and a blind runner who imitates its
*shape* rather than its *arithmetic* will land out of tolerance. That is the
single strongest argument for putting the `pace` formula in the skill in so many
words, which is what I did.

---

## 3. What Step 3 caught

I wrote the skill, then followed it literally against
`workspace/inbox/2026-08-17-ai-brief.md` in a scratch workspace. Result: 24
beats, **21 of 22 claims passed on the first `check`**; one fix; then exit 0,
zero overrides, runtime 120.0s. Everything below is a place I reached for
knowledge that was not in the file, and every one of them is now in it.

**a) I could not run the command I had written.** `agsoc video check …` from a
directory that was not the repo root:

```
error: Failed to spawn: `agsoc`
  Caused by: No such file or directory (os error 2)
```

The skill never said the CLI is invoked as `uv run agsoc`, nor that the cwd
matters, nor where `workspace/` is resolved from. Added as step 0, and every
command in the file is now written `uv run agsoc …`.

**b) A quote must be one contiguous span of one file.** I hit this while
outlining act 03: I wanted a `list` beat combining `claude-context` and `cline`,
which are two separate bullets. There is no way to cite that. This is a
*structural* constraint — it decides how many beats you have — and I had left it
to be discovered from a refusal. Now stated in step 4, before the YAML.

**c) The multi-line quote.** I needed `quote: >-` immediately and had only
written the vague "a quote may span several lines of YAML". Added the folded
block scalar with a worked example and the reason it still matches (whitespace
runs fold to one space before comparison).

**d) The cold open's act.** I wrote `act: ""` from having read the committed
episodes, not from my own file. Now stated.

**e) The one real failure was the one the skill predicted, and its wording was
too weak.** `check` refused c-023:

```
 !  c-023   beat 22  statement  fail
      why      the quote is not in sources/_pasted.txt
      quote    “points to a future where specialized business domain knowledge is modularized into
               agent-callable capabilities”
      source   …r Claude Code and other agents, pointing to a future where specialized business
               domain knowledge is modularized into agent‑callable capabilities instead of just
               living in human experts…
```

*points to* vs *pointing to*. I had retyped a phrase while believing I had
copied it — with the rule "copy a quote, never retype it" written in my own hard
rules. The near-miss excerpt made the fix instant. I sharpened the failure guide
to name this exact shape, and to say the repair direction: **paste the source
bytes over the quote and reword the beat**, not the other way round.

**f) `dumbbell` refuses on a digit anywhere, including inside a product name.**
Building a coverage test of all ten types, a digit-free-looking dumbbell was
refused at load:

```
beat 3 (dumbbell): `rows[0]` `label` reads 'DeepSeek V4-Pro', so this card puts
a number on the screen — it needs `src` and `quote`.
```

`dumbbell_prints_a_figure` greps a bare `\d`, which is a *different rule* from
the "begins with a digit" boundary that governs every other field (D-106). An
author who has internalised "`V4-Pro` is a name and costs nothing" will write
exactly this. Called out explicitly, with `V4-Pro` as the example.

**g) An uncited `dumbbell` fails `check`, and the schema says otherwise.** My
first draft repeated the code's framing — "it renders no numbers, that is why it
needs no `src`". Tested it:

```
the-brief/dumb · 1 claim · 1 no_source
 !  c-001   beat  0  dumbbell   no_source
      why      the beat cites no `src`
```

exit 1. `script.py` has `dumbbell` as `cited: False`, but `claims.py` puts it in
`EXTRACTED_TYPES`, so `verify` produces a `no_source` record and `is_blocking`
refuses it. **The schema's exemption is unreachable through `check`.** See §5.
The skill now tells authors to cite every dumbbell, which is what actually
works.

**h) `before` and `after` are claims, and `before: 0` is the trap.** A
deliberately sloppy `jumpChart` produced:

```
why  the quote does not contain 1, 0 by value; beat 2 row 0 ('context-mode'):
     `shown` states 1, 98, but the bar is drawn from `before: 0` — the cell and
     the geometry disagree
```

Two refusals from one row. `0` looks like the absence of a number and is a
claim; the `1` in `&lt;1%` is a claim *and* a geometry mismatch. Both now
spelled out, along with the honest warning that a chart whose source publishes
only the "after" is one step from a fabricated "before" — which is literally
D-099.

**i) My staleness sentence was wrong.** I had written that `review` goes STALE
after any edit. It does not: `_script_drift` compares the *claims* the script
produces, not its bytes, so reformatting and the step-9 `status:` flip are both
safe. Verified — after flipping to `in_review`, `review` still showed all 22
verdicts. Corrected rather than deleted, because the author does need to re-run
`check` after changing what a beat says.

**j) Re-drafting an existing episode.** `agsoc video new 2026-08-17` refuses if
the directory exists — which is exactly the state the operator's real workspace
is in. Without instructions the blind runner will either loop or invent a new
episode id. The skill now handles it: check `video list`, skip `ingest` if
`sources/` is populated, replace the beats document.

**All ten catalogue types were exercised against the real code**, not just the
five my episode used: `title`, `statement`, `body`, `list`, `kpis` in the
walkthrough; `quote`, `jumpChart`, `dumbbell`, `custom`, `signoff` in a second
scratch episode that finishes `3 pass · 1 manual`, exit 0. Every field
description in §7 of the skill is one the checker has accepted.

---

## 4. Required fields I could not fit

**None.** Every required field of every type in `BEAT_TYPES` is in the skill's
§7 table, and every one has been written and accepted by the loader. Two things
are described rather than tabulated, deliberately:

- `dumbbell.rows[].values` — the table says `values`; the prose says what makes
  it writable: a **pair** aligned with `series[2]`, positions on the track in
  `[0, 1]`, **not the source's numbers**. There is no way to state that in a
  table cell without an author writing ratings into it.
- `custom.js` — the field is named and its lint is named, but the skill does not
  teach the engine's drawing API (`E`, `P`, `rise`, `an`, `EZ`). That is
  intentional: I am discouraging the type, and a tutorial for it would be an
  invitation. An author who insists has the committed episode and `engine.js`.

`claim_override` is the one shared field I left out of the skill on purpose. It
is §8.4's bypass, the skill's whole goal is a run that needs none, and an author
who knows the escape hatch reaches for it before the honest fix. `check`'s own
`fix` line names it when it is genuinely the answer.

---

## 5. Issues and concerns

### What the blind runner will most likely get wrong

Ranked, as a prediction to be checked:

1. **A quote that is one word off from the source.** This is what got me, with
   the rule in front of me, and it is intrinsic: an agent writing prose and a
   citation in the same breath will smooth the citation. Mitigated (a whole
   failure-mode entry, a worked example, an instruction to paste the near-miss
   bytes) but not solved — the skill cannot make a model copy instead of
   generate. **I expect at least one of these per blind run.** The good news is
   it costs one edit and `check` points straight at it.
2. **`pace` left at `1.0`.** The metadata document ships with `pace: 1.0` and
   the runtime rule lives in step 4, several screens above where the runner
   writes the file. Step 5 now restates the formula and names the failure
   (`left at 1.0 your episode runs at a third of its target`) rather than
   cross-referencing step 4. If a run still comes back at ~35s and OUT OF
   TOLERANCE, this is why, and the next fix is putting the runtime verdict in
   `check` rather than only in `review`.
3. **Too few beats.** 22–26 beats out of a five-story brief is more than it
   feels like. A runner that writes 12 will still land in tolerance via `pace`
   (that is the formula's virtue) but produce eight-second static cards. This
   failure is *invisible to `check` and to `review`* — nothing in the pipeline
   measures it. The skill argues it in prose; prose is all there is.
4. **A number in a `kicker`.** Kickers read like chrome and are extracted like
   content. The skill lists `kicker` first among claimed fields for that reason.

### Things in the pipeline that made this hard to write

- **`dumbbell`'s citation status is inconsistent between two modules** (§3g).
  `script.py` documents an exemption that `claims.py` and `verify.py` do not
  honour: `cited: False` and `cited_when` imply "an uncited digit-free dumbbell
  is fine", and `check` returns `no_source` and exit 1. One of the two is wrong.
  My reading is that **`verify` is right and the schema comment is stale** — a
  dumbbell asserts a comparison even without digits, and `EXTRACTED_TYPES` is
  the honest classification — but as it stands the schema's own docstrings teach
  an author something that fails. No Python written; recorded here.
- **The count-fit rule is unreachable from the skill's half of the pipeline.**
  D-087's refusal lives in `engine/planbuild.js` and only fires during a render,
  which the author must never run. So an author can produce a script that
  passes `check` and `review` cleanly and still fails at render on a hold. The
  skill compensates with a conservative floor. **`agsoc video check` (or
  `review`) reporting required-vs-actual hold per beat would close this**, and
  it is arithmetic over the plan, not a render.
- **`review` is the only place runtime is reported, and it is not a gate.** An
  agent that runs `check` (exit 0) and stops never learns the episode is 82
  seconds short. The skill orders the two commands and says to read the last two
  lines; a `check` that also printed the runtime verdict would make that
  impossible to skip.
- **Spec §7's example comment is wrong about `pace`.** It says
  `pace: 1.293 # written by agsoc video review, not by the agent`. `review`
  writes nothing at all, by design (D-026, and its own docstring). The agent
  writes `pace`, and the skill says so. Following the code, flagging the spec.
- **§13's `agsoc coverage check` does not exist** (already known; handled as
  above).
- Small: `_pasted` as a source key is discoverable only by listing `sources/`
  or reading `_manifest.json`. `agsoc video ingest`'s success line prints the
  brief path but not the keys it created; printing them would remove a lookup
  the skill currently has to teach.

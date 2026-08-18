# Task 2 Brief: close what the blind run found

**Phase:** 6 · **Branch:** `feat/video-phase-06-storyboard`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

The blind acceptance run **passed**: a fresh agent with no project context
followed `skills/storyboard/SKILL.md`, produced 24 beats, and got **22/22 claims
passing on the first `check`, zero overrides**, runtime `120.0s · within
tolerance`. It never opened a source file or the schema.

That is the phase's exit criterion met once. **This task fixes the twelve things
it had to guess, and the four defects writing the skill exposed** — then a second
blind run by a different agent confirms.

## The one instruction that is wrong, not merely missing

Step 3 says: *"If `agsoc video new` says the episode already exists, do not try
again. You are re-drafting an episode that is already there."*

**That is false when the day already has an episode and the brief is a different
one, and following it edits someone else's work.** The runner was saved only by
an external instruction not to touch `2026-08-17`. It minted `2026-08-17b` and
guessed that was legal.

Fix the instruction **and** give a stated convention for a second episode on one
date. This is the highest-severity item in the list.

## The gap that would have failed most authors

**The corpus keeps the source's typography and the brief's rendering hides it.**
`_pasted.txt` holds U+2011 non-breaking hyphens (`V4‑Pro`, `open‑weight`), em
dashes, curly apostrophes. Anything hand-typed with an ASCII `-` fails `check`
as "quote is not in sources".

The runner survived by *reading the bytes first* and slicing spans
programmatically. **The skill's own author did not** — their single failing claim
was a retyped quote, with the "never retype" rule in front of them (D-109).

"Never retype" is evidently not sufficient as a rule. Say *why* — the bytes
differ from what you see — and give the author a way to extract a span rather
than an instruction to be careful.

## The rest of the friction log

Fix these in the skill; each is one or two sentences:

1. **`voice.md` is an unfilled template** with no video guidance. Say what to do.
2. *(the episode-id item above)*
3. **`agsoc video new`'s own "next" hint omits `--series`** — the CLI's hint is
   wrong and would fail. Fix the CLI hint (see code fixes below).
5. **No guidance on coverage-check keyword granularity** (`deepseek` vs `v4-pro`).
6. **"Cover it as an explicit update" is undefined** — no rule for how much to
   restate, no way to record that you did. Either define it or say "drop it" is
   the supported branch today.
7. **`date_long: ''`** — say whether empty is intended or an authoring hole.
8. **KPI `unit` semantics for magnitudes.** Leader-verified as *correct*:
   `2.4T` → 2.4e12 against "2.4 trillion" passes, `9.4T` and `2.4B` fail. But the
   token *also* lands in `check`'s "names not found" list, so a verified figure
   reads as unchecked. Code fix below; the skill should state that `unit` carries
   magnitude and is checked by value.
9. **Beats-per-act arithmetic only works if the cold open sits outside the acts**,
   and nothing says how many acts to use when `series.toml` declares none.
10. **`pace` trailing zeros** — "3 decimals" is impossible for `1.31` in YAML.
    Say "up to 3 decimals".
11. **`act` on the signoff** is unspecified.

## Code fixes — small, and each is a real defect

- **`dumbbell` citation disagrees across modules.** Leader-verified:
  `script.py` `cited: False`, but `claims.py` has `dumbbell` in
  `EXTRACTED_TYPES`, so an uncited dumbbell gets `no_source` and `check` exits 1.
  **The documented exemption is unreachable.** Decide and make the two agree.
  My reading: a dumbbell asserts a *comparison* even with no digits on screen, so
  requiring `src`/`quote` is the honest resolution — but argue it, and if you
  disagree, say why.
- **A digit-initial token should not also produce an entity atom.** D-106 settled
  that digit-initial is a figure; emitting `2.4T` and `95B` as *names* as well
  puts correctly-verified figures in the "names not found" list. D-102 warned the
  risk with that list is that it stops being read — this is that, arriving.
- **`check` never reports runtime.** Only `review` does, so an agent that stops
  at a green `check` never learns its episode is a third of its target. Add the
  runtime line to `check`.
- **`agsoc video new`'s "next" hint omits `--series`**, so the hint fails for any
  non-`default` series.

## Rules, each with its negative half

- **R1** The skill never instructs an author to edit an existing episode.
  **Negative:** re-drafting your *own* episode stays possible and documented.
- **R2** `check` and `claims.json` agree on which types need citation.
  **Negative:** whatever you decide, both modules say the same thing.
- **R3** A verified figure never appears in "names not found". **Negative:** real
  proper nouns still do (D-102 — recorded, not gated).
- **R4** `check` reports runtime and tolerance. **Negative:** it stays a *claim*
  gate — runtime is reported, never a refusal.
- **R5** Every command the skill tells an author to run works as written.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `dumbbell` uncited → `no_source` still | R2 |
| M2 | citation change silently makes some other type uncited | R2 negative |
| M3 | `2.4T` still an entity atom | R3 |
| M4 | genuine proper nouns dropped from entity atoms | R3 negative |
| M5 | `check` reports no runtime | R4 |
| M6 | `check` *refuses* on runtime | R4 negative |
| M7 | `video new` hint still omits `--series` | R5 |

## Ground rules

- **Commits: tests first, then implementation**, skill changes separate from code
  changes. Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1` in any mutation sweep** (D-100).
- **Never quote a piped exit code** (D-105).
- **If you modify `workspace/`, back it up first and restore it.** Note there are
  now two episodes: `2026-08-17` and the blind run's `2026-08-17b`. **Leave both.**
- Verify every command the skill mentions by running it (D-109: the CLI's own
  hint was wrong, and an author trusts the tool over the doc).
- No new dependencies, no network, no LLM.
- **Report the mutation score.**

---

- [ ] **Step 1** — tests for the code fixes. Failing. Commit.
- [ ] **Step 2** — the four code fixes. Commit.
- [ ] **Step 3** — the skill rewrite covering all twelve items. Commit.
- [ ] **Step 4** — re-run `check` and `review` on **both** existing episodes;
      neither may regress. Paste both.
- [ ] **Step 5** — mutants plus your own sweep.

---

## Your report

`docs/superpowers/worklog/video/phase-06/task-2-report.md`:

1. **Your dumbbell citation decision**, argued.
2. **What you changed in the skill**, item by item against the twelve.
3. **TDD evidence** and the **mutation score**.
4. **Both episodes' `check` and `review`**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What will the second blind runner still get wrong?** Predict it — the last
     prediction was three items and two of them happened.
   - Anything in the friction log you decided *not* to fix, and why.

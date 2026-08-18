# Task 1 Brief: the `storyboard` skill

**Phase:** 6 · **Branch:** `feat/video-phase-06-storyboard`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §13 (skills), §6 (pipeline), §7 (beat catalogue), §8 (verification)

Write `skills/storyboard/SKILL.md`: the instructions an agent follows to turn a
brief and a corpus into a `script.yaml` that passes `agsoc video check`.

## What you are actually writing

**Prose that a stranger executes.** Not documentation. The test is not whether it
reads well — it is whether **a fresh agent with no context follows it and the
first `check` passes with zero overrides.** Someone else runs that test, not you,
and everything they have to guess is a defect in this file.

Write for that reader: an agent that has never seen this repo, holding a brief
and a corpus, that will do exactly what you say and nothing you left out.

## The thing that makes this valuable

Phases 3–5 built a system with **eight specific refusals**, each found by running
real content, each now enforced. An author who does not know them hits them one
at a time, and a refusal you did not expect reads as the tool being broken.

| The trap | What gets refused |
|---|---|
| Display rounding | `round(value, decimals) != value` — `0.756` at 1 decimal shows `$0.8`, a figure in no source |
| A count-up that cannot finish inside its hold | at a 2s hold the final frame read `40%` for an authored `50%` |
| `dumbbell` where magnitudes exist | it renders **no digits at all**, by design — it is for sources that published ratings, not scores |
| `custom` without `attest` | it executes; the attestation is a person's signed sentence |
| `jumpChart.shown` outside `<s>`/`</s>`/entities | it used to be arbitrary JS |
| A figure absent from its beat's `quote` | the entire point of the verifier |
| A row value outside `[0, scale]` | refused, never clipped |
| `<` written literally in `shown` | write `&lt;` — a real cell like `<1% → 3%` needs it |

**Front-load these as positive instructions.** *"Write the figure exactly as the
source writes it"* is followed; *"do not round"* is a rule someone breaks while
believing they complied. Where a rule has a reason a person would find
persuasive, give the reason in a clause — an author who understands why the
dumbbell has no axis will not try to add one.

Do not simply paste the table. Put each rule where the author needs it, in the
step where they would otherwise get it wrong.

## Hard rules the skill must state

- **NEVER run `agsoc video approve`, `render`, or `post`.** Work ends at
  `status: in_review`. This is the project's spine — `fanout` states it first and
  so should you.
- **Never invent a figure.** If a source gives direction rather than magnitude,
  `dumbbell` with its required footnote is the honest form.
- **Every beat that asserts anything carries `src` and a verbatim `quote`**, and
  every figure the beat displays appears inside that quote. A `quote` is copied,
  never retyped.
- **Run the coverage check before writing** (§13). See the open question below.

## Decide these; do not default

- **Coverage.** §13 says always run `agsoc coverage check`. **That command does
  not exist** — coverage lives in `engine/coverage.mjs` until Phase 11
  (`node coverage.mjs check <terms>`, per CLAUDE.md). Say something true today
  that will not need rewriting when the command lands.
- **How many beats, and what holds.** `series.toml` sets `target_sec = 120`,
  `tolerance_sec = 8`, and `[structure]` acts are advisory. Without a concrete
  rule of thumb, every first draft lands OUT OF TOLERANCE — `review` prints
  exactly that. Give the author arithmetic they can do before writing, and check
  it against the two committed episodes, which are the only real scripts that
  exist.
- **`custom`.** It executes, and D-088's substitute for a check is a human
  sentence. **Discourage it**; do not present it as a convenience.

## What to read before writing a word

- `skills/fanout/SKILL.md` — the house style you are matching. Frontmatter, then
  **Hard rules**, then **Workflow**. Short, imperative, no hedging.
- `src/agenticsocial/video/script.py` — `BEAT_TYPES` is the authoritative field
  list. **Every required field of every type must be discoverable from your
  skill**, or the author writes an invalid beat and gets a schema error.
- `workspace/series/the-brief/episodes/2026-08-17/script.yaml` — a real, passing
  script. The best single artefact you have.
- `engine/content/2026-08-14.js` and `2026-08-12.js` — the only two real
  episodes; they are where the pacing and tone answers live.
- Spec §7 (every beat type) and §8 (what verification does).
- `workspace/voice.md` and `series.toml`.

## Ground rules

- **One commit.** This is one file plus whatever it needs.
- **No new Python.** If you believe a command is missing, that is a finding for
  the report — do not build it here.
- **Verify every command you tell the author to run.** Run it. A skill that
  instructs an agent to run a command with the wrong flags is worse than one that
  omits it, because the agent will trust you over the `--help`. `agsoc video`
  subcommands and their exact flags are checkable in one minute.
- **If `workspace/` is modified, back it up first and restore it.** It is the
  operator's own content and is not version controlled by this repo.
- **Never quote a piped exit code** — `cmd | head` reports `head`'s status
  (D-105).

---

- [ ] **Step 1** — read the list above, including both committed episodes.
- [ ] **Step 2** — write `skills/storyboard/SKILL.md`.
- [ ] **Step 3 — walk it yourself, honestly.** Take the brief at
      `workspace/inbox/2026-08-17-ai-brief.md` and follow your own skill as
      literally as you can. **Every time you use knowledge that is not in the
      file, that is a defect — fix the file.** You will not catch them all;
      someone else runs the real test.
- [ ] **Step 4** — commit.

---

## Your report

`docs/superpowers/worklog/video/phase-06/task-1-report.md`:

1. **The decisions you made** on coverage, beat counts/holds, and `custom`.
2. **Your beat-count arithmetic**, and how it checks out against the two
   committed episodes.
3. **What Step 3 caught** — the things you were about to leave implicit. This is
   the most useful section; be specific rather than tidy.
4. **Which required fields you could not fit** into readable instructions, if
   any. A type an author cannot write correctly from your skill is a gap, and
   naming it beats hiding it.
5. **Issues or concerns**, including:
   - **What will the blind runner most likely get wrong?** Predict it. That
     prediction gets checked against what actually happens, and being right about
     a weakness you could not fix is worth more than a confident guess.
   - Anything in the pipeline that made this hard to write — awkward commands,
     missing output, an error message that would not teach an author what to do.

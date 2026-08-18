# Task 1 Brief: `agsoc video console` — the screen that beats a terminal

**Phase:** 12 · **Branch:** `feat/video-phase-12-console`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §12 (the review console), §12.2 screens **C** and **D**

The last phase. Build the one surface §12 says a terminal cannot do well:
**adjudicating claims against source text, with the supporting quote highlighted
in place.**

## Scope, already decided — do not widen it

§12 specifies five screens. **Build C (episode review) and D (claim
adjudication). Do not build A, B, or E.**

**E — approve — must not exist here, and the reason is the project's own
history.** The gate is `agsoc video approve`; it takes identifiers and loads from
disk (D-072) because in v1 **a draft was published** through a second path around
a gate (D-059). *A second way to approve is exactly the defect Phase 7 spent
three tasks eliminating.* The console **prints the command; it never runs it.**

**The console is read-only.** It writes nothing into the episode. Reading a
ledger is safe; writing one makes a second writer, and this project has a
decision about second writers.

## The single most important element

§12.3, verbatim: *"the source excerpt with the supporting quote highlighted in
place. That highlight is the single most important element in the product; design
the screen around it."*

**Everything since Phase 2 exists to make that highlight trustworthy.** The
corpus keeps its bytes (§4). Folding applies to the comparison only (§8.2.1).
`quote_span` records the offset **in the original text, not the folded text** —
and Phase 5 was written that way *specifically so this screen could highlight the
real bytes*. Use the span. If it does not land correctly, that is a finding worth
more than the screen.

Show enough surrounding source that the operator can see the context the quote
was taken from. A quote highlighted with no context around it is the "verbatim
but torn from context" failure (§8.3) rendered as a feature.

## What must survive the trip to HTML

The console is **all summary lines**, and this project has caught itself
overclaiming **six times** (D-106, D-110, D-112, D-118, D-121, D-123), every one
on a summary line, always because a second checker was added and the screens
summarising the first were not moved.

So:

- **Every verdict word comes from `verify.classify()` / `binding_verdict()`.**
  Do not re-implement, do not re-derive, do not map to friendlier language.
- **A `manual` is *attested*, not verified** (D-088, D-121). An attested claim
  carries a person's sentence, and the screen must show the sentence.
- **A pass-2 verdict is a judgement, not a measurement** (D-121). `reproducible:
  false` is a checked field; the screen must not present it with the same weight
  as a mechanical `pass`.
- **`residual_risk` shows even on `supported`** — §8.3 calls it often the most
  useful output of the pass, and Phase 9 found one on a *supported* claim that
  silently ages into falsity on a later render date.
- **A stale ledger must be unmistakable.** A console showing stale verdicts as
  current is the same defect as the summary bugs, with better typography.

## Screen D — override deserves friction

§12: *"It requires a typed reason and is presented as authoring an on-the-record
statement, not clicking 'accept'. Show it will land in the file as a diff. This
is a case where the UI should feel slightly heavier than necessary."*

The console cannot write the override — it prints the YAML the operator will
paste, and the command. **§8.4's asymmetry is the whole design: passing
verification is automatic; bypassing it costs you a written sentence with your
name on it.** A console that made overriding easy would undo it.

## Rules, each with its negative half

- **R1** One self-contained HTML file, **zero network requests**. **Negative:**
  it still works offline from `file://` — `scene.html` already proves this project
  can do that (D-089).
- **R2** The quote is highlighted **in place, in the original source bytes**.
  **Negative:** enough surrounding context to judge whether it was torn from it.
- **R3** Verdict words derive from `classify()`/`binding_verdict()`.
  **Negative:** no second mapping, no friendlier synonyms.
- **R4** The console **cannot approve** and **writes nothing** to the episode.
  **Negative:** it prints the exact commands that do.
- **R5** A stale ledger is unmistakable. **Negative:** a current one is shown
  without noise.
- **R6** `manual` reads as attested; pass 2 reads as a judgement.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | any external request (font, CDN, favicon) | R1 |
| M2 | the highlight computed by searching the folded text | R2 |
| M3 | quote shown with no surrounding source | R2 negative |
| M4 | a verdict word re-derived in the template | R3 |
| M5 | `manual` rendered as "verified" | R6 |
| M6 | pass-2 `supported` styled identically to a mechanical `pass` | R6 |
| M7 | `residual_risk` hidden on `supported` | spec §8.3 |
| M8 | stale ledger rendered as current | R5 |
| M9 | the console writes into the episode directory | R4 |
| M10 | an approve action of any kind | R4 / D-059 |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1`, and paste the harness output** (D-118).
- **Never quote a piped exit code** (D-105).
- **No new dependencies. No network. No CDN, no webfont, no remote favicon.**
- **If you modify `workspace/`, back it up first**, verify the path does not
  already exist, and restore it. Three real episodes: `2026-08-17`, `-17b`,
  `-17c`; they stay unapproved and unedited.
- Never run `agsoc video approve`, `render`, or `post`.
- **Report the mutation score with evidence.**

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — `agsoc video console <ep>`, screen C. Commit.
- [ ] **Step 3** — screen D, the adjudication view. Commit.
- [ ] **Step 4** — mutants plus your own sweep.
- [ ] **Step 5 — open it and look at it.** Generate the console for a real
      episode, **open the file in a browser**, and confirm: the highlight lands
      on the right bytes, no network request is made (check devtools or the CSP),
      and a claim with a `residual_risk` shows it. **Paste the page text and say
      what you saw.**

---

## Your report

`docs/superpowers/worklog/video/phase-12/task-1-report.md`:

1. **How the highlight is computed**, and whether `quote_span` landed correctly
   on real data. If it did not, that is the headline.
2. **Where the file goes**, and whether it is gitignored.
3. **TDD evidence**, the **mutation score with harness output**.
4. **Step 5's evidence**, pasted — including how you verified zero network
   requests.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What can an operator misread on this screen?** You are building the
     surface where someone attaches their name to a claim. Six overclaims in this
     project all lived on summary lines; a console is nothing but summary lines.
   - Phase 11 left `check` unable to distinguish *not covered* from *covered but
     never recorded*. Is the console the place to surface that?

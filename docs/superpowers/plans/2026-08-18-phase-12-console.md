# Phase 12 — The review console

**Goal:** The one screen where a graphical surface genuinely beats a terminal:
**adjudicating claims against source text, with the supporting quote highlighted
in place.**

**Spec:** §12 · **Roadmap:** §5 · **Branch:** `feat/video-phase-12-console`
**Depends on:** 8, 9 — merged.

## Scope, decided rather than discovered

§12 specifies five screens (A series home, B episode list, C episode review,
D claim adjudication, E approve). **This phase builds C and D, and not A, B or
E** — stated up front so it is a decision and not an omission.

The reasoning:

- **§12 itself says what the UI is for**: *"the one step where a graphical
  surface genuinely beats a terminal."* A and B are lists the CLI already prints
  well. **C and D are the step.**
- **E must not be built.** The gate is `agsoc video approve`, it takes
  identifiers and loads from disk (D-072), and it exists because in v1 **a draft
  was published** through a second path around a gate (D-059). *A second way to
  approve is precisely the defect this project spent Phase 7 eliminating.* The
  console links to the command; it never performs it.
- The console is therefore **read-only**, which is also why it is safe to ship
  without a blind acceptance run.

## The single most important element

§12.3: *"the source excerpt with the supporting quote highlighted in place. That
highlight is the single most important element in the product; design the screen
around it."*

Everything the project built since Phase 2 exists to make that highlight
trustworthy: the corpus keeps its bytes (§4), folding applies to the *comparison*
only (§8.2.1), and `quote_span` records the offset in the **original** text
precisely so a UI can highlight the real bytes. **Phase 5 was made to compute
spans against the original rather than the folded text for this screen.**

## Constraints that follow from the project's own rules

- **No new dependencies, no network, no CDN.** The operator is offline on their
  own machine; `scene.html` already proves this project can render a page with a
  strict CSP and zero external requests (D-089).
- **The console never writes to the workspace.** Reading a ledger is safe;
  writing one is a second writer, and this project has a decision about second
  writers (D-059, D-113).
- **It must not overclaim.** Six instances so far (D-106, D-110, D-112, D-118,
  D-121, D-123), every one on a summary line. A console is *all* summary lines.
  `verify.classify()` / `binding_verdict()` are the single source of a verdict
  word — **the console derives from them, it does not re-implement them.**
- **A `manual` is attested, not verified; a pass-2 verdict is a judgement, not a
  measurement** (D-121). Both distinctions must survive the trip to HTML.

## Tasks

**Task 1 — `agsoc video console <ep>`** writes a single self-contained HTML file:
beats grouped by act, the claims panel, and **the source excerpt with the quote
highlighted in place**. Probe frames stand in for the live preview — §12 asks for
the real engine in an iframe, and that is a defensible follow-up, but frames on
disk are what exist and they are honest about being frames.

**Task 2 — the adjudication view** (§12's D): open claims one at a time, what was
asserted, what the source says, why each pass ruled as it did, near-miss
candidates, and the refuter's reasoning. **Override is shown as authoring an
on-the-record statement** with the diff it will produce — and the console prints
the command rather than running it.

## Open questions to decide, not default

- **Where does the file go, and is it gitignored?** It is derived, it contains
  the operator's content, and `workspace/` is already not version controlled.
- **What does the console do about a stale ledger?** `review` already reports
  staleness; a console showing stale verdicts as current is the same defect with
  better typography.
- **Phase 11's gap:** `check` cannot distinguish *not covered* from *covered but
  never recorded*, and nothing nags after a render that an episode is unrecorded.
  The console is the natural place to surface it.

## Exit criteria

- [ ] `agsoc video console <ep>` produces one self-contained HTML file, offline.
- [ ] The supporting quote is **highlighted in place in the source excerpt**.
- [ ] Verdict words come from `classify()` / `binding_verdict()`, never re-derived.
- [ ] `manual` reads as attested-not-verified; pass 2 reads as a judgement.
- [ ] `residual_risk` shows even on `supported`.
- [ ] A stale ledger is unmistakable.
- [ ] **The console cannot approve anything, and writes nothing to `workspace/`.**
- [ ] No network requests; no new dependencies.

## Carried, not done

Screens A, B, E (by decision above). The live `scene.html` iframe preview.
D-124 (`skills/verify` has never had a blind acceptance run). D-056/D-120
(`engine/` unpackaged — `render` works from a source checkout and nowhere else).

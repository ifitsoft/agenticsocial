# Phase 5 — The mechanical verifier

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Every claim a beat makes is checked against bytes on disk, and the result is a durable record a human can adjudicate.

**Spec:** §8 (the claim ledger), §8.1 (the record), §8.2 (pass 1), §8.2.1 (folding), §8.2.2 (claim numbers), §8.4 (the gate)
**Roadmap:** §5 · **Branch:** `feat/video-phase-05-verifier`

**Scope: pass 1 only.** The adversarial pass is Phase 9. This phase builds the
mechanical check — pure Python, no network, no LLM, milliseconds — plus the
ledger it writes and the command that runs it.

## The sentence this phase makes true

Everything since Phase 2 has been building toward one claim, and it is still
false today. The Phase 4 Task 2 implementer said it plainly:

> **Nothing anywhere yet checks that a `value` appears in its `quote`.** R1 only
> checks the quote exists.

Phase 2 built the corpus. Phase 3 gave beats a schema with `src` and `quote`.
Phase 4 made the rendered bytes equal the verified bytes. **This phase closes the
loop**, and after it `agsoc video check` either passes or names exactly which
claim it cannot support.

## What is already decided — read before designing

Six phases produced findings this phase inherits. Re-deriving them wastes a task.

| | |
|---|---|
| **D-071** | §8.2.1 folding (hyphen/dash/quote/space/ellipsis families, comparison only, never on disk) and §8.2.2 claim numbers (strip punctuation, currency, unit suffix; digits-only remains). Both found by running a real brief. |
| **D-081** | `jumpChart.shown` is a documented HTML override — the one field where the frame and the script *should* differ. And CSS `text-transform:uppercase` means any frame reader must case-fold or every kicker false-positives. |
| **D-085** | What a chart shows that nothing can verify: `shown`, `scale`, the `gain` length, footnote text. Ranked, and the first is unclosable by design. |
| **D-083** | A frame reader must sample **past the count**. Mid-count values are unstable, bounded and derived — motion, not assertion. |
| **D-041** | Pasted text is ground truth; `--corroborate` is opt-in and belongs here, not in Phase 2. |
| **D-072** | **A gate takes identifiers, not objects.** `check` loads what it verifies. |

## Global Constraints

- Python ≥3.11. **No new dependencies. No LLM calls** — this pass is mechanical
  and deterministic, and that is what makes it re-runnable in a year.
- **No network in any test.** `tests/conftest.py` guards sockets *and* the
  `research` seam.
- Folding applies to the **comparison only**. The corpus keeps its bytes;
  `sha256` still covers the originals. Normalising on disk breaks §4.
- `script.yaml` is never written by this phase.
- Every verdict names the **beat index and type**, and the **claim id**.

## File Structure

| File | Responsibility |
|---|---|
| `src/agenticsocial/video/claims.py` | extract claims from a `Script`; the record shape |
| `src/agenticsocial/video/verify.py` | pass 1 — fold, quote presence, numeric containment, entity presence |
| `src/agenticsocial/video/cli.py` *(modify)* | `agsoc video check` |
| `tests/test_video_claims.py`, `tests/test_video_verify.py` | |

## Tasks

**Task 1 — claim extraction.** Walk a `Script`'s beats and produce claim records:
id, beat index and type, the rendered text, the atoms (§8.2.2 claim numbers and
entities), `src`, `quote`. **Extraction is where the false-refusal rate is set** —
too greedy and every product name becomes a claim, too shy and a figure slips
through unchecked. D-071 is the settled rule; implement it, do not re-litigate it.

**Task 2 — the mechanical pass and the ledger.** Fold, check quote presence in
the corpus document, check every claim number appears in the quote, check entity
presence. Write `claims.json` per §8.1, including `corpus_sha` so a check is
invalidated when the corpus changes. Verdicts: `pass`, `fail`, `no_source`,
`manual` (for `custom`, whose `attest` is the human substitute).

**Task 3 — `agsoc video check`, and `review` learns to show it.** The command
runs the pass and writes the ledger. `review` gains the thing Phase 3 named as
its biggest gap: **`quote` is invisible today**, so an operator sees `src` but
not what the source actually says.

## The overrides question — decide it in Task 2, do not default

Spec §8.4 gives `claim_override` an escape hatch: a written reason in
`script.yaml`, by name, as a visible diff. That design is deliberate — *passing
verification is automatic; bypassing it costs you a written sentence with your
name on it.*

But D-040 warned about the other end: a checker too strict makes operators
override reflexively and the gate becomes theatre. **Track the override rate as a
health signal from day one**; a high rate means the checker is wrong, not the
operator.

## Exit criteria

- [ ] A beat claiming a figure absent from its quote **fails**, naming the claim.
- [ ] A beat whose quote is absent from the corpus **fails**, distinguishably.
- [ ] The real brief in `workspace/inbox/` verifies clean, non-breaking hyphens
      and all — this is the regression test for D-071.
- [ ] `V4-Pro` does not demand its `4` appear in the quote; `95B` does demand its
      `95`.
- [ ] `claims.json` records `corpus_sha`; a changed corpus invalidates the check.
- [ ] `custom` beats land as `manual` with their `attest` recorded.
- [ ] No network, no LLM, suite stays near 2s.

## Carried, not blocking

`engine/` packaging (D-056) before Phase 8. `video/render.py`'s subprocess seam
unguarded in tests (D-067). `date_long` never reaches the screen and `warm_acts`
is dropped by `planbuild.js` (D-081) — both belong to whichever phase next
touches the title card.

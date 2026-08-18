# Phase 7 — The approve gate and drift detection

**Goal:** `agsoc video approve` is the one gate, it refuses on open claims, and an
approval is bound to the exact bytes it approved.

**Spec:** §8.4 (the gate), §10 (status machine), §6 (pipeline)
**Roadmap:** §5 · **Branch:** `feat/video-phase-07-approve`
**Depends on:** 5 (verifier) — merged.

## The sentence this phase makes true

Phase 5 can tell you a claim is unsupported. **Nothing stops you rendering
anyway.** `approve` is the one place the project spends its authority, and §8.4
is unambiguous about what it costs to get past it.

## What this phase inherits, and must not re-derive

| | |
|---|---|
| **D-072** | **A gate takes identifiers, not objects.** `approve(ws, series, ep)` loads what it gates. |
| **D-059** | The v1 defect this exists to prevent: a **draft was published**. The gate was skipped from an in-memory object, then `save_variant` stamped the status on disk, and the closing transition passed legitimately. **The bypass laundered itself.** Root cause: a second, ungated status writer. |
| **D-062** | Freezing stops *accidental* forging only — `dataclasses.replace(v, status=...)` forges in one line. Do not claim more. |
| **D-103** | `claim_override` is a mapping (`reason`, `by`), both required and non-blank. **This phase is what consumes it.** |
| **D-104** | `check` already reports an override as *recorded, not applied* — approve is where "applied" happens. |
| **D-102** | Entity misses are **recorded, not gated**. Do not let them block approval. |
| **D-088** | An unattested `manual` blocks; an attested one is a human's signed sentence and passes. |

## The gap Phase 5 named, and this phase must close

Task 3's report, verbatim: *"nothing binds the ledger to the script's bytes — a
changed `scale` shifts every bar with no wrong digit and leaves the ledger
looking current."*

That is the drift case §10 cares about, in its most dangerous form: **an edit
that changes what the viewer sees while every claim still verifies.** `corpus_sha`
cannot see it, and neither can a numeric check, because no number changed.
`script_sha256` is the answer and this is the phase that records it.

## Global constraints

- **Only the CLI moves status.** The agent writes `in_review` and stops
  (CLAUDE.md, and it applies to implementers).
- `approved → rendering` is gated on `claims.json` being clean (§8.4).
- Editing an approved script does **not** silently keep approval: `approve`
  records `script_sha256` and drift is named, per §10 — *stricter than the text
  side, deliberately, because a render is expensive and a video is harder to
  retract.*
- All workspace writes via `workspace.atomic_write`.
- No network, no LLM, no new dependencies.

## Tasks

**Task 1 — the gate.** `agsoc video approve <ep> [--series S]`. Refuses while any
claim is `fail`, `no_source`, or an unattested `manual`. Records `script_sha256`
and the approver. Takes identifiers and loads from disk (D-072). **Refuses on a
stale or absent ledger** — approving against a ledger that no longer describes the
script is the same defect as not checking at all.

**Task 2 — overrides, applied.** §8.4's escape hatch, and the asymmetry is the
design: *passing verification is automatic; bypassing it costs you a written
sentence with your name on it.* An override clears exactly the claim it names —
never a whole beat, never the episode. Report the override rate; D-040 says a
high rate means the checker is wrong, not the operator.

**Task 3 — drift.** `script_sha256` binding, and a `render`-side refusal naming
what changed. Phase 5's `stale_reason` already answers the script half; wire it,
do not rebuild it.

## Open questions to decide, not default

- **Who is the approver?** §8.4's override carries `by:`. Approval should too, and
  there is no user identity in this system. Decide the source and say why.
- **Does `approve` re-run `check`, or require a fresh ledger?** Re-running is
  friendlier; requiring is stricter and makes the ledger the artifact of record.
  Argue it — this is the phase's one real design choice.
- **What un-approves?** `approved → in_review` exists in `VIDEO_TRANSITIONS`.
  Decide whether a drifted script auto-returns there or simply refuses to render.

## Exit criteria

- [ ] An episode with any `fail` / `no_source` / unattested `manual` **cannot** be
      approved, and the refusal names the claim.
- [ ] A clean episode approves, records `script_sha256` and the approver.
- [ ] Editing the script after approval is **detected and named**, including an
      edit that changes no number (the `scale` case).
- [ ] An override clears exactly one claim, requires `reason` + `by`, and is
      visible in `review`.
- [ ] **There is no second status writer.** Prove it: search for every path that
      writes status and show the gate covers all of them (D-059).
- [ ] No network, no LLM.

## Carried

D-107 (word-spelled figures) is Phase 9. `render` itself is Phase 8 — this phase
supplies the refusal it enforces, not the renderer.

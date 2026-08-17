# Phase 2 — Ingest: build the verification corpus

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Turn a research query, a pasted digest, or an existing agsoc source into a **corpus on disk** — the fetched text that every later claim is checked against.

**Architecture:** Reuses v1's `research.py` (ddgs search, trafilatura extraction) for fetching. Phase 2 adds the corpus layer: one text file per source, a manifest binding each to its URL, fetch time and sha256, and `brief.md` as the human-readable assembly. No LLM calls — `research.py` fetches and formats, it never summarises (`CLAUDE.md`).

**Spec:** `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md` §4, §5, §11
**Roadmap:** `docs/superpowers/plans/2026-08-16-video-mvp-roadmap.md` §5
**Branch:** `feat/video-phase-02-ingest`

## Why the corpus is the point

Spec §4 states it plainly: *the verification corpus is a directory of fetched
text, not a memory.* A claim is never checked against what an agent recalls
reading — it is checked against bytes on disk. That is what makes Phase 5's
verification reproducible months later, and what lets the review console
highlight the exact supporting span.

Everything in this phase serves that: **if the corpus is not trustworthy, the
fact-checking built on it is theatre.**

## Global Constraints

- Python ≥3.11. No new dependencies — `ddgs` and `trafilatura` are already in `pyproject.toml`.
- **No network in any test.** `research.search` and `research.extract` are stubbed at the module boundary; `respx` exists for anything using `httpx` directly.
- All writes through `workspace.atomic_write`. A failed fetch must never leave a half-written corpus file.
- `script.yaml` is never written by this phase.
- Corpus files are UTF-8. A source key becomes a filename — the Phase 1 path-safety rules apply (D-038).

## File Structure

| File | Responsibility |
|---|---|
| `src/agenticsocial/video/corpus.py` | corpus files + `_manifest.json`: write, read, verify |
| `src/agenticsocial/video/ingest.py` | orchestrates research / paste / from-source into a corpus + `brief.md` |
| `src/agenticsocial/video/cli.py` *(modify)* | `agsoc video ingest` |
| `src/agenticsocial/workspace.py` *(modify)* | D-049 gate fix |
| `tests/test_video_corpus.py`, `tests/test_video_ingest.py` | |

## Tasks

**Task 0 — carried debt.** D-049 (the text pipeline's `set_status` gates on the in-memory `Variant`, the identical bug fixed in `episode.py`) and D-057 (two tests that would launch real Chromium if a guard were removed). Small, and it clears the decks before new work lands on top.

**Task 1 — the corpus.** `corpus.py`: write a fetched document as `sources/<key>.txt`, record `{url, title, fetched_at, sha256, bytes}` in `sources/_manifest.json`, and verify a corpus against its manifest. This is the integrity layer; it gets the most adversarial attention.

**Task 2 — ingestion.** `ingest.py`: `--research "query"` (search, extract, write), `--paste FILE` (the paste *is* the corpus, per D-041), `--from-source ID` (pull an existing agsoc source's body in). Assembles `brief.md`. Partial failure is the normal case — three sources fetched, one 403 — and must produce a usable corpus plus an honest record of what failed.

**Task 3 — the CLI.** `agsoc video ingest`, with the subprocess-free error surface Phase 1 established: no traceback reaches an operator, and network failure is reported per-source rather than aborting the run.

`--corroborate` (D-041) is **not** in this phase. Pasted text is ground truth; web-checking it is a verification concern and belongs with Phase 5, where the claim ledger exists to record contradictions.

## Exit criteria

- [ ] `agsoc video ingest <ep> --research "<query>"` writes a corpus and a brief, offline-testable.
- [ ] `--paste` makes the pasted text the corpus verbatim, with its own manifest entry.
- [ ] Every corpus file's recorded sha256 matches its bytes; a tampered corpus is detectable.
- [ ] One source failing to fetch does not lose the others, and the failure is recorded.
- [ ] No network in the suite; runtime stays near 1s.
- [ ] No traceback from anything an operator can type.

## Carried into this phase from Phase 1 / 1.5

Beyond Task 0: series field validation (D-025), `script.yaml` separator robustness
and BOM (D-040), and 12 `series.py`/`episode.py` asymmetries (D-042). These are
**not** blocking Phase 2 and get picked up where their consumers appear — but
D-042's two separate `64` constants should be unified the first time anything in
this phase touches either module, per D-036.

**`engine/` is not in the wheel (D-056) — required before Phase 8, not here.**

# Phase 2 Gate: whole-branch adversarial review

**Branch:** `feat/video-phase-02-ingest` vs `main`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

You are reviewing an entire phase. Nothing here is merged. Your verdict decides
whether it is.

## What this phase was for

Spec §4: *the verification corpus is a directory of fetched text, not a memory.*
A claim is checked against **bytes on disk**, never against what an agent recalls
reading. Phase 2 builds that corpus and the ingestion that fills it.

**If the corpus is not trustworthy, every fact-check built on it is theatre.**
That sentence is the review's centre of gravity.

## Read first

- `docs/superpowers/plans/2026-08-17-phase-02-ingest.md` — the plan and its exit criteria
- `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md` §4, §5, §11
- `docs/superpowers/worklog/video/DECISIONS.md` — **D-059 through D-065 especially**

**Do NOT read** any `task-*-report.md`.

## Scope

```
git diff main..HEAD -- src tests
git log --oneline main..HEAD
```

`src/agenticsocial/video/{corpus,ingest,cli}.py`, plus changes to
`workspace.py`, `models.py`, `x/publish.py`, `cli.py`, `video/{models,episode,series}.py`.

## What this phase already knows about itself — do not re-report these

- `corpus.py` had **12 of 14 mutants survive** on first pass; Task 1c closed all
  seven real ones. Remaining survivors are cosmetic (`sort_keys`, `indent`,
  `ensure_ascii`, a redundant `sorted()`, one unreachable recheck).
- The `-2` collision key was fetch-order-dependent; Task 2 fixed it by looking up
  the exact URL in the manifest.
- `assert_safe_name` moved to `workspace.py`.
- `Variant`, `Episode` and `Series` are frozen (D-062) — and freezing stops
  *accidental* forging only; `replace()` still forges in one line. That is
  known and accepted; the load-bearing defence is that no gate reads the object.

## Attack these

**1. The integrity claim.** Can you make `verify()` return `[]` on a corpus whose
bytes are not what was recorded? Try: a manifest entry with no `sha256`, a
`sha256` of `None`, a document that is a symlink, a manifest key with a `.txt`
already in it, unicode normalisation differences, a zero-byte document. This is
the claim the product rests on.

**2. Four gate bypasses were fixed in this phase (D-059).** One of them published
an unapproved draft. **Try to publish a draft.** Try to reach `RENDERING` without
`APPROVED`. Use `dataclasses.replace`, stale objects, hand-edited files, and
`save_variant`. Run the real CLI in a subprocess where it matters.

**3. The no-network guarantee is conditional and that was only found by
mutation.** Task 3 discovered its suite reached the live network the moment the
implementation was wrong — it hung for ten minutes rather than failing. **Verify
the `no_network` fixture is total**: break `ingest.py` and `cli.py` in several
ways and confirm no test reaches a socket. A suite whose isolation depends on the
code being correct is not isolated.

**4. Path safety in corpus keys.** Keys become filenames and, from Phase 5, come
from **agent-authored YAML**. Try to read or write outside `sources/`.

**5. Harness blindness (D-035, D-064).** For every negative test: *what would it
do if the code did nothing at all?* This phase found five vacuous tests, four of
them mine, including one in the brief that introduced the anti-vacuity method.
**Assume there are more.** Known forms: a fixture invalid in the wrong dimension;
a symmetric encode/decode on both sides; a runner converting failures to values;
an assertion satisfied by incidental text (`assert "1" in output` against an
episode id containing `1`).

**6. Sibling asymmetry (D-036).** Five instances so far. Compare `corpus.py`,
`ingest.py`, `episode.py` and `series.py` function by function. A long list beats
a clean bill of health.

**7. Spec coverage.** §4, §5 (`sources/`, `_manifest.json`, `brief.md`), §11
(`agsoc video ingest`). Anything in scope with no implementation, or implemented
without authorisation?

## Known and deliberately deferred — do not re-report as new

- `--corroborate` is Phase 5, not here (D-041): pasted text is ground truth, and
  recording a contradiction needs the claim ledger.
- `%YAML` directives, leading blank lines, missing leading `---`, UTF-8 BOM in
  `script.yaml` raise `EpisodeError` though PyYAML accepts them.
- `tolerance_sec`, `name`, `byline`, `register`, `design.*` accept wrong types.
- `engine/` is not in the wheel (D-056) — required before Phase 8.
- A symlinked series or `episodes/` directory can write outside the workspace,
  accepted deliberately (D-041/D-057).

**Do** tell me if you think any of those is harm rather than confusion.

## Output

Write to `docs/superpowers/worklog/video/phase-02/phase-gate-review.md`:

**Verdict** (`merge` / `merge-after-fixes` / `do-not-merge`) · **Findings**
ranked, each with file:line, a concrete failure scenario, a suggested fix ·
**Harness-blindness audit** — every test you believe cannot fail ·
**Sibling asymmetry list** · **Mutation results**, weighted toward `ingest.py`
and `cli.py`, which have had the least adversarial attention · **Spec coverage** ·
**What I could not verify**.

Do NOT commit. Restore every file you touch; confirm
`git status --porcelain -- src tests` is empty. `docs/` may change while you
work — that is the leader, not interference.

Final message: the verdict, one line per finding, your mutation results, whether
the no-network fixture is total, and plainly whether you would put your name on
merging this to `main`.

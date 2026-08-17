# Phase 2 — Ingest: the verification corpus

Builds the corpus every later fact-check is checked against, and the ingestion
that fills it. **Also fixes a bug that could publish an unapproved draft to X.**

**Plan:** `docs/superpowers/plans/2026-08-17-phase-02-ingest.md`
**Spec:** §4, §5, §11 · **Decisions:** D-059 … D-067

---

## What you can do

```bash
agsoc video ingest 2026-08-17 --series the-brief --paste workspace/inbox/brief.md
agsoc video ingest 2026-08-17 --series the-brief --research "gemini 3.7 pricing"
agsoc video ingest 2026-08-17 --series the-brief --from-source 2026-08-14-kill-staging
```

Each writes `sources/<key>.txt`, a `sources/_manifest.json` binding every document
to its URL, title, fetch time, byte count and **sha256**, and a `brief.md`
regenerated from the manifest.

Run against a real 7.7 KB research brief: ingested, sha256 recorded, `verify()`
sound, and a same-length tamper (`$0.75` → `$9.75`, byte count unchanged) is
detected.

## Why the integrity work is the point

Spec §4: *the verification corpus is a directory of fetched text, not a memory.*
A claim is never checked against what an agent recalls reading — it is checked
against bytes on disk. That is what makes Phase 5 reproducible a year later and
what lets the review console highlight an exact supporting span.

Concretely, on a real brief:

```
PASS    DeepSeek V4-Pro costs $1.32 per 1M input tokens.
PASS    DeepSeek raised prices by up to 1,100%.
REFUSE  DeepSeek raised prices by 1,400%.        <- invented figure
REFUSE  Gemini 3.7 Flash costs $0.75/1M tokens.  <- true, but not in THIS source
```

The second refusal is the design in miniature: `$0.75` is a real price, but the
source does not say it, so the video may not claim it (D-041).

## ⚠️ A draft could be published. Fixed here.

`v1` shipped with a bug that broke the README's central promise — *"Nothing goes
live without you running `agsoc approve`"*. Verified before the fix:

```
status on disk : draft
tweets posted  : 2
status after   : published
```

**The bypass laundered itself** in three individually-defensible steps: the gate
was skipped because it was decided from an in-memory object; the posting loop's
`save_variant` then stamped `publishing` onto the draft; the closing transition
therefore passed legitimately. The final file is indistinguishable from a proper
publish.

Root cause: `save_variant` was a **second, ungated status writer**. The video
pipeline had exactly one gated writer; the text pipeline had two. Both pipelines
now have one, and the gate reads disk rather than the object.

That was the fourth bypass of the same family (D-045, D-049, D-059). `Variant`,
`Episode` and `Series` are now frozen — which stops *accidental* forging, not
deliberate forging; **the load-bearing defence is that no gate reads the object**
(D-062).

## What's in it

| | |
|---|---|
| `video/corpus.py` | documents, manifest, `verify()` |
| `video/ingest.py` | research / paste / from-source; partial failure is normal |
| `video/cli.py` | `agsoc video ingest` |
| `workspace.py` | one gated status writer; `assert_safe_name` rehomed here |
| `models.py`, `video/models.py` | `Variant`, `Episode`, `Series` frozen |

## Test plan

`uv run pytest` — **482 passed in ~2s**, offline, no new dependencies. **No test
touches Playwright, ffmpeg or the network.**

Worth trying to break: `--paste` a cp1252 file, `--paste` a missing file, two
input modes at once, no input mode, an unknown `--from-source`, a `--series`
containing `../`. Each was a real defect at some point.

## Known and deliberately deferred

- `--corroborate` is Phase 5 (D-041) — recording a contradiction needs the claim
  ledger that does not exist yet.
- `engine/` is not in the wheel (D-056) — **required before Phase 8**.
- `%YAML`, BOM, and missing-leading-`---` scripts raise `EpisodeError` though
  PyYAML accepts them; `tolerance_sec`/`register`/`design.*` accept wrong types.
- A symlinked series directory can write outside the workspace — accepted
  deliberately (D-041).

## Notes on how this was reviewed

Mutation testing found what reading did not, repeatedly. `corpus.py` had **12 of
14 mutants survive** on first pass; all seven real ones are now closed.
`ingest.py`/`cli.py` finished at **18/19 with the survivor proven equivalent**.

Four findings worth naming, none of which was visible by reading the code:

- **The suite's no-network guarantee was a convention, not a mechanism.** A
  gate review measured 17 outbound attempts across three mutants; one run took
  150s against a 2s baseline. A socket guard turned out to be half a fix —
  `ddgs` fetches through `primp`, a Rust client that never touches Python's
  `socket` module. **You cannot guard a boundary you do not own**, so the guard
  now sits on `research.search`/`research.extract`, this project's only two
  fetch calls. Those mutants now fail in 0.8s instead of timing out at 90s.
- **`verify()` trusted its own manifest.** A key of `../../../../../../outside`
  made it report a corpus SOUND while `sources/` held no documents, having
  hashed a file outside the workspace to say so. That is the claim Phase 5 rests
  on, defeated by the thing it was meant to check.
- **Publishing could grant itself** — `post --resume` honoured a `publishing`
  status with `approved_at: null`.
- **A brief-supplied implementation had a silent-wrong-citation bug** its own
  test caught: the returned key said `blog-google` while the bytes landed in
  `blog-google-2`. Any claim citing it would have pointed at the wrong article.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

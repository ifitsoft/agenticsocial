# Task 3d Report: Fix the separator arithmetic, pin metadata bytes

**Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `c47236b`

## 1. What I changed

`src/agenticsocial/video/episode.py`:

- `_SEP_RE` now *consumes* the separator's trailing newline instead of looking
  ahead at it: `r"(\r\n|\r|\n)---[ \t]*(\r\n|\r|\n)"`.
- `_split` slices the remainder from `sep.end()`, with no arithmetic at all.
  The old `sep.end() + len(sep.group(1))` computed the offset from the
  **leading** newline's length; with CRLF metadata and LF beats it skipped two
  bytes where only one existed and ate the `b` of `beats:`.
- Docstring rewritten to state why the lookahead must not come back, and why
  the search starts at `start.end() - len(nl)`.

Nothing else changed. `_compose` was already correct.

I followed the brief's code blocks verbatim. They did not disagree with the
prose anywhere.

## 2. TDD evidence

### RED (after commit 1, before the fix) — `/tmp/red.txt`

```
FAILED tests/test_video_episode.py::test_mixed_line_endings_preserve_beats_bytes[\r\n-\n] - AssertionError: assert b'beats:\n  - type: statement\n' in b'---\r\nepisode...
FAILED tests/test_video_episode.py::test_mixed_line_endings_preserve_beats_bytes[\r\n-\r] - AssertionError: assert b'beats:\r  - type: statement\r' in b'---\r\nepisode...
FAILED tests/test_video_episode.py::test_first_byte_of_beats_is_never_eaten - AssertionError: assert b'beats:' in b'---\r\nepisode: e\r\nseries: the-brie...
========================= 3 failed, 55 passed in 0.59s =========================
```

The corruption is visible in the failure output:

```
b'---\r\nepisode: e\r\nseries: the-brief\r\nstatus: in_review\r\n---\r\neats:\n  - type: statement\n'
```

Three of the eight new tests failed. Noted honestly:

- `test_an_all_crlf_script_stays_all_crlf` and `test_an_all_lf_script_stays_all_lf`
  passed at RED. They are mutation-killers, not bug-reproducers; the CRLF one is
  the only thing that kills mutant 2.
- The two *mirror* mixed cases (`\n`/`\r\n` and `\n`/`\r`) also passed at RED.
  Under the old code those inserted a **spurious leading newline** rather than
  eating a byte, and `assert beats.encode() in raw` cannot see a prepended
  byte. They are weaker than the brief implies — they only bite when the
  leading newline is the longer one. They do fail under mutant 1 (see below),
  because the `create_episode`-written LF baseline shifts the arithmetic.

### GREEN — `/tmp/g1.txt`, `/tmp/g2.txt`

```
============================== 58 passed in 0.69s ==============================
```

```
============================= 242 passed in 1.40s ==============================
```

234 → 242 is exactly the 8 tests added (5 parametrised + 3).

## 3. Mutation results

Each mutant applied to the fixed source, full suite run, `git checkout` between.

| # | Mutation | Result | Caught by |
|---|---|---|---|
| 1 | `_split` → `text[sep.end() + len(sep.group(1)) :]` | **killed** — 18 failed, 224 passed | `test_first_byte_of_beats_is_never_eaten`, all five `test_mixed_line_endings_preserve_beats_bytes` params, `test_beats_without_a_trailing_newline_is_preserved`, + 11 more |
| 2 | `_compose` → drop `head.replace("\n", nl)` | **killed** — 1 failed, 241 passed | `test_an_all_crlf_script_stays_all_crlf` (`assert 2 == 0`, output `b'---\r\nepisode: e\nseries: the-brief\nstatus: in_review\r\n---\r\nbeats:\r\n...'`) |
| 3 | `_SEP_RE` lookahead + `text[sep.end():]` | **killed** — 8 failed, 234 passed | `test_beats_bytes_survive_a_status_change[\n,\r\n,\r]`, `..._repeated_status_changes`, `test_trailing_whitespace_and_tabs_in_beats_are_preserved`, `test_beats_without_a_trailing_newline_is_preserved` |
| 4 | `_split` → search from `start.end()` | **SURVIVED — 242 passed** | nothing |

**Mutant 2 is dead this time.** The 3c survivor is killed by
`test_an_all_crlf_script_stays_all_crlf`, which is the first test in the suite
to assert on the metadata block's bytes.

**Mutant 4 survives.** Stated plainly, and nothing was adjusted to hide it.
`start.end() - len(nl)` only matters when the metadata document is **empty** —
`---\n---\nbeats:\n` — so the newline closing the opening fence must double as
the separator's leading newline. No test in the suite writes an empty metadata
document. Under mutant 4 that file splits differently (no separator found), so
the beats document would be discarded and replaced with `beats: []`. Confirmed
by hand: the behaviour is real and unpinned. I did not add a test for it,
because the brief lists the four mutants under Step 4 as a check, not as a
licence to keep writing tests until they all die — flagging it is the honest
output. One extra test would fix it:
`ep.script_path.write_bytes(b"---\n---\nbeats:\n  - x\n")` then assert
`b"beats:\n  - x\n"` survives.

## 4. Files changed

- `src/agenticsocial/video/episode.py` — `_SEP_RE`, `_split`
- `tests/test_video_episode.py` — 8 tests appended, nothing modified

| Commit | SHA | Message |
|---|---|---|
| 1 (RED) | `910c850` | `test: pin mixed line endings and the metadata block's bytes` |
| 2 (GREEN) | `7f09648` | `fix: consume the separator's trailing newline instead of guessing its length` |

`git status --porcelain -- src tests` is clean.

## 5. Issues and concerns

### Q1. Which newline does the separator line itself use when metadata and beats disagree — and is that defensible?

**The metadata document's.** `_compose` emits `f"---{nl}{head}{nl}---{nl}{body}"`
and `nl` comes from `_DOC_START_RE`, i.e. the newline that ends the *opening*
fence. Observed:

```
IN : b'---\r\nepisode: e\r\nstatus: draft\r\n---\nbeats:\n  - x\n'
OUT: b'---\r\nepisode: e\r\nstatus: in_review\r\n---\r\nbeats:\n  - x\n'
```

The separator's own LF was rewritten to CRLF. That **is** a byte the operator
wrote, changed by a write path.

It is defensible, and I would not change it:

- The separator line belongs to the metadata block we re-emit; the beats
  document begins at the byte after it. Some choice has to be made, and taking
  it from the block we own is the coherent one.
- It is **idempotent**. I verified the second write is byte-identical modulo
  the status value, for the mixed case, the trailing-tab case, and the
  blank-line case (`/tmp/probe2.out`). So it normalises once and never churns
  `script_sha256` again.
- The alternative — remembering the separator's trailing newline and re-emitting
  it — would preserve one more byte at the cost of a second newline variable
  threaded through `_read_meta`/`_compose`, which is precisely the kind of
  parallel-newline bookkeeping that produced defects in attempts 1–3.

Worth recording as a decision rather than leaving implicit: *the guarantee is
about the beats document, not the whole file.* The metadata document and the
separator line are tool-owned and get normalised.

### Q2. Is there any remaining input where a write path changes a byte the operator wrote?

**Inside the beats document: I could not break it.** I probed 24 adversarial
inputs across two scripts (`/tmp/probe.py`, `/tmp/probe2.py`; outputs in
`/tmp/probe.out`, `/tmp/probe2.out`) and every one round-tripped the
post-separator bytes exactly:

empty metadata document · separator line with trailing spaces and tabs · a
`---` line **inside** the beats document · beats with no trailing newline ·
empty beats document · beats that is a single newline · beats starting with
spaces · beats starting with a blank CRLF line · beats immediately starting
with another `---` · a lone CR inside otherwise-CRLF beats · a `\r\n\r\n\n…\r`
mixture inside one beats document · a CR-only (classic Mac) file · a YAML
document-end `...` marker · tabs and astral-plane emoji · all five mixed
metadata/beats pairings · repeated draft → review → approve cycles.

Only two write paths exist (`set_status`, `create_episode`) — `script_path` is
referenced nowhere else in `src/`, so there is no third path to audit.

**Outside the beats document, yes — five, all in the metadata block, all
normalisation rather than corruption:**

1. **Comments in the metadata document are destroyed.**
   `---\n# operator note\nepisode: e\n…` → the comment is gone. This is
   `yaml.safe_dump` doing exactly what the module docstring says it does to
   beats — we just accept it for doc 1.
2. **Block scalars in metadata are reflowed, and can lose a trailing newline.**
   `note: |\n  ---\n  keep me\n` → `note: '---\n\n  keep me'`. Round-tripping
   that gives `"---\nkeep me"` where the operator wrote `"---\nkeep me\n"`.
   That is a *semantic* change, not just formatting. Nothing in Phase 1 writes
   block scalars into doc 1, so it is latent.
3. **A blank line before the separator is swallowed**, because it becomes the
   separator's leading newline: `status: draft\r\n\r\n---\n` → `status: draft\r\n---\r\n`.
4. **Trailing whitespace on the separator line is stripped**: `--- \t\n` → `---\n`.
5. **Exotic YAML line breaks in metadata are normalised**: a NEL (`\xc2\x85`)
   between two metadata keys comes back as `\n`. Harmless, worth knowing.

**Two robustness defects found while probing — neither is byte corruption, both
are worth a follow-up:**

- **`UnicodeDecodeError` escapes the `EpisodeError` contract.** `_read_meta`
  catches only `OSError`. A single latin-1 byte anywhere in the file — a `é`
  pasted from a non-UTF-8 source, a lone surrogate — crashes with a raw
  `UnicodeDecodeError`:
  ```
  latin-1 byte in beats: *** UnicodeDecodeError escapes the contract: 'utf-8' codec can't decode byte 0xe9 in position 47
  ```
  Task 4's `except EpisodeError` in `agsoc video list` will not catch this, so
  one bad byte in one episode takes out the whole listing — the exact failure
  mode D-018 exists to prevent. The fix is one line: add `UnicodeDecodeError`
  to the `except` clause in `_read_meta`. I did not make it, because it is
  outside this brief's stated file-level change and belongs with its own test.
- **A UTF-8 BOM makes the episode unreadable** with a confusing message:
  `cannot parse script metadata — expected '<document start>'…`. `﻿---`
  fails `_DOC_START_RE`, so the whole file is handed to the YAML parser.
  Windows editors emit BOMs routinely. `encoding="utf-8-sig"` on the read
  (paired with plain `utf-8` on the write) would handle it — but note that
  silently dropping the BOM *is itself* a byte change, so this needs a decision,
  not a reflex fix. It currently fails loudly, which is the safe default.

A NUL byte inside beats, for the record, passes through untouched.

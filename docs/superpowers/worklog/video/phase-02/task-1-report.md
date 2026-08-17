# Task 1 Report: The corpus — files, manifest, integrity

**Branch:** `feat/video-phase-02-ingest` · **Follows:** `1fb5703`
**Commits:** `485dbf6` (tests) · `2a43613` (implementation)

## 1. What I implemented

`src/agenticsocial/video/corpus.py`, exactly as the brief's code block specifies —
no deviations, no additions, no dependencies. `CorpusError`, `MANIFEST_NAME`,
`key_for`, `read_manifest`, `document_text`, `write_document`, `verify`.

The three load-bearing properties are all present and all pinned by tests:
document written before manifest; `sha256` of the exact bytes recorded; keys
routed through `_assert_safe_name` before any write.

No network in source or in tests. The module imports only `hashlib`, `json`,
`datetime`, `urllib.parse` and three project modules.

**Brief-vs-code disagreements found: none.** I checked every prose claim against
the code block. The two that looked like candidates both hold up:

- Prose says an explicit key is "used verbatim". The code applies the collision
  suffix to explicit keys too, so verbatim is conditional on no collision. The
  test only covers the non-colliding case. This is a documentation nuance, not a
  contradiction — flagged, not changed.
- Prose says keys become filenames and unsafe keys are "a `CorpusError`, never a
  write". True in `write_document`; the guard also sits in `document_text`, which
  the prose does not mention. That is correct behaviour, under-described.

## 2. TDD evidence

### RED — `485dbf6`, before any implementation existed

```
tests/test_video_corpus.py:5: in <module>
    from agenticsocial.video import corpus as C
E   ImportError: cannot import name 'corpus' from 'agenticsocial.video'
ERROR tests/test_video_corpus.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.07s
```

RED here is a collection error, not 29 individual failures — the module did not
exist, so pytest could not collect the file. Worth stating plainly rather than
implying per-test RED.

### GREEN — `2a43613`

```
collected 29 items
...
29 passed in 0.51s
```

All 29 corpus tests pass. Full suite:

```
412 passed in 1.51s
```

## 3. Mutation results

Each mutant applied in isolation, full suite run, file restored between.
Mechanised in a throwaway script; nothing under `src/` or `tests/` was left
modified (verified with `git status --porcelain -- src tests`).

| # | Mutant | Result | Killed by |
|---|--------|--------|-----------|
| 1 | manifest written before document | **KILLED** — 1 failed / 411 passed | `test_the_document_is_written_before_the_manifest` |
| 2a | `hashlib.sha256(text)` — literally | **KILLED** — 14 failed / 398 passed | `TypeError` at every write; 12 named below plus 2 more |
| 2b | `hashlib.sha256(text.encode())` | **SURVIVED** — 412 passed | *nothing — see below* |
| 3 | collision suffix loop dropped | **KILLED** — 1 failed / 411 passed | `test_same_host_twice_gets_a_distinct_key` |
| 4 | orphan scan skipped | **KILLED** — 2 failed / 410 passed | `test_verify_detects_an_orphan_file`, `test_verify_reports_every_problem_sorted` |
| 5 | `verify` compares `bytes`, not `sha256` | **SURVIVED** — 412 passed | *nothing — real gap, see §6* |
| 6 | `www-` strip dropped | **KILLED** — 1 failed / 411 passed | `test_key_for_derives_from_the_host[www.reuters.com]` |
| 7 | `document_text` drops `_assert_safe_name` | **SURVIVED** — 412 passed | *nothing — real gap, see §6* |

### Mutant 2 — you asked whether it is even a behaviour change. It is not.

I ran it both ways rather than assuming, because the mutant is ambiguous as
written.

**Read literally** (`hashlib.sha256(text)` with `text` still a `str`), it is not
a hashing change at all — it is a `TypeError: Strings must be encoded before
hashing` raised on every call to `write_document`. 14 tests fail, but they fail
because the function is broken, not because the digest is wrong. Counting that
as a kill would be counting a crash as an integrity check.

**Read as intended** (`hashlib.sha256(text.encode())`), it is a **no-op**. `raw`
is defined three lines above as `text.encode("utf-8")`, and `str.encode()`
defaults to UTF-8, so the two expressions are the same bytes. The full suite
passes — correctly. There is nothing to kill.

This is not a hole in the tests. The only way `text.encode()` could diverge from
the bytes on disk is if `atomic_write` encoded differently; it opens with
`encoding="utf-8", newline=""`, so it does not. `raw` is a local alias that also
serves `bytes`, and using it twice is tidier than encoding twice — but it buys no
correctness that `text.encode()` would lose.

**Verdict: mutant 2 is equivalent, not surviving. No kill to report.**

## 4. Files changed

| Commit | File | Change |
|--------|------|--------|
| `485dbf6` | `tests/test_video_corpus.py` | new, 29 tests, verbatim from the brief |
| `2a43613` | `src/agenticsocial/video/corpus.py` | new, verbatim from the brief |

Nothing under `docs/` was staged in either commit. Final
`git status --porcelain -- src tests` is empty.

## 5. Vacuity audit

For each test not already exercised by the seven brief mutants, I constructed the
mutant that test exists to kill, applied it, and checked the *intended* test was
among the failures. 14 targeted mutants:

| Mutant | Intended test | Result |
|--------|---------------|--------|
| A `read_manifest` returns a ghost entry instead of `{}` | `test_read_manifest_on_an_empty_corpus` | killed (+7 collateral) |
| B unknown-key message loses the key | `test_document_text_for_an_unknown_key_is_actionable` | killed |
| C corrupt manifest swallowed, returns `{}` | `test_a_corrupt_manifest_is_a_corpus_error` | killed |
| D document read with `errors="replace"` | `test_a_non_utf8_document_is_a_corpus_error` | killed |
| E `verify` drops the missing-file check | `test_verify_detects_a_missing_document` | killed (+1) |
| F `write_document` drops the safe-name guard | `test_an_unsafe_key_is_refused_before_any_write` | killed (all 6 params) |
| G explicit `key=` ignored | `test_an_explicit_key_is_used_verbatim` | killed |
| H non-ASCII dropped on write | `test_unicode_text_round_trips` | killed |
| I orphan scan counts `_manifest.json` itself | `test_verify_is_silent_on_a_sound_corpus` | killed (+4) |
| J manifest not re-read before write | `test_two_sources_coexist` | killed (+3) |
| K hostless URL gets a `"unknown"` fallback | `test_key_for_rejects_a_url_with_no_host` | killed |
| L manifest entry drops `title` | `test_write_document_creates_the_file_and_manifest_entry` | killed |
| M `verify` returns unsorted | `test_verify_reports_every_problem_sorted` | killed |
| N missing-`sources_dir` early return removed | `test_verify_on_an_empty_corpus` | **SURVIVED** |

**13 of 14 killed by their intended test.** Combined with the brief's seven, every
test in the file is non-vacuous in the sense that *some* mutant kills it.

Three findings.

**Finding 1 — `test_verify_detects_a_modified_document` is vacuous for the property
it names.** This is mutant 5, and it matters more than the others because it is
the exact claim the module exists to make. The test writes `"one"` (3 bytes) and
tampers it to `"tampered"` (8 bytes). A verifier that compared only the recorded
byte *length* passes that test. So does one that compared modification times.
Nothing in the suite forces `verify` to be a hash check.

Demonstrated, against the real implementation:

```
GAP A  byte length unchanged: True  manifest bytes=22
GAP A  verify() with sha256 : [('modified', 'blog-google')]
```

`"Anthropic raised $100M"` tampered to `"Anthropic raised $900M"` — same length,
different meaning, and the difference is the entire fact. The shipped code catches
it. The test suite would not notice if a future refactor stopped catching it. The
one-line fix is a same-length tamper in that test; I have **not** made it, because
your rules say report, do not adjust. Say the word and it is one commit.

**Finding 2 — `document_text`'s path guard is untested.** Mutant 7. Every
`_assert_safe_name` test targets `write_document`; nothing calls `document_text`
with a traversing key. Demonstrated:

```
GAP B  document_text('../../../secret') -> CorpusError: unsafe source key ...
GAP B  without the guard the same path resolves to: 'series-level file the corpus must not reach'
```

The guard works and is load-bearing — a key reaching `document_text` in Phase 5
will come from a claim's `source:` field, i.e. from agent-authored YAML, which is
precisely the untrusted-input path D-038 exists for. It is one `pytest.raises`
away from being pinned.

**Finding 3 — `verify`'s missing-`sources_dir` branch has zero coverage.** Mutant N:
deleting the early return breaks nothing, because `create_episode` always makes
`sources/`. The branch is not wrong — it is what stops `iterdir()` raising if a
directory is deleted out from under us — it is just unreached by any test. Lower
stakes than the other two.

## 6. Issues and concerns

### `verify` reads every document fully — is there a size at which that hurts?

Nothing caps what gets written. `write_document` takes whatever string it is
handed. `verify` then reads every document into memory one at a time
(`path.read_bytes()`), so peak memory is the largest single document, not the
corpus total.

Arithmetic: a fetched article after boilerplate stripping is ~5–50 KB. Twenty of
those is under 1 MB and hashing it is sub-millisecond. You would need a document
in the hundreds of MB before `read_bytes()` was a problem, and at that point the
problem is not `verify` — it is that Task 2 wrote hundreds of MB of "article"
into the corpus without asking.

So the size limit belongs at the **fetch boundary in Task 2**, not in `verify`.
That is where the runaway input actually arrives, where a cap can be reported to
the operator as "this page is not an article", and where refusing costs nothing.
Adding a cap here would only reject a corpus that is already on disk. My
recommendation: Task 2 caps the fetched body (a few MB is generous), and `verify`
stays as it is. If a very large document ever becomes legitimate, switch
`read_bytes()` to a chunked `hashlib` update — a three-line change, no interface
impact.

### The collision rule: `blog-google` and `blog-google-2`

**The key derivation is not wrong, but it is incomplete, and for this corpus that
gap is real.** Here is the distinction I would draw.

The key's job is to be a **stable, safe filename** — the handle a claim writes
down and Phase 5 dereferences. `-2` does that job correctly: it is deterministic
given write order, filesystem-safe, and collision-free. Encoding the article's
identity *into the key* would be worse, not better: it would mean slugifying a
title or hashing a URL, and then keys become long, ugly, and — with a title —
unstable, because the same URL re-fetched with a changed headline would produce a
different key and orphan every claim that cited the old one. Key stability is
worth more than key expressiveness.

Attribution is not the key's job. It is the **manifest's** job, and the manifest
already does it: `blog-google-2` carries `url`, `title`, `fetched_at`, `sha256`.
Nothing is lost — a human or a console can always resolve which article
`blog-google-2` is by opening `_manifest.json`. The key is a pointer; the manifest
is the record.

So the design is sound. What I would change is one thing, and it is a real
concern rather than a formality:

**`-2` is ordering-dependent, and nothing pins the ordering.** Fetch the same two
URLs in the other order and the same article gets a different key. That only
becomes dangerous if the corpus is ever rebuilt — a re-fetch, a recovery, an
"ingest these five URLs again" — after claims already cite `blog-google-2`. The
citations would silently re-point at the *other* article. Same key, different
source, no error anywhere. That is the one failure mode in this module that
produces a *wrong* fact-check rather than a loud one.

Two things make it safe, neither of which is a key-format change:

1. **Never re-derive a key for a URL already in the manifest.** Today, writing the
   same URL twice creates `blog-google-2` as a duplicate document rather than
   recognising it. Task 2 should look the URL up in the manifest first and either
   reuse its key or refuse. That kills the rebuild hazard at the source.
2. **Have the review console show `title`/`url` wherever it shows a key.** The
   operator should never have to reason about `-2` unaided.

Neither belongs in this task. Both belong in Task 2 and Phase 5 respectively, and
I would rather they be recorded now than discovered later. Recommend a decision
entry for (1).

### `_assert_safe_name` imported from `series.py`

It should not live there, and this is now the second phase to say so. It is a
path-safety primitive (D-038) with no series semantics whatsoever; `series.py`
merely happened to need it first. Three modules now import it — `episode.py`,
`corpus.py`, and `series.py` itself — and two of them reach across for a private
name, which means the leading underscore is currently lying about the API surface.

Where it should live: a small shared module in the package. Given the existing
layout, `agenticsocial/workspace.py` is the honest home — it already owns
`atomic_write`, i.e. it is already the module about *touching the filesystem
safely*, which is exactly what this function governs. `video/paths.py` would work
too but scopes it narrower than it deserves; the rule is not video-specific.

I have **not** moved it. It is a cross-cutting rename touching three modules and
their tests, it is not in this task's scope, and doing it inside an integrity task
would muddy the diff. It wants its own small task with its own commit — I would
suggest slotting it into Phase 2 before Task 2 adds a fourth importer.

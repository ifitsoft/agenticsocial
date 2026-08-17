# Task 2 Report: Ingestion — fill the corpus, honestly

**Branch:** `feat/video-phase-02-ingest`
**Commits:** `a648c38` (tests), `89cf55e` (implementation)

---

## 1. What I implemented

`src/agenticsocial/video/ingest.py` — three entry points (`ingest_research`,
`ingest_paste`, `ingest_source`), a frozen `IngestResult`, `IngestError`, and a
`brief.md` writer. `search`/`extract` are injected, defaulting to `research.py`.

I also had to change **`src/agenticsocial/video/corpus.py`** — one added
parameter. That was not optional; see the defect below.

### Defect in the brief (Step 3 code block cannot satisfy R3)

The brief's `_write` was:

```python
existing = _existing_key_for_url(episode, url)
if existing is not None:
    C.write_document(episode, text, url=url, title=title, key=existing)
    return existing
```

`corpus.write_document` suffixes **any** key already present in the manifest,
including one passed explicitly:

```python
manifest = read_manifest(episode)
if key in manifest:
    base, n = key, 2
    while f"{base}-{n}" in manifest:
        n += 1
    key = f"{base}-{n}"
```

So the lookup found `blog-google`, handed it to `write_document`, and the bytes
landed in `blog-google-2` anyway. R3 was unimplementable as written. I ran the
brief's module verbatim first to confirm rather than assume:

```
>       assert set(C.read_manifest(episode)) == {"blog-google"}
E       AssertionError: assert {'blog-google...log-google-2'} == {'blog-google'}
1 failed, 13 passed in 0.70s
```

**This is worse than the mutant it was supposed to prevent.** M3 (no lookup at
all) at least reports the key it actually used. The brief's version returned
`existing` — a key the bytes were never written under — so `IngestResult.keys`
said `blog-google` while the manifest said `blog-google-2`. A caller trusting
the result would cite a key whose document is not the one it just ingested.
That is precisely the silent-wrong-fact-check failure R3 exists to prevent, and
the brief's own code introduced it. `test_the_same_url_twice_reuses_its_key`
caught it only on its *second* assertion; the first (`first.keys ==
second.keys == ["blog-google"]`) passed on the lie.

Fix, in two parts:

- `corpus.write_document` gains `replace: bool = False`. Default behaviour is
  unchanged (two distinct documents must never share a key — that is what makes
  `_pasted-2` and `blog-google-2` work). `replace=True` is how a caller that
  matched the **exact** URL says "same document, refresh it in place".
- `ingest._write` passes `replace=True` on an exact-URL match and **returns
  `write_document`'s return value, never `existing`** — the key reported must be
  the key on disk.

I flagged this rather than silently following the code block, per the ground
rules. The test block and the prose both demand R3; only the Step 3 code block
contradicted them, so the code block is what I changed.

---

## 2. TDD evidence

### RED (piped, `/tmp/red.txt`)

```
tests/test_video_ingest.py:4: in <module>
    from agenticsocial.video import ingest as I
E   ImportError: cannot import name 'ingest' from 'agenticsocial.video'
ERROR tests/test_video_ingest.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.08s
```

### Passed on arrival: **0 of 14**

All 14 failed at collection, as the brief predicted. This number is weak
evidence either way — a module that does not exist cannot produce a vacuous
pass. The transcription question is answered by the mutation results in §3, not
by this count. See §5.3.

### GREEN (`/tmp/green1.txt`, `/tmp/full.txt`)

```
14 passed in 0.64s
```
```
444 passed in 1.86s
```

Full suite: **444 passed, 0 failed** (430 before this task).

---

## 3. Mutation results

All nine from the brief, plus eight of my own. Each: apply, run the **full**
suite, `git checkout` between. Raw output in `/tmp/mutants2.txt`, `/tmp/sweep.txt`.

| # | Mutant | Result | Killed by |
|---|--------|--------|-----------|
| M1 | failed `extract` propagates | KILLED (3 failed) | `test_a_failed_extraction_does_not_lose_the_others`, `test_a_failure_names_its_reason`, `test_the_brief_names_what_failed` |
| M2 | failures recorded, successes not written | KILLED (4 failed) | `test_a_failed_extraction_does_not_lose_the_others`, `test_the_same_url_twice_reuses_its_key`, `test_a_different_url_on_the_same_host_still_gets_a_new_key`, `test_documents_are_written_before_the_brief` |
| M3 | `write_document` without the manifest URL lookup | **KILLED** (1) | `test_the_same_url_twice_reuses_its_key` |
| M4 | URL lookup matches on host, not exact URL | **KILLED** (1) | `test_a_different_url_on_the_same_host_still_gets_a_new_key` |
| M5 | paste keyed by `key_for(url)` instead of `_pasted` | KILLED (2) | `test_paste_is_written_under_the_pasted_key`, `test_a_second_paste_does_not_overwrite_the_first` |
| M6 | `extract` returning `None` treated as success | KILLED (1) | `test_an_empty_extraction_is_a_failure_not_an_empty_document` |
| M7 | `brief.md` written before the documents | **see below** | — |
| M8 | `brief.md` omits the failure list | KILLED (1) | `test_the_brief_names_what_failed` |
| M9 | empty search produces a silent empty corpus | KILLED (1) | `test_an_empty_search_still_writes_a_brief_that_says_so` |

**M3 and M4 are both dead**, each to exactly the test written for it, and each
by a single test — no accidental coverage propping them up. S8 below is a third,
independent check on R3's negative half and also dies.

### M7 — one formulation survives

I wrote M7 twice.

- **M7-a (extra premature brief, real brief still written last): SURVIVED,
  444 passed.**
- **M7-b (brief written first from the search results, never rewritten):
  KILLED (2 failed)** — `test_documents_are_written_before_the_brief`,
  `test_the_brief_names_what_failed`.

The test asserts `order[-1] == "brief.md"` — that the *last* write is the brief.
It does not assert the brief is written *only* after its sources. M7-a writes a
sources-less `brief.md`, then the documents, then the correct brief. Ordering is
fine at the end, so the test is content.

Whether that matters: on the happy path, no. If the process dies mid-run — the
403-heavy afternoon this module was built for — M7-a leaves a `brief.md` on disk
citing a corpus that does not exist, which is exactly the hazard the test's own
docstring names ("a brief that exists while its sources do not is a citation to
nothing"). The test pins the ordering but not the invariant behind it. I did not
add a test for this, because the test file is the brief's contract and changing
it mid-task is how a transcription happens; flagging it is the honest move.
A one-line strengthening would close it: `assert order.count("brief.md") == 1`.

### My own sweep (8 additional mutants)

| # | Mutant | Result | Killed by |
|---|--------|--------|-----------|
| S1 | `_write` returns `existing` instead of `write_document`'s key — **the brief's own bug** | KILLED (1) | `test_the_same_url_twice_reuses_its_key` |
| S2 | whitespace-only extract treated as success (`if not text`) | **SURVIVED** | — |
| S3 | failure reason dropped (empty string) | KILLED (2) | `test_a_failure_names_its_reason`, `test_the_brief_names_what_failed` |
| S4 | brief omits the query | KILLED (1) | `test_the_brief_records_the_query` |
| S5 | empty source body written as a document anyway | KILLED (1) | `test_ingest_source_with_an_empty_body_is_a_failure` |
| S6 | manifest `url` for a paste set to the title, not empty | KILLED (1) | `test_paste_is_written_under_the_pasted_key` |
| S7 | results with no `href` not skipped | **SURVIVED** | — |
| S8 | `replace=True` on **every** write, not only exact-URL matches | KILLED (1) | `test_a_different_url_on_the_same_host_still_gets_a_new_key` |

**S2 survived.** `extract` returning `"   \n"` — a page that parsed to nothing
but whitespace — is the same hazard as M6 (a cited source containing nothing),
and no test distinguishes `if not text` from `if not text or not text.strip()`.
Real, low-frequency; trafilatura returning whitespace-only is rarer than
returning `None`, but it is the same class of bug. The implementation is
correct; the *test* is what's missing.

**S7 survived.** A search result with no `href` currently `continue`s; without
the guard it becomes a recorded failure with an empty URL. Cosmetic, and
arguably the mutant is the better behaviour (it at least records that a result
was unusable). Not worth a test.

Three survivors total: M7-a, S2, S7. Only M7-a touches an invariant the brief
states.

---

## 4. Files changed

| File | Commit |
|------|--------|
| `tests/test_video_ingest.py` (new, 14 tests) | `a648c38` |
| `src/agenticsocial/video/ingest.py` (new) | `89cf55e` |
| `src/agenticsocial/video/corpus.py` (`replace=` param) | `89cf55e` |

Two commits, not squashed. Nothing under `docs/` staged. `git status --porcelain
-- src tests` is clean.

No network anywhere: `search` and `extract` are injected in every test;
`research.py` imports `ddgs`/`trafilatura` lazily inside its functions, so even
`from .. import research` performs no I/O. No dependencies added.

---

## 5. Issues and concerns

### 5.1 `ingest_source` keys as `src-<id>`

**Not right, and it will break.** `source.id` is `f"{created}-{slugify(title)}"`
— unbounded, driven by the source title. A source titled with a long sentence
yields a key like
`src-2026-08-17-we-should-probably-kill-the-staging-environment-before-q3`, and
that key becomes a filename (`+ ".txt"`), a manifest key, and a citation token
an agent has to type correctly inside a claim. `assert_safe_name` only rejects
slashes and NULs, so nothing catches length. `episode.py` caps episode ids with
`MAX_ID_LEN` for exactly this reason; corpus keys have no equivalent.

It is also inconsistent with every other key in the corpus: `blog-google` and
`_pasted` are short and host- or role-derived, and a claim citing
`src-2026-08-17-we-should-…` is unreadable in a fact-check table.

Two coherent options, neither of which I took unasked: derive from the source's
`origin_url` when it has one and fall back to `src-<created-date>`; or truncate
to a documented limit. I left the brief's behaviour in place because it is what
the code block specifies and no test constrains it — but it is a defect waiting
for a real title, and I would fix it before the CLI exposes `--from-source`.

### 5.2 Every entry point overwrites `brief.md`

**A data-loss bug, and the asymmetry is the tell.** The corpus *accumulates* —
that is R3's whole point, keys are stable across rebuilds — while `brief.md` is
truncated by whichever ingest ran last. Ingest a research query, then paste a
digest: the corpus holds both, and `brief.md` says `_Query: (pasted)_` with one
source listed. The record of where three of your four sources came from, and of
the one that 403'd, is gone. R2's negative half ("never silent — it appears in
the returned result *and* in `brief.md`") is defeated by the next ingest,
because `IngestResult` is in-memory and `brief.md` was the durable half.

The failure record is the part I would not lose. Whether the fix is appending a
dated section per ingest, or regenerating the whole brief from the manifest each
time (the manifest already holds url, title, fetched_at for every document — it
is the real source of truth, and a brief derived from it would be correct by
construction), the current behaviour is not defensible. No test covers a second
ingest of a *different* kind, which is why it is green.

### 5.3 Did this brief's tests read as derived-from-mutants, or as transcriptions?

**Partly. The R3 tests genuinely tested; several others still transcribe. And
the passed-on-arrival count did not measure it.**

The honest evidence, in order.

**It worked where it mattered most.** `test_the_same_url_twice_reuses_its_key`
found a real defect in the implementation the same brief supplied. That is the
strongest possible proof of non-transcription: a transcribed test cannot fail
against the thing it was transcribed from. The mutant-first framing is what did
it — M3 was specified as a *behaviour* ("without the manifest URL lookup"), so
the assertion was written against the manifest's contents
(`set(C.read_manifest(episode)) == {"blog-google"}`) rather than against the
function's return value. The return value lied; the manifest could not. Had the
test only checked `res.keys`, it would have passed and shipped the bug. The same
holds for M4/`test_a_different_url_on_the_same_host_still_gets_a_new_key`, which
also checks the corpus rather than the result.

**Several tests are still transcriptions.**
`test_an_empty_search_still_writes_a_brief_that_says_so` asserts `"no sources"`
appears in the brief — a string that exists in the brief only because the Step 3
code block writes `_No sources were ingested._`. The rule (R5 negative: "says
so") does not pin any wording; the test pins that wording. Same for
`test_the_brief_names_what_failed` asserting `"403"` — that survives only
because the mutant *format* keeps the exception message. And
`test_defaults_are_the_research_module` asserts `default is None`, which is a
transcription of the signature, not of behaviour; its own docstring admits it is
"not behavioural". A brief that specified R6 as "no test may reach the network"
would be checked by a socket guard in `conftest.py`, not by reading a signature.

**The passed-on-arrival count measured nothing.** It was 0/14, because the
module did not exist and everything died at import. That is the *normal* outcome
for a new module, and it will be 0 whether the tests are excellent or pure
transcription. The count only detects vacuity when tests run against
*pre-existing* code — the two vacuous tests earlier in this phase were in that
situation. For a new-module task, the metric that actually discriminates is the
one in §3: **17 mutants applied, 14 killed**, and the three survivors each name
a specific gap. Mutation score is the transcription rate; passed-on-arrival is
its proxy only sometimes, and not this time.

**What I would change in the method.** The mutant table is the improvement worth
keeping — write it, then write assertions that can only be satisfied by
inspecting *state* (manifest, disk) rather than the function's own report of
itself, because the return value is under the implementation's control and the
disk is not. Two additions: (a) drop passed-on-arrival for new-module tasks in
favour of a required post-implementation mutation score, since the former is
uninformative there; (b) do not ship a Step 3 code block, or ship it only after
the tests are committed. I ran the brief's implementation verbatim and it failed
its own tests — useful here, but the pull to reconcile the tests toward the
supplied code rather than the code toward the tests is real, and I felt it. The
tests being committed first (`a648c38`, before I had written a line of
`ingest.py`) is the only thing that made resisting it structural rather than a
matter of my discretion.

**Verdict: yes, with a caveat.** Mutants-first produced two tests that caught a
live bug in the brief's own implementation, which no prior brief in this project
has done. The negative halves are where the value concentrated — R3's negative
(M4) and R4's negative (M5, S6) killed cleanly. What did not improve is
brief/`brief.md` wording assertions, which remain string-matching against a
supplied implementation. Keep the method; drop the code block and the
passed-on-arrival metric.

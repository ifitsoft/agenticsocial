# Task 1b Report: Close the corpus's two real gaps, and rehome the path guard

**Branch:** `feat/video-phase-02-ingest` · **Base:** `2a43613`

## 1. What I changed

**Step 1 — tests only.** Replaced `test_verify_detects_a_modified_document` with
`test_verify_detects_a_same_length_modification` (22 bytes → 22 bytes,
`$100M` → `$900M`) and appended the three tests from the brief verbatim. No other
existing test touched.

**Step 2 — nothing.** Confirmed, as the brief predicted. Full suite green on
arrival: `421 passed`. `verify` already compares `sha256`, `document_text`
already calls the guard, the missing-dir branch already exists. **There is no
second commit** — I did not manufacture an empty one. Two commits, not three.

**Step 3 — the rehome.** `_assert_safe_name` + `_UNSAFE_CHARS` moved out of
`video/series.py` into `workspace.py` as public `assert_safe_name` /
`_UNSAFE_NAME_CHARS`, next to `atomic_write`. All three importers
(`series.py`, `episode.py`, `corpus.py`) now import from `..workspace`; all
eight call sites updated.

```
$ grep -rn "_assert_safe_name\|_UNSAFE_CHARS" src/ tests/
grep-exit=1   (no matches)
```

## 2. Which new tests passed immediately vs failed

**All four passed immediately. None failed.** There was no red-to-green cycle
and I am not going to imply one.

```
$ uv run pytest tests/test_video_corpus.py
collected 38 items
tests/test_video_corpus.py ......................................  [100%]
============================== 38 passed in 0.33s ==============================
```

That is exactly the shape the brief called: these tests pin behaviour the code
already had and nothing checked. Step 4 is the only evidence they bite.

## 3. Mutation results — all five

| # | Mutant | Result |
|---|--------|--------|
| 1 | `verify` compares `bytes` (st_size) instead of `sha256` | **killed** |
| 2 | `document_text` drops `assert_safe_name` | **killed** |
| 3 | `verify` drops the missing-`sources_dir` branch | **SURVIVES** |
| 4 | `assert_safe_name` drops the `{".", ".."}` check | **killed** |
| 5 | `assert_safe_name` drops the `"\\"` check | **killed** |

```
MUTANT 1: rc=1 | 1 failed, 420 passed
    FAILED test_verify_detects_a_same_length_modification - assert [] == [('modified', 'blog-google')]
MUTANT 2: rc=1 | 1 failed, 420 passed
    FAILED test_document_text_cannot_reach_outside_the_corpus - DID NOT RAISE CorpusError
MUTANT 3: rc=0 | 421 passed          <-- SURVIVED
MUTANT 4: rc=1 | 6 failed, 415 passed
    FAILED test_video_corpus.py::test_an_unsafe_key_is_refused_before_any_write[.]
    FAILED test_video_corpus.py::test_an_unsafe_key_is_refused_before_any_write[..]
    FAILED test_video_episode.py::test_load_episode_refuses_unsafe_ids[..]
    FAILED test_video_episode.py::test_load_episode_refuses_unsafe_ids[.]
    FAILED test_video_series.py::test_load_series_refuses_unsafe_names[..]
    FAILED test_video_series.py::test_load_series_refuses_unsafe_names[.]
MUTANT 5: rc=1 | 3 failed, 418 passed
    FAILED test_video_corpus.py::test_an_unsafe_key_is_refused_before_any_write[a\b]
    FAILED test_video_episode.py::test_load_episode_refuses_unsafe_ids[a\b]
    FAILED test_video_series.py::test_load_series_refuses_unsafe_names[a\b]
```

### DEFECT IN THE BRIEF (#17): Step 1's code block cannot cover gap 3

`test_verify_reports_everything_missing_when_the_corpus_dir_is_gone` `rmtree`s
`sources_dir` and then **recreates it and restores the manifest**. So
`sources_dir.is_dir()` is `True` when `verify` runs, the guarded branch is never
entered, and the two `("missing", ...)` entries come from the normal per-key
loop. Deleting the branch changes nothing. I followed the code block as
instructed; flagging it here.

The deeper finding is that the branch cannot be covered as written, because the
manifest **lives inside `sources_dir`**:

```
$ uv run python /tmp/probe.py
sources_dir exists after create_episode: True
dir truly gone -> manifest: {} verify: []
```

If the directory is gone, `read_manifest` returns `{}`, so
`[("missing", k) for k in sorted(manifest)]` is **always `[]`**. That list
comprehension is unreachable-with-content — dead code dressed as a feature.
The branch's only real job is stopping `iterdir()` from raising. With the branch
removed and the directory genuinely gone:

```
FileNotFoundError: [Errno 2] No such file or directory: .../episodes/2026-08-14/sources
```

**The test that would actually kill mutant 3** is the two-line version — no
recreate, no manifest restore:

```python
def test_verify_survives_a_deleted_corpus_dir(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    shutil.rmtree(episode.sources_dir)
    assert C.verify(episode) == []      # not a crash
```

I did **not** add it: only `test_verify_detects_a_modified_document` was
authorised to change. Your call whether to take it, or to simplify the branch to
`return []` now that its list comprehension is provably dead.

## 4. Files changed and commit SHAs

| Commit | SHA | Files |
|--------|-----|-------|
| 1 — tests | `feddd8e` | `tests/test_video_corpus.py` |
| 2 — source gaps | *(none — nothing to fix)* | — |
| 3 — rehome | `39e2993` | `src/agenticsocial/workspace.py`, `video/series.py`, `video/episode.py`, `video/corpus.py` |

Final suite: **421 passed**. Pre-task, at `2a43613`, it was **412 passed** —
measured, by restoring the old test file and re-running. The delta is +9: the
replaced tamper test is 1-for-1, plus 7 parametrised traversal cases, plus the
two named tests. Observed, not predicted:

```
$ uv run pytest
============================= 421 passed in 1.39s ==============================
```

`git status --porcelain -- src tests` is empty. Nothing under `docs/` staged.

## 5. Issues and concerns

### Q1 — Anything left in `series.py` reached into privately?

**No.** After the rehome, every cross-module import of `series.py` is public:

```
src/agenticsocial/video/cli.py:13:from .series import load_series, scaffold_series, series_slugs
src/agenticsocial/video/plan.py:21:from .episode import read_script
tests/...: scaffold_series, load_series, list_series
```

The remaining private names in `series.py` — `_toml_str`, `_validate_slug`,
`_table`, `_TOML_SHORT_ESCAPES` — are used only inside that module and all carry
genuine series semantics. `series.py` is now clean on this axis.

### Q2 — Is the manifest sufficient for a URL-keyed collision fix in Task 2?

**Yes, structurally — the manifest already stores `url` per entry**, so Task 2
can build `{entry["url"]: key for key, entry in manifest.items()}` and reuse or
refuse without any change to what is persisted. No migration needed.

Three things in `corpus.py` will nonetheless bite that implementation:

1. **`url=""` is legal today.** `test_an_explicit_key_is_used_verbatim` writes
   with `url=""`, and `key_for` is only called when `key is None`, so the
   pasted-text path stores an empty URL. A reverse index would collapse every
   pasted document onto one entry. Task 2 needs an explicit rule: empty URL
   never participates in reuse.
2. **No validation that manifest entries are dicts.** `read_manifest` checks the
   top level is an object but not the values, so `entry["url"]` can raise
   `TypeError`/`KeyError` past the `CorpusError` contract. See mutant B below.
3. The `-2` suffix format is pinned by **no test at all** (mutant C survives).
   Whatever Task 2 does to it, nothing currently guards the old behaviour, so
   pin the format in the same commit that changes it.

Confirming your read: the current `-2` rule is fetch-order-dependent and silently
re-points on a rebuild. It is the module's only failure mode that produces a
*wrong* fact-check rather than a loud one, and it is not detectable by `verify`
— every hash still matches; the hashes are just bound to the wrong article.

### Q3 — What else here cannot be distinguished from a weaker implementation?

I wrote 14 more targeted mutants against `corpus.py` and ran the full suite on
each. **12 of 14 survive.** Ranked by whether the weaker version is actually
worse, not by whether it differs:

**Real gaps — a weaker implementation is observably wrong and nothing sees it**

| Mutant | What breaks unseen |
|---|---|
| **A** `key_for`: `startswith("www-")` → `"www" in key` | `blog.wwwfoo.com` → key `-wwwfoo-com`. No test has an *internal* `www`, so the stripping **rule** is unpinned — only two happy cases are. |
| **B** `read_manifest`: drop `isinstance(data, dict)` | A manifest that is a JSON `[]` or `"x"` leaks `TypeError`/`AttributeError` past the `CorpusError` contract. Directly blocks Q2's reverse index. |
| **C** `write_document`: collision counter starts at `1` | Keys become `blog-google-1`. `test_same_host_twice_gets_a_distinct_key` only asserts `a != b`, so the **key format is entirely unspecified**. |
| **I** `write_document`: `key is not None` → `key or key_for(url)` | An explicit `key=""` would silently become the host key instead of being refused. The existing test can't see it because it passes `url=""` too, so both paths raise. Same bug class as this whole task. |
| **K** `write_document`: drop `sources_dir.mkdir` | Every test fixture pre-creates the directory, so first-write-into-a-bare-episode is untested. |
| **M** `write_document`: `fetched_at` default → `""` | The test asserts only `"fetched_at" in entry`. Provenance is the module's reason to exist, and its timestamp is pinned to *presence*, not *plausibility*. |
| **H** `verify`: drop the `not entry.is_file()` orphan skip | A subdirectory under `sources/` gets reported as an orphan. Minor, but `verify` is the gate. |

**Cosmetic — survive, but the weaker version is not worse**

- **D/E/F** manifest `sort_keys` / `indent` / `ensure_ascii`: diff-noise only; all
  round-trip identically.
- **L** `verify`: `sorted()` around `iterdir` — redundant, the final
  `sorted(problems)` already covers it.
- **J** the post-collision `assert_safe_name` recheck is unreachable: `base` was
  already checked and `-{n}` cannot introduce an unsafe character. Harmless
  belt-and-braces; worth a comment saying so, or deleting.

**Killed (2 of 14)** — `G` (non-atomic document write, caught by
`test_the_document_is_written_before_the_manifest`) and `N` (sha-AND-size,
caught by the new same-length test).

The pattern across A, C, I and M is one thing: **the tests pin outcomes, not
rules.** `key == "blog-google"` is pinned; *"strip a leading `www-`"* is not.
`a != b` is pinned; *"the suffix is `-2`"* is not. `"fetched_at" in entry` is
pinned; *"it is a real local timestamp"* is not. That is the same defect shape as
the tamper test that started this task — a test that names a property and then
asserts something weaker than the property.

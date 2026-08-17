# Task 1c Brief: Pin the rules, not the outcomes

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `39e2993`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

**This closes `corpus.py`. Whatever else surfaces goes to Phase 3.**

## Why

Task 1b wrote 14 mutants against `corpus.py`. **Twelve survived, seven of them
real** — and named the pattern behind every one:

> The tests pin **outcomes**, not **rules**. `key == "blog-google"` is pinned;
> "strip a leading `www-`" is not. `a != b` is pinned; "the suffix is `-2`" is
> not.

That is the same shape as the tamper test that started Task 1b, and as four of
the vacuous tests found across earlier phases. This task fixes it in the one
module where it matters most: **the corpus is what every fact-check is checked
against.** A rule nobody pinned is a rule the next editor can change silently.

Two of my own tests are also vacuous and are corrected here:

- **`test_document_text_refuses_a_traversing_key`** — every key it passes raises
  `CorpusError` anyway, for the wrong reason (no such file). Only the concrete
  planted-file test actually kills the mutant.
- **`test_verify_reports_everything_missing_when_the_corpus_dir_is_gone`** —
  it recreates `sources_dir` and restores the manifest, so the branch it targets
  is never entered. Brief defect #17.

## The dead branch

Task 1b proved `verify`'s missing-`sources_dir` branch **cannot** do what it
claims: the manifest lives *inside* `sources_dir`, so if the directory is gone
`read_manifest` returns `{}` and `[("missing", k) for k in {}]` is provably `[]`.
Its only real job is stopping `iterdir()` raising `FileNotFoundError`. Make the
code say that.

## Ground rules

- **Two commits.** Tests first, then source. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 17 defects across four phases now.
- **Authorised test changes:** the two vacuous tests named above, replaced.
- Do not add dependencies. Never stage anything under `docs/`.

---

- [ ] **Step 1: Replace the two vacuous tests, add the rule pins**

Replace `test_document_text_refuses_a_traversing_key` with:

```python
@pytest.mark.parametrize(
    "bad", ["../../../series", "../secret", "a/b", "..", ".", "", "a\\b"]
)
def test_document_text_refuses_a_traversing_key(episode, bad):
    """Each key must be refused as UNSAFE, not merely as absent. The previous
    version passed with the guard removed: every key raised CorpusError anyway
    because no such file existed."""
    with pytest.raises(C.CorpusError, match="unsafe"):
        C.document_text(episode, bad)
```

Replace `test_verify_reports_everything_missing_when_the_corpus_dir_is_gone`
with:

```python
def test_verify_is_silent_when_the_corpus_dir_does_not_exist(episode):
    """The manifest lives inside sources_dir, so if the directory is gone there
    is nothing recorded either. The guard exists to stop iterdir() raising, not
    to report losses — the previous version of this test recreated the directory
    and never entered the branch at all."""
    import shutil

    C.write_document(episode, "one", url="https://blog.google/x")
    shutil.rmtree(episode.sources_dir)
    assert C.verify(episode) == []
```

Append the rule pins:

```python
# --- the RULES, not just the outcomes -----------------------------------------
# Task 1b: 12 of 14 mutants survived because tests pinned example outputs while
# leaving the rule that produced them free to change.


def test_only_a_leading_www_is_stripped(episode):
    """`www` inside a host is part of the name. Pinning two happy examples left
    `"www" in key` passing."""
    assert C.key_for("https://www.reuters.com/x") == "reuters-com"
    assert C.key_for("https://blog.wwwfoo.com/x") == "blog-wwwfoo-com"
    assert C.key_for("https://wwwfoo.com/x") == "wwwfoo-com"


def test_the_collision_suffix_format_is_stable(episode):
    """Claims cite these keys. `a != b` left the format entirely unspecified."""
    C.write_document(episode, "one", url="https://blog.google/x")
    assert C.write_document(episode, "two", url="https://blog.google/y") == "blog-google-2"
    assert C.write_document(episode, "three", url="https://blog.google/z") == "blog-google-3"


def test_an_explicit_empty_key_is_refused_not_replaced(episode):
    """`key=""` must not silently fall back to the host key. Invisible before
    because the only test passing an explicit key also passed url=""."""
    with pytest.raises(C.CorpusError):
        C.write_document(episode, "x", url="https://blog.google/x", key="")


def test_write_creates_the_sources_dir_when_absent(episode):
    """Every fixture pre-created it, so dropping the mkdir broke nothing."""
    import shutil

    shutil.rmtree(episode.sources_dir)
    C.write_document(episode, "one", url="https://blog.google/x")
    assert (episode.sources_dir / "blog-google.txt").is_file()


def test_fetched_at_is_a_plausible_timestamp(episode):
    """Presence was asserted; plausibility was not — in the module whose reason
    to exist is provenance."""
    from datetime import datetime

    C.write_document(episode, "one", url="https://blog.google/x")
    stamp = C.read_manifest(episode)["blog-google"]["fetched_at"]
    assert datetime.fromisoformat(stamp).year >= 2020


def test_an_explicit_fetched_at_is_recorded_verbatim(episode):
    C.write_document(
        episode, "one", url="https://blog.google/x", fetched_at="2026-08-14T09:00:00+01:00"
    )
    assert C.read_manifest(episode)["blog-google"]["fetched_at"] == (
        "2026-08-14T09:00:00+01:00"
    )


def test_a_subdirectory_is_not_an_orphan(episode):
    """Dropping the is_file() skip made any directory read as a stray source."""
    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / "cache").mkdir()
    assert C.verify(episode) == []


def test_a_manifest_whose_entries_are_not_objects_is_a_corpus_error(episode):
    """`entry["url"]` would otherwise leak TypeError past the CorpusError
    contract that every caller catches."""
    import json

    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / C.MANIFEST_NAME).write_text(
        json.dumps({"blog-google": "not an object"}), encoding="utf-8"
    )
    with pytest.raises(C.CorpusError):
        C.read_manifest(episode)


def test_a_manifest_that_is_a_json_array_is_a_corpus_error(episode):
    C.write_document(episode, "one", url="https://blog.google/x")
    (episode.sources_dir / C.MANIFEST_NAME).write_text("[]", encoding="utf-8")
    with pytest.raises(C.CorpusError):
        C.read_manifest(episode)
```

```bash
uv run pytest tests/test_video_corpus.py 2>&1 | tail -15
git add tests/test_video_corpus.py
git commit -m "test: pin the corpus rules, not just example outcomes

12 of 14 mutants survived because tests asserted example outputs while
leaving the rules that produced them free to change: the www- strip, the
collision suffix format, the explicit-key contract, and fetched_at's
plausibility were all unpinned."
```

Expect failures on: the empty-key test, the manifest-entry-type test, and
possibly the traversal `match="unsafe"` tests. Report exactly which.

- [ ] **Step 2: Implement**

**2a.** `read_manifest` validates entry shape, not just the top level:

```python
    if not isinstance(data, dict):
        raise CorpusError(f"{path}: {MANIFEST_NAME} must be an object")
    for key, entry in data.items():
        if not isinstance(entry, dict):
            raise CorpusError(
                f"{path}: manifest entry {key!r} must be an object, got "
                f"{type(entry).__name__}"
            )
    return data
```

**2b.** `write_document`'s explicit-key path — an empty key is a caller error,
not a request for the default. The existing `key if key is not None else
key_for(url)` is already correct; `assert_safe_name` then rejects `""`. **Verify
that is true rather than assuming it** — if `key=""` currently reaches
`key_for`, say so.

**2c.** `verify`'s dead branch says what it does:

```python
    manifest = read_manifest(episode)
    problems: list[tuple[str, str]] = []
    if not episode.sources_dir.is_dir():
        # The manifest lives in this directory, so if it is gone `manifest` is
        # already empty. This guard exists only to stop iterdir() raising.
        return problems
```

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/corpus.py
git commit -m "fix: validate manifest entry shape, and say what the empty-dir guard does

entry[\"url\"] could leak TypeError past the CorpusError contract every
caller catches. The missing-sources_dir branch cannot report losses --
the manifest lives in that directory -- so it now says so."
```

- [ ] **Step 3: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `key_for` → `"www" in key` instead of `startswith("www-")`
2. collision counter starts at `1`
3. `key if key is not None else …` → `key or key_for(url)`
4. drop `sources_dir.mkdir`
5. `fetched_at` default → `""`
6. `verify` → drop the `not entry.is_file()` orphan skip
7. `read_manifest` → drop the entry-shape loop
8. `read_manifest` → drop the top-level `isinstance` check
9. `document_text` → drop `assert_safe_name`

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-1c-report.md`:

1. **What I changed.**
2. **Which new tests failed at RED** vs passed on arrival — say plainly.
3. **Mutation results** for all nine.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Re-run your 14-mutant sweep. How many survive now, and are any of the
     remainder real rather than cosmetic?
   - You said the pattern is "tests pin outcomes, not rules". Having now fixed
     it here — is that a property of my briefs specifically, or of
     example-based testing generally? If the latter, what would you change about
     how these briefs specify tests?

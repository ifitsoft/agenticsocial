# Task 1b Brief: Close the corpus's two real gaps, and rehome the path guard

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `2a43613`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Two of Task 1's mutants survived. Both are real, and I verified both by hand.

**1. My tamper test is vacuous for the property the module exists to provide.**
`test_verify_detects_a_modified_document` tampers `"one"` (3 bytes) into
`"tampered"` (8 bytes) — so a verifier comparing only recorded *length* passes
it. Comparing `bytes` instead of `sha256` survives the whole suite.

```
original : 'Anthropic raised $100M'  (22 bytes)
tampered : 'Anthropic raised $900M'  (22 bytes)
length-only check: SAME - undetected
sha256:            differs - caught
```

The realistic tamper — changing a figure — is exactly the one my test could not
see. Sixteenth defect in my briefs, and the most pointed: the test for tamper
detection was blind to tampering.

**2. `document_text`'s path guard is untested, and load-bearing.** With it
removed:

```
key='../../../series'        -> READ: workspace/series/the-brief/series.txt
key='../../../../../voice'   -> READ: workspace/voice.txt
```

Reachable, not theoretical: **Phase 5's source key comes from agent-authored
YAML** — a `src:` field in a script is the input to this function.

**3. `verify`'s missing-`sources_dir` branch has zero coverage** — deleting it
breaks nothing.

**4. `_assert_safe_name` is in the wrong module.** It is a D-038 path primitive
with no series semantics, now imported by three modules, two of them reaching for
a private name across a package boundary. Task 5 of Phase 1 flagged the same
smell and I deferred it. Task 2 would add a fourth importer, so it moves now.

## Ground rules

- **Three commits:** tests, then the two source gaps, then the rehome. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- **Authorised test change:** `test_verify_detects_a_modified_document` only.
- Do not add dependencies. Never stage anything under `docs/`.

---

- [ ] **Step 1: Tests**

Replace `test_verify_detects_a_modified_document` in
`tests/test_video_corpus.py` entirely:

```python
def test_verify_detects_a_same_length_modification(episode):
    """The realistic tamper is changing a figure, not changing a length. The
    previous version of this test replaced 3 bytes with 8, so a verifier
    comparing only `bytes` passed it — blind to exactly what it named."""
    C.write_document(episode, "Anthropic raised $100M", url="https://blog.google/x")
    (episode.sources_dir / "blog-google.txt").write_text(
        "Anthropic raised $900M", encoding="utf-8"
    )
    assert C.verify(episode) == [("modified", "blog-google")]
```

Append:

```python
@pytest.mark.parametrize(
    "bad", ["../../../series", "../secret", "a/b", "..", ".", "", "a\\b"]
)
def test_document_text_refuses_a_traversing_key(episode, bad):
    """Phase 5's source key comes from agent-authored YAML. Without this guard
    the key `../../../../../voice` reads workspace/voice.txt."""
    with pytest.raises(C.CorpusError):
        C.document_text(episode, bad)


def test_document_text_cannot_reach_outside_the_corpus(episode):
    """Concrete: plant a file where a traversal would land and prove it stays
    unreachable."""
    series_dir = episode.dir.parent.parent
    (series_dir / "series.txt").write_text("SECRET", encoding="utf-8")
    with pytest.raises(C.CorpusError):
        C.document_text(episode, "../../../series")


def test_verify_reports_everything_missing_when_the_corpus_dir_is_gone(episode):
    import shutil

    C.write_document(episode, "one", url="https://blog.google/x")
    C.write_document(episode, "two", url="https://venturebeat.com/y")
    manifest = (episode.sources_dir / C.MANIFEST_NAME).read_text(encoding="utf-8")
    shutil.rmtree(episode.sources_dir)
    episode.sources_dir.mkdir()
    (episode.sources_dir / C.MANIFEST_NAME).write_text(manifest, encoding="utf-8")
    assert C.verify(episode) == [
        ("missing", "blog-google"),
        ("missing", "venturebeat-com"),
    ]
```

```bash
uv run pytest tests/test_video_corpus.py 2>&1 | tail -12
git add tests/test_video_corpus.py
git commit -m "test: pin same-length tampering and the corpus path guard

The tamper test replaced 3 bytes with 8, so a length-only verifier
passed it -- blind to changing a figure, the realistic tamper. The
document_text path guard had no test at all; without it the key
../../../../../voice reads workspace/voice.txt."
```

Expect `test_verify_detects_a_same_length_modification` and the traversal tests
to **pass immediately** — they pin behaviour the code already has but nothing
checked. That is the point; the mutants in Step 4 are what prove they bite.

- [ ] **Step 2: Nothing to fix in source for gaps 1–3**

Task 1's implementation is already correct on all three: `verify` compares
`sha256`, `document_text` calls `_assert_safe_name`, and the missing-dir branch
exists. **The gap was in the tests, not the code.** Confirm this by running the
suite — if anything fails, that is a finding and you should stop and report it.

- [ ] **Step 3: Rehome the path guard (own commit)**

Move `_assert_safe_name` from `src/agenticsocial/video/series.py` to
`src/agenticsocial/workspace.py`, renamed public, since three modules depend on
it and `workspace.py` already owns `atomic_write` — it is the module about
touching the filesystem safely.

In `workspace.py`, add near `atomic_write`:

```python
_UNSAFE_NAME_CHARS = ("/", "\\", "\x00")


def assert_safe_name(name: str, kind: str, error: type[Exception]) -> None:
    """Reject anything that could address a path outside its parent directory.

    Deliberately separate from any naming rule. Naming governs what agsoc will
    CREATE; this governs what it will TOUCH. A directory a human named `My-Show`
    stays loadable; `../../outside` does not, whoever made it. See D-038.

    `error` is the caller's exception type, so each module raises its own.
    """
    if not name or name in {".", ".."} or any(c in name for c in _UNSAFE_NAME_CHARS):
        raise error(f"unsafe {kind} {name!r} — must be a single directory name, not a path")
```

Then in `series.py`, delete the local definition and `_UNSAFE_CHARS`, and import
it: `from ..workspace import Workspace, assert_safe_name, atomic_write`. Update
its call sites to `assert_safe_name(...)`.

In `episode.py` and `corpus.py`, replace `from .series import _assert_safe_name`
with `from ..workspace import assert_safe_name` and update call sites.

`grep -rn "_assert_safe_name" src/ tests/` must come back empty afterwards.

```bash
uv run pytest 2>&1 | tail -5
git add src/
git commit -m "refactor: move the path guard to workspace, where filesystem safety lives

It is a D-038 path primitive with no series semantics, and three modules
imported it -- two reaching for a private name across a package
boundary. Task 2 would have been the fourth."
```

- [ ] **Step 4: Mutation check**

Apply, run the full suite, `git checkout` between. All must now fail:

1. `verify` → compare `bytes` instead of `sha256` *(survived before this task)*
2. `document_text` → drop `assert_safe_name` *(survived before this task)*
3. `verify` → drop the missing-`sources_dir` branch
4. `assert_safe_name` → drop the `{".", ".."}` check
5. `assert_safe_name` → drop the `"\\"` check

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-1b-report.md`:

1. **What I changed.**
2. **Which new tests passed immediately vs failed** — most should pass; say so
   plainly rather than implying a red-to-green cycle that did not happen.
3. **Mutation results** for all five.
4. **Files changed**, all three commit SHAs.
5. **Issues or concerns**, including:
   - After the rehome, is there anything left in `series.py` that other modules
     reach into privately?
   - The `-2` collision key is fetch-order-dependent, so a corpus rebuild can
     silently re-point `blog-google-2` at the *other* article — the one failure
     mode here that produces a **wrong** fact-check rather than a loud one. The
     fix belongs in Task 2 (look the URL up in the manifest, reuse its key or
     refuse, never re-derive). Does anything in `corpus.py` need to change to
     make that possible, or is the manifest already sufficient?
   - Anything else in this module whose test cannot distinguish it from a
     weaker implementation.

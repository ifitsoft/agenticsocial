# Task 3c Report: Make byte preservation actually true

**Branch:** `feat/video-phase-01-scaffolding` · **Commits:** `ff70230` (tests), `c47236b` (fix)

---

## 1. What I changed

Implemented the brief exactly as its code blocks were written.

- `src/agenticsocial/video/episode.py`
  - `import re`; deleted `_SEP`; added `_DOC_START_RE` / `_SEP_RE`.
  - `_split` now returns `(meta_text, beats_text, newline)` and detects `\r\n`, `\r`, `\n`.
  - `_read_meta` reads via `open(..., newline="")` — line endings arrive untranslated —
    and returns the three-tuple.
  - `_compose` takes `nl`, re-emits the metadata block and both `---` fences with the
    file's own line ending, and still passes the beats through untouched.
  - `create_episode`: `d.exists() or d.is_symlink()`, `mkdir` loop moved inside the
    cleanup `try`, metadata factored into `_new_meta`.
  - `episode_ids`: `iterdir()` wrapped so `OSError` surfaces as `EpisodeError`.
  - `resolve_episode`: empty query rejected as its first statement.
  - `load_episode` / `set_status` updated for the three-tuple.
- `src/agenticsocial/workspace.py` — `atomic_write` opens with `newline=""`.
- `tests/test_video_episode.py` — appended the 9 tests (11 with parametrisation)
  from the brief verbatim. No existing test touched. No dependencies added.

---

## 2. TDD evidence

### RED — after commit 1, before any implementation

```
FAILED tests/test_video_episode.py::test_beats_bytes_survive_a_status_change[\r\n]
FAILED tests/test_video_episode.py::test_beats_bytes_survive_a_status_change[\r]
FAILED tests/test_video_episode.py::test_beats_bytes_survive_repeated_status_changes[\r\n]
FAILED tests/test_video_episode.py::test_unreadable_episodes_dir_raises_episode_error
FAILED tests/test_video_episode.py::test_create_over_a_dangling_symlink_raises_episode_error
FAILED tests/test_video_episode.py::test_empty_query_does_not_resolve_an_episode
========================= 6 failed, 44 passed in 0.38s =========================
```

The three LF-only byte tests (`[\n]`, trailing-whitespace, no-trailing-newline)
passed at RED. That is expected and not a weak test: on an LF file the old code
already preserved bytes. Those three exist to kill mutants 3, 4 and 5, and they do
(section 3).

### GREEN — after commit 2

```
tests/test_video_episode.py::test_beats_bytes_survive_a_status_change[\n] PASSED [ 82%]
tests/test_video_episode.py::test_beats_bytes_survive_a_status_change[\r\n] PASSED [ 84%]
tests/test_video_episode.py::test_beats_bytes_survive_a_status_change[\r] PASSED [ 86%]
tests/test_video_episode.py::test_beats_bytes_survive_repeated_status_changes[\n] PASSED [ 88%]
tests/test_video_episode.py::test_beats_bytes_survive_repeated_status_changes[\r\n] PASSED [ 90%]
tests/test_video_episode.py::test_trailing_whitespace_and_tabs_in_beats_are_preserved PASSED [ 92%]
tests/test_video_episode.py::test_beats_without_a_trailing_newline_is_preserved PASSED [ 94%]
tests/test_video_episode.py::test_unreadable_episodes_dir_raises_episode_error PASSED [ 96%]
tests/test_video_episode.py::test_create_over_a_dangling_symlink_raises_episode_error PASSED [ 98%]
tests/test_video_episode.py::test_empty_query_does_not_resolve_an_episode PASSED [100%]

============================== 50 passed in 0.22s ==============================
```

Full suite:

```
234 passed in 0.74s
```

---

## 3. Mutation results

Each mutant applied to `episode.py`, full suite run, `git checkout` between.
Verbatim from the driver's output.

| # | Mutant | Result | Caught by |
|---|--------|--------|-----------|
| 1 | `_read_meta` → `path.read_text(encoding="utf-8")` | **killed** — 3 failed, 231 passed | `test_beats_bytes_survive_a_status_change[\r\n]`, `[\r]`, `test_beats_bytes_survive_repeated_status_changes[\r\n]` |
| 2 | `_compose` → drop `head.replace("\n", nl)` | **SURVIVED** — 234 passed | nothing |
| 3 | `_read_meta` → `beats_text.rstrip()` | **killed** — 8 failed, 226 passed | `test_beats_bytes_survive_a_status_change[\n]`, `[\r\n]`, `[\r]`, `..._repeated_status_changes[\n]`, `[\r\n]`, `test_trailing_whitespace_and_tabs_in_beats_are_preserved`, plus the two pre-existing `test_set_status_preserves_comments_and_formatting_in_beats` and `test_beats_bytes_are_identical_across_a_status_change` |
| 4 | `_compose` → append `nl` when beats lacks a trailing newline | **killed** — 1 failed, 233 passed | `test_beats_without_a_trailing_newline_is_preserved` |
| 5 | `_compose` → `beats_text.expandtabs()` | **killed** — 1 failed, 233 passed | `test_trailing_whitespace_and_tabs_in_beats_are_preserved` |
| 6 | `episode_ids` → drop the `try/except OSError` | **killed** — 1 failed, 233 passed | `test_unreadable_episodes_dir_raises_episode_error` |
| 7 | `resolve_episode` → drop the empty-query guard | **killed** — 1 failed, 233 passed | `test_empty_query_does_not_resolve_an_episode` |

**Mutants 3, 4 and 5 — the whitespace blind spot — are now all killed.** That gap
is closed: the byte guarantee is pinned.

**Mutant 2 survived, and that is a real hole.** Dropping `head.replace("\n", nl)`
leaves the *beats* bytes untouched, so every byte assertion still passes — the
tests only ever compare the beats document. What the mutant actually corrupts is
the **metadata block**: a CRLF file comes back with CRLF fences and LF metadata
lines, i.e. we manufacture a mixed-line-ending file. Nothing in the suite looks at
metadata bytes, so nothing notices. Reporting rather than fixing, per the brief.
The missing test is a metadata-side byte assertion, e.g. that `read_bytes()` of a
CRLF script contains no lone `\n`. That matters more than it looks, because of the
next finding.

---

## 4. Files changed

```
src/agenticsocial/video/episode.py
src/agenticsocial/workspace.py
tests/test_video_episode.py
```

- `ff70230` test: pin beats preservation at the byte level, not the content level
- `c47236b` fix: preserve beats bytes exactly, including line endings

Nothing under `docs/` staged. `git status --porcelain -- src tests` is empty.

---

## 5. Issues and concerns

### 5a. Is `_split`'s new regex pair correct for the empty-metadata case?

**Yes — the empty-metadata case is correct.** Constructed and run:

```
  empty metadata  '---\n---\nbeats: []\n'    -> ('', 'beats: []\n', '\n')
  empty metadata CRLF                        -> ('', 'beats: []\r\n', '\r\n')
  no second document '---\na: 1\n'           -> ('a: 1\n', None, '\n')
  single doc, no leading ---                 -> ('a: 1\nb: 2\n', None, '\n')
  only '---\n'                               -> ('', None, '\n')
  empty file ''                              -> ('', None, '\n')
  only '---'                                 -> ('---', None, '\n')
  sep at EOF, no trailing nl                 -> ('a: 1\n---', None, '\n')
```

- `---\n---\nbeats: []\n`: `meta_text` is `text[4:3]` — an inverted slice, which
  Python yields as `""`. `_parse_meta("")` → `safe_load` → `None` → `{}`. The
  `start.end() - len(nl)` search origin does its job: the newline closing the
  opening `---` serves as the separator's leading newline. Remainder is exactly
  `beats: []\n`. Through the real API:
  `b'---\n---\nbeats: []\n'` → `b'---\nstatus: in_review\n---\nbeats: []\n'`.
  Beats byte-identical; metadata now holds only `status`, which is right — there
  was no metadata to preserve.
- **No second document** (`---\na: 1\n`, and the no-fence `a: 1\nb: 2\n`): both
  return `None` for the remainder, so `_compose` writes `beats: []`. Matches the
  pre-existing tolerance tests.
- **`"---\n"` alone**: `("", None, "\n")` → loads as a draft episode. No crash.
- **Empty file**: `_DOC_START_RE` does not match, so the whole (empty) text is
  metadata → `{}` → draft. Matches `test_load_tolerates_an_empty_script`.
- One rough edge, **pre-existing and not a regression**: `---\na: 1\n---` (fence at
  EOF, no trailing newline) fails the `(?=\r\n|\r|\n)` lookahead, so `a: 1\n---`
  goes to the YAML parser, which raises `ComposerError: expected a single document
  in the stream` → surfaces as `EpisodeError`. The old `_SEP = "\n---\n"` did the
  same thing. Loud, not silent. Leaving it.

### 5b. A file mixing line endings — CRLF metadata, LF beats

**The index arithmetic is wrong here, and it silently eats a byte of the operator's
beats document.** This is the part of the brief you flagged, and the suspicion was
justified.

`sep.end() + len(sep.group(1))` assumes the separator's *trailing* newline is the
same length as its *leading* one. `group(1)` is the leading newline. In a mixed
file they differ. Observed through the real API:

```
[crlf-meta-lf-beats] before: b'---\r\nepisode: e\r\nstatus: draft\r\n---\nbeats:\n  - type: statement\n'
[crlf-meta-lf-beats] after : b'---\r\nepisode: e\r\nstatus: in_review\r\n---\r\neats:\n  - type: statement\n'
```

`beats:` became `eats:`. The leading newline is `\r\n` (len 2), the trailing one is
`\n` (len 1), so the `+2` step consumes the `\n` **and the `b`**. `_split` alone:

```
('episode: e\r\nstatus: draft', 'eats:\n  - type: statement\n', '\r\n')
```

The mirror case inserts instead of deleting:

```
[lf-meta-crlf-beats] before: b'---\nepisode: e\nstatus: draft\n---\r\nbeats:\r\n  - type: statement\r\n'
[lf-meta-crlf-beats] after : b'---\nepisode: e\nstatus: in_review\n---\n\nbeats:\r\n  - type: statement\r\n'
```

A spurious blank line appears at the head of the beats document.

**Is it defensible? No.** Silent single-character deletion from the script is
strictly worse than the CRLF→LF rewrite this task fixed: that one changed every
byte and would have tripped `script_sha256` loudly; this one produces a script that
still parses and is quietly wrong. And it is reachable without an operator doing
anything exotic — mutant 2 above shows our own writer can *manufacture* a mixed
file, and an editor appending LF beats to a CRLF file does it too.

**I did not work around it.** The code block is what is committed. The fix is two
characters of intent — stop pretending the trailing newline matches the leading one
and just consume it:

```python
_SEP_RE = re.compile(r"(\r\n|\r|\n)---[ \t]*(\r\n|\r|\n)")
...
    return text[start.end() : sep.start()], text[sep.end() :], nl
```

I trialled exactly that and reverted it. Full suite: **234 passed**, and both
mixed cases become byte-exact:

```
[crlf-meta-lf-beats] after : b'---\r\nepisode: e\r\nstatus: in_review\r\n---\r\nbeats:\n  - type: statement\n'
[lf-meta-crlf-beats] after : b'---\nepisode: e\nstatus: in_review\n---\nbeats:\r\n  - type: statement\r\n'
```

The lookahead buys nothing: the empty-metadata case is handled by the
`start.end() - len(nl)` search origin, not by the lookahead, and consuming the
trailing newline cannot swallow a following third-document fence (verified:
`---\n---\n---\n` still yields `---\n` as the remainder). Recommend a follow-up
task that pairs this with a mixed-ending byte test and a metadata-side byte test
(the mutant-2 gap) — both defects live in the same seam.

### 5c. Does `newline=""` in `atomic_write` change anything on this platform?

**No — provably a no-op here, byte for byte, for every input.** Written both ways
to disk and compared:

```
os.linesep = '\n'
  newline=None  write('a\nb\n')     -> b'a\nb\n'
  newline=''    write('a\nb\n')     -> b'a\nb\n'
  newline=None  write('a\r\nb\r\n') -> b'a\r\nb\r\n'
  newline=''    write('a\r\nb\r\n') -> b'a\r\nb\r\n'
  newline=None  write('a\rb\r')     -> b'a\rb\r'
  newline=''    write('a\rb\r')     -> b'a\rb\r'
```

This is not a sampling argument. With `newline=None`, Python's only write-side
transformation is `"\n"` → `os.linesep`; `\r` and `\r\n` are never touched. Since
`os.linesep == "\n"` on macOS, that mapping is the identity, so `newline=None` and
`newline=""` are equivalent for *any* string on this platform. The change is
correctness for Windows only, and the full suite (234 passed, including every
`frontmatter.dump` path through `create_source`, `create_variant` and
`save_variant`) confirms nothing in the text pipeline observes a difference.

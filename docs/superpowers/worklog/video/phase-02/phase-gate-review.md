# Phase 2 gate review — `feat/video-phase-02-ingest`

Reviewer: QA (adversarial). Wrote none of this code. Baseline: 469 passed in 2.1s.
No `task-*-report.md` was read.

## Verdict: **merge-after-fixes**

The gate itself held. I ran thirteen separate forgery attacks at it —
`dataclasses.replace` to `APPROVED` and to `PUBLISHING`, a hand-mutated `meta`
dict laundered through `save_variant`, a stale `APPROVED` object whose file had
been reverted underneath it, and the video equivalents — and every one was
refused by the on-disk check. That is real work and it is done properly.

Three things stop this being a clean merge, and all three are named in the
phase's own exit criteria:

1. `verify()` returns `[]` on a corpus that contains **no documents at all**,
   because it never validates manifest keys. *"A tampered corpus is detectable"*
   is the criterion; a manifest pointing at `../secret` or at an absolute path
   is not detected.
2. `agsoc video ingest --research` **tracebacks and loses the run** on a search
   result with a hostless href. Criterion: *"No traceback from anything an
   operator can type"*, and also *"one source failing does not lose the others,
   and the failure is recorded"* — neither holds here.
3. The no-network guarantee is **not structural**. I broke `ingest.py` two ways
   and the suite made live DNS and TCP connections to `html.duckduckgo.com`,
   `blog.google` and `venturebeat.com`, taking 150s and 58s. Criterion: *"No
   network in the suite."* It is true of this code, not of this suite.

None is deep. F1 is one line in a loop, F2 is one `except` clause, F3 is a
fifteen-line `conftest.py`. I would merge the day they land.

---

## Findings, ranked

### F1 · HIGH · `verify()` never validates manifest keys — a corpus with nothing in it verifies as sound
`src/agenticsocial/video/corpus.py:148-155`

`write_document` and `document_text` both call `assert_safe_name`. `verify()`
calls it nowhere, and neither does `read_manifest`. It does
`episode.sources_dir / (key + SUFFIX)` on whatever string the manifest hands it.

Reproduced (both return `[]`, with `sources/` containing only `_manifest.json`):

```python
# key "../secret" — target planted one directory up, hashed honestly
{"../secret": {"url": "https://evil.example/", "sha256": <sha of that file>}}
C.verify(ep)   # -> []   "sound"

# an absolute key — pathlib's "/" discards the left operand entirely
{"/tmp/x/outside": {...}}
C.verify(ep)   # -> []   and it read and hashed a file outside the workspace
```

So `verify() == []` currently means *"every recorded key hashes to something
somewhere"*, not *"the corpus on disk is what was fetched"*. `document_text`
then refuses the same key as unsafe, so the pipeline says **sound** and then
says **no such source** — the integrity gate and the reader disagree about the
same corpus. The brief notes keys come from agent-authored YAML from Phase 5;
this is the hole that opens onto.

**Fix:** in the `for key in sorted(manifest)` loop, guard the key and report
rather than raise, so `verify` stays total:

```python
try:
    assert_safe_name(key, "source key", CorpusError)
except CorpusError:
    problems.append(("unsafe", key)); continue
```

Test to add: the sibling of `test_document_text_cannot_reach_outside_the_corpus`
— plant the file where the traversal lands, and assert `verify` reports it.
`test_document_text_refuses_a_traversing_key` already carries the anti-vacuity
note that makes this test easy to write correctly.

### F2 · HIGH · a hostless search result tracebacks, drops the failure, and writes no brief
`src/agenticsocial/video/ingest.py:137` · `src/agenticsocial/video/cli.py:205-208`

`_write` → `key_for` raises `CorpusError` for a URL with no host. `ingest_research`
wraps `extract()` in `try/except Exception` but leaves `_write` bare, and the CLI
catches only `IngestError` and `OSError`. Reproduced through the real `agsoc`
binary (search stubbed at import, no network):

```
$ agsoc video ingest 2026-08-17 --series the-brief --research "gemini"
CorpusError: cannot derive a source key: '/local/story' has no host   [full rich traceback]
$ ls .../sources/     # blog-google.txt, _manifest.json  — written
$ ls .../             # no brief.md
```

DDG returns relative and non-`http` hrefs routinely, so this is a Tuesday, not
an attack. The corpus is left half-filled with no record of what happened, which
is the one outcome §4 exists to prevent.

**Fix:** wrap the `_write` call per result and append to `failures`; add
`C.CorpusError` to the CLI's `except`.

### F3 · HIGH · the no-network guarantee is conditional, exactly as Task 3 feared
`tests/test_video_cli.py:340-350` · `tests/test_video_ingest.py` (no guard at all)

`no_network` is a plain, non-autouse fixture in one test module that patches one
function (`ingest.ingest_research`). `test_video_ingest.py` — which is where
ingestion is actually tested — has no network guard whatsoever; it relies on
every test passing `search=`/`extract=` **and on the implementation honouring
them**.

Measured, with a `socket.connect` / `getaddrinfo` sentinel on `PYTHONPATH`:

| mutation | reached the network | suite wall time |
|---|---|---|
| `search = search or research.search` → `search = research.search` | 3 hits, `html.duckduckgo.com:443` | **150s** |
| same for `extract` | 13 hits, `blog.google`, `venturebeat.com` | 2.3s |
| a `research.search(...)` call added to `ingest_paste` | 1 hit | **58s** |
| a `research.extract(...)` call added to `ingest_source` | 0 — only because no test gives a source an `origin_url` | 2.0s |

That last row is the uncomfortable one: the fetch was there and the suite did
not care. `test_defaults_are_the_research_module` cannot see any of this; it
asserts two signature defaults are `None`, which every one of these mutants
preserves. Its own docstring says it is not behavioural.

**Fix:** a real `tests/conftest.py` with an autouse session fixture that patches
`socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo` to
raise, opt-out by marker. Fifteen lines. It turns a ten-minute hang into a named
failure in the first second, and it protects every test file, present and future.

### F4 · MEDIUM-HIGH · a corpus document may be a symlink, and `verify()` blesses it
`src/agenticsocial/video/corpus.py:150,153,159`

Replace `a-com.txt` with a symlink to a file outside the workspace whose bytes
currently match: `is_file()` follows it, the hash matches, `verify() == []`. The
bytes the corpus vouches for are now owned by something outside the corpus and
can change between the check and the read. `agsoc` never creates one
(`atomic_write`'s `os.replace` overwrites the link), but a hand-built or
agent-built corpus can contain one, and this is the one case where "bytes on
disk" stops being a stable claim rather than merely a wrong one.

Note the asymmetry: `create_episode` and `scaffold_series` both test
`d.exists() or d.is_symlink()`; nothing in `corpus.py` tests `is_symlink()`.

**Fix:** `("unsafe", key)` when `path.is_symlink()`, in `verify` and in
`document_text`.

### F5 · MEDIUM · `document_text()` does not return the bytes that were recorded
`src/agenticsocial/video/corpus.py:79`

`Path.read_text()` applies universal-newline translation. Verified:

```
wrote   'line one\r\nline two\r\n\r\n  padded  '
on disk b'line one\r\nline two\r\n\r\n  padded  '   verify() == []   sha matches
read back 'line one\nline two\n\n  padded  '        != what was written
```

The module's opening sentence is *"a claim is never checked against what an agent
recalls reading — it is checked against bytes on disk"*, and the accessor quietly
rewrites those bytes. Any exact-quote match or character offset computed from
`document_text` — the spec's *"highlight the exact supporting span"* — is
computed against text that is not what `sha256` covers. CRLF is normal in fetched
and pasted material.

This is the same defect the text pipeline already learned once: commit c47236b,
*"preserve beats bytes exactly, including line endings."* `episode.py` preserves;
`corpus.py` does not.

**Fix:** `path.read_bytes().decode("utf-8")`. Test: a document containing CRLF
and trailing spaces round-trips byte-for-byte.

### F6 · MEDIUM · a corrupt `_manifest.json` tracebacks out of the CLI
`src/agenticsocial/video/cli.py:205-208`

Same missing `except` as F2, reached differently — and this one needs no attacker,
only a crash mid-write:

```
$ printf '{"a": ' > .../sources/_manifest.json
$ agsoc video ingest 2026-08-17 --series the-brief --paste p.md
CorpusError: ..._manifest.json: _manifest.json is unreadable — Expecting value ...   [traceback]
```

`test_a_manifest_whose_entries_are_not_objects_is_a_corpus_error` justifies itself
as protecting *"the CorpusError contract that every caller catches"*. The only
caller does not catch it. `video_preview` catches `PlanError` and `RenderError`;
`video_ingest` catches neither of ingest's downstream error types.

### F7 · MEDIUM · re-ingesting the same source or paste duplicates it instead of refreshing
`src/agenticsocial/video/ingest.py:148,171`

`ingest_research` goes through `_write`, which looks the exact URL up in the
manifest so a rebuild reuses the key a claim already cites — the failure mode
`test_the_same_url_twice_reuses_its_key` calls *"the one failure here that
produces a wrong fact-check rather than a loud one."* `ingest_paste` and
`ingest_source` call `C.write_document` directly and skip that entirely. Ingest
the same source twice and you get `src-x` and `src-x-2` holding identical bytes;
paste twice and `_pasted` / `_pasted-2` (pinned as correct by
`test_a_second_paste_does_not_overwrite_the_first`, which is defensible for a
paste — two pastes really are two documents — but is undefensible for
`--from-source`, where the identity of the source is known exactly).

Worse for `--from-source`: `key = f"src-{source.id}"[:64]`. Two source ids
sharing a 64-character prefix collapse to one key, and because this path skips
the URL check, the second silently gets `-2` rather than being recognised as
distinct-or-same. **Fix:** route `ingest_source` through `_write` keyed on the
source id, or record the source id in the manifest entry and match on it.

### F8 · MEDIUM (test gap) · the sha256 comparison itself is unpinned
`src/agenticsocial/video/corpus.py:154`

`digest != manifest[key].get("sha256")` → `.get("sha256", digest)` **survives the
entire suite**. Under that mutant a manifest entry with no `sha256` verifies as
sound no matter what the document says. The code is right today (missing → `None`
→ mismatch → `modified`, which I confirmed, as I did for `sha256: null`), but the
central claim of the phase has no test standing behind it. Add: a manifest entry
with `sha256` deleted, over a tampered document, must report `modified`.

### F9 · MEDIUM (test gap) · no test uses a document whose bytes have padding
Hashing `raw.strip()` instead of `raw` survives the suite: every test document is
unpadded, so the corpus's byte-exactness is only ever tested on bytes that make
stripping a no-op. Same blind spot that produces F5.

### F10 · MEDIUM (test gap) · the gate's own default status is unpinned
`src/agenticsocial/workspace.py:231`

`meta.get("status", Status.DRAFT.value)` → `Status.APPROVED.value` **survives all
469 tests.** This is the fallback the publish gate reads for a variant file with
no `status:` key. The safe default is currently there by care alone; nothing in
the suite would notice it flipping. (I confirmed the live behaviour is safe: no
frontmatter, empty frontmatter, and a missing `status` key all read as `draft`
and are refused.) Add one test: a variant file with no `status:` key cannot be
posted.

### F11 · MEDIUM · `publishing` is a self-granting status on the resume path
`src/agenticsocial/cli.py:207-211`

Write `status: publishing` into a variant that was never approved (`approved_at:
null`, `posted_ids: []`) and `agsoc post <id> --resume` skips the gate branch
entirely and proceeds to the keyring:

```
$ agsoc post 2026-08-17-attack-me --resume
no X token — connect first with `agsoc auth x`     # i.e. it got past the gate
```

With a token present it publishes. I am *not* calling this a bypass: anyone who
can write `publishing` can write `approved`, and the file is the record by
design. But the resume shortcut is the one place where a status grants passage
without any approval evidence existing, and the evidence is right there in the
same file. **Cheap hardening:** honour the shortcut only when
`meta["approved_at"]` is set (or `posted_ids` is non-empty) — a genuinely
interrupted publish always has both.

### F12 · LOW-MEDIUM (test gaps) · three ingest guards nothing tests
All three survive the suite:
- `if not text or not text.strip()` → `if not text` — a whitespace-only
  extraction becomes a corpus document containing nothing, citable as a source.
- `ingest_paste`'s empty-text guard removed entirely — `agsoc video ingest
  --paste empty.md` would report success on an empty corpus. (Live behaviour is
  correct; I confirmed it exits 1 with *"pasted text was empty"*. Untested.)
- `raise IngestError("search failed: … check your connection")` → `results = []`
  — a connection failure reported as *"nothing was ingested"*. The existing test
  patches `ingest_research` itself, so it covers the CLI's handler and not the
  conversion.

### F13 · LOW · malformed search results vanish or crash
`if not url: continue` survives the suite — a result with no `href` is dropped
with **no failure recorded**, so neither the count nor the brief mentions it.
Non-dict / non-string result shapes (`search` returning `None`, `"str"`,
`[{"href": 5}]`) raise `TypeError` / `AttributeError` out of `ingest_research`,
uncaught by the CLI. Same family as F2 and the same one-line fix.

### F14 · LOW · `tests/test_cli.py` still uses the exception-swallowing runner
`tests/test_video_cli.py:17` wraps `CliRunner` with `catch_exceptions=False` and
documents why (D-035). `tests/test_cli.py` — which owns every test of `post`, the
command that publishes — uses the bare `runner.invoke`. I injected a crash at the
top of `post` and all five of its tests failed, so nothing is vacuous **today**;
they survive only because each asserts a distinctive string (`"allowed next"`,
`"--resume"`). The failure output reads `assert 'allowed next' in ''` — that empty
string is the traceback being swallowed. One future test written as
`assert result.exit_code == 1` alone is silently vacuous. Apply the same wrapper.

### F15 · LOW · a keyring failure tracebacks (pre-existing)
`PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring agsoc post <id>` →
`NoKeyringError` traceback from `x_auth.load_token()`. Normal on a headless box
or over SSH. Not introduced here, but `cli.py::post` was edited in this phase and
`auth` next door handles its own `AuthError` cleanly.

### F16 · LOW · orphan detection is shallow
`verify()` iterates `sources_dir` non-recursively and skips anything failing
`is_file()`. An unrecorded `sources/sub/secret.txt`, and a symlink to a directory
in `sources/`, are both invisible. Low harm — a claim can only cite a guarded key
— but "a document nothing recorded" is exactly what the check is for.

### F17 · LOW · corpus keys have neither a charset rule nor a length cap
`write_document` accepts keys `" "`, `"..."`, `"..txt"`, `"-"`. Episode ids get
`assert_safe_name` **and** `EPISODE_ID_RE` **and** `MAX_ID_LEN`; series slugs get
`assert_safe_name` **and** `SLUG_RE` **and** `MAX_NAME_LEN`; corpus keys get only
the first, and the 64-character cap lives in `ingest.py`, not in the module that
owns the filenames. Keys are citation tokens from Phase 3 onward.

### F18 · INFORMATIONAL · approval is per-status, not per-content
Documented in CLAUDE.md, so not a finding against this phase — but I demonstrated
it end to end and it belongs in the same conversation as D-059: approve a
variant, then `save_variant` a replaced body (which correctly does *not* change
status), then post. `posted == ['SWAPPED PAYLOAD']`. Agents are permitted to write
variant files; *"any change to a variant body means resetting `status:
in_review`"* is a convention with nothing enforcing it. A body sha256 recorded in
`set_status(APPROVED)` and re-checked in `publish_variant` would close it in about
six lines, and this phase already built the exact machinery (`disk_status`) that
makes it natural.

---

## Harness-blindness audit

I looked for tests that would pass if the code did nothing, and injected total
crashes (`raise RuntimeError` at the top of `post`, `approve`, and `video ingest`)
to find them mechanically.

**Actively vacuous: none found.** The crash injections killed 5/5 `post` tests,
3/3 `approve` tests and 23 `video ingest` tests. The corpus tests carry
anti-vacuity notes and every one I checked holds up under the mutation that
matches its docstring — `test_verify_is_silent_when_the_corpus_dir_does_not_exist`
really does enter its branch, `test_document_text_cannot_reach_outside_the_corpus`
really does plant the file where the traversal lands, and
`test_verify_detects_a_same_length_modification` really is length-preserving.
This is the strongest test file in the repo.

**Blind in the sense that matters, though:**

1. `tests/test_video_ingest.py::test_defaults_are_the_research_module` — the only
   test claiming to protect the no-fetch seam, and it cannot detect a fetch. Every
   network-reaching mutant I wrote leaves both defaults `None`. Its docstring is
   honest about this ("Not behavioural"); the problem is that nothing behavioural
   exists beside it. (F3)
2. The `no_network` fixture — a fixture that guards only the tests that request it
   and only one function. Its own docstring states the risk it exists to prevent
   ("without this the test would then fetch for real and hang rather than fail"),
   and then leaves `test_video_ingest.py` unguarded. (F3)
3. `tests/test_cli.py` — 23 tests one weak assertion away from vacuity, in the
   file that covers publishing. (F14)
4. Untested-by-construction, found by mutation rather than by reading: the sha256
   comparison (F8), byte padding (F9), the gate's default status (F10), the three
   ingest guards (F12), the missing-href skip (F13). Each of these is a line whose
   deletion changes behaviour and changes no test.

One test I would call mis-aimed rather than blind:
`test_a_second_paste_does_not_overwrite_the_first` pins `_pasted-2` as correct
while `test_the_same_url_twice_reuses_its_key` pins refresh-in-place as correct.
Both are defensible; nothing records why the two branches differ (F7).

## Sibling asymmetry list

Comparing `corpus.py`, `ingest.py`, `episode.py`, `series.py` function by function:

1. `write_document` and `document_text` guard the key with `assert_safe_name`;
   **`verify()` and `read_manifest()` do not**. (F1)
2. `atomic_write` opens with `newline=""` to preserve bytes; `document_text` reads
   with `read_text()`, which translates them. Within the same module. (F5)
3. `episode.py` goes to real trouble to preserve beats bytes verbatim (D-026,
   c47236b); `corpus.py`, whose entire purpose is byte fidelity, does not. (F5)
4. `ingest_research` writes through `_write` (URL-stable key); `ingest_paste` and
   `ingest_source` call `C.write_document` directly. (F7)
5. `ingest_research` wraps `search()` and `extract()` in `try/except`; the
   `_write` call between them is bare. (F2)
6. `video_preview` catches `PlanError` and `RenderError`; `video_ingest` catches
   neither `CorpusError` nor anything a malformed result can raise. (F2, F6, F13)
7. `create_episode` validates name + charset + length and checks
   `d.exists() or d.is_symlink()`; `write_document` validates name only and does
   `mkdir(exist_ok=True)` with no symlink check. (F4, F17)
8. `read_manifest` converts `OSError` to `CorpusError`; `verify()` lets `OSError`
   from `iterdir()` and `read_bytes()` escape raw, so callers written against the
   `CorpusError` contract miss it.
9. `episode_ids()` converts `OSError` to `EpisodeError` specifically so
   `agsoc video list` can degrade gracefully; `verify()` has no such contract.
10. `_brief` defends against `C.CorpusError` from `read_manifest`;
    `_existing_key_for_url`, three lines away, calls the same function bare. (F6)
11. `tests/test_video_cli.py` uses `catch_exceptions=False`; `tests/test_cli.py`
    does not. (F14)
12. `x/publish.py` threads `set_status`'s return value; `cli.py::approve` discards
    it. Harmless today (nothing reads `v` after), but it is the pattern the phase
    just spent a commit standardising.

## Mutation results

63 mutants, whole-suite runs, weighted per the brief. Sentinel on `PYTHONPATH`
recording every `connect` / `create_connection` / `getaddrinfo`.

| module | mutants | killed | survived | real survivors |
|---|---|---|---|---|
| `video/ingest.py` | 23 | 17 | 6 | 5 |
| `video/cli.py` | 16 | 14 | 2 | 1 |
| `video/corpus.py` | 11 | 9 | 2 | 2 |
| `workspace.py` / `models.py` / `x/publish.py` / `video/episode.py` | 13 | 11 | 2 | 1 |

**Survivors that matter**

| id | mutation | consequence |
|---|---|---|
| I5 | `if not text or not text.strip()` → `if not text` | a whitespace-only fetch becomes a citable empty document (F12) |
| I6 | drop `if not url: continue` | result with no href vanishes with no failure recorded (F13) |
| I14 | drop `ingest_paste`'s empty guard | empty paste reported as a successful ingest (F12) |
| I16 | `raise IngestError(...)` → `results = []` | a connection failure reported as an empty corpus (F12) |
| I19 | `title = ...` → `title = ""` | manifest titles never recorded; provenance silently thinner |
| C10 | `if m is not None` → `if m` | `--research ""` reads as "no mode", and `--research "" --paste f` passes the exactly-one check and silently takes research |
| K1 | `.get("sha256")` → `.get("sha256", digest)` | a manifest entry with no sha256 verifies as sound (F8) |
| K4 | `sha256(raw)` → `sha256(raw.strip())` | byte padding is outside every test (F9) |
| W4 | `disk_status` default `DRAFT` → `APPROVED` | the gate's own fallback is untested (F10) |

**Equivalent / cosmetic survivors** (recorded so nobody re-derives them): I7
(`_write` returning `existing` — identical under `replace=True`); G1
(`cli.py::post` reading `v.status` instead of `ws.disk_status(v)` — `_load`
re-reads from disk, so no test can distinguish them; the hunk is defence in depth,
not a behaviour change); G4 (discarding `set_status`'s return in `publish.py` —
nothing downstream reads `variant.status`); W5 (`newline=""` in `atomic_write` —
unobservable on POSIX, load-bearing on Windows); N2 (a fetch added to
`ingest_source` — silent only because no test gives a source an `origin_url`,
which is itself the F3 gap).

**Network reached during mutation:** 17 outbound attempts across 3 mutants, to
`html.duckduckgo.com:443`, `blog.google:443`, `venturebeat.com:443`. Two of those
runs took 150s and 58s instead of 2s.

## Gate attacks (all refused)

| attack | result |
|---|---|
| `publish_variant` on a draft | `TransitionError` |
| `replace(v, status=APPROVED)` then publish | `TransitionError` |
| `replace(v, status=PUBLISHING)` then publish (skips the gate branch) | `TransitionError` |
| `v.meta["status"]="approved"` + `save_variant` + publish | `TransitionError`, disk still `draft` |
| `set_status(draft → PUBLISHING)` | `TransitionError` |
| `set_status(replace(APPROVED) → PUBLISHING)` | `TransitionError` |
| stale `APPROVED` object after the file was reverted to draft | `TransitionError` |
| `agsoc post` on a draft (real CLI, subprocess) | exit 1, before the keyring |
| `agsoc approve` on a draft (real CLI, subprocess) | exit 1 |
| episode `set_status(draft → RENDERING)` | `TransitionError` |
| episode `set_status(replace(APPROVED) → RENDERING)` | `TransitionError` |
| stale `APPROVED` episode after the file was reverted | `TransitionError` |
| `agsoc video ingest ../../../../etc` / `--series ../../..` | refused as unsafe |

Two things did go through, neither an in-memory forgery: a hand-edited file
saying `approved` (by design — the file is the record), and the `--resume`
shortcut on a hand-written `publishing` (F11).

## Spec coverage

- **§4 ① INGEST** — all three inputs (research / paste / existing source) produce
  `brief.md` + `sources/*.txt`. Implemented.
- **§5 layout** — `sources/`, `_manifest.json` (`url`, `fetched_at`, `sha256`,
  `title`, plus `bytes`), `_pasted.txt`, `brief.md`: all present and in the right
  places. One documentation drift: §5 illustrates `venturebeat.txt`, the
  implementation writes `venturebeat-com.txt`. The reasoning in `key_for`'s
  docstring is sound (stripping the TLD needs a TLD list and gets `.co.uk` wrong);
  the spec should be corrected to match rather than the other way round.
- **§11 `agsoc video ingest`** — present with `--research`, `--paste`,
  `--from-source`. `--corroborate` correctly deferred (D-041).
- Nothing implemented without authorisation. `claims.json` is Phase 3, absent, as
  it should be.
- **Exit criteria:** 3 of 6 met unconditionally (`--research`, `--paste`, partial
  failure). *"A tampered corpus is detectable"* — met for honest tampering, not
  for a hostile or hand-built manifest (F1, F4). *"No network in the suite"* — met
  by this code, not by this suite (F3). *"No traceback from anything an operator
  can type"* — not met (F2, F6, F13, F15).

## On the deferred list

Reviewed; I would not reclassify any of them as harm. One note: the accepted
"a symlinked series or `episodes/` directory can write outside the workspace"
(D-041/D-057) now has a new instance — `sources/` — and it interacts with F4,
where a symlink stops being a write-location question and becomes an integrity
question. Worth re-reading that decision when F4 is fixed, not before.

## What I could not verify

- Anything downstream of the corpus: the mechanical and adversarial check passes
  (Phase 3+) are what will actually consume `document_text`, so F5's practical
  severity depends on code that does not exist yet.
- Real `ddgs` / `trafilatura` behaviour — deliberately never exercised. My
  malformed-result cases are constructed, not observed; I believe relative hrefs
  are common but did not confirm it against the live service.
- Filesystem behaviour beyond this macOS/APFS box. Case-insensitivity and unicode
  normalisation on a case-sensitive Linux volume or on Windows are untested by me
  and by the suite. F5's `newline=""` question is Windows-only.
- Concurrency: two `agsoc video ingest` runs against one episode. `atomic_write`
  makes each file safe, but the manifest is read-modify-write and the loser's
  entries are lost. I did not pursue it — a local single-operator tool.
- `engine/` and anything render-related; out of scope for this phase.

---

Restored every file I touched. `git status --porcelain -- src tests` is empty.
Nothing staged, nothing committed.

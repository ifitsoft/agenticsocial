# Task 4 Report — Gate fixes: the verifier must not trust its own manifest

**Branch:** `feat/video-phase-02-ingest` · **Follows:** `cad0230`

**Headline metric — mutation score: 15/18 (83%) as I delivered it in four
commits; 18/18 (100%) as the branch now stands.** All ten of the brief's
mutants: 9/10 → **10/10**. My own sweep: 6/8 → **8/8**.

The three survivors were all one finding: **the conftest socket guard does not
stop the library that actually searches** — `ddgs` fetches through `primp`, a
Rust HTTP client invisible to a Python `socket` patch. Measured, not reasoned.

> **Provenance note.** Two follow-up commits (`6bb6897`, `287da46`) landed on
> this branch at 16:09, after I finished my four. **They are not mine** — I did
> not write or commit them. They apply the exact remedy this report recommended
> in section 5. I have since re-measured them and record the result here so the
> document matches the branch; see §3 and §5-Q1. The 18/18 figure belongs to the
> branch, not to my four commits.

---

## 1. What I changed, per finding

### F3 — isolation as a mechanism (commit `57cf483`)

`tests/conftest.py`, new, exactly as the brief specifies: an autouse fixture
patching `socket.socket.connect`, `socket.socket.connect_ex` and
`socket.create_connection` to raise `NetworkUseInTest`.

The brief also says to delete the `no_network` fixture in
`tests/test_video_ingest.py`. **There is no such fixture in that file.** It
lives in `tests/test_video_cli.py:341`, and it is not a network guard at all —
it stubs `ingest.ingest_research` with `_fake_ingest(["stub-source"], [])`. I
followed the intent, deleted it there, and measured first that deletion is safe:
the suite still passed 469/469 in 1.98s with it gone, because every `--research`
test that needs the stub patches `ingest_research` itself. Two tests
(`..._unknown_episode...`, `..._unknown_series...`) took it only as a network
guard and now rely on conftest. Flagging the file-name discrepancy per the
ground rules.

### F1, F4, F5, F8, F9 — corpus integrity (commit `675219e`)

`src/agenticsocial/video/corpus.py`:

- `verify()` runs `assert_safe_name` on every manifest key **before** it builds
  a path, and records `("unsafe", key)` without resolving it. A key of
  `../../../../../../outside` no longer causes a file outside the workspace to
  be hashed.
- `verify()` records `("symlink", key)` for a symlinked document and does not
  hash it. The corpus must own the bytes it vouches for.
- A manifest entry with no `sha256` is `("modified", key)` explicitly, rather
  than relying on `digest != None` — which is correct today but is exactly what
  `.get("sha256", digest)` silently undoes.
- `document_text` is `path.read_bytes().decode("utf-8")`. `read_text` applies
  universal-newline translation, so a CRLF document was returned as different
  bytes than its sha256 covers. Same defect `c47236b` fixed for beats.
- `verify`'s docstring now names all five problem kinds.

### F2 — ingest records what it cannot key (commit `d6bca60`)

`ingest_research` catches `C.CorpusError` around `_write` and appends to
`failures`. Partial failure is the module's stated normal case, and a result the
corpus cannot key is one of them.

### F10, F11 — the gate (commit `192a771`)

`cli.py::post` now refuses a `publishing` status with no `approved_at`, placed
before the interrupted/resume branch and before the keyring, so a forged status
fails without prompting for credentials. `disk_status`'s DRAFT fallback is now
pinned by a test.

---

## 2. TDD evidence

Every implementation change was preceded by a failing test.

**Step 2 RED** (`/tmp/t4/step2-red.txt`):

```
FAILED tests/test_video_corpus.py::test_verify_refuses_a_manifest_key_that_escapes_the_corpus - AssertionError: assert 'missing' == 'unsafe'
FAILED tests/test_video_corpus.py::test_verify_flags_a_symlinked_document - AssertionError: assert ('symlink', 'blog-google') in []
FAILED tests/test_video_corpus.py::test_document_text_returns_the_bytes_the_hash_covers - AssertionError: assert 'line one\nline two\n' == 'line one\r\nline two\r\n'
3 failed, 49 passed in 0.48s
```

`test_a_manifest_entry_with_no_sha256_is_not_sound` (F8) and
`test_padding_a_document_is_a_modification` (F9) were **green on arrival**. They
are regression pins against M7/M8, not RED tests — the code already hashed
unstripped bytes and already compared against a `.get("sha256")` that returns
`None`. Both mutants are killed (section 3), which is what they are for.

**Step 3 RED** (`/tmp/t4/step3-red2.txt`):

```
FAILED tests/test_video_ingest.py::test_a_hostless_result_that_extracts_is_recorded_not_raised - agenticsocial.video.corpus.CorpusError: cannot derive a source key: 'not-a-...
1 failed, 17 passed in 0.15s
```

**The brief's own F2 test does not reproduce F2.** Run verbatim against the
unfixed code it passes (`/tmp/t4/step3-red.txt`: `17 passed`), because
`fake_extract` returns `None` for an unmapped url, so `not-a-url` is rejected as
"no readable text extracted" and never reaches `_write`. I kept the brief's test
(code blocks are authoritative) and added
`test_a_hostless_result_that_extracts_is_recorded_not_raised`, which maps
`not-a-url` to text so `key_for` actually raises. That one is RED above and it
is the test that kills M3.

**Step 4 RED** (`/tmp/t4/step4-red.txt`):

```
FAILED tests/test_cli.py::test_resume_refuses_a_publishing_that_was_never_approved - assert 0 == 1
1 failed, 49 passed in 0.27s
```

Exit code 0 — the forged variant **published**. `test_disk_status_defaults_to_draft...`
(F10) was green on arrival, a pin against M9.

**Suite at my four commits:** `479 passed in 1.45s` (baseline before this task:
469 passed in 1.83s). 10 tests added.
**Suite on the branch as it now stands:** `482 passed in 3.18s` — the three extra
are `tests/test_no_network.py` from `6bb6897`, which is not mine.

---

## 3. Mutation results

Harness: `/tmp/t4/mutate.py` — applies one textual mutation, runs the full suite
under a 90s hard timeout, restores the file, reports. Raw output:
`/tmp/t4/mutants-a.txt`, `/tmp/t4/mutants-b.txt`, `/tmp/t4/net-measure.txt`.

### The brief's ten

| # | Mutant | Verdict | Killed by |
|---|--------|---------|-----------|
| M1 | `verify()` without the manifest-key guard | **KILLED** (1.9s) | `test_verify_refuses_a_manifest_key_that_escapes_the_corpus` |
| M2 | guards the key but still hashes the resolved path | **KILLED** (1.6s) | same |
| M3 | `ingest_research` lets `CorpusError` propagate | **KILLED** (1.9s) | `test_a_hostless_result_that_extracts_is_recorded_not_raised` |
| M4 | conftest socket guard removed | **SURVIVED** at my 4 commits → **KILLED** (83.7s) after `6bb6897` | `test_research_search_is_blocked_in_tests`, `test_research_extract_is_blocked_in_tests` |
| M5 | `verify()` follows symlinks | **KILLED** (2.0s) | `test_verify_flags_a_symlinked_document` |
| M6 | `document_text` back to `read_text()` | **KILLED** (1.9s) | `test_document_text_returns_the_bytes_the_hash_covers` |
| M7 | `.get("sha256", digest)` | **KILLED** (1.8s) | `test_a_manifest_entry_with_no_sha256_is_not_sound` |
| M8 | `sha256(raw.strip())` | **KILLED** (1.8s) | `test_padding_a_document_is_a_modification` |
| M9 | `disk_status` fallback → `APPROVED` | **KILLED** (2.2s) | `test_disk_status_defaults_to_draft_not_something_permissive` |
| M10 | `post --resume` ignores `approved_at` | **KILLED** (1.7s) | `test_resume_refuses_a_publishing_that_was_never_approved` |

**9/10.**

**M4 is unkillable by construction, and I want to be exact about why.** I removed
`tests/conftest.py` and ran the suite with an independent socket sentinel loaded
via `-p` (`/tmp/t4/sentinel.py`), which records every `connect`/`connect_ex`/
`create_connection` to a file:

```
rc= 0 secs=3.3
['479 passed in 1.77s']
sentinel file exists: False
```

479 pass and **zero** socket attempts. Against the *correct* implementation no
test wants a socket, so no assertion can notice the guard's absence. The guard
did not constrain current behaviour; it only constrained what a *future wrong*
implementation costs. That is a legitimate reason for it to exist and an
illegitimate reason to score it — I reported it as SURVIVED rather than
excusing it.

**This is now fixed on the branch, and the fix is exactly the right shape.**
`6bb6897` adds `tests/test_no_network.py`, which asserts *directly* that
`research.search` and `research.extract` raise inside a test. That converts an
unobservable property into an assertion, so M4 is now killable. Re-measured:

```
M4  KILLED  rc=1  83.7s  2 failed, 480 passed in 81.95s (0:01:21)
      killed by: test_research_search_is_blocked_in_tests
      killed by: test_research_extract_is_blocked_in_tests
```

Note the 83.7s. With conftest deleted those two tests do not merely fail — they
reach DuckDuckGo for real first. The runtime *is* the evidence that the guard is
what stands between this suite and a live fetch.

### My own sweep

| # | Mutant | Verdict | Killed by |
|---|--------|---------|-----------|
| S1 | `verify()` never reports `missing` | **KILLED** (1.8s) | `test_verify_detects_a_missing_document`, `test_verify_reports_every_problem_sorted` |
| S2 | `document_text` drops its `assert_safe_name` | **KILLED** (1.8s) | 6× `test_document_text_refuses_a_traversing_key[...]` (8 failures) |
| S3 | F2 swallowed silently — `continue` without recording the failure | **KILLED** (1.8s) | `test_a_hostless_result_that_extracts_is_recorded_not_raised` |
| S4 | F11 check present but its `approved_at` condition always false | **KILLED** (1.9s) | `test_resume_refuses_a_publishing_that_was_never_approved` |
| S5 | `document_text` decodes with `errors="replace"` | **KILLED** (1.6s) | `test_a_non_utf8_document_is_a_corpus_error` |
| N1 | `search = research.search` — injected search ignored | **ESCAPED** at my 4 commits → **KILLED** (3.6s) after `287da46` | 12 failures across `test_video_ingest.py` |
| N2 | `extract = research.extract` — injected extract ignored | **KILLED** (3.6s) | 9 failures across `test_video_ingest.py` |
| N3 | both N1 and N2 | **ESCAPED** at my 4 commits → **KILLED** (2.1s) after `287da46` | 12 failures across `test_video_ingest.py` |

**6/8 at my four commits → 8/8 on the branch.** S1–S5 confirm the new assertions
are load-bearing in both directions; S3 and S4 in particular confirm the F2 and
F11 fixes are pinned by *content*, not merely by presence.

Re-measured after `287da46` (`/tmp/t4/net-recheck.txt`):

```
N1  KILLED  rc=1  3.6s  NetworkUseInTest=36  12 failed, 470 passed in 1.93s
N3  KILLED  rc=1  2.1s  NetworkUseInTest=36  12 failed, 470 passed in 1.93s
```

Both previously ran the full 90s to timeout against DuckDuckGo. They now fail in
seconds, and `NetworkUseInTest` is raised 36 times and surfaced as assertions
rather than absorbed into a hang.

**Combined: 15/18 = 83% as delivered in my four commits; 18/18 = 100% as the
branch now stands.**

---

## 4. Files changed and commit SHAs

My four, in the order the brief specifies:

```
57cf4831ab8c4b45c7f9e866c1fdb16a45cef44b  test: block sockets suite-wide instead of trusting one fixture
675219e674f81406dfa46d3fa9c3a6f690a70def  fix: the verifier must not trust its own manifest
d6bca60eba6de82b18721642fa1cd7b3ac370992  fix: a result the corpus cannot key is a failure, not an abort
192a7717b15786855cbeef40dda51eb63fabd437  fix: publishing cannot grant itself
```

Two further commits are on the branch. **They are not mine** — they landed at
16:09, after I finished, and apply the §5-Q1 remedy:

```
6bb6897daae10385e45d0d7dd54b6d098c89a216  test: pin that the suite cannot reach the network
287da462418dcde38459680f63261085fd3c3c2b  test: block the fetch seam, not just the socket
```

That makes six commits on the branch where the ground rules specify four. I am
flagging the count rather than reconciling it, since the extra two are not mine
to squash or reorder.

```
 src/agenticsocial/cli.py          |  5 +++
 src/agenticsocial/video/corpus.py | 29 ++++++++++++++----
 src/agenticsocial/video/ingest.py |  9 +++++-
 tests/conftest.py                 | 27 +++++++++++++++++
 tests/test_cli.py                 | 46 ++++++++++++++++++++++++++++
 tests/test_video_cli.py           | 18 ++---------
 tests/test_video_corpus.py        | 64 +++++++++++++++++++++++++++++++++++++++
 tests/test_video_ingest.py        | 35 +++++++++++++++++++++
 tests/test_workspace.py           | 13 ++++++++
 9 files changed, 224 insertions(+), 22 deletions(-)
```

Nothing under `docs/` staged. `git status --porcelain -- src tests` is clean.

---

## 5. Issues and concerns

### Q1 — After the conftest guard, does any mutant still reach a socket?

**At my four commits: yes.** Measured, and it was the most important finding in
this report. **On the branch as it now stands: no** — commits `6bb6897` and
`287da46` (not mine, see the provenance note) closed it, and I have re-measured
to confirm rather than take it on trust. The original measurement is preserved
below because it is the evidence for why the fix is shaped the way it is; the
closing sub-section records the recheck.

The guard patches Python's `socket` module. `research.search` goes through
`ddgs`, which uses **`primp` — a Rust HTTP client that opens its sockets in
native code and never touches `socket.socket`.** The guard is invisible to it.

Direct probe with the guard installed exactly as conftest installs it
(`/tmp/t4/probe_primp.py`, output `/tmp/t4/probe_primp.txt`):

```
urllib: blocked by the guard
  0.0s
ddgs: REACHED NETWORK, 2 results
  2.7s
```

Two live results off DuckDuckGo, in-process, under the guard.

Then, per-mutant, with the guard modified to *record* each attempt before
raising (measurement instrument, reverted after):

| Mutant | Wall time | Python-socket attempts blocked | Outcome |
|---|---|---|---|
| N1 (`search` injection ignored) | **90.0s, timed out** | 3, all to `html.duckduckgo.com:443` | escaped — real searches ran via primp |
| N2 (`extract` injection ignored) | 3.6s | 15, to `2001:4860:4802:32::15` (blog.google) and `216.150.1.1` (venturebeat) | **killed fast — the guard worked** |
| N3 (both) | 90.0s, timed out | 57, incl. `2620:0:861:ed1a::1:443` (Wikimedia) | escaped |

So the guard is doing real work on the extraction path — `trafilatura` uses
`urllib3`, which is pure Python, and N2 dies in 3.6s instead of hanging. It does
nothing on the search path, which is where the gate review's
`html.duckduckgo.com` attempts and its 150s run came from. **F3 is half fixed.**
A mutant that ignores the injected `search` still hangs the suite for as long as
you let it.

I did not fix this, for two reasons: the brief gives conftest's contents as an
authoritative code block, and the ground rules fix the commit count at four.
The remedy I recommended was one block appended to the same autouse fixture,
test-side only, no new dependency — guarding the project's own single fetch
seam, which both `ingest.py` and `research.py` document as the only place
fetching happens:

```python
    from agenticsocial import research

    monkeypatch.setattr(research, "search", blocked)
    monkeypatch.setattr(research, "extract", blocked)
```

#### Recheck — the remedy was applied by someone else, and it works

`287da46` added exactly that block to `tests/conftest.py`, and `6bb6897` added
`tests/test_no_network.py` pinning it (including a NEGATIVE test that a test can
still install its own fake, which is the property that keeps the guard from
breaking legitimate injection). Neither commit is mine. Re-measured on the
branch as it stands:

| Mutant | Before (my 4 commits) | After (`287da46`) |
|---|---|---|
| N1 injected `search` ignored | 90.0s, timed out, live DuckDuckGo | **KILLED in 3.6s**, 36 `NetworkUseInTest` |
| N3 both ignored | 90.0s, timed out, 57 blocked attempts | **KILLED in 2.1s**, 36 `NetworkUseInTest` |
| M4 conftest removed | SURVIVED, unobservable | **KILLED in 83.7s** by the two new tests |

Full suite on the branch: **482 passed in 3.18s**, `git status --porcelain -- src tests`
clean.

"The suite cannot reach the network" is now **true for both search and
extraction**, and — unlike before — it is asserted rather than assumed. F3 is
fully fixed.

### Q2 — Does `verify()` now refuse everything it should?

It refuses the reported hole and the family around it: traversing keys, symlinks,
missing documents, modified bytes, a missing hash, and orphans. Two gaps remain,
neither reachable by the reported attack and both worth recording:

1. **`read_manifest` still does not validate key *types* or entry field types.**
   A key that is not a string (JSON forbids it) is impossible, but
   `manifest[key]["sha256"]` being an `int` or a `list` compares unequal to a
   hex digest and reports `("modified", key)` — loud, so acceptable.
2. **A hardlink is not a symlink.** `path.is_symlink()` is False for a hardlink,
   so a document hardlinked from outside the corpus verifies as sound and its
   bytes are shared with a file the corpus does not own. Editing through the
   other name is still caught (the sha256 changes), so this is a weaker hole
   than F4 — nobody can change the bytes unnoticed — but the corpus does not
   solely own them. Fixing it means comparing `st_nlink > 1`, which also flags
   innocent cases. Recording it rather than guessing.

No manifest I could construct now makes `verify()` hash a file outside
`sources_dir`.

### Q3 — Anything F11 breaks for a legitimate resume?

Nothing I could find, and I tested the case explicitly:
`test_a_legitimately_approved_publishing_still_resumes` drives
`draft → in_review → approved → publishing` through the real gate and then
`post --resume`, and it publishes (exit 0, status `published`). It passed both
before and after the fix, so the fix is not paid for by a working path.

Two things I checked deliberately:

- `publish_variant` never clears `approved_at`; `set_status(APPROVED)` is the
  only writer and nothing removes it. A variant that reached `publishing`
  through the gate always carries it.
- The check keys on `PUBLISHING` only, so resuming from `FAILED` is untouched.

One residual: a variant file hand-written or produced by a pre-`approved_at`
schema, sitting legitimately mid-publish, would now be refused. `create_variant`
has always written the key, and `workspace/` is not version-controlled, so I
judge this to be theoretical — but it is the only way this check can bite an
honest user, and the error message tells them exactly what to do
("Reset status to in_review and approve it").

### Q4 — Discrepancies flagged, per the ground rules

1. The `no_network` fixture is in `tests/test_video_cli.py`, not
   `tests/test_video_ingest.py`, and it is a stub injector rather than a network
   guard. The `git add` line in step 1 names the wrong file. (Section 1.)
2. The brief's F2 test passes against the unfixed code — it never reaches the
   raising call. Kept as given, plus a test that actually reproduces F2.
   (Section 2.)
3. Step 1's prose says "session-wide"; the code block's fixture takes
   `monkeypatch` and is therefore function-scoped. Followed the code block. The
   effect is the same (every test is guarded) and function scope is strictly
   better here, since per-test `monkeypatch` restoration is what lets an
   individual test override it. Noting it only because the words differ.

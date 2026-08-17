# Task 4b Report: Guard the seam we own, not the socket we don't

**Branch:** `feat/video-phase-02-ingest` · **Follows:** `192a771`

| | |
|---|---|
| Test commit (RED) | `6bb6897` — *test: pin that the suite cannot reach the network* |
| Guard commit (GREEN) | `287da46` — *test: block the fetch seam, not just the socket* |

## 1. What I changed

- **New** `tests/test_no_network.py` — three tests, verbatim from the brief. Two
  positive (`research.search` / `research.extract` must raise something whose
  message mentions "network"), one negative (a test's own `monkeypatch.setattr`
  must still win over the guard).
- **Extended** `tests/conftest.py::_no_network` — kept all three socket patches,
  added `monkeypatch.setattr(research, "search"/"extract", blocked)`, and took
  the brief's reworded message ("a test tried to reach the network. Tests must
  never fetch —"). Verbatim from the brief's code block.

Nothing under `src/` changed. Nothing under `docs/` was staged.

### Tooling note

`timeout` does not exist on this machine (macOS, no coreutils, `gtimeout` absent).
Every run below was bounded with `perl -e 'alarm shift; exec @ARGV' <secs> …`,
which is equivalent (SIGALRM survives `exec`; a kill shows up as exit 142). No
run was unbounded. This is a deviation from the brief's literal `timeout 120 …`
command, flagged here because the brief's code blocks are authoritative.

## 2. RED / GREEN

**RED** (`/tmp/red.txt`, guard not yet installed) — exactly the two failures the
brief predicted, plus the negative test passing:

```
FAILED tests/test_no_network.py::test_research_search_is_blocked_in_tests - Failed: DID NOT RAISE Exception
FAILED tests/test_no_network.py::test_research_extract_is_blocked_in_tests - Failed: DID NOT RAISE Exception
2 failed, 1 passed in 13.57s
```

Two things in that run are worth recording, because they are the leader's claim
reproduced independently:

- `research.search` **did not raise at all**. It reached duckduckgo through
  primp and returned results, with the socket guard installed. The 13.57s is
  almost entirely that live fetch.
- `research.extract` did not raise either — but for a different reason. The
  socket guard *did* fire; `trafilatura` swallowed it and returned `None`:
  `ERROR trafilatura.downloads: download error: https://example.com/a a test
  tried to open a socket…`. So even where the socket guard worked, it produced
  a silent `None` rather than a failure. A seam guard fails loudly; a socket
  guard is at the mercy of whatever catches `Exception` above it.

**GREEN** — full suite, before and after:

| | tests | runtime |
|---|---|---|
| before (`192a771`, `/tmp/baseline.txt`) | 479 passed | 2.21s |
| after (`287da46`, `/tmp/green.txt`) | 482 passed | 2.07s |

+3 tests, and the suite is no slower. A confirming re-run after reverting the
mutants gave `482 passed in 5.05s` (`/tmp/green2.txt`); the spread between 2.07s
and 5.05s is machine noise on a 2-second suite, not the guard.

## 3. The two escaped mutants, re-measured

Both applied to `src/agenticsocial/video/ingest.py` and reverted with
`git checkout --` afterwards. Suite run: `tests/test_video_ingest.py`.

| mutant | Task 4 | now | reaches out? |
|---|---|---|---|
| `search = research.search` (ignores injected `search`) | 90.0s → timeout | **0.80s, 12 failed / 6 passed** | no |
| both: `search = research.search`, `extract = research.extract` | 90.0s → timeout | **1.26s, 12 failed / 6 passed** | no |

Wall-clock for the whole bounded invocation was 2.52s and 1.46s respectively
(interpreter startup included). Both now fail with the guard's own message
rather than a network timeout:

```
FAILED tests/test_video_ingest.py::test_the_brief_records_the_query
  - agenticsocial.video.ingest.IngestError: search failed: a test tried to reac...
```

Neither mutant reaches the network. Both are killed at the first `search(...)`
call, before any `extract`, which is why the second mutant is not slower than
the first. Roughly a **70×** improvement, and more to the point a *deterministic*
failure instead of a timeout that depends on DNS and duckduckgo's mood.

## 4. Existing tests that broke

**None.** All 479 pre-existing tests still pass, including the eight `respx`
tests in `tests/test_auth.py` and `tests/test_x_client.py`. Nothing had to be
weakened.

The ordering argument in the brief holds as written: the autouse fixture runs
during setup, and a test body's later `monkeypatch.setattr` overwrites the
guard's attribute. `tests/test_no_network.py::test_a_test_can_still_install_its_own_fake`
pins that, and it is the test that passed even in RED — worth noting that it
therefore only became meaningful in GREEN.

## 5. Issues and concerns

### Q1 — Is `research.search` / `research.extract` genuinely the only fetch seam?

Grep of `src/` for `httpx|urllib|requests|subprocess|socket|curl|ddgs|trafilatura|webbrowser|HTTPServer`
(`/tmp/outbound_grep.txt`) finds four outbound-capable sites, not two:

| site | stack | status under the guard |
|---|---|---|
| `research.py:10,22` — `ddgs`, `trafilatura` | primp (Rust) / urllib3 | **guarded at the seam** (the new patch) |
| `x/client.py:15,22` — `httpx.Client.post` | httpcore → Python `socket` | **guarded by the socket patch** |
| `x/auth.py:48` — `httpx.post` | httpcore → Python `socket` | **guarded by the socket patch** |
| `x/auth.py:109,111` — `HTTPServer` bind, `webbrowser.open` | Python stdlib | binds/opens a browser; only reachable from `authorize()`, which no test calls |
| `video/render.py:40` — `subprocess.run` of `node` / `ffmpeg` | child process | **not guarded** — see below |

`x/auth.py:71,108` and `video/corpus.py:17` are `urllib.parse` only — string
parsing, no I/O.

**Are the `httpx` sites reachable from a test? Measured, not reasoned.** I ran a
throwaway probe file inside the suite (deleted afterward, never committed) that
calls `httpx.get`, `XClient.post_tweet`, and `auth._exchange` against real URLs
with no mock (`/tmp/probe.txt`):

```
HTTPX_DIRECT: NetworkUseInTest a test tried to reach the network. Tests must never fetch — …
XCLIENT:      NetworkUseInTest a test tried to reach the network. Tests must never fetch — …
AUTH:         NetworkUseInTest a test tried to reach the network. Tests must never fetch — …
3 passed in 0.06s
```

So: reachable in principle, blocked in practice, and blocked *fast* (0.06s for
all three). `httpx` is pure-Python down to `socket.create_connection`, so unlike
`ddgs` it has no native bypass. The socket patch is genuinely load-bearing for
the `x/` half and should not be removed now that the seam guard exists — the two
cover different stacks.

**The one remaining hole is `video/render.py`.** `_run` shells out to `node`
(Playwright) and `ffmpeg`. A child process inherits neither the socket patch nor
the `research` patch — both are in-process monkeypatches. Today every render
test patches `R.subprocess.run`, so nothing launches, but that is *convention*,
exactly the state `research` was in before Task 4. A mutant that dropped the
injection there would spawn Playwright and could reach the network for as long
as the browser felt like it. Not in scope for 4b and not currently exploitable,
but it is the honest answer to "is the seam guard complete": it is complete for
in-process fetches, and `subprocess` is out of its reach by construction. If
Phase 8 makes `render` a first-class command, the same lesson applies — guard
`render._run`, the seam we own, rather than trying to police a child process.

### Q2 — Does the guard break `respx`-based tests?

**No, and there is a reason it cannot.** `respx` patches the httpx *transport*,
so a mocked request is answered in Python and never descends to
`socket.create_connection` — the socket patch has nothing to fire on. And
`respx` has no relationship to `agenticsocial.research`, so the seam patch is
irrelevant to it. Measured: all eight `@respx.mock` tests in `test_auth.py` and
`test_x_client.py` pass in the GREEN run.

There is one shape of `respx` test that *would* break: one that lets a request
fall through to a real transport (`respx.mock(assert_all_mocked=False)` with
pass-through, or a URL outside the mocked routes). That break would be correct —
such a test is reaching the network — and the fix would be to add the route, not
to relax the guard.

### Other notes

- The guard's `blocked` closure ignores its arguments, so `research.search` and
  `research.extract` become argument-signature-blind during tests. That is fine
  for a raiser, but it means the guard cannot catch a caller that passes the
  *wrong arguments* to `search` — signature drift is pinned separately by
  `test_video_ingest.py::test_defaults_are_the_research_module`.
- `NetworkUseInTest` is defined in `conftest.py`, so it is not importable by
  name from a test module. Tests that want to assert on it must match the
  message (as `test_no_network.py` does with `"network" in str(e)`) or catch
  `Exception`. Acceptable, but if a future test needs the type, the class should
  move to a real module.

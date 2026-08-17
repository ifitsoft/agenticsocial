# Task 4b Brief: Guard the seam we own, not the socket we don't

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `192a771`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Small and bounded. **This is the last blocker on the Phase 2 gate.**

## Why the socket guard is not enough

Task 4 added an autouse socket guard. It half works, and the reason matters.
Leader-verified with the guard installed exactly as `conftest.py` installs it:

```
urllib : blocked (RuntimeError)
ddgs   : *** REACHED NETWORK *** 2 results
```

`ddgs` depends on **`primp`, a Rust HTTP client that opens sockets in native code
and never touches Python's `socket` module.** Patching `socket.socket.connect` is
invisible to it. `trafilatura` uses urllib3, which is pure Python, so extraction
*is* guarded — search is not.

Measured consequence: two mutants ran **90 seconds to timeout** against
`html.duckduckgo.com` instead of failing. "No network in the suite" is a Phase 2
exit criterion and it is currently false.

**The lesson generalises:** you cannot reliably guard a boundary you do not own.
`socket` belongs to Python; `primp` bypasses it. **`research.search` and
`research.extract` belong to us** — they are this project's only two fetch calls,
and a guard there cannot be bypassed by a dependency's choice of HTTP stack.

## Ground rules

- **Two commits.** Test first, then the guard. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 22 defects across four phases.
- Do not add dependencies. Never stage anything under `docs/`.
- **Use a timeout on every run.** A previous run of this suite hung for ten
  minutes on a live fetch, and another for 90 seconds.

---

- [ ] **Step 1: The test**

Append to `tests/conftest.py`'s module — no, put it in a real test file. Create
`tests/test_no_network.py`:

```python
"""The suite must not reach the network, whatever the code under test does.

A socket guard is not sufficient: ddgs fetches through primp, a Rust HTTP client
that never touches Python's socket module. The guard has to sit on the seam this
project owns -- research.search and research.extract are its only two fetch
calls.
"""
import pytest

from agenticsocial import research


def test_research_search_is_blocked_in_tests():
    """precondition: nothing in this test patches research.search. If this ever
    fails, a suite run can reach duckduckgo and hang rather than fail."""
    with pytest.raises(Exception) as e:
        research.search("gemini pricing", max_results=1)
    assert "network" in str(e.value).lower()


def test_research_extract_is_blocked_in_tests():
    """precondition: nothing in this test patches research.extract."""
    with pytest.raises(Exception) as e:
        research.extract("https://example.com/a")
    assert "network" in str(e.value).lower()


def test_a_test_can_still_install_its_own_fake(monkeypatch):
    """NEGATIVE half: the guard must not stop a test injecting a fake. It runs
    first; a test's own patch wins afterwards."""
    monkeypatch.setattr(research, "search", lambda q, max_results=8: [{"href": "x"}])
    assert research.search("q") == [{"href": "x"}]
```

```bash
timeout 120 uv run pytest tests/test_no_network.py 2>&1 | tail -10
git add tests/test_no_network.py
git commit -m "test: pin that the suite cannot reach the network

A socket guard misses ddgs entirely -- it fetches through primp, a Rust
client that never touches Python's socket module. Measured: urllib
blocked, ddgs reached the network and returned results."
```

Expect **two failures** (the guard does not exist yet) and one pass.

- [ ] **Step 2: Guard the seam**

In `tests/conftest.py`, extend the existing autouse fixture. Keep the socket
patches — they catch anything that goes through Python's stack and cost nothing:

```python
@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def blocked(*a, **kw):
        raise NetworkUseInTest(
            "a test tried to reach the network. Tests must never fetch — "
            "inject or patch the fetcher instead."
        )

    # Python's socket layer catches trafilatura (urllib3) and anything else in
    # pure Python.
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    # But it does NOT catch ddgs: it fetches through primp, a Rust client that
    # opens sockets in native code. You cannot guard a boundary you do not own.
    # research.search/extract are this project's only two fetch calls, and a
    # guard there cannot be bypassed by a dependency's choice of HTTP stack.
    from agenticsocial import research

    monkeypatch.setattr(research, "search", blocked)
    monkeypatch.setattr(research, "extract", blocked)
```

Ordering matters and is why this works: the autouse fixture installs the guard
before each test body runs, and a test that wants a fake calls
`monkeypatch.setattr` afterwards, which wins. Nothing that already passes should
break — **but verify that rather than trusting me**, and if something does break,
report whether the guard or the test is wrong.

```bash
timeout 300 uv run pytest 2>&1 | tail -6
git add tests/conftest.py
git commit -m "test: block the fetch seam, not just the socket

ddgs reaches the network through primp, a Rust HTTP client invisible to a
Python socket patch. Two mutants ran 90s to timeout against duckduckgo
instead of failing. research.search/extract are the only two fetch calls
this project makes, and a guard there cannot be bypassed."
```

- [ ] **Step 3: Measure, do not reason**

Re-run the two mutants that escaped in Task 4 — `ingest_research` ignoring its
injected `search`, and ignoring both injected callables — and confirm each now
**fails fast** rather than reaching out. Report the wall time for each; the
previous figures were 90.0s and 90.0s to timeout.

```bash
timeout 180 uv run pytest -q 2>&1 | tail -3     # baseline, note the runtime
```

Then, with the guard in place, run the direct probe:

```bash
timeout 60 uv run python -c "
import socket, pytest
" 2>/dev/null; timeout 120 uv run pytest tests/test_no_network.py -q 2>&1 | tail -3
```

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-4b-report.md`:

1. **What I changed.**
2. **RED/GREEN**, and the full-suite count and runtime before and after.
3. **The two escaped mutants, re-measured** — wall time each, and whether either
   still reaches out.
4. **Any existing test that broke**, and whether the guard or the test is wrong.
5. **Issues or concerns**, including:
   - Is `research.search`/`research.extract` genuinely the only fetch seam? Grep
     for any other outbound call in `src/` — `httpx`, `urllib`, `requests`,
     `subprocess` invoking `curl`. `x/auth.py` and `x/client.py` use `httpx`; are
     they reachable from a test?
   - Does the guard break `respx`-based tests, which legitimately intercept HTTP?

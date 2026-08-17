# Task 3d Brief: Fix the separator arithmetic, pin metadata bytes

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `c47236b`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Two defects, both mine, both in the regex I told the 3c implementer I was least
confident about. It attacked it as asked, found them, trialled a fix, reverted it
and reported rather than working around the brief. This task lands its fix.

**1. The index arithmetic is wrong for mixed line endings.**
`text[sep.end() + len(sep.group(1)):]` assumes the separator's *trailing* newline
is the same length as its *leading* one. Leader-verified:

```
CRLF metadata + LF beats  →  b'\r\neats:\n  - type: statement\n'
```

The `b` of `beats:` is eaten. The mirror case inserts a spurious blank line.
This is worse than the bug 3c fixed: that one changed every byte and would trip
`script_sha256` loudly, while this produces a script that still parses and is
quietly wrong.

Mixed endings are not exotic — **our own writer manufactures them.** Mutant 2
below shows `_compose` emitting CRLF fences around LF metadata lines.

**2. Mutant 2 survived 3c: nothing asserts on metadata bytes.** Dropping
`head.replace("\n", nl)` leaves beats bytes intact, so every byte test still
passes; what it corrupts is the metadata block. The suite pins beats bytes, not
script bytes.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not modify existing tests. Do not add dependencies.
- Never stage anything under `docs/`. Report observed counts.

## Files

- Modify: `src/agenticsocial/video/episode.py`
- Modify: `tests/test_video_episode.py` (append only)

---

- [ ] **Step 1: Append the tests, run, commit them failing**

```python
# --- mixed line endings, and the metadata block ---------------------------------
# `sep.end() + len(sep.group(1))` assumed the separator's trailing newline was
# the same length as its leading one. With CRLF metadata and LF beats it ate the
# first byte of the beats document, silently, leaving a file that still parses.


@pytest.mark.parametrize(
    "meta_nl,beats_nl",
    [("\r\n", "\n"), ("\n", "\r\n"), ("\r", "\n"), ("\n", "\r"), ("\r\n", "\r")],
)
def test_mixed_line_endings_preserve_beats_bytes(series, meta_nl, beats_nl):
    ep = create_episode(series, "ep")
    meta = meta_nl.join(["episode: e", "series: the-brief", "status: draft", ""])
    beats = beats_nl.join(["beats:", "  - type: statement", ""])
    ep.script_path.write_bytes(
        f"---{meta_nl}{meta}---{beats_nl}{beats}".encode()
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert beats.encode() in ep.script_path.read_bytes()


def test_first_byte_of_beats_is_never_eaten(series):
    """The specific corruption: b'beats:' became b'eats:'."""
    ep = create_episode(series, "ep")
    ep.script_path.write_bytes(
        b"---\r\nepisode: e\r\nseries: the-brief\r\nstatus: draft\r\n"
        b"---\nbeats:\n  - type: statement\n"
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    raw = ep.script_path.read_bytes()
    assert b"beats:" in raw
    assert b"eats:\n" not in raw.replace(b"beats:", b"")


def test_an_all_crlf_script_stays_all_crlf(series):
    """Kills the 3c survivor: dropping head.replace() emits LF metadata lines
    inside CRLF fences, and no byte test looked at the metadata block."""
    ep = create_episode(series, "ep")
    ep.script_path.write_bytes(
        b"---\r\nepisode: e\r\nseries: the-brief\r\nstatus: draft\r\n"
        b"---\r\nbeats:\r\n  - type: statement\r\n"
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    raw = ep.script_path.read_bytes()
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0


def test_an_all_lf_script_stays_all_lf(series):
    ep = create_episode(series, "ep")
    ep.script_path.write_bytes(
        b"---\nepisode: e\nseries: the-brief\nstatus: draft\n"
        b"---\nbeats:\n  - type: statement\n"
    )
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert b"\r" not in ep.script_path.read_bytes()
```

```bash
uv run pytest tests/test_video_episode.py 2>&1 | tail -30
git add tests/test_video_episode.py
git commit -m "test: pin mixed line endings and the metadata block's bytes

CRLF metadata with LF beats silently ate the first byte of the beats
document. Nothing asserted on metadata bytes, so the 3c mutant that
emits LF metadata inside CRLF fences survived."
```

- [ ] **Step 2: Implement**

In `src/agenticsocial/video/episode.py`, `_SEP_RE` consumes the separator's
trailing newline instead of looking ahead, and `_split` slices from `sep.end()`:

```python
_SEP_RE = re.compile(r"(\r\n|\r|\n)---[ \t]*(\r\n|\r|\n)")


def _split(text: str) -> tuple[str, str | None, str]:
    """Split into (metadata text, verbatim remainder, newline).

    Purely textual — nothing here parses YAML. The separator's trailing newline
    is consumed by the match, so the remainder begins at the first byte the
    operator wrote. Do NOT reintroduce a lookahead and compute the offset from
    the leading newline's length: the two newlines can differ (CRLF metadata,
    LF beats) and that arithmetic silently ate the first byte of beats. See
    D-033.

    The search begins at `start.end() - len(nl)` so the newline ending the
    opening `---` can serve as the separator's leading newline when the
    metadata document is empty.
    """
    start = _DOC_START_RE.match(text)
    if not start:
        return text, None, "\n"
    nl = start.group(1)
    sep = _SEP_RE.search(text, start.end() - len(nl))
    if not sep:
        return text[start.end() :], None, nl
    return text[start.end() : sep.start()], text[sep.end() :], nl
```

Nothing else changes. `_compose` already re-emits the metadata block with `nl`
and the beats text untouched.

- [ ] **Step 3: Run everything, then commit**

```bash
uv run pytest tests/test_video_episode.py -v 2>&1 | tail -40
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/episode.py
git commit -m "fix: consume the separator's trailing newline instead of guessing its length

The offset was computed from the LEADING newline's length, so a script
with CRLF metadata and LF beats lost the first byte of its beats
document -- silently, leaving a file that still parsed."
```

- [ ] **Step 4: Mutation check**

Apply each, run the full suite, `git checkout` between. All must fail:

1. `_split` → `text[sep.end() + len(sep.group(1)) :]` (the old arithmetic)
2. `_compose` → drop `head.replace("\n", nl)` (the 3c survivor)
3. `_SEP_RE` → `r"(\r\n|\r|\n)---[ \t]*(?=\r\n|\r|\n)"` with `text[sep.end():]`
4. `_split` → search from `start.end()` instead of `start.end() - len(nl)`

Mutant 2 is the one 3c could not kill. If it survives again, say so plainly.

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-3d-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN (both runs).
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Which newline does the separator line itself use when metadata and beats
     disagree, and is that defensible?
   - Is there any remaining input where a write path changes a byte the operator
     wrote? This is the fourth attempt at this guarantee — if you can still break
     it, that is the single most useful thing you can tell me.

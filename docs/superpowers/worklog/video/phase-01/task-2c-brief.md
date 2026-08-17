# Task 2c Brief: A correct TOML string escaper, and the last two unvalidated fields

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `8af23fd`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Task 2b replaced naive interpolation with `json.dumps` as a TOML basic-string
escaper. **That was my mistake and it is a live bug.** `json.dumps` defaults to
`ensure_ascii=True`, which encodes non-BMP characters as UTF-16 surrogate pairs.
TOML v1.0.0 requires every `\uXXXX` escape to be a Unicode *scalar* value, and
surrogates are not scalar values.

Verified against the committed code:

```
name       = "The Brief 😀"
SeriesError: …/series.toml: malformed series.toml — Escaped character is not a
Unicode scalar value
```

Both `--name "The Brief 😀"` and `--name "北京 𠀋"` fail. So does any historic
script or CJK extension-B ideograph. And it fails in the D-020 shape all over
again: **we write the file, then blame the operator for it being malformed.**

The obvious correction is also wrong. `ensure_ascii=False` fixes non-BMP but then
emits raw U+007F (DELETE), which TOML forbids inside a basic string. Neither flag
setting is correct on its own — this needs an explicit escaper.

Two smaller items ride along, both raised by the Task 2b implementer: `acts` and
`warm_acts` are now the only fields reaching the system unvalidated, directly
below `formats`, which is strictly validated.

## Ground rules

- **Two commits.** Failing tests first, then the implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — five of my briefs have had that defect, and
  the last one was caught by an implementer, not by me.
- Do not modify existing tests. Do not add dependencies.
- Never stage anything under `docs/`. Report observed counts, not predicted ones.

## Files

- Modify: `src/agenticsocial/video/series.py`
- Modify: `tests/test_video_series.py` (append only)

---

- [ ] **Step 1: Append the tests, run, commit them failing**

```python
# --- TOML basic-string escaping ------------------------------------------------
# json.dumps was wrong: ensure_ascii=True emits UTF-16 surrogate pairs for
# non-BMP characters, and TOML requires \uXXXX escapes to be Unicode scalar
# values. ensure_ascii=False is also wrong: it emits raw U+007F, which TOML
# forbids in a basic string. Hence an explicit escaper.


@pytest.mark.parametrize(
    "hostile",
    [
        "The Brief 😀",            # non-BMP: emoji
        "北京 𠀋",                  # non-BMP: CJK extension B
        "Ünïcödé BMP",             # BMP non-ASCII
        "Ω≈ç√∫",                   # BMP symbols
        "del\x7fhere",             # U+007F, forbidden raw in TOML
        "bell\x07here",            # C0 control with no short escape
        "null\x00byte",            # U+0000
        "esc\x1bseq",              # U+001B
        'quote" and \\slash',
        "line\nbreak\ttab\r\n",
        "\x0c formfeed \x08 backspace",
        "mixed 😀 \x07 \"q\" \\s ünïcödé",
    ],
)
def test_any_name_round_trips_through_toml(ws, hostile):
    """A name is operator input. Every string must survive scaffold -> load."""
    scaffold_series(ws, "hostile", name=hostile)
    assert load_series(ws, "hostile").name == hostile


def test_every_codepoint_below_0x100_round_trips(ws):
    """Sweep the whole C0/C1 + Latin-1 range rather than sampling it."""
    name = "".join(chr(c) for c in range(1, 0x100))
    scaffold_series(ws, "sweep", name=name)
    assert load_series(ws, "sweep").name == name


def test_non_bmp_name_produces_a_literal_utf8_file(ws):
    """The escaper must pass non-ASCII through literally, not escape it.
    TOML files are UTF-8; escaping is only for what UTF-8 cannot carry safely."""
    s = scaffold_series(ws, "emoji", name="The Brief 😀")
    raw = (s.dir / "series.toml").read_text(encoding="utf-8")
    assert "😀" in raw
    assert "\\ud83d" not in raw


def test_del_and_control_chars_are_escaped_not_literal(ws):
    s = scaffold_series(ws, "ctrl", name="del\x7fhere")
    raw = (s.dir / "series.toml").read_text(encoding="utf-8")
    assert "\x7f" not in raw
    assert "\\u007F" in raw or "\\u007f" in raw


def test_hostile_name_round_trips_through_coverage_json_too(ws):
    import json as _json

    name = "😀 \"q\" \\s \x07"
    s = scaffold_series(ws, "both", name=name)
    data = _json.loads((s.dir / "coverage.json").read_text(encoding="utf-8"))
    assert data["series"] == name


# --- acts / warm_acts were the last unvalidated fields -------------------------


@pytest.mark.parametrize("bad", ['"not a list"', "5", "{a = 1}", '["a", "b"]'])
def test_wrong_shaped_acts_is_rejected(ws, bad):
    _write_series(ws, "bad", f'[series]\nname = "B"\n\n[structure]\nacts = {bad}\n')
    with pytest.raises(SeriesError, match="acts"):
        load_series(ws, "bad")


def test_wellformed_acts_still_loads(ws):
    _write_series(
        ws,
        "good",
        '[series]\nname = "G"\n\n'
        '[[structure.acts]]\nid = "01"\nlabel = "One"\nbeats = 6\n',
    )
    assert load_series(ws, "good").acts == [{"id": "01", "label": "One", "beats": 6}]


@pytest.mark.parametrize("bad", ['"03"', "[3]", "5"])
def test_wrong_shaped_warm_acts_is_rejected(ws, bad):
    _write_series(
        ws, "bad", f'[series]\nname = "B"\n\n[structure]\nwarm_acts = {bad}\n'
    )
    with pytest.raises(SeriesError, match="warm_acts"):
        load_series(ws, "bad")
```

```bash
uv run pytest tests/test_video_series.py 2>&1 | tail -40
git add tests/test_video_series.py
git commit -m "test: pin TOML escaping across the codepoint range, and acts shape

json.dumps emits UTF-16 surrogate pairs for non-BMP characters, which
TOML rejects as non-scalar. Any emoji or CJK ext-B name was impossible."
```

- [ ] **Step 2: Implement**

**2a.** In `src/agenticsocial/video/series.py`, replace `_toml_str` entirely.
Remove nothing else that uses `json` — `render_coverage_json` keeps using it.

```python
_TOML_SHORT_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _toml_str(value: str) -> str:
    """Render a TOML v1.0.0 basic string.

    TOML files are UTF-8, so every printable character — including non-BMP ones
    like emoji — is written literally. Only what UTF-8 cannot carry safely
    inside a basic string gets escaped: the quote, the backslash, the C0
    controls, and U+007F.

    Do NOT substitute json.dumps here. With ensure_ascii=True it emits UTF-16
    surrogate pairs, which TOML rejects because \\uXXXX must name a Unicode
    scalar value; with ensure_ascii=False it emits raw U+007F, which TOML
    forbids in a basic string. Neither setting is correct. See D-022.
    """
    out = ['"']
    for ch in value:
        short = _TOML_SHORT_ESCAPES.get(ch)
        if short is not None:
            out.append(short)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)
```

**2b.** In `load_series`, immediately after the `target_sec` validation and
before the `return`, add:

```python
    acts = structure.get("acts", [])
    if not isinstance(acts, list) or not all(isinstance(a, dict) for a in acts):
        raise SeriesError(
            f"{path}: [[structure.acts]] must be a list of tables — "
            "write [[structure.acts]] blocks, not a bare acts = value"
        )

    warm_acts = structure.get("warm_acts", [])
    if not isinstance(warm_acts, list) or not all(
        isinstance(a, str) for a in warm_acts
    ):
        raise SeriesError(f"{path}: [structure] warm_acts must be a list of strings")
```

and change the two corresponding arguments in the `Series(...)` call to use the
locals:

```python
        acts=acts,
        warm_acts=warm_acts,
```

Deliberately *shape* validation only. Whether an act has a usable `id`, a
positive `beats`, or a unique id is the renderer's business in Phase 4 — it owns
that meaning. This task only guarantees the loader hands Phase 4 a list of
tables rather than a string it will index into character by character.

- [ ] **Step 3: Run everything, then commit**

```bash
uv run pytest tests/test_video_series.py -v 2>&1 | tail -40
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/series.py
git commit -m "fix: write TOML basic strings correctly instead of via json.dumps

json.dumps with ensure_ascii=True emits UTF-16 surrogate pairs for
non-BMP characters; TOML requires \\uXXXX to name a Unicode scalar, so
any emoji or CJK ext-B series name produced a file we then blamed the
operator for. ensure_ascii=False is also wrong: raw U+007F is forbidden
in a basic string. Uses an explicit escaper.

Also shape-validates acts and warm_acts, the last two fields reaching
the loader unchecked."
```

- [ ] **Step 4: Mutation check**

Apply each to `series.py`, run `uv run pytest 2>&1 | tail -3`, `git checkout`
between each. All must fail:

1. `_toml_str` → `return json.dumps(value)`
2. `_toml_str` → `return json.dumps(value, ensure_ascii=False)`
3. `_toml_str` → `return '"' + value + '"'`
4. drop the `elif ord(ch) < 0x20 or ord(ch) == 0x7F` branch (controls raw)
5. drop the `acts` shape check
6. drop the `warm_acts` shape check

Mutant 2 is the important one: it is the plausible "fix" a future maintainer
reaches for. If it survives, the escaper is not actually pinned. Report any
survivor rather than strengthening the tests yourself.

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-2c-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped, test-only commit) and GREEN (both runs).
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed** and both commit SHAs.
5. **Issues or concerns**, including:
   - Is the escaper now actually correct against TOML v1.0.0? Try to break it.
     Lone surrogates in the *input* (`"\ud800"`) are the case I am least sure of
     — what does Python do writing that to a UTF-8 file, and what should we do?
   - `render_coverage_json` uses `ensure_ascii=False`; `_toml_str` now writes
     literal UTF-8 too. Are the two files finally consistent about encoding
     policy, or is there still a case where they disagree about the same string?
   - Anything else in `series.py` still reaching the system unvalidated.

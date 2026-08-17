# Task 0 Brief: Carried debt that becomes load-bearing this phase

**Phase:** 3 · **Branch:** `feat/video-phase-03-script-schema`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Small, and it clears the decks. Both items were deferred with reasons; both stop
being deferrable now.

## Why now

**`tolerance_sec` becomes a gate input this phase.** Phase 3 adds
`abs(total - target_sec) > tolerance_sec`. Today `tolerance_sec` accepts
`"eight"`, `-99` and `true`, sitting one line below `target_sec`, which is
strictly validated *for exactly this reason*. A gate reading an unvalidated
value is how the last four bypasses started (D-025, D-063).

**`register` is branched on in Phase 4** and accepts `"shouty"` today, so a typo
silently selects a default branch. Unlike `cadence`, which is explicitly
advisory.

**Two separate `64` constants** (`MAX_NAME_LEN` in `series.py`, `MAX_ID_LEN` in
`episode.py`) will drift exactly as D-036 predicts — that pattern has produced
five defects, and the first module to touch either is this one.

## The rules, with their negative halves

- **R1** `tolerance_sec` must be a non-negative integer. **Negative:** `0` is
  valid (an exact-runtime series); `-1`, `"eight"` and `true` are not.
- **R2** `register` must be one of a known set. **Negative:** `cadence` stays
  free-form, because nothing branches on it.
- **R3** `name` and `byline` must be strings. **Negative:** absent is fine and
  defaults; present-but-wrong-typed is an error.
- **R4** One length limit, one constant, both modules. **Negative:** changing it
  in one place must not leave the other at the old value.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `tolerance_sec` check dropped | R1 |
| M2 | `tolerance_sec` rejects `0` | R1 negative |
| M3 | `tolerance_sec` accepts `True` (bool is an int) | R1 |
| M4 | `register` check dropped | R2 |
| M5 | `cadence` validated against a set too | R2 negative |
| M6 | `name`/`byline` type check dropped | R3 |
| M7 | one module's limit changed, the other left | R4 |

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 22 defects across four phases.
- Do not add dependencies. Never stage anything under `docs/`.
- **Report the mutation score.**

---

- [ ] **Step 1: Tests**

Append to `tests/test_video_series.py`:

```python
# --- fields that become gate inputs this phase (D-025, D-063) ------------------


@pytest.mark.parametrize("bad", ['"eight"', "-1", "true", "1.5"])
def test_bad_tolerance_sec_is_rejected(ws, bad):
    """precondition: no other field is invalid, so only tolerance_sec can fail.
    Phase 3 gates runtime on this value; target_sec one line above is strictly
    validated for exactly this reason."""
    _write_series(ws, "bad", f'[series]\nname = "B"\n\n[runtime]\ntolerance_sec = {bad}\n')
    with pytest.raises(SeriesError, match="tolerance_sec"):
        load_series(ws, "bad")


def test_zero_tolerance_is_valid(ws):
    """R1 NEGATIVE: a series demanding an exact runtime is legitimate, and a
    naive `> 0` check would reject it."""
    _write_series(ws, "exact", '[series]\nname = "E"\n\n[runtime]\ntolerance_sec = 0\n')
    assert load_series(ws, "exact").tolerance_sec == 0


@pytest.mark.parametrize("bad", ['"shouty"', "5", "true"])
def test_unknown_register_is_rejected(ws, bad):
    """precondition: register is the only invalid field. Phase 4 BRANCHES on
    this; a typo must not silently select a default."""
    _write_series(ws, "bad", f'[series]\nname = "B"\n\n[series]\n')  # placeholder
    _write_series_overwrite(ws, "bad", f'[series]\nname = "B"\nregister = {bad}\n')
    with pytest.raises(SeriesError, match="register"):
        load_series(ws, "bad")


def test_both_registers_in_the_spec_are_accepted(ws):
    for value in ("reported", "first-person"):
        slug = "r-" + value.replace("-", "")
        _write_series(ws, slug, f'[series]\nname = "R"\nregister = "{value}"\n')
        assert load_series(ws, slug).register == value


def test_cadence_stays_free_form(ws):
    """R2 NEGATIVE: cadence is explicitly advisory (spec 6) — nothing branches
    on it, so validating it would reject a legitimate 'fortnightly'."""
    _write_series(ws, "c", '[series]\nname = "C"\ncadence = "fortnightly"\n')
    assert load_series(ws, "c").cadence == "fortnightly"


@pytest.mark.parametrize("field", ["name", "byline"])
@pytest.mark.parametrize("bad", ["5", "[\"a\"]", "true"])
def test_non_string_text_fields_are_rejected(ws, field, bad):
    """precondition: the field is present. A non-string name reaches _toml_str
    on the next scaffold and raises TypeError far from here."""
    _write_series(ws, "bad", f'[series]\n{field} = {bad}\n')
    with pytest.raises(SeriesError, match=field):
        load_series(ws, "bad")


def test_absent_text_fields_still_default(ws):
    """R3 NEGATIVE: absent is not the same as wrong-typed."""
    _write_series(ws, "min", "[series]\n")
    s = load_series(ws, "min")
    assert s.name == "min" and s.byline == ""


def test_one_length_limit_shared_by_both_modules(ws):
    """R4. Two separate 64s will drift exactly as D-036 predicts — that pattern
    has produced five defects in this project."""
    from agenticsocial.video import episode as E
    from agenticsocial.video import series as S

    assert S.MAX_NAME_LEN is E.MAX_ID_LEN
```

Add the helper the register test needs, next to `_write_series`:

```python
def _write_series_overwrite(ws, slug, body):
    d = ws.series_dir / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "episodes").mkdir(exist_ok=True)
    (d / "series.toml").write_text(body, encoding="utf-8")
```

```bash
uv run pytest tests/test_video_series.py 2>&1 | tail -15
git add tests/test_video_series.py
git commit -m "test: pin the series fields that become gate inputs

tolerance_sec accepts \"eight\", -1 and true today, one line below
target_sec which is strictly validated for exactly this reason. Phase 3
gates runtime on it. register is branched on in Phase 4 and accepts
anything."
```

- [ ] **Step 2: Implement**

In `src/agenticsocial/video/series.py`:

```python
REGISTERS = ("reported", "first-person")
```

In `load_series`, after the `target_sec` validation:

```python
    tolerance_sec = runtime.get("tolerance_sec", 8)
    if (
        isinstance(tolerance_sec, bool)
        or not isinstance(tolerance_sec, int)
        or tolerance_sec < 0
    ):
        raise SeriesError(
            f"{path}: [runtime] tolerance_sec must be a non-negative integer "
            "(0 means the runtime must match target_sec exactly)"
        )

    register = meta.get("register", "reported")
    if register not in REGISTERS:
        raise SeriesError(
            f"{path}: [series] register must be one of "
            f"{', '.join(REGISTERS)} — got {register!r}. "
            "Phase 4 selects voice rules from this value."
        )

    for field in ("name", "byline"):
        value = meta.get(field)
        if value is not None and not isinstance(value, str):
            raise SeriesError(
                f"{path}: [series] {field} must be a string, got "
                f"{type(value).__name__}"
            )
```

and use the locals in the `Series(...)` call: `tolerance_sec=tolerance_sec`,
`register=register`.

**Do not validate `cadence`** — spec §6 marks it advisory and nothing branches on
it. Validating it would reject a legitimate `"fortnightly"`.

For R4, `episode.py` imports the single constant rather than defining a second:

```python
from .series import MAX_NAME_LEN as MAX_ID_LEN
```

If that creates a circular import, say so and put the constant in
`workspace.py` beside `assert_safe_name`, which is where the other shared
primitive already lives.

- [ ] **Step 3: Run everything, then commit**

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/series.py src/agenticsocial/video/episode.py
git commit -m "fix: validate the series fields that gates read

tolerance_sec becomes a gate input in Phase 3 and accepted \"eight\", -1
and true. register is branched on in Phase 4 and accepted anything.
name/byline reached _toml_str untyped. One length constant, not two."
```

- [ ] **Step 4: Kill all seven mutants**, then your own sweep.

---

## Your report

`docs/superpowers/worklog/video/phase-03/task-0-report.md`:

1. **What I changed.**
2. **TDD evidence** and the **mutation score**.
3. **All seven mutant results**, plus your own sweep.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Did the shared constant need moving to `workspace.py`? Say which and why.
   - `design.*` values are still unvalidated (`accent = 5` loads). Phase 4
     interpolates them into rendered output. Is that this phase's problem or
     Phase 4's, and what breaks first if it is left?
   - Anything else a Phase 3 gate will read that nothing validates.

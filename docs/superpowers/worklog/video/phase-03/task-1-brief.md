# Task 1 Brief: `script.py` — what a beat is

**Phase:** 3 · **Branch:** `feat/video-phase-03-script-schema` · **Follows:** `1fe0a6f`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## What this builds

`script.py` owns the **schema**: what a beat is, per type, and whether a given
`script.yaml` conforms. It knows nothing about frames, formats or JSON.
`plan.py` keeps **resolution** — pace, absolute times, frame numbers, the Node
handoff — and becomes a consumer.

The split matters because **Phase 5 verifies claims**, and a claim is anchored to
a beat's `src` and `quote`. The verifier must walk beats as data without caring
how they render.

## Where the field lists come from

Spec §7.1 and **the two committed episodes that actually rendered**
(`engine/content/2026-08-12.js`, `2026-08-14.js`). A field neither the spec names
nor a committed episode uses does not go in. Read both episodes before writing
the registry — they are the only evidence of what these beats really need.

## Rules, each with its negative half

- **R1** Every beat has a `type` drawn from the catalogue. **Negative:** an
  unknown type is an error naming the known ones; a *known but not-yet-renderable*
  type is **valid** and says so separately — validation and rendering are
  different gates.
- **R2** Each type's required fields are present and correctly typed.
  **Negative:** optional fields absent is fine; present-but-wrong-typed is an
  error. Falsy-but-valid (`hold: 0` is invalid, but `sub: ""` is fine) must not
  be conflated with absent.
- **R3** Errors name the **beat index and type**. **Negative:** a message saying
  only "text is required" against a twelve-beat script is unusable.
- **R4** `kpis` and `jumpChart` **must** carry `src` and `quote` (spec §7.2 —
  "there is no path to rendering a number that isn't in a source").
  **Negative:** `title` and `signoff` assert nothing and require neither.
- **R5** `acts[]` entries in `series.toml` are validated: each needs a string
  `id`, and `beats` if present is a positive integer. **Negative:** `label` is
  optional and free-form.
- **R6** Validation never writes. **Negative:** not even to normalise — document
  2's bytes are load-bearing (D-026).

## The mutants this task must kill

Derive assertions from these before writing them. **Include falsy values in
every "wrong type" case** — Task 0's sweep survived because every bad value I
chose was truthy.

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | unknown type accepted | R1 |
| M2 | not-yet-renderable type rejected as unknown | R1 negative |
| M3 | required-field check dropped for one type | R2 |
| M4 | `if value:` instead of `if value is not None:` | R2 negative |
| M5 | error omits the beat index | R3 |
| M6 | `src`/`quote` not required on `kpis` | R4 |
| M7 | `src`/`quote` required on `title` too | R4 negative |
| M8 | `acts[]` entry shape unchecked | R5 |
| M9 | `beats = -1` accepted | R5 |
| M10 | validation rewrites `script.yaml` | R6 |

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 23 defects across five phases. Two in the last
  brief alone: a test that passed on the unfixed tree because CPython interns
  small ints, and parametrised "bad" values that were all truthy.
- Do not add dependencies. No network. Never stage anything under `docs/`.
- **Report the mutation score.**

## Interfaces

```python
class ScriptError(Exception): ...

@dataclass(frozen=True)
class Beat:
    index: int
    type: str
    hold: float
    act: str
    kicker: str
    src: str
    quote: str
    fields: dict          # the type-specific payload, already validated

@dataclass(frozen=True)
class Script:
    episode: str
    series: str
    status: str
    pace: float
    beats: tuple[Beat, ...]

RENDERABLE: frozenset[str]        # what plan.py can currently emit
BEAT_TYPES: dict[str, dict]       # the catalogue

def load_script(episode) -> Script          # parses, validates, never writes
def validate_acts(acts, where) -> None      # R5
```

`Beat`/`Script` frozen per D-062 — a snapshot that mutates lies about its file.

---

- [ ] **Step 1: Write the tests**

Create `tests/test_video_script.py`. Every test carries a `precondition:` line.

Cover, at minimum: each catalogue type validating with its documented fields; an
unknown type rejected **by name** with the known ones listed; a known-but-not-yet-
renderable type accepted by `load_script` and refused by `plan.build_plan` **with
a different message**; per-type required-field omissions; wrong-typed fields
**including falsy ones** (`text: 0`, `items: []` where non-empty is required,
`kicker: false`); an error message containing both the index and the type;
`kpis`/`jumpChart` without `src` or `quote` refused; `title`/`signoff` accepted
without either; `acts[]` with a non-string `id`, a missing `id`, `beats = "six"`,
`beats = -1`, `beats = 0`; `label` absent accepted; and a byte-identity check
that `load_script` leaves `script.yaml` unchanged.

For the two committed episodes, add a test that **every beat type they use is in
the catalogue** — they are the only real evidence of what these beats need:

```python
def test_the_catalogue_covers_the_committed_episodes():
    """precondition: engine/content/*.js are the two episodes that really
    rendered. A catalogue that cannot describe them is describing something
    else."""
    import re
    from pathlib import Path

    from agenticsocial.video import script as S

    used = set()
    for p in Path("engine/content").glob("*.js"):
        used |= set(re.findall(r"\b(kpis|jumpChart|rise|fade|draw|count)\s*\(", p.read_text()))
    # engine primitives map to beat types; assert the ones the spec names exist
    for t in ("statement", "body", "list", "kpis", "jumpChart", "quote", "title", "signoff", "custom"):
        assert t in S.BEAT_TYPES, t
```

```bash
uv run pytest tests/test_video_script.py 2>&1 | tail -12
git add tests/test_video_script.py
git commit -m "test: specify the beat catalogue, its required fields, and act shape"
```

- [ ] **Step 2: Implement**

Write `src/agenticsocial/video/script.py` from the rules above. Shape the
catalogue as data, not branches — a registry keyed by type name, each entry
declaring required and optional fields and their types, so adding a type in
Phase 4 is a table entry rather than a new `if`.

Then make `plan.py` a consumer: it calls `load_script`, and its own
`SUPPORTED_BEATS` check becomes the **renderable** gate with a message that
distinguishes it from an unknown type:

```
beat 3 (dumbbell) is a valid beat type but cannot be rendered yet —
this phase renders: statement
```

`plan.py` keeps every timing behaviour it has: scaled holds, absolute
`start`/`end`, integer frames, `script_sha256`, one read of the file. **Do not
regress those** — they are pinned by `tests/test_video_plan.py` and were four
tasks of work.

- [ ] **Step 3: Run everything, then commit**

- [ ] **Step 4: Kill all ten mutants**, then your own sweep.

---

## Your report

`docs/superpowers/worklog/video/phase-03/task-1-report.md`:

1. **What I implemented**, and where each type's fields came from — spec, a
   committed episode, or my judgement. Say which for any field you had to decide.
2. **TDD evidence** and the **mutation score**.
3. **All ten mutant results**, plus your own sweep. Include at least three
   falsy-value mutants — that class survived the last two tasks.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Which catalogue fields are *speculative* — named by neither the spec nor a
     committed episode? Those are the ones Phase 4 will find wrong.
   - Does splitting `script.py` from `plan.py` actually pay, or is it two modules
     where one belonged? Argue it.
   - Task 0 flagged that `warm_acts` may reference act ids that need not exist —
     the only cross-field invariant in `series.toml`. Worth enforcing here?

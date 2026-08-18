"""Phase 9 Task 3 mutation harness. D-118: a score with no harness is a claim.

Each mutant is one exact-string edit to a source file. A mutant is KILLED when
the suite fails with it applied, SURVIVED when the suite passes. Run with
PYTHONDONTWRITEBYTECODE=1 (D-100: consecutive mutants land inside one mtime
second and CPython reuses a stale .pyc, which produces false survivors AND
false kills).

    PYTHONDONTWRITEBYTECODE=1 python3 task-3-mutants.py

The brief's M5 — "the storyboard rule stated but with no worked example" — is
not a source edit, so it is checked here as a file assertion instead of being
left unmeasured.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/aabdukarim/Documents/Code/agenticsocial")
V = ROOT / "src/agenticsocial/video/verify.py"
C = ROOT / "src/agenticsocial/video/cli.py"
STORYBOARD = ROOT / "skills/storyboard/SKILL.md"

# (id, what a weaker implementation would do, file, find, replace)
MUTANTS = [
    # --- R1: a summary count never disagrees with the table beneath it ---
    ("T1", "M1 — `_counts` reports pass 1's verdicts", C,
     '        word = binding_verdict(record)',
     '        word = _verdict(record)'),
    ("T2", "M2 — the head line is converted, the table is left behind", C,
     '    return binding_verdict(record) + ("*" if _written(record) else "")',
     '    return _verdict(record) + ("*" if _written(record) else "")'),
    ("T3", "M2, the other half — the table is converted, the head line is not", C,
     '''            f"beat {record.get('beat_index')} · {binding}"
            + ("" if binding == measured else f" · pass 1 {measured}")''',
     '''            f"beat {record.get('beat_index')} · {measured}"'''),
    ("T4", "M3 — summary and table kept in sync by two code paths", C,
     '''    tally: dict[str, int] = {}
    for record in records:
        word = binding_verdict(record)''',
     '''    tally: dict[str, int] = {}
    for record in records:
        _state, _ = adversarial_state(record)
        word = _verdict(record) if _state in ("unjudged", "supported") else _state'''),
    ("T5", "the binding verdict is always the measurement", V,
     '''    state, _ = adversarial_state(record)
    if state in ("unjudged", "supported"):
        return str((record.get("mechanical") or {}).get("verdict") or "?")
    return state''',
     '''    return str((record.get("mechanical") or {}).get("verdict") or "?")'''),
    ("T6", "R1's positive half: a `supported` claim reads `supported`, not `pass`", V,
     '    if state in ("unjudged", "supported"):',
     '    if state in ("unjudged",):'),
    ("T7", "a stale or expired judgement quietly restores `pass`", V,
     '    if state in ("unjudged", "supported"):',
     '    if state in ("unjudged", "supported", "stale", "expired", "malformed"):'),

    # --- R3: a refutation reaches the ledger byte-exact ---
    ("T8", "M4 — the CLI sanitises the prose it was handed", C,
     '        return _text(text, label)',
     '        return _text(text.replace("$", ""), label)'),
    ("T9", "M4 — the file is read, then the inline argument silently wins", C,
     '''    if inline is not None and path is not None:
        raise _fail(''',
     '''    if False:
        raise _fail('''),
    ("T10", "an unreadable refutation file is a traceback, not a refusal", C,
     '''        except OSError as e:
            raise _fail(f"cannot read {path}: {e}")''',
     '''        except UnicodeError as e:
            raise _fail(f"cannot read {path}: {e}")'''),
    ("T11", "a verdict with no refutation at all is accepted", C,
     '''    if refutation is None:
        raise _fail(''',
     '''    if False:
        raise _fail('''),
    ("T12", "the lost-magnitude note never fires", C,
     '''    found = _LOST_MAGNITUDE.search(text)
    if found is None:
        return''',
     '''    found = _LOST_MAGNITUDE.search(text)
    if found is None or True:
        return'''),
    ("T13", "the note fires on every refutation, so nobody reads it", C,
     r'_LOST_MAGNITUDE = re.compile(r"(?<![\w.])(\.\d[\d,]*)")',
     r'_LOST_MAGNITUDE = re.compile(r"(\.\d[\d,]*)")'),
    ("T14", "the note is printed for prose that came out of a file", C,
     '''    if refutation_file is None:
        _echo_lost_magnitude(''',
     '''    if True:
        _echo_lost_magnitude('''),
]

CMD = ["uv", "run", "pytest", "-x", "-q", "--no-header", "-p", "no:randomly"]


def run_suite():
    return subprocess.run(
        CMD, cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def skill_checks():
    """M5: the rule without a worked example is the mutant, so assert the work.

    Not a source edit and therefore not scoreable by the suite — but leaving it
    unmeasured is how a table of five mutants reports four.
    """
    text = STORYBOARD.read_text(encoding="utf-8")
    checks = [
        ("the rule is in the hard rules", "names its subject in its own text" in text),
        ("the rule has its own step", "### 4.5" in text),
        ("`title` and `signoff` are exempt", "assert nothing, so they are exempt" in text),
        ("a before/after is shown", "# before" in text and "# after" in text),
    ] + [
        (f"{cid} is worked through", f"`{cid}`" in text)
        for cid in ("c-005", "c-007", "c-010", "c-019")
    ]
    for what, ok in checks:
        print(f"  M5    {'ok      ' if ok else 'MISSING '} {what}")
    return all(ok for _, ok in checks)


def main():
    baseline = run_suite()
    print(f"baseline: {'PASS' if baseline.returncode == 0 else 'FAIL'} "
          f"({baseline.stdout.strip().splitlines()[-1]})")
    if baseline.returncode != 0:
        sys.exit("baseline is not green; a sweep on a red tree measures nothing")

    killed, survived = [], []
    for name, what, path, find, replace in MUTANTS:
        original = path.read_text(encoding="utf-8")
        if original.count(find) != 1:
            sys.exit(f"{name}: anchor matches {original.count(find)} times — "
                     "a mutant that does not apply is not a measurement")
        path.write_text(original.replace(find, replace), encoding="utf-8")
        try:
            result = run_suite()
        finally:
            path.write_text(original, encoding="utf-8")
        tail = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "?"
        if result.returncode == 0:
            survived.append((name, what))
            print(f"  {name:<5} SURVIVED  {what}")
        else:
            killed.append(name)
            print(f"  {name:<5} killed    {what}  [{tail}]")
    print(f"\n{len(killed)} killed, {len(survived)} survived, {len(MUTANTS)} total")
    for name, what in survived:
        print(f"SURVIVOR {name}: {what}")
    print("\nM5 — the storyboard rule, checked as a file rather than a mutant:")
    print("M5 " + ("ok" if skill_checks() else "INCOMPLETE"))


if __name__ == "__main__":
    main()

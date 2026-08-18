"""Phase 9 Task 1 mutation harness. D-118: a score with no harness is a claim.

Each mutant is one exact-string edit to a source file. A mutant is KILLED when
the suite fails with it applied, SURVIVED when the suite passes. Run with
PYTHONDONTWRITEBYTECODE=1 (D-100: consecutive mutants land inside one mtime
second and CPython reuses a stale .pyc, which produces false survivors AND
false kills).

    PYTHONDONTWRITEBYTECODE=1 python3 mutants.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/aabdukarim/Documents/Code/agenticsocial")
V = ROOT / "src/agenticsocial/video/verify.py"
C = ROOT / "src/agenticsocial/video/cli.py"
A = ROOT / "src/agenticsocial/video/approve.py"

# (id, what a weaker implementation would do, file, find, replace)
MUTANTS = [
    ("M1", "`refuted` approves", V,
     'return adversarial_state(record)[0] in ("unjudged", "supported")',
     'return adversarial_state(record)[0] in ("unjudged", "supported", "refuted")'),
    ("M2", "`unsupported` approves", V,
     'return adversarial_state(record)[0] in ("unjudged", "supported")',
     'return adversarial_state(record)[0] in ("unjudged", "supported", "unsupported")'),
    ("M3", "pass-2 refusal prints pass 1's remedy", C,
     '    state, _ = adversarial_state(record)\n    if state in ("refuted", "unsupported"):',
     '    state, _ = adversarial_state(record)\n    if False:'),
    ("M3b", "the pass-2 `why` line is dropped from the refusal", C,
     '        if _pass2_why(record):\n            typer.echo(_detail("pass 2", _pass2_why(record)))\n        typer.echo(_detail("fix", _next_step(record)))',
     '        typer.echo(_detail("fix", _next_step(record)))'),
    ("M3c", "review's table shows the verdict that passed, not the one that binds", C,
     '''    state, _ = adversarial_state(record)
    binding = _verdict(record) if state in ("unjudged", "supported") else state
    return binding''',
     '''    return _verdict(record)'''),
    ("M4", "`supported` blocks", V,
     'return adversarial_state(record)[0] in ("unjudged", "supported")',
     'return adversarial_state(record)[0] in ("unjudged",)'),
    ("M5", "`residual_risk` shown only on failures", C,
     '        if judged["residual_risk"]:',
     '        if judged["residual_risk"] and judged["state"] != "supported":'),
    ("M6", "a missing `residual_risk` is an error", V,
     '    risk = block.get("residual_risk")\n    if risk is not None and not isinstance(risk, str):',
     '    risk = block.get("residual_risk")\n    if not isinstance(risk, str):'),
    ("M7", "an unknown verdict is treated as supported", V,
     '''    if verdict not in ADVERSARIAL_VERDICTS:
        return "malformed", (''',
     '''    if verdict not in ADVERSARIAL_VERDICTS:
        return "supported", "" if True else ('''),
    ("M8", '"not yet judged" collapses into "judged and open"', V,
     '''    if block is None:
        return "unjudged", ""''',
     '''    if block is None:
        return "malformed", "no adversarial block"'''),
    ("M9", "a second verdict path: the screen reads the field itself", C,
     '''    state, _ = adversarial_state(record)
    return "" if state == "unjudged" else f" · pass 2 {state}"''',
     '''    block = record.get("adversarial") or {}
    state = block.get("verdict")
    return "" if not state else f" · pass 2 {state}"'''),
    ("M10a", "a verdict is carried forward without checking the binding", V,
     '        if isinstance(block, dict) and block.get("claim_sha256") == digest:',
     '        if isinstance(block, dict):'),
    ("M10b", "the gate does not re-check the binding", V,
     '    if block.get("claim_sha256") != claim_sha256(record):',
     '    if False:'),
    ("M11a", "`attempted_refutation` may be empty at the gate", V,
     '    if not isinstance(refutation, str) or not refutation.strip():\n        return "malformed", (',
     '    if False:\n        return "malformed", ('),
    ("M11b", "`attempted_refutation` may be empty at the writer", V,
     '    if not isinstance(attempted_refutation, str) or not attempted_refutation.strip():',
     '    if False:'),
    ("M12a", "`reproducible` is not required in the record", V,
     '    if block.get("reproducible") is not False:',
     '    if False:'),
    ("M12b", "a pass-2 verdict never expires", V,
     '    if age > PASS2_HORIZON_DAYS:',
     '    if False:'),
    ("M12c", "the ledger stores no honesty flag at all", V,
     '        "reproducible": False,\n    }\n    record["adversarial"] = block',
     '    }\n    record["adversarial"] = block'),
    ("M12d", "the approval record says nothing about pass 2", A,
     '        "adversarial": verify_mod.pass2_tally(records),',
     ''),
    # --- the implementer's own sweep ---
    ("S1", "expiry is checked BEFORE the verdict, so an old refutation reads `expired`", V,
     '''    if verdict != "supported":''',
     '''    if verdict != "supported" and (
        datetime.now().astimezone() - judged_at
    ).days <= PASS2_HORIZON_DAYS:'''),
    ("S2", "an unreadable `judged_at` is treated as fresh", V,
     '''    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None''',
     '''    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now().astimezone()'''),
    ("S3", "the writer accepts a stale ledger", V,
     '''    stale = stale_reason(episode, ledger)
    if stale:''',
     '''    stale = stale_reason(episode, ledger)
    if False:'''),
    ("S4", "the writer judges a claim pass 1 refused", V,
     '    if (record.get("mechanical") or {}).get("verdict") != "pass":',
     '    if False:'),
    ("S5", "an unknown claim id is silently dropped", V,
     '''    if record is None:
        raise VerifyError(''',
     '''    if record is None:
        return {} if True else VerifyError('''),
    ("S6", "the writer needs no author", V,
     '    if not (by or "").strip():',
     '    if False:'),
    ("S7", "a judgement with no author passes the gate", V,
     '    if not isinstance(block.get("judged_by"), str) or not block["judged_by"].strip():',
     '    if False:'),
    ("S8", "§8.4's override cannot clear a pass-2 refusal", V,
     '        return "overridden" if override_state(record)[0] is not None else "open"\n    mechanical',
     '        return "open"\n    mechanical'),
    ("S9", "the coverage banner is silent when pass 2 judged nothing", C,
     '''    tally = verify_mod.pass2_tally(records)
    typer.echo(''',
     '''    tally = verify_mod.pass2_tally(records)
    if tally["judged"] == 0:
        return
    typer.echo('''),
    ("S10", "a malformed block still has its risk quoted", V,
     '    if state in ("unjudged", "malformed"):\n        return None',
     '    if state in ("unjudged",):\n        return None'),
    ("S11", "every re-check throws all pass-2 work away", V,
     '        fresh["adversarial"] = _carry_forward(fresh, previous)',
     '        fresh["adversarial"] = None'),
    ("S12", "the binding covers the beat text only", V,
     '''    identity = [
        record.get("id"),
        record.get("beat_index"),
        record.get("text"),
        record.get("src"),
        record.get("quote"),
    ]''',
     '''    identity = [record.get("text")]'''),
    ("S13", "the claim row shows pass 1 only", C,
     '        f"{_verdict(record)}{_pass2_mark(record)}"',
     '        f"{_verdict(record)}"'),
    ("S14", "recording a verdict restamps the pass-1 check", V,
     '''    record["adversarial"] = block
    write_ledger(episode, ledger)''',
     '''    record["adversarial"] = block
    ledger["checked_at"] = datetime.now().astimezone().isoformat(timespec="microseconds")
    write_ledger(episode, ledger)'''),
    ("S15", "the writer accepts any verdict string", V,
     '    if verdict not in ADVERSARIAL_VERDICTS:\n        raise VerifyError(',
     '    if False:\n        raise VerifyError('),
    ("S16", "`review` never prints the pass-2 block", C,
     '        _print_pass2(verify_mod.claim_records(ledger))',
     '        pass'),
]

CMD = ["uv", "run", "pytest", "-x", "-q", "--no-header", "-p", "no:randomly"]


def run_suite():
    return subprocess.run(
        CMD, cwd=ROOT, capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


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
            first = next((line for line in result.stdout.splitlines()
                          if line.startswith("FAILED") or "::" in line and "F" in line), "")
            print(f"  {name:<5} killed    {what}  [{tail}]")
    print(f"\n{len(killed)} killed, {len(survived)} survived, {len(MUTANTS)} total")
    for name, what in survived:
        print(f"SURVIVOR {name}: {what}")


if __name__ == "__main__":
    main()

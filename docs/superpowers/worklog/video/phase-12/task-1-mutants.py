"""Phase 12 Task 1 mutation harness. D-118: a score with no harness is a claim.

Each mutant is one exact-string edit to a source file. A mutant is KILLED when
the suite fails with it applied, SURVIVED when the suite passes. The harness
refuses to run if an anchor does not match exactly once — a mutant that does not
apply is not a measurement.

Run with PYTHONDONTWRITEBYTECODE=1 (D-100: consecutive mutants land inside one
mtime second and CPython reuses a stale .pyc, which produces false survivors AND
false kills):

    PYTHONDONTWRITEBYTECODE=1 python3 docs/superpowers/worklog/video/phase-12/task-1-mutants.py

M1-M10 are the Phase 12 brief's own mutant table. S* are this task's own sweep.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/aabdukarim/Documents/Code/agenticsocial")
K = ROOT / "src/agenticsocial/video/console.py"
C = ROOT / "src/agenticsocial/video/cli.py"

# (id, what a weaker implementation would do, file, find, replace)
MUTANTS = [
    # --- M1: any external request ---------------------------------------------------
    ("M1a", "a remote favicon", K,
     "'<link rel=\"icon\" href=\"data:,\">'",
     "'<link rel=\"icon\" href=\"https://example.com/favicon.ico\">'"),
    ("M1b", "a webfont imported from the stylesheet", K,
     'STYLE = """\n:root {',
     'STYLE = """\n@import url("https://fonts.example/inter.css");\n:root {'),
    ("M1c", "the CSP is dropped from the page", K,
     "'<meta http-equiv=\"Content-Security-Policy\" content=\"default-src '",
     "'<meta name=\"generator\" content=\"x\"><!--default-src '"),
    ("M1d", "the CSP permits inline script", K,
     "\"'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; \"",
     "\"'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; \"\n        \"img-src data:; base-uri 'none'; \""),

    # --- M2: the highlight computed by searching the folded text --------------------
    ("M2", "the highlight is found by searching the folded text", K,
     '    span = record.get("quote_span")\n'
     '    if isinstance(span, (list, tuple)) and len(span) == 2:',
     '    needle = verify_mod._needle(record.get("quote") or "")\n'
     '    folded, _ = verify_mod.fold_spans(document)\n'
     '    at = folded.find(needle) if needle else -1\n'
     '    span = None if at < 0 else [at, at + len(needle)]\n'
     '    if isinstance(span, (list, tuple)) and len(span) == 2:'),
    ("M2b", "the marked text is tidied before it is shown", K,
     '<mark class="{mark_class}">{esc(document[at:to])}</mark>',
     '<mark class="{mark_class}">{esc(document[at:to].strip())}</mark>'),
    ("M2c", "the near miss is shown as the supporting quote", K,
     '    span = record.get("quote_span")\n',
     '    span = None\n'),

    # --- M3: the quote with no surrounding source -----------------------------------
    ("M3", "the quote is shown with no context around it", K,
     "    lo, hi = max(0, at - CONTEXT), min(len(document), to + CONTEXT)",
     "    lo, hi = at, to"),
    ("M3b", "only a few characters of context", K,
     "CONTEXT = 320",
     "CONTEXT = 0"),

    # --- M4: a verdict word re-derived in the template -------------------------------
    ("M4a", "the claim's word is read from the mechanical block", K,
     "    verdict = binding_verdict(record)\n    state = classify(record)",
     '    verdict = (record.get("mechanical") or {}).get("verdict")\n'
     "    state = classify(record)"),
    ("M4b", "the gate state is re-derived from the verdict", K,
     "    verdict = binding_verdict(record)\n    state = classify(record)",
     "    verdict = binding_verdict(record)\n"
     '    state = "verified" if verdict == "pass" else "open"'),
    ("M4c", "the beat-list cell shows the measurement", K,
     "            verdict = binding_verdict(record)\n",
     '            verdict = (record.get("mechanical") or {}).get("verdict")\n'),
    ("M4d", "pass 1's word loses its label", K,
     '    return _row("pass 1", f\'<span class="measured">{word}</span>{tail}\')',
     '    return _row("verdict", f\'<span class="measured">{word}</span>{tail}\')'),

    # --- M5: `manual` rendered as verified ------------------------------------------
    ("M5a", "an attested claim is labelled verified", K,
     '<span class="state state-{_slug(state)}">{esc(state)}</span>',
     '<span class="state state-{_slug(state)}">'
     '{esc("verified" if state == "attested" else state)}</span>'),
    ("M5b", "the attestation sentence is not shown", K,
     '    attest = str((record.get("mechanical") or {}).get("attest") or "").strip()\n'
     '    if state != "attested":\n        return ""',
     '    attest = str((record.get("mechanical") or {}).get("attest") or "").strip()\n'
     "    if True:\n        return \"\""),
    ("M5c", "attested drops the NOT verified caveat", K,
     "machine checked this (D-088), NOT verified. You are approving the ",
     "machine checked this (D-088). You are approving the "),

    # --- M6: pass 2 styled and worded as a measurement -------------------------------
    ("M6a", "the judgement is presented as a measurement", K,
     "· a judgement by an agent, NOT a '",
     "· checked by pass 2 '"),
    ("M6b", "the judgement block is styled like every other row", K,
     "        '<div class=\"judged\">',",
     "        '<div class=\"row\">',"),
    ("M6c", "the judgement's author and expiry are dropped", K,
     '        _row(\n            "judged by",',
     '        _row(\n            "note",'),

    # --- M7: `residual_risk` hidden on `supported` ----------------------------------
    ("M7a", "the risk is shown only where the judgement refuses", K,
     '    if judged["residual_risk"]:',
     '    if judged["residual_risk"] and why:'),
    ("M7b", "the risk is never shown", K,
     '        parts.append(\n            _row("residual risk", esc(judged["residual_risk"]), cls="risk")\n        )',
     "        pass"),

    # --- M8: a stale ledger rendered as current --------------------------------------
    ("M8a", "a stale ledger shows its verdicts anyway", K,
     "    if stale:\n        return [], _banner(",
     "    if False:\n        return [], _banner("),
    ("M8b", "the staleness banner stops shouting", K,
     "<strong>claims.json is STALE</strong>",
     "<span>claims.json was written earlier</span>"),
    ("M8c", "staleness is decided here rather than by `stale_reason`", K,
     "    stale = verify_mod.stale_reason(episode, ledger)",
     "    stale = None if ledger else \"no claims.json\""),

    # --- M9: the console writes into the episode ------------------------------------
    ("M9a", "any --out is accepted, including inside the episode", C,
     "    if resolved == root or root in resolved.parents:",
     "    if False:"),
    ("M9b", "the default lands beside the script", C,
     '        Path(tempfile.gettempdir()) / "agsoc-console" / f"{s.slug}-{ep.id}.html"',
     '        ep.dir / "console.html"'),
    ("M9c", "the guard compares unresolved paths", C,
     "    resolved = target.resolve()\n    root = ws.root.resolve()",
     "    resolved = target\n    root = ws.root"),

    # --- M10: an approve action of any kind -----------------------------------------
    ("M10a", "a button appears beside the command", K,
     '"approve: the gate is a command you run yourself, and it re-reads every "',
     '"approve: <button>approve this episode</button> or run "'),
    ("M10b", "an event handler reaches the page", K,
     '<article class="claim claim-{_slug(state)}" ',
     '<article onclick="approve()" class="claim claim-{_slug(state)}" '),

    # --- this task's own sweep --------------------------------------------------------
    ("S1", "nothing is escaped", K,
     "    return _escape(str(value), quote=True)",
     "    return str(value)"),
    ("S2", "the near miss is labelled as the quote", K,
     '        else \'<span class="tag tag-near">quote NOT FOUND — this is the closest \'',
     '        else \'<span class="tag tag-quote">supporting quote \''),
    ("S3", "the open count is dropped from the header", K,
     "    if open_count:",
     "    if False:"),
    ("S4", "pass-2 coverage is only reported when pass 2 ran", K,
     '    return (\n        f\'<p class="tally pass2">pass 2 · {tally["judged"]} of \'',
     '    if not tally["judged"]:\n        return ""\n    return (\n'
     '        f\'<p class="tally pass2">pass 2 · {tally["judged"]} of \''),
    ("S5", "screen D opens only the claims the gate refuses", K,
     """    return (
        verify_mod.is_blocking(record)
        or written is not None
        or fault is not None
        or classify(record) == "attested"
        or judgement(record) is not None
    )""",
     "    return verify_mod.is_blocking(record)"),
    ("S6", "the override diff loses its diff", K,
     '        "<ins>+   claim_override:\\n</ins>"',
     '        "    claim_override:\\n"'),
    ("S7", "the override is presented as a small formality", K,
     '        \'<div class="diff-wrap"><p class="diff-head">To override this claim you \'',
     '        \'<div class="diff-wrap"><p class="diff-head">Override: \''),
    ("S8", "the refuter's reasoning is not shown", K,
     '        _row("attacked", esc(judged["attempted_refutation"])),',
     "        \"\","),
    ("S9", "beats are not grouped by act", K,
     "        if beat.act != act:",
     "        if act is not None and False:"),
    ("S10", "an unrecorded render is not mentioned", K,
     "    if any(entry.get(\"date\") == episode.id for entry in ledger[\"episodes\"]):\n        return \"\"",
     "    if True:\n        return \"\""),
    ("S11", "a probe frame is linked rather than embedded", K,
     '            body = f\'<img alt="{esc(frame.name)}" src="data:image/png;base64,{data}">\'',
     '            body = f\'<img alt="{esc(frame.name)}" src="{frame}">\''),
    ("S12", "with no frames the page says nothing about looking", K,
     '            "at a pixel — the approval covers the beats, the pace and the "\n'
     '            "design, and never this machine\'s fonts or Chromium (D-116). Draw "',
     '            "at a pixel. Draw "'),
    ("S13", "the approve command is not printed", K,
     '        f"<code>agsoc video approve {esc(episode.id)} --series "',
     '        f"<code>agsoc video ready {esc(episode.id)} --series "'),
    ("S14", "the drift banner is silent", K,
     "    drift = approve_mod.approval_drift(episode)",
     "    drift = None"),
    ("S15", "an unparseable script still produces a page", C,
     "        html = console_mod.build(s, ep)",
     "        try:\n            html = console_mod.build(s, ep)\n"
     "        except Exception:\n            html = \"<!doctype html>\\n<html></html>\""),
    ("S17", "the fix line is printed on claims that are not open", K,
     "            if verify_mod.is_blocking(record)\n            else \"\",",
     "            if True\n            else \"\","),
    ("S16", "the runtime is reported without the target", K,
     "f\"runtime {check.total_sec:.1f}s · target {check.target_sec}s ± \"",
     "f\"runtime {check.total_sec:.1f}s · \""),
]

CMD = ["uv", "run", "pytest", "-x", "-q", "--no-header"]


def run_suite():
    return subprocess.run(
        CMD, cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def main():
    baseline = run_suite()
    print(f"baseline: {'PASS' if baseline.returncode == 0 else 'FAIL'} "
          f"({baseline.stdout.strip().splitlines()[-1]})")
    if baseline.returncode != 0:
        sys.exit("baseline is not green; a sweep on a red tree measures nothing")

    for name, _what, path, find, _replace in MUTANTS:
        count = path.read_text(encoding="utf-8").count(find)
        if count != 1:
            sys.exit(f"{name}: anchor matches {count} times — a mutant that "
                     "does not apply is not a measurement")

    killed, survived = [], []
    for name, what, path, find, replace in MUTANTS:
        original = path.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    main()

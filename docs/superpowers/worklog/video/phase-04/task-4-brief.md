# Task 4 Brief: The render page must not be able to reach the network

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Follows:** `ca73d0c`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Small, and the last thing before the phase gate.

## Why

Task 3 asked what a `custom` beat can actually do and answered honestly. I
verified the sharpest parts:

```
outbound requests from a custom beat: [ 'https://example.com/exfil?x=The%20Brief' ]
can it reassign the escaper?  true
is __seek writable?           true
```

**The request left the browser carrying page data.** And a custom beat can
reassign `escapeHTML` — so it can reintroduce the exact divergence Task 1 closed,
*after* validation has passed, from inside a `script.yaml`.

**The threat chain is not hypothetical for this product.** Spec §1: the agent
drafts from fetched sources. So: hostile text in a source → the corpus →
the storyboard skill reads it → it writes a `custom` beat → that beat executes
with network access on the operator's machine. Every link already exists.

## What this task does, and what it explicitly does not

**Does:** stop the render page reaching the network, with a Content-Security-Policy
in `scene.html`. That closes exfiltration — the half that leaves the machine.

**Does not:** sandbox `custom`. It will still read and write `window`, mutate
other beats' DOM, and reassign engine functions. Task 3's assessment stands and
the report must repeat it rather than imply the problem is solved. **A CSP is a
network boundary, not an execution boundary.**

The honest framing, same as D-062's on freezing: this raises the floor
substantially and is not a wall. The real control for `custom` remains `attest`
plus a human reading it.

## Rules, each with its negative half

- **R1** The render page cannot open a network connection. **Negative:** it must
  still load its own local scripts — `engine.js`, `planbuild.js`, `.plan.js`,
  `content/*.js` — and render both committed episodes unchanged.
- **R2** The policy is enforced by the page, not by the runner. **Negative:** not
  a Playwright route-blocker — `scene.html` is opened directly in a browser to
  scrub the slider, and that path must be protected too.
- **R3** A blocked attempt is **visible**. **Negative:** it must not fail the
  render silently; `render.mjs` already collects `pageerror`, and a CSP violation
  should surface somewhere a person will see.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | CSP removed | R1 |
| M2 | CSP present but `connect-src` permissive | R1 |
| M3 | CSP so strict the local scripts fail to load | R1 negative |
| M4 | blocking done in `render.mjs` instead of the page | R2 |
| M5 | violations swallowed with no signal | R3 |

## Ground rules

- **Two commits.** Test first, then the policy. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- No new dependencies.
- **Both committed episodes must still render** — `--day 2026-08-14 --probe` and
  `--day 2026-08-12 --probe` — and `determinism.test.mjs` must stay green. A CSP
  that breaks the engine is worse than no CSP.
- **Report the mutation score.**

---

- [ ] **Step 1** — a test that fires `fetch`, `XMLHttpRequest` and an
      `<img src="https://…">` from inside a custom beat and asserts **no request
      leaves the page**, using Playwright's request event as the oracle. It must
      fail before the policy exists. Also assert the beat still renders its
      visible content, so M3 cannot pass.

- [ ] **Step 2** — the policy in `scene.html`. Start from
      `default-src 'self'; connect-src 'none'` and widen only as far as the
      engine actually needs. `img-src` and `style-src` will need `'unsafe-inline'`
      or `data:` — **determine that by running, not by guessing**, and say in the
      report exactly which directives you had to loosen and why.

- [ ] **Step 3** — both probes, the determinism test, and the mutants.

---

## Your report

`docs/superpowers/worklog/video/phase-04/task-4-report.md`:

1. **The final policy**, directive by directive, with why each is as loose as it
   is. A CSP nobody can explain is one nobody will maintain.
2. **Evidence no request escapes** — the three vectors, measured.
3. **Both probe runs and the determinism output.**
4. **Mutation results.**
5. **Issues or concerns**, including:
   - What can a `custom` beat still do after this? Repeat it plainly — the
     network half being closed must not read as the problem being solved.
   - Does the CSP hold when `scene.html` is opened directly from the filesystem,
     as an operator scrubbing the slider would?
   - Is there any remaining path out — `<iframe>`, dynamic `import()`,
     `navigator.sendBeacon`, WebSocket, `<link rel=prefetch>`? Test them rather
     than reasoning about them.

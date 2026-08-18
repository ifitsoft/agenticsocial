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
 * `text` (bold via `**`); D-080 adds `*accent*` for `<em>`, which scene.html
 * styles as colour rather than italics — "a second emphasis that speaks in
 * colour rather than weight, used exactly where each episode pivots". Those two
 * markers are the whole vocabulary. A script.yaml is written by an agent
 * against a source, so its markup surface has to be something this file grants,
 * not something Chromium happens to accept.
 *
 * The ORDER is the trick, and it only works one way round: escape first, then
 * make the tag. Convert `**` first and the escape pass eats the `<b>` you just
 * built, so the reader sees the tag as literal text. `**` before `*` for the
 * same reason in miniature: a single-asterisk pass run first would take the
 * first `*` of every `**` opener and emphasise from there.
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
  return escapeHTML(t)
    .replace(/\*\*([\s\S]+?)\*\*/g, '<b>$1</b>')
    .replace(/\*([\s\S]+?)\*/g, '<em>$1</em>');
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

/* ===================== the two strictly verifiable types =====================
 *
 * Spec §7.2: "there is no path to rendering a number that isn't in a source."
 *
 * Everything above is presentation. These two carry figures a viewer will
 * believe, and the rules below are what make that belief earned. All of them
 * are checked EAGERLY — while buildFromPlan walks the beats, not inside the
 * closure seek() calls. A throw from inside a build closure fires at the frame
 * that scene first appears on, and render.mjs only inspects page errors after
 * goto (which is seek(0)) and again at the end: a bad beat 14 would be reported
 * after nine hundred frames had already been written.
 */

/* R1. The schema refuses an uncited chart too, and that is not sufficient: a
 * plan can reach the page without passing through Python at all. render.mjs
 * --plan reads any JSON file, and determinism.test.mjs writes its own .plan.js.
 * Blank is not a citation — `src: ""` satisfies every "is the key there" check
 * and cites nothing. */
function requireCitation(b) {
  var missing = [];
  for (var i = 0; i < 2; i++) {
    var k = ['src', 'quote'][i];
    if (typeof b[k] !== 'string' || !b[k].trim()) missing.push('`' + k + '`');
  }
  if (missing.length) {
    throw new Error(
      'a ' + b.type + ' beat has no ' + missing.join(' and ') +
        ' — it renders numbers, and spec §7.2 allows no path to rendering a ' +
        'number that is not in a source',
    );
  }
}

/* R1, Task 3 — a beat whose value animation cannot finish inside its hold.
 *
 * Verified on the real renderer: a three-row kpis stack at a 2-second hold ends
 * its LAST rendered frame on 40% for an authored 50%. The third row starts
 * counting at 1.59s and takes 1.35s; the beat is over at 2.0s.
 *
 * D-083 allowed mid-count frames on the grounds that such a value is unstable,
 * bounded and derived — a viewer sees it move, it never exceeds the authored
 * figure, and the next frame corrects it. All three properties fail at the end
 * of a beat: nothing follows to correct it, so the mid-count value IS the
 * terminal value. If the beat is the last one, it is the number the video ends
 * on. That is a figure in no source, no quote and no plan, which is exactly
 * what requireExactAtDecimals refuses — arrived at through the clock instead of
 * through rounding.
 *
 * This is the renderer's business and nowhere else's: script.py knows the hold
 * and nothing about `.62`, and engine.js knows `.62` and nothing about the
 * hold. Only this file sees both.
 *
 * The two entrance offsets below are this file's own — buildKpis and
 * buildJumpChart pass them as `d0` — so they are named here and used in both
 * places. Everything after `d0` is engine.js's, read from its constants rather
 * than retyped: two copies of `.62` agree right up until somebody retimes the
 * stack, and then this check passes beats that end mid-count again while still
 * reporting ok.
 */
var KPI_D0 = 0.35;
var JUMP_D0 = 0.3;

function round3(n) {
  /* plan.json's holds are rounded to 3dp by plan.py, and a requirement of
   * 2.9400000000000004 would refuse the hold an operator typed after reading
   * the error. */
  return Math.round(n * 1000) / 1000;
}

/* The seconds this beat's value animation needs, or 0 if nothing counts.
 *
 * Not "how long the beat's animations run" — the footnote fade and the act chip
 * are decoration, and a card whose footnote is still arriving at the cut is a
 * pacing choice. This is only about animations whose END STATE is a figure the
 * viewer will read off the screen.
 */
function requiredHold(b) {
  if (b.type === 'kpis') {
    /* The LAST item that actually counts, not the last item. `kpis()` only
     * calls count() for a numeric value; a trailing string is printed verbatim
     * at p>0 and has nothing to finish. Staggering from items.length would
     * demand time for an animation that does not exist. */
    var items = b.items || [];
    var last = -1;
    for (var i = 0; i < items.length; i++) {
      if (typeof items[i].value === 'number') last = i;
    }
    if (last < 0) return 0;
    return round3(KPI_D0 + last * KPI_STAGGER + KPI_COUNT_DUR);
  }
  if (b.type === 'jumpChart') {
    /* jumpChart staggers differently and counts differently: no digit changes,
     * but the gain segment and the `to` dot are positioned at
     * `from + (to - from) * p`, so an unfinished bar sits at a value between
     * the two — beside a `shown` cell that states the finished one. The frame
     * contradicts its own label. */
    var rows = b.rows || [];
    if (!rows.length) return 0;
    return round3(JUMP_D0 + (rows.length - 1) * JUMP_STAGGER + JUMP_GROW_D0 + JUMP_GROW_DUR);
  }
  if (b.type === 'dumbbell') {
    /* Only the rows that SEPARATE. A merged marker is placed at its position
     * and revealed — scale and opacity, no travel — so there is nothing it can
     * fail to finish. A separating row animates one marker out of the other,
     * and cut off early it draws a gap narrower than the one authored: on a
     * chart that encodes direction only, the width of that gap is the whole
     * claim, and a half-drawn one reads as "on par" on a row that is not. */
    var gaps = dumbbellGaps(planDumbbellRows(b));
    if (!gaps.length) return 0;
    return round3(
      DUMB_D0 + gaps[gaps.length - 1] * DUMB_STAGGER + DUMB_MOVE_D0 + DUMB_MOVE_DUR,
    );
  }
  return 0;
}

function requireCountFitsHold(b, index) {
  var needed = requiredHold(b);
  if (!needed) return;
  var hold = typeof b.hold === 'number' ? b.hold : 0;
  if (hold >= needed) return; /* inclusive: see the report on the quint tail */
  throw new Error(
    'beat ' + index + ' (' + b.type + ') holds ' + hold + 's, but its value ' +
      'animation is still running at ' + needed + 's — the last frame of the ' +
      'beat would freeze a mid-count figure that is in no source, no quote and ' +
      'no plan. Give it a hold of ' + needed + 's or more, or fewer rows',
  );
}

/* R2, and the heart of this file.
 *
 * count() formats with `decimals ? v.toFixed(decimals) : Math.round(v)`. So
 * `value: 0.756, decimals: 1` puts 0.8 on the screen — a figure in no source,
 * in no quote and in no plan. Phase 5 would verify 0.756 against the quote,
 * pass, and ship a video showing a number nobody checked. Display rounding is a
 * number-inventing machine.
 *
 * `decimals` is optional and its absence is NOT "print it as written": absent
 * takes the Math.round branch, so it is checked as 0. That is where the hole is
 * widest — `value: 0.75` with no `decimals` reaches the frame as `1`.
 *
 * The NEGATIVE half is just as load-bearing: a prefix, a suffix and a thousands
 * separator change how a value READS, not what it IS. `$0.75` is 0.75. Refusing
 * those would be the same mistake pointed the other way.
 */
function requireExactAtDecimals(value, decimals) {
  if (Number(value.toFixed(decimals)) !== value) {
    throw new Error(
      'kpi value ' + value + ' would reach the frame as ' +
        value.toFixed(decimals) + ' at decimals ' + decimals +
        ' — display rounding invents a figure that is in no source, no quote ' +
        'and no plan; write the number you want on screen',
    );
  }
}

function planKpiItems(b) {
  var out = [];
  var items = b.items || [];
  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    /* typeof, not `||`: `prefix: ""` and an absent prefix are the same thing
     * here, but `value: 0` is a legitimate headline figure — "0 seconds of
     * downtime" — and `it.value || ''` would erase it. */
    var prefix = typeof it.prefix === 'string' ? it.prefix : '';
    var unit = typeof it.unit === 'string' ? it.unit : '';
    if (typeof it.value === 'number') {
      var decimals = typeof it.decimals === 'number' ? it.decimals : 0;
      requireExactAtDecimals(it.value, decimals);
      out.push([it.value, it.label, unit, decimals, prefix]);
    } else {
      /* kpis() prints a non-numeric value verbatim and reads prefix and suffix
       * only inside count(), so on this branch the engine would drop them.
       * Compose them here instead: dropping an authored symbol is the same
       * divergence as inventing one, pointed the other way. */
      out.push([prefix + String(it.value) + unit, it.label]);
    }
  }
  return out;
}

/* The KPI stack. `kpis()` sets each label with `text:`, so it is text on the
 * stage the way every other label in this file is (R3): the only field in
 * either chart type that is HTML is `jumpChart.shown`.
 *
 * `tone` is the engine's blue/warm switch and no beat field names it — spec
 * §7.1 gives kpis `items` and `kicker` and nothing else — so it stays 'blue',
 * the palette's `accent`. */
function buildKpis(b, index) {
  requireCitation(b);
  requireCountFitsHold(b, index);
  var items = planKpiItems(b);
  return function () {
    planKicker(b, 0.05);
    kpis(items, KPI_D0, 'blue');
  };
}

/* R4 — a row value outside [0, scale] is refused, not clipped.
 *
 * jumpChart() positions every dot at `value / max * 100 + '%'`, so a row above
 * the scale is drawn past the end of its track and a negative one to the left
 * of zero. Clipping would be worse than refusing: the bar would sit at 100% and
 * read as the maximum, which is a number the plan did not carry. Inclusive at
 * both ends — 0 is a benchmark that scored nothing before, and a value equal to
 * the scale is drawn at 100% of the track, which is on the card. */
function planJumpRows(b) {
  var out = [];
  var rows = b.rows || [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    for (var k = 0; k < 2; k++) {
      var name = ['before', 'after'][k];
      var v = r[name];
      if (typeof v !== 'number' || !(v >= 0 && v <= b.scale)) {
        throw new Error(
          'jumpChart rows[' + i + '] ' + name + ' is ' + v + ', outside the ' +
            'chart scale of ' + b.scale + ' — the engine draws every dot at ' +
            name + ' / scale, so this bar lands off its track. It is not ' +
            'clipped: a clipped bar reads as the maximum, and that is a ' +
            'number nothing in the script says',
        );
      }
    }
    /* `shown` is the ONE field in either chart rendered as HTML — a documented
     * display override that content/2026-08-14.js depends on for
     * `<s>34.4</s> &rarr; 43.6`. Absent blanks the cell rather than printing
     * `undefined`; `shown: ""` blanks it deliberately, the way `sub: ""`
     * blanks a title card's subtitle, and the two are indistinguishable to the
     * viewer by design. */
    out.push([r.label, r.before, r.after, typeof r.shown === 'string' ? r.shown : '']);
  }
  return out;
}

/* The before-to-after chart. Rows keep the order they were authored in: they
 * are a ranking as often as not, and a chart that reorders them tells a
 * different story with the same numbers.
 *
 * The footnote is REQUIRED by the schema and drawn as TEXT. It is where "scores
 * as published by Google, on a common 0-70% scale" lives, which is what stops
 * the chart being read as something this series measured itself — dropping it
 * changes what the chart claims. It fades in after the last bar has grown; the
 * offset is per-row layout, not plan timing, so R5 still holds (the plan's
 * `hold` is never read here). */
function buildJumpChart(b, index) {
  requireCitation(b);
  requireCountFitsHold(b, index);
  var rows = planJumpRows(b);
  return function () {
    planKicker(b, 0.02);
    var chart = E('div', 'chart');
    jumpChart(rows, b.scale, JUMP_D0, chart);
    var ft = E('div', 'foot', { p: chart, text: b.footnote });
    fade(ft, JUMP_D0 + rows.length * JUMP_STAGGER + 0.6, { dur: 0.5, dy: 10, blur: 0 });
  };
}

/* ============================ dumbbell ============================
 *
 * The type that renders NO numbers, and the one whose missing property is the
 * point. Spec §7.2: it "encodes direction only and must carry a footnote saying
 * so. It is the correct type when a source publishes ratings rather than
 * scores." engine.js:121's comment calling jumpChart "a before→after dumbbell"
 * is misleading — they are different types, and the difference is a
 * VERIFICATION difference (a jumpChart's figures must be in a source; a
 * dumbbell has no figures) rather than a visual one.
 *
 * A row is refused off the track by script.py, and no citation is required:
 * there is no number on this card for a source to contain.
 */
var DUMB_D0 = 0.55;

function planDumbbellRows(b) {
  var out = [];
  var rows = b.rows || [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    var v = r.values || [];
    /* the engine's positional tuple, built here — same split as jumpChart:
     * mappings are what an operator writes, tuples are what the engine reads. */
    out.push([r.label, v[0], v[1], typeof r.note === 'string' ? r.note : '']);
  }
  return out;
}

/* One legend entry: the swatch, then the name as TEXT. Not innerHTML — the
 * series names are authored strings and 2026-08-12's own legend is the one
 * place the committed episode writes markup around them. */
function planLegendEntry(leg, swatchCss, swatchCls, label) {
  var s = E('span', null, { p: leg });
  E('i', swatchCls, { p: s, css: swatchCss });
  E('span', null, { p: s, text: label });
}

/* Whether any row's markers separate. Also what decides the requiredHold: a
 * merged marker is placed and revealed, it does not travel. */
function dumbbellGaps(rows) {
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    if (rows[i][1] !== rows[i][2]) out.push(i);
  }
  return out;
}

function buildDumbbell(b, index) {
  requireCountFitsHold(b, index);
  var rows = planDumbbellRows(b);
  var series = b.series || [];
  var merged = dumbbellGaps(rows).length < rows.length;
  return function () {
    planKicker(b, 0.02);
    /* The caption is the sentence the chart illustrates — "Evaluators rated it
     * on par with primary care physicians" in the episode — so it is `.body`,
     * the class that paragraph uses, and prose like every other authored
     * field. */
    fade(E('div', 'body', prose(b.caption)), 0.05, { dur: 0.7 });
    E('div', 'sp-s');
    /* `series[2]` is the only thing that says which colour is which entity. On
     * a chart with no axis and a two-tone marker, an unlabelled colour is not a
     * series, it is a dot. The third swatch appears only when some row actually
     * merges: a key to a marker that is not on the card is noise. */
    var leg = E('div', 'legend');
    planLegendEntry(leg, { background: 'var(--blue)' }, null, series[0]);
    planLegendEntry(leg, { background: 'var(--cyan)' }, null, series[1]);
    if (merged) planLegendEntry(leg, null, 'split', 'both');
    fade(leg, 0.3, { dur: 0.6, dy: 12 });

    var chart = E('div', 'chart');
    dumbbell(rows, DUMB_D0, chart);

    /* The axis names the DIRECTION and nothing else — no ticks, no numbers,
     * which is the whole type. The words are the renderer's, not the plan's:
     * they state no magnitude, and without them a reader has no way to know
     * which end of an unlabelled track is the good one. Set as text, so the
     * arrow is a character rather than an entity. */
    var ax = E('div', 'axis', { p: chart });
    E('span', null, { p: ax, text: 'lower' });
    E('span', null, { p: ax, text: 'higher →' });
    var after = DUMB_D0 + rows.length * DUMB_STAGGER;
    fade(ax, after + 0.6, { dur: 0.5, dy: 0, blur: 0 });
    var ft = E('div', 'foot', { p: chart, text: b.footnote });
    fade(ft, after + 0.8, { dur: 0.5, dy: 10, blur: 0 });
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
  kpis: buildKpis,
  jumpChart: buildJumpChart,
  dumbbell: buildDumbbell,
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
    /* The index travels with the beat so a refusal can name it. An operator
     * reading "a kpis beat holds 2s" in a twelve-beat episode has to find which
     * one; `beat 7` is the row they are looking at in `agsoc video review`. */
    scene(b.act_label || b.act || '', b.hold, b.src || '', make(b, i));
  }
}

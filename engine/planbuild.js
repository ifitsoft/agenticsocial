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
    warmActs: [],
    pace: 1, // holds are already scaled in Python; do not scale twice
  });
  for (var i = 0; i < plan.beats.length; i++) {
    var b = plan.beats[i];
    if (b.type !== 'statement') {
      throw new Error('unsupported beat type: ' + b.type);
    }
    /* act_label is resolved in Python — an act ID joined against
     * [[structure.acts]]. Do NOT look it up here: this file has no series.toml,
     * and a second resolution is a second place for the join to drift.
     * `b.act` is the fallback for a plan written before act_label existed. */
    scene(b.act_label || b.act || '', b.hold, b.src || '', buildStatement(b));
  }
}

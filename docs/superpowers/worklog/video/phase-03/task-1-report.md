# Task 1 Report: `script.py` — what a beat is

**Phase:** 3 · **Branch:** `feat/video-phase-03-script-schema`
**Commits:** `1989d99` (tests) · `429871e` (implementation)
**Suite:** 509 → **742 passed** · **Mutation score: 26/26**

---

## 1. What I implemented

`src/agenticsocial/video/script.py` — the schema, and only the schema. It knows
nothing about frames, formats or JSON.

- `ScriptError`, frozen `Beat` and `Script` (D-062), `DEFAULT_HOLD = 3.0`.
- `BEAT_TYPES` — the catalogue as **data**: a dict keyed by type name, each entry
  `{"required": {field: checker}, "optional": {field: checker}, "cited": bool}`.
  Adding a type in Phase 4 is a row, not a new branch.
- `RENDERABLE = frozenset({"statement"})` — what `plan.py` can currently emit.
- `load_script(episode) -> Script`, `load_script_with_digest(episode) -> (Script, str)`,
  `validate_acts(acts, where) -> None`.

Checkers are small functions returning `None` (accept) or a reason phrase. They
are written against the value's **type**, never its truthiness — that is the
whole defence against M4.

`plan.py` is now a consumer. It keeps every timing behaviour: scaled holds,
absolute `start`/`end`, integer frames, the documented key order, `script_sha256`
computed from the same read as the beats. `SUPPORTED_BEATS` is now *literally*
`script.RENDERABLE` rather than a second frozenset — two lists drift the first
time either is widened, which is the D-036 pattern that has produced five defects
in this project.

### Two additions to the brief's interface, both deliberate

| Addition | Why |
|---|---|
| `load_script_with_digest(episode) -> (Script, str)` | `Script` has no `script_sha256` field and I did not want to change the frozen dataclass the brief specifies. Splitting the digest into a second read would mean the bytes hashed and the beats validated could be different file contents — exactly what `test_metadata_and_beats_come_from_the_same_read` exists to prevent. `load_script` is `[0]` of this. |
| `build_plan` calls `validate_acts` | R5 has no teeth unless something calls it, and `build_plan` is the only place holding both the series and the episode. `series.py` cannot call it: `script → episode → series`, so `series → script` would be an import cycle. |

`build_plan` wraps `ScriptError` as `PlanError` (message passed through
unchanged) because `cli.py` catches `PlanError`. `EpisodeError` still propagates
untouched — a file that is not a script at all is a lower-level failure than a
schema one, and wrapping it would have changed existing CLI behaviour.

### Where each type's fields came from

| Type | Fields | Source |
|---|---|---|
| `statement` | `text` | spec §7.1 + both episodes (`rise(h, …)` on an `h1`/`h2`) |
| `body` | `text` | spec §7.1 + both episodes (`fade(b, …)` on `.body`) |
| `list` | `items[]`, `lead?` | spec §7.1 + both episodes (`.stack` / `.item` loops) |
| `kpis` | `items[{value, unit, label, decimals}]` | spec §7.1 and the §7 YAML block; the item shape is exercised by `2026-08-14.js` |
| `jumpChart` | `before`, `after`, `scale`, `footnote` | **spec §7.1 only — contradicted by the episode. See §5.** |
| `dumbbell` | `rows[]`, `series[2]`, `caption`, `footnote` | spec §7.1; `2026-08-12.js` builds exactly this inline (legend of two, `.foot`, per-row notes) |
| `quote` | `text`, `attribution` | spec §7.1 only — neither episode has one |
| `title` | `sub?` | spec §7.1 + both cold opens (`THE<br>BRIEF` + a lede) |
| `signoff` | `text?` | spec §7.1 + both closers (`THAT'S THE BRIEF.`) |
| `custom` | `js` | spec §7.1 + the §7 YAML block |
| shared | `act`, `hold`, `kicker`, `src`, `quote`, `claim_override` | spec §7.1's "shared optional fields on every type" |

**Decisions I had to make** (the spec names the field but not the rule):

1. **`kpis` items: `value` and `label` required; `unit` and `decimals` optional.**
   The spec lists all four without marking any optional. Requiring `decimals` on
   every KPI would be hostile — `[3,'hours ahead of the human reporters']` in
   `2026-08-14.js` has none. `value` may be a number *or* a non-empty string,
   because `engine.js`'s `kpis()` has an explicit non-numeric fallback.
2. **`dumbbell.rows` is validated as a non-empty list and nothing more.** The
   spec does not name the row columns and the episode builds them inline as
   `[label, a, b, note, up]`. Inventing a column contract here would have been
   the largest speculation in the file.
3. **Required text fields must be non-empty; optional ones may be `""`.**
   `sub: ""` is a title card without a subtitle — a real thing. `quote.text: ""`
   is a missing sentence.
4. **`act` `id: ""` is valid.** R5's letter is "a string `id`". Both episodes
   open with `scene('', …)`, so an empty act name is evidenced. It is also the
   falsy-but-valid case that separates `isinstance(id, str)` from `if id:`.
5. **`label` on an act is not type-checked at all** — R5 says free-form.
6. **`claim_override` rides in `Beat.fields`.** It is the one shared field the
   frozen dataclass has no slot for, and Phase 5 must not lose it.

---

## 2. TDD evidence

`tests/test_video_script.py` written and committed first (`1989d99`), red:

```
=== script (collection) ===
=========================== short test summary info ============================
ERROR tests/test_video_script.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.07s

=== plan ===
FAILED tests/test_video_plan.py::test_unsupported_beat_type_is_refused_by_name
 - assert 'cannot be rendered yet' in "/Volumes/…/script.yaml: beat 0 has
   unsupported type 'title' — this phase renders: statement"
1 failed, 34 passed in 0.57s
```

The plan-side failure is worth a note. My first edit to that test swapped
`jumpChart` for `title` and asserted only that both type names appeared — and it
**passed on the unfixed tree**, because the pre-split message already named both.
That is the same class of vacuity as the interned-small-int defect from Task 3b.
The `cannot be rendered yet` assertion is what makes the edit non-vacuous, and I
left a comment in the test saying so.

Green after `429871e`:

```
742 passed in 2.87s
```

Baseline before this task was `509 passed`.

---

## 3. Mutation results

Harness: apply a textual mutation to `script.py` or `plan.py`, run the full
suite, restore from the original bytes. Every mutant was applied and reverted;
`git status --porcelain -- src tests` is clean.

### The brief's ten

| # | Mutant | Result | First failing test |
|---|---|---|---|
| M1 | unknown type accepted (`BEAT_TYPES.get` with a permissive default) | **KILLED** | `test_unknown_type_is_rejected_by_name_and_lists_the_known_ones` |
| M2 | unrenderable type reported with the unknown-type wording | **KILLED** | `test_unsupported_beat_type_is_refused_by_name` |
| M3 | required-field check dropped for one type (`jumpChart.footnote`) | **KILLED** | `test_a_required_field_is_required[jumpChart.footnote]` |
| M4 | `if not raw.get(name)` instead of a presence check | **KILLED** | `test_a_wrongly_typed_field_is_refused[list.lead=0]` |
| M5 | error omits the beat index | **KILLED** | `test_an_error_names_the_beat_index_and_the_type` |
| M5b | error index is a constant `0` (M5's subtler form) | **KILLED** | `test_an_error_names_the_beat_index_and_the_type` |
| M6 | `src`/`quote` not required on `kpis` (`cited: False`) | **KILLED** | `test_a_chart_without_a_source_is_refused[src-kpis]` |
| M7 | `src`/`quote` required on `title` too (`cited: True`) | **KILLED** | `test_unsupported_beat_type_is_refused_by_name` |
| M8 | `acts[]` entry shape unchecked | **KILLED** | `test_an_act_with_a_non_string_id_is_refused[0]` |
| M9 | `beats = -1` accepted (`count <= 0` check dropped) | **KILLED** | `test_an_act_beats_count_must_be_a_positive_integer[-1]` |
| M10 | validation normalises `script.yaml` on read | **KILLED** | `test_a_comment_bearing_script_survives_plan_building_byte_for_byte` |

### My own sweep — sixteen more, ten of them falsy-value

| # | Mutant | Result | First failing test |
|---|---|---|---|
| S1 | **FALSY** `text` accepts `""` (emptiness check removed) | **KILLED** | `test_a_wrongly_typed_field_is_refused[statement.text='']` |
| S2 | **FALSY** `hold <= 0` → `hold < 0`, so `hold: 0` loads | **KILLED** | `test_a_wrongly_typed_shared_field_is_refused[hold=0]` |
| S3 | **FALSY** shared fields checked by truthiness (`if raw.get(name)`) | **KILLED** | `test_a_wrongly_typed_shared_field_is_refused[act=0]` |
| S4 | **FALSY** citation checked for presence only, so `src: ""` cites | **KILLED** | `test_a_chart_whose_source_is_empty_is_refused[-src-kpis]` |
| S5 | **FALSY** `items: []` accepted (list emptiness unchecked) | **KILLED** | `test_a_wrongly_typed_field_is_refused[list.items=[]]` |
| S6 | **FALSY** `_is_int` stops excluding `bool`, so `beats = True` loads | **KILLED** | `test_an_act_beats_count_must_be_a_positive_integer[True]` |
| S7 | **FALSY** `positive_number` `>` → `>=`, so `scale: 0` loads | **KILLED** | `test_a_wrongly_typed_field_is_refused[jumpChart.scale=0]` |
| S8 | **FALSY** act `beats` gated on `act.get("beats")`, so `beats = 0` loads | **KILLED** | `test_an_act_beats_count_must_be_a_positive_integer[0]` |
| S13 | **FALSY** `if not kind:` for a missing `type`, so `type: 0` is diagnosed as absent | **KILLED** *(survived first pass — see below)* | `test_a_present_but_falsy_type_is_unknown_not_missing[0]` |
| S14 | **FALSY** `pace <= 0` → `pace < 0` | **KILLED** | `test_a_non_positive_pace_is_refused[0]` |
| S9 | `series[2]` length check weakened to `len(v) < 1` | **KILLED** | `test_a_wrongly_typed_field_is_refused[dumbbell.series=['only one']]` |
| S10 | beat indices become 1-based | **KILLED** | `test_each_catalogue_type_validates_with_its_documented_fields[body]` |
| S11 | kpi item `label` no longer required | **KILLED** | `test_a_wrongly_typed_field_is_refused[kpis.items=[{'value': 1}]]` |
| S12 | `SUPPORTED_BEATS` drifts from `RENDERABLE` (D-036 regression) | **KILLED** | `test_unsupported_beat_type_is_refused_by_name` |
| S15 | payload also carries the shared fields (two homes for `src`) | **KILLED** | `test_the_payload_does_not_repeat_the_shared_fields` |

**S13 survived the first sweep and is the one real hole the sweep found.** Writing
`if not kind:` instead of `if kind is None:` still raises — so my
`test_a_non_string_or_missing_type_is_refused` (which only asserted *that* it
raised) could not see it. But it refuses for the wrong reason: it tells an
operator who wrote `type: 0` to add a `type` key that is already on the line in
front of them. Added `test_a_present_but_falsy_type_is_unknown_not_missing`,
which pins that `type: 0`/`""`/`False`/`[]` report *unknown type*, not *no type*.
It fails on the mutant and passes on the fix.

**MUTATION SCORE: 26/26.**

Two structural guards exist so the sweep cannot silently rot:

- `test_every_catalogue_type_with_required_fields_is_covered_above` — M3 is only
  killed if the parametrisation enumerates *every* type with required fields, so
  the table is asserted equal to the catalogue's.
- `test_the_wrong_type_table_contains_falsy_values_for_every_field_it_covers` —
  asserts every `(type, field)` pair in the wrong-type table has at least one
  falsy bad value. This is the guard against the exact defect from the last two
  tasks recurring in the next one.

---

## 4. Files changed

| File | Commit | Change |
|---|---|---|
| `tests/test_video_script.py` | `1989d99`, `429871e` | new, 742-test suite's largest module |
| `tests/test_video_plan.py` | `1989d99` | one test updated: the unsupported-type message now distinguishes unrenderable from unknown |
| `src/agenticsocial/video/script.py` | `429871e` | new |
| `src/agenticsocial/video/plan.py` | `429871e` | schema removed; now a consumer |

**Commits:** `1989d99` (tests, RED) · `429871e` (implementation, GREEN).
Nothing under `docs/` was staged. `git status --porcelain -- src tests` is clean.

---

## 5. Issues and concerns

### 5a. Which catalogue fields are speculative

Ranked by how confident I am Phase 4 will find them wrong.

1. **`jumpChart`'s entire field set — `before`, `after`, `scale`, `footnote`.**
   This is the one I most expect to be wrong, and it is not a judgement call I
   made in a vacuum: **the spec and the only committed episode that renders a
   jumpChart flatly disagree.** Spec §7.1 gives four scalars, which can describe
   exactly one bar. `engine/content/2026-08-14.js` calls
   `jumpChart(rows, max, d0, parent)` with **four rows**:

   ```js
   jumpChart([
     ['FrontierCode 1.1', 34.4, 43.6, '<s>34.4</s> &rarr; 43.6'],
     ['DeepSWE v1.1',     48.0, 65.3, '<s>48–49</s> &rarr; 65.3'],
     ['AutomationBench',  17.0, 30.4, '<s>17.0</s> &rarr; 30.4'],
     ['GDP.pdf',          22.0, 34.0, '<s>22.0</s> &rarr; 34.0']
   ],70,.5,chart);
   ```

   The spec's shape cannot express that episode. I followed the spec because it
   is the named schema authority for §7.1 and the brief asks for spec fields, but
   **I am flagging this as a defect in the spec, not a judgement of mine.** The
   real shape is almost certainly `rows[]` + `scale` + `footnote`, with `scale`
   mapping to the engine's `max` argument. When Phase 4 changes it, it should be
   one row of `BEAT_TYPES` plus a `rows`-shaped checker — that is what shaping
   the catalogue as data bought.

2. **`quote`'s `text` + `attribution`.** Neither committed episode has a quote
   beat. Nothing here is evidenced by a render — the whole type is spec-only.
   `attribution` being *required* is my reading of the unmarked column; a quote
   card with no attribution may well be legitimate.

3. **`dumbbell.caption`.** `2026-08-12.js` has a legend, per-row notes, an axis
   and a `.foot`, but nothing that unambiguously plays the role of `caption`. It
   is required in my catalogue on the spec's word alone. `series[2]` and
   `footnote` I am confident about; `rows[]`'s *column* shape I deliberately left
   unvalidated rather than guess.

4. **`kpis` item optionality.** `value` and `label` required, `unit` and
   `decimals` optional. The spec marks none of them optional; I split them by
   what the episode actually omits. If Phase 4 disagrees, it is a checker edit.

5. **`custom.js` as a required non-empty string.** Evidenced only by the spec's
   YAML block. §7.1 marks `custom` "manual attestation required", which suggests
   a second field for the attestation that neither the spec nor an episode names
   — Phase 4 will probably need one.

6. **`list.lead` accepting `""`.** Optional decorative fields take `free_text`;
   `lead` is arguably content and should take `text`. Low stakes either way.

### 5b. Does the `script.py` / `plan.py` split pay?

Yes, and the diff is the argument: `plan.py` lost 89 lines and gained a
docstring. But the honest version is narrower than "separation of concerns".

The split pays for **three specific reasons**:

1. **Phase 5 is the buyer.** The verifier walks `Script.beats` reading `.src`,
   `.quote` and `.fields`. If it had to call `build_plan`, it would drag in FPS,
   formats, `plan.json` key order and the renderable gate — and it would be
   *unable to verify an unrenderable beat*, which is precisely backwards: an
   unverified `dumbbell` is more dangerous than an unverified `statement`.
2. **The two gates have different answers and different fixes.** Before the
   split there was one message for "you typo'd the type" and "we haven't built
   that yet". A single module makes that conflation the path of least
   resistance; two modules make it hard to write by accident.
3. **It broke a symmetry that was already producing defects.** `SUPPORTED_BEATS`
   was a frozenset that had to stay in step with the (then implicit) catalogue.
   It is now `= RENDERABLE`, one definition. Mutant S12 exists to prove that
   drift is now visible.

Against: `script.py` is 380 lines and `plan.py` is 140, so this is not two peers
— it is a large schema module with a small consumer. If Phase 5 turns out not to
need `Script` (if it reads `plan.json` instead), the split earns only reason 2,
and reason 2 alone is worth about thirty lines, not a module. I think that risk
is small — `plan.json` is lossy by design; it drops every field a `statement`
does not use — but it is the honest failure mode.

### 5c. Should `warm_acts` referencing non-existent act ids be enforced here?

**No — and I deliberately did not.** Three reasons, in order of weight:

1. **It is not this module's data.** `validate_acts` takes `acts` and nothing
   else. A cross-field rule needs `warm_acts` *and* `acts` together, so it is a
   `series.toml` invariant and belongs wherever the rest of `series.toml` is
   validated — `series.py`. Putting it in `script.py` would mean either widening
   the signature the brief specifies or passing the whole `Series`, and
   `series.py` cannot import `script.py` without a cycle (`script → episode →
   series`). That is a real architectural signal, not an inconvenience.

2. **It would be enforced at the wrong moment.** I already have `build_plan`
   calling `validate_acts`, which is late — but act *shape* is cheap and
   unambiguous, so a late check costs nothing. A `warm_acts` reference error is
   the kind of thing an operator wants at `agsoc series` time, on the file they
   just edited, not when a render fails.

3. **The rule may not even be right.** Spec §6 says `beats` counts are advisory;
   `accent_warm` is marked "reserved". A `warm_acts = ["03"]` written *before*
   `[[structure.acts]]` is filled in is a plausible working state, and neither
   committed episode's `warmActs` is checked against anything — `2026-08-12.js`
   has `warmActs:['03 — Agents']`, which is the act **label**, not the act
   **id**. So even the matching key is unsettled: is a warm act named by `id`
   (`"03"`) or by `label` (`"03 — Agents"`)? Enforcing a rule whose join column
   is ambiguous would turn a soft problem into a hard failure on the wrong side.

**Recommendation:** enforce it in `series.py` as a **warning**, not an error,
once Phase 4 settles whether beats reference acts by `id` or `label`. That same
decision also decides whether a beat's `act` field should be validated against
the catalogue of act ids — which I did not do here for the same reason.

### 5d. Two errors of mine, both disclosed

1. **A self-contradictory parametrisation in the RED commit.** I listed `id: ""`
   as both a rejected non-string id and an accepted falsy-but-valid one. The
   implementation could not satisfy both. Resolved in favour of accepting it
   (R5's letter; both episodes' cold opens have an empty act name; and it is the
   case that separates `isinstance` from truthiness). Fixed in `429871e` with the
   reason written into the test docstring.
2. **A vacuous test edit, caught before committing.** See §2 — the rewritten
   plan-side unsupported-type test passed on the unfixed tree until I added the
   `cannot be rendered yet` assertion.

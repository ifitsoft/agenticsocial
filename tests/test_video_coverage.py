"""The coverage ledger, ported from `engine/coverage.test.mjs` (D-112, R4).

The node file existed because `coverage.mjs` had **no tests at all**, which is
why a tool that printed *"NOT COVERED. Safe to run as new."* over three prior
stories was never asked whether it was safe. Porting the behaviour without
porting these assertions would move the defect, not the guarantee — so every
assertion in the node file has a counterpart here, and the sections below keep
its order and its reasoning.

Two properties are load-bearing and each has a negative half:

  - The matcher is **one-directional**: it strips non-alphanumerics from both
    sides, so it can only ever *add* a match (R1). Negative: a genuinely new
    story still comes back absent (R1-negative, mutant M2).
  - The message **never claims more than the search supports** (R2). Negative:
    a real hit still reads as an unambiguous stop (R2-negative).

What Phase 11 adds on top of the port: the ledger is **per-series** (R3), it is
written by `agsoc coverage add` after a render (R5), and `add` and `check` must
agree about normalisation — the round trip, mutant M8, the failure that is
invisible until a story is re-told.

Matching assertions run against **the real ledger**: `engine/coverage.json`, the
series' actual record, copied into a temp workspace and never written back. It
stays in the repo after the node command retires for exactly this reason —
the same argument `test_engine_supported_path.py` makes for `content/*.js`.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.workspace import Workspace

runner = CliRunner()

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "engine" / "coverage.json"


def run(*args):
    """Invoke the CLI with exceptions propagating (D-035)."""
    return runner.invoke(app, list(args), catch_exceptions=False)


def mentions(out: str) -> int:
    """How many terms the tool reported as previously covered.

    Counting the marker the tool prints, rather than re-implementing the
    matcher, keeps the oracle independent of the code under test — the node
    file's argument, kept."""
    return out.count("prior mention")


def hit_count(out: str) -> int:
    import re

    m = re.search(r"(\d+) hit\(s\)", out)
    return int(m.group(1)) if m else 0


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


@pytest.fixture()
def brief(ws):
    """A series whose ledger is the real record, byte for byte."""
    run("series", "new", "the-brief", "--name", "The Brief")
    (ws.series_dir / "the-brief" / "coverage.json").write_text(
        LEGACY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return ws


def check(*terms, series="the-brief"):
    return run("coverage", "check", *terms, "--series", series)


# --- the regression: a hyphenated term against a spaced ledger entry -------------------


def test_a_hyphenated_product_term_finds_the_spaced_entry(brief):
    """`gemini-3.7` is what an author writes; `Gemini 3.7 Flash` is what the
    ledger holds. A raw substring match answered "not covered" and a blind
    runner cleared the story on that answer."""
    r = check("gemini-3.7")
    assert mentions(r.output) == 1
    assert hit_count(r.output) > 0


def test_the_hit_names_the_episode_and_the_story_it_collides_with(brief):
    r = check("gemini-3.7")
    assert "2026-08-14" in r.output
    assert "Gemini 3.7 Flash" in r.output


def test_a_hit_never_reads_as_permission(brief):
    r = check("gemini-3.7")
    assert r.exit_code == 0
    assert "prior mention" in r.output
    assert "safe to run as new" not in r.output.lower()


def test_check_exits_zero_on_a_hit(brief):
    """A hit is a verdict to read, not a crash."""
    assert check("gemini-3.7").exit_code == 0


def test_the_bare_vendor_term_still_finds_its_four_mentions(brief):
    """The fallback the runner had to invent. Whatever the new matcher does, it
    may not lose an old hit."""
    assert hit_count(check("gemini").output) == 4


def test_every_separator_spelling_gives_the_same_answer(brief):
    forms = ["gemini-3.7", "gemini 3.7", "Gemini_3.7", "GEMINI-3-7", "gemini3.7"]
    results = [check(f) for f in forms]
    assert all(r.exit_code == 0 for r in results)
    counts = [hit_count(r.output) for r in results]
    assert counts[0] > 0
    assert all(c == counts[0] for c in counts), f"{forms} -> {counts}"


# --- the negative half: a genuinely new story is still absent -------------------------


@pytest.mark.parametrize(
    "term", ["deepseek", "v4-pro", "qwen3.8-max", "alibaba", "nothing-like-this-9x"]
)
def test_a_story_the_series_never_told_is_reported_absent(brief, term):
    """M2: a matcher loose enough to find `gemini-3.7` by accident finds these
    too. `deepseek` and `v4-pro` are the brief's own examples."""
    r = check(term)
    assert r.exit_code == 0
    assert "no entry matches" in r.output
    assert hit_count(r.output) == 0
    assert mentions(r.output) == 0


def test_a_term_made_only_of_separators_matches_nothing(brief):
    """Punctuation normalises to nothing, and an empty needle is a substring of
    every string — the loosest possible matcher, reached by accident."""
    r = check("...")
    assert r.exit_code == 0
    assert "no entry matches" in r.output
    assert hit_count(r.output) == 0


@pytest.mark.parametrize("term,why", [("watermark", "watermarking"), ("llm", "LiteLLM")])
def test_a_term_that_starts_mid_token_still_hits(brief, term, why):
    """Tightening to whole-token equality would fix `gemini-3.7` and lose these
    — one silent miss traded for two."""
    assert hit_count(check(term).output) > 0, why


# --- the message says what it knows, and no more ---------------------------------------


def test_a_miss_never_says_safe(brief):
    r = check("deepseek")
    assert r.exit_code == 0 and "no entry matches" in r.output
    assert "safe" not in r.output.lower()


def test_a_miss_never_says_all_clear(brief):
    r = check("deepseek")
    assert r.exit_code == 0 and "no entry matches" in r.output
    assert "all clear" not in r.output.lower()


def test_a_miss_says_what_was_searched(brief):
    import re

    out = check("deepseek").output
    assert "searched" in out.lower()
    assert re.search(r"\d+ stor", out, re.I)


def test_a_miss_states_the_limit_of_what_absence_proves(brief):
    """Stated on the MISS, beside the term it is about — not only in the
    summary at the bottom. A mutation sweep killed the weaker version of this
    assertion: dropping the per-term bound left the closing paragraph behind
    and an `or` was happy with it."""
    out = check("deepseek").output.lower()
    assert "that is all it proves" in out
    assert "does not mean the story is new" in out


def test_a_miss_points_at_related_entries_without_counting_them(brief):
    """The near miss the runner found by hand: the term is absent, but a piece
    of it is all over the ledger. A pointer, not a hit."""
    out = check("gemini-9.9").output
    assert hit_count(out) == 0
    assert "gemini" in out.lower()
    assert "related" in out.lower()


def test_a_hit_still_reads_as_a_stop(brief):
    """R2-negative: no "maybe", no "possible" — the instruction is unchanged
    and it is an instruction."""
    out = check("gemini-3.7").output
    assert "updates" in out.lower() or "drop them" in out.lower()
    for soft in ("might be", "possibly", "maybe"):
        assert soft not in out.lower()


# --- an invented ledger, so these cannot depend on the real one -----------------------


FIXTURE = {
    "series": "Fixture",
    "episodes": [
        {
            "date": "2026-01-01",
            "video": "fixture.mp4",
            "runtimeSec": 1,
            "stories": [
                {
                    "id": "acme-foo-9-9-ultra",
                    "title": "Acme ships Foo 9.9 Ultra",
                    "act": "01 — The headline",
                    "angle": "launch",
                    "entities": ["Acme", "Foo 9.9 Ultra"],
                    "sources": ["acme.example"],
                    "note": "A spaced product name, the shape the real ledger uses.",
                }
            ],
        }
    ],
}


@pytest.fixture()
def fixture_series(ws):
    run("series", "new", "fixture")
    (ws.series_dir / "fixture" / "coverage.json").write_text(
        json.dumps(FIXTURE, indent=2) + "\n", encoding="utf-8"
    )
    return ws


def test_a_hyphenated_term_finds_the_fixture_entry(fixture_series):
    assert hit_count(check("foo-9.9", series="fixture").output) == 1


def test_a_neighbouring_version_does_not(fixture_series):
    r = check("foo-9.8", series="fixture")
    assert r.exit_code == 0 and "no entry matches" in r.output
    assert hit_count(r.output) == 0


def test_the_series_ledger_is_what_was_read(fixture_series):
    r = check("gemini", series="fixture")
    assert r.exit_code == 0 and "no entry matches" in r.output
    assert hit_count(r.output) == 0


def test_a_term_that_appears_only_in_an_entity_is_found(ws):
    """The ledger's own fields are not decoration, and an author searching a
    vendor name is the commonest search this tool gets. The entity here appears
    in NO other field — a sweep killed the earlier version of this test, which
    searched for a name the title carried too."""
    run("series", "new", "entities-only")
    led = json.loads(json.dumps(FIXTURE))
    led["episodes"][0]["stories"][0]["entities"] = ["Zetacorp Holdings"]
    (ws.series_dir / "entities-only" / "coverage.json").write_text(
        json.dumps(led, indent=2) + "\n", encoding="utf-8"
    )
    assert hit_count(check("zetacorp", series="entities-only").output) == 1


def test_a_term_that_appears_only_in_a_source_is_found(fixture_series):
    assert hit_count(check("acme.example", series="fixture").output) == 1


def test_a_term_that_appears_only_in_the_title_is_found(ws):
    """A title-only match, with the entities emptied so nothing else can carry
    it: `add` derives a title from what the card said, and a checker that does
    not read titles cannot see most of what `add` writes."""
    run("series", "new", "bare")
    bare = json.loads(json.dumps(FIXTURE))
    story = bare["episodes"][0]["stories"][0]
    story["entities"] = []
    story["sources"] = []
    story["note"] = ""
    story["id"] = "row-1"
    (ws.series_dir / "bare" / "coverage.json").write_text(
        json.dumps(bare, indent=2) + "\n", encoding="utf-8"
    )
    assert hit_count(check("foo-9.9", series="bare").output) == 1


def test_list_still_works(fixture_series):
    r = run("coverage", "list", "--series", "fixture")
    assert r.exit_code == 0
    assert "Acme ships Foo 9.9 Ultra" in r.output


def test_list_ids_still_works(fixture_series):
    r = run("coverage", "list", "--series", "fixture", "--ids")
    assert r.exit_code == 0
    assert r.output.strip() == "acme-foo-9-9-ultra"


def test_episode_still_works(fixture_series):
    r = run("coverage", "episode", "2026-01-01", "--series", "fixture")
    assert r.exit_code == 0
    assert "01 — The headline" in r.output


def test_an_unknown_episode_still_exits_non_zero(fixture_series):
    r = run("coverage", "episode", "1999-09-09", "--series", "fixture")
    assert r.exit_code == 1
    assert "2026-01-01" in r.output


def test_check_with_no_terms_still_exits_two(fixture_series):
    assert run("coverage", "check", "--series", "fixture").exit_code == 2


# --- R3: the ledger is per-series ------------------------------------------------------


def test_one_series_history_does_not_suppress_another_series_story(brief, ws):
    """The scoping change, stated as a test. Two series sharing one ledger means
    one series' history suppresses the other's stories — which is a story
    silently dropped, not a story re-told."""
    run("series", "new", "cardio-weekly")
    r = check("gemini", series="cardio-weekly")
    assert r.exit_code == 0 and "no entry matches" in r.output
    assert hit_count(r.output) == 0
    assert mentions(r.output) == 0
    assert hit_count(check("gemini").output) == 4  # and the-brief still has them


def test_a_check_names_the_series_it_searched(brief):
    assert "the-brief" in check("deepseek").output


def test_another_series_hit_is_reported_as_a_pointer_not_a_hit(brief, ws):
    """Silence would have been defensible; this is the other answer. A story
    another series told is not this series' hit — it cannot be, or the ledger
    would suppress across series again — but the author is told it exists."""
    run("series", "new", "cardio-weekly")
    r = check("gemini", series="cardio-weekly")
    assert hit_count(r.output) == 0
    assert "the-brief" in r.output


def test_an_unreadable_neighbouring_series_does_not_break_the_check(brief, ws):
    """The cross-series pointer reads files this series does not own. One broken
    neighbour must not take the check down — D-018's argument, again."""
    d = ws.series_dir / "broken"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text('[series]\nname = "b"\nslug = "broken"\n', encoding="utf-8")
    (d / "coverage.json").write_text("{ not json", encoding="utf-8")
    r = check("gemini")
    assert r.exit_code == 0
    assert hit_count(r.output) == 4


def test_check_refuses_an_unknown_series(ws):
    r = check("gemini", series="nope")
    assert r.exit_code == 1
    assert "nope" in r.output


def test_check_refuses_a_series_with_no_ledger(ws):
    run("series", "new", "the-brief")
    (ws.series_dir / "the-brief" / "coverage.json").unlink()
    r = check("gemini")
    assert r.exit_code == 1
    assert "coverage.json" in r.output


# --- migration: R3's negative half -----------------------------------------------------


def legacy() -> dict:
    return json.loads(LEGACY.read_text(encoding="utf-8"))


def ledger_of(ws, slug) -> dict:
    return json.loads((ws.series_dir / slug / "coverage.json").read_text(encoding="utf-8"))


def stories_of(led: dict) -> list[dict]:
    return [s for e in led["episodes"] for s in e["stories"]]


def test_migration_moves_every_story_into_the_series(ws):
    run("series", "new", "the-brief", "--name", "The Brief")
    r = run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    assert r.exit_code == 0
    before, after = legacy(), ledger_of(ws, "the-brief")
    assert len(after["episodes"]) == len(before["episodes"])
    assert len(stories_of(after)) == len(stories_of(before))


def test_migration_preserves_every_story_verbatim(ws):
    """M5. A migration that silently drops an entry is worse than no migration:
    the failure mode is a story re-told as new."""
    run("series", "new", "the-brief")
    run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    before = {json.dumps(s, sort_keys=True) for s in stories_of(legacy())}
    after = {json.dumps(s, sort_keys=True) for s in stories_of(ledger_of(ws, "the-brief"))}
    assert before == after


def test_migration_preserves_the_episode_metadata(ws):
    run("series", "new", "the-brief")
    run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    after = ledger_of(ws, "the-brief")["episodes"]
    assert len(after) == len(legacy()["episodes"]) == 2
    for was, now in zip(legacy()["episodes"], after):
        assert was == now


def test_migration_reports_the_counts_it_moved(ws):
    run("series", "new", "the-brief")
    r = run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    assert "18" in r.output and "2" in r.output


def test_migration_writes_exactly_one_series(ws):
    """M6: a migration that duplicates every entry into every series suppresses
    stories the other series never told."""
    run("series", "new", "the-brief")
    run("series", "new", "cardio-weekly")
    r = run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    assert r.exit_code == 0
    assert len(stories_of(ledger_of(ws, "the-brief"))) == 18
    assert ledger_of(ws, "cardio-weekly")["episodes"] == []


def test_migration_leaves_the_source_untouched(ws):
    before = LEGACY.read_bytes()
    run("series", "new", "the-brief")
    r = run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    assert r.exit_code == 0
    assert LEGACY.read_bytes() == before


def test_migration_is_idempotent(ws):
    """Run twice, and the second run adds nothing — an operator who is not sure
    whether it ran must be able to find out by running it."""
    run("series", "new", "the-brief")
    run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    once = ledger_of(ws, "the-brief")
    r = run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    assert r.exit_code == 0
    assert ledger_of(ws, "the-brief") == once


def test_migration_refuses_when_the_same_date_holds_different_stories(ws):
    """The one case where silence would lose data: same date, different content.
    Refuse and name it rather than pick a winner."""
    run("series", "new", "the-brief")
    led = ledger_of(ws, "the-brief")
    led["episodes"].append(
        {"date": "2026-08-12", "stories": [{"id": "x", "title": "Something else"}]}
    )
    (ws.series_dir / "the-brief" / "coverage.json").write_text(
        json.dumps(led, indent=2) + "\n", encoding="utf-8"
    )
    r = run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    assert r.exit_code == 1
    assert "2026-08-12" in r.output
    assert ledger_of(ws, "the-brief") == led


def test_migration_refuses_a_source_that_holds_one_date_twice(ws):
    """Two entries for one date in the SOURCE is not something a merge can
    resolve either — and the naive merge writes both, so the ledger would then
    hold a date twice and `episode` would show one of them."""
    run("series", "new", "the-brief")
    legacy_twice = legacy()
    legacy_twice["episodes"].append(dict(legacy_twice["episodes"][0]))
    path = ws.root / "twice.json"
    path.write_text(json.dumps(legacy_twice), encoding="utf-8")
    r = run("coverage", "migrate", str(path), "--series", "the-brief")
    assert r.exit_code == 1
    assert "2026-08-12" in r.output
    assert ledger_of(ws, "the-brief")["episodes"] == []


def test_the_migration_refuses_if_its_own_arithmetic_stops_balancing(monkeypatch):
    """The guard under the merge, exercised directly. It is unreachable by
    construction today, which is exactly why it is worth a test: it is there to
    catch the edit that makes it reachable, and an untested guard is a comment.
    """
    from agenticsocial.video import coverage as cov

    real = cov.counts
    calls = {"n": 0}

    def lying_counts(ledger):
        calls["n"] += 1
        stories, episodes = real(ledger)
        return (stories - 1 if calls["n"] == 2 else stories), episodes

    monkeypatch.setattr(cov, "counts", lying_counts)
    with pytest.raises(cov.CoverageError, match="does not balance"):
        cov.migrate({"episodes": []}, legacy())


def test_migration_dry_run_writes_nothing(ws):
    run("series", "new", "the-brief")
    before = ledger_of(ws, "the-brief")
    r = run("coverage", "migrate", str(LEGACY), "--series", "the-brief", "--dry-run")
    assert r.exit_code == 0
    assert ledger_of(ws, "the-brief") == before


def test_migration_refuses_a_missing_source(ws):
    run("series", "new", "the-brief")
    r = run("coverage", "migrate", "no/such/file.json", "--series", "the-brief")
    assert r.exit_code == 1


def test_the_migrated_ledger_answers_the_check(ws):
    """The point of migrating at all: the history has to be reachable from the
    command that replaces the one being retired."""
    run("series", "new", "the-brief")
    run("coverage", "migrate", str(LEGACY), "--series", "the-brief")
    assert hit_count(check("gemini-3.7").output) > 0


# --- `add`: what a story is, and who writes it ----------------------------------------

SCRIPT = """---
episode: '2026-08-20'
series: the-brief
status: {status}
pace: 1.0
{render}---
beats:
  - type: title
    act: "01"
    hold: 3.0
    sub: Five stories from the last 24 hours.

  - type: statement
    act: "01"
    hold: 4.0
    kicker: Today's headline
    text: DeepSeek V4-Pro raised prices by up to 1,100%.
    src: pasted
    quote: DeepSeek V4-Pro raised prices by up to 1,100%

  - type: list
    act: "02"
    hold: 4.0
    lead: The largest open-weight model to date
    items:
      - Alibaba Qwen3.8-Max
      - roughly 2.4 trillion parameters
    src: pasted
    quote: Alibaba Qwen3.8-Max, roughly 2.4 trillion parameters

  - type: signoff
    act: "02"
    hold: 2.0
    text: That is the brief.
"""

RENDERED_META = {
    "render": {
        "outcome": "rendered",
        "format": "vertical",
        "file": "out/vertical-1080x1920.mp4",
        "runtime_sec": 119.9,
        "at": "2026-08-20T09:00:00-05:00",
    }
}


def make_episode(ws, status="rendered", slug="the-brief", ep="2026-08-20"):
    d = ws.series_dir / slug / "episodes" / ep
    (d / "sources").mkdir(parents=True, exist_ok=True)
    (d / "out").mkdir(exist_ok=True)
    render = ""
    if status == "rendered":
        render = "render:\n" + "".join(
            f"  {k}: {json.dumps(v)}\n" for k, v in RENDERED_META["render"].items()
        )
    body = SCRIPT.format(status=status, render=render)
    (d / "script.yaml").write_text(body, encoding="utf-8")
    (d / "sources" / "_manifest.json").write_text(
        json.dumps({"pasted": {"url": "https://example.test/digest", "title": "digest"}}),
        encoding="utf-8",
    )
    return d


def test_add_records_the_episode_and_its_stories(brief, ws):
    make_episode(ws)
    r = run("coverage", "add", "2026-08-20", "--series", "the-brief")
    assert r.exit_code == 0
    led = ledger_of(ws, "the-brief")
    dates = [e["date"] for e in led["episodes"]]
    assert "2026-08-20" in dates
    ep = next(e for e in led["episodes"] if e["date"] == "2026-08-20")
    assert len(ep["stories"]) == 2  # the two asserting beats; title/signoff assert nothing


def test_add_records_what_the_episode_said_not_a_placeholder(brief, ws):
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    led = ledger_of(ws, "the-brief")
    titles = " ".join(s["title"] for s in stories_of(led))
    assert "V4-Pro" in titles
    assert "Qwen3.8-Max" in titles


def test_add_records_the_entities_the_checker_extracted(brief, ws):
    """What is in the ledger to match against is what decides whether `check`
    works in six months."""
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    ent = {e for s in stories_of(ledger_of(ws, "the-brief")) for e in s.get("entities", [])}
    # Substring, not equality: `claims.py` extracts glued multi-entity runs
    # (D-102) — "DeepSeek V4-Pro" is one atom. That costs the ledger nothing,
    # because the matcher is containment-based and `deepseek` finds it anyway.
    assert any("DeepSeek" in e for e in ent), ent
    assert any("Qwen3.8-Max" in e for e in ent), ent


def test_add_records_the_source_the_beat_cited(brief, ws):
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    src = {s for st in stories_of(ledger_of(ws, "the-brief")) for s in st.get("sources", [])}
    assert "pasted" in src
    assert "example.test" in src


def test_add_records_the_rendered_file_and_runtime(brief, ws):
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    ep = next(
        e for e in ledger_of(ws, "the-brief")["episodes"] if e["date"] == "2026-08-20"
    )
    assert ep["video"] == "out/vertical-1080x1920.mp4"
    assert ep["runtimeSec"] == 119.9


def test_add_refuses_an_episode_that_was_never_rendered(brief, ws):
    """R5: `add` records after render. An episode still in review has not told
    anyone anything.

    Asserted on the status refusal SPECIFICALLY: there are two guards here (the
    status, and the render record beside it), and each will refuse the other's
    input. A sweep found that an assertion on the word "render" alone let
    either guard be deleted while the other quietly covered for it."""
    make_episode(ws, status="in_review")
    r = run("coverage", "add", "2026-08-20", "--series", "the-brief")
    assert r.exit_code == 1
    assert "in_review, not rendered" in r.output
    assert ledger_of(ws, "the-brief")["episodes"] == legacy()["episodes"]


def test_add_refuses_an_episode_marked_rendered_with_no_render_record(brief, ws):
    """The other guard, on its own input. `rendered` with nothing to account for
    it is a status somebody hand-edited, and the ledger is not the place to
    find that out."""
    d = make_episode(ws, status="rendered")
    body = (d / "script.yaml").read_text(encoding="utf-8")
    head, rest = body.split("render:\n", 1)
    rest = rest.split("---\n", 1)[1]
    (d / "script.yaml").write_text(head + "---\n" + rest, encoding="utf-8")
    r = run("coverage", "add", "2026-08-20", "--series", "the-brief")
    assert r.exit_code == 1
    assert "no render record" in r.output
    assert ledger_of(ws, "the-brief")["episodes"] == legacy()["episodes"]


def test_add_refuses_to_record_the_same_episode_twice(brief, ws):
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    once = ledger_of(ws, "the-brief")
    r = run("coverage", "add", "2026-08-20", "--series", "the-brief")
    assert r.exit_code == 1
    assert "--replace" in r.output
    assert ledger_of(ws, "the-brief") == once


def test_add_replace_rewrites_the_episode_in_place(brief, ws):
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    r = run("coverage", "add", "2026-08-20", "--series", "the-brief", "--replace")
    assert r.exit_code == 0
    dates = [e["date"] for e in ledger_of(ws, "the-brief")["episodes"]]
    assert dates.count("2026-08-20") == 1


def test_the_ledger_is_written_atomically(brief, ws, monkeypatch):
    """Every workspace write goes through `atomic_write` (CLAUDE.md). A ledger
    half-written by an interrupted `add` is a ledger that has lost history — the
    one thing this file must never do."""
    from agenticsocial.video import coverage as cov

    seen = []
    real = cov.atomic_write
    monkeypatch.setattr(
        cov, "atomic_write", lambda p, t: (seen.append(p), real(p, t))[1]
    )
    make_episode(ws)
    assert run("coverage", "add", "2026-08-20", "--series", "the-brief").exit_code == 0
    assert seen == [ws.series_dir / "the-brief" / "coverage.json"]


def test_add_dry_run_writes_nothing(brief, ws):
    make_episode(ws)
    before = ledger_of(ws, "the-brief")
    r = run("coverage", "add", "2026-08-20", "--series", "the-brief", "--dry-run")
    assert r.exit_code == 0
    assert "V4-Pro" in r.output
    assert ledger_of(ws, "the-brief") == before


def test_add_carries_the_operators_note(brief, ws):
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief", "--note", "ran as an update")
    ep = next(
        e for e in ledger_of(ws, "the-brief")["episodes"] if e["date"] == "2026-08-20"
    )
    assert ep["note"] == "ran as an update"


def test_add_says_the_ledger_records_what_was_rendered(brief, ws):
    """The bound on what `add` knows, printed where the operator reads it: a
    render is not a publication, and the two differ the moment one is
    discarded."""
    make_episode(ws)
    out = run("coverage", "add", "2026-08-20", "--series", "the-brief").output.lower()
    assert "rendered" in out


def test_add_preserves_the_existing_history(brief, ws):
    make_episode(ws)
    assert run("coverage", "add", "2026-08-20", "--series", "the-brief").exit_code == 0
    after = ledger_of(ws, "the-brief")
    assert len(after["episodes"]) == 3
    for was in legacy()["episodes"]:
        assert was in after["episodes"]


def test_add_keeps_the_ledger_newest_first(brief, ws):
    make_episode(ws)
    assert run("coverage", "add", "2026-08-20", "--series", "the-brief").exit_code == 0
    dates = [e["date"] for e in ledger_of(ws, "the-brief")["episodes"]]
    assert dates == ["2026-08-12", "2026-08-14", "2026-08-20"]


# --- M8: the round trip ----------------------------------------------------------------


@pytest.mark.parametrize(
    "term", ["v4-pro", "V4 Pro", "v4pro", "deepseek", "qwen3.8-max", "QWEN3-8-MAX", "qwen38max"]
)
def test_what_add_wrote_is_what_check_can_find(brief, ws, term):
    """M8, the mutant most likely to be got wrong. `add` and `check` must agree
    about normalisation, or the ledger fills with entries the checker cannot
    see — and that failure is invisible until a story is re-told."""
    make_episode(ws)
    assert hit_count(check(term).output) == 0, "precondition: not covered before"
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    assert hit_count(check(term).output) > 0


def test_the_round_trip_survives_a_story_id_the_ledger_derived(brief, ws):
    """The ids `add` derives must themselves be findable: an id nobody can
    search for is a row nobody can act on."""
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    ids = [s["id"] for s in stories_of(ledger_of(ws, "the-brief")) if "v4" in s["id"]]
    assert ids
    assert hit_count(check(ids[0]).output) > 0


def test_a_story_the_new_episode_did_not_tell_is_still_absent(brief, ws):
    """The round trip's negative half — `add` must not make everything match."""
    make_episode(ws)
    assert run("coverage", "add", "2026-08-20", "--series", "the-brief").exit_code == 0
    r = check("nothing-like-this-9x")
    assert r.exit_code == 0 and "no entry matches" in r.output
    assert hit_count(r.output) == 0


def test_add_writes_a_ledger_the_loader_still_accepts(brief, ws):
    make_episode(ws)
    run("coverage", "add", "2026-08-20", "--series", "the-brief")
    r = run("coverage", "list", "--series", "the-brief")
    assert r.exit_code == 0
    assert "2026-08-20" in r.output


# --- R5's negative half: the pipeline does not write the ledger behind you -------------


def test_render_does_not_record_coverage_as_a_side_effect():
    """An automatic `add` after render records what was *rendered*, not what was
    *published*, and those differ the moment a render is discarded. The
    decision is that the operator writes the ledger; this pins it against the
    module that would otherwise be the convenient place to do it."""
    src = (ROOT / "src" / "agenticsocial" / "video" / "render.py").read_text(encoding="utf-8")
    assert "coverage" not in src


# --- R4: the node command retires, the data survives -----------------------------------


def test_the_node_coverage_command_is_gone():
    assert not (ROOT / "engine" / "coverage.mjs").exists()
    assert not (ROOT / "engine" / "coverage.test.mjs").exists()


def test_the_ledger_data_survives_the_retirement():
    """D-119's shape: the command goes, the data survives. `engine/coverage.json`
    is the migration source and this suite's real-ledger fixture."""
    assert LEGACY.is_file()
    assert len(stories_of(legacy())) == 18


def test_no_document_still_tells_an_author_to_run_the_node_command():
    for path in (
        ROOT / "skills" / "storyboard" / "SKILL.md",
        ROOT / "engine" / "README.md",
        ROOT / "CLAUDE.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "node coverage.mjs" not in text, path
        assert "node engine/coverage.mjs" not in text, path


def test_the_skill_names_the_new_command():
    text = (ROOT / "skills" / "storyboard" / "SKILL.md").read_text(encoding="utf-8")
    assert "uv run agsoc coverage check" in text

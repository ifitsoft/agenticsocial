"""`agsoc video console` — spec §12, screens C and D.

The console is a screen whose whole job is to make a bad claim impossible to
skim past, so almost every test here is about a way it could quietly say
something stronger than the ledger does.

Three habits, each because the matching mutant is a one-line edit:

  * **Every verdict word comes from `verify.classify()` / `binding_verdict()`.**
    Six overclaims in this project (D-106, D-110, D-112, D-118, D-121, D-123)
    were one cause: a second checker was added and the screens summarising the
    first were not moved. The tests below substitute those functions and demand
    the page change — a re-derivation in the template survives anything weaker.
  * **The highlight is asserted against the ORIGINAL bytes.** The fixture source
    is built so the folded offsets and the original offsets differ; an
    implementation that searches the folded text lands two characters off and
    every assertion here still has to fail.
  * **Assert on the element you mean** (D-118). The page is one long string and
    a substring search over the whole of it passes for reasons its author did
    not intend, so the helpers below cut out the one claim's block first.
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agenticsocial.cli import app
from agenticsocial.video import console as console_mod
from agenticsocial.video import corpus
from agenticsocial.video import verify as V
from agenticsocial.video.episode import create_episode, load_episode
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace

runner = CliRunner()


def run(*args):
    """Invoke the CLI, and refuse to let a crash read as a clean refusal (D-035)."""
    result = runner.invoke(app, list(args), catch_exceptions=False)
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"a crash reached the runner: {result.exception!r}"
    )
    return result


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


EP = "2026-08-17"

# The prefix exists to make the folded coordinates and the original coordinates
# disagree: NBSP+space folds to one space (-1), `…` folds to `...` (+2), a
# three-space run folds to one (-2) and `\n\n` folds to one space (-1). Anything
# after it sits at a different index in the folded text than in the file, so a
# highlight computed on the folded string lands on the wrong bytes — M2.
#
# The https URL is here on purpose too: it is source TEXT, and a console that
# prints the source must print it. The no-network test therefore cannot be
# satisfied by `"http" not in html`, which is the assertion that would pass
# while the page loaded a webfont (M1).
SOURCE = (
    "The Brief — sources  log …   2026.\n\n"
    "DeepSeek's 1.6T MoE flagship quietly moved from preview to general "
    "availability this week, then announced new pricing starting August 16 at "
    "about $1.32 / $3.96 per 1M tokens (in/out). Full report at "
    "https://local-ai-zone.example/report/2026-08-17 has the underlying tables.\n\n"
    "Alibaba's Qwen3.8-Max, at roughly 2.4 trillion parameters with about 95B "
    "active, is the largest open-weight release so far."
)

QUOTE = "announced new pricing starting August 16"


def write_script(ep, beats, status="draft"):
    # The id is QUOTED: `episode: 2026-08-17` unquoted is a YAML date.
    body = yaml.safe_dump({"beats": list(beats)}, sort_keys=False, allow_unicode=True)
    ep.script_path.write_text(
        f"---\nepisode: '{ep.id}'\nseries: the-brief\nstatus: {status}\n---\n{body}",
        encoding="utf-8",
    )


def episode(series, beats, sources=None, ep_id=EP, status="draft"):
    ep = create_episode(series, ep_id)
    for key, text in (sources or {"local-ai-zone": SOURCE}).items():
        corpus.write_document(
            ep, text, url=f"https://{key}.example/x", key=key, fetched_at="2026-08-17"
        )
    write_script(ep, beats, status=status)
    return load_episode(series, ep_id)


def clean_beat(**over):
    beat = {
        "type": "statement",
        "act": "cold-open",
        "hold": 3.0,
        "text": "DeepSeek announced new pricing on August 16.",
        "src": "local-ai-zone",
        "quote": QUOTE,
    }
    beat.update(over)
    return beat


def fabricated_beat(**over):
    """A quote that is not in the source at all — the near-miss case (§8.2)."""
    beat = {
        "type": "statement",
        "act": "turn",
        "hold": 3.0,
        "text": "DeepSeek announced new pricing on August 19.",
        "src": "local-ai-zone",
        "quote": "announced new pricing starting August 19",
    }
    beat.update(over)
    return beat


def custom_beat(**over):
    beat = {
        "type": "custom",
        "act": "turn",
        "hold": 3.0,
        "js": "c.fillRect(0,0,10,10)",
        "attest": "Draws the price ladder from the two figures above.",
    }
    beat.update(over)
    return beat


def checked(series, beats, **kw):
    """An episode with a ledger `check` would have written."""
    ep = episode(series, beats, **kw)
    V.write_ledger(ep, V.verify_episode(ep))
    return load_episode(series, kw.get("ep_id", EP))


def console(*args, ep_id=EP, out=None, expect=0):
    """Run the command and return the HTML it wrote."""
    argv = ["video", "console", ep_id, "--series", "the-brief"]
    if out is not None:
        argv += ["--out", str(out)]
    argv += list(args)
    result = run(*argv)
    assert result.exit_code == expect, result.output
    if expect != 0:
        return result.output
    path = _written_path(result.output)
    return path.read_text(encoding="utf-8")


def _written_path(output: str) -> Path:
    match = re.search(r"(\S+\.html)", output)
    assert match, f"the command did not say where it wrote the file:\n{output}"
    return Path(match.group(1))


# --- reading the page back --------------------------------------------------------


class _Page(HTMLParser):
    """Enough of a parser to ask where the page would go for bytes."""

    FETCHING = ("src", "href", "srcset", "data", "poster", "action", "formaction")

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.urls: list[tuple[str, str, str]] = []  # (tag, attr, value)
        self.attrs: list[tuple[str, str, str]] = []
        self.styles: list[str] = []
        self.marks: list[str] = []
        self.meta: list[dict] = []
        self._style = False
        self._mark = 0
        self._buf: list[str] = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for key, value in attrs:
            value = value or ""
            self.attrs.append((tag, key.lower(), value))
            if key.lower() in self.FETCHING:
                self.urls.append((tag, key.lower(), value))
            if key.lower() == "style":
                self.styles.append(value)
        if tag == "meta":
            self.meta.append({k.lower(): (v or "") for k, v in attrs})
        if tag == "style":
            self._style = True
        if tag == "mark":
            self._mark += 1
            self._buf = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "style":
            self._style = False
        if tag == "mark" and self._mark:
            self._mark -= 1
            self.marks.append("".join(self._buf))

    def handle_data(self, data):
        if self._style:
            self.styles.append(data)
        if self._mark:
            self._buf.append(data)


def block(html: str, element_id: str) -> str:
    """One element's own markup, by id — never the whole page (D-118).

    An assertion that searches the whole console for a small string passes for
    reasons its author did not intend; every claim-level assertion below cuts
    the claim out first.
    """
    match = re.search(
        rf'<(?P<tag>\w+)[^>]*\bid="{re.escape(element_id)}"(?P<rest>.*?)</(?P=tag)>',
        html,
        re.DOTALL,
    )
    assert match, f"no element with id={element_id!r} in the page"
    return match.group(0)


def csp(html: str) -> str:
    for meta in _Page(html).meta:
        if meta.get("http-equiv", "").lower() == "content-security-policy":
            return meta.get("content", "")
    return ""


# --- R1 / M1: one file, and it never reaches the network ---------------------------


def test_the_command_writes_one_self_contained_html_file(series, tmp_path):
    """precondition: everything else in this file is about a page that exists."""
    checked(series, [clean_beat()])
    out = tmp_path / "console.html"
    html = console(out=out)
    assert out.is_file()
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert list(out.parent.iterdir()) == [out], "the console is ONE file"


def test_no_attribute_on_the_page_points_off_the_machine(series, tmp_path):
    """precondition: M1. R1 is not "I did not add a CDN" — it is a property of
    the bytes, so this asks every fetchable attribute where it would go.

    The fixture source contains an https URL as TEXT, so a page that prints its
    sources contains "https://" and the cheap assertion is useless."""
    checked(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    assert "https://local-ai-zone.example/report" in html, (
        "the source text must be on the page, or this test proves nothing"
    )
    page = _Page(html)
    for tag, attr, value in page.urls:
        assert value.startswith(("#", "data:")) or value == "", (
            f"<{tag} {attr}={value!r}> would fetch from off the page"
        )
    assert "script" not in page.tags
    assert "iframe" not in page.tags
    for style in page.styles:
        assert "@import" not in style
        assert not re.search(r"url\(\s*['\"]?(?!data:)[a-z]+:", style, re.I), style


def test_the_page_carries_a_csp_that_refuses_by_default(series, tmp_path):
    """precondition: M1's other half — D-089 put the policy in `scene.html`
    rather than in the runner because the page is also opened by hand. A console
    opened from `file://` is exactly that case."""
    checked(series, [clean_beat()])
    policy = csp(console(out=tmp_path / "c.html"))
    assert "default-src 'none'" in policy
    assert "form-action 'none'" in policy
    assert "script-src" not in policy, (
        "the page has no JavaScript; naming script-src would only permit some"
    )
    assert "http" not in policy


def test_the_source_text_is_escaped_not_interpreted(series, tmp_path):
    """precondition: the corpus is fetched text and the script is agent-written
    (D-089's threat chain). A console that renders either as markup is a page
    whose content decides what the page says."""
    hostile = "Prices <script>alert(1)</script> & \"quotes\" fell to 5% today."
    checked(
        series,
        [clean_beat(text="Prices fell to 5% today.", quote="Prices <script>alert(1)")],
        sources={"local-ai-zone": hostile},
    )
    html = console(out=tmp_path / "c.html")
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# --- R2 / M2 / M3: the highlight, in the original bytes, in context ------------------


def test_the_fixture_really_does_shift_under_folding(series):
    """precondition: this test is the reason M2 is detectable at all. If the
    folded and original offsets agreed, every assertion about the highlight
    would pass against an implementation that searched the folded text."""
    folded, _ = V.fold_spans(SOURCE)
    original = V.quote_span(QUOTE, SOURCE)
    assert original is not None
    assert folded.find(V._needle(QUOTE)) != original[0], (
        "the fixture no longer distinguishes folded coordinates from real ones"
    )


def test_the_highlight_covers_exactly_the_bytes_quote_span_names(series, tmp_path):
    """precondition: R2, and the reason Phase 5 computed spans against the
    original text rather than the folded text (§8.2.1). The marked characters
    must be the file's own bytes, not a re-search of anything."""
    checked(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    span = V.quote_span(QUOTE, SOURCE)
    assert _Page(html).marks, "nothing is highlighted at all"
    assert SOURCE[span[0] : span[1]] in _Page(html).marks


def test_the_highlight_is_surrounded_by_the_source_it_was_taken_from(series, tmp_path):
    """precondition: M3 and R2's negative half. "Verbatim but torn from context"
    is §8.3's own failure mode; a quote highlighted with nothing around it is
    that failure shipped as a feature."""
    checked(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    span = V.quote_span(QUOTE, SOURCE)
    excerpt = block(html, "excerpt-c-001")
    before = SOURCE[max(0, span[0] - 60) : span[0]].strip()
    after = SOURCE[span[1] : span[1] + 60].strip()
    assert before and after
    assert before.split()[-1] in excerpt, "no source before the quote"
    assert after.split()[0] in excerpt, "no source after the quote"


def test_a_missing_quote_shows_the_near_miss_and_never_calls_it_the_quote(
    series, tmp_path
):
    """precondition: §8.2 — "near-misses report as failures with the closest
    candidate span attached, so the human sees WHY rather than a bare red mark."
    Labelling the near miss as the supporting quote would be the worst of both."""
    checked(series, [fabricated_beat()])
    html = console(out=tmp_path / "c.html")
    excerpt = block(html, "excerpt-c-001")
    assert "closest" in excerpt.lower()
    assert "not found" in excerpt.lower() or "no supporting quote" in excerpt.lower()
    span = V.closest_span("announced new pricing starting August 19", SOURCE)
    assert span is not None
    assert SOURCE[span[0] : span[1]] in _Page(excerpt).marks


# --- R3 / M4: the verdict words come from `verify`, or they are re-derived -----------


def test_the_claim_state_is_whatever_classify_returns(series, tmp_path, monkeypatch):
    """precondition: M4. `classify` is the single place §8.4's list is spelled
    out (D-113); a template that re-derives it is a second checker, and every
    one of this project's six overclaims was a second checker."""
    checked(series, [clean_beat()])
    monkeypatch.setattr(console_mod, "classify", lambda record: "zzsentinelstate")
    html = console(out=tmp_path / "c.html")
    assert "zzsentinelstate" in block(html, "claim-c-001")


def test_the_verdict_word_is_whatever_binding_verdict_returns(
    series, tmp_path, monkeypatch
):
    """precondition: M4's other half — `binding_verdict` is the one word the
    pipeline says about a claim (D-123), and the console is all summary lines."""
    checked(series, [clean_beat()])
    monkeypatch.setattr(console_mod, "binding_verdict", lambda record: "zzsentinelword")
    html = console(out=tmp_path / "c.html")
    assert "zzsentinelword" in block(html, "claim-c-001")


def test_a_refuted_claim_never_shows_a_bare_pass(series, tmp_path):
    """precondition: D-123, the sixth overclaim. A refuted claim's MECHANICAL
    verdict is `pass` — that is what pass 2 is for — so a screen built on the
    measurement puts a green word on the line the gate refuses."""
    ep = checked(series, [clean_beat()])
    V.record_adversarial(
        ep,
        "c-001",
        verdict="refuted",
        attempted_refutation="The source dates the price change to a different product.",
        by="Ali Abdukarim",
    )
    html = console(out=tmp_path / "c.html")
    claim = block(html, "claim-c-001")
    assert "refuted" in claim
    assert re.search(r"pass 1[^<]*pass|pass 1</\w+>\s*<[^>]*>pass", claim), (
        "pass 1's verdict is reported, and it is labelled `pass 1`"
    )
    assert not re.search(r'class="[^"]*verdict[^"]*"[^>]*>\s*pass\s*<', claim), (
        "the binding verdict cell says `refuted`, never a bare `pass`"
    )


def test_the_console_never_compares_against_a_pass_1_verdict_word(series):
    """precondition: M4 by construction. Pass 1's verdict is REPORTED by this
    module and never branched on — a comparison here is the beginning of a
    second mapping (D-123's AST test, same argument)."""
    src = Path(console_mod.__file__).read_text(encoding="utf-8")
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    for word in ("pass", "fail", "no_source", "manual", "supported", "refuted"):
        assert f'== "{word}"' not in code and f'!= "{word}"' not in code, word
        assert f'in ("{word}"' not in code, word


# --- R6 / M5 / M6 / M7: attested is not verified, a judgement is not a measurement ---


def test_a_manual_claim_reads_as_attested_and_shows_the_sentence(series, tmp_path):
    """precondition: M5, D-088 and D-121. Nothing mechanical looked at what a
    `custom` beat draws; the approval rests on a person's sentence, so the
    screen has to show the sentence."""
    checked(series, [custom_beat()])
    html = console(out=tmp_path / "c.html")
    claim = block(html, "claim-c-001")
    assert "attested" in claim
    assert "NOT verified" in claim
    assert "Draws the price ladder from the two figures above." in claim
    assert not re.search(r'class="[^"]*state[^"]*"[^>]*>\s*verified\s*<', claim)


def test_an_unattested_manual_claim_is_open_and_says_what_is_missing(series, tmp_path):
    """precondition: M5's negative half — `attested` is earned by the sentence,
    not by the beat type."""
    ep = episode(series, [custom_beat()])
    ledger = V.verify_episode(ep)
    ledger["claims"][0]["mechanical"]["attest"] = ""
    V.write_ledger(ep, ledger)
    claim = block(console(out=tmp_path / "c.html"), "claim-c-001")
    assert "open" in claim
    assert "attested" not in claim.replace("unattested", "")


def _support(ep, claim_id="c-001", risk=None):
    V.record_adversarial(
        ep,
        claim_id,
        verdict="supported",
        attempted_refutation="Checked the date against the two other sources.",
        residual_risk=risk,
        by="Ali Abdukarim",
    )


def test_a_pass_2_supported_claim_is_marked_as_a_judgement(series, tmp_path):
    """precondition: M6 and D-121. Pass 1 re-runs to the same answer in a year
    and pass 2 does not; a reader who cannot tell them apart trusts them
    equally."""
    ep = checked(series, [clean_beat()])
    _support(ep)
    claim = block(console(out=tmp_path / "c.html"), "claim-c-001")
    assert "NOT a measurement" in claim
    assert "judgement" in claim
    assert "Ali Abdukarim" in claim
    assert "Checked the date against the two other sources." in claim


def test_a_judged_claim_is_styled_apart_from_a_mechanical_pass(series, tmp_path):
    """precondition: M6 stated as the mutant does — "styled identically". The
    distinction has to reach the markup, not only the prose."""
    ep = checked(series, [clean_beat(), clean_beat(text="Pricing started August 16.")])
    _support(ep, "c-002")
    html = console(out=tmp_path / "c.html")
    plain = set(re.findall(r'class="([^"]+)"', block(html, "claim-c-001")))
    judged = set(re.findall(r'class="([^"]+)"', block(html, "claim-c-002")))
    assert judged - plain, "a judged claim carries no class a measured one does not"
    css = "\n".join(_Page(html).styles)
    for extra in judged - plain:
        for name in extra.split():
            if name.startswith("judg") or name.startswith("pass2"):
                assert f".{name}" in css
                break


def test_residual_risk_is_shown_on_a_supported_claim(series, tmp_path):
    """precondition: M7. §8.3 calls `residual_risk` often the most useful output
    of the whole pass, and Phase 9 found one on a SUPPORTED claim that ages into
    falsity. A risk shown only on failures is a risk nobody reads."""
    ep = checked(series, [clean_beat()])
    _support(ep, risk="The source does not state an effective date.")
    claim = block(console(out=tmp_path / "c.html"), "claim-c-001")
    assert "The source does not state an effective date." in claim
    assert "residual risk" in claim.lower()


def test_pass_2_coverage_is_reported_even_at_zero(series, tmp_path):
    """precondition: D-121's ruling — `unjudged` is reported, not gated, so an
    episode signed with pass 2 never run must not look like one pass 2 cleared."""
    checked(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    assert "0 of 1 claim judged" in html


# --- R5 / M8: a stale ledger --------------------------------------------------------


def test_a_stale_ledger_is_unmistakable_and_no_verdict_is_shown(series, tmp_path):
    """precondition: M8. A stale ledger is worse than an absent one because it
    looks like verification — `review` answers this by showing no verdicts at
    all, and a console with better typography must not answer it more softly."""
    ep = checked(series, [clean_beat()])
    write_script(ep, [clean_beat(text="DeepSeek announced new pricing in August.")])
    html = console(out=tmp_path / "c.html")
    assert "STALE" in html
    assert V.stale_reason(load_episode(series, EP), V.read_ledger(ep)) is not None
    page = _Page(html)
    assert not re.search(r'class="[^"]*\bverdict\b[^"]*"', html), (
        "no verdict may reach the screen from a ledger nothing can trust"
    )
    assert not page.marks, "and no highlight either — the spans describe old words"


def test_a_current_ledger_is_shown_without_a_staleness_banner(series, tmp_path):
    """precondition: M8's negative half — R5 says a current ledger is shown
    WITHOUT noise, and a banner on every episode is one nobody reads."""
    checked(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    assert "STALE" not in html
    assert re.search(r'class="[^"]*\bverdict\b[^"]*"', html)


def test_an_absent_ledger_says_run_check_and_does_not_shout(series, tmp_path):
    """precondition: "not checked yet" is the normal state of a fresh script,
    and a screen that shouts about it is a screen whose shouting gets tuned
    out — taking the stale case with it."""
    episode(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    assert "agsoc video check" in html
    assert "STALE" not in html


# --- R4 / M9 / M10: it writes nothing, and it cannot approve ------------------------


def _tree(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_the_console_writes_nothing_into_the_episode_directory(series, tmp_path):
    """precondition: M9 and R4. Reading a ledger is safe; writing one makes a
    second writer, and this project has a decision about second writers
    (D-059, D-113)."""
    ep = checked(series, [clean_beat(), custom_beat()])
    before = _tree(ep.dir)
    console(out=tmp_path / "c.html")
    assert _tree(ep.dir) == before


def test_the_console_refuses_to_write_inside_the_workspace(series, ws):
    """precondition: M9 stated as a refusal rather than as a habit. The default
    path is outside `workspace/` and so is every path it will accept."""
    ep = checked(series, [clean_beat()])
    before = _tree(ws.root)
    output = console(out=ep.dir / "console.html", expect=1)
    assert "workspace" in output
    assert _tree(ws.root) == before


def test_the_default_path_is_outside_the_workspace(series, ws, tmp_path):
    """precondition: M9's default half — a refusal is worthless if the ordinary
    invocation writes there anyway."""
    checked(series, [clean_beat()])
    result = run("video", "console", EP, "--series", "the-brief")
    assert result.exit_code == 0, result.output
    path = _written_path(result.output)
    assert path.is_file()
    assert ws.root.resolve() not in path.resolve().parents


def test_the_page_has_no_action_of_any_kind(series, tmp_path):
    """precondition: M10 and D-059. A second way to approve is precisely the
    defect Phase 7 spent three tasks eliminating, so the page carries nothing
    that could become one."""
    ep = checked(series, [clean_beat()])
    _support(ep)
    page = _Page(console(out=tmp_path / "c.html"))
    for forbidden in ("form", "button", "input", "textarea", "select"):
        assert forbidden not in page.tags
    for tag, attr, value in page.attrs:
        assert not attr.startswith("on"), f"<{tag} {attr}> is an event handler"
    for tag, attr, value in page.urls:
        assert not value.lower().startswith("javascript:")


def test_the_console_module_cannot_run_a_command(series):
    """precondition: M10 by construction — the console PRINTS the command. A
    module that can spawn a process is one edit away from running it."""
    src = Path(console_mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "approve_episode", "set_status"):
        assert forbidden not in src, forbidden


def test_the_page_prints_the_approve_command_it_will_not_run(series, tmp_path):
    """precondition: R4's negative half. The console links to the gate; the gate
    takes identifiers and loads from disk (D-072)."""
    checked(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    assert f"agsoc video approve {EP} --series the-brief --by" in html


# --- screen D: override is authored, not clicked ------------------------------------


def test_an_open_claim_gets_an_adjudication_block(series, tmp_path):
    """precondition: §12's screen D — the state the operator is in when `check`
    came back with failures: what was asserted, what the source says, why each
    pass ruled as it did."""
    checked(series, [fabricated_beat()])
    adj = block(console(out=tmp_path / "c.html"), "adjudicate-c-001")
    assert "DeepSeek announced new pricing on August 19." in adj  # what was asserted
    assert "local-ai-zone" in adj  # what it was checked against
    assert "why" in adj.lower()


def test_the_override_is_shown_as_a_statement_with_the_diff_it_will_make(
    series, tmp_path
):
    """precondition: §12 — "it requires a typed reason and is presented as
    authoring an on-the-record statement, not clicking accept. Show it will land
    in the file as a diff." §8.4's asymmetry is the whole design."""
    checked(series, [fabricated_beat()])
    adj = block(console(out=tmp_path / "c.html"), "adjudicate-c-001")
    assert "claim_override:" in adj
    assert "reason:" in adj and "by:" in adj
    assert "+" in adj, "the YAML is shown as the diff it will make"
    assert "script.yaml" in adj
    assert "NOT verified" in adj


def test_the_adjudication_shows_the_refuters_reasoning(series, tmp_path):
    """precondition: §12's screen D — "the refuter's reasoning for adversarial
    ones". A pass-2 refusal an operator cannot read is one they override
    blind."""
    ep = checked(series, [clean_beat()])
    V.record_adversarial(
        ep,
        "c-001",
        verdict="unsupported",
        attempted_refutation="The August 16 date belongs to a different product line.",
        by="Ali Abdukarim",
    )
    adj = block(console(out=tmp_path / "c.html"), "adjudicate-c-001")
    assert "The August 16 date belongs to a different product line." in adj
    assert "unsupported" in adj


def test_a_written_override_is_shown_with_the_name_on_it(series, tmp_path):
    """precondition: §8.4 — the approval rests on the sentence and the name, so
    the one screen before approval must show both (D-088's argument, D-123's
    finding about the verdict beside them)."""
    checked(
        series,
        [
            fabricated_beat(
                claim_override={
                    "reason": "The source's own correction notice gives August 19.",
                    "by": "Ali Abdukarim",
                }
            )
        ],
    )
    claim = block(console(out=tmp_path / "c.html"), "claim-c-001")
    assert "The source's own correction notice gives August 19." in claim
    assert "Ali Abdukarim" in claim
    assert "overridden" in claim
    assert "NOT verified" in claim


# --- the rest of screen C ------------------------------------------------------------


def test_beats_are_grouped_by_act(series, tmp_path):
    """precondition: §12's screen C — "ordered beats grouped by act"."""
    checked(series, [clean_beat(), fabricated_beat(), custom_beat()])
    html = console(out=tmp_path / "c.html")
    assert block(html, "act-cold-open")
    assert block(html, "act-turn")
    assert html.index('id="act-cold-open"') < html.index('id="act-turn"')


def test_every_beat_carries_its_hold_and_the_runtime_is_reported(series, tmp_path):
    """precondition: §12's screen C — hold per beat, and a running total against
    the series' target_sec."""
    checked(series, [clean_beat(hold=4.5)])
    html = console(out=tmp_path / "c.html")
    assert "4.5" in block(html, "beat-0")
    assert "120" in html  # the scaffolded target
    assert "OUT OF TOLERANCE" in html  # one beat is nowhere near 120s


def test_an_episode_rendered_but_never_recorded_is_surfaced(series, tmp_path):
    """precondition: Phase 11's gap — `check` cannot tell "not covered" from
    "covered but never recorded", and nothing nags after a render. The console
    is the one screen that reads both files."""
    ep = checked(series, [clean_beat()], status="rendered")
    html = console(out=tmp_path / "c.html")
    assert "coverage" in html.lower()
    assert "not recorded" in html.lower()
    assert "agsoc coverage add" in html


def test_a_probe_frame_on_disk_is_embedded_and_dated(series, tmp_path):
    """precondition: the plan's own compromise — §12 asks for the live engine in
    an iframe, and frames on disk are what exist. They are embedded (R1) and
    labelled with when they were drawn, because a frame older than the script is
    a picture of something else."""
    ep = checked(series, [clean_beat()])
    ep.probe_dir.mkdir(parents=True, exist_ok=True)
    png = bytes.fromhex("89504e470d0a1a0a") + b"probe-frame-bytes"
    (ep.probe_dir / "s00.png").write_bytes(png)
    html = console(out=tmp_path / "c.html")
    assert "data:image/png;base64," in html
    assert "s00.png" in html


def test_without_a_probe_the_page_prints_the_command_that_draws_one(series, tmp_path):
    """precondition: D-116 — nothing can extend the approval over the pixels, so
    the console says how to look at them rather than implying it has."""
    checked(series, [clean_beat()])
    html = console(out=tmp_path / "c.html")
    assert f"agsoc video probe {EP}" in html
    assert "data:image/png" not in html


def test_an_unreadable_script_refuses_rather_than_writing_half_a_page(series, tmp_path):
    """precondition: D-018's shape — but a console built from a file nobody
    parsed is worse than no console. It refuses, and says why."""
    ep = create_episode(series, EP)
    ep.script_path.write_text("---\nepisode: '2026-08-17'\n---\nbeats: 4\n", "utf-8")
    out = tmp_path / "c.html"
    output = console(out=out, expect=1)
    assert not out.exists()
    assert "beats" in output


def test_an_unknown_episode_refuses(series, tmp_path):
    """precondition: the ordinary typo, and it must not traceback (D-035)."""
    output = console(ep_id="2026-01-01", out=tmp_path / "c.html", expect=1)
    assert "2026-01-01" in output

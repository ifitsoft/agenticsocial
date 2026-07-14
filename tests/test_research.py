from agenticsocial.research import build_brief


RESULTS = [
    {"title": "Kill your staging env", "href": "https://ex.com/a", "body": "Why staging lies."},
    {"title": "Progressive delivery 101", "href": "https://ex.com/b", "body": "Flags and rollouts."},
]


def test_build_brief_lists_results_with_citations():
    brief = build_brief("Kill staging", "staging environments", RESULTS, {})
    assert brief.startswith("# Brief: Kill staging")
    assert "staging environments" in brief
    assert "https://ex.com/a" in brief
    assert "Why staging lies." in brief
    assert "## Search results" in brief


def test_build_brief_includes_extracted_articles():
    brief = build_brief("T", "q", [], {"https://ex.com/full": "Full article text here."})
    assert "## Extracted: https://ex.com/full" in brief
    assert "Full article text here." in brief


def test_build_brief_truncates_long_extracts():
    brief = build_brief("T", "q", [], {"https://ex.com/big": "x" * 20000})
    assert len(brief) < 12000
    assert "truncated" in brief

"""The suite must not reach the network, whatever the code under test does.

A socket guard is not sufficient: ddgs fetches through primp, a Rust HTTP client
that never touches Python's socket module. The guard has to sit on the seam this
project owns -- research.search and research.extract are its only two fetch
calls.
"""
import pytest

from agenticsocial import research


def test_research_search_is_blocked_in_tests():
    """precondition: nothing in this test patches research.search. If this ever
    fails, a suite run can reach duckduckgo and hang rather than fail."""
    with pytest.raises(Exception) as e:
        research.search("gemini pricing", max_results=1)
    assert "network" in str(e.value).lower()


def test_research_extract_is_blocked_in_tests():
    """precondition: nothing in this test patches research.extract."""
    with pytest.raises(Exception) as e:
        research.extract("https://example.com/a")
    assert "network" in str(e.value).lower()


def test_a_test_can_still_install_its_own_fake(monkeypatch):
    """NEGATIVE half: the guard must not stop a test injecting a fake. It runs
    first; a test's own patch wins afterwards."""
    monkeypatch.setattr(research, "search", lambda q, max_results=8: [{"href": "x"}])
    assert research.search("q") == [{"href": "x"}]

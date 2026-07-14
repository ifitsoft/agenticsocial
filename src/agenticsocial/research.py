"""Deterministic research fetching. No LLM calls — the agent reads the brief."""
from __future__ import annotations

from datetime import datetime

EXTRACT_CHAR_LIMIT = 8000


def search(query: str, max_results: int = 8) -> list[dict]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        return [
            {"title": r.get("title", ""), "href": r.get("href", ""), "body": r.get("body", "")}
            for r in ddgs.text(query, max_results=max_results)
        ]


def extract(url: str) -> str | None:
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    return trafilatura.extract(downloaded)


def build_brief(title: str, query: str, results: list[dict], extracts: dict[str, str]) -> str:
    fetched = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        f"# Brief: {title}",
        "",
        f"_Query: {query} · fetched {fetched}_",
        "",
    ]
    if results:
        lines += ["## Search results", ""]
        for i, r in enumerate(results, 1):
            lines += [f"### {i}. {r['title']}", f"<{r['href']}>", "", r["body"], ""]
    for url, text in extracts.items():
        if len(text) > EXTRACT_CHAR_LIMIT:
            text = text[:EXTRACT_CHAR_LIMIT] + "\n\n_[truncated]_"
        lines += [f"## Extracted: {url}", "", text, ""]
    return "\n".join(lines)

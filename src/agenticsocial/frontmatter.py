"""Markdown files with a YAML frontmatter block delimited by `---` lines."""
from __future__ import annotations

import yaml


def parse(text: str) -> tuple[dict, str]:
    """Split a document into (metadata, body).

    Documents without a well-formed frontmatter block parse as ({}, text).
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    return meta, text[end + 5 :]


def dump(meta: dict, body: str) -> str:
    header = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{header}\n---\n{body}"

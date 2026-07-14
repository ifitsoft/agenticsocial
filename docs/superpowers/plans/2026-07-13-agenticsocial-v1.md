# agenticsocial v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `agsoc` CLI — a local-first, agent-driven content pipeline that captures sources, gathers research briefs, enforces a human approval gate, and publishes threads to X via the official API.

**Architecture:** A "dumb" Python CLI owns storage (markdown + YAML frontmatter in a workspace directory), deterministic research fetching, credential handling (OS keychain), and X publishing with resume support. It makes no LLM calls; bundled agent skills teach Claude Code (or any agentic CLI) the drafting workflow. Status transitions are enforced only by the CLI so nothing posts without human approval.

**Tech Stack:** Python 3.11+, `uv` + hatchling packaging, `typer` (CLI), `pyyaml`, `httpx`, `keyring`, `ddgs` (DuckDuckGo search), `trafilatura` (article extraction), `pytest` + `respx` (tests).

**Spec:** `docs/superpowers/specs/2026-07-13-agenticsocial-v1-design.md`

## Global Constraints

- Python floor: `requires-python = ">=3.11"`.
- Package name on PyPI: `agenticsocial`; import package: `agenticsocial`; CLI binary: `agsoc`.
- The CLI makes **no LLM calls** anywhere.
- Workspace default path: `./workspace`, overridable via `AGSOC_WORKSPACE` env var.
- Variant status vocabulary (exact strings): `draft`, `in_review`, `approved`, `scheduled`, `publishing`, `published`, `failed`. `scheduled` is reserved (no transitions in v1).
- Only the CLI transitions statuses; `in_review → approved` only via `agsoc approve`; only `approved` (or `failed` via `--resume`) variants can be posted.
- Thread delimiter inside variant bodies (exact string, on its own line): `---tweet---`.
- Tweet limit 280 weighted chars; every URL counts as 23.
- Tokens live only in the OS keychain (service `agenticsocial`, account `x`) — never in workspace files.
- All workspace writes are atomic (temp file + `os.replace`).
- X API endpoints: authorize `https://x.com/i/oauth2/authorize`, token `https://api.x.com/2/oauth2/token`, tweets `https://api.x.com/2/tweets`. OAuth scopes: `tweet.read tweet.write users.read offline.access`. Redirect URI: `http://localhost:8721/callback`.
- Tests must not hit the network. HTTP is mocked with `respx`; search/extract libraries are monkeypatched.
- Run everything through `uv run` (e.g. `uv run pytest`, `uv run agsoc`).
- Commit messages: conventional style (`feat:`, `test:`, `chore:`, `docs:`), each ending with the trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## File Structure

```
pyproject.toml
src/agenticsocial/
  __init__.py          # __version__
  cli.py               # typer app, all commands
  frontmatter.py       # parse/dump markdown + YAML frontmatter
  textutils.py         # slugify, split_thread, weighted_length
  models.py            # Status enum, transitions, Source/Variant dataclasses
  workspace.py         # Workspace class: scaffold, sources, variants, status enforcement
  research.py          # search + extraction → brief markdown
  x/
    __init__.py
    auth.py            # OAuth 2.0 PKCE flow + keyring storage
    client.py          # XClient: post_tweet
    publish.py         # validate_thread, publish_variant (resume-safe)
skills/
  fanout/SKILL.md
  capture/SKILL.md
  repurpose/SKILL.md
tests/
  test_frontmatter.py test_textutils.py test_models.py test_workspace.py
  test_cli.py test_auth.py test_x_client.py test_publish.py test_research.py
```

---

### Task 1: Package scaffold & CLI entry point

**Files:**
- Create: `pyproject.toml`, `src/agenticsocial/__init__.py`, `src/agenticsocial/cli.py`, `tests/test_cli.py`
- Modify: `.gitignore` (append workspace entry)

**Interfaces:**
- Consumes: nothing.
- Produces: `agenticsocial.__version__: str`; `agenticsocial.cli.app` (a `typer.Typer` instance) that later tasks register commands on; `agsoc` console script.

- [ ] **Step 1: Write pyproject and package init**

`pyproject.toml`:

```toml
[project]
name = "agenticsocial"
version = "0.1.0"
description = "Local-first, agent-driven content pipeline: capture, research, draft, review, post."
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "keyring>=25.0",
    "ddgs>=9.0",
    "trafilatura>=1.12",
]

[project.scripts]
agsoc = "agenticsocial.cli:app"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "respx>=0.21",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agenticsocial"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`src/agenticsocial/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/agenticsocial/cli.py`:

```python
"""agsoc — local-first content pipeline CLI."""
from __future__ import annotations

import typer

from . import __version__

app = typer.Typer(
    help="Capture sources, research, review drafts, and post to X. The agent drafts; you approve.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the agsoc version."""
    typer.echo(__version__)
```

Append to `.gitignore`:

```
# agenticsocial content workspace (personal content, not part of the repo)
workspace/
```

- [ ] **Step 2: Write the failing test**

`tests/test_cli.py`:

```python
from typer.testing import CliRunner

from agenticsocial import __version__
from agenticsocial.cli import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output
```

- [ ] **Step 3: Sync and run the test**

Run: `uv sync && uv run pytest tests/test_cli.py -v`
Expected: PASS (scaffold and test land together; the meaningful check is that packaging, entry point, and imports all resolve).

- [ ] **Step 4: Sanity-check the console script**

Run: `uv run agsoc version`
Expected output: `0.1.0`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src tests .gitignore
git commit -m "feat: scaffold agenticsocial package with agsoc CLI entry point"
```

---

### Task 2: Frontmatter module

**Files:**
- Create: `src/agenticsocial/frontmatter.py`
- Test: `tests/test_frontmatter.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `frontmatter.parse(text: str) -> tuple[dict, str]` and `frontmatter.dump(meta: dict, body: str) -> str`. Round-trip stable; `parse` on a document without frontmatter returns `({}, text)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_frontmatter.py`:

```python
from agenticsocial import frontmatter


def test_parse_splits_meta_and_body():
    text = "---\nplatform: x\nstatus: draft\n---\nHello world\n"
    meta, body = frontmatter.parse(text)
    assert meta == {"platform": "x", "status": "draft"}
    assert body == "Hello world\n"


def test_parse_without_frontmatter_returns_empty_meta():
    meta, body = frontmatter.parse("just text\n")
    assert meta == {}
    assert body == "just text\n"


def test_parse_unclosed_frontmatter_treated_as_body():
    text = "---\nbroken: yes\nno closing delimiter\n"
    meta, body = frontmatter.parse(text)
    assert meta == {}
    assert body == text


def test_roundtrip_preserves_meta_and_body():
    meta = {"platform": "x", "status": "draft", "posted_ids": [], "posted_url": None}
    body = "Tweet one\n\n---tweet---\n\nTweet two\n"
    meta2, body2 = frontmatter.parse(frontmatter.dump(meta, body))
    assert meta2 == meta
    assert body2 == body


def test_dump_preserves_key_order():
    meta = {"z": 1, "a": 2}
    assert frontmatter.dump(meta, "").index("z:") < frontmatter.dump(meta, "").index("a:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_frontmatter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.frontmatter'`

- [ ] **Step 3: Implement**

`src/agenticsocial/frontmatter.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_frontmatter.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/frontmatter.py tests/test_frontmatter.py
git commit -m "feat: add YAML frontmatter parse/dump"
```

---

### Task 3: Text utilities

**Files:**
- Create: `src/agenticsocial/textutils.py`
- Test: `tests/test_textutils.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `slugify(title: str) -> str`; `split_thread(body: str) -> list[str]`; `weighted_length(text: str) -> int`; constants `TWEET_LIMIT = 280`, `URL_WEIGHT = 23`, `THREAD_DELIM = "---tweet---"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_textutils.py`:

```python
from agenticsocial.textutils import (
    TWEET_LIMIT,
    URL_WEIGHT,
    slugify,
    split_thread,
    weighted_length,
)


def test_slugify_basic():
    assert slugify("The Staging Environment is a LIE!") == "the-staging-environment-is-a-lie"


def test_slugify_truncates_and_never_empty():
    assert len(slugify("x " * 100)) <= 60
    assert slugify("!!!") == "untitled"


def test_split_thread_on_delimiter():
    body = "Tweet one\n\n---tweet---\n\nTweet two\n\n---tweet---\nTweet three"
    assert split_thread(body) == ["Tweet one", "Tweet two", "Tweet three"]


def test_split_thread_single_tweet():
    assert split_thread("Just one post\n") == ["Just one post"]


def test_split_thread_ignores_empty_segments():
    assert split_thread("A\n\n---tweet---\n\n\n---tweet---\n\nB") == ["A", "B"]


def test_weighted_length_plain_text():
    assert weighted_length("hello") == 5


def test_weighted_length_counts_urls_as_23():
    text = "read this: https://example.com/a-very-long-path-that-goes-on-forever"
    assert weighted_length(text) == len("read this: ") + URL_WEIGHT


def test_tweet_limit_constant():
    assert TWEET_LIMIT == 280
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_textutils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.textutils'`

- [ ] **Step 3: Implement**

`src/agenticsocial/textutils.py`:

```python
"""Deterministic text helpers: slugs, thread splitting, X-weighted length."""
from __future__ import annotations

import re

TWEET_LIMIT = 280
URL_WEIGHT = 23  # X wraps every URL in t.co, which always counts as 23 chars
THREAD_DELIM = "---tweet---"

_URL_RE = re.compile(r"https?://\S+")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-") or "untitled"


def split_thread(body: str) -> list[str]:
    """Split on lines containing only the delimiter; drop empty segments."""
    segments: list[list[str]] = [[]]
    for line in body.splitlines():
        if line.strip() == THREAD_DELIM:
            segments.append([])
        else:
            segments[-1].append(line)
    tweets = ["\n".join(seg).strip() for seg in segments]
    return [t for t in tweets if t]


def weighted_length(text: str) -> int:
    """Approximate X character weighting: URLs are 23, everything else 1.

    (CJK double-weighting is not modeled in v1.)
    """
    stripped, n_urls = _URL_RE.subn("", text)
    return len(stripped) + n_urls * URL_WEIGHT
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_textutils.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/textutils.py tests/test_textutils.py
git commit -m "feat: add slugify, thread splitting, and weighted tweet length"
```

---

### Task 4: Status model & transitions

**Files:**
- Create: `src/agenticsocial/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Status(str, Enum)` with members `DRAFT/IN_REVIEW/APPROVED/SCHEDULED/PUBLISHING/PUBLISHED/FAILED`; `ALLOWED_TRANSITIONS: dict[Status, set[Status]]`; `assert_transition(current: Status, target: Status) -> None` raising `TransitionError` (message names allowed next states); dataclasses `Source(id, type, title, dir, origin_url, created)` and `Variant(platform, status, meta, body, path)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:

```python
import pytest

from agenticsocial.models import Status, TransitionError, assert_transition


def test_status_values_match_spec():
    assert [s.value for s in Status] == [
        "draft", "in_review", "approved", "scheduled",
        "publishing", "published", "failed",
    ]


@pytest.mark.parametrize(
    "current,target",
    [
        (Status.DRAFT, Status.IN_REVIEW),
        (Status.IN_REVIEW, Status.DRAFT),
        (Status.IN_REVIEW, Status.APPROVED),
        (Status.APPROVED, Status.IN_REVIEW),
        (Status.APPROVED, Status.PUBLISHING),
        (Status.PUBLISHING, Status.PUBLISHED),
        (Status.PUBLISHING, Status.FAILED),
        (Status.FAILED, Status.PUBLISHING),
    ],
)
def test_allowed_transitions(current, target):
    assert_transition(current, target)  # must not raise


@pytest.mark.parametrize(
    "current,target",
    [
        (Status.DRAFT, Status.APPROVED),      # can't skip review
        (Status.DRAFT, Status.PUBLISHED),
        (Status.IN_REVIEW, Status.PUBLISHING),  # can't post unapproved
        (Status.PUBLISHED, Status.DRAFT),     # published is terminal
        (Status.SCHEDULED, Status.PUBLISHING),  # reserved in v1
    ],
)
def test_forbidden_transitions(current, target):
    with pytest.raises(TransitionError):
        assert_transition(current, target)


def test_error_message_names_allowed_states():
    with pytest.raises(TransitionError, match="allowed next: draft, approved"):
        assert_transition(Status.IN_REVIEW, Status.PUBLISHED)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.models'`

- [ ] **Step 3: Implement**

`src/agenticsocial/models.py`:

```python
"""Domain model: sources, variants, and the status lifecycle.

The approval gate lives here: there is deliberately no edge from
in_review to publishing, and none into approved except from in_review.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"  # reserved for the v2 calendar
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.PUBLISHING},
    Status.SCHEDULED: set(),
    Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.PUBLISHING},
}

_ORDER = list(Status)


class TransitionError(Exception):
    def __init__(self, current: Status, target: Status):
        allowed = ", ".join(
            s.value for s in _ORDER if s in ALLOWED_TRANSITIONS[current]
        ) or "none (terminal)"
        super().__init__(
            f"cannot move {current.value} -> {target.value}; allowed next: {allowed}"
        )


def assert_transition(current: Status, target: Status) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise TransitionError(current, target)


@dataclass
class Source:
    id: str
    type: str  # url | idea | transcript
    title: str
    dir: Path
    origin_url: str | None = None
    created: str = ""


@dataclass
class Variant:
    platform: str  # x | linkedin | youtube
    status: Status
    meta: dict
    body: str
    path: Path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/models.py tests/test_models.py
git commit -m "feat: add status lifecycle with enforced approval gate"
```

---

### Task 5: Workspace — scaffold and sources

**Files:**
- Create: `src/agenticsocial/workspace.py`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: `frontmatter.parse/dump` (Task 2), `textutils.slugify` (Task 3), `models.Source` (Task 4).
- Produces: `atomic_write(path: Path, text: str) -> None`; `WorkspaceError(Exception)`; `class Workspace` with `__init__(self, root: Path)`, attributes `root: Path`, `sources_dir: Path`, classmethods `Workspace.init(root: Path) -> Workspace` and `Workspace.locate() -> Workspace` (env `AGSOC_WORKSPACE`, default `./workspace`; raises `WorkspaceError` if absent), methods `create_source(title: str, type: str = "idea", origin_url: str | None = None, body: str = "", created: str | None = None) -> Source`, `list_sources() -> list[Source]`, `resolve_source(query: str) -> Source`. Also module constants `VOICE_TEMPLATE: str`, `CONFIG_TEMPLATE: str`, and `load_config(ws) -> dict` (parsed `config.toml`). Task 6 adds variant methods to this same class.

- [ ] **Step 1: Write the failing tests**

`tests/test_workspace.py`:

```python
import pytest

from agenticsocial.workspace import Workspace, WorkspaceError, load_config


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


def test_init_scaffolds_workspace(tmp_path):
    ws = Workspace.init(tmp_path / "workspace")
    assert ws.sources_dir.is_dir()
    assert (ws.root / "voice.md").exists()
    assert (ws.root / "config.toml").exists()
    assert load_config(ws) == {"x": {"client_id": ""}}


def test_init_is_idempotent_and_preserves_edits(tmp_path):
    ws = Workspace.init(tmp_path / "workspace")
    (ws.root / "voice.md").write_text("MY VOICE", encoding="utf-8")
    Workspace.init(tmp_path / "workspace")
    assert (ws.root / "voice.md").read_text(encoding="utf-8") == "MY VOICE"


def test_locate_uses_env_var(tmp_path, monkeypatch):
    Workspace.init(tmp_path / "elsewhere")
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "elsewhere"))
    assert Workspace.locate().root == tmp_path / "elsewhere"


def test_locate_missing_workspace_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "nope"))
    with pytest.raises(WorkspaceError, match="agsoc init"):
        Workspace.locate()


def test_create_source_writes_source_md(ws):
    src = ws.create_source("Kill Staging!", type="idea", created="2026-07-13")
    assert src.id == "2026-07-13-kill-staging"
    assert (ws.sources_dir / src.id / "source.md").exists()


def test_create_source_rejects_duplicate(ws):
    ws.create_source("Same title", created="2026-07-13")
    with pytest.raises(WorkspaceError, match="already exists"):
        ws.create_source("Same title", created="2026-07-13")


def test_list_sources_roundtrip(ws):
    ws.create_source("B idea", created="2026-07-14")
    ws.create_source("A idea", type="url", origin_url="https://ex.com/a", created="2026-07-13")
    sources = ws.list_sources()
    assert [s.id for s in sources] == ["2026-07-13-a-idea", "2026-07-14-b-idea"]
    assert sources[0].origin_url == "https://ex.com/a"
    assert sources[0].type == "url"
    assert sources[0].title == "A idea"


def test_resolve_source_by_substring(ws):
    ws.create_source("Kill staging", created="2026-07-13")
    ws.create_source("Queues gotchas", created="2026-07-13")
    assert ws.resolve_source("staging").id == "2026-07-13-kill-staging"


def test_resolve_source_ambiguous_or_missing(ws):
    ws.create_source("Idea one", created="2026-07-13")
    ws.create_source("Idea two", created="2026-07-13")
    with pytest.raises(WorkspaceError, match="matches multiple"):
        ws.resolve_source("idea")
    with pytest.raises(WorkspaceError, match="no source"):
        ws.resolve_source("zzz")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workspace.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.workspace'`

- [ ] **Step 3: Implement**

`src/agenticsocial/workspace.py`:

```python
"""The content workspace: a plain directory of markdown files.

Layout:
    workspace/
      sources/<id>/source.md      one directory per source
      sources/<id>/<platform>.md  variants (x.md, linkedin.md, youtube.md)
      sources/<id>/brief.md       optional research brief
      voice.md                    voice profile the agent reads before drafting
      config.toml                 workspace settings
"""
from __future__ import annotations

import os
import tempfile
import tomllib
from datetime import date
from pathlib import Path

from . import frontmatter
from .models import Source
from .textutils import slugify

VOICE_TEMPLATE = """\
# Voice profile

## Persona
Describe who you are online: role, niche, what you want to be known for.

## Per-platform rules
### X
- hook-first: the first line must earn the next
- no hashtags
- <= 280 chars per tweet

### LinkedIn (v1.1)
- no em-dashes
- exactly 1 CTA question at the end
- short paragraphs with line breaks

### YouTube (v1.1)
- SEO title <= 100 chars
- timestamped chapters

## Example posts I liked
Paste 2-3 posts (yours or others') whose voice you want to match.
"""

CONFIG_TEMPLATE = """\
[x]
# OAuth 2.0 Client ID from your X developer app (Native App / public client).
# Create one at https://developer.x.com -> your app -> user authentication settings.
client_id = ""
"""


class WorkspaceError(Exception):
    pass


def atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_config(ws: "Workspace") -> dict:
    with open(ws.root / "config.toml", "rb") as f:
        return tomllib.load(f)


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.sources_dir = self.root / "sources"

    @classmethod
    def init(cls, root: Path) -> "Workspace":
        ws = cls(root)
        ws.sources_dir.mkdir(parents=True, exist_ok=True)
        for name, template in (("voice.md", VOICE_TEMPLATE), ("config.toml", CONFIG_TEMPLATE)):
            if not (ws.root / name).exists():
                (ws.root / name).write_text(template, encoding="utf-8")
        return ws

    @classmethod
    def locate(cls) -> "Workspace":
        root = Path(os.environ.get("AGSOC_WORKSPACE", "workspace"))
        if not (root / "sources").is_dir():
            raise WorkspaceError(
                f"no workspace at {root}/ — run `agsoc init` there or set AGSOC_WORKSPACE"
            )
        return cls(root)

    # -- sources -----------------------------------------------------------

    def create_source(
        self,
        title: str,
        type: str = "idea",
        origin_url: str | None = None,
        body: str = "",
        created: str | None = None,
    ) -> Source:
        created = created or date.today().isoformat()
        sid = f"{created}-{slugify(title)}"
        d = self.sources_dir / sid
        if d.exists():
            raise WorkspaceError(f"source already exists: {sid}")
        d.mkdir(parents=True)
        meta = {
            "id": sid,
            "type": type,
            "title": title,
            "origin_url": origin_url,
            "created": created,
        }
        atomic_write(d / "source.md", frontmatter.dump(meta, body))
        return Source(id=sid, type=type, title=title, dir=d, origin_url=origin_url, created=created)

    def _read_source(self, d: Path) -> Source:
        meta, _ = frontmatter.parse((d / "source.md").read_text(encoding="utf-8"))
        return Source(
            id=meta["id"],
            type=meta.get("type", "idea"),
            title=meta.get("title", meta["id"]),
            dir=d,
            origin_url=meta.get("origin_url"),
            created=str(meta.get("created", "")),
        )

    def list_sources(self) -> list[Source]:
        dirs = sorted(d for d in self.sources_dir.iterdir() if (d / "source.md").exists())
        return [self._read_source(d) for d in dirs]

    def resolve_source(self, query: str) -> Source:
        sources = self.list_sources()
        exact = [s for s in sources if s.id == query]
        if exact:
            return exact[0]
        matches = [s for s in sources if query.lower() in s.id.lower()]
        if len(matches) > 1:
            ids = ", ".join(s.id for s in matches)
            raise WorkspaceError(f"'{query}' matches multiple sources: {ids}")
        if not matches:
            raise WorkspaceError(f"no source matching '{query}' — see `agsoc list`")
        return matches[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspace.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/workspace.py tests/test_workspace.py
git commit -m "feat: add workspace scaffold, source creation, and lookup"
```

---

### Task 6: Workspace — variants and status enforcement

**Files:**
- Modify: `src/agenticsocial/workspace.py` (add methods to `Workspace`)
- Test: `tests/test_workspace.py` (append)

**Interfaces:**
- Consumes: Task 5's `Workspace`, `models.Variant/Status/assert_transition` (Task 4).
- Produces: `Workspace.create_variant(source: Source, platform: str, body: str = "") -> Variant` (initial status `draft`); `Workspace.load_variant(source: Source, platform: str) -> Variant` (raises `WorkspaceError` if missing); `Workspace.variants(source: Source) -> list[Variant]`; `Workspace.save_variant(v: Variant) -> None` (atomic); `Workspace.set_status(v: Variant, target: Status) -> None` (enforces transitions, stamps `approved_at` on APPROVED and `posted_at` on PUBLISHED, saves). Timestamps via `datetime.now().astimezone().isoformat(timespec="seconds")`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_workspace.py`:

```python
from agenticsocial.models import Status, TransitionError


@pytest.fixture()
def src(ws):
    return ws.create_source("Kill staging", created="2026-07-13")


def test_create_and_load_variant(ws, src):
    ws.create_variant(src, "x", body="Tweet one\n\n---tweet---\n\nTweet two\n")
    v = ws.load_variant(src, "x")
    assert v.platform == "x"
    assert v.status == Status.DRAFT
    assert v.meta["posted_ids"] == []
    assert "Tweet two" in v.body
    assert v.path == src.dir / "x.md"


def test_load_missing_variant_raises(ws, src):
    with pytest.raises(WorkspaceError, match="no x variant"):
        ws.load_variant(src, "x")


def test_variants_lists_only_platform_files(ws, src):
    ws.create_variant(src, "x")
    (src.dir / "brief.md").write_text("notes", encoding="utf-8")
    assert [v.platform for v in ws.variants(src)] == ["x"]


def test_set_status_persists_and_stamps_approved_at(ws, src):
    ws.create_variant(src, "x", body="hi")
    v = ws.load_variant(src, "x")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    v2 = ws.load_variant(src, "x")
    assert v2.status == Status.APPROVED
    assert v2.meta["approved_at"]  # stamped


def test_set_status_enforces_gate(ws, src):
    ws.create_variant(src, "x", body="hi")
    v = ws.load_variant(src, "x")
    with pytest.raises(TransitionError):
        ws.set_status(v, Status.APPROVED)  # draft -> approved is forbidden
    assert ws.load_variant(src, "x").status == Status.DRAFT  # nothing saved


def test_save_variant_roundtrips_body_edits(ws, src):
    ws.create_variant(src, "x", body="old")
    v = ws.load_variant(src, "x")
    v.body = "new body"
    ws.save_variant(v)
    assert ws.load_variant(src, "x").body == "new body"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workspace.py -v`
Expected: new tests FAIL with `AttributeError: 'Workspace' object has no attribute 'create_variant'`; Task 5 tests still PASS.

- [ ] **Step 3: Implement**

Add to `src/agenticsocial/workspace.py` (imports: add `from datetime import datetime` and extend the models import to `from .models import Source, Status, Variant, assert_transition`; add module constant `PLATFORMS = ("x", "linkedin", "youtube")`). Methods on `Workspace`:

```python
    # -- variants ----------------------------------------------------------

    def create_variant(self, source: Source, platform: str, body: str = "") -> Variant:
        path = source.dir / f"{platform}.md"
        if path.exists():
            raise WorkspaceError(f"{platform} variant already exists for {source.id}")
        meta = {
            "platform": platform,
            "status": Status.DRAFT.value,
            "approved_at": None,
            "posted_url": None,
            "posted_at": None,
            "posted_ids": [],
        }
        atomic_write(path, frontmatter.dump(meta, body))
        return Variant(platform=platform, status=Status.DRAFT, meta=meta, body=body, path=path)

    def load_variant(self, source: Source, platform: str) -> Variant:
        path = source.dir / f"{platform}.md"
        if not path.exists():
            raise WorkspaceError(f"no {platform} variant for {source.id}")
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        meta.setdefault("posted_ids", [])
        return Variant(
            platform=platform,
            status=Status(meta.get("status", "draft")),
            meta=meta,
            body=body,
            path=path,
        )

    def variants(self, source: Source) -> list[Variant]:
        return [
            self.load_variant(source, p)
            for p in PLATFORMS
            if (source.dir / f"{p}.md").exists()
        ]

    def save_variant(self, v: Variant) -> None:
        v.meta["status"] = v.status.value
        atomic_write(v.path, frontmatter.dump(v.meta, v.body))

    def set_status(self, v: Variant, target: Status) -> None:
        assert_transition(v.status, target)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        if target is Status.APPROVED:
            v.meta["approved_at"] = now
        if target is Status.PUBLISHED:
            v.meta["posted_at"] = now
        v.status = target
        self.save_variant(v)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspace.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/workspace.py tests/test_workspace.py
git commit -m "feat: add variant storage with enforced status transitions"
```

---

### Task 7: CLI — init, new, list, status

**Files:**
- Modify: `src/agenticsocial/cli.py`
- Test: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `Workspace` (Tasks 5–6), `Status`.
- Produces: CLI commands `agsoc init [PATH]`, `agsoc new TITLE [--url URL] [--file PATH] [--type idea|url|transcript]`, `agsoc list [--status STATUS]`, `agsoc status`. Helper `_workspace() -> Workspace` that exits with code 1 and the `WorkspaceError` message when no workspace exists — reused by every later command task.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
import pytest

from agenticsocial.models import Status
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    monkeypatch.setenv("AGSOC_WORKSPACE", str(root))
    return Workspace.init(root)


def test_init_creates_workspace(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path / "ws")])
    assert result.exit_code == 0
    assert (tmp_path / "ws" / "voice.md").exists()
    assert "voice.md" in result.output


def test_new_creates_source_and_prints_id(ws):
    result = runner.invoke(app, ["new", "Kill staging"])
    assert result.exit_code == 0
    assert "-kill-staging" in result.output
    assert len(ws.list_sources()) == 1


def test_new_with_url_sets_type(ws):
    runner.invoke(app, ["new", "Some post", "--url", "https://ex.com/p"])
    src = ws.list_sources()[0]
    assert src.type == "url"
    assert src.origin_url == "https://ex.com/p"


def test_new_without_workspace_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("AGSOC_WORKSPACE", str(tmp_path / "missing"))
    result = runner.invoke(app, ["new", "x"])
    assert result.exit_code == 1
    assert "agsoc init" in result.output


def test_list_shows_sources_and_variant_statuses(ws):
    src = ws.create_source("Kill staging", created="2026-07-13")
    ws.create_variant(src, "x", body="hi")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "2026-07-13-kill-staging" in result.output
    assert "x:draft" in result.output


def test_list_filters_by_status(ws):
    a = ws.create_source("Aaa", created="2026-07-13")
    ws.create_variant(a, "x", body="hi")
    b = ws.create_source("Bbb", created="2026-07-13")
    v = ws.create_variant(b, "x", body="hi")
    ws.set_status(v, Status.IN_REVIEW)
    result = runner.invoke(app, ["list", "--status", "in_review"])
    assert "bbb" in result.output
    assert "aaa" not in result.output


def test_status_overview(ws):
    src = ws.create_source("Kill staging", created="2026-07-13")
    v = ws.create_variant(src, "x", body="hi")
    ws.set_status(v, Status.IN_REVIEW)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "in_review" in result.output
    assert "1" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: new tests FAIL (exit code 2, "No such command"); the version test still PASSES.

- [ ] **Step 3: Implement**

Replace `src/agenticsocial/cli.py` with:

```python
"""agsoc — local-first content pipeline CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .models import Status
from .workspace import Workspace, WorkspaceError

app = typer.Typer(
    help="Capture sources, research, review drafts, and post to X. The agent drafts; you approve.",
    no_args_is_help=True,
)


def _fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=False)
    return typer.Exit(code=1)


def _workspace() -> Workspace:
    try:
        return Workspace.locate()
    except WorkspaceError as e:
        raise _fail(str(e))


@app.command()
def version() -> None:
    """Print the agsoc version."""
    typer.echo(__version__)


@app.command()
def init(path: Path = typer.Argument(Path("workspace"))) -> None:
    """Scaffold a content workspace (sources/, voice.md, config.toml)."""
    ws = Workspace.init(path)
    typer.echo(f"workspace ready at {ws.root}/")
    typer.echo("next: edit voice.md (your voice profile) and config.toml (X client_id)")


@app.command()
def new(
    title: str,
    url: Optional[str] = typer.Option(None, "--url", help="origin URL (sets type=url)"),
    file: Optional[Path] = typer.Option(None, "--file", help="file whose text becomes the source body (sets type=transcript)"),
    type: Optional[str] = typer.Option(None, "--type", help="idea | url | transcript"),
) -> None:
    """Create a source from a title/idea, a URL, or a transcript file."""
    ws = _workspace()
    body = ""
    inferred = "idea"
    if url:
        inferred = "url"
    if file:
        inferred = "transcript"
        body = file.read_text(encoding="utf-8")
    try:
        src = ws.create_source(title, type=type or inferred, origin_url=url, body=body)
    except WorkspaceError as e:
        raise _fail(str(e))
    typer.echo(f"created source {src.id}")


@app.command("list")
def list_(
    status: Optional[str] = typer.Option(None, "--status", help="only sources with a variant in this status"),
) -> None:
    """List sources and their variant statuses."""
    ws = _workspace()
    wanted = Status(status) if status else None
    for src in ws.list_sources():
        variants = ws.variants(src)
        if wanted and not any(v.status is wanted for v in variants):
            continue
        pills = " ".join(f"{v.platform}:{v.status.value}" for v in variants) or "(no variants)"
        typer.echo(f"{src.id}  [{src.type}]  {pills}")


@app.command()
def status() -> None:
    """Workspace overview: variant counts per status."""
    ws = _workspace()
    counts: dict[str, int] = {}
    for src in ws.list_sources():
        for v in ws.variants(src):
            counts[v.status.value] = counts.get(v.status.value, 0) + 1
    if not counts:
        typer.echo("workspace is empty — create a source with `agsoc new`")
        return
    for s in Status:
        if s.value in counts:
            typer.echo(f"{s.value:12} {counts[s.value]}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/cli.py tests/test_cli.py
git commit -m "feat: add init, new, list, and status commands"
```

---

### Task 8: CLI — review & approve

**Files:**
- Create: `src/agenticsocial/x/__init__.py` (empty), `src/agenticsocial/x/publish.py` (validation half)
- Modify: `src/agenticsocial/cli.py`
- Test: `tests/test_publish.py` (validation), `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `split_thread`, `weighted_length`, `TWEET_LIMIT` (Task 3); `Workspace`, `Status` (Tasks 5–7); `_workspace`, `_fail` (Task 7).
- Produces: `x.publish.ValidationError(Exception)`; `x.publish.validate_thread(body: str) -> list[str]` (returns tweets; raises naming the offending tweet number and weighted count). CLI commands `agsoc review SOURCE [--platform x]`, `agsoc approve SOURCE [--platform x]`. Task 11 extends `x/publish.py` with `publish_variant`.

- [ ] **Step 1: Write the failing validation tests**

`tests/test_publish.py`:

```python
import pytest

from agenticsocial.x.publish import ValidationError, validate_thread


def test_validate_thread_splits_and_passes():
    assert validate_thread("A\n\n---tweet---\n\nB") == ["A", "B"]


def test_validate_thread_rejects_empty_body():
    with pytest.raises(ValidationError, match="empty"):
        validate_thread("\n\n")


def test_validate_thread_rejects_overlong_tweet():
    body = "ok\n\n---tweet---\n\n" + "x" * 281
    with pytest.raises(ValidationError, match="tweet 2 is 281"):
        validate_thread(body)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_publish.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.x'`

- [ ] **Step 3: Implement validation**

Create empty `src/agenticsocial/x/__init__.py`. Then `src/agenticsocial/x/publish.py`:

```python
"""Thread validation and (in Task 11) resume-safe publishing."""
from __future__ import annotations

from ..textutils import TWEET_LIMIT, split_thread, weighted_length


class ValidationError(Exception):
    pass


def validate_thread(body: str) -> list[str]:
    tweets = split_thread(body)
    if not tweets:
        raise ValidationError("variant body is empty")
    for i, t in enumerate(tweets, 1):
        n = weighted_length(t)
        if n > TWEET_LIMIT:
            raise ValidationError(
                f"tweet {i} is {n} weighted chars (limit {TWEET_LIMIT}); URLs count as 23"
            )
    return tweets


def format_review(tweets: list[str]) -> str:
    lines = []
    for i, t in enumerate(tweets, 1):
        n = weighted_length(t)
        flag = "  ⚠ OVER LIMIT" if n > TWEET_LIMIT else ""
        lines.append(f"── tweet {i}/{len(tweets)} · {n}/{TWEET_LIMIT} chars{flag}")
        lines.append(t)
        lines.append("")
    return "\n".join(lines)
```

Run: `uv run pytest tests/test_publish.py -v` — Expected: 3 PASS

- [ ] **Step 4: Write the failing CLI tests**

Append to `tests/test_cli.py`:

```python
@pytest.fixture()
def reviewable(ws):
    src = ws.create_source("Kill staging", created="2026-07-13")
    v = ws.create_variant(src, "x", body="Tweet one\n\n---tweet---\n\nTweet two")
    ws.set_status(v, Status.IN_REVIEW)
    return ws, src


def test_review_renders_thread_with_counts(reviewable):
    result = runner.invoke(app, ["review", "staging"])
    assert result.exit_code == 0
    assert "tweet 1/2" in result.output
    assert "Tweet two" in result.output
    assert "in_review" in result.output


def test_approve_moves_status(reviewable):
    ws, src = reviewable
    result = runner.invoke(app, ["approve", "staging"])
    assert result.exit_code == 0
    assert ws.load_variant(src, "x").status == Status.APPROVED


def test_approve_rejects_overlong_tweet(ws):
    src = ws.create_source("Long one", created="2026-07-13")
    v = ws.create_variant(src, "x", body="y" * 300)
    ws.set_status(v, Status.IN_REVIEW)
    result = runner.invoke(app, ["approve", "long"])
    assert result.exit_code == 1
    assert "300" in result.output
    assert ws.load_variant(src, "x").status == Status.IN_REVIEW


def test_approve_from_draft_fails_with_transition_message(ws):
    src = ws.create_source("Draft one", created="2026-07-13")
    ws.create_variant(src, "x", body="hi")
    result = runner.invoke(app, ["approve", "draft-one"])
    assert result.exit_code == 1
    assert "allowed next" in result.output
```

Run: `uv run pytest tests/test_cli.py -v`
Expected: new tests FAIL ("No such command 'review'")

- [ ] **Step 5: Implement the commands**

Add to `src/agenticsocial/cli.py` (new imports: `from .models import Status, TransitionError`, `from .x.publish import ValidationError, format_review, validate_thread`, `from .textutils import split_thread`):

```python
def _load(ws: Workspace, source_query: str, platform: str):
    try:
        src = ws.resolve_source(source_query)
        return src, ws.load_variant(src, platform)
    except WorkspaceError as e:
        raise _fail(str(e))


@app.command()
def review(
    source: str,
    platform: str = typer.Option("x", "--platform"),
) -> None:
    """Render a variant for human review: per-tweet character counts and content."""
    ws = _workspace()
    src, v = _load(ws, source, platform)
    typer.echo(f"{src.id} · {platform} · status: {v.status.value}\n")
    typer.echo(format_review(split_thread(v.body)))
    if v.status is Status.IN_REVIEW:
        typer.echo(f"approve with: agsoc approve {src.id}")


@app.command()
def approve(
    source: str,
    platform: str = typer.Option("x", "--platform"),
) -> None:
    """Approve a variant for publishing (the human gate — agents must not run this)."""
    ws = _workspace()
    src, v = _load(ws, source, platform)
    try:
        if platform == "x":
            validate_thread(v.body)
        ws.set_status(v, Status.APPROVED)
    except (ValidationError, TransitionError) as e:
        raise _fail(str(e))
    typer.echo(f"approved {src.id} ({platform}) — post with: agsoc post {src.id}")
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/agenticsocial/x src/agenticsocial/cli.py tests/test_publish.py tests/test_cli.py
git commit -m "feat: add review and approve commands with thread validation"
```

---

### Task 9: X auth — OAuth 2.0 PKCE + keyring

**Files:**
- Create: `src/agenticsocial/x/auth.py`
- Modify: `src/agenticsocial/cli.py` (add `auth` command)
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `load_config` (Task 5), `_workspace`/`_fail` (Task 7).
- Produces: `x.auth.pkce_pair() -> tuple[str, str]` (verifier, S256 challenge); `x.auth.save_token(token: dict) -> None` / `x.auth.load_token() -> dict | None` (keyring service `agenticsocial`, account `x`, JSON-encoded); `x.auth.authorize(client_id: str) -> dict` (interactive browser flow; returns and saves token dict with keys `access_token`, `refresh_token`, `expires_in`, ...); `x.auth.refresh(client_id: str, token: dict) -> dict` (exchanges refresh_token, saves and returns new token); `x.auth.AuthError(Exception)`. Constants `TOKEN_URL`, `AUTH_URL`, `REDIRECT_URI`, `SCOPES` as in Global Constraints. CLI command `agsoc auth x`.

- [ ] **Step 1: Write the failing tests**

`tests/test_auth.py`:

```python
import base64
import hashlib

import httpx
import pytest
import respx

from agenticsocial.x import auth


@pytest.fixture()
def fake_keyring(monkeypatch):
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        auth.keyring, "set_password", lambda svc, acct, val: store.__setitem__((svc, acct), val)
    )
    monkeypatch.setattr(
        auth.keyring, "get_password", lambda svc, acct: store.get((svc, acct))
    )
    return store


def test_pkce_pair_is_valid_s256():
    verifier, challenge = auth.pkce_pair()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    assert challenge == expected
    assert 43 <= len(verifier) <= 128


def test_token_roundtrip_via_keyring(fake_keyring):
    assert auth.load_token() is None
    auth.save_token({"access_token": "abc", "refresh_token": "r1"})
    assert auth.load_token() == {"access_token": "abc", "refresh_token": "r1"}
    assert ("agenticsocial", "x") in fake_keyring


@respx.mock
def test_refresh_exchanges_and_saves(fake_keyring):
    respx.post(auth.TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "new", "refresh_token": "r2", "expires_in": 7200}
        )
    )
    token = auth.refresh("client123", {"refresh_token": "r1"})
    assert token["access_token"] == "new"
    assert auth.load_token()["refresh_token"] == "r2"


@respx.mock
def test_refresh_failure_raises_autherror(fake_keyring):
    respx.post(auth.TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(auth.AuthError, match="agsoc auth x"):
        auth.refresh("client123", {"refresh_token": "r1"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.x.auth'`

- [ ] **Step 3: Implement**

`src/agenticsocial/x/auth.py`:

```python
"""OAuth 2.0 PKCE flow for X. Tokens live only in the OS keychain."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import keyring

SERVICE = "agenticsocial"
ACCOUNT = "x"
AUTH_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REDIRECT_PORT = 8721
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SCOPES = "tweet.read tweet.write users.read offline.access"


class AuthError(Exception):
    pass


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def save_token(token: dict) -> None:
    keyring.set_password(SERVICE, ACCOUNT, json.dumps(token))


def load_token() -> dict | None:
    raw = keyring.get_password(SERVICE, ACCOUNT)
    return json.loads(raw) if raw else None


def _exchange(data: dict) -> dict:
    resp = httpx.post(TOKEN_URL, data=data, timeout=30)
    if resp.status_code != 200:
        raise AuthError(
            f"token request failed ({resp.status_code}): {resp.text} — run `agsoc auth x` to reconnect"
        )
    token = resp.json()
    save_token(token)
    return token


def refresh(client_id: str, token: dict) -> dict:
    return _exchange(
        {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": client_id,
        }
    )


class _CallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None

    def do_GET(self):  # noqa: N802 (http.server API)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CallbackHandler.code = (params.get("code") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>agsoc: authorized</h1>You can close this tab.")

    def log_message(self, *args):  # silence request logging
        pass


def authorize(client_id: str) -> dict:
    """Interactive: open the browser, catch the callback, exchange the code."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    server = HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
    print(f"opening browser to authorize (or visit):\n{url}")
    webbrowser.open(url)
    server.handle_request()  # blocks for exactly one callback
    server.server_close()
    if not _CallbackHandler.code:
        raise AuthError("no authorization code received — flow cancelled?")
    return _exchange(
        {
            "grant_type": "authorization_code",
            "code": _CallbackHandler.code,
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
    )
```

Add the CLI command to `src/agenticsocial/cli.py` (imports: `from .workspace import Workspace, WorkspaceError, load_config` and `from .x import auth as x_auth`):

```python
@app.command()
def auth(platform: str = typer.Argument("x")) -> None:
    """Connect a platform account (v1: x). One-time browser OAuth flow."""
    if platform != "x":
        raise _fail(f"unsupported platform '{platform}' — v1 supports: x")
    ws = _workspace()
    client_id = load_config(ws).get("x", {}).get("client_id", "")
    if not client_id:
        raise _fail(f"set [x] client_id in {ws.root / 'config.toml'} first (see README)")
    try:
        x_auth.authorize(client_id)
    except x_auth.AuthError as e:
        raise _fail(str(e))
    typer.echo("X account connected — token stored in your OS keychain")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py tests/test_cli.py -v`
Expected: all PASS (the interactive `authorize` path is exercised manually later; unit tests cover pkce/save/load/refresh).

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/x/auth.py src/agenticsocial/cli.py tests/test_auth.py
git commit -m "feat: add X OAuth PKCE flow with keychain token storage"
```

---

### Task 10: X client

**Files:**
- Create: `src/agenticsocial/x/client.py`
- Test: `tests/test_x_client.py`

**Interfaces:**
- Consumes: nothing internal (pure httpx).
- Produces: `x.client.XApiError(Exception)`; `class XClient` with `__init__(self, access_token: str, http: httpx.Client | None = None)` and `post_tweet(self, text: str, in_reply_to: str | None = None) -> str` returning the created tweet id. Constant `API_URL = "https://api.x.com/2/tweets"`. Error behavior: 429 → message includes `x-rate-limit-reset` header value; 401 → message includes "agsoc auth x"; other ≥400 → status + body.

- [ ] **Step 1: Write the failing tests**

`tests/test_x_client.py`:

```python
import httpx
import pytest
import respx

from agenticsocial.x.client import API_URL, XApiError, XClient


@respx.mock
def test_post_tweet_returns_id():
    route = respx.post(API_URL).mock(
        return_value=httpx.Response(201, json={"data": {"id": "111", "text": "hello"}})
    )
    client = XClient("tok")
    assert client.post_tweet("hello") == "111"
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer tok"
    assert b'"text": "hello"' in sent.content or b'"text":"hello"' in sent.content


@respx.mock
def test_post_tweet_chains_replies():
    route = respx.post(API_URL).mock(
        return_value=httpx.Response(201, json={"data": {"id": "222", "text": "t"}})
    )
    XClient("tok").post_tweet("t", in_reply_to="111")
    assert b'"in_reply_to_tweet_id"' in route.calls.last.request.content


@respx.mock
def test_rate_limit_error_mentions_reset():
    respx.post(API_URL).mock(
        return_value=httpx.Response(429, headers={"x-rate-limit-reset": "1789300000"}, json={})
    )
    with pytest.raises(XApiError, match="1789300000"):
        XClient("tok").post_tweet("t")


@respx.mock
def test_unauthorized_error_suggests_auth():
    respx.post(API_URL).mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(XApiError, match="agsoc auth x"):
        XClient("tok").post_tweet("t")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_x_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.x.client'`

- [ ] **Step 3: Implement**

`src/agenticsocial/x/client.py`:

```python
"""Thin client for the X API v2 tweets endpoint."""
from __future__ import annotations

import httpx

API_URL = "https://api.x.com/2/tweets"


class XApiError(Exception):
    pass


class XClient:
    def __init__(self, access_token: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(timeout=30)
        self._headers = {"Authorization": f"Bearer {access_token}"}

    def post_tweet(self, text: str, in_reply_to: str | None = None) -> str:
        payload: dict = {"text": text}
        if in_reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": in_reply_to}
        resp = self._http.post(API_URL, json=payload, headers=self._headers)
        if resp.status_code == 429:
            reset = resp.headers.get("x-rate-limit-reset", "unknown")
            raise XApiError(f"rate limited by X; retry after unix time {reset}")
        if resp.status_code == 401:
            raise XApiError("X rejected the token (401) — reconnect with `agsoc auth x`")
        if resp.status_code >= 400:
            raise XApiError(f"X API error {resp.status_code}: {resp.text}")
        return resp.json()["data"]["id"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_x_client.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/x/client.py tests/test_x_client.py
git commit -m "feat: add X API client with actionable error messages"
```

---

### Task 11: Resume-safe publishing + CLI post

**Files:**
- Modify: `src/agenticsocial/x/publish.py`, `src/agenticsocial/cli.py`
- Test: `tests/test_publish.py` (append), `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `validate_thread` (Task 8), `XClient`/`XApiError` (Task 10), `Workspace.set_status/save_variant` (Task 6), `x.auth.load_token/refresh` (Task 9), `load_config` (Task 5).
- Produces: `x.publish.publish_variant(ws: Workspace, variant: Variant, client: XClient) -> str` — transitions `approved|failed → publishing`, posts remaining tweets (skipping `len(meta["posted_ids"])`), persists `posted_ids` after **each** tweet, chains replies, sets `posted_url` (`https://x.com/i/web/status/<first_id>`), transitions to `published`; on any exception transitions to `failed` and re-raises. CLI command `agsoc post SOURCE [--platform x] [--dry-run] [--resume]`.

- [ ] **Step 1: Write the failing publish tests**

Append to `tests/test_publish.py`:

```python
from pathlib import Path

import pytest

from agenticsocial.models import Status
from agenticsocial.workspace import Workspace
from agenticsocial.x.client import XApiError
from agenticsocial.x.publish import publish_variant


class FakeClient:
    def __init__(self, fail_at: int | None = None):
        self.posted: list[tuple[str, str | None]] = []
        self.fail_at = fail_at
        self._n = 0

    def post_tweet(self, text, in_reply_to=None):
        self._n += 1
        if self.fail_at is not None and self._n >= self.fail_at:
            raise XApiError("boom")
        self.posted.append((text, in_reply_to))
        return f"id{self._n}"


@pytest.fixture()
def approved_variant(tmp_path):
    ws = Workspace.init(tmp_path / "ws")
    src = ws.create_source("Thread", created="2026-07-13")
    v = ws.create_variant(src, "x", body="One\n\n---tweet---\n\nTwo\n\n---tweet---\n\nThree")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    return ws, src, v


def test_publish_posts_thread_with_reply_chain(approved_variant):
    ws, src, v = approved_variant
    client = FakeClient()
    url = publish_variant(ws, v, client)
    assert url == "https://x.com/i/web/status/id1"
    assert client.posted == [("One", None), ("Two", "id1"), ("Three", "id2")]
    saved = ws.load_variant(src, "x")
    assert saved.status == Status.PUBLISHED
    assert saved.meta["posted_ids"] == ["id1", "id2", "id3"]
    assert saved.meta["posted_url"] == url
    assert saved.meta["posted_at"]


def test_publish_failure_marks_failed_and_keeps_posted_ids(approved_variant):
    ws, src, v = approved_variant
    with pytest.raises(XApiError):
        publish_variant(ws, v, FakeClient(fail_at=3))
    saved = ws.load_variant(src, "x")
    assert saved.status == Status.FAILED
    assert saved.meta["posted_ids"] == ["id1", "id2"]


def test_publish_resume_skips_already_posted(approved_variant):
    ws, src, v = approved_variant
    with pytest.raises(XApiError):
        publish_variant(ws, v, FakeClient(fail_at=3))
    resumed = ws.load_variant(src, "x")
    client = FakeClient()
    publish_variant(ws, resumed, client)
    # only the third tweet is posted, replying to the last posted id
    assert client.posted == [("Three", "id2")]
    assert ws.load_variant(src, "x").status == Status.PUBLISHED


def test_publish_refuses_unapproved(tmp_path):
    ws = Workspace.init(tmp_path / "ws")
    src = ws.create_source("Nope", created="2026-07-13")
    v = ws.create_variant(src, "x", body="hi")  # draft
    from agenticsocial.models import TransitionError
    with pytest.raises(TransitionError):
        publish_variant(ws, v, FakeClient())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_publish.py -v`
Expected: new tests FAIL with `ImportError: cannot import name 'publish_variant'`

- [ ] **Step 3: Implement publish_variant**

Append to `src/agenticsocial/x/publish.py` (new imports at top: `from ..models import Status, Variant`, `from ..workspace import Workspace`; `XClient` is only type-hinted via duck typing so no import needed):

```python
def publish_variant(ws: Workspace, variant: Variant, client) -> str:
    """Post an approved (or failed, when resuming) X variant as a thread.

    posted_ids is persisted after every tweet so an interruption never
    double-posts: resuming skips len(posted_ids) tweets and replies to the
    last posted id.
    """
    tweets = validate_thread(variant.body)
    ws.set_status(variant, Status.PUBLISHING)  # gate: only approved/failed may enter
    posted: list[str] = list(variant.meta.get("posted_ids") or [])
    try:
        for text in tweets[len(posted):]:
            reply_to = posted[-1] if posted else None
            posted.append(client.post_tweet(text, in_reply_to=reply_to))
            variant.meta["posted_ids"] = posted
            ws.save_variant(variant)
    except BaseException:
        ws.set_status(variant, Status.FAILED)
        raise
    variant.meta["posted_url"] = f"https://x.com/i/web/status/{posted[0]}"
    ws.set_status(variant, Status.PUBLISHED)
    return variant.meta["posted_url"]
```

Run: `uv run pytest tests/test_publish.py -v` — Expected: all PASS

- [ ] **Step 4: Write the failing CLI tests**

Append to `tests/test_cli.py`:

```python
@pytest.fixture()
def approved(ws):
    src = ws.create_source("Ready", created="2026-07-13")
    v = ws.create_variant(src, "x", body="One\n\n---tweet---\n\nTwo")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    return ws, src


def test_post_dry_run_prints_without_posting(approved):
    ws, src = approved
    result = runner.invoke(app, ["post", "ready", "--dry-run"])
    assert result.exit_code == 0
    assert "would post 2 tweets" in result.output
    assert ws.load_variant(src, "x").status == Status.APPROVED  # unchanged


def test_post_requires_auth_token(approved, monkeypatch):
    from agenticsocial.x import auth as x_auth
    monkeypatch.setattr(x_auth, "load_token", lambda: None)
    result = runner.invoke(app, ["post", "ready"])
    assert result.exit_code == 1
    assert "agsoc auth x" in result.output


def test_post_publishes_and_prints_url(approved, monkeypatch):
    ws, src = approved
    from agenticsocial.x import auth as x_auth
    monkeypatch.setattr(x_auth, "load_token", lambda: {"access_token": "tok", "refresh_token": "r"})

    class FakeClient:
        def __init__(self, *a, **k):
            self.n = 0
        def post_tweet(self, text, in_reply_to=None):
            self.n += 1
            return f"id{self.n}"

    import agenticsocial.cli as cli_mod
    monkeypatch.setattr(cli_mod, "XClient", FakeClient)
    result = runner.invoke(app, ["post", "ready"])
    assert result.exit_code == 0
    assert "https://x.com/i/web/status/id1" in result.output
    assert ws.load_variant(src, "x").status == Status.PUBLISHED


def test_post_unapproved_fails_loudly(ws):
    src = ws.create_source("Unready", created="2026-07-13")
    ws.create_variant(src, "x", body="hi")
    result = runner.invoke(app, ["post", "unready"])
    assert result.exit_code == 1
    assert "allowed next" in result.output
```

Run: `uv run pytest tests/test_cli.py -v` — Expected: new tests FAIL ("No such command 'post'")

- [ ] **Step 5: Implement the post command**

Add to `src/agenticsocial/cli.py` (new imports: `from .models import Status, TransitionError, assert_transition`, `from .x.client import XApiError, XClient`, `from .x.publish import ValidationError, format_review, publish_variant, validate_thread`):

```python
@app.command()
def post(
    source: str,
    platform: str = typer.Option("x", "--platform"),
    dry_run: bool = typer.Option(False, "--dry-run", help="validate and print; no network, no status change"),
    resume: bool = typer.Option(False, "--resume", help="continue a failed thread from where it stopped"),
) -> None:
    """Publish an approved variant to X. Threads post tweet-by-tweet, resumably."""
    if platform != "x":
        raise _fail(f"unsupported platform '{platform}' — v1 posts to: x")
    ws = _workspace()
    src, v = _load(ws, source, platform)
    try:
        tweets = validate_thread(v.body)
    except ValidationError as e:
        raise _fail(str(e))
    if dry_run:
        typer.echo(f"would post {len(tweets)} tweets:\n")
        typer.echo(format_review(tweets))
        return
    if v.status is Status.FAILED and not resume:
        raise _fail(
            f"{src.id} previously failed after {len(v.meta.get('posted_ids') or [])} tweets — "
            "rerun with --resume to continue the thread"
        )
    try:
        assert_transition(v.status, Status.PUBLISHING)  # gate check BEFORE touching the keyring
    except TransitionError as e:
        raise _fail(str(e))
    token = x_auth.load_token()
    if not token:
        raise _fail("no X token — connect first with `agsoc auth x`")
    client_id = load_config(ws).get("x", {}).get("client_id", "")
    if client_id and token.get("refresh_token"):
        try:
            token = x_auth.refresh(client_id, token)
        except x_auth.AuthError as e:
            raise _fail(str(e))
    try:
        url = publish_variant(ws, v, XClient(token["access_token"]))
    except TransitionError as e:
        raise _fail(str(e))
    except XApiError as e:
        raise _fail(f"posting failed mid-thread: {e}\nresume with: agsoc post {src.id} --resume")
    typer.echo(f"published: {url}")
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/agenticsocial/x/publish.py src/agenticsocial/cli.py tests/test_publish.py tests/test_cli.py
git commit -m "feat: add resume-safe thread publishing and post command"
```

---

### Task 12: Research briefs

**Files:**
- Create: `src/agenticsocial/research.py`
- Modify: `src/agenticsocial/cli.py`
- Test: `tests/test_research.py`, `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `Workspace.resolve_source` (Task 5), `atomic_write` (Task 5), `_workspace`/`_fail` (Task 7).
- Produces: `research.search(query: str, max_results: int = 8) -> list[dict]` (dicts with `title`, `href`, `body` — thin wrapper over `ddgs.DDGS().text`); `research.extract(url: str) -> str | None` (trafilatura fetch+extract, None on failure); `research.build_brief(title: str, query: str, results: list[dict], extracts: dict[str, str]) -> str` (pure markdown formatting, always cites URLs). CLI command `agsoc research SOURCE [--query TEXT] [--max-results N]` writing `brief.md` (overwrites).

- [ ] **Step 1: Write the failing tests**

`tests/test_research.py`:

```python
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
```

Append to `tests/test_cli.py`:

```python
def test_research_writes_brief(ws, monkeypatch):
    src = ws.create_source("Kill staging", created="2026-07-13")
    import agenticsocial.cli as cli_mod
    monkeypatch.setattr(
        cli_mod.research, "search",
        lambda query, max_results=8: [{"title": "T1", "href": "https://ex.com/a", "body": "snippet"}],
    )
    monkeypatch.setattr(cli_mod.research, "extract", lambda url: "article text")
    result = runner.invoke(app, ["research", "staging"])
    assert result.exit_code == 0
    brief = (src.dir / "brief.md").read_text(encoding="utf-8")
    assert "https://ex.com/a" in brief
    assert "brief.md" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agenticsocial.research'`

- [ ] **Step 3: Implement**

`src/agenticsocial/research.py`:

```python
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
```

Add to `src/agenticsocial/cli.py` (imports: `from . import research` and `from .workspace import ..., atomic_write`):

```python
@app.command("research")
def research_cmd(
    source: str,
    query: Optional[str] = typer.Option(None, "--query", help="search query (default: source title)"),
    max_results: int = typer.Option(8, "--max-results"),
) -> None:
    """Fetch search results (and the origin article, if any) into brief.md."""
    ws = _workspace()
    try:
        src = ws.resolve_source(source)
    except WorkspaceError as e:
        raise _fail(str(e))
    q = query or src.title
    results = research.search(q, max_results=max_results)
    extracts: dict[str, str] = {}
    if src.origin_url:
        text = research.extract(src.origin_url)
        if text:
            extracts[src.origin_url] = text
    brief = research.build_brief(src.title, q, results, extracts)
    atomic_write(src.dir / "brief.md", brief)
    typer.echo(f"wrote {src.dir / 'brief.md'} ({len(results)} results, {len(extracts)} extractions)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research.py tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agenticsocial/research.py src/agenticsocial/cli.py tests/test_research.py tests/test_cli.py
git commit -m "feat: add research command building cited briefs"
```

---

### Task 13: Agent skills & README

**Files:**
- Create: `skills/fanout/SKILL.md`, `skills/capture/SKILL.md`, `skills/repurpose/SKILL.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the full CLI surface (Tasks 7–12).
- Produces: three agent skills usable from Claude Code (or as plain prompts elsewhere); a README covering install, X app setup, workflow, and skills. No code — verify by running the documented commands.

- [ ] **Step 1: Write the fanout skill**

`skills/fanout/SKILL.md`:

```markdown
---
name: fanout
description: Use when the user wants to turn an agenticsocial source into platform drafts — reads the voice profile and research brief, writes variants, and stops at in_review for human approval.
---

# Fanout: source → platform variants

You are drafting social content from a source in an agenticsocial workspace.

## Hard rules
- NEVER run `agsoc approve` or `agsoc post`. Your job ends at `in_review`.
- ALWAYS read `voice.md` before writing a single word, and follow its
  per-platform rules exactly.
- If `brief.md` exists in the source directory, ground claims in it and
  keep source URLs handy for reference links.

## Workflow
1. Find the source: `agsoc list`, then read `workspace/sources/<id>/source.md`
   (and `brief.md` if present).
2. Read `workspace/voice.md`.
3. Draft the X variant at `workspace/sources/<id>/x.md`:
   - YAML frontmatter: `platform: x`, `status: draft`, `approved_at: null`,
     `posted_url: null`, `posted_at: null`, `posted_ids: []`
   - Body: tweets separated by `---tweet---` on its own line.
   - The first tweet is the hook. Write 2–3 alternative hooks as an HTML
     comment (`<!-- alt hooks: ... -->`) at the end of the file so the user
     can swap.
   - Keep every tweet ≤ 280 chars (URLs count as 23). Check with
     `agsoc review <id>` — fix anything flagged.
4. Set `status: in_review` in the frontmatter when the draft is ready.
5. Tell the user: review with `agsoc review <id>`, approve with
   `agsoc approve <id>`, then `agsoc post <id>`.
```

- [ ] **Step 2: Write the capture skill**

`skills/capture/SKILL.md`:

```markdown
---
name: capture
description: Use when the user dumps rough ideas, voice-note transcripts, or a stream of thoughts — turns them into clean agenticsocial sources for later drafting.
---

# Capture: rough input → clean sources

Turn a messy idea dump into one or more agenticsocial sources.

## Workflow
1. Split the input into distinct post-worthy ideas. Merge fragments that
   belong together; drop filler.
2. For each idea, run: `agsoc new "<crisp working title>"`.
   For a long transcript, save it to a file first and use
   `agsoc new "<title>" --file <path>`.
3. Append a short summary of the user's raw thinking to the body of each
   created `source.md` (below the frontmatter) so context isn't lost.
4. Report the created source ids and suggest next steps: `agsoc research <id>`
   for topics needing grounding, or the fanout skill to draft now.

## Hard rules
- Never invent ideas the user didn't express.
- Never run `agsoc approve` or `agsoc post`.
```

- [ ] **Step 3: Write the repurpose skill**

`skills/repurpose/SKILL.md`:

```markdown
---
name: repurpose
description: Use when the user has long-form content (blog post URL, article, video transcript) to turn into platform-native social posts via agenticsocial.
---

# Repurpose: long-form → platform variants

Turn existing long-form content into social variants.

## Workflow
1. Create the source:
   - Blog/article: `agsoc new "<title>" --url <url>` then `agsoc research <id>`
     (this also extracts the article text into `brief.md`).
   - Transcript: `agsoc new "<title>" --file <transcript path>`.
2. Read the extracted content. Identify the 1–3 strongest standalone
   insights — a thread carries ONE insight, not a summary of everything.
3. Follow the fanout skill from step 2 to draft variants in the user's voice.
4. Include a link back to the original in the final tweet.

## Hard rules
- Platform-native beats faithful: rewrite, don't excerpt.
- Never run `agsoc approve` or `agsoc post`.
```

- [ ] **Step 4: Write the README**

Replace `README.md` with:

```markdown
# agenticsocial

Local-first, agent-driven content pipeline. Your agent (Claude Code or any
agentic CLI) gathers research and drafts posts in your voice; a deliberately
dumb CLI (`agsoc`) owns storage, the human approval gate, and publishing to X.
Nothing goes live without you running `agsoc approve`.

**v1 publishes to X/Twitter.** LinkedIn and YouTube variants are structured-for
and land next.

## Install

```bash
uv tool install agenticsocial   # or: pip install agenticsocial
agsoc init                      # scaffolds ./workspace
```

Then edit `workspace/voice.md` — it's what makes drafts sound like you.

## Connect X

1. Create an app at https://developer.x.com (free tier: ~500 posts/month).
2. In *User authentication settings*: OAuth 2.0, type **Native App** (public
   client), callback URL `http://localhost:8721/callback`.
3. Put the OAuth 2.0 Client ID in `workspace/config.toml` under `[x] client_id`.
4. Run `agsoc auth x` — tokens are stored in your OS keychain, never in files.

## Workflow

```bash
agsoc new "Why we deleted staging"        # capture an idea
agsoc research staging                    # fetch a cited brief into brief.md
# → your agent drafts workspace/sources/<id>/x.md (see skills/)
agsoc review staging                      # per-tweet char counts
agsoc approve staging                     # the human gate
agsoc post staging                        # thread goes live, URL recorded
agsoc post staging --resume               # continue if a thread failed mid-way
```

Content lives in `workspace/` as plain markdown with YAML frontmatter.
Statuses: `draft → in_review → approved → publishing → published | failed`.
Only the CLI moves statuses; agents draft, humans approve.

## Agent skills

`skills/` ships three skills for Claude Code (usable as plain prompts anywhere):

- **capture** — idea dump → clean sources
- **fanout** — source + voice profile + brief → platform drafts, stopping at `in_review`
- **repurpose** — blog post / transcript → platform-native variants

## Development

```bash
uv sync && uv run pytest
```

Apache-2.0. Contributions welcome — especially LinkedIn/YouTube publishers
and the Fanout web UI (see `docs/superpowers/specs/`).
```

- [ ] **Step 5: Verify documented commands against reality**

Run: `uv run pytest -q` (all pass), then smoke-test the documented workflow end-to-end without network:

```bash
export AGSOC_WORKSPACE=/tmp/agsoc-smoke
uv run agsoc init /tmp/agsoc-smoke
uv run agsoc new "Why we deleted staging"
uv run agsoc list
printf -- '---\nplatform: x\nstatus: in_review\napproved_at: null\nposted_url: null\nposted_at: null\nposted_ids: []\n---\nHello thread\n\n---tweet---\n\nSecond tweet\n' > /tmp/agsoc-smoke/sources/*staging*/x.md
uv run agsoc review staging
uv run agsoc approve staging
uv run agsoc post staging --dry-run
uv run agsoc status
unset AGSOC_WORKSPACE
```

Expected: each command exits 0; `post --dry-run` prints "would post 2 tweets"; `status` shows `approved 1`.

- [ ] **Step 6: Commit**

```bash
git add skills README.md
git commit -m "docs: add agent skills and README"
```

---

## Final verification (after all tasks)

- [ ] `uv run pytest -v` — full suite green.
- [ ] Smoke-test from Task 13 Step 5 passes.
- [ ] Grep gate integrity: `grep -rn "approve\|post" skills/` — every skill contains the "Never run `agsoc approve` or `agsoc post`" rule.
- [ ] No tokens or workspace content staged: `git status` shows no `workspace/` files.
```

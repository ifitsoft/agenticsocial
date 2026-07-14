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

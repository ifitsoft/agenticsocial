"""Domain model for video series and episodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models import Status

FORMATS = ("vertical", "wide")


class SeriesError(Exception):
    pass


class EpisodeError(Exception):
    pass


@dataclass(frozen=True)
class Series:
    slug: str
    name: str
    dir: Path
    byline: str = ""
    cadence: str = "daily"
    register: str = "reported"
    target_sec: int = 120
    tolerance_sec: int = 8
    formats: list[str] = field(default_factory=lambda: ["vertical", "wide"])
    design: dict = field(default_factory=dict)
    acts: list[dict] = field(default_factory=list)
    warm_acts: list[str] = field(default_factory=list)

    @property
    def episodes_dir(self) -> Path:
        return self.dir / "episodes"


@dataclass(frozen=True)
class Episode:
    id: str
    series_slug: str
    dir: Path
    status: Status
    meta: dict = field(default_factory=dict)

    @property
    def script_path(self) -> Path:
        return self.dir / "script.yaml"

    @property
    def sources_dir(self) -> Path:
        return self.dir / "sources"

    @property
    def out_dir(self) -> Path:
        return self.dir / "out"

    @property
    def probe_dir(self) -> Path:
        """Single-frame inspection PNGs. Spec §5 puts it beside `out/`, and
        `create_episode` has made it since Phase 1. Beside rather than inside
        because `out/` is the deliverable — the thing you upload — and a probe
        is a working note about it."""
        return self.dir / "probe"

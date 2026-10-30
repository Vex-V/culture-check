"""Settings, read once from the environment (and `.env` in the working
directory, when there is one). Everything else asks `settings()`."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """KEY=value lines, never over a variable already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    data: Path
    qloo_key: str = field(repr=False)
    qloo_base: str
    vlm: str
    llm: str
    max_seconds: float
    max_mb: float
    per_visitor_day: int
    per_day: int

    @property
    def uploads(self) -> Path:
        return self.data / "uploads"

    @property
    def out(self) -> Path:
        """Where vidra writes one folder per video."""
        return self.data / "vidra" / "out"

    @property
    def reports(self) -> Path:
        return self.data / "reports"

    @property
    def qloo_cache(self) -> Path:
        return self.data / "qloo-cache"


def from_env() -> Settings:
    _load_env_file(Path.cwd() / ".env")
    env = os.environ.get
    return Settings(
        data=Path(env("CC_DATA", "data")).resolve(),
        qloo_key=env("QLOO_API_KEY", ""),
        qloo_base=env("QLOO_API_BASE", "https://hackathon.api.qloo.com").rstrip("/"),
        vlm=env("CC_VLM", ""),
        llm=env("CC_LLM", ""),
        max_seconds=float(env("CC_MAX_SECONDS", "90")),
        max_mb=float(env("CC_MAX_MB", "60")),
        per_visitor_day=int(env("CC_PER_VISITOR_DAY", "5")),
        per_day=int(env("CC_PER_DAY", "100")),
    )


@lru_cache(maxsize=1)
def settings() -> Settings:
    return from_env()


@lru_cache(maxsize=1)
def start_vidra() -> None:
    """Point vidra's data root (custom questions, weights) inside ours; once."""
    import vidra

    vidra.configure(data_root=settings().data / "vidra")

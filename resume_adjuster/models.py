from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


class Stage(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    TAILORING = "tailoring"
    RENDERING = "rendering"
    CHECKING = "checking_layout"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Project:
    source_id: str
    title: str
    url: str | None
    bullets: list[str]
    source_order: int
    proposed: bool = False


@dataclass
class ParsedResume:
    projects: list[Project]
    skills: dict[str, list[str]]
    paragraphs: list[str]


@dataclass
class TailoredResume:
    projects: list[Project]
    skills: dict[str, list[str]]
    notices: list[str] = field(default_factory=list)


@dataclass
class Job:
    id: str
    work_dir: Path
    stage: Stage = Stage.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    error_code: str | None = None
    error: str | None = None
    notices: list[str] = field(default_factory=list)
    result: Path | None = None
    cancel_requested: bool = False

    def public(self) -> dict:
        return {
            "id": self.id,
            "stage": self.stage,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "error_code": self.error_code,
            "error": self.error,
            "notices": self.notices,
            "ready": self.stage == Stage.READY,
        }

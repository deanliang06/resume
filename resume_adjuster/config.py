from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path = Path(".resume-adjuster-data")
    max_upload_bytes: int = 5 * 1024 * 1024
    max_expanded_bytes: int = 50 * 1024 * 1024
    result_ttl_seconds: int = 30 * 60
    abandoned_ttl_seconds: int = 60 * 60
    job_timeout_seconds: int = 5 * 60
    conversion_timeout_seconds: int = 60
    max_render_attempts: int = 12

    @property
    def jobs_root(self) -> Path:
        return self.data_root / "jobs"

    @property
    def results_root(self) -> Path:
        return self.data_root / "results"

    @property
    def converter(self) -> str | None:
        configured = os.getenv("RESUME_ADJUSTER_SOFFICE")
        return configured or shutil.which("soffice") or shutil.which("libreoffice")

    @property
    def generation_model(self) -> str:
        return os.getenv("RESUME_ADJUSTER_MODEL", "gpt-5-mini")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(data_root=Path(os.getenv("RESUME_ADJUSTER_DATA", ".resume-adjuster-data")))

    def initialize(self) -> None:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.results_root.mkdir(parents=True, exist_ok=True)

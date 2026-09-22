from __future__ import annotations

import os
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

    @property
    def jobs_root(self) -> Path:
        return self.data_root / "jobs"

    @property
    def results_root(self) -> Path:
        return self.data_root / "results"

    @property
    def generation_model(self) -> str:
        return os.getenv("RESUME_ADJUSTER_MODEL", "deepseek/deepseek-v4-flash-0731")

    @property
    def generation_base_url(self) -> str:
        return os.getenv("RESUME_ADJUSTER_BASE_URL", "https://openrouter.ai/api/v1")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(data_root=Path(os.getenv("RESUME_ADJUSTER_DATA", ".resume-adjuster-data")))

    def initialize(self) -> None:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.results_root.mkdir(parents=True, exist_ok=True)

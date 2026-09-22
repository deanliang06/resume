from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .docx_template import apply_tailoring, parse_resume, validate_docx_package
from .errors import JobCancelled, ResumeError
from .generation import OpenAIProjectGenerator
from .latex_template import apply_latex_tailoring, parse_latex
from .models import Job, Stage
from .skill_profiles import skill_labels
from .tailoring import tailor

LOG = logging.getLogger("resume_adjuster.jobs")


class JobManager:
    def __init__(self, settings: Settings, project_generator=None):
        self.settings = settings
        self.settings.initialize()
        self.project_generator = project_generator or OpenAIProjectGenerator(
            model=settings.generation_model,
            base_url=settings.generation_base_url,
        )
        self.jobs: dict[str, Job] = {}
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="resume-worker")

    def create(self, upload: bytes, description: str, skills_format: str = "standard") -> Job:
        from .errors import InvalidInput

        if not description.strip():
            raise InvalidInput("A job description is required.")
        skill_labels(skills_format)
        if len(upload) > self.settings.max_upload_bytes:
            raise InvalidInput("The uploaded DOCX exceeds the 5 MB limit.")
        job_id = uuid.uuid4().hex
        work_dir = (self.settings.jobs_root / job_id).resolve()
        self._assert_owned(work_dir, self.settings.jobs_root)
        work_dir.mkdir(parents=True)
        source = work_dir / "source.docx"
        source.write_bytes(upload)
        try:
            validate_docx_package(source, self.settings.max_expanded_bytes)
            parse_resume(source)
        except Exception:
            self._safe_rmtree(work_dir, self.settings.jobs_root)
            raise
        job = Job(job_id, work_dir, skills_format=skills_format)
        with self.lock:
            self.jobs[job_id] = job
        self.executor.submit(self._run, job, source, description)
        return job

    def create_latex(
        self,
        source_text: str,
        description: str,
        skills_format: str = "standard",
    ) -> Job:
        from .errors import InvalidInput

        if not description.strip():
            raise InvalidInput("A job description is required.")
        skill_labels(skills_format)
        source_bytes = source_text.encode("utf-8")
        if len(source_bytes) > self.settings.max_upload_bytes:
            raise InvalidInput("The LaTeX source exceeds the 5 MB limit.")
        template, _ = parse_latex(source_text)
        job_id = uuid.uuid4().hex
        work_dir = (self.settings.jobs_root / job_id).resolve()
        self._assert_owned(work_dir, self.settings.jobs_root)
        work_dir.mkdir(parents=True)
        source = work_dir / "source.tex"
        source.write_text(template.source, encoding="utf-8")
        job = Job(
            job_id,
            work_dir,
            output_format="latex",
            skills_format=skills_format,
        )
        with self.lock:
            self.jobs[job_id] = job
        self.executor.submit(self._run_latex, job, source, description)
        return job

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.expires_at and datetime.now(timezone.utc) >= job.expires_at and job.stage == Stage.READY:
                job.stage = Stage.FAILED
                job.error_code = "expired_result"
                job.error = "This result has expired. Submit the resume again."
                if job.result and job.result.exists():
                    job.result.unlink()
                job.result = None
            return job

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.stage in {Stage.READY, Stage.FAILED, Stage.CANCELLED}:
            return False
        job.cancel_requested = True
        return True

    def _stage(self, job: Job, stage: Stage) -> None:
        if job.cancel_requested:
            raise JobCancelled("The job was cancelled.")
        job.stage = stage
        job.updated_at = datetime.now(timezone.utc)
        LOG.info("job=%s stage=%s", job.id, stage)

    def _run(self, job: Job, source: Path, description: str) -> None:
        started = time.monotonic()
        try:
            self._stage(job, Stage.VALIDATING)
            validate_docx_package(source, self.settings.max_expanded_bytes)
            _, _, parsed = parse_resume(source)
            self._stage(job, Stage.TAILORING)
            candidate = tailor(
                parsed,
                description,
                self.project_generator,
                job.skills_format,
            )
            if time.monotonic() - started > self.settings.job_timeout_seconds:
                raise ResumeError("The job exceeded its five-minute deadline.", code="timeout")
            self._stage(job, Stage.WRITING)
            candidate_path = job.work_dir / "candidate.docx"
            apply_tailoring(source, candidate_path, candidate)
            validate_docx_package(candidate_path, self.settings.max_expanded_bytes)
            parse_resume(candidate_path)
            result = (self.settings.results_root / f"{job.id}.docx").resolve()
            self._assert_owned(result, self.settings.results_root)
            temporary = result.with_suffix(".tmp")
            shutil.copyfile(candidate_path, temporary)
            temporary.replace(result)
            job.result = result
            job.notices = candidate.notices
            job.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.settings.result_ttl_seconds)
            self._stage(job, Stage.READY)
        except JobCancelled as exc:
            job.stage = Stage.CANCELLED
            job.error_code = exc.code
            job.error = str(exc)
        except ResumeError as exc:
            job.stage = Stage.FAILED
            job.error_code = exc.code
            job.error = str(exc)
        except Exception:
            LOG.exception("job=%s unexpected failure", job.id)
            job.stage = Stage.FAILED
            job.error_code = "internal_error"
            job.error = "An unexpected internal error occurred."
        finally:
            job.updated_at = datetime.now(timezone.utc)
            self._safe_rmtree(job.work_dir, self.settings.jobs_root)
            LOG.info("job=%s final=%s duration=%.3f", job.id, job.stage, time.monotonic() - started)

    def _run_latex(self, job: Job, source: Path, description: str) -> None:
        started = time.monotonic()
        try:
            self._stage(job, Stage.VALIDATING)
            template, parsed = parse_latex(source.read_text(encoding="utf-8"))
            self._stage(job, Stage.TAILORING)
            candidate = tailor(
                parsed,
                description,
                self.project_generator,
                job.skills_format,
            )
            if time.monotonic() - started > self.settings.job_timeout_seconds:
                raise ResumeError("The job exceeded its five-minute deadline.", code="timeout")
            self._stage(job, Stage.WRITING)
            output = apply_latex_tailoring(template, candidate)
            parse_latex(output)
            result = (self.settings.results_root / f"{job.id}.tex").resolve()
            self._assert_owned(result, self.settings.results_root)
            temporary = result.with_suffix(".tmp")
            temporary.write_text(output, encoding="utf-8")
            temporary.replace(result)
            job.result = result
            job.notices = candidate.notices
            job.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.settings.result_ttl_seconds)
            self._stage(job, Stage.READY)
        except JobCancelled as exc:
            job.stage = Stage.CANCELLED
            job.error_code = exc.code
            job.error = str(exc)
        except ResumeError as exc:
            job.stage = Stage.FAILED
            job.error_code = exc.code
            job.error = str(exc)
        except Exception:
            LOG.exception("job=%s unexpected failure", job.id)
            job.stage = Stage.FAILED
            job.error_code = "internal_error"
            job.error = "An unexpected internal error occurred."
        finally:
            job.updated_at = datetime.now(timezone.utc)
            self._safe_rmtree(job.work_dir, self.settings.jobs_root)
            LOG.info("job=%s final=%s duration=%.3f", job.id, job.stage, time.monotonic() - started)

    @staticmethod
    def _assert_owned(target: Path, root: Path) -> None:
        target.resolve().relative_to(root.resolve())

    def _safe_rmtree(self, target: Path, root: Path) -> None:
        try:
            self._assert_owned(target, root)
            if target.resolve() == root.resolve():
                raise ValueError("Refusing to delete an owned root.")
            shutil.rmtree(target, ignore_errors=False)
        except FileNotFoundError:
            pass
        except Exception:
            LOG.warning("cleanup failed for job=%s", target.name, exc_info=True)

    def sweep(self) -> None:
        now = datetime.now(timezone.utc)
        with self.lock:
            for job in self.jobs.values():
                if job.stage == Stage.READY and job.expires_at and now >= job.expires_at:
                    self.get(job.id)
        cutoff = time.time() - self.settings.abandoned_ttl_seconds
        for child in self.settings.jobs_root.iterdir():
            if child.is_dir() and child.stat().st_mtime < cutoff:
                active = self.jobs.get(child.name)
                if not active or active.stage in {Stage.READY, Stage.FAILED, Stage.CANCELLED}:
                    self._safe_rmtree(child, self.settings.jobs_root)

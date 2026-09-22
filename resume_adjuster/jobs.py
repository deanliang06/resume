from __future__ import annotations

import copy
import logging
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .converter import LibreOfficeConverter
from .docx_template import apply_tailoring, parse_resume, validate_docx_package
from .errors import JobCancelled, LayoutFailure, ResumeError
from .generation import OpenAIProjectGenerator
from .models import Job, Stage, TailoredResume
from .pdf_validation import validate_pdf
from .tailoring import tailor

LOG = logging.getLogger("resume_adjuster.jobs")


class JobManager:
    def __init__(self, settings: Settings, converter=None, project_generator=None):
        self.settings = settings
        self.settings.initialize()
        self.converter = converter or LibreOfficeConverter(settings.converter, settings.conversion_timeout_seconds)
        self.project_generator = project_generator or OpenAIProjectGenerator(settings.generation_model)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="resume-worker")

    def create(self, upload: bytes, description: str) -> Job:
        from .errors import InvalidInput

        if not description.strip():
            raise InvalidInput("A job description is required.")
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
        job = Job(job_id, work_dir)
        with self.lock:
            self.jobs[job_id] = job
        self.executor.submit(self._run, job, source, description)
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

    def _fit_candidates(self, candidate: TailoredResume):
        current = copy.deepcopy(candidate)
        yield current
        # Remove optional third bullets from least-relevant projects first.
        for project in reversed(current.projects):
            if len(project.bullets) == 3:
                project.bullets.pop()
                yield copy.deepcopy(current)
        if len(current.projects) == 4:
            current.projects.pop()
            current.notices.append("Four supported projects did not fit; the lowest-ranked project was removed.")
            yield copy.deepcopy(current)

    def _run(self, job: Job, source: Path, description: str) -> None:
        started = time.monotonic()
        try:
            self._stage(job, Stage.VALIDATING)
            validate_docx_package(source, self.settings.max_expanded_bytes)
            _, _, parsed = parse_resume(source)
            self._stage(job, Stage.TAILORING)
            candidate = tailor(parsed, description, self.project_generator)
            last_error: Exception | None = None
            seen = set()
            for attempt, fitted in enumerate(self._fit_candidates(candidate), start=1):
                if attempt > self.settings.max_render_attempts:
                    break
                if time.monotonic() - started > self.settings.job_timeout_seconds:
                    raise ResumeError("The job exceeded its five-minute deadline.", code="timeout")
                signature = repr([(p.title, p.bullets) for p in fitted.projects]) + repr(fitted.skills)
                if signature in seen:
                    continue
                seen.add(signature)
                self._stage(job, Stage.RENDERING)
                docx_path = job.work_dir / f"candidate-{attempt}.docx"
                pdf_path = job.work_dir / f"candidate-{attempt}.pdf"
                apply_tailoring(source, docx_path, fitted)
                self.converter.convert(docx_path, pdf_path, job.work_dir / f"profile-{attempt}")
                self._stage(job, Stage.CHECKING)
                try:
                    validate_pdf(pdf_path, fitted)
                except LayoutFailure as exc:
                    last_error = exc
                    continue
                result = (self.settings.results_root / f"{job.id}.pdf").resolve()
                self._assert_owned(result, self.settings.results_root)
                temporary = result.with_suffix(".tmp")
                shutil.copyfile(pdf_path, temporary)
                temporary.replace(result)
                job.result = result
                job.notices = fitted.notices
                job.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.settings.result_ttl_seconds)
                self._stage(job, Stage.READY)
                return
            if last_error:
                raise LayoutFailure(f"No candidate satisfied the one-page layout rules: {last_error}")
            raise LayoutFailure("No valid layout candidate could be produced.")
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

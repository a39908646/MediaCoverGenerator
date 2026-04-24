from __future__ import annotations

import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from mediacovergenerator.logging import logger
from mediacovergenerator.models import JobSummary
from mediacovergenerator.storage import ConfigRepository, HistoryRepository

if TYPE_CHECKING:
    from mediacovergenerator.service import LibraryUpdateService


class JobManager:
    def __init__(self, project_root: Path, config_repository: ConfigRepository, history_repository: HistoryRepository):
        self.project_root = project_root
        self.config_repository = config_repository
        self.history_repository = history_repository
        self._service: LibraryUpdateService | None = None
        self._jobs: dict[str, JobSummary] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def _get_service(self) -> "LibraryUpdateService":
        if self._service is None:
            from mediacovergenerator.service import LibraryUpdateService

            self._service = LibraryUpdateService(self.project_root, self.history_repository)
        return self._service

    def list_jobs(self) -> list[JobSummary]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)

    def active_jobs(self) -> int:
        return sum(1 for job in self.list_jobs() if job.status in {"pending", "running"})

    def start(self, library_ids: list[str] | None = None, title: str = "") -> JobSummary:
        job_id = uuid.uuid4().hex
        summary = JobSummary(
            id=job_id,
            status="pending",
            created_at=datetime.utcnow(),
            title=title or "准备生成封面",
            library_ids=library_ids or [],
        )
        cancel_event = threading.Event()
        with self._lock:
            self._jobs[job_id] = summary
            self._cancel_events[job_id] = cancel_event
        thread = threading.Thread(target=self._run, args=(job_id, library_ids or []), daemon=True)
        thread.start()
        return summary

    def cancel(self, job_id: str) -> JobSummary:
        with self._lock:
            event = self._cancel_events[job_id]
        self._update(job_id, cancel_requested=True)
        event.set()
        return self._snapshot(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            if job.status in {"pending", "running"}:
                raise ValueError("Active job cannot be deleted")
            self._jobs.pop(job_id, None)
            self._cancel_events.pop(job_id, None)
            return True

    def delete_many(self, job_ids: list[str]) -> tuple[int, list[str], list[str]]:
        deleted = 0
        blocked: list[str] = []
        missing: list[str] = []
        for job_id in job_ids:
            try:
                self.delete(job_id)
                deleted += 1
            except KeyError:
                missing.append(job_id)
            except ValueError:
                blocked.append(job_id)
        return deleted, blocked, missing

    def _run(self, job_id: str, library_ids: list[str]) -> None:
        cancel_event = self._cancel_events[job_id]
        self._update(job_id, status="running", started_at=datetime.utcnow(), message="Loading configuration")
        try:
            service = self._get_service()
            config = self.config_repository.load()
            all_libraries = service.list_libraries(config)
            selected_ids = library_ids or ([] if not config.selected_library_ids else config.selected_library_ids)
            if selected_ids:
                target_libraries = [library for library in all_libraries if library.id in selected_ids]
            else:
                target_libraries = all_libraries

            self._update(
                job_id,
                title=self._build_title(target_libraries),
                total_libraries=len(target_libraries),
                library_ids=[library.id for library in target_libraries],
                library_names=[library.name for library in target_libraries],
                message="Generating covers",
            )

            for index, library in enumerate(target_libraries, start=1):
                if cancel_event.is_set():
                    self._update(job_id, status="cancelled", finished_at=datetime.utcnow(), message="Job cancelled")
                    return
                self._update(job_id, message=f"Processing {library.name} ({index}/{len(target_libraries)})")
                try:
                    service.generate_for_library(config, library.id, cancel_event)
                    current = self._snapshot(job_id)
                    self._update(job_id, completed_libraries=current.completed_libraries + 1)
                except Exception as exc:
                    logger.exception("Library update failed for %s", library.name)
                    current = self._snapshot(job_id)
                    self._update(
                        job_id,
                        failed_libraries=current.failed_libraries + 1,
                        errors=current.errors + [f"{library.name}: {exc}"],
                    )
            current = self._snapshot(job_id)
            final_status = "completed" if current.failed_libraries == 0 else "failed"
            self._update(job_id, status=final_status, finished_at=datetime.utcnow(), message="Job finished")
        except Exception as exc:
            logger.exception("Job failed")
            current = self._snapshot(job_id)
            self._update(
                job_id,
                status="failed",
                finished_at=datetime.utcnow(),
                message=str(exc),
                errors=current.errors + [str(exc)],
            )

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(update=changes)

    def _snapshot(self, job_id: str) -> JobSummary:
        with self._lock:
            return self._jobs[job_id]

    @staticmethod
    def _build_title(libraries) -> str:
        if not libraries:
            return "无可执行媒体库"
        names = [library.name for library in libraries]
        if len(names) == 1:
            return f"生成 {names[0]} 封面"
        if len(names) == 2:
            return f"生成 {names[0]}、{names[1]} 封面"
        return f"生成 {names[0]}、{names[1]} 等 {len(names)} 个媒体库封面"

from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from mediacovergenerator.jobs import JobManager
from mediacovergenerator.logging import logger
from mediacovergenerator.storage import ConfigRepository


class AppScheduler:
    def __init__(self, project_root: Path, config_repository: ConfigRepository, job_manager: JobManager):
        self.project_root = project_root
        self.config_repository = config_repository
        self.job_manager = job_manager
        self._scheduler = BackgroundScheduler()
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._scheduler.start()
            self._started = True
        self.reload()

    def shutdown(self) -> None:
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    def reload(self) -> None:
        config = self.config_repository.load()
        self._scheduler.remove_all_jobs()

        if not config.schedule.enabled:
            logger.info("Built-in scheduler disabled")
            return

        trigger = CronTrigger.from_crontab(config.schedule.cron)
        self._scheduler.add_job(
            self._scheduled_run,
            trigger=trigger,
            id="scheduled-cover-generation",
            replace_existing=True,
        )
        logger.info("Built-in scheduler enabled with cron: %s", config.schedule.cron)

    def _scheduled_run(self) -> None:
        if self.job_manager.active_jobs() > 0:
            logger.warning("Skipped scheduled run because another job is still active")
            return
        logger.info("Starting scheduled cover generation job")
        self.job_manager.start()


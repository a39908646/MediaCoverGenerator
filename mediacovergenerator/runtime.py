from __future__ import annotations

import threading
from pathlib import Path

from mediacovergenerator.logging import logger
from mediacovergenerator.service import LibraryUpdateService
from mediacovergenerator.storage import ConfigRepository, HistoryRepository


def run_once(project_root: Path) -> int:
    config_repository = ConfigRepository(project_root)
    history_repository = HistoryRepository(project_root)
    config = config_repository.load()
    service = LibraryUpdateService(project_root, history_repository)

    libraries = service.list_libraries(config)
    selected_ids = config.selected_library_ids or [library.id for library in libraries]
    if not selected_ids:
        logger.warning("No libraries selected and no libraries available; skipping run")
        return 0

    logger.info("Starting one-shot run for libraries: %s", selected_ids)
    failures: list[str] = []
    for library_id in selected_ids:
        try:
            service.generate_for_library(config, library_id, threading.Event())
            logger.info("Finished library %s", library_id)
        except Exception as exc:
            logger.exception("One-shot run failed for library %s", library_id)
            failures.append(f"{library_id}: {exc}")

    if failures:
        logger.error("One-shot run completed with failures: %s", failures)
        return 1

    logger.info("One-shot run completed successfully")
    return 0


from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mediacovergenerator.emby import EmbyClient
from mediacovergenerator.jobs import JobManager
from mediacovergenerator.logging import logger
from mediacovergenerator.models import AppConfig
from mediacovergenerator.storage import ConfigRepository


@dataclass(slots=True)
class WebhookResolution:
    library_id: str
    library_name: str
    event: str
    item_id: str | None = None


class EmbyWebhookManager:
    SUPPORTED_EVENTS = {"library.new"}

    def __init__(self, project_root: Path, config_repository: ConfigRepository, job_manager: JobManager):
        self.project_root = project_root
        self.config_repository = config_repository
        self.job_manager = job_manager
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def handle(self, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        config = self.config_repository.load()
        self._validate_config(config, token)
        resolution = self._resolve_payload(config, payload)
        if config.selected_library_ids and resolution.library_id not in config.selected_library_ids:
            logger.info(
                "Ignored webhook for library %s (%s) because it is not selected",
                resolution.library_name,
                resolution.library_id,
            )
            return {
                "accepted": True,
                "scheduled": False,
                "reason": "library_not_selected",
                "library_id": resolution.library_id,
                "library_name": resolution.library_name,
            }

        delay_seconds = max(0, int(config.webhook.delay_seconds))
        self._schedule_library_job(resolution.library_id, resolution.library_name, delay_seconds)
        return {
            "accepted": True,
            "scheduled": True,
            "event": resolution.event,
            "library_id": resolution.library_id,
            "library_name": resolution.library_name,
            "delay_seconds": delay_seconds,
        }

    def _validate_config(self, config: AppConfig, token: str | None) -> None:
        if not config.webhook.enabled:
            raise PermissionError("Webhook monitoring is disabled")
        expected_token = (config.webhook.token or "").strip()
        if expected_token and token != expected_token:
            raise ValueError("Invalid webhook token")

    def _resolve_payload(self, config: AppConfig, payload: dict[str, Any]) -> WebhookResolution:
        event = str(payload.get("Event") or payload.get("event") or "").strip()
        if event not in self.SUPPORTED_EVENTS:
            raise LookupError(f"Unsupported webhook event: {event or 'unknown'}")

        item = payload.get("Item") or payload.get("item") or {}
        library_map = EmbyClient(config.emby).get_library_map()

        direct_library_id = str(item.get("LibraryId") or payload.get("LibraryId") or "").strip()
        if direct_library_id and direct_library_id in library_map:
            library = library_map[direct_library_id]
            return WebhookResolution(
                library_id=direct_library_id,
                library_name=library.get("Name", direct_library_id),
                event=event,
                item_id=str(item.get("Id") or payload.get("Id") or "") or None,
            )

        item_path = self._extract_item_path(item)
        if item_path:
            matched = self._match_library_by_path(library_map, item_path)
            if matched:
                return WebhookResolution(
                    library_id=matched["Id"],
                    library_name=matched.get("Name", matched["Id"]),
                    event=event,
                    item_id=str(item.get("Id") or payload.get("Id") or "") or None,
                )

        item_id = str(item.get("Id") or payload.get("Id") or "").strip()
        if item_id:
            client = EmbyClient(config.emby)
            item_info = client.get_item(item_id)
            item_path = self._extract_item_path(item_info)
            if item_path:
                matched = self._match_library_by_path(library_map, item_path)
                if matched:
                    return WebhookResolution(
                        library_id=matched["Id"],
                        library_name=matched.get("Name", matched["Id"]),
                        event=event,
                        item_id=item_id,
                    )

        raise LookupError("Unable to resolve library from webhook payload")

    def _schedule_library_job(self, library_id: str, library_name: str, delay_seconds: int) -> None:
        with self._lock:
            existing = self._timers.pop(library_id, None)
            if existing:
                existing.cancel()

            timer = threading.Timer(
                delay_seconds,
                self._run_scheduled_job,
                args=(library_id, library_name),
            )
            timer.daemon = True
            self._timers[library_id] = timer
            timer.start()
        logger.info(
            "Scheduled webhook update for library %s (%s) after %s seconds",
            library_name,
            library_id,
            delay_seconds,
        )

    def _run_scheduled_job(self, library_id: str, library_name: str) -> None:
        with self._lock:
            self._timers.pop(library_id, None)
        self.job_manager.start(
            [library_id],
            title=f"入库监控：更新 {library_name} 封面",
        )

    @staticmethod
    def _extract_item_path(item: dict[str, Any]) -> str | None:
        path = item.get("Path") or item.get("path")
        return str(path).strip() if path else None

    @staticmethod
    def _normalize_path(value: str) -> str:
        return value.replace("\\", "/").rstrip("/").lower()

    def _match_library_by_path(self, library_map: dict[str, dict[str, Any]], item_path: str) -> dict[str, Any] | None:
        normalized_item_path = self._normalize_path(item_path)
        best_match: tuple[int, dict[str, Any]] | None = None
        for library in library_map.values():
            for location in library.get("Locations", []) or []:
                normalized_location = self._normalize_path(str(location))
                if (
                    normalized_item_path == normalized_location
                    or normalized_item_path.startswith(f"{normalized_location}/")
                ):
                    match_length = len(normalized_location)
                    if not best_match or match_length > best_match[0]:
                        best_match = (match_length, library)
        return best_match[1] if best_match else None

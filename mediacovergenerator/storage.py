from __future__ import annotations

import copy
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mediacovergenerator.models import AppConfig, HistoryRecord, LibraryTitleConfig
from mediacovergenerator.titles import dump_title_config, load_title_config


def resolve_path(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


class ConfigRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._lock = threading.RLock()
        self.config_path = project_root / "data" / "config.json"

    def load(self) -> AppConfig:
        with self._lock:
            if not self.config_path.exists():
                config = AppConfig()
                self.save(config)
                return config
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            config = AppConfig.model_validate(data)
            if not config.library_titles and config.titles_yaml.strip():
                config = config.model_copy(
                    update={
                        "library_titles": [
                            LibraryTitleConfig(
                                library_name=name,
                                zh_title=values[0] if len(values) > 0 else name,
                                en_title=values[1] if len(values) > 1 else "",
                                bg_color=values[2] if len(values) > 2 else "",
                            )
                            for name, values in load_title_config(config.titles_yaml).items()
                        ]
                    }
                )
            normalized = config.model_dump(mode="json")
            if normalized != data:
                self.save(config)
            return config

    def save(self, config: AppConfig) -> AppConfig:
        with self._lock:
            config = config.model_copy(
                update={
                    "library_titles": [
                        item
                        for item in config.library_titles
                        if (item.library_id or item.library_name or item.zh_title or item.en_title or item.bg_color)
                    ],
                }
            )
            config = config.model_copy(
                update={
                    "titles_yaml": dump_title_config(config.library_titles),
                }
            )
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.ensure_directories(config)
            return config

    def ensure_directories(self, config: AppConfig) -> None:
        for raw_path in [
            config.paths.data_dir,
            config.paths.cache_dir,
            config.paths.covers_input_dir,
            config.paths.recent_covers_dir,
            config.paths.fonts_dir,
        ]:
            resolve_path(self.project_root, raw_path).mkdir(parents=True, exist_ok=True)


class HistoryRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._lock = threading.RLock()
        self.history_path = project_root / "data" / "history.json"

    def load(self) -> list[HistoryRecord]:
        with self._lock:
            if not self.history_path.exists():
                return []
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return [HistoryRecord.model_validate(item) for item in data]

    def save(self, records: list[HistoryRecord]) -> None:
        with self._lock:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(
                json.dumps([record.model_dump(mode="json") for record in records], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def append(self, record: HistoryRecord, limit: int = 200) -> None:
        with self._lock:
            records = self.load()
            records.insert(0, record)
            self.save(records[:limit])

    def list_recent(self, limit: int = 50) -> list[HistoryRecord]:
        return self.load()[:limit]

    def get(self, record_id: str) -> HistoryRecord | None:
        with self._lock:
            return next((record for record in self.load() if record.id == record_id), None)

    def delete(self, record_id: str, delete_file: bool = True) -> bool:
        with self._lock:
            records = self.load()
            target = next((record for record in records if record.id == record_id), None)
            if not target:
                return False
            remaining = [record for record in records if record.id != record_id]
            self.save(remaining)
            if delete_file and target.saved_path:
                try:
                    Path(target.saved_path).unlink(missing_ok=True)
                except OSError:
                    pass
            return True

    def delete_many(self, record_ids: list[str], delete_files: bool = True) -> int:
        with self._lock:
            if not record_ids:
                return 0
            record_ids_set = set(record_ids)
            records = self.load()
            targets = [record for record in records if record.id in record_ids_set]
            if not targets:
                return 0
            remaining = [record for record in records if record.id not in record_ids_set]
            self.save(remaining)
            if delete_files:
                for record in targets:
                    if not record.saved_path:
                        continue
                    try:
                        Path(record.saved_path).unlink(missing_ok=True)
                    except OSError:
                        pass
            return len(targets)

    def clear(self, delete_files: bool = True) -> int:
        with self._lock:
            records = self.load()
            count = len(records)
            if delete_files:
                for record in records:
                    if not record.saved_path:
                        continue
                    try:
                        Path(record.saved_path).unlink(missing_ok=True)
                    except OSError:
                        pass
            self.save([])
            return count


class WebhookRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._lock = threading.RLock()
        self.webhook_path = project_root / "data" / "last_webhook.json"

    def save(self, payload: dict[str, Any], token_provided: bool) -> dict[str, Any]:
        with self._lock:
            record = {
                "received_at": datetime.now(timezone.utc).isoformat(),
                "token_provided": token_provided,
                "payload": copy.deepcopy(payload),
            }
            self.webhook_path.parent.mkdir(parents=True, exist_ok=True)
            self.webhook_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return record

    def load(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.webhook_path.exists():
                return None
            return json.loads(self.webhook_path.read_text(encoding="utf-8"))

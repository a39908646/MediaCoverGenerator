from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SortBy = Literal["Random", "PremiereDate", "DateCreated"]
CoverStyle = Literal[
    "static_1",
    "static_2",
    "static_3",
]


class EmbySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "emby"
    base_url: str = ""
    api_key: str = ""
    verify_ssl: bool = True
    timeout_seconds: int = 30


class PathsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_dir: str = "data"
    cache_dir: str = "data/cache"
    covers_input_dir: str = "data/input"
    recent_covers_dir: str = "data/recent_covers"
    fonts_dir: str = "data/fonts"


class ScheduleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    cron: str = "0 3 * * *"


class WebhookSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    token: str = ""
    delay_seconds: int = 60


class CoverSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: CoverStyle = "static_1"
    sort_by: SortBy = "Random"
    use_primary: bool = True
    resolution: str = "480p"
    custom_width: int = 1920
    custom_height: int = 1080
    zh_font_preset: str = "chaohei"
    en_font_preset: str = "EmblemaOne"
    zh_font_custom: str = ""
    en_font_custom: str = ""
    zh_font_size: float = 170
    en_font_size: float = 75
    zh_font_offset: float = 0
    title_spacing: float = 40
    en_line_spacing: float = 40
    title_scale: float = 1.0
    blur_size: int = 50
    color_ratio: float = 0.8
    multi_1_blur: bool = True
    bg_color_mode: Literal["auto", "custom", "config"] = "auto"
    custom_bg_color: str = ""
    save_recent_covers: bool = True
    covers_history_limit_per_library: int = 10


class LibraryTitleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_id: str = ""
    library_name: str = ""
    zh_title: str = ""
    en_title: str = ""
    bg_color: str = ""


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emby: EmbySettings = Field(default_factory=EmbySettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    webhook: WebhookSettings = Field(default_factory=WebhookSettings)
    cover: CoverSettings = Field(default_factory=CoverSettings)
    selected_library_ids: list[str] = Field(default_factory=list)
    library_titles: list[LibraryTitleConfig] = Field(default_factory=list)
    titles_yaml: str = Field(
        default=(
            "# 示例\n"
            "\"电影\": [\"电影\", \"MOVIES\"]\n"
            "\"电视剧\": [\"剧集\", \"SERIES\", \"#24415a\"]\n"
        )
    )


class LibraryInfo(BaseModel):
    id: str
    name: str
    collection_type: str = ""


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_ids: list[str] = Field(default_factory=list)


class DeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(default_factory=list)


class HistoryRecord(BaseModel):
    id: str
    server: str
    library_id: str
    library_name: str
    source_item_ids: list[str] = Field(default_factory=list)
    saved_path: str | None = None
    style: str
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def ensure_created_at_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class JobSummary(BaseModel):
    id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    title: str = ""
    message: str = ""
    library_ids: list[str] = Field(default_factory=list)
    library_names: list[str] = Field(default_factory=list)
    total_libraries: int = 0
    completed_libraries: int = 0
    failed_libraries: int = 0
    cancel_requested: bool = False
    errors: list[str] = Field(default_factory=list)

    @field_validator("created_at", "started_at", "finished_at", mode="after")
    @classmethod
    def ensure_timestamps_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    configured: bool
    emby_reachable: bool
    active_jobs: int

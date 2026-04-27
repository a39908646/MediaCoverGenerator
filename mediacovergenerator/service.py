from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from mediacovergenerator.emby import EmbyClient
from mediacovergenerator.models import AppConfig, HistoryRecord, LibraryInfo
from mediacovergenerator.storage import HistoryRepository
from mediacovergenerator.titles import TitleConfigResolver

if TYPE_CHECKING:
    from mediacovergenerator.fonts import FontResolver
    from mediacovergenerator.generator import PosterGenerator


class LibraryUpdateService:
    def __init__(self, project_root: Path, history_repository: HistoryRepository):
        self.project_root = project_root
        self.history_repository = history_repository
        self._font_resolver: FontResolver | None = None
        self._generator: PosterGenerator | None = None

    def _get_font_resolver(self) -> "FontResolver":
        if self._font_resolver is None:
            from mediacovergenerator.fonts import FontResolver

            self._font_resolver = FontResolver(self.project_root)
        return self._font_resolver

    def _get_generator(self) -> "PosterGenerator":
        if self._generator is None:
            from mediacovergenerator.generator import PosterGenerator

            self._generator = PosterGenerator(self.project_root)
        return self._generator

    def list_libraries(self, config: AppConfig) -> list[LibraryInfo]:
        return EmbyClient(config.emby).list_libraries()

    def generate_for_library(
        self,
        config: AppConfig,
        library_id: str,
        stop_event,
    ) -> HistoryRecord:
        client = EmbyClient(config.emby)
        libraries = client.get_library_map()
        library = libraries.get(str(library_id))
        if not library:
            raise KeyError(f"Library not found: {library_id}")

        generator = self._get_generator()
        library_name = library["Name"]
        title = TitleConfigResolver.from_config(config).resolve(str(library_id), library_name)
        font_paths = self._get_font_resolver().resolve(config)
        source_item_ids = self._prepare_library_images(client, config, library, stop_event)

        encoded_cover = generator.render(
            config=config,
            library_name=library_name,
            title=title,
            font_paths=font_paths,
            stop_event=stop_event,
        )
        image_bytes, content_type, extension = generator.decode_image(encoded_cover)
        saved_path = generator.save_recent_cover(
            config=config,
            library_name=library_name,
            server_name=config.emby.name,
            image_bytes=image_bytes,
            extension=extension,
        )
        client.set_library_image(str(library_id), encoded_cover, content_type)

        record = HistoryRecord(
            id=hashlib.md5(f"{library_id}-{datetime.now(timezone.utc).isoformat()}".encode("utf-8")).hexdigest(),
            server=config.emby.name,
            library_id=str(library_id),
            library_name=library_name,
            source_item_ids=source_item_ids,
            saved_path=str(saved_path) if saved_path else None,
            style=config.cover.style,
            created_at=datetime.now(timezone.utc),
        )
        self.history_repository.append(record)
        return record

    def _prepare_library_images(
        self,
        client: EmbyClient,
        config: AppConfig,
        library: dict,
        stop_event,
    ) -> list[str]:
        generator = self._get_generator()
        library_name = library["Name"]
        cache_dir = generator.library_cache_dir(config, library_name)
        cache_dir.mkdir(parents=True, exist_ok=True)
        for file in cache_dir.glob("*"):
            if file.is_file():
                file.unlink()

        input_dir = generator.library_input_dir(config, library_name)
        if input_dir.exists():
            copied = 0
            for source in sorted(input_dir.iterdir()):
                if not source.is_file() or source.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                    continue
                copied += 1
                shutil.copy(source, cache_dir / source.name)
            if copied:
                generator.prepare_library_images(cache_dir, generator.get_required_items(config))
                return []

        items = self._collect_items(client, config, library, stop_event)
        if not items:
            raise RuntimeError(f"No valid media items found for library {library_name}")

        source_ids: list[str] = []
        for index, item in enumerate(items, start=1):
            if stop_event.is_set():
                raise RuntimeError("Job cancelled")
            image_url = self._get_image_url(client, config, item)
            if not image_url:
                continue
            content = client.download_image(image_url)
            if not content:
                continue
            target = cache_dir / f"{index}.jpg"
            target.write_bytes(content)
            item_id = self._get_item_id(config, item)
            if item_id:
                source_ids.append(str(item_id))
        if not any(cache_dir.iterdir()):
            raise RuntimeError(f"Unable to download images for library {library_name}")
        generator.prepare_library_images(cache_dir, generator.get_required_items(config))
        return source_ids

    def _collect_items(self, client: EmbyClient, config: AppConfig, library: dict, stop_event) -> list[dict]:
        generator = self._get_generator()
        required_items = generator.get_required_items(config)
        collection_type = library.get("CollectionType")
        if collection_type == "boxsets":
            include_types = "BoxSet,Movie"
        elif collection_type == "playlists":
            include_types = "Playlist,Movie,Series,Episode,Audio"
        elif collection_type == "music":
            include_types = "MusicAlbum,Audio"
        else:
            include_types = self._include_types(config)

        valid_items: list[dict] = []
        seen_keys: set[str] = set()
        offset = 0
        for _ in range(20):
            if stop_event.is_set():
                raise RuntimeError("Job cancelled")
            batch = client.list_items(
                parent_id=str(library["Id"]),
                include_types=include_types,
                sort_by=config.cover.sort_by,
                start_index=offset,
                limit=50,
            )
            if not batch:
                break
            for item in batch:
                image_url = self._get_image_url(client, config, item)
                if not image_url:
                    continue
                content_key = self._build_content_key(item)
                image_key = self._build_image_key(image_url)
                if (content_key and content_key in seen_keys) or (image_key and image_key in seen_keys):
                    continue
                if content_key:
                    seen_keys.add(content_key)
                if image_key:
                    seen_keys.add(image_key)
                valid_items.append(item)
                if len(valid_items) >= required_items:
                    return valid_items[:required_items]
            offset += 50
        return valid_items[:required_items]

    def _include_types(self, config: AppConfig) -> str:
        if self._get_generator().is_single_image_style(config):
            return {
                "PremiereDate": "Movie,Series",
                "DateCreated": "Movie,Episode",
                "Random": "Movie,Series",
            }.get(config.cover.sort_by, "Movie,Series")
        if config.cover.sort_by == "DateCreated":
            return "Movie,Episode"
        return "Movie,Series"

    def _get_image_url(self, client: EmbyClient, config: AppConfig, item: dict) -> str | None:
        if item.get("Type") in {"MusicAlbum", "Audio"}:
            if item.get("ParentBackdropImageTags"):
                return client.build_image_url(item.get("ParentBackdropItemId"), "Backdrop", item["ParentBackdropImageTags"][0], 0)
            if item.get("PrimaryImageTag"):
                return client.build_image_url(item.get("PrimaryImageItemId"), "Primary", item.get("PrimaryImageTag"))
            if item.get("AlbumPrimaryImageTag"):
                return client.build_image_url(item.get("AlbumId"), "Primary", item.get("AlbumPrimaryImageTag"))

        prefer_primary = config.cover.use_primary
        single_style = self._get_generator().is_single_image_style(config)
        if item.get("Type") == "Episode":
            if not prefer_primary and item.get("ParentBackdropImageTags"):
                return client.build_image_url(item.get("ParentBackdropItemId"), "Backdrop", item["ParentBackdropImageTags"][0], 0)
            if item.get("SeriesPrimaryImageTag"):
                return client.build_image_url(item.get("SeriesId"), "Primary", item.get("SeriesPrimaryImageTag"))
            if item.get("ParentBackdropImageTags"):
                return client.build_image_url(item.get("ParentBackdropItemId"), "Backdrop", item["ParentBackdropImageTags"][0], 0)

        if prefer_primary:
            if item.get("ImageTags", {}).get("Primary"):
                return client.build_image_url(item.get("Id"), "Primary", item["ImageTags"]["Primary"])
            if item.get("ParentBackdropImageTags"):
                return client.build_image_url(item.get("ParentBackdropItemId"), "Backdrop", item["ParentBackdropImageTags"][0], 0)
            if item.get("BackdropImageTags"):
                return client.build_image_url(item.get("Id"), "Backdrop", item["BackdropImageTags"][0], 0)
        else:
            if item.get("ParentBackdropImageTags"):
                return client.build_image_url(item.get("ParentBackdropItemId"), "Backdrop", item["ParentBackdropImageTags"][0], 0)
            if item.get("BackdropImageTags"):
                return client.build_image_url(item.get("Id"), "Backdrop", item["BackdropImageTags"][0], 0)
            if item.get("ImageTags", {}).get("Primary"):
                return client.build_image_url(item.get("Id"), "Primary", item["ImageTags"]["Primary"])
        if not single_style and item.get("ImageTags", {}).get("Primary"):
            return client.build_image_url(item.get("Id"), "Primary", item["ImageTags"]["Primary"])
        return None

    def _get_item_id(self, config: AppConfig, item: dict) -> str | None:
        if item.get("Type") in {"MusicAlbum", "Audio"}:
            if item.get("ParentBackdropImageTags"):
                return item.get("ParentBackdropItemId")
            if item.get("PrimaryImageTag"):
                return item.get("PrimaryImageItemId")
            if item.get("AlbumPrimaryImageTag"):
                return item.get("AlbumId")

        if item.get("ParentBackdropImageTags") and not config.cover.use_primary:
            return item.get("ParentBackdropItemId")
        if item.get("BackdropImageTags") or item.get("ImageTags", {}).get("Primary"):
            return item.get("Id")
        if item.get("ParentBackdropImageTags"):
            return item.get("ParentBackdropItemId")
        return None

    @staticmethod
    def _build_content_key(item: dict) -> str | None:
        item_type = item.get("Type")
        if item_type == "Episode":
            if item.get("SeriesId"):
                return f"series:{item['SeriesId']}"
            if item.get("ParentBackdropItemId"):
                return f"parent:{item['ParentBackdropItemId']}"
        if item_type in {"MusicAlbum", "Audio"}:
            if item.get("AlbumId"):
                return f"album:{item['AlbumId']}"
            if item.get("ParentBackdropItemId"):
                return f"parent:{item['ParentBackdropItemId']}"
        if item.get("Id"):
            return f"item:{item['Id']}"
        return None

    @staticmethod
    def _build_image_key(image_url: str) -> str:
        parsed = urlparse(image_url)
        normalized_query = "&".join(
            chunk for chunk in parsed.query.split("&") if chunk and not chunk.startswith("api_key=")
        )
        return f"img:{parsed.path}?{normalized_query}"

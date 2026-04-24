from __future__ import annotations

import base64
import random
import re
import shutil
from datetime import datetime
from pathlib import Path

from mediacovergenerator.logging import logger
from mediacovergenerator.models import AppConfig
from mediacovergenerator.storage import resolve_path
from mediacovergenerator.style.style_animated_1 import create_style_animated_1
from mediacovergenerator.style.style_animated_2 import create_style_animated_2
from mediacovergenerator.style.style_animated_3 import create_style_animated_3
from mediacovergenerator.style.style_animated_4 import create_style_animated_4
from mediacovergenerator.style.style_static_1 import create_style_static_1
from mediacovergenerator.style.style_static_2 import create_style_static_2
from mediacovergenerator.style.style_static_3 import create_style_static_3
from mediacovergenerator.style.style_static_4 import create_style_static_4
from mediacovergenerator.titles import ResolvedTitle
from mediacovergenerator.utils.image_manager import ResolutionConfig
from mediacovergenerator.utils.network_helper import validate_font_file


class PosterGenerator:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._sanitize_log_cache: set[str] = set()

    def sanitize_filename(self, value: str) -> str:
        if not value:
            return "unknown"
        safe = re.sub(r'[<>:"/\\|?*]', "_", value).strip()
        if not safe:
            return "unknown"
        if safe.startswith("."):
            safe = f"_{safe[1:]}"
        if len(safe) > 100:
            safe = safe[:100]
        if safe != value and value not in self._sanitize_log_cache:
            self._sanitize_log_cache.add(value)
            logger.debug("Sanitized file name '%s' -> '%s'", value, safe)
        return safe

    def get_required_items(self, config: AppConfig) -> int:
        style = config.cover.style
        if style in {"static_3", "animated_3"}:
            return 9
        if style in {"animated_1", "animated_2", "animated_4"}:
            return max(3, min(9, int(config.cover.animated_2_image_count)))
        return 1

    def is_single_image_style(self, config: AppConfig) -> bool:
        return config.cover.style in {"static_1", "static_2", "static_4"}

    def library_cache_dir(self, config: AppConfig, library_name: str) -> Path:
        return resolve_path(self.project_root, config.paths.cache_dir) / self.sanitize_filename(library_name)

    def library_input_dir(self, config: AppConfig, library_name: str) -> Path:
        return resolve_path(self.project_root, config.paths.covers_input_dir) / self.sanitize_filename(library_name)

    def prepare_library_images(self, library_dir: Path, required_items: int) -> bool:
        library_dir.mkdir(parents=True, exist_ok=True)
        required_items = max(1, int(required_items))
        existing_numbers: list[int] = []
        missing_numbers: list[int] = []
        for i in range(1, required_items + 1):
            target = library_dir / f"{i}.jpg"
            if target.exists():
                existing_numbers.append(i)
            else:
                missing_numbers.append(i)
        if not missing_numbers:
            return True

        source_files: list[Path] = []
        scanned = 0
        target_pattern = re.compile(r"^[1-9][0-9]*\.jpg$", re.IGNORECASE)
        for entry in library_dir.iterdir():
            scanned += 1
            if not entry.is_file():
                continue
            if target_pattern.match(entry.name):
                continue
            if entry.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                source_files.append(entry)
                if len(source_files) >= 512:
                    break
        if scanned > 2000:
            logger.info("Large library dir scanned quickly: %s -> %s samples", library_dir, len(source_files))

        if not source_files:
            if existing_numbers:
                source_files = [library_dir / f"{i}.jpg" for i in existing_numbers]
            else:
                return False

        last_source: Path | None = None
        for missing_number in missing_numbers:
            target = library_dir / f"{missing_number}.jpg"
            if len(source_files) == 1:
                selected = source_files[0]
            else:
                candidates = [item for item in source_files if item != last_source] or source_files
                selected = random.choice(candidates)
            shutil.copy(selected, target)
            last_source = selected
        return True

    def render(
        self,
        config: AppConfig,
        library_name: str,
        title: ResolvedTitle,
        font_paths: tuple[Path, Path],
        stop_event,
    ) -> str:
        if not validate_font_file(font_paths[0]) or not validate_font_file(font_paths[1]):
            raise RuntimeError("Font validation failed")

        resolution_config = self._resolution_config(config)
        font_size = self._font_sizes(config, resolution_config)
        font_offset = (
            float(config.cover.zh_font_offset or 0),
            float(config.cover.title_spacing or 40) * max(float(config.cover.title_scale), 0.1),
            float(config.cover.en_line_spacing or 40) * max(float(config.cover.title_scale), 0.1),
        )
        bg_color_config = {
            "mode": config.cover.bg_color_mode,
            "custom_color": config.cover.custom_bg_color,
            "config_color": title.bg_color,
        }
        font_path = (str(font_paths[0]), str(font_paths[1]))
        title_tuple = (title.zh_title, title.en_title)
        image_dir = self.library_cache_dir(config, library_name)
        required_items = self.get_required_items(config)

        if not self.is_single_image_style(config):
            if not self.prepare_library_images(image_dir, required_items):
                raise RuntimeError(f"Unable to prepare library images in {image_dir}")

        style = config.cover.style
        image_path = image_dir / "1.jpg"
        if style == "static_1":
            return create_style_static_1(
                str(image_path),
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
            )
        if style == "static_2":
            return create_style_static_2(
                str(image_path),
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
            )
        if style == "static_4":
            return create_style_static_4(
                str(image_path),
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
            )
        if style == "static_3":
            return create_style_static_3(
                image_dir,
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                is_blur=config.cover.multi_1_blur,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
            )
        if style == "animated_1":
            return create_style_animated_1(
                image_dir,
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                is_blur=config.cover.multi_1_blur,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
                animation_duration=config.cover.animation_duration,
                animation_fps=config.cover.animation_fps,
                animation_format=config.cover.animation_format,
                animation_resolution=config.cover.animation_resolution,
                animation_reduce_colors=config.cover.animation_reduce_colors,
                image_count=self.get_required_items(config),
                departure_type=config.cover.animated_2_departure_type,
                stop_event=stop_event,
            )
        if style == "animated_2":
            return create_style_animated_2(
                image_dir,
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                is_blur=config.cover.multi_1_blur,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
                animation_duration=config.cover.animation_duration,
                animation_fps=config.cover.animation_fps,
                animation_format=config.cover.animation_format,
                animation_resolution=config.cover.animation_resolution,
                animation_reduce_colors=config.cover.animation_reduce_colors,
                image_count=self.get_required_items(config),
                stop_event=stop_event,
            )
        if style == "animated_3":
            return create_style_animated_3(
                image_dir,
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                is_blur=config.cover.multi_1_blur,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
                animation_duration=config.cover.animation_duration,
                animation_scroll=config.cover.animation_scroll,
                animation_fps=config.cover.animation_fps,
                animation_format=config.cover.animation_format,
                animation_resolution=config.cover.animation_resolution,
                animation_reduce_colors=config.cover.animation_reduce_colors,
                stop_event=stop_event,
            )
        if style == "animated_4":
            return create_style_animated_4(
                image_dir,
                title_tuple,
                font_path,
                font_size=font_size,
                font_offset=font_offset,
                is_blur=config.cover.multi_1_blur,
                blur_size=config.cover.blur_size,
                color_ratio=config.cover.color_ratio,
                resolution_config=resolution_config,
                bg_color_config=bg_color_config,
                animation_duration=config.cover.animation_duration,
                animation_fps=config.cover.animation_fps,
                animation_format=config.cover.animation_format,
                animation_resolution=config.cover.animation_resolution,
                animation_reduce_colors=config.cover.animation_reduce_colors,
                image_count=self.get_required_items(config),
                stop_event=stop_event,
            )
        raise ValueError(f"Unsupported style: {style}")

    def decode_image(self, encoded: str) -> tuple[bytes, str, str]:
        content_type = "image/png"
        extension = "png"
        if encoded.startswith("R0lG"):
            content_type = "image/gif"
            extension = "gif"
        elif encoded.startswith("UklG"):
            content_type = "image/webp"
            extension = "webp"
        elif encoded.startswith("/9j/"):
            content_type = "image/jpeg"
            extension = "jpg"
        image_bytes = base64.b64decode(encoded)
        return image_bytes, content_type, extension

    def save_recent_cover(
        self,
        config: AppConfig,
        library_name: str,
        server_name: str,
        image_bytes: bytes,
        extension: str,
    ) -> Path | None:
        if not config.cover.save_recent_covers:
            return None
        recent_dir = resolve_path(self.project_root, config.paths.recent_covers_dir)
        recent_dir.mkdir(parents=True, exist_ok=True)
        safe_library = self.sanitize_filename(library_name)
        safe_server = self.sanitize_filename(server_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = recent_dir / f"{safe_server}_{safe_library}_{timestamp}.{extension}"
        target.write_bytes(image_bytes)

        pattern = f"{safe_server}_{safe_library}_"
        files = [
            path
            for path in recent_dir.iterdir()
            if path.is_file() and path.name.startswith(pattern) and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".apng"}
        ]
        files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for old_file in files[config.cover.covers_history_limit_per_library :]:
            old_file.unlink(missing_ok=True)
        return target

    def _resolution_config(self, config: AppConfig) -> ResolutionConfig:
        if config.cover.resolution == "custom":
            return ResolutionConfig((config.cover.custom_width, config.cover.custom_height))
        return ResolutionConfig(config.cover.resolution)

    def _font_sizes(self, config: AppConfig, resolution_config: ResolutionConfig) -> tuple[float, float]:
        title_scale = max(float(config.cover.title_scale or 1.0), 0.1)
        if config.cover.style.startswith("animated"):
            return (
                float(config.cover.zh_font_size) * title_scale,
                float(config.cover.en_font_size) * title_scale,
            )
        return (
            resolution_config.get_font_size(float(config.cover.zh_font_size)) * title_scale,
            resolution_config.get_font_size(float(config.cover.en_font_size)) * title_scale,
        )


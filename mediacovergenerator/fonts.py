from __future__ import annotations

import hashlib
import re
from pathlib import Path

from mediacovergenerator.logging import logger
from mediacovergenerator.models import AppConfig
from mediacovergenerator.storage import resolve_path
from mediacovergenerator.utils.network_helper import NetworkHelper, validate_font_file


class FontResolver:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.repo_fonts_dir = project_root / "mediacovergenerator" / "assets" / "fonts"

    def resolve(self, config: AppConfig) -> tuple[Path, Path]:
        fonts_dir = resolve_path(self.project_root, config.paths.fonts_dir)
        fonts_dir.mkdir(parents=True, exist_ok=True)

        zh_path = self._resolve_one(
            fonts_dir=fonts_dir,
            preset=config.cover.zh_font_preset,
            custom=config.cover.zh_font_custom,
            fallback_name="chaohei.ttf",
        )
        en_path = self._resolve_one(
            fonts_dir=fonts_dir,
            preset=config.cover.en_font_preset,
            custom=config.cover.en_font_custom,
            fallback_name="EmblemaOne.woff2",
        )
        return zh_path, en_path

    def _resolve_one(self, fonts_dir: Path, preset: str, custom: str, fallback_name: str) -> Path:
        if custom:
            detected = self._detect_string_type(custom)
            if detected == "path":
                path = Path(custom).expanduser()
                if validate_font_file(path):
                    return path
                raise FileNotFoundError(f"Invalid font path: {path}")
            if detected == "url":
                return self._download_font(custom, fonts_dir)

        preset_path = self.repo_fonts_dir / self._preset_file_name(preset, fallback_name)
        if validate_font_file(preset_path):
            return preset_path

        fallback_path = self.repo_fonts_dir / fallback_name
        if validate_font_file(fallback_path):
            return fallback_path
        raise FileNotFoundError(f"Unable to resolve default font {fallback_name}")

    @staticmethod
    def _detect_string_type(value: str) -> str | None:
        if re.match(r"^https?://[^\s]+$", value, re.IGNORECASE):
            return "url"
        if Path(value).expanduser().is_absolute() or value.startswith((".", "~")) or re.search(r"[\\/]", value):
            return "path"
        return None

    @staticmethod
    def _preset_file_name(preset: str, fallback_name: str) -> str:
        mapping = {
            "chaohei": "chaohei.ttf",
            "yasong": "yasong.ttf",
            "EmblemaOne": "EmblemaOne.woff2",
            "Melete": "Melete.otf",
            "Phosphate": "phosphate.ttf",
            "JosefinSans": "josefinsans.woff2",
            "LilitaOne": "lilitaone.woff2",
        }
        return mapping.get(preset, fallback_name)

    def _download_font(self, url: str, fonts_dir: Path) -> Path:
        extension = Path(url.split("?")[0]).suffix or ".ttf"
        filename = f"downloaded_{hashlib.md5(url.encode('utf-8')).hexdigest()}{extension}"
        target_path = fonts_dir / filename
        if validate_font_file(target_path):
            return target_path

        helper = NetworkHelper(timeout=60, max_retries=2)
        if not helper.download_file_sync(url, target_path):
            raise RuntimeError(f"Failed to download font from {url}")
        if not validate_font_file(target_path):
            raise RuntimeError(f"Downloaded font is invalid: {url}")
        logger.info("Downloaded font: %s", target_path)
        return target_path

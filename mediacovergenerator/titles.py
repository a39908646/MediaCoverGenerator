from __future__ import annotations

from dataclasses import dataclass

import yaml

from mediacovergenerator.logging import logger
from mediacovergenerator.models import AppConfig, LibraryTitleConfig


@dataclass(slots=True)
class ResolvedTitle:
    zh_title: str
    en_title: str
    bg_color: str | None = None


def load_title_config(yaml_str: str) -> dict[str, list[str]]:
    if not yaml_str:
        return {}
    try:
        yaml_str = yaml_str.replace("：", ":").replace("\t", "  ")
        processed_lines: list[str] = []
        for line in yaml_str.splitlines():
            if ":" in line and not line.strip().startswith("#"):
                key_part, value_part = line.split(":", 1)
                key = key_part.strip()
                if key and not (key.startswith('"') or key.startswith("'")):
                    if key[0].isdigit() or any(char in key for char in [" ", "-", ".", "(", ")", "[", "]"]):
                        key = f'"{key}"'
                processed_lines.append(f"{key}:{value_part}")
            else:
                processed_lines.append(line)
        data = yaml.safe_load("\n".join(processed_lines)) or {}
        if not isinstance(data, dict):
            return {}

        filtered: dict[str, list[str]] = {}
        for key, value in data.items():
            if isinstance(value, list) and len(value) >= 2 and all(isinstance(entry, str) for entry in value[:2]):
                filtered[str(key)] = [value[0], value[1]] + ([value[2]] if len(value) > 2 and isinstance(value[2], str) else [])
            else:
                logger.warning("Ignored malformed title config entry: %s -> %s", key, value)
        return filtered
    except Exception as exc:
        logger.warning("Failed to parse title config, falling back to defaults: %s", exc)
        return {}


def dump_title_config(entries: list[LibraryTitleConfig]) -> str:
    lines = ["# 自动生成，请优先通过媒体库列表维护主副标题"]
    for entry in entries:
        name = (entry.library_name or "").strip()
        zh_title = (entry.zh_title or "").strip()
        en_title = (entry.en_title or "").strip()
        bg_color = (entry.bg_color or "").strip()
        if not name or not zh_title:
            continue
        values = [zh_title, en_title]
        if bg_color:
            values.append(bg_color)
        dumped = ", ".join(f'"{value}"' for value in values)
        lines.append(f'"{name}": [{dumped}]')
    return "\n".join(lines) + "\n"


class TitleConfigResolver:
    def __init__(self, library_titles: list[LibraryTitleConfig] | None = None, yaml_text: str = ""):
        self._library_titles = library_titles or []
        self._mapping = load_title_config(yaml_text)

    @classmethod
    def from_config(cls, config: AppConfig) -> "TitleConfigResolver":
        return cls(config.library_titles, config.titles_yaml)

    @staticmethod
    def _match_name(left: str, right: str) -> bool:
        return (
            str(left) == str(right)
            or str(left).strip() == str(right).strip()
            or str(left).lower() == str(right).lower()
        )

    def resolve(self, library_id: str, library_name: str) -> ResolvedTitle:
        for entry in self._library_titles:
            if entry.library_id and str(entry.library_id) == str(library_id):
                return ResolvedTitle(
                    zh_title=(entry.zh_title or library_name).strip() or library_name,
                    en_title=(entry.en_title or "").strip(),
                    bg_color=(entry.bg_color or "").strip() or None,
                )
        for entry in self._library_titles:
            if entry.library_name and self._match_name(entry.library_name, library_name):
                return ResolvedTitle(
                    zh_title=(entry.zh_title or library_name).strip() or library_name,
                    en_title=(entry.en_title or "").strip(),
                    bg_color=(entry.bg_color or "").strip() or None,
                )

        zh_title = library_name
        en_title = ""
        bg_color = None
        for config_name, values in self._mapping.items():
            if self._match_name(config_name, library_name):
                zh_title = values[0]
                en_title = values[1] if len(values) > 1 else ""
                bg_color = values[2] if len(values) > 2 else None
                break
        return ResolvedTitle(zh_title=zh_title, en_title=en_title, bg_color=bg_color)

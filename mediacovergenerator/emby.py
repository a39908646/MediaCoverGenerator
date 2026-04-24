from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import requests

from mediacovergenerator.logging import logger
from mediacovergenerator.models import EmbySettings, LibraryInfo


class EmbyClient:
    def __init__(self, settings: EmbySettings):
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = settings.verify_ssl
        self.timeout = settings.timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.base_url and self.settings.api_key)

    def ping(self) -> bool:
        if not self.is_configured():
            return False
        try:
            response = self._request("GET", "/emby/System/Info/Public")
            return response.ok
        except Exception:
            return False

    def list_libraries(self) -> list[LibraryInfo]:
        response = self._request("GET", "/emby/Library/VirtualFolders/Query")
        data = response.json()
        return [
            LibraryInfo(
                id=str(item.get("Id", "")),
                name=item.get("Name", ""),
                collection_type=item.get("CollectionType", "") or "",
            )
            for item in data.get("Items", [])
            if item.get("Name") and item.get("Id")
        ]

    def get_library_map(self) -> dict[str, dict[str, Any]]:
        response = self._request("GET", "/emby/Library/VirtualFolders/Query")
        data = response.json()
        return {str(item.get("Id")): item for item in data.get("Items", []) if item.get("Id")}

    def list_items(
        self,
        parent_id: str,
        include_types: str,
        sort_by: str,
        start_index: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/emby/Items",
            params={
                "ParentId": parent_id,
                "SortBy": sort_by,
                "Limit": limit,
                "StartIndex": start_index,
                "IncludeItemTypes": include_types,
                "Recursive": "true",
                "SortOrder": "Descending",
            },
        )
        return response.json().get("Items", [])

    def get_item(self, item_id: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            "/emby/Items",
            params={
                "Ids": item_id,
                "Fields": "Path,ParentId",
                "Limit": 1,
            },
        )
        items = response.json().get("Items", [])
        if not items:
            raise KeyError(f"Item not found: {item_id}")
        return items[0]

    def build_image_url(self, item_id: str, image_type: str, tag: str | None = None, index: int | None = None) -> str:
        path = f"/emby/Items/{item_id}/Images/{image_type}"
        if index is not None:
            path = f"{path}/{index}"
        params = {}
        if tag:
            params["tag"] = tag
        params["api_key"] = self.settings.api_key
        return f"{self.base_url}{path}?{urlencode(params)}"

    def download_image(self, url: str) -> bytes | None:
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.ok:
                return response.content
        except requests.RequestException as exc:
            logger.warning("Failed to download image %s: %s", url, exc)
        return None

    def set_library_image(self, library_id: str, image_payload: str, content_type: str) -> None:
        self._request(
            "POST",
            f"/emby/Items/{library_id}/Images/Primary",
            params={},
            data=image_payload.encode("utf-8"),
            headers={"Content-Type": content_type},
        )

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        if not self.is_configured():
            raise RuntimeError("Emby is not configured")
        query = {"api_key": self.settings.api_key}
        if params:
            query.update(params)
        response = self.session.request(
            method=method,
            url=f"{self.base_url}{path}",
            params=query,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body_preview = response.text[:500] if response.text else ""
            logger.error(
                "Emby request failed: %s %s -> %s, response=%s",
                method,
                response.url,
                response.status_code,
                body_preview,
            )
            raise exc
        return response

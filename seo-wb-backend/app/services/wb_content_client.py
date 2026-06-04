from typing import Any

from app.core.errors import AppError
from app.core.config import Settings
from app.core.ttl_cache import TTLCache
from app.services.wb_base_client import WbBaseClient


_catalog_cache: TTLCache[Any] | None = None


class WbContentClient(WbBaseClient):
    def __init__(self, settings: Settings, api_key: str, **kwargs: Any) -> None:
        global _catalog_cache
        super().__init__(settings, api_key, base_url=settings.wb_content_base_url, category="content", **kwargs)
        if _catalog_cache is None:
            _catalog_cache = TTLCache(settings.wb_catalog_cache_ttl_seconds)

    async def ping(self) -> Any:
        return await self.request("GET", "/ping", rate_scope="ping")

    async def get_subjects(self, parent_id: int | None = None, locale: str = "ru") -> list[dict[str, Any]]:
        cache_key = f"subjects:{locale}:{parent_id}:all"
        if _catalog_cache:
            cached = _catalog_cache.get(cache_key)
            if cached is not None:
                return cached
        all_items: list[dict[str, Any]] = []
        limit = 1000
        offset = 0
        while True:
            params: dict[str, Any] = {"locale": locale, "limit": limit, "offset": offset}
            if parent_id is not None:
                params["parentID"] = parent_id
            payload = await self.request("GET", "/content/v2/object/all", params=params)
            batch = payload.get("data") or []
            all_items.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        if _catalog_cache:
            _catalog_cache.set(cache_key, all_items)
        return all_items

    async def get_parent_categories(self, locale: str = "ru") -> list[dict[str, Any]]:
        cache_key = f"parent-categories:{locale}"
        if _catalog_cache:
            cached = _catalog_cache.get(cache_key)
            if cached is not None:
                return cached
        payload = await self.request("GET", "/content/v2/object/parent/all", params={"locale": locale})
        data = payload.get("data") or []
        if _catalog_cache:
            _catalog_cache.set(cache_key, data)
        return data

    async def get_subject_charcs(self, subject_id: int, locale: str = "ru") -> list[dict[str, Any]]:
        payload = await self.request("GET", f"/content/v2/object/charcs/{subject_id}", params={"locale": locale})
        return payload.get("data") or []

    async def get_colors(self, locale: str = "ru") -> list[dict[str, Any]]:
        payload = await self.request("GET", "/content/v2/directory/colors", params={"locale": locale})
        return payload.get("data") or []

    async def get_kinds(self, locale: str = "ru") -> list[str]:
        payload = await self.request("GET", "/content/v2/directory/kinds", params={"locale": locale})
        return payload.get("data") or []

    async def get_countries(self, locale: str = "ru") -> list[dict[str, Any]]:
        payload = await self.request("GET", "/content/v2/directory/countries", params={"locale": locale})
        return payload.get("data") or []

    async def get_seasons(self, locale: str = "ru") -> list[str]:
        payload = await self.request("GET", "/content/v2/directory/seasons", params={"locale": locale})
        return payload.get("data") or []

    async def get_vat_rates(self, locale: str = "ru") -> list[dict[str, Any]]:
        payload = await self.request("GET", "/content/v2/directory/vat", params={"locale": locale})
        return payload.get("data") or []

    async def get_tnved(self, subject_id: int, search: str | int | None = None, locale: str = "ru") -> list[dict[str, Any]]:
        params: dict[str, Any] = {"subjectID": subject_id, "locale": locale}
        if search:
            params["search"] = search
        payload = await self.request("GET", "/content/v2/directory/tnved", params=params)
        return payload.get("data") or []

    async def get_brands(self, subject_id: int, next_value: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"subjectId": subject_id}
        if next_value is not None:
            params["next"] = next_value
        return await self.request("GET", "/api/content/v1/brands", params=params)

    async def get_card_limits(self) -> dict[str, Any]:
        return await self.request("GET", "/content/v2/cards/limits")

    async def generate_barcodes(self, count: int = 1) -> dict[str, Any]:
        return await self.request("POST", "/content/v2/barcodes", json_body={"count": count})

    async def upload_cards(self, groups: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.request("POST", "/content/v2/cards/upload", json_body=groups)

    async def upload_cards_add(self, imt_id: int, cards_to_add: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.request("POST", "/content/v2/cards/upload/add", json_body={"imtID": imt_id, "cardsToAdd": cards_to_add})

    async def move_nm_cards(self, nm_ids: list[int], target_imt: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"nmIDs": nm_ids}
        if target_imt is not None:
            payload["targetIMT"] = target_imt
        return await self.request("POST", "/content/v2/cards/moveNm", json_body=payload)

    async def get_card_errors(self) -> dict[str, Any]:
        return await self.request("POST", "/content/v2/cards/error/list", json_body={})

    async def get_cards_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/content/v2/get/cards/list", json_body=payload)

    async def upload_media_links(self, nm_id: int, links: list[str]) -> dict[str, Any]:
        return await self.request("POST", "/content/v3/media/save", json_body={"nmId": nm_id, "data": links})

    async def upload_media_file(self, nm_id: int, photo_number: int, file_name: str, content: bytes) -> dict[str, Any]:
        client = await self._client()
        response = await client.post(
            "/content/v3/media/file",
            headers={"Authorization": self._api_key, "X-Nm-Id": str(nm_id), "X-Photo-Number": str(photo_number)},
            timeout=self._settings.wb_media_timeout_seconds,
            files={"uploadfile": (file_name, content)},
        )
        payload = self._parse_payload(response)
        self._log_diagnostic(
            "POST",
            "/content/v3/media/file",
            response.status_code,
            {"fileName": file_name, "nmId": nm_id, "photoNumber": photo_number},
            self._sanitize_response_meta(response, payload),
            None,
        )
        if response.status_code >= 400:
            raise AppError(
                "wildberries_media_upload_failed",
                f"Wildberries media API returned {response.status_code}.",
                502,
                {"status_code": response.status_code, "payload": payload},
            )
        return payload

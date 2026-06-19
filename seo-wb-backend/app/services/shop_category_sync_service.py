import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import decrypt_secret
from app.models.shop_category import StoreCategory, StoreCategorySyncState
from app.models.store import Store
from app.services.wb_client import WildberriesClient


# TN VED codes on Wildberries are 10-digit numeric strings.
_TNVED_PATTERN = re.compile(r"\b\d{10}\b")
# Characteristic names that carry the TN VED code on a WB card.
_TNVED_NAMES = {"тнвэд", "тн вэд", "код тнвэд", "код тн вэд"}
# Known WB charcID values for the TN VED field (defensive, name match is primary).
_TNVED_CHARC_IDS = {14177449}

_PAGE_LIMIT = 100
# Safety cap so a runaway pagination never loops forever (100 * 500 = 50k cards).
_MAX_PAGES = 500


def _norm_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _iter_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _extract_tnved(card: dict[str, Any]) -> str | None:
    """Best-effort extraction of the 10-digit TN VED code from a WB card."""
    if not isinstance(card, dict):
        return None

    # 1. Direct card-level field (new card flow stores tnved on the variant).
    for direct in _iter_values(card.get("tnved")):
        match = _TNVED_PATTERN.search(direct)
        if match:
            return match.group(0)

    # 2. Characteristic matched by name or known charc id.
    fallback: str | None = None
    for charc in card.get("characteristics") or []:
        if not isinstance(charc, dict):
            continue
        name = _norm_name(charc.get("name"))
        charc_id = charc.get("id") or charc.get("charcID")
        values = _iter_values(charc.get("value"))
        named = name in _TNVED_NAMES or (charc_id in _TNVED_CHARC_IDS if charc_id is not None else False)
        for raw in values:
            match = _TNVED_PATTERN.search(raw)
            if not match:
                continue
            if named:
                return match.group(0)
            if fallback is None:
                fallback = match.group(0)
    return fallback


class ShopCategorySyncService:
    """Pulls the shop's categories (WB subject + default TN VED) directly from
    Wildberries and stores only the aggregated catalog. It streams the card list
    page by page and keeps just the subject/TN VED tallies, so it never persists
    the full product set."""

    def __init__(self, settings: Settings, db: Session, store: Store) -> None:
        self._db = db
        self._store = store
        self._wb = WildberriesClient(settings, decrypt_secret(settings, store.wb_api_key_encrypted))

    @staticmethod
    def _extract_cards(response: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(response.get("cards"), list):
            return response["cards"]
        data = response.get("data")
        if isinstance(data, dict) and isinstance(data.get("cards"), list):
            return data["cards"]
        return []

    @staticmethod
    def _extract_cursor(response: dict[str, Any]) -> dict[str, Any]:
        if isinstance(response.get("cursor"), dict):
            return response["cursor"]
        data = response.get("data")
        if isinstance(data, dict) and isinstance(data.get("cursor"), dict):
            return data["cursor"]
        return {}

    async def sync(self, state: StoreCategorySyncState | None = None) -> dict[str, Any]:
        names: dict[int, str] = {}
        counts: dict[int, int] = defaultdict(int)
        tnved_counters: dict[int, Counter] = defaultdict(Counter)

        cursor_updated_at: str | None = None
        cursor_nm_id: int | None = None
        cards_scanned = 0

        for _ in range(_MAX_PAGES):
            cursor: dict[str, Any] = {"limit": _PAGE_LIMIT}
            if cursor_updated_at:
                cursor["updatedAt"] = cursor_updated_at
            if cursor_nm_id:
                cursor["nmID"] = cursor_nm_id
            payload = {
                "settings": {
                    "sort": {"ascending": True},
                    "cursor": cursor,
                    "filter": {"withPhoto": -1},
                }
            }

            response = await self._wb.get_cards_list(payload)
            cards = self._extract_cards(response)
            if not cards:
                break

            for card in cards:
                cards_scanned += 1
                subject_id = card.get("subjectID") or card.get("subjectId")
                if not subject_id:
                    continue
                subject_id = int(subject_id)
                counts[subject_id] += 1
                subject_name = card.get("subjectName")
                if subject_name and subject_id not in names:
                    names[subject_id] = str(subject_name)
                tnved = _extract_tnved(card)
                if tnved:
                    tnved_counters[subject_id][tnved] += 1

            next_cursor = self._extract_cursor(response)
            last_card = cards[-1]
            cursor_updated_at = next_cursor.get("updatedAt") or last_card.get("updatedAt")
            cursor_nm_id = (
                int(next_cursor.get("nmID") or next_cursor.get("nmId") or last_card.get("nmID") or last_card.get("nmId") or 0)
                or None
            )
            if state is not None:
                # Persist progress so the UI can poll while the job runs.
                state.total_scanned = cards_scanned
                state.categories_found = len(counts)
                self._db.commit()

            total = int(next_cursor.get("total") or len(cards))
            if total < _PAGE_LIMIT:
                break

        self._upsert_catalog(names, counts, tnved_counters)

        rows = (
            self._db.query(StoreCategory)
            .filter_by(store_id=self._store.id)
            .order_by(StoreCategory.product_count.desc(), StoreCategory.subject_name.asc())
            .all()
        )
        return {
            "synced_categories": len(counts),
            "products_scanned": cards_scanned,
            "categories": rows,
        }

    def _upsert_catalog(
        self,
        names: dict[int, str],
        counts: dict[int, int],
        tnved_counters: dict[int, Counter],
    ) -> None:
        now = datetime.now(timezone.utc)
        existing = {
            row.subject_id: row
            for row in self._db.query(StoreCategory).filter_by(store_id=self._store.id).all()
        }

        for subject_id, count in counts.items():
            options = [
                {"code": code, "count": n}
                for code, n in tnved_counters[subject_id].most_common()
            ]
            best_tnved = options[0]["code"] if options else None
            row = existing.get(subject_id)
            if row is None:
                row = StoreCategory(store_id=self._store.id, subject_id=subject_id, source="auto")
                self._db.add(row)
            if names.get(subject_id):
                row.subject_name = names[subject_id]
            row.product_count = count
            row.tnved_options = options
            # Respect a manually locked TN VED; otherwise adopt the most-used one.
            if not row.locked and best_tnved:
                row.tnved = best_tnved
            row.last_synced_at = now

        self._db.commit()

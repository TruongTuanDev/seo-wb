from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.seller import Seller
from app.models.wb_product import WbProduct, WbProductSyncState
from app.services.wb_content_client import WbContentClient


STALE_SYNC_MINUTES = 15


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


class WbProductSyncService:
    def __init__(self, db: Session, seller: Seller, client: WbContentClient) -> None:
        self._db = db
        self._seller = seller
        self._client = client

    async def sync(self, *, full: bool = False, max_batches: int | None = None) -> dict[str, Any]:
        state = self._db.query(WbProductSyncState).filter_by(seller_id=self._seller.id, sync_type="active_cards").one_or_none()
        if state is None:
            state = WbProductSyncState(seller_id=self._seller.id, sync_type="active_cards")
            self._db.add(state)
            self._db.commit()
            self._db.refresh(state)
        elif state.status == "running" and self.is_stale_state(state):
            state.status = "interrupted"
            state.last_error = "stale running product sync recovered"
            state.finished_at = datetime.now(UTC)
            self._db.commit()

        cursor_updated_at = None if full else state.cursor_updated_at
        cursor_nm_id = None if full else state.cursor_nm_id
        state.status = "running"
        state.last_error = None
        state.started_at = datetime.now(UTC)
        state.finished_at = None
        total_synced = 0
        batches = 0
        self._db.commit()

        try:
            while True:
                limit = 100
                payload = {
                    "settings": {
                        "sort": {"ascending": True},
                        "cursor": {"limit": limit},
                        "filter": {"withPhoto": -1},
                    }
                }
                if cursor_updated_at:
                    payload["settings"]["cursor"]["updatedAt"] = cursor_updated_at.isoformat()
                if cursor_nm_id:
                    payload["settings"]["cursor"]["nmID"] = cursor_nm_id

                response = await self._client.get_cards_list(payload)
                cards = self._extract_cards(response)
                cursor = self._extract_cursor(response)
                if not cards:
                    break
                for card in cards:
                    self._upsert_product(card)
                    total_synced += 1
                batches += 1
                last_card = cards[-1]
                cursor_updated_at = _parse_dt(cursor.get("updatedAt") or last_card.get("updatedAt"))
                cursor_nm_id = int(cursor.get("nmID") or cursor.get("nmId") or last_card.get("nmID") or last_card.get("nmId") or 0) or None
                if max_batches is not None and batches >= max_batches:
                    break
                total = int(cursor.get("total") or len(cards))
                if total < limit:
                    break

            state.cursor_updated_at = cursor_updated_at
            state.cursor_nm_id = cursor_nm_id
            state.total_synced = total_synced
            state.status = "completed"
            state.finished_at = datetime.now(UTC)
            self._db.commit()
            return {
                "status": state.status,
                "totalSynced": total_synced,
                "cursorUpdatedAt": cursor_updated_at.isoformat() if cursor_updated_at else None,
                "cursorNmId": cursor_nm_id,
                "batches": batches,
            }
        except Exception as exc:
            state.status = "failed"
            state.last_error = str(exc)[:1000]
            state.finished_at = datetime.now(UTC)
            self._db.commit()
            raise

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

    def _upsert_product(self, card: dict[str, Any]) -> WbProduct:
        nm_id = int(card.get("nmID") or card.get("nmId"))
        product = self._db.query(WbProduct).filter_by(seller_id=self._seller.id, nm_id=nm_id).one_or_none()
        if product is None:
            product = WbProduct(seller_id=self._seller.id, nm_id=nm_id, raw_data={})
            self._db.add(product)

        photos = card.get("photos") or []
        first_photo = photos[0] if photos else {}
        dimensions = card.get("dimensions") or {}
        sizes = card.get("sizes") or []
        skus: list[str] = []
        for size in sizes:
            for sku in size.get("skus") or []:
                skus.append(str(sku))

        product.imt_id = card.get("imtID") or card.get("imtId")
        product.nm_uuid = card.get("nmUUID") or card.get("nmUuid")
        product.subject_id = card.get("subjectID") or card.get("subjectId")
        product.subject_name = card.get("subjectName")
        product.vendor_code = card.get("vendorCode")
        product.brand = card.get("brand")
        product.title = card.get("title")
        product.description = card.get("description")
        product.need_kiz = card.get("needKiz")
        product.kiz_marked = card.get("kizMarked")
        product.photo_big_url = first_photo.get("big") or first_photo.get("tm")
        product.photo_square_url = first_photo.get("square")
        product.length = _parse_decimal(dimensions.get("length"))
        product.width = _parse_decimal(dimensions.get("width"))
        product.height = _parse_decimal(dimensions.get("height"))
        product.weight_brutto = _parse_decimal(dimensions.get("weightBrutto"))
        product.dimensions_valid = bool(dimensions) if dimensions is not None else None
        product.characteristics = card.get("characteristics") or []
        product.sizes = sizes
        product.skus = list(dict.fromkeys(skus))
        product.raw_data = card
        product.wb_updated_at = _parse_dt(card.get("updatedAt"))
        self._db.commit()
        self._db.refresh(product)
        return product

    @staticmethod
    def is_stale_state(state: WbProductSyncState) -> bool:
        if state.status != "running" or not state.updated_at:
            return False
        return (datetime.now(UTC) - state.updated_at.astimezone(UTC)).total_seconds() > STALE_SYNC_MINUTES * 60

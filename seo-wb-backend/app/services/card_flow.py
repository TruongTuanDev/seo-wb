from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.concurrency import run_ai_limited
from app.core.errors import AppError
from app.core.security import decrypt_secret
from app.models.card import CardDraft
from app.models.store import Store
from app.models.user import User
from app.schemas.card import CardUploadGroup, ImageAnalysis, ProductInput
from app.services.card_generator import CardGenerator
from app.services.card_payload_enricher import CardPayloadEnricher
from app.services.garment_analyzer import GarmentAnalyzer
from app.services.gemini_analyzer import GeminiAnalyzer
from app.services.subject_resolver import SubjectResolver
from app.services.wb_client import WildberriesClient
from starlette.concurrency import run_in_threadpool


class CardFlowService:
    def __init__(self, settings: Settings, db: Session, user: User, store: Store):
        self._settings = settings
        self._db = db
        self._user = user
        self._store = store
        self._wb_api_key = decrypt_secret(settings, store.wb_api_key_encrypted)
        self._wb = WildberriesClient(settings, self._wb_api_key)

    async def generate_draft(self, image_bytes: list[bytes], user_input: ProductInput) -> CardDraft:
        analysis = await run_ai_limited(
            self._settings,
            lambda: run_in_threadpool(GeminiAnalyzer(self._settings).analyze, image_bytes, user_input),
        )
        subject = await self._resolve_subject(user_input, analysis)
        charcs = await self._wb.get_subject_charcs(int(subject["subjectID"]), locale="ru")
        card_payload = await run_ai_limited(
            self._settings,
            lambda: run_in_threadpool(CardGenerator(self._settings).generate, user_input, analysis, subject, charcs),
        )
        raw_payload = [group.model_dump(mode="json", exclude_none=True) for group in card_payload]
        await self._enrich_payload(raw_payload, int(subject["subjectID"]), user_input=user_input, analysis=analysis)
        first_variant = raw_payload[0]["variants"][0] if raw_payload and raw_payload[0].get("variants") else {}
        garment_json = GarmentAnalyzer.normalize_analysis(
            analysis.garment_json,
            front_image_bytes=image_bytes[0],
            title=str(first_variant.get("title") or analysis.product_name or ""),
            description=str(first_variant.get("description") or ""),
            category=str(subject.get("subjectName") or analysis.category or user_input.category or ""),
            gender=analysis.gender or user_input.gender,
        )
        analysis.garment_json = garment_json
        draft = CardDraft(
            user_id=self._user.id,
            store_id=self._store.id,
            status="draft",
            subject_id=int(subject["subjectID"]),
            vendor_code=card_payload[0].variants[0].vendorCode if card_payload and card_payload[0].variants else None,
            analysis=analysis.model_dump(),
            garment_json=garment_json,
            card_payload=raw_payload,
        )
        self._db.add(draft)
        self._db.commit()
        self._db.refresh(draft)
        return draft

    async def push_new_cards(self, groups: list[CardUploadGroup], dry_run: bool) -> dict[str, Any] | None:
        payload = [group.model_dump(mode="json", exclude_none=True) for group in groups]
        for group in payload:
            await self._enrich_payload([group], int(group["subjectID"]))
        await self._ensure_skus(payload, dry_run=dry_run)
        if dry_run:
            return None
        return await self._wb.upload_cards(payload)

    async def push_merge_cards(
        self,
        imt_id: int,
        variants: list[dict[str, Any]],
        dry_run: bool,
        subject_id: int | None = None,
    ) -> dict[str, Any] | None:
        if subject_id is not None:
            await self._enrich_payload({"cardsToAdd": variants}, subject_id)
        await self._ensure_variant_skus(variants, dry_run=dry_run)
        if dry_run:
            return None
        return await self._wb.upload_cards_add(imt_id, variants)

    async def move_nm_cards(self, nm_ids: list[int], target_imt: int | None, dry_run: bool) -> dict[str, Any] | None:
        if dry_run:
            return None
        return await self._wb.move_nm_cards(nm_ids, target_imt)

    async def get_cards_by_text(self, text_search: str, limit: int = 100, with_photo: int = -1) -> dict[str, Any]:
        return await self._wb.get_cards_list(
            {
                "settings": {
                    "cursor": {"limit": limit},
                    "filter": {"withPhoto": with_photo, "textSearch": text_search},
                }
            }
        )

    async def get_card_errors(self) -> dict[str, Any]:
        return await self._wb.get_card_errors()

    async def suggest_tnved(self, subject_id: int, search: str | None = None) -> dict[str, Any]:
        items = await self._wb.get_tnved(subject_id, search=search, locale="ru")
        return {"data": items, "selected": items[0] if items else None}

    async def enrich_payload_with_tnved(self, subject_id: int, payload: Any, search: str | None = None) -> dict[str, Any]:
        items = await self._wb.get_tnved(subject_id, search=search, locale="ru")
        selected = items[0] if items else None
        if not selected:
            return {"payload": payload, "tnved": None, "applied": False}

        charcs = await self._wb.get_subject_charcs(subject_id, locale="ru")
        seasons = await self._wb.get_seasons(locale="ru")
        CardPayloadEnricher(charcs, directories={"season": seasons}).enrich_payload(
            payload,
            subject_id=subject_id,
            tnved=selected,
        )
        return {"payload": payload, "tnved": selected, "applied": True}

    async def upload_media_links(self, nm_id: int, links: list[str]) -> dict[str, Any]:
        return await self._wb.upload_media_links(nm_id, links)

    async def upload_media_file(self, nm_id: int, photo_number: int, file_name: str, content: bytes) -> dict[str, Any]:
        return await self._wb.upload_media_file(nm_id, photo_number, file_name, content)

    async def _ensure_skus(self, payload: list[dict[str, Any]], dry_run: bool) -> None:
        missing_sizes = []
        for group in payload:
            for variant in group.get("variants", []):
                for size in variant.get("sizes", []):
                    if not size.get("skus"):
                        missing_sizes.append(size)
        await self._fill_missing_skus(missing_sizes, dry_run=dry_run)

    async def _ensure_variant_skus(self, variants: list[dict[str, Any]], dry_run: bool) -> None:
        missing_sizes = []
        for variant in variants:
            for size in variant.get("sizes", []):
                if not size.get("skus"):
                    missing_sizes.append(size)
        await self._fill_missing_skus(missing_sizes, dry_run=dry_run)

    async def _fill_missing_skus(self, missing_sizes: list[dict[str, Any]], dry_run: bool) -> None:
        if not missing_sizes:
            return
        if dry_run:
            for index, size in enumerate(missing_sizes, 1):
                size["skus"] = [f"DRY-RUN-SKU-{index}"]
            return

        barcodes = []
        remaining = len(missing_sizes)
        while remaining > 0:
            batch_size = min(remaining, 5000)
            payload_response = await self._wb.generate_barcodes(batch_size)
            batch = payload_response.get("data") or []
            if len(batch) < batch_size:
                raise AppError(
                    "barcode_generation_failed",
                    "Wildberries did not return enough generated SKUs.",
                    502,
                    {"requested": batch_size, "received": len(batch)},
                )
            barcodes.extend(batch)
            remaining -= batch_size
        for size, barcode in zip(missing_sizes, barcodes, strict=True):
            size["skus"] = [str(barcode)]

    async def _resolve_subject(self, user_input: ProductInput, analysis: ImageAnalysis) -> dict[str, Any]:
        return await SubjectResolver(self._settings, self._wb).resolve(user_input, analysis)

    async def _enrich_payload(
        self,
        payload: Any,
        subject_id: int,
        *,
        user_input: ProductInput | None = None,
        analysis: ImageAnalysis | None = None,
    ) -> None:
        charcs = await self._wb.get_subject_charcs(subject_id, locale="ru")
        seasons = await self._wb.get_seasons(locale="ru")
        tnved_items = await self._wb.get_tnved(subject_id, locale="ru")
        tnved = tnved_items[0] if tnved_items else None
        CardPayloadEnricher(charcs, directories={"season": seasons}).enrich_payload(
            payload,
            subject_id=subject_id,
            tnved=tnved,
            user_input=user_input,
            analysis=analysis,
        )

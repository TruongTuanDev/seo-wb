import asyncio
import copy
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.concurrency import run_job_limited
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models.card import CardDraft, CardJob
from app.models.store import Store
from app.models.user import User
from app.schemas.card import CardUploadGroup
from app.services.card_flow import CardFlowService
from app.services.product_intent_parser import ProductIntentParser


class CardJobRunner:
    def __init__(self, settings: Settings):
        self._settings = settings
        # Spacing between media uploads to stay under WB's per-seller global limiter.
        self._media_delay = float(getattr(settings, "wb_media_upload_delay_seconds", 0.8) or 0.8)

    async def run(self, job_id: int) -> None:
        await run_job_limited(self._settings, lambda: self._run(job_id))

    async def _run(self, job_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.get(CardJob, job_id)
            if not job:
                return
            self._mark(db, job, "running", "validating")
            user = db.get(User, job.user_id)
            store = db.get(Store, job.store_id)
            if not user or not store:
                raise RuntimeError("Job user or store no longer exists.")

            groups = [CardUploadGroup.model_validate(group) for group in job.card_payload]
            flow = CardFlowService(self._settings, db, user, store)

            self._mark(db, job, "running", "dry_run")
            dry_run_groups = [CardUploadGroup.model_validate(group) for group in copy.deepcopy(job.card_payload)]
            if job.mode == "add_to_existing_imt":
                await flow.push_merge_cards(
                    int(job.target_imt or 0),
                    [variant.model_dump(mode="json", exclude_none=True) for variant in dry_run_groups[0].variants],
                    dry_run=True,
                    subject_id=job.subject_id,
                )
            else:
                await flow.push_new_cards(dry_run_groups, dry_run=True)

            groups = [CardUploadGroup.model_validate(group) for group in job.card_payload]

            self._mark(db, job, "running", "pushing_card")
            if job.mode == "add_to_existing_imt":
                variants = [variant.model_dump(mode="json", exclude_none=True) for variant in groups[0].variants]
                wb_response = await flow.push_merge_cards(
                    int(job.target_imt or 0),
                    variants,
                    dry_run=False,
                    subject_id=job.subject_id,
                )
            else:
                wb_response = await flow.push_new_cards(groups, dry_run=False)

            self._update_draft_after_push(db, job, wb_response)

            self._mark(db, job, "running", "waiting_nm_id")
            await asyncio.sleep(8)
            await self._raise_if_wb_errors(flow, groups)
            nm_map = await self._wait_for_nm_ids(flow, groups)

            if job.mode == "create_then_merge":
                self._mark(db, job, "running", "merging_nm")
                await flow.move_nm_cards(list(nm_map.values()), job.target_imt, dry_run=False)

            self._mark(db, job, "running", "uploading_media")
            try:
                await self._upload_media(flow, job.media_manifest, nm_map)
            except AppError:
                # The card already exists on WB at this point. A media error
                # (typically a 429 rate limit) does not necessarily mean the
                # photos are missing, so verify the real state on WB before
                # treating the whole publish as failed.
                if not await self._verify_media_complete(flow, job.media_manifest, nm_map):
                    raise
                self._mark(db, job, "running", "media_verified")

            self._mark(db, job, "running", "setting_prices")
            price_result = await self._set_prices(flow, job.price_manifest, nm_map)

            self._mark(db, job, "completed", "completed", {"wb_response": wb_response, "nm_map": nm_map, "prices": price_result})
            self._complete_draft(db, job, wb_response, nm_map)
        except Exception as exc:
            db.rollback()
            failed_job = db.get(CardJob, job_id)
            if failed_job:
                failed_job.status = "failed"
                failed_job.step = "failed"
                failed_job.error = self._format_job_error(exc)
                db.commit()
                self._set_draft_status(db, failed_job, "needs_user_fix")
        finally:
            db.close()

    def _mark(
        self,
        db: Session,
        job: CardJob,
        status: str,
        step: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        job.status = status
        job.step = step
        if result is not None:
            job.result = result
        db.commit()
        db.refresh(job)

    def _set_draft_status(self, db: Session, job: CardJob, status: str) -> None:
        if not job.draft_id:
            return
        draft = db.get(CardDraft, job.draft_id)
        if draft:
            draft.status = status
            db.commit()

    def _update_draft_after_push(self, db: Session, job: CardJob, wb_response: dict[str, Any] | None) -> None:
        if not job.draft_id:
            return
        draft = db.get(CardDraft, job.draft_id)
        if not draft:
            return
        draft.status = "pushed"
        draft.card_payload = job.card_payload
        draft.wb_response = wb_response
        db.commit()

    def _complete_draft(
        self,
        db: Session,
        job: CardJob,
        wb_response: dict[str, Any] | None,
        nm_map: dict[str, int],
    ) -> None:
        if not job.draft_id:
            return
        draft = db.get(CardDraft, job.draft_id)
        if not draft:
            return
        draft.status = "completed"
        draft.wb_response = {
            **(wb_response or {}),
            "nm_map": nm_map,
        }
        db.commit()

    async def _wait_for_nm_ids(self, flow: CardFlowService, groups: list[CardUploadGroup]) -> dict[str, int]:
        nm_map: dict[str, int] = {}
        for group in groups:
            for variant in group.variants:
                vendor_code = variant.vendorCode
                aliases = self._vendor_code_aliases(variant)
                normalized_aliases = {alias.strip().casefold() for alias in aliases}
                for attempt in range(1, 31):
                    if attempt in {1, 4, 8, 15, 25}:
                        await self._raise_if_wb_errors(flow, groups)
                    search = aliases[min(attempt - 1, len(aliases) - 1)]
                    response = await flow.get_cards_by_text(search, limit=100, with_photo=-1)
                    cards = self._extract_cards(response)
                    found = next(
                        (
                            card
                            for card in cards
                            if str(card.get("vendorCode") or card.get("vendor_code") or "").strip().casefold()
                            in normalized_aliases
                        ),
                        None,
                    )
                    nm_id = found and (found.get("nmID") or found.get("nmId") or found.get("nm_id"))
                    if nm_id:
                        nm_map[vendor_code] = int(nm_id)
                        break
                    await asyncio.sleep(min(5 + attempt * 0.5, 10))
                if vendor_code not in nm_map:
                    raise RuntimeError(f'WB accepted the card, but NM ID was not found for vendorCode "{vendor_code}" yet.')
        return nm_map

    @staticmethod
    def _vendor_code_aliases(variant: Any) -> list[str]:
        vendor_code = str(variant.vendorCode or "").strip()
        aliases = [vendor_code]
        if "/" not in vendor_code:
            return aliases

        base, suffix = vendor_code.rsplit("/", 1)
        normalized_suffix = suffix.strip().casefold()
        seen = {vendor_code.casefold()}
        for characteristic in variant.characteristics:
            values = characteristic.value if isinstance(characteristic.value, list) else [characteristic.value]
            for value in values:
                text = str(value or "").strip()
                if not text:
                    continue
                if ProductIntentParser.vendor_suffix_from_color(text).casefold() != normalized_suffix:
                    continue
                alias = f"{base}/{text}"
                if alias.casefold() not in seen:
                    aliases.append(alias)
                    seen.add(alias.casefold())
        return aliases

    async def _raise_if_wb_errors(self, flow: CardFlowService, groups: list[CardUploadGroup]) -> None:
        vendor_codes = {variant.vendorCode for group in groups for variant in group.variants}
        response = await flow.get_card_errors()
        found_errors: dict[str, dict[str, Any]] = {}
        for item in self._extract_error_items(response):
            for vendor_code in vendor_codes:
                messages = self._extract_vendor_error_messages(item, vendor_code)
                if messages:
                    found_errors[vendor_code] = {
                        "vendorCode": vendor_code,
                        "object": item.get("object") or item.get("subjectName"),
                        "imtID": item.get("imtID") or item.get("imtId"),
                        "nmID": item.get("nmID") or item.get("nmId"),
                        "messages": [str(message) for message in messages],
                    }
        if found_errors:
            lines = ["Wildberries rejected card payload:"]
            for code, entry in found_errors.items():
                context = ", ".join(
                    str(value)
                    for value in (entry.get("object"), f"imtID={entry.get('imtID')}" if entry.get("imtID") else None)
                    if value
                )
                suffix = f" ({context})" if context else ""
                lines.append(f"- {code}{suffix}")
                lines.extend(f"  - {message}" for message in entry["messages"])
            raise RuntimeError("\n".join(lines))

    @staticmethod
    def _extract_cards(response: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(response.get("cards"), list):
            return response["cards"]
        data = response.get("data")
        if isinstance(data, dict) and isinstance(data.get("cards"), list):
            return data["cards"]
        if isinstance(data, list):
            return data
        return []

    @staticmethod
    def _extract_error_items(response: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        containers = [response]
        if isinstance(response, dict):
            containers.append(response.get("data"))

        for container in containers:
            if isinstance(container, list):
                items.extend(item for item in container if isinstance(item, dict))
                continue
            if not isinstance(container, dict):
                continue
            for key in ("items", "cards", "errors"):
                value = container.get(key)
                if isinstance(value, list):
                    items.extend(item for item in value if isinstance(item, dict))
                elif isinstance(value, dict) and key == "errors":
                    items.append({"errors": value})
        return items

    @staticmethod
    def _extract_vendor_error_messages(item: dict[str, Any], vendor_code: str) -> list[str]:
        aliases = {
            vendor_code,
            vendor_code.strip(),
            vendor_code.strip().casefold(),
        }
        item_vendor_code = str(item.get("vendorCode") or item.get("vendor_code") or "").strip()
        errors = item.get("errors") or item.get("error") or item.get("messages") or item.get("message")

        if isinstance(errors, dict):
            for key, value in errors.items():
                if str(key).strip().casefold() in aliases:
                    return CardJobRunner._coerce_messages(value)
            if item_vendor_code and item_vendor_code.casefold() in aliases:
                return CardJobRunner._coerce_messages(errors)
            return []

        if item_vendor_code and item_vendor_code.casefold() in aliases:
            return CardJobRunner._coerce_messages(errors)
        return []

    @staticmethod
    def _coerce_messages(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(message) for message in value if message is not None]
        if isinstance(value, dict):
            messages: list[str] = []
            for nested_value in value.values():
                messages.extend(CardJobRunner._coerce_messages(nested_value))
            return messages
        return [str(value)]

    @staticmethod
    def _format_job_error(exc: Exception) -> str:
        if isinstance(exc, AppError):
            payload = {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
            return json.dumps(payload, ensure_ascii=False, indent=2)[:4000]
        return str(exc)[:4000]

    async def _upload_media(self, flow: CardFlowService, media_manifest: dict[str, Any], nm_map: dict[str, int]) -> None:
        items = media_manifest.get("items", [])
        for index, item in enumerate(items):
            vendor_code = str(item.get("vendorCode") or "")
            path = Path(str(item.get("path") or ""))
            photo_number = int(item.get("photoNumber") or 1)
            nm_id = nm_map.get(vendor_code)
            if not nm_id or not path.exists():
                continue
            content = await asyncio.to_thread(path.read_bytes)
            await self._upload_media_with_retry(flow, nm_id, photo_number, path.name, content)
            # Space out requests so we don't trip WB's per-seller global limiter.
            if index < len(items) - 1:
                await asyncio.sleep(self._media_delay)

    async def _upload_media_with_retry(
        self,
        flow: CardFlowService,
        nm_id: int,
        photo_number: int,
        file_name: str,
        content: bytes,
        attempts: int = 5,
    ) -> None:
        for attempt in range(1, attempts + 1):
            try:
                await flow.upload_media_file(nm_id, photo_number, file_name, content)
                return
            except AppError as exc:
                status = exc.details.get("status_code") if isinstance(exc.details, dict) else None
                if status == 429 and attempt < attempts:
                    await asyncio.sleep(min(30.0, 5.0 * attempt))
                    continue
                raise

    async def _set_prices(
        self,
        flow: CardFlowService,
        price_manifest: dict[str, Any],
        nm_map: dict[str, int],
    ) -> dict[str, Any]:
        """Apply per-variant prices on WB after the card has an nmID. A pricing
        failure never fails the whole job — the card is already live."""
        items_in = (price_manifest or {}).get("items") or []
        price_items: list[dict[str, Any]] = []
        for entry in items_in:
            vendor_code = str(entry.get("vendorCode") or "")
            nm_id = nm_map.get(vendor_code)
            price = entry.get("price")
            if not nm_id or not price:
                continue
            item: dict[str, Any] = {"nmID": int(nm_id), "price": int(price)}
            if entry.get("discount") is not None:
                item["discount"] = int(entry["discount"])
            price_items.append(item)

        if not price_items:
            return {"applied": False, "reason": "no_prices"}

        try:
            await flow.apply_prices(price_items)
        except Exception as exc:  # noqa: BLE001 - report, do not fail the publish
            return {"applied": False, "error": str(exc)[:500], "submitted": price_items}

        verified: dict[str, int] = {}
        try:
            await asyncio.sleep(6)
            applied = await flow.get_applied_prices([item["nmID"] for item in price_items])
            verified = {str(nm_id): price for nm_id, price in applied.items()}
        except Exception:  # noqa: BLE001 - verification is best-effort
            verified = {}
        return {"applied": True, "submitted": price_items, "verified": verified}

    async def _verify_media_complete(
        self,
        flow: CardFlowService,
        media_manifest: dict[str, Any],
        nm_map: dict[str, int],
    ) -> bool:
        """Check WB directly: a card is considered done when every variant has at
        least the number of photos we tried to upload. WB may still be processing
        photos right after upload, so retry a few times."""
        expected: dict[str, int] = {}
        for item in media_manifest.get("items", []):
            vendor_code = str(item.get("vendorCode") or "")
            path = Path(str(item.get("path") or ""))
            if vendor_code and nm_map.get(vendor_code) and path.exists():
                expected[vendor_code] = expected.get(vendor_code, 0) + 1
        if not expected:
            return True

        for attempt in range(1, 4):
            all_ok = True
            for vendor_code, expected_count in expected.items():
                nm_id = int(nm_map.get(vendor_code) or 0)
                response = await flow.get_cards_by_text(vendor_code, limit=100, with_photo=-1)
                cards = self._extract_cards(response)
                card = next(
                    (c for c in cards if int(c.get("nmID") or c.get("nmId") or c.get("nm_id") or 0) == nm_id),
                    None,
                )
                photos = (card or {}).get("photos") or []
                if len(photos) < expected_count:
                    all_ok = False
                    break
            if all_ok:
                return True
            if attempt < 3:
                await asyncio.sleep(5)
        return False

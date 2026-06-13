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
from app.services.admin_runtime import get_effective_ai_runtime_settings
from app.services.card_generator import CardGenerator
from app.services.card_payload_enricher import CardPayloadEnricher
from app.services.garment_analyzer import GarmentAnalyzer
from app.services.gemini_analyzer import GeminiAnalyzer
from app.services.product_copy_policy import (
    build_copy_policy_context,
    build_seo_title,
    cleanup_description,
    cleanup_title,
    render_description,
    resolve_product_family,
)
from app.services.seo_content_validator import SeoContentValidator
from app.services.seo_keyword_planner import SeoKeywordPlanner
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
        runtime_settings = get_effective_ai_runtime_settings(self._db, self._settings)
        analysis = await run_ai_limited(
            self._settings,
            lambda: run_in_threadpool(GeminiAnalyzer(self._settings).analyze, image_bytes, user_input),
        )
        garment_json: dict[str, Any] = {}
        try:
            garment_json = await run_ai_limited(
                self._settings,
                lambda: run_in_threadpool(
                    GarmentAnalyzer(self._settings).analyze,
                    image_bytes[0],
                    image_bytes[1] if len(image_bytes) > 1 else None,
                    user_input.category or analysis.product_name,
                    None,
                    analysis.category or user_input.category,
                    analysis.gender or user_input.gender,
                ),
            )
        except Exception:
            garment_json = {}
        subject = await self._resolve_subject(user_input, analysis)
        charcs = await self._wb.get_subject_charcs(int(subject["subjectID"]), locale="ru")
        attribute_confidence = CardPayloadEnricher(charcs).build_attribute_confidence(
            subject_id=int(subject["subjectID"]),
            user_input=user_input,
            analysis=analysis,
        )
        seo_keyword_plan = SeoKeywordPlanner.build_plan(
            category=user_input.category or analysis.category,
            subject_name=subject.get("subjectName"),
            brand=user_input.brand,
            gender=user_input.gender or analysis.gender,
            analysis=analysis,
            user_input=user_input,
            confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
            wb_characteristics=charcs,
            product_family_policy=build_copy_policy_context(subject, analysis, user_input),
        )
        card_payload = await run_ai_limited(
            self._settings,
            lambda: run_in_threadpool(
                CardGenerator(self._settings).generate,
                user_input,
                analysis,
                subject,
                charcs,
                garment_json,
                seo_keyword_plan,
                attribute_confidence,
            ),
        )
        raw_payload = [group.model_dump(mode="json", exclude_none=True) for group in card_payload]
        await self._enrich_payload(raw_payload, int(subject["subjectID"]), user_input=user_input, analysis=analysis)
        analysis_payload = analysis.model_dump()
        analysis_payload["product_input"] = user_input.model_dump(mode="json", exclude_none=True)
        if garment_json:
            analysis_payload["garment_json"] = garment_json
            analysis_payload["garment_area"] = garment_json.get("garment_area")
        analysis_payload["attribute_confidence"] = attribute_confidence
        analysis_payload["seo_keyword_plan"] = seo_keyword_plan
        seo_score = self._apply_seo_validation(
            raw_payload,
            seo_keyword_plan=seo_keyword_plan,
            attribute_confidence=attribute_confidence,
            runtime_settings=runtime_settings,
            subject=subject,
            analysis=analysis,
            user_input=user_input,
        )
        analysis_payload["seo_score"] = seo_score
        analysis_payload["seo_issues"] = seo_score.get("issues", [])
        draft = CardDraft(
            user_id=self._user.id,
            store_id=self._store.id,
            status="draft",
            subject_id=int(subject["subjectID"]),
            vendor_code=card_payload[0].variants[0].vendorCode if card_payload and card_payload[0].variants else None,
            analysis=analysis_payload,
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

    def _apply_seo_validation(
        self,
        payload: list[dict[str, Any]],
        *,
        seo_keyword_plan: dict[str, Any],
        attribute_confidence: dict[str, Any],
        runtime_settings: Any,
        subject: dict[str, Any] | None = None,
        analysis: ImageAnalysis | None = None,
        user_input: ProductInput | None = None,
    ) -> dict[str, Any]:
        min_chars = int(getattr(runtime_settings, "description_min_chars", 600) or 600)
        max_chars = int(getattr(runtime_settings, "description_max_chars", 900) or 900)
        min_score = int(getattr(runtime_settings, "seo_min_score", 70) or 70)
        repair_attempts = max(0, int(getattr(runtime_settings, "seo_repair_max_attempts", 1) or 0))
        require_primary_keyword_in_title = bool(getattr(runtime_settings, "require_primary_keyword_in_title", True))
        include_gender_in_title = bool(getattr(runtime_settings, "include_gender_in_title", False))
        min_grammar_score = int(getattr(runtime_settings, "minimum_grammar_score", 70) or 70)
        min_marketplace_score = int(getattr(runtime_settings, "minimum_marketplace_score", 70) or 70)
        min_critical_attribute_score = int(getattr(runtime_settings, "minimum_critical_attribute_score", 80) or 80)
        scorecards: list[dict[str, Any]] = []
        for group in payload:
            for variant in group.get("variants", []) or []:
                title = str(variant.get("title") or "")
                description = str(variant.get("description") or "")
                final_validator_result: dict[str, Any] | None = None
                policy = resolve_product_family(subject or {}, analysis, user_input)
                title_attributes = (
                    self._seo_title_attributes(user_input, analysis, subject or {}, seo_keyword_plan, attribute_confidence)
                    if analysis is not None and user_input is not None and subject is not None
                    else {}
                )

                for attempt in range(repair_attempts + 1):
                    validator_result = SeoContentValidator.validate(
                        title=title,
                        description=description,
                        seo_keyword_plan=seo_keyword_plan,
                        confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
                        inferred_attributes=attribute_confidence.get("inferred_attributes"),
                        min_chars=min_chars,
                        max_chars=max_chars,
                        auto_fix=True,
                    )
                    description = str(validator_result.get("fixed_description") or description or "")

                    primary_keyword = str(seo_keyword_plan.get("primary_keyword") or "").strip()
                    needs_title_repair = (
                        require_primary_keyword_in_title
                        and primary_keyword
                        and primary_keyword.casefold() not in title.casefold()
                    )
                    if needs_title_repair and analysis is not None and user_input is not None and subject is not None:
                        rebuilt_title = build_seo_title(
                            subject.get("subjectName"),
                            analysis.gender or user_input.gender,
                            title_attributes,
                            seo_keyword_plan,
                            brand=(user_input.brand or "").strip() or None,
                            include_gender_in_title=include_gender_in_title,
                        )
                        title = cleanup_title(
                            str(rebuilt_title.get("title") or title),
                            str(subject.get("subjectName") or "Товар"),
                            analysis,
                            user_input,
                        )

                    final_validator_result = SeoContentValidator.validate(
                        title=title,
                        description=description,
                        seo_keyword_plan=seo_keyword_plan,
                        confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
                        inferred_attributes=attribute_confidence.get("inferred_attributes"),
                        min_chars=min_chars,
                        max_chars=max_chars,
                        auto_fix=False,
                    )
                    candidate_scorecard = SeoContentValidator.build_scorecard(
                        title=title,
                        description=description,
                        seo_keyword_plan=seo_keyword_plan,
                        validator_result=final_validator_result,
                        confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
                        inferred_attributes=attribute_confidence.get("inferred_attributes"),
                        subject_name=(subject or {}).get("subjectName"),
                    )
                    if (
                        candidate_scorecard.get("seo_score", 0) >= min_score
                        and candidate_scorecard.get("grammar_score", 0) >= min_grammar_score
                        and candidate_scorecard.get("marketplace_score", 0) >= min_marketplace_score
                        and candidate_scorecard.get("critical_attribute_score", 0) >= min_critical_attribute_score
                        and final_validator_result.get("valid", False)
                    ):
                        break

                    if attempt >= repair_attempts:
                        break

                    if analysis is not None and user_input is not None and subject is not None:
                        rebuilt_title = build_seo_title(
                            subject.get("subjectName"),
                            analysis.gender or user_input.gender,
                            title_attributes,
                            seo_keyword_plan,
                            brand=(user_input.brand or "").strip() or None,
                            include_gender_in_title=include_gender_in_title,
                        )
                        title = cleanup_title(
                            str(rebuilt_title.get("title") or title),
                            str(subject.get("subjectName") or "Товар"),
                            analysis,
                            user_input,
                        )
                        regenerated_description = render_description(policy, title=title, analysis=analysis, user_input=user_input)
                        description = cleanup_description(
                            regenerated_description,
                            title=title,
                            subject=subject,
                            analysis=analysis,
                            user_input=user_input,
                        )

                variant["title"] = title
                variant["description"] = description
                validator_result = final_validator_result or {
                    "score": 0,
                    "issues": ["SEO validation did not run"],
                    "suggestions": [],
                }
                scorecards.append(
                    SeoContentValidator.build_scorecard(
                        title=title,
                        description=description,
                        seo_keyword_plan=seo_keyword_plan,
                        validator_result=validator_result,
                        confirmed_attributes=attribute_confidence.get("confirmed_attributes"),
                        inferred_attributes=attribute_confidence.get("inferred_attributes"),
                        subject_name=(subject or {}).get("subjectName"),
                    )
                )
        if not scorecards:
            return {
                "seo_score": 0,
                "title_score": 0,
                "description_score": 0,
                "attributes_score": 0,
                "keyword_coverage_score": 0,
                "issues": ["No variants generated"],
                "suggestions": ["Generate at least one variant"],
                "status": "poor",
            }
        aggregate = {
            "seo_score": int(round(sum(item["seo_score"] for item in scorecards) / len(scorecards))),
            "title_score": int(round(sum(item["title_score"] for item in scorecards) / len(scorecards))),
            "description_score": int(round(sum(item["description_score"] for item in scorecards) / len(scorecards))),
            "attributes_score": int(round(sum(item["attributes_score"] for item in scorecards) / len(scorecards))),
            "keyword_coverage_score": int(round(sum(item["keyword_coverage_score"] for item in scorecards) / len(scorecards))),
            "keyword_score": int(round(sum(item.get("keyword_score", 0) for item in scorecards) / len(scorecards))),
            "grammar_score": int(round(sum(item.get("grammar_score", 0) for item in scorecards) / len(scorecards))),
            "marketplace_score": int(round(sum(item.get("marketplace_score", 0) for item in scorecards) / len(scorecards))),
            "critical_attribute_score": int(round(sum(item.get("critical_attribute_score", 0) for item in scorecards) / len(scorecards))),
            "issues": [],
            "suggestions": [],
            "status": "poor",
            "variants": scorecards,
        }
        for item in scorecards:
            aggregate["issues"].extend(item.get("issues", []))
            aggregate["suggestions"].extend(item.get("suggestions", []))
        aggregate["issues"] = list(dict.fromkeys(aggregate["issues"]))[:10]
        aggregate["suggestions"] = list(dict.fromkeys(aggregate["suggestions"]))[:10]
        score = aggregate["seo_score"]
        aggregate["status"] = "excellent" if score >= 85 else "good" if score >= 70 else "needs_review" if score >= 50 else "poor"
        return aggregate

    @staticmethod
    def _seo_title_attributes(
        user_input: ProductInput,
        analysis: ImageAnalysis,
        subject: dict[str, Any],
        seo_keyword_plan: dict[str, Any],
        attribute_confidence: dict[str, Any],
    ) -> dict[str, Any]:
        confirmed = (attribute_confidence or {}).get("confirmed_attributes") or {}
        inferred = (attribute_confidence or {}).get("inferred_attributes") or {}
        seo_inputs = user_input.seo_inputs if user_input else None
        return {
            "material": getattr(seo_inputs, "material", None) or confirmed.get("composition") or inferred.get("composition") or analysis.material,
            "color": getattr(seo_inputs, "color", None) or confirmed.get("color") or inferred.get("color") or analysis.color or user_input.color,
            "fit": getattr(seo_inputs, "fit", None) or confirmed.get("fit") or inferred.get("fit") or analysis.fit_type,
            "season": getattr(seo_inputs, "season", None) or confirmed.get("season") or inferred.get("season") or analysis.season,
            "quantity_in_set": getattr(seo_inputs, "quantity_in_set", None),
            "key_feature": getattr(seo_inputs, "key_feature", None),
            "subject": subject.get("subjectName"),
            "primary_keyword": seo_keyword_plan.get("primary_keyword"),
        }

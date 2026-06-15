import asyncio
import base64
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from PIL import Image, ImageOps
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models import CardDraft
from app.models.admin import GeneratedImageJob, UsageRecord
from app.models.user import User
from app.services.billing_foundation import (
    IMAGE_JOB_QUEUE_NORMAL,
    log_platform_audit,
    record_credit_transaction,
)
from app.services.image_storage import ImageStorage
from app.services.image_concurrency import DistributedImageApiLimiter, is_retryable_openai_error
from app.services.product_image_prompt_builder import build_product_image_prompt


IMAGE_JOB_STORAGE_DIR = Path("storage/image_jobs")
IMAGE_JOB_QUEUE_KEY = IMAGE_JOB_QUEUE_NORMAL
logger = logging.getLogger(__name__)


class ProductImageGenerator:
    def __init__(self, settings: Settings, redis: Redis):
        self._settings = settings
        self._redis = redis
        self._storage = ImageStorage(settings)
        self._api_limiter = DistributedImageApiLimiter(
            redis,
            limit=settings.image_global_concurrency,
            lease_seconds=settings.image_api_slot_lease_seconds,
        )

    async def create_job(
        self,
        *,
        user_id: int,
        store_id: int,
        draft_id: int,
        variant_id: str,
        variant_index: int,
        quantity: int,
        metadata: dict[str, Any],
        front_image: bytes,
        back_image: bytes | None = None,
        model_image: bytes | None = None,
        job_type: str = "openai",
        model_id: str | None = None,
        queue_name: str = IMAGE_JOB_QUEUE_NORMAL,
        credit_cost: int = 0,
        db: Session | None = None,
    ) -> dict[str, Any]:
        if job_type == "try_on":
            raise AppError("fal_ai_not_supported", "Virtual Try-On is not supported because Fal.ai integration has been removed.", 400)
        elif job_type in {"openai", "gpt_image_openai", "gpt_image"} and not self._settings.openai_api_key:
            raise AppError("missing_openai_key", "OPENAI_API_KEY is missing.", 500)

        lock_ttl = max(self._settings.image_generation_lock_ttl_seconds, self._settings.image_job_lease_seconds * 2)
        lock_key = self._lock_key(user_id, draft_id, variant_id)
        locked = await self._redis.set(lock_key, "1", nx=True, ex=lock_ttl)
        if not locked:
            raise AppError("image_generation_already_running", "Image generation is already running for this card.", 409)
        store_lock_key = self._store_lock_key(store_id)
        store_locked = True
        if self._settings.max_active_order_per_store > 0:
            store_locked = await self._redis.set(
                store_lock_key,
                "1",
                nx=True,
                ex=lock_ttl,
            )
        if not store_locked:
            await self._redis.delete(lock_key)
            raise AppError(
                "store_image_generation_already_running",
                "Bạn đang có ảnh được tạo cho shop này, vui lòng đợi hoàn tất.",
                409,
            )

        job_id = uuid4().hex
        total = max(1, min(quantity, self._settings.max_ai_product_images))
        job_dir = IMAGE_JOB_STORAGE_DIR / job_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        tasks: list[asyncio.Task[tuple[int, dict[str, Any]]]] = []
        try:
            metadata = json.loads(json.dumps(metadata))
            metadata.setdefault("variant_id", variant_id)
            metadata.setdefault("variant_index", variant_index)
            self._prepare_reference_image(front_image, input_dir / "front.jpg")
            if back_image:
                self._prepare_reference_image(back_image, input_dir / "back.jpg")
            has_model_reference = bool(model_image)
            if model_image:
                self._prepare_reference_image(model_image, input_dir / "model.jpg")

            state = {
                "id": job_id,
                "user_id": user_id,
                "store_id": store_id,
                "draft_id": draft_id,
                "variant_id": variant_id,
                "variant_index": variant_index,
                "lock_key": lock_key,
                "store_lock_key": store_lock_key if self._settings.max_active_order_per_store > 0 else None,
                "status": "queued",
                "step": "queued",
                "progress": 0,
                "total": total,
                "metadata": metadata,
                "has_model_reference": has_model_reference,
                "images": [],
                "error": None,
                "job_type": job_type,
                "model_id": model_id,
                "queue_name": queue_name,
                "credit_cost": max(0, int(credit_cost or 0)),
            }
            await self._save_state(job_id, state)
            if db is not None:
                self._persist_job_record(db, state)
                log_platform_audit(
                    db,
                    action="PRIORITY_QUEUE_ASSIGNMENT",
                    target_type="image_job",
                    target_id=job_id,
                    metadata={"queue_name": queue_name, "user_id": user_id, "job_type": job_type},
                )
                db.commit()
            await self._redis.rpush(queue_name, job_id)
            return self._public_state(state)
        except Exception:
            await self._redis.delete(lock_key)
            if self._settings.max_active_order_per_store > 0:
                await self._redis.delete(store_lock_key)
            raise

    async def get_job(self, job_id: str, user_id: int) -> dict[str, Any]:
        state = await self._load_state(job_id)
        if not state or int(state.get("user_id") or 0) != user_id:
            raise AppError("image_job_not_found", "Image generation job was not found.", 404)
        return self._public_state(state)

    async def update_job_image(
        self,
        *,
        job_id: str,
        image_id: str,
        user_id: int,
        db: Session,
        action: str,
    ) -> dict[str, Any]:
        job = db.get(GeneratedImageJob, job_id)
        if not job or job.deleted_at is not None or job.user_id != user_id:
            raise AppError("image_job_not_found", "Image generation job was not found.", 404)
        state = await self._load_state(job_id)
        next_images = []
        found = False
        for image in list(job.images or []):
            if image.get("image_id") != image_id:
                next_images.append(image)
                continue
            found = True
            next_images.append(self._apply_image_action(image, action))
        if not found:
            raise AppError("image_not_found", "Generated image was not found.", 404)
        next_state = dict(state or {
            "id": job.id,
            "status": job.status,
            "step": job.step,
            "progress": len(next_images),
            "total": job.quantity,
            "variant_id": (job.metadata_json or {}).get("variant_id"),
            "images": list(job.images or []),
            "error": job.error_message,
            "job_type": job.job_type,
            "queue_name": job.queue_name,
            "credit_cost": job.credit_cost,
        })
        next_state["images"] = next_images
        next_state["validation_summary"] = self._validation_summary(next_images)
        next_state["seller_warning"] = self._seller_warning_for_images(next_images)
        next_state["final_validation_status"] = self._overall_validation_status(next_images)
        if next_state.get("status") in {"completed", "completed_with_warnings"}:
            next_state["status"] = (
                "completed_with_warnings"
                if next_state["validation_summary"]["warning_count"]
                or next_state["validation_summary"]["review_required_count"]
                or next_state["validation_summary"]["failed_count"]
                else "completed"
            )
            next_state["step"] = next_state["status"]
        if state:
            await self._save_state(job_id, {**state, **next_state})
        self._sync_job_json(db, job, next_state)
        return self._public_state(next_state)

    async def retry_single_catalog_image_job(
        self,
        *,
        job_id: str,
        image_id: str,
        user_id: int,
        db: Session,
    ) -> dict[str, Any]:
        job = db.get(GeneratedImageJob, job_id)
        if not job or job.deleted_at is not None or job.user_id != user_id:
            raise AppError("image_job_not_found", "Image generation job was not found.", 404)
        if job.job_type not in {"gpt_image", "gpt_image_openai"}:
            raise AppError("unsupported_job_type", "Individual image retry is only supported for GPT catalog jobs.", 400)
        source_image = next((item for item in list(job.images or []) if item.get("image_id") == image_id), None)
        if not source_image:
            raise AppError("image_not_found", "Generated image was not found.", 404)

        input_dir = IMAGE_JOB_STORAGE_DIR / job_id / "input"
        front_path = input_dir / "front.jpg"
        back_path = input_dir / "back.jpg"
        model_path = input_dir / "model.jpg"
        if not front_path.exists():
            raise AppError("missing_front_image", "Source job inputs are unavailable for retry.", 400)

        metadata = json.loads(json.dumps(job.metadata_json or {}))
        metadata["override_tasks"] = [{
            "pose": source_image.get("pose") or "front",
            "type": source_image.get("task_type") or "catalog",
            "label": source_image.get("label") or "Retried Image",
        }]

        raw_state = await self._load_state(job_id) or {}
        return await self.create_job(
            user_id=user_id,
            store_id=int(job.store_id or 0),
            draft_id=int(job.draft_id or 0),
            variant_id=str(raw_state.get("variant_id") or metadata.get("variant_id") or image_id),
            variant_index=int(raw_state.get("variant_index") or metadata.get("variant_index") or 0),
            quantity=1,
            metadata=metadata,
            front_image=front_path.read_bytes(),
            back_image=back_path.read_bytes() if back_path.exists() else None,
            model_image=model_path.read_bytes() if model_path.exists() else None,
            job_type=job.job_type,
            model_id=job.model_id,
            queue_name=job.queue_name or IMAGE_JOB_QUEUE_NORMAL,
            credit_cost=job.credit_cost if (job.quantity or 0) <= 1 else max(0, int(round((job.credit_cost or 0) / max(job.quantity or 1, 1)))),
            db=db,
        )

    @staticmethod
    def _apply_image_action(image: dict[str, Any], action: str) -> dict[str, Any]:
        next_image = json.loads(json.dumps(image))
        validation_result = dict(next_image.get("validation_result") or {})
        manual_actions = dict(validation_result.get("manual_actions") or {})
        if action == "hide":
            manual_actions["hidden"] = True
        elif action == "use_anyway":
            manual_actions["used_anyway"] = True
            validation_result["can_use_for_listing"] = True
        elif action == "approve":
            manual_actions["approved_manually"] = True
            validation_result["validation_status"] = "approved"
            validation_result["risk_level"] = "low"
            validation_result["can_use_for_listing"] = True
        elif action == "reject":
            manual_actions["rejected_manually"] = True
            validation_result["validation_status"] = "failed"
            validation_result["risk_level"] = "high"
            validation_result["can_use_for_listing"] = False
        else:
            raise AppError("invalid_image_action", "Unsupported image action.", 400)
        validation_result["manual_actions"] = manual_actions
        next_image["validation_result"] = validation_result
        return next_image

    @staticmethod
    def _validation_summary(images: list[dict[str, Any]]) -> dict[str, Any]:
        approved = warning = review_required = failed = 0
        for image in images:
            status = str((image.get("validation_result") or {}).get("validation_status") or "").lower()
            if status == "approved":
                approved += 1
            elif status == "warning":
                warning += 1
            elif status == "review_required":
                review_required += 1
            elif status == "failed":
                failed += 1
        return {
            "total_images": len(images),
            "approved_count": approved,
            "warning_count": warning,
            "review_required_count": review_required,
            "failed_count": failed,
        }

    @staticmethod
    def _seller_warning_for_images(images: list[dict[str, Any]]) -> str | None:
        if any(((image.get("validation_result") or {}).get("validation_status") == "failed") for image in images):
            return "High risk images were generated. Review carefully before publishing."
        if any(((image.get("validation_result") or {}).get("validation_status") == "review_required") for image in images):
            return "Some generated images need seller review before publishing."
        if any(((image.get("validation_result") or {}).get("validation_status") == "warning") for image in images):
            return "Some generated images contain medium-risk validation warnings. Review carefully before publishing."
        return None

    @staticmethod
    def _overall_validation_status(images: list[dict[str, Any]]) -> str:
        statuses = [str((image.get("validation_result") or {}).get("validation_status") or "").lower() for image in images]
        if "failed" in statuses:
            return "failed"
        if "review_required" in statuses:
            return "review_required"
        if "warning" in statuses:
            return "warning"
        return "approved"

    def _sync_job_json(self, db: Session, job: GeneratedImageJob, state: dict[str, Any]) -> None:
        validation_result = dict(job.validation_result or {})
        validation_result["validation_summary"] = state.get("validation_summary")
        validation_result["seller_warning"] = state.get("seller_warning")
        validation_result["final_validation_status"] = state.get("final_validation_status")
        job.images = list(state.get("images") or [])
        job.validation_result = validation_result
        job.status = self._normalize_status(str(state.get("status") or job.status))
        job.step = str(state.get("step") or job.step)
        job.error_message = state.get("error")
        db.commit()

    async def resolve_media_path(self, job_id: str, file_name: str, user_id: int) -> Path:
        state = await self._load_state(job_id)
        if not state or int(state.get("user_id") or 0) != user_id:
            raise AppError("generated_image_not_found", "Generated image was not found.", 404)
        safe_name = Path(file_name).name
        output_dir = (IMAGE_JOB_STORAGE_DIR / job_id / "output").resolve()
        path = (output_dir / safe_name).resolve()
        if output_dir not in path.parents or not path.is_file():
            raise AppError("generated_image_not_found", "Generated image was not found.", 404)
        return path

    async def run_job(self, job_id: str, db: Session) -> dict[str, Any]:
        state = await self._load_state(job_id)
        if not state:
            raise AppError("image_job_not_found", "Image generation job was not found.", 404)
        if state.get("status") in {"completed", "completed_with_warnings", "failed", "failed_validation"}:
            await self._release_job_locks(state)
            return self._public_state(state)

        if state.get("job_type") == "try_on":
            from app.services.virtual_try_on import VirtualTryOnService
            self._update_job_record(db, state)
            service = VirtualTryOnService(self._settings, self._redis)
            try:
                result = await service.run_try_on_job(
                    job_id=job_id,
                    db=db,
                    state=state,
                    save_state_fn=self._save_state,
                    attach_draft_fn=self._attach_to_draft
                )
                self._sync_job_from_state(db, job_id, await self._load_state(job_id) or state)
                return result
            except Exception:
                self._sync_job_from_state(db, job_id, await self._load_state(job_id) or state)
                raise
            finally:
                lock_key = state.get("lock_key")
                if lock_key:
                    await self._redis.delete(str(lock_key))

        if state.get("job_type") in {"gpt_image", "gpt_image_openai"}:
            from app.services.gpt_image_catalog import GPTImageCatalogService
            self._update_job_record(db, state)
            service = GPTImageCatalogService(self._settings, self._redis)
            try:
                result = await service.run_gpt_image_job(
                    job_id=job_id,
                    db=db,
                    state=state,
                    save_state_fn=self._save_state,
                    attach_draft_fn=self._attach_to_draft,
                    use_openai=(state.get("job_type") == "gpt_image_openai")
                )
                self._sync_job_from_state(db, job_id, await self._load_state(job_id) or state)
                return result
            except Exception:
                self._sync_job_from_state(db, job_id, await self._load_state(job_id) or state)
                raise
            finally:
                lock_key = state.get("lock_key")
                if lock_key:
                    await self._redis.delete(str(lock_key))
                store_lock_key = state.get("store_lock_key")
                if store_lock_key:
                    await self._redis.delete(str(store_lock_key))

        try:
            state["status"] = "processing"
            state["step"] = "processing"
            await self._save_state(job_id, state)
            self._update_job_record(db, state)

            total = int(state["total"])
            metadata = state.get("metadata") or {}
            has_model_reference = bool(state.get("has_model_reference"))
            generated_by_index: dict[int, dict[str, Any]] = {}
            concurrency = max(1, min(total, self._settings.openai_image_concurrency))
            semaphore = asyncio.Semaphore(concurrency)

            async def generate_index(index: int) -> tuple[int, dict[str, Any]]:
                async with semaphore:
                    started_at = monotonic()
                    prompt = build_product_image_prompt(metadata, index, total, has_model_reference)
                    content = await self._generate_one_with_retry(job_id, prompt, has_model_reference)
                    file_name = f"generated-{index + 1:02d}.jpg"
                    output_path = IMAGE_JOB_STORAGE_DIR / job_id / "output" / file_name
                    storage_result = await asyncio.to_thread(
                        self._storage.save_generated_image,
                        job_id=job_id,
                        file_name=file_name,
                        content=content,
                        local_path=output_path,
                    )
                    item = {
                        "fileName": file_name,
                        "url": storage_result["url"],
                        "storage": storage_result["storage"],
                        "storageKey": storage_result["storageKey"],
                        "bytes": storage_result["bytes"],
                        "width": storage_result.get("width"),
                        "height": storage_result.get("height"),
                        "prompt": prompt,
                    }
                    logger.info(
                        "Generated image job=%s image_index=%d duration_seconds=%.2f",
                        job_id,
                        index,
                        monotonic() - started_at,
                    )
                    return index, item

            tasks = [asyncio.create_task(generate_index(index)) for index in range(total)]
            for completed in asyncio.as_completed(tasks):
                index, item = await completed
                generated_by_index[index] = item
                ordered_images = [generated_by_index[item_index] for item_index in sorted(generated_by_index)]
                state["images"] = ordered_images
                state["progress"] = len(ordered_images)
                await self._save_state(job_id, state)

            generated_images = [generated_by_index[index] for index in range(total)]

            self._attach_to_draft(db, state, generated_images)
            state["status"] = "completed"
            state["step"] = "completed"
            await self._save_state(job_id, state)
            self._sync_job_from_state(db, job_id, state)
            return self._public_state(state)
        except Exception as exc:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            state["status"] = "failed"
            state["step"] = "failed"
            state["error"] = str(exc)[:2000]
            await self._save_state(job_id, state)
            self._sync_job_from_state(db, job_id, state)
            raise
        finally:
            lock_key = state.get("lock_key")
            if lock_key:
                await self._redis.delete(str(lock_key))
            store_lock_key = state.get("store_lock_key")
            if store_lock_key:
                await self._redis.delete(str(store_lock_key))

    async def _generate_one_with_retry(self, job_id: str, prompt: str, has_model_reference: bool) -> bytes:
        state = await self._load_state(job_id)
        metadata = (state or {}).get("metadata", {})
        runtime_config = metadata.get("runtime_config", {})
        attempts = max(1, int(runtime_config.get("max_retry", self._settings.openai_image_retry_attempts)) + 1)
        model = metadata.get("model") or runtime_config.get("default_image_model") or self._settings.openai_image_model or "gpt-image-2"
        retryable_errors = (RateLimitError, APIConnectionError, APITimeoutError)
        for attempt in range(attempts):
            try:
                async with self._api_limiter.slot():
                    return await asyncio.to_thread(self._generate_one, job_id, prompt, has_model_reference, model)
            except Exception as exc:
                if attempt >= attempts - 1 or not is_retryable_openai_error(exc):
                    raise
                delay = min(2 ** attempt, 12) + random.uniform(0, 0.75)
                logger.warning(
                    "Retrying OpenAI image job=%s attempt=%d/%d delay_seconds=%.2f error=%s",
                    job_id,
                    attempt + 1,
                    attempts - 1,
                    delay,
                    str(exc)[:300],
                )
                await asyncio.sleep(delay)
        raise RuntimeError("OpenAI image generation retry loop exited unexpectedly.")

    def _generate_one(self, job_id: str, prompt: str, has_model_reference: bool, model: str) -> bytes:
        is_explicit = model in {"gpt-image-1", "dall-e-2"} or self._settings.openai_image_model in {"gpt-image-1", "dall-e-2"}
        if ("gpt-image-1" in model or "dall-e-2" in model) and not is_explicit:
            raise AppError("invalid_openai_model", f"Fallback to {model} is disabled. Default model is gpt-image-2.", 500)
        client = OpenAI(api_key=self._settings.openai_api_key)
        input_dir = IMAGE_JOB_STORAGE_DIR / job_id / "input"
        image_paths = [input_dir / "front.jpg", input_dir / "back.jpg"]
        if has_model_reference:
            image_paths.append(input_dir / "model.jpg")

        files = [path.open("rb") for path in image_paths if path.exists()]
        try:
            request_args: dict[str, Any] = {
                "model": model,
                "image": files,
                "prompt": prompt,
                "size": "1024x1536",
                "quality": "medium",
                "n": 1,
            }
            # GPT image models return base64 image data by default and reject response_format.
            if "gpt-image" in model.lower():
                request_args["output_format"] = "jpeg"
            else:
                request_args["response_format"] = "b64_json"
            response = client.images.edit(**request_args)
        finally:
            for file in files:
                file.close()
        item = response.data[0]
        if getattr(item, "b64_json", None):
            return base64.b64decode(item.b64_json)
        elif getattr(item, "url", None):
            import httpx
            with httpx.Client(timeout=60.0) as http_client:
                r = http_client.get(item.url)
                r.raise_for_status()
                return r.content
        raise RuntimeError("OpenAI did not return image bytes or URL.")

    @staticmethod
    def _prepare_reference_image(content: bytes, output_path: Path) -> None:
        from io import BytesIO

        image = Image.open(BytesIO(content))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="JPEG", quality=88, optimize=True)

    @staticmethod
    def _attach_to_draft(db: Session, state: dict[str, Any], images: list[dict[str, Any]]) -> None:
        draft = db.get(CardDraft, int(state["draft_id"]))
        if not draft or draft.user_id != int(state["user_id"]):
            raise RuntimeError("Draft was not found for generated image attachment.")
        payload = json.loads(json.dumps(draft.card_payload or []))
        variant_index = int(state.get("variant_index") or 0)
        if not payload or not payload[0].get("variants") or variant_index >= len(payload[0]["variants"]):
            raise RuntimeError("Draft variant was not found for generated image attachment.")
        variant = payload[0]["variants"][variant_index]
        media = variant.get("media") or {}
        existing_items = list(media.get("local_files") or [])
        start_number = len(existing_items) + 1
        new_items = [
            {
                "photoNumber": start_number + index,
                "imageId": image.get("image_id"),
                "fileName": image["fileName"],
                "url": image["url"],
                "imageJobId": state["id"],
                "generated": True,
                "pose": image.get("pose"),
                "output_type": image.get("output_type"),
                "validation_status": ((image.get("validation_result") or {}).get("validation_status")),
                "can_use_for_listing": ((image.get("validation_result") or {}).get("can_use_for_listing")),
            }
            for index, image in enumerate(images)
        ]
        media["local_files"] = existing_items + new_items
        media["cover"] = media.get("cover") or new_items[0]["url"]
        variant["media"] = media
        draft.card_payload = payload
        db.commit()

    async def _save_state(self, job_id: str, state: dict[str, Any]) -> None:
        await self._redis.set(self._key(job_id), json.dumps(state, ensure_ascii=False), ex=60 * 60 * 24)

    async def _release_job_locks(self, state: dict[str, Any]) -> None:
        for key_name in ("lock_key", "store_lock_key"):
            if state.get(key_name):
                await self._redis.delete(str(state[key_name]))

    async def _load_state(self, job_id: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._key(job_id))
        if not raw:
            return None
        return json.loads(raw)

    @staticmethod
    def _public_state(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": state.get("id"),
            "status": state.get("status"),
            "step": state.get("step"),
            "progress": int(state.get("progress") or 0),
            "total": int(state.get("total") or 0),
            "variant_id": state.get("variant_id"),
            "images": state.get("images") or [],
            "error": state.get("error"),
            "job_type": state.get("job_type"),
            "queue_name": state.get("queue_name"),
            "credit_cost": int(state.get("credit_cost") or 0),
            "failed_validations": state.get("failed_validations") or [],
            "quality_report": state.get("quality_report"),
            "seller_warning": state.get("seller_warning"),
            "final_validation_status": state.get("final_validation_status"),
            "validation_summary": state.get("validation_summary"),
            "openai_calls_metadata": state.get("openai_calls_metadata"),
            "quality_check_enabled": state.get("quality_check_enabled"),
        }

    @staticmethod
    def _key(job_id: str) -> str:
        return f"image_generation_job:{job_id}"

    @staticmethod
    def _lock_key(user_id: int, draft_id: int, variant_id: str) -> str:
        return f"image_generation_lock:{user_id}:{draft_id}:{variant_id}"

    @staticmethod
    def _store_lock_key(store_id: int) -> str:
        return f"image_generation_store_lock:{store_id}"

    def _persist_job_record(self, db: Session, state: dict[str, Any]) -> None:
        if db is None:
            return
        metadata = state.get("metadata") or {}
        runtime_config = metadata.get("runtime_config") or {}
        model_id = state.get("model_id")
        if model_id in {"custom", "none", "auto_russian_model", ""}:
            model_id = None

        db.add(
            GeneratedImageJob(
                id=str(state["id"]),
                user_id=int(state["user_id"]),
                store_id=int(state["store_id"]) if state.get("store_id") is not None else None,
                draft_id=int(state["draft_id"]) if state.get("draft_id") is not None else None,
                job_type=str(state.get("job_type") or "gpt_image"),
                status="pending",
                step=str(state.get("step") or "queued"),
                model_id=model_id,
                ai_model=metadata.get("model") or runtime_config.get("default_image_model") or self._default_ai_model(str(state.get("job_type") or "")),
                style=metadata.get("style") or metadata.get("background_style"),
                quantity=int(state.get("total") or 1),
                garment_json=metadata.get("garment_json") or {},
                validation_result={},
                generation_prompt=None,
                prompt=None,
                pose=((metadata.get("override_tasks") or [{}])[0] or {}).get("pose"),
                output_type=metadata.get("output_type"),
                metadata_json=metadata,
                images=[],
                queue_name=str(state.get("queue_name") or IMAGE_JOB_QUEUE_NORMAL),
                credit_cost=max(0, int(state.get("credit_cost") or 0)),
            )
        )
        db.commit()

    def _update_job_record(self, db: Session, state: dict[str, Any]) -> None:
        if db is None:
            return
        self._sync_job_from_state(db, str(state["id"]), state)

    def _sync_job_from_state(self, db: Session, job_id: str, state: dict[str, Any]) -> None:
        if db is None:
            return
        job = db.get(GeneratedImageJob, job_id)
        if not job:
            return
        metadata = state.get("metadata") or {}
        runtime_config = metadata.get("runtime_config") or {}
        images = list(state.get("images") or [])
        validation_result = {
            "failed_validations": list(state.get("failed_validations") or []),
            "quality_report": state.get("quality_report"),
            "seller_warning": state.get("seller_warning"),
            "final_validation_status": state.get("final_validation_status"),
            "validation_summary": state.get("validation_summary"),
            "openai_calls_metadata": state.get("openai_calls_metadata"),
        }
        prompt = images[0].get("prompt") if images else job.prompt
        primary_image = images[0] if images else {}
        job.status = self._normalize_status(str(state.get("status") or "pending"))
        job.step = str(state.get("step") or job.step)
        job.ai_model = metadata.get("model") or runtime_config.get("default_image_model") or job.ai_model or self._default_ai_model(str(state.get("job_type") or ""))
        job.style = metadata.get("style") or metadata.get("background_style") or job.style
        job.quantity = int(state.get("total") or job.quantity or 1)
        job.garment_json = metadata.get("garment_json") or job.garment_json or {}
        job.validation_result = validation_result
        job.generation_prompt = prompt
        job.prompt = prompt
        job.pose = primary_image.get("pose") or ((metadata.get("override_tasks") or [{}])[0] or {}).get("pose") or job.pose
        job.output_type = primary_image.get("output_type") or metadata.get("output_type") or job.output_type
        job.error_message = state.get("error")
        job.metadata_json = metadata
        job.images = images
        job.estimated_cost = self._estimate_cost(job.ai_model, job.quantity)
        job.queue_name = str(state.get("queue_name") or job.queue_name or IMAGE_JOB_QUEUE_NORMAL)
        job.credit_cost = max(0, int(state.get("credit_cost") or job.credit_cost or 0))
        if job.status in {"completed", "completed_with_warnings"}:
            job.completed_at = datetime.now(timezone.utc)
            self._ensure_usage_record(db, job)
        db.commit()

    def _ensure_usage_record(self, db: Session, job: GeneratedImageJob) -> None:
        existing = db.get(UsageRecord, job.id)
        if existing:
            existing.provider = self._provider_for_model(job.ai_model or "")
            existing.model = job.ai_model or "unknown"
            existing.operation = "image_generation"
            existing.quantity = job.quantity
            existing.estimated_cost = job.estimated_cost
            db.commit()
            return
        db.add(
            UsageRecord(
                id=job.id,
                user_id=job.user_id,
                job_id=job.id,
                provider=self._provider_for_model(job.ai_model or ""),
                model=job.ai_model or "unknown",
                operation="image_generation",
                quantity=job.quantity,
                estimated_cost=job.estimated_cost,
            )
        )
        user = db.get(User, job.user_id)
        if user:
            user.used_quota = max(0, int(user.used_quota or 0) + int(job.quantity or 0))
            user.used_cost = round(float(user.used_cost or 0.0) + float(job.estimated_cost or 0.0), 4)
            if job.credit_cost > 0 and job.credits_consumed_at is None:
                user.credit_balance = max(0, int(user.credit_balance or 0) - int(job.credit_cost or 0))
                user.credits_used = max(0, int(user.credits_used or 0) + int(job.credit_cost or 0))
                job.credits_consumed_at = datetime.now(timezone.utc)
                record_credit_transaction(
                    db,
                    user=user,
                    transaction_type="consume",
                    credits=-int(job.credit_cost or 0),
                    balance_after=int(user.credit_balance or 0),
                    job_id=job.id,
                    description="Credits consumed after successful image generation",
                    metadata={"job_type": job.job_type, "queue_name": job.queue_name},
                )
                log_platform_audit(
                    db,
                    action="CREDIT_CONSUME",
                    target_type="image_job",
                    target_id=job.id,
                    metadata={"user_id": user.id, "credits": int(job.credit_cost or 0), "queue_name": job.queue_name},
                )
        db.commit()

    @staticmethod
    def _normalize_status(status: str) -> str:
        return {"queued": "pending", "processing": "running"}.get(status, status)

    def _default_ai_model(self, job_type: str) -> str:
        if job_type in {"try_on", "gpt_image"}:
            return self._settings.fal_gpt_image_model or "gpt-image-2"
        return self._settings.openai_image_model or "gpt-image-2"

    @staticmethod
    def _provider_for_model(model: str) -> str:
        model_lower = model.lower()
        if "gemini" in model_lower:
            return "gemini"
        if "fal" in model_lower:
            return "fal"
        return "openai"

    def _estimate_cost(self, model: str | None, quantity: int) -> float:
        model_name = (model or "").lower()
        per_image = 0.05 if "gpt-image" in model_name else 0.03
        if "gemini" in model_name:
            per_image = 0.01
        return round(max(1, quantity) * per_image, 4)

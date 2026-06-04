import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import httpx
import fal_client
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.services.image_storage import ImageStorage
from app.services.gpt_prompt_builder import GPTPromptBuilder
from app.services.garment_validator import GarmentValidator

logger = logging.getLogger(__name__)

IMAGE_JOB_STORAGE_DIR = Path("storage/image_jobs")


def _classify_validation_result(val_res: dict[str, Any], retry_used: bool) -> dict[str, Any]:
    validation_score = int(val_res.get("validation_score", round(float(val_res.get("score", 0.0)) * 100)))
    critical_mismatch = bool(val_res.get("critical_mismatch"))
    wrong_garment_type = bool(val_res.get("wrong_garment_type"))
    wrong_garment_area = bool(val_res.get("wrong_garment_area"))
    missing_core_identity = bool(val_res.get("missing_core_identity"))

    if validation_score < 50 or critical_mismatch or wrong_garment_type or wrong_garment_area or missing_core_identity:
        validation_status = "failed"
        risk_level = "high"
        can_use_for_listing = False
    elif validation_score >= 85 and not critical_mismatch:
        validation_status = "approved"
        risk_level = "low"
        can_use_for_listing = True
    elif validation_score >= 70:
        validation_status = "warning"
        risk_level = "medium"
        can_use_for_listing = True
    elif validation_score >= 50:
        validation_status = "review_required"
        risk_level = "medium"
        can_use_for_listing = True
    else:
        validation_status = "failed"
        risk_level = "high"
        can_use_for_listing = False

    warning_messages = list(dict.fromkeys([
        *[str(item) for item in val_res.get("warnings", []) if str(item).strip()],
        *[str(item) for item in val_res.get("issues", []) if str(item).strip()],
        *[str(item) for item in val_res.get("realism_issues", []) if str(item).strip()],
    ]))

    if validation_status == "failed":
        high_risk_message = "High risk: not recommended for publishing."
        if high_risk_message not in warning_messages:
            warning_messages.append(high_risk_message)

    return {
        "validation_status": validation_status,
        "validation_score": max(0, min(validation_score, 100)),
        "risk_level": risk_level,
        "warnings": warning_messages,
        "dominant_delta_e": val_res.get("dominant_color_delta_e"),
        "palette_delta_e": val_res.get("palette_delta_e"),
        "missing_details": list(val_res.get("missing_details") or []),
        "can_use_for_listing": can_use_for_listing,
        "retry_used": retry_used,
        "critical_mismatch": critical_mismatch,
        "wrong_garment_type": wrong_garment_type,
        "wrong_garment_area": wrong_garment_area,
        "missing_core_identity": missing_core_identity,
    }


def _build_validation_summary(images: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"approved": 0, "warning": 0, "review_required": 0, "failed": 0}
    for image in images:
        status = ((image.get("validation_result") or {}).get("validation_status") or "").strip().lower()
        if status in counts:
            counts[status] += 1
    return {
        "total_images": len(images),
        "approved_count": counts["approved"],
        "warning_count": counts["warning"],
        "review_required_count": counts["review_required"],
        "failed_count": counts["failed"],
    }


def file_to_data_uri(path: Path) -> str:
    import base64
    with open(path, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode("utf-8")
    mime = "image/jpeg" if path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
    return f"data:{mime};base64,{encoded}"


class GPTImageCatalogService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._storage = ImageStorage(settings)
        model_env = os.getenv("FAL_GPT_IMAGE_MODEL")
        if model_env:
            self._model = model_env
        else:
            self._model = settings.fal_gpt_image_model or "gpt-image-2"

        is_explicit = (model_env in {"gpt-image-1", "dall-e-2"}) or (settings.fal_gpt_image_model in {"gpt-image-1", "dall-e-2"})
        if ("gpt-image-1" in self._model or "dall-e-2" in self._model) and not is_explicit:
            raise AppError("invalid_image_model", f"Fallback to {self._model} is disabled. Default model is gpt-image-2.", 500)

        if settings.fal_key:
            os.environ["FAL_KEY"] = settings.fal_key

    async def run_gpt_image_job(
        self,
        job_id: str,
        db: Session,
        state: dict[str, Any],
        save_state_fn: Callable[[str, dict[str, Any]], Any],
        attach_draft_fn: Callable[[Session, dict[str, Any], list[dict[str, Any]]], Any],
        use_openai: bool = False,
    ) -> dict[str, Any]:
        if not use_openai and not self._settings.fal_key:
            raise AppError("missing_fal_key", "FAL_KEY is missing.", 500)
        elif use_openai and not self._settings.openai_api_key:
            raise AppError("missing_openai_key", "OPENAI_API_KEY is missing.", 500)

        # Mark job as processing
        state["status"] = "processing"
        state["step"] = "gpt_image_processing"
        state["progress"] = 0
        state.setdefault("failed_validations", [])
        state.setdefault("validation_summary", {})
        await save_state_fn(job_id, state)

        try:
            total = int(state.get("total") or 5)
            metadata = state.get("metadata") or {}
            runtime_config = metadata.get("runtime_config") or {}
            validation_threshold = int(runtime_config.get("validation_threshold", 85))
            realism_threshold = int(runtime_config.get("realism_threshold", 80))
            validation_failure_behavior = str(runtime_config.get("validation_failure_behavior") or "warn").lower()
            job_model = metadata.get("model")
            if job_model:
                self._model = job_model
                is_explicit = job_model in {"gpt-image-1", "dall-e-2"}
                if ("gpt-image-1" in self._model or "dall-e-2" in self._model) and not is_explicit:
                    raise AppError("invalid_image_model", f"Fallback to {self._model} is disabled. Default model is gpt-image-2.", 500)
            style = metadata.get("style") or "studio"
            garment_json = metadata.get("garment_json") or {}

            # Set up directories
            job_dir = IMAGE_JOB_STORAGE_DIR / job_id
            input_dir = job_dir / "input"
            output_dir = job_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            front_path = input_dir / "front.jpg"
            back_path = input_dir / "back.jpg"
            model_path = input_dir / "model.jpg"

            if not front_path.exists():
                raise AppError("missing_front_image", "Front product image is missing from storage.", 400)

            has_back_image = back_path.exists()
            has_model_image = model_path.exists()
            source_front_bytes = front_path.read_bytes()
            source_back_bytes = back_path.read_bytes() if has_back_image else None

            auto_model_generation = bool(metadata.get("auto_model_generation")) and use_openai

            if not has_model_image and not auto_model_generation:
                raise AppError("missing_model_reference", "Please select a real model reference before generating catalog images.", 400)

            if not use_openai:
                # Upload reference images once to Fal CDN instead of base64 encoding
                state["step"] = "uploading_inputs"
                await save_state_fn(job_id, state)

                front_url = await asyncio.to_thread(fal_client.upload_file, front_path)
                back_url = await asyncio.to_thread(fal_client.upload_file, back_path) if has_back_image else None
                model_url = await asyncio.to_thread(fal_client.upload_file, model_path) if has_model_image else None
            else:
                front_url = back_url = model_url = None

            # Build tasks based on simplified quantity strategy
            tasks_to_run = list(metadata.get("override_tasks") or self.build_tasks(total, has_back_image))
            state["total"] = len(tasks_to_run)
            await save_state_fn(job_id, state)

            generated_by_index = {}
            approved_items = {}
            progress_lock = asyncio.Lock()
            semaphore = asyncio.Semaphore(3)
            validator = GarmentValidator(self._settings)
            seller_warning = None

            async def run_one_task(idx: int, task: dict[str, Any]) -> dict[str, Any]:
                nonlocal seller_warning
                async with semaphore:
                    pose = task["pose"]
                    task_type = task["type"]
                    label = task["label"]
                    output_type = task.get("output_type") or "catalog"
                    validation_pose = task.get("validation_pose")

                    logger.info("Processing task %d/%d: %s (%s)", idx + 1, len(tasks_to_run), label, pose)

                    # Initialize prompt
                    if task_type == "detail":
                        prompt = (
                            "Create a professional ecommerce garment detail shot using the uploaded product and model references.\n\n"
                            "Focus tightly on the product while it is worn naturally by the same model.\n\n"
                            "Preserve exact product color, fabric texture, logo/text, seams, pockets and closures.\n\n"
                            "Clean studio background.\n\n"
                            "Do not change the product design.\n\n"
                            "Do not invent new text or logos.\n\n"
                            "The image must look like a real ecommerce product photograph taken with a real camera.\n"
                            "No CGI.\n"
                            "No 3D render.\n"
                            "No cartoon.\n"
                            "No illustration."
                        )
                    else:
                        prompt = GPTPromptBuilder.build_prompt(garment_json, style, pose, has_model_reference=has_model_image)

                    # Clean cinematic wording
                    prompt = GPTPromptBuilder.clean_cinematic_wording(prompt)

                    # Update step for progress visibility
                    async with progress_lock:
                        state["step"] = f"generating_{pose}"
                        await save_state_fn(job_id, state)

                    image_urls = []
                    if model_url:
                        image_urls.append(model_url)
                    image_urls.append(front_url)
                    if back_url:
                        image_urls.append(back_url)

                    image_paths = [front_path]
                    if has_model_image:
                        image_paths.insert(0, model_path)
                    if has_back_image:
                        image_paths.append(back_path)

                    # Setup image references and generate
                    if use_openai:
                        image_bytes = await self._generate_with_openai_retry(
                            image_paths,
                            prompt,
                            job_model,
                            int(runtime_config.get("max_retry", self._settings.openai_image_retry_attempts)),
                        )
                    else:
                        image_bytes, fal_url = await self._generate_with_fal(image_urls, prompt)

                    # Validate image (run in thread pool to avoid blocking)
                    val_res = await asyncio.to_thread(
                        validator.validate_image,
                        image_bytes,
                        garment_json,
                        validation_pose,
                        source_front_bytes,
                        source_back_bytes,
                        validation_threshold=validation_threshold,
                        realism_threshold=realism_threshold,
                    )
                    realism_score = val_res.get("realism_score", 100)
                    logger.info("Validation result for %s: passed=%s, score=%f, realism_score=%s", pose, val_res["passed"], val_res["score"], realism_score)

                    retry_used = False
                    retry_prompt = None
                    is_unrealistic = realism_score < realism_threshold
                    is_inconsistent = not val_res["passed"]
                    # Catalog generation should always get one strict fidelity retry when validation fails.
                    needs_retry = is_unrealistic or is_inconsistent

                    if needs_retry:
                        logger.warning("Validation or realism check failed for pose %s (realism_score: %s, passed: %s). Retrying once with stronger prompt...", pose, realism_score, val_res["passed"])
                        retry_used = True
                        # Record the first failed attempt
                        async with progress_lock:
                            failed_reasons = val_res.get("issues", []) + val_res.get("realism_issues", [])
                            state["failed_validations"].append({
                                "failed_pose": pose,
                                "failed_reason": ", ".join(failed_reasons),
                                "validation_score": val_res.get("validation_score", int(round(float(val_res["score"]) * 100))),
                                "realism_score": realism_score,
                                "retry_used": False,
                                "output_type": output_type,
                            })
                            await save_state_fn(job_id, state)

                        # Determine retry prompt
                        if is_unrealistic:
                            # Use stronger realism prompt
                            retry_prompt = GPTPromptBuilder.build_strong_realism_prompt(
                                garment_json=garment_json,
                                style=style,
                                pose=pose
                            )
                        else:
                            if garment_json.get("complex_product_mode"):
                                retry_prompt = GPTPromptBuilder.build_complex_retry_prompt(
                                    garment_json,
                                    val_res.get("issues", []) + val_res.get("missing_details", []),
                                    garment_json.get("special_details", []) + garment_json.get("must_preserve", []),
                                )
                            else:
                                # Build stricter consistency prompt
                                retry_prompt = GPTPromptBuilder.build_prompt(
                                    garment_json,
                                    style,
                                    pose,
                                    strict_retry_fields=val_res.get("failed_fields", []),
                                    has_model_reference=has_model_image
                                )

                        # Clean cinematic wording from retry prompt
                        retry_prompt = GPTPromptBuilder.clean_cinematic_wording(retry_prompt)

                        # Retry generate
                        if use_openai:
                            image_bytes = await self._generate_with_openai_retry(
                                image_paths,
                                retry_prompt,
                                job_model,
                                int(runtime_config.get("max_retry", self._settings.openai_image_retry_attempts)),
                            )
                        else:
                            image_bytes, fal_url = await self._generate_with_fal(image_urls, retry_prompt)

                        # Re-validate
                        val_res = await asyncio.to_thread(
                            validator.validate_image,
                            image_bytes,
                            garment_json,
                            validation_pose,
                            source_front_bytes,
                            source_back_bytes,
                            validation_threshold=validation_threshold,
                            realism_threshold=realism_threshold,
                        )
                        realism_score = val_res.get("realism_score", 100)
                        logger.info("Validation retry result for %s: passed=%s, score=%f, realism_score=%s", pose, val_res["passed"], val_res["score"], realism_score)

                    # Save the image (either passed, or the best retry attempt if failed)
                    file_name = f"generated-{idx + 1:02d}.jpg"
                    out_path = output_dir / file_name
                    storage_res = await asyncio.to_thread(
                        self._storage.save_generated_image,
                        job_id=job_id,
                        file_name=file_name,
                        content=image_bytes,
                        local_path=out_path
                    )
                    
                    item = {
                        "image_id": uuid4().hex,
                        "fileName": file_name,
                        "url": storage_res["url"],
                        "storage": storage_res["storage"],
                        "storageKey": storage_res["storageKey"],
                        "bytes": storage_res["bytes"],
                        "width": storage_res.get("width"),
                        "height": storage_res.get("height"),
                        "prompt": prompt,
                        "label": label,
                        "pose": pose,
                        "task_type": task_type,
                        "output_type": output_type,
                        "style": style,
                        "validation_result": {
                            **val_res,
                            "retry_prompt": retry_prompt,
                        }
                    }
                    validation_result = item["validation_result"]
                    validation_result.update(_classify_validation_result(validation_result, retry_used))
                    validation_result["image_id"] = item["image_id"]
                    validation_result["pose"] = pose
                    validation_result["label"] = label

                    async with progress_lock:
                        if validation_result["validation_status"] in {"warning", "review_required", "failed"}:
                            seller_warning = (
                                "This product contains complex details such as rhinestones, rips or distressing. "
                                "AI could not preserve them accurately. Please review or use a simpler catalog mode."
                            ) if garment_json.get("complex_product_mode") else (
                                "AI could not preserve the product accurately enough. Please review the result."
                            )
                        if validation_result["validation_status"] == "failed":
                            logger.warning("Validation failed for pose %s after retry=%s. Marking image high risk.", pose, retry_used)
                            failed_reasons = validation_result.get("warnings", [])
                            state["failed_validations"].append({
                                "image_id": item["image_id"],
                                "failed_pose": pose,
                                "failed_reason": ", ".join(failed_reasons),
                                "validation_score": validation_result["validation_score"],
                                "realism_score": realism_score,
                                "retry_used": retry_used,
                                "dominant_delta_e": validation_result.get("dominant_delta_e"),
                                "palette_delta_e": validation_result.get("palette_delta_e"),
                                "missing_details": validation_result.get("missing_details", []),
                                "complex_product_mode": val_res.get("complex_product_mode", False),
                                "retry_prompt": retry_prompt,
                                "final_validation_status": validation_result.get("validation_status", "failed"),
                                "output_type": output_type,
                            })
                        if validation_result["can_use_for_listing"]:
                            approved_items[idx] = item

                        generated_by_index[idx] = item
                        state["images"] = [generated_by_index[i] for i in sorted(generated_by_index)]
                        state["progress"] = len(generated_by_index)
                        state["validation_summary"] = _build_validation_summary(state["images"])
                        await save_state_fn(job_id, state)

                    return item

            # Execute all tasks concurrently
            async_tasks = [asyncio.create_task(run_one_task(idx, t)) for idx, t in enumerate(tasks_to_run)]
            await asyncio.gather(*async_tasks)

            # Order final images list
            ordered_images = [generated_by_index[idx] for idx in range(len(tasks_to_run))]
            approved_images = [approved_items[idx] for idx in sorted(approved_items)]
            summary = _build_validation_summary(ordered_images)
            has_failed = summary["failed_count"] > 0
            has_warnings = summary["warning_count"] > 0 or summary["review_required_count"] > 0 or has_failed
            state["validation_summary"] = summary
            state["seller_warning"] = seller_warning
            state["final_validation_status"] = "failed" if has_failed else "review_required" if summary["review_required_count"] > 0 else "warning" if summary["warning_count"] > 0 else "approved"

            if validation_failure_behavior == "block" and has_failed:
                state["status"] = "failed_validation"
                state["step"] = "failed_validation"
                state["error"] = seller_warning
            else:
                attach_draft_fn(db, state, approved_images if validation_failure_behavior == "block" else ordered_images)
                state["status"] = "completed_with_warnings" if has_warnings else "completed"
                state["step"] = state["status"]
                state["error"] = seller_warning if has_warnings else None
            await save_state_fn(job_id, state)

            return {
                "id": job_id,
                "status": state["status"],
                "step": state["step"],
                "progress": len(tasks_to_run),
                "total": len(tasks_to_run),
                "images": ordered_images,
                "error": state.get("error")
            }

        except Exception as exc:
            logger.exception("GPT-Image catalog job failed: %s", job_id)
            state["status"] = "failed"
            state["step"] = "failed"
            state["error"] = str(exc)[:2000]
            await save_state_fn(job_id, state)
            raise

    async def _generate_with_fal(self, image_urls: list[str], prompt: str) -> tuple[bytes, str]:
        arguments = {
            "image_urls": image_urls,
            "prompt": prompt,
            "quality": "medium"
        }
        res = await fal_client.run_async(
            self._model,
            arguments=arguments
        )
        # Extract image URL
        img_url = None
        if "image" in res and isinstance(res["image"], dict) and "url" in res["image"]:
            img_url = res["image"]["url"]
        elif "images" in res and isinstance(res["images"], list) and len(res["images"]) > 0:
            img_url = res["images"][0]["url"]

        if not img_url:
            raise RuntimeError(f"FAL GPT-Image response did not contain image URL. Response: {res}")

        # Download image content
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(img_url)
            r.raise_for_status()
            image_bytes = r.content

        return image_bytes, img_url

    @staticmethod
    def build_tasks(quantity: int, has_back_image: bool) -> list[dict[str, Any]]:
        back_task = (
            {
                "pose": "back",
                "type": "catalog",
                "label": "Back View",
                "output_type": "catalog",
                "validation_pose": "back",
            }
            if has_back_image
            else {
                "pose": "detail",
                "type": "detail",
                "label": "Detail Shot",
                "output_type": "detail",
                "validation_pose": None,
            }
        )
        if quantity == 1:
            return [
                {"pose": "front", "type": "catalog", "label": "Front Catalog", "output_type": "catalog", "validation_pose": "front"},
            ]
        if quantity == 3:
            return [
                {"pose": "front", "type": "catalog", "label": "Front Catalog", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "side_45", "type": "catalog", "label": "Side 45 Catalog", "output_type": "catalog", "validation_pose": "side_45"},
                {"pose": "hand_on_hip", "type": "catalog", "label": "Hand On Hip Catalog", "output_type": "catalog", "validation_pose": "hand_on_hip"},
            ]
        if quantity == 5:
            return [
                {"pose": "front", "type": "catalog", "label": "Front Catalog", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "side_45", "type": "catalog", "label": "Side 45 Catalog", "output_type": "catalog", "validation_pose": "side_45"},
                {"pose": "walking", "type": "catalog", "label": "Walking Lifestyle", "output_type": "lifestyle", "validation_pose": "walking"},
                back_task,
                {"pose": "hand_on_hip", "type": "catalog", "label": "Hand On Hip Catalog", "output_type": "catalog", "validation_pose": "hand_on_hip"},
            ]
        return [
            {"pose": "front", "type": "catalog", "label": "Front Catalog", "output_type": "catalog", "validation_pose": "front"},
            {"pose": "side_45", "type": "catalog", "label": "Side 45 Catalog", "output_type": "catalog", "validation_pose": "side_45"},
            {"pose": "walking", "type": "catalog", "label": "Walking Lifestyle", "output_type": "lifestyle", "validation_pose": "walking"},
            back_task,
            {"pose": "hand_on_hip", "type": "catalog", "label": "Hand On Hip Catalog", "output_type": "catalog", "validation_pose": "hand_on_hip"},
            {"pose": "sitting", "type": "catalog", "label": "Sitting Lifestyle", "output_type": "lifestyle", "validation_pose": "sitting"},
        ]

    async def _generate_with_openai_retry(self, image_paths: list[Path], prompt: str, job_model: str | None = None, max_retry: int | None = None) -> bytes:
        attempts = max(1, int(max_retry if max_retry is not None else self._settings.openai_image_retry_attempts) + 1)
        from openai import APIConnectionError, APITimeoutError, RateLimitError
        retryable_errors = (RateLimitError, APIConnectionError, APITimeoutError)
        import random
        for attempt in range(attempts):
            try:
                return await asyncio.to_thread(self._generate_with_openai, image_paths, prompt, job_model)
            except retryable_errors:
                if attempt >= attempts - 1:
                    raise
                delay = min(2 ** attempt, 12) + random.uniform(0, 0.75)
                await asyncio.sleep(delay)
        raise RuntimeError("OpenAI image generation retry loop exited unexpectedly.")

    def _generate_with_openai(self, image_paths: list[Path], prompt: str, job_model: str | None = None) -> bytes:
        from openai import OpenAI
        import base64
        model = job_model or self._settings.openai_image_model or "gpt-image-2"
        is_explicit = (self._settings.openai_image_model in {"gpt-image-1", "dall-e-2"}) or (job_model in {"gpt-image-1", "dall-e-2"})
        if ("gpt-image-1" in model or "dall-e-2" in model) and not is_explicit:
            raise AppError("invalid_openai_model", f"Fallback to {model} is disabled. Default model is gpt-image-2.", 500)
        client = OpenAI(api_key=self._settings.openai_api_key)
        files = [path.open("rb") for path in image_paths if path.exists()]
        try:
            request_args = {
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

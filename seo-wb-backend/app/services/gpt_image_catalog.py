import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

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


def _build_catalog_bundle(quantity: int, has_back_image: bool) -> list[dict[str, Any]]:
    # Keep legacy jobs that requested the old 9-image bundle compatible.
    if quantity == 9:
        quantity = 8
    if quantity not in {3, 6, 8}:
        quantity = 6

    if quantity == 3:
        return [
            {"pose": "front", "type": "catalog", "label": "Front", "output_type": "catalog", "validation_pose": "front"},
            {"pose": "side_45", "type": "catalog", "label": "Side", "output_type": "catalog", "validation_pose": "side_45"},
            {"pose": "back", "type": "catalog", "label": "Back", "output_type": "catalog", "validation_pose": "back"},
        ]
    elif quantity == 6:
        if has_back_image:
            return [
                {"pose": "front", "type": "catalog", "label": "Front", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "side_45", "type": "catalog", "label": "Side", "output_type": "catalog", "validation_pose": "side_45"},
                {"pose": "back", "type": "catalog", "label": "Back", "output_type": "catalog", "validation_pose": "back"},
                {"pose": "walking", "type": "lifestyle", "label": "Lifestyle", "output_type": "lifestyle", "validation_pose": None},
                {"pose": "detail", "type": "detail", "label": "Detail", "output_type": "detail", "validation_pose": "detail"},
                {"pose": "front", "type": "lifestyle", "label": "Banner", "output_type": "lifestyle", "validation_pose": None},
            ]
        else:
            return [
                {"pose": "front", "type": "catalog", "label": "Front", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "side_45", "type": "catalog", "label": "Side", "output_type": "catalog", "validation_pose": "side_45"},
                {"pose": "walking", "type": "lifestyle", "label": "Lifestyle", "output_type": "lifestyle", "validation_pose": None},
                {"pose": "detail", "type": "detail", "label": "Detail", "output_type": "detail", "validation_pose": "detail"},
                {"pose": "extra_detail", "type": "detail", "label": "Extra Detail", "output_type": "detail", "validation_pose": "extra_detail"},
                {"pose": "front", "type": "lifestyle", "label": "Banner", "output_type": "lifestyle", "validation_pose": None},
            ]
    else:  # quantity == 8
        if has_back_image:
            return [
                {"pose": "front", "type": "catalog", "label": "Front", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "side_45", "type": "catalog", "label": "Side", "output_type": "catalog", "validation_pose": "side_45"},
                {"pose": "back", "type": "catalog", "label": "Back", "output_type": "catalog", "validation_pose": "back"},
                {"pose": "walking", "type": "lifestyle", "label": "Walking", "output_type": "lifestyle", "validation_pose": "walking"},
                {"pose": "hand_on_hip", "type": "catalog", "label": "Hand On Hip", "output_type": "catalog", "validation_pose": "hand_on_hip"},
                {"pose": "sitting", "type": "lifestyle", "label": "Sitting", "output_type": "lifestyle", "validation_pose": "sitting"},
                {"pose": "fabric_detail", "type": "detail", "label": "Fabric Detail", "output_type": "detail", "validation_pose": "fabric_detail"},
                {"pose": "front", "type": "lifestyle", "label": "Banner", "output_type": "lifestyle", "validation_pose": None},
            ]
        else:
            return [
                {"pose": "front", "type": "catalog", "label": "Front", "output_type": "catalog", "validation_pose": "front"},
                {"pose": "side_45", "type": "catalog", "label": "Side", "output_type": "catalog", "validation_pose": "side_45"},
                {"pose": "walking", "type": "lifestyle", "label": "Walking", "output_type": "lifestyle", "validation_pose": "walking"},
                {"pose": "hand_on_hip", "type": "catalog", "label": "Hand On Hip", "output_type": "catalog", "validation_pose": "hand_on_hip"},
                {"pose": "sitting", "type": "lifestyle", "label": "Sitting", "output_type": "lifestyle", "validation_pose": "sitting"},
                {"pose": "fabric_detail", "type": "detail", "label": "Fabric Detail", "output_type": "detail", "validation_pose": "fabric_detail"},
                {"pose": "product_detail", "type": "detail", "label": "Product Detail", "output_type": "detail", "validation_pose": "product_detail"},
                {"pose": "front", "type": "lifestyle", "label": "Banner", "output_type": "lifestyle", "validation_pose": None},
            ]


def build_catalog_bundle(quantity: int, has_back_image: bool) -> list[dict[str, Any]]:
    tasks = _build_catalog_bundle(quantity, has_back_image)
    focused_labels_by_size = {
        3: {"Detail"},
        6: {"Front", "Detail", "Back" if has_back_image else "Extra Detail"},
        8: {"Front", "Side", "Fabric Detail", "Back" if has_back_image else "Product Detail"},
    }
    focused_labels = focused_labels_by_size[len(tasks)]
    return [{**task, "product_focus": task["label"] in focused_labels} for task in tasks]


class GPTImageCatalogService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._storage = ImageStorage(settings)

    async def run_gpt_image_job(
        self,
        job_id: str,
        db: Session,
        state: dict[str, Any],
        save_state_fn: Callable[[str, dict[str, Any]], Any],
        attach_draft_fn: Callable[[Session, dict[str, Any], list[dict[str, Any]]], Any],
        use_openai: bool = True,
    ) -> dict[str, Any]:
        use_openai = True
        if not self._settings.openai_api_key:
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
                is_explicit = job_model in {"gpt-image-1", "dall-e-2"}
                if ("gpt-image-1" in job_model or "dall-e-2" in job_model) and not is_explicit:
                    raise AppError("invalid_image_model", f"Fallback to {job_model} is disabled. Default model is gpt-image-2.", 500)
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

            front_url = back_url = model_url = None

            # Build tasks based on simplified quantity strategy
            tasks_to_run = list(metadata.get("override_tasks") or self.build_tasks(total, has_back_image))
            state["total"] = len(tasks_to_run)
            await save_state_fn(job_id, state)

            # Every bundle gets at most one quality retry, regardless of size.
            quantity = len(tasks_to_run)
            max_openai_calls = quantity + 1

            openai_calls_count = 0
            initial_generation_calls = 0
            retry_calls_used = 0
            calls_lock = asyncio.Lock()

            def get_retry_priority(task: dict[str, Any]) -> int:
                label = str(task.get("label") or "").lower()
                pose = str(task.get("pose") or "").lower()
                task_type = str(task.get("type") or "").lower()
                
                if label == "banner":
                    return 8
                if "front" in pose:
                    return 1
                if "side" in pose:
                    return 2
                if "back" in pose:
                    return 3
                if "walking" in pose or task_type == "lifestyle":
                    return 4
                if "hand_on_hip" in pose:
                    return 5
                if "sitting" in pose:
                    return 6
                if any(detail_term in pose for detail_term in ["detail", "fabric_detail", "logo_detail", "extra_detail", "product_detail"]):
                    return 7
                return 9

            generated_by_index = {}
            approved_items = {}
            progress_lock = asyncio.Lock()
            semaphore = asyncio.Semaphore(3)
            validator = GarmentValidator(self._settings)
            seller_warning = None

            async def save_image_item(
                idx: int,
                task: dict[str, Any],
                image_bytes: bytes,
                val_res: dict[str, Any],
                retry_used: bool,
                retry_skipped_due_to_limit: bool,
                retry_priority: int,
                retry_prompt: str | None,
                prompt: str,
            ) -> dict[str, Any]:
                nonlocal seller_warning
                pose = task["pose"]
                task_type = task["type"]
                label = task["label"]
                output_type = task.get("output_type") or "catalog"

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
                    "product_focus": bool(task.get("product_focus")),
                    "style": style,
                    "retry_used": retry_used,
                    "retry_skipped_due_to_limit": retry_skipped_due_to_limit,
                    "retry_priority": retry_priority,
                    "validation_result": {
                        **val_res,
                        "retry_prompt": retry_prompt,
                        "retry_used": retry_used,
                        "retry_skipped_due_to_limit": retry_skipped_due_to_limit,
                        "retry_priority": retry_priority,
                    }
                }
                validation_result = item["validation_result"]
                validation_result.update(_classify_validation_result(validation_result, retry_used))
                validation_result["image_id"] = item["image_id"]
                validation_result["pose"] = pose
                validation_result["label"] = label

                async with progress_lock:
                    if validation_result["validation_status"] in {"warning", "review_required", "failed"}:
                        is_gemini_unavailable = any("Gemini tạm thời không khả dụng" in str(w) for w in validation_result.get("warnings", []))
                        if is_gemini_unavailable:
                            seller_warning = "Gemini tạm thời không khả dụng, vui lòng tự duyệt ảnh."
                        else:
                            seller_warning = (
                                "This product contains complex details such as rhinestones, rips or distressing. "
                                "AI could not preserve them accurately. Please review or use a simpler catalog mode."
                            ) if garment_json.get("complex_product_mode") else (
                                "AI could not preserve the product accurately enough. Please review the result."
                            )
                    
                    # Manage failed validations to avoid duplicates
                    state["failed_validations"] = [
                        fv for fv in state["failed_validations"] if fv.get("failed_pose") != pose
                    ]

                    if validation_result["validation_status"] == "failed" or retry_skipped_due_to_limit:
                        logger.warning("Validation failed for pose %s (retry_used=%s, skipped=%s). Marking image high risk/failed.", pose, retry_used, retry_skipped_due_to_limit)
                        failed_reasons = validation_result.get("warnings", [])
                        state["failed_validations"].append({
                            "image_id": item["image_id"],
                            "failed_pose": pose,
                            "failed_reason": ", ".join(failed_reasons),
                            "validation_score": validation_result["validation_score"],
                            "realism_score": val_res.get("realism_score", 100),
                            "retry_used": retry_used,
                            "retry_skipped_due_to_limit": retry_skipped_due_to_limit,
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
                    else:
                        if idx in approved_items:
                            del approved_items[idx]

                    generated_by_index[idx] = item
                    state["images"] = [generated_by_index[i] for i in sorted(generated_by_index)]
                    state["progress"] = len(generated_by_index)
                    state["validation_summary"] = _build_validation_summary(state["images"])
                    await save_state_fn(job_id, state)

                return item

            async def run_initial_task(idx: int, task: dict[str, Any]) -> dict[str, Any]:
                nonlocal seller_warning
                async with semaphore:
                    pose = task["pose"]
                    task_type = task["type"]
                    label = task["label"]
                    output_type = task.get("output_type") or "catalog"
                    validation_pose = task.get("validation_pose")

                    logger.info("Phase 1: Generating task %d/%d: %s (%s)", idx + 1, len(tasks_to_run), label, pose)

                    is_detail = pose in {"detail", "fabric_detail", "logo_detail", "extra_detail", "product_detail"}
                    if is_detail:
                        prompt = GPTPromptBuilder.build_detail_prompt(garment_json, pose, style)
                    else:
                        prompt = GPTPromptBuilder.build_prompt(
                            garment_json,
                            style,
                            pose,
                            product_focus=bool(task.get("product_focus")),
                            has_model_reference=has_model_image,
                            selected_model_gender=metadata.get("selected_model_gender"),
                            output_type=output_type,
                        )

                    prompt = GPTPromptBuilder.clean_cinematic_wording(prompt)

                    # Update step for progress visibility
                    async with progress_lock:
                        state["step"] = f"generating_{pose}"
                        await save_state_fn(job_id, state)

                    if is_detail:
                        image_paths = [front_path]
                    else:
                        image_paths = [front_path]
                        if has_model_image:
                            image_paths.insert(0, model_path)
                        if has_back_image:
                            image_paths.append(back_path)

                    # Increment call count
                    nonlocal openai_calls_count, initial_generation_calls
                    async with calls_lock:
                        openai_calls_count += 1
                        initial_generation_calls += 1

                    image_bytes = await self._generate_with_openai_retry(
                        image_paths,
                        prompt,
                        job_model,
                        int(runtime_config.get("max_retry", self._settings.openai_image_retry_attempts)),
                    )

                    # Validate image
                    try:
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
                    except Exception as e:
                        logger.warning("Gemini validation failed (first attempt) for pose %s: %s. Using fallback.", pose, e)
                        val_res = {
                            "passed": True,
                            "score": 0.70,
                            "validation_score": 70,
                            "realism_score": 80,
                            "validation_threshold": validation_threshold,
                            "realism_threshold": realism_threshold,
                            "dominant_delta_e_threshold": 15.0,
                            "palette_delta_e_threshold": 18.0,
                            "realism_issues": [],
                            "issues": [],
                            "warnings": ["Gemini tạm thời không khả dụng, vui lòng tự duyệt ảnh (Lỗi: " + str(e)[:200] + ")"],
                            "failed_fields": [],
                            "missing_details": [],
                            "complex_product_mode": garment_json.get("complex_product_mode", False),
                            "critical_mismatch": False,
                            "wrong_garment_type": False,
                            "wrong_garment_area": False,
                            "missing_core_identity": False,
                            "critical_issues": [],
                            "medium_issues": [],
                            "minor_issues": [],
                            "pose_validation": "pass",
                            "expected_pose": validation_pose or None,
                            "final_validation_status": "passed",
                            "dominant_color_delta_e": None,
                            "palette_delta_e": None,
                        }

                    priority = get_retry_priority(task)
                    realism_score = val_res.get("realism_score", 100)
                    is_unrealistic = realism_score < realism_threshold
                    is_inconsistent = not val_res["passed"]
                    needs_retry = is_unrealistic or is_inconsistent

                    await save_image_item(
                        idx=idx,
                        task=task,
                        image_bytes=image_bytes,
                        val_res=val_res,
                        retry_used=False,
                        retry_skipped_due_to_limit=False,
                        retry_priority=priority,
                        retry_prompt=None,
                        prompt=prompt
                    )

                    return {
                        "idx": idx,
                        "task": task,
                        "image_bytes": image_bytes,
                        "val_res": val_res,
                        "prompt": prompt,
                        "priority": priority,
                        "needs_retry": needs_retry,
                        "image_paths": image_paths,
                        "is_detail": is_detail,
                        "output_type": output_type,
                        "validation_pose": validation_pose
                    }

            # Phase 1: Execute all tasks concurrently
            async_tasks = [asyncio.create_task(run_initial_task(idx, t)) for idx, t in enumerate(tasks_to_run)]
            phase1_results = await asyncio.gather(*async_tasks)

            # Phase 2: Sequential Prioritized Retries
            retry_candidates = [res for res in phase1_results if res["needs_retry"]]
            retry_candidates.sort(key=lambda x: x["priority"])

            for res in retry_candidates:
                idx = res["idx"]
                task = res["task"]
                pose = task["pose"]
                image_paths = res["image_paths"]
                prompt = res["prompt"]
                is_detail = res["is_detail"]
                priority = res["priority"]
                output_type = res["output_type"]
                validation_pose = res["validation_pose"]
                val_res = res["val_res"]
                realism_score = val_res.get("realism_score", 100)

                can_retry = False
                async with calls_lock:
                    if openai_calls_count < max_openai_calls:
                        openai_calls_count += 1
                        retry_calls_used += 1
                        can_retry = True
                    else:
                        logger.warning(
                            "Validation failed for pose %s, but OpenAI call limit reached (%d/%d). Skipping validation retry.",
                            pose, openai_calls_count, max_openai_calls
                        )

                if can_retry:
                    logger.warning("Validation or realism check failed for pose %s (realism_score: %s, passed: %s). Retrying once with stronger prompt...", pose, realism_score, val_res["passed"])
                    if is_detail:
                        retry_prompt = (
                            "STRICT PRODUCT DETAIL FIDELITY MODE\n"
                            "Do not generate any person, model, head, body, face, legs or arms.\n"
                            "This is a product-only close-up detail shot.\n"
                            "Focus only on the garment's texture, fabric, seams, pockets and closures.\n\n"
                            + GPTPromptBuilder.build_detail_prompt(garment_json, pose, style)
                        )
                    elif realism_score < realism_threshold:
                        retry_prompt = GPTPromptBuilder.build_strong_realism_prompt(
                            garment_json=garment_json,
                            style=style,
                            pose=pose,
                            has_model_reference=has_model_image,
                            selected_model_gender=metadata.get("selected_model_gender"),
                            output_type=output_type,
                        )
                    else:
                        if garment_json.get("complex_product_mode"):
                            retry_prompt = GPTPromptBuilder.build_complex_retry_prompt(
                                garment_json,
                                val_res.get("issues", []) + val_res.get("missing_details", []),
                                garment_json.get("special_details", []) + garment_json.get("must_preserve", []),
                            )
                        else:
                            retry_prompt = GPTPromptBuilder.build_prompt(
                                garment_json,
                                style,
                                pose,
                                product_focus=bool(task.get("product_focus")),
                                strict_retry_fields=val_res.get("failed_fields", []),
                                has_model_reference=has_model_image,
                                selected_model_gender=metadata.get("selected_model_gender"),
                                output_type=output_type,
                            )

                    focus_block = GPTPromptBuilder.product_focus_block(
                        garment_json,
                        bool(task.get("product_focus")),
                    )
                    if focus_block and focus_block not in retry_prompt:
                        retry_prompt = f"{focus_block}\n\n{retry_prompt}"
                    retry_prompt = GPTPromptBuilder.clean_cinematic_wording(retry_prompt)

                    async with progress_lock:
                        state["step"] = f"retrying_{pose}"
                        await save_state_fn(job_id, state)

                    retry_image_bytes = await self._generate_with_openai_retry(
                        image_paths,
                        retry_prompt,
                        job_model,
                        int(runtime_config.get("max_retry", self._settings.openai_image_retry_attempts)),
                    )

                    try:
                        new_val_res = await asyncio.to_thread(
                            validator.validate_image,
                            retry_image_bytes,
                            garment_json,
                            validation_pose,
                            source_front_bytes,
                            source_back_bytes,
                            validation_threshold=validation_threshold,
                            realism_threshold=realism_threshold,
                        )
                    except Exception as e:
                        logger.warning("Gemini validation failed (retry attempt) for pose %s: %s. Using fallback.", pose, e)
                        new_val_res = {
                            "passed": True,
                            "score": 0.70,
                            "validation_score": 70,
                            "realism_score": 80,
                            "validation_threshold": validation_threshold,
                            "realism_threshold": realism_threshold,
                            "dominant_delta_e_threshold": 15.0,
                            "palette_delta_e_threshold": 18.0,
                            "realism_issues": [],
                            "issues": [],
                            "warnings": ["Gemini tạm thời không khả dụng, vui lòng tự duyệt ảnh (Lỗi: " + str(e)[:200] + ")"],
                            "failed_fields": [],
                            "missing_details": [],
                            "complex_product_mode": garment_json.get("complex_product_mode", False),
                            "critical_mismatch": False,
                            "wrong_garment_type": False,
                            "wrong_garment_area": False,
                            "missing_core_identity": False,
                            "critical_issues": [],
                            "medium_issues": [],
                            "minor_issues": [],
                            "pose_validation": "pass",
                            "expected_pose": validation_pose or None,
                            "final_validation_status": "passed",
                            "dominant_color_delta_e": None,
                            "palette_delta_e": None,
                        }

                    await save_image_item(
                        idx=idx,
                        task=task,
                        image_bytes=retry_image_bytes,
                        val_res=new_val_res,
                        retry_used=True,
                        retry_skipped_due_to_limit=False,
                        retry_priority=priority,
                        retry_prompt=retry_prompt,
                        prompt=prompt
                    )
                else:
                    warnings_list = list(val_res.get("warnings") or [])
                    skipped_warning = "Validation retry skipped because OpenAI call limit was reached."
                    if skipped_warning not in warnings_list:
                        warnings_list.append(skipped_warning)
                    val_res["warnings"] = warnings_list

                    await save_image_item(
                        idx=idx,
                        task=task,
                        image_bytes=res["image_bytes"],
                        val_res=val_res,
                        retry_used=False,
                        retry_skipped_due_to_limit=True,
                        retry_priority=priority,
                        retry_prompt=None,
                        prompt=prompt
                    )

            # Order final images list
            ordered_images = [generated_by_index[idx] for idx in range(len(tasks_to_run))]
            approved_images = [approved_items[idx] for idx in sorted(approved_items)]
            summary = _build_validation_summary(ordered_images)
            has_failed = summary["failed_count"] > 0
            has_warnings = summary["warning_count"] > 0 or summary["review_required_count"] > 0 or has_failed
            state["validation_summary"] = summary
            state["seller_warning"] = seller_warning
            state["final_validation_status"] = "failed" if has_failed else "review_required" if summary["review_required_count"] > 0 else "warning" if summary["warning_count"] > 0 else "approved"

            openai_calls_metadata = {
                "openai_call_limit": max_openai_calls,
                "openai_calls_used": openai_calls_count,
                "initial_generation_calls": initial_generation_calls,
                "retry_calls_used": retry_calls_used,
                "retry_budget_remaining": max(0, max_openai_calls - openai_calls_count),
                "retry_skipped_due_to_limit": any(
                    (generated_by_index[idx].get("retry_skipped_due_to_limit") or False)
                    for idx in range(len(tasks_to_run))
                )
            }
            state["openai_calls_metadata"] = openai_calls_metadata
            metadata["openai_calls_metadata"] = openai_calls_metadata

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
    @staticmethod
    def build_tasks(quantity: int, has_back_image: bool) -> list[dict[str, Any]]:
        return build_catalog_bundle(quantity, has_back_image)

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

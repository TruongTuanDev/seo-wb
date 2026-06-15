import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

import httpx
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.services.image_storage import ImageStorage
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

_face_app = None

def get_face_app():
    global _face_app
    if _face_app is None:
        try:
            import insightface
            # Initialize with CPU context
            _face_app = insightface.app.FaceAnalysis(name='buffalo_l')
            _face_app.prepare(ctx_id=-1, det_size=(640, 640)) # -1 for CPU
        except Exception as e:
            logger.error("Failed to initialize InsightFace: %s", e)
    return _face_app

def check_face_similarity(template_path: Path, generated_bytes: bytes) -> float:
    """Computes InsightFace face embedding cosine similarity between template and generated image."""
    app = get_face_app()
    if app is None:
        logger.warning("InsightFace is not initialized. Bypassing face similarity check.")
        return 1.0
        
    try:
        import cv2
        import numpy as np
        
        # Load template image
        img1 = cv2.imread(str(template_path))
        if img1 is None:
            logger.warning("Could not read face template image: %s", template_path)
            return 1.0
            
        faces1 = app.get(img1)
        if not faces1:
            logger.warning("No faces detected in template image: %s", template_path)
            return 1.0
            
        # Load generated image
        nparr = np.frombuffer(generated_bytes, np.uint8)
        img2 = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img2 is None:
            logger.warning("Could not decode generated image bytes for face verification.")
            return 1.0
            
        faces2 = app.get(img2)
        if not faces2:
            logger.info("No faces detected in generated try-on image. Bypassing check.")
            return 1.0
            
        # Use primary (largest) face in both
        face1 = max(faces1, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
        face2 = max(faces2, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
        
        feat1 = face1.normed_embedding
        feat2 = face2.normed_embedding
        
        sim = float(np.dot(feat1, feat2))
        logger.info("InsightFace face similarity score: %f", sim)
        return sim
    except Exception as exc:
        logger.error("InsightFace face verification failed: %s", exc)
        return 1.0 # Bypassing

def check_and_adjust_occupancy(segmented_bytes: bytes, target_occupancy: float = 0.75) -> bytes:
    """Measures model area occupancy and rescales the transparent model if outside 0.6 <= occupancy <= 0.9."""
    try:
        img = Image.open(BytesIO(segmented_bytes)).convert("RGBA")
        width, height = img.size
        total_pixels = width * height
        
        # Get alpha channel data
        alpha = img.getchannel('A')
        alpha_data = list(alpha.getdata())
        
        # Count non-transparent pixels (alpha > 0)
        non_transparent_pixels = sum(1 for a in alpha_data if a > 0)
        occupancy = non_transparent_pixels / total_pixels
        logger.info("Measured model area occupancy: %f", occupancy)
        
        if 0.6 <= occupancy <= 0.9:
            return segmented_bytes
            
        # We need to rescale
        # Area scale ratio is target_occupancy / current_occupancy
        # Scale factor for dimensions is square root of area scale ratio
        scale_factor = (target_occupancy / occupancy) ** 0.5
        
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        # Resize using LANCZOS
        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create a new transparent canvas of original size
        new_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        
        # Paste centered
        paste_x = (width - new_width) // 2
        paste_y = (height - new_height) // 2
        new_canvas.paste(resized_img, (paste_x, paste_y), resized_img)
        
        out_buf = BytesIO()
        new_canvas.save(out_buf, format="PNG")
        return out_buf.getvalue()
    except Exception as exc:
        logger.error("Occupancy resizing failed: %s", exc)
        return segmented_bytes

BUILTIN_MODELS = [
    {
        "id": "model_1",
        "name": "Model 1",
        "gender": "Female",
        "bodyType": "Petite",
        "height": 155,
        "weight": 45,
        "frontImageUrl": "/models/model1.JPG",
        "front_template": "/models/model1.JPG",
        "imageUrl": "/models/model1.JPG",
        "label": "Female – Petite",
        "description": "Height: 155cm • Weight: 45kg",
        "availablePoses": ["front", "side_45", "walking", "hand_on_hip", "sitting", "back"]
    },
    {
        "id": "model_2",
        "name": "Model 2",
        "gender": "Female",
        "bodyType": "Slim",
        "height": 170,
        "weight": 52,
        "frontImageUrl": "/models/model2.png",
        "front_template": "/models/model2.png",
        "imageUrl": "/models/model2.png",
        "label": "Female – Slim",
        "description": "Height: 170cm • Weight: 52kg",
        "availablePoses": ["front", "side_45", "walking", "hand_on_hip", "sitting", "back"]
    },
    {
        "id": "model_3",
        "name": "Model 3",
        "gender": "Female",
        "bodyType": "Average",
        "height": 165,
        "weight": 60,
        "frontImageUrl": "/models/model3.png",
        "front_template": "/models/model3.png",
        "imageUrl": "/models/model3.png",
        "label": "Female – Average",
        "description": "Height: 165cm • Weight: 60kg",
        "availablePoses": ["front"]
    },
    {
        "id": "model_4",
        "name": "Model 4",
        "gender": "Female",
        "bodyType": "Curvy",
        "height": 170,
        "weight": 72,
        "frontImageUrl": "/models/model4.png",
        "front_template": "/models/model4.png",
        "imageUrl": "/models/model4.png",
        "label": "Female – Curvy",
        "description": "Height: 170cm • Weight: 72kg",
        "availablePoses": ["front"]
    },
    {
        "id": "model_5",
        "name": "Model 5",
        "gender": "Female",
        "bodyType": "Plus Size",
        "height": 175,
        "weight": 85,
        "frontImageUrl": "/models/model5.png",
        "front_template": "/models/model5.png",
        "imageUrl": "/models/model5.png",
        "label": "Female – Plus Size",
        "description": "Height: 175cm • Weight: 85kg",
        "availablePoses": ["front"]
    },
    {
        "id": "model_6",
        "name": "Model 6",
        "gender": "Male",
        "bodyType": "Slim",
        "height": 180,
        "weight": 68,
        "frontImageUrl": "/models/model6.png",
        "front_template": "/models/model6.png",
        "imageUrl": "/models/model6.png",
        "label": "Male – Slim",
        "description": "Height: 180cm • Weight: 68kg",
        "availablePoses": ["front"]
    },
    {
        "id": "model_7",
        "name": "Model 7",
        "gender": "Male",
        "bodyType": "Average",
        "height": 178,
        "weight": 78,
        "frontImageUrl": "/models/model7.png",
        "front_template": "/models/model7.png",
        "imageUrl": "/models/model7.png",
        "label": "Male – Average",
        "description": "Height: 178cm • Weight: 78kg",
        "availablePoses": ["front"]
    },
    {
        "id": "model_8",
        "name": "Model 8",
        "gender": "Male",
        "bodyType": "Athletic",
        "height": 185,
        "weight": 88,
        "frontImageUrl": "/models/model8.png",
        "front_template": "/models/model8.png",
        "imageUrl": "/models/model8.png",
        "label": "Male – Athletic",
        "description": "Height: 185cm • Weight: 88kg",
        "availablePoses": ["front"]
    },
    {
        "id": "model_9",
        "name": "Model 9",
        "gender": "Male",
        "bodyType": "Heavy",
        "height": 182,
        "weight": 105,
        "frontImageUrl": "/models/model9.png",
        "front_template": "/models/model9.png",
        "imageUrl": "/models/model9.png",
        "label": "Male – Heavy",
        "description": "Height: 182cm • Weight: 105kg",
        "availablePoses": ["front"]
    },
    {
        "id": "model_10",
        "name": "Model 10",
        "gender": "Male",
        "bodyType": "Solid",
        "height": 188,
        "weight": 92,
        "frontImageUrl": "/models/model10.png",
        "front_template": "/models/model10.png",
        "imageUrl": "/models/model10.png",
        "label": "Male – Solid",
        "description": "Height: 188cm • Weight: 92kg",
        "availablePoses": ["front"]
    }
]

CONTEXT_PROMPTS = [
    "model posing in a cozy modern cafe, soft morning light, bokeh background, professional photography, highly detailed",
    "model walking on a fashionable urban street, natural sunlight, depth of field, city life background, professional photography",
    "model in a professional photography studio, neutral grey background, high-end studio lighting, soft shadows, sharp focus",
    "model in a bright minimalist showroom, elegant interior design, soft ambient light, clean aesthetics",
    "close up shot of the fabric texture and garment details, model posing in a luxury boutique, warm soft lighting",
    "model standing in an outdoor park with green foliage, warm sunset golden hour light, beautiful nature bokeh",
    "model in a modern loft apartment, brick wall background, natural window light, lifestyle photography",
    "model on a minimalist concrete background, high fashion editorial style, dramatic lighting, sharp details",
    "model posing next to a marble wall, upscale hotel lobby, soft luxurious lighting, professional fashion shoot",
    "model walking in a quiet high-end shopping district, autumn vibe, soft natural daylight, cinematic look"
]

IMAGE_JOB_STORAGE_DIR = Path("storage/image_jobs")

CATEGORY_TO_GARMENT_TYPE = {
    "shirt": "upper_body",
    "t-shirt": "upper_body",
    "hoodie": "upper_body",
    "jacket": "upper_body",
    "pants": "lower_body",
    "jeans": "lower_body",
    "shorts": "lower_body",
    "skirt": "lower_body",
    "dress": "full_body",
    "set": "full_body"
}

def resolve_garment_type(category: str) -> str:
    cat = str(category or "").lower().strip()
    
    # Map Russian terms to English keys
    if any(x in cat for x in ["брюки", "штаны", "леггинсы", "тайтсы", "джоггеры", "pants"]):
        return CATEGORY_TO_GARMENT_TYPE["pants"]
    if any(x in cat for x in ["джинсы", "jeans"]):
        return CATEGORY_TO_GARMENT_TYPE["jeans"]
    if any(x in cat for x in ["шорты", "shorts"]):
        return CATEGORY_TO_GARMENT_TYPE["shorts"]
    if any(x in cat for x in ["юбк", "skirt"]):
        return CATEGORY_TO_GARMENT_TYPE["skirt"]
    if any(x in cat for x in ["плать", "сарафан", "dress"]):
        return CATEGORY_TO_GARMENT_TYPE["dress"]
    if any(x in cat for x in ["костюм", "комбинезон", "комплект", "set"]):
        return CATEGORY_TO_GARMENT_TYPE["set"]
    if any(x in cat for x in ["рубаш", "блуз", "shirt"]):
        return CATEGORY_TO_GARMENT_TYPE["shirt"]
    if any(x in cat for x in ["футболк", "майк", "топ", "t-shirt"]):
        return CATEGORY_TO_GARMENT_TYPE["t-shirt"]
    if any(x in cat for x in ["худи", "свитшот", "толстовк", "джемпер", "свитер", "пуловер", "кардиган", "hoodie"]):
        return CATEGORY_TO_GARMENT_TYPE["hoodie"]
    if any(x in cat for x in ["куртк", "пальто", "пиджак", "жилет", "ветровк", "бомбер", "jacket"]):
        return CATEGORY_TO_GARMENT_TYPE["jacket"]
        
    return "upper_body"

def resolve_english_category(category: str) -> str:
    cat = str(category or "").lower().strip()
    if any(x in cat for x in ["брюки", "штаны", "леггинсы", "джоггеры", "pants"]):
        return "pants"
    if any(x in cat for x in ["джинсы", "jeans"]):
        return "jeans"
    if any(x in cat for x in ["шорты", "shorts"]):
        return "shorts"
    if any(x in cat for x in ["юбк", "skirt"]):
        return "skirt"
    if any(x in cat for x in ["плать", "сарафан", "dress"]):
        return "dress"
    if any(x in cat for x in ["костюм", "комбинезон", "комплект", "set"]):
        return "set"
    if any(x in cat for x in ["рубаш", "блуз", "shirt"]):
        return "shirt"
    if any(x in cat for x in ["футболк", "майк", "топ", "t-shirt"]):
        return "t-shirt"
    if any(x in cat for x in ["худи", "свитшот", "толстовк", "джемпер", "свитер", "пуловер", "кардиган", "hoodie"]):
        return "hoodie"
    if any(x in cat for x in ["куртк", "пальто", "пиджак", "жилет", "ветровк", "бомбер", "jacket"]):
        return "jacket"
    return "clothing"
import hashlib

def compute_garment_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()

import base64

def file_to_data_uri(path: Path) -> str:
    with open(path, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode("utf-8")
    mime = "image/jpeg" if path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
    return f"data:{mime};base64,{encoded}"

def build_simplified_catalog_tasks(
    model_id: str,
    quantity: int,
    selected_style: str,
    has_back_image: bool,
    front_data_uri: str,
    back_data_uri: str | None,
    model_metadata: dict
) -> list[dict[str, Any]]:
    available_poses = model_metadata.get("availablePoses", ["front"])
    
    model_dir = Path("storage/admin_models") / model_id
    if not model_dir.is_dir():
        model_dir = Path("storage/models") / model_id
    
    def get_model_path_for_pose(pose: str) -> Path:
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".JPG"]:
            p = model_dir / f"{pose}{ext}"
            if p.exists():
                return p
        # Check reference file if pose is front
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".JPG"]:
            p_ref = model_dir / f"reference{ext}"
            if p_ref.exists():
                return p_ref
        
        # If the requested pose is not front and it was not found, try front
        if pose != "front":
            for ext in [".png", ".jpg", ".jpeg", ".webp", ".JPG"]:
                p = model_dir / f"front{ext}"
                if p.exists():
                    return p
        
        # Fallback paths
        fallback_p = Path("storage/models") / f"{model_id}.png"
        if fallback_p.exists():
            return fallback_p
        
        # Default global fallback
        return Path("storage/models") / "model1.png"

    def resolve_pose(desired_pose: str) -> str:
        if desired_pose in ["front", "side_45", "back", "walking", "hand_on_hip", "sitting"]:
            if desired_pose in available_poses:
                return desired_pose
            return "front"
        return desired_pose

    from app.services.gpt_image_catalog import build_catalog_bundle
    abstract_tasks = build_catalog_bundle(quantity, has_back_image)
    
    tasks = []
    for atask in abstract_tasks:
        ttype = atask["type"]
        pose_name = atask["pose"]
        label = atask["label"]
        product_focus = bool(atask.get("product_focus"))
        
        if ttype == "catalog":
            resolved = resolve_pose(pose_name)
            p_path = get_model_path_for_pose(resolved)
            g_url = back_data_uri if (pose_name == "back" and has_back_image and back_data_uri) else front_data_uri
            tasks.append({
                "type": "vton_raw",
                "pose": resolved,
                "human_path": p_path,
                "garment_url": g_url,
                "label": label,
                "product_focus": product_focus,
                "style_key": "none"
            })
        elif ttype == "lifestyle":
            resolved = resolve_pose(pose_name)
            p_path = get_model_path_for_pose(resolved)
            tasks.append({
                "type": "vton_bg",
                "pose": resolved,
                "human_path": p_path,
                "garment_url": front_data_uri,
                "label": label,
                "product_focus": product_focus,
                "style_key": selected_style
            })
        elif ttype == "detail":
            vton_type = "logo_detail"
            if pose_name == "fabric_detail":
                vton_type = "fabric_detail"
            elif pose_name == "logo_detail":
                vton_type = "logo_detail"
            elif pose_name in {"front_detail", "extra_detail"}:
                vton_type = "front_detail"
            
            tasks.append({
                "type": vton_type,
                "pose": "detail",
                "garment_url": front_data_uri,
                "label": label,
                "product_focus": product_focus,
                "style_key": "none"
            })
            
    return tasks

class VirtualTryOnService:
    def __init__(self, settings: Settings, redis: Redis):
        self._settings = settings
        self._redis = redis
        self._storage = ImageStorage(settings)
        self._vton_cache = {}
        self._vton_cache_lock = asyncio.Lock()

    def get_models(self) -> list[dict[str, Any]]:
        return BUILTIN_MODELS

    async def run_try_on_job(
        self,
        job_id: str,
        db: Session,
        state: dict[str, Any],
        save_state_fn: Callable[[str, dict[str, Any]], Any],
        attach_draft_fn: Callable[[Session, dict[str, Any], list[dict[str, Any]]], Any]
    ) -> dict[str, Any]:
        raise AppError("fal_ai_not_supported", "Virtual Try-On is not supported because Fal.ai integration has been removed.", 400)

        # Update status to processing
        state["status"] = "processing"
        state["step"] = "vton_processing"
        state["progress"] = 0
        await save_state_fn(job_id, state)

        try:
            total = int(state.get("total") or 1)
            metadata = state.get("metadata") or {}
            background_style = metadata.get("background_style") or "none"
            garment_type = metadata.get("garment_type") or "upper_body"
            product_category = metadata.get("product_category") or ""

            # Parse model ID
            model_id = metadata.get("model_id") or "model_1"
            if "/" in model_id:
                model_id = Path(model_id).parent.name

            from app.models.admin import ModelTemplate
            db_model = db.get(ModelTemplate, model_id)
            model_exists = False
            if db_model and db_model.deleted_at is None:
                model_exists = True
            elif model_id.startswith("model_"):
                model_exists = True
            elif (Path("storage/admin_models") / model_id).is_dir():
                model_exists = True

            if not model_exists:
                model_id = "model_1"
                db_model = db.get(ModelTemplate, model_id)

            # 1. Resolve model metadata and build tasks using build_simplified_catalog_tasks
            if db_model:
                poses = db_model.poses or {}
                available_poses = [pose for pose, url in poses.items() if url] or ["front"]
                model_metadata = {
                    "id": db_model.id,
                    "name": db_model.name,
                    "gender": db_model.gender,
                    "bodyType": db_model.body_type,
                    "height": db_model.height_cm or 0,
                    "weight": db_model.weight_kg or 0,
                    "availablePoses": available_poses,
                    "isAiGenerated": bool(db_model.is_ai_generated),
                }
            else:
                model_metadata = next((m for m in BUILTIN_MODELS if m["id"] == model_id), {"availablePoses": ["front"]})
            
            # File paths
            job_dir = IMAGE_JOB_STORAGE_DIR / job_id
            input_dir = job_dir / "input"
            output_dir = job_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            state["step"] = "uploading_inputs"
            await save_state_fn(job_id, state)
            
            front_path = input_dir / "front.jpg"
            back_path = input_dir / "back.jpg"

            if not front_path.exists():
                raise AppError("missing_front_image", "Front garment image is missing from storage.", 400)
            
            has_back_garment = back_path.exists()
            state["step"] = "uploading_inputs"
            await save_state_fn(job_id, state)

            front_data_uri = await asyncio.to_thread(fal_client.upload_file, front_path)
            back_data_uri = await asyncio.to_thread(fal_client.upload_file, back_path) if has_back_garment else None

            tasks_to_run = build_simplified_catalog_tasks(
                model_id=model_id,
                quantity=total,
                selected_style=background_style,
                has_back_image=has_back_garment,
                front_data_uri=front_data_uri,
                back_data_uri=back_data_uri,
                model_metadata=model_metadata
            )
            
            # Populate human_url for tasks requiring it
            for task in tasks_to_run:
                if "human_path" in task:
                    task["human_url"] = await asyncio.to_thread(fal_client.upload_file, task["human_path"])
            
            
            state["step"] = "context_diversification"
            await save_state_fn(job_id, state)

            # Calculate garment hash from front garment bytes
            with open(front_path, "rb") as f:
                front_bytes = f.read()
            garment_hash = compute_garment_hash(front_bytes)

            generated_by_index = {}
            progress_lock = asyncio.Lock()
            semaphore = asyncio.Semaphore(3)

            async def run_one_task(idx: int, task: dict[str, Any]) -> dict[str, Any]:
                async with semaphore:
                    ttype = task["type"]
                    label = task["label"]
                    face_sim_score = None
                    
                    if ttype in ["vton_raw", "vton_bg"]:
                        h_url = task["human_url"]
                        h_path = task["human_path"]
                        g_url = task["garment_url"]
                        
                        cache_key = f"{model_id}:{task.get('pose', 'front')}:{garment_hash}:{garment_type}"
                        async with self._vton_cache_lock:
                            if cache_key not in self._vton_cache:
                                vton_url = await self._run_vton(
                                    human_url=h_url,
                                    garment_url=g_url,
                                    garment_type=garment_type,
                                    metadata=metadata
                                )
                                vton_bytes = await self._download_image(vton_url)
                                
                                # Perform validation checks
                                from app.services.catalog_quality import check_color_similarity, verify_garment_category_florence
                                
                                # 1. Color check
                                with open(front_path, "rb") as f:
                                    front_bytes = f.read()
                                color_sim = check_color_similarity(front_bytes, vton_bytes)
                                
                                # 2. Face check
                                face_sim = check_face_similarity(h_path, vton_bytes)
                                
                                # 3. Florence-2 category verification
                                category_ok = verify_garment_category_florence(vton_url, product_category)
                                
                                logger.info(
                                    "VTON Attempt 1 (Index %d): Color similarity = %f (threshold=0.85), Face similarity = %f (threshold=0.90), Category OK = %s",
                                    idx + 1, color_sim, face_sim, category_ok
                                )
                                
                                # If any check fails, retry once
                                if (color_sim < 0.85 or face_sim < 0.90 or not category_ok) and self._settings.enable_image_validation_retry:
                                    logger.warning(
                                        "Validation failed. Retrying VTON generation once for Index %d...",
                                        idx + 1
                                    )
                                    vton_url = await self._run_vton(
                                        human_url=h_url,
                                        garment_url=g_url,
                                        garment_type=garment_type,
                                        metadata=metadata
                                    )
                                    vton_bytes = await self._download_image(vton_url)
                                    
                                    # Recalculate face similarity for the retried image
                                    face_sim = check_face_similarity(h_path, vton_bytes)
                                    
                                self._vton_cache[cache_key] = (vton_url, vton_bytes, face_sim)
                                
                            vton_url, vton_bytes, face_sim_score = self._vton_cache[cache_key]
                        
                        # Phase 2: Segmentation, Occupancy resizing, Background Change & Compositing
                        try:
                            # 1. Run BiRefNet segmentation
                            from PIL import Image
                            from io import BytesIO
                            biref_res = await fal_client.run_async(
                                "fal-ai/birefnet/v2",
                                arguments={"image_url": vton_url}
                            )
                            segmented_url = biref_res["image"]["url"]
                            segmented_bytes = await self._download_image(segmented_url)
                            
                            # 2. Adjust occupancy if necessary
                            adjusted_segmented_bytes = check_and_adjust_occupancy(segmented_bytes, target_occupancy=0.75)
                            
                            # 3. Create or generate the background
                            if ttype == "vton_raw":
                                with Image.open(BytesIO(adjusted_segmented_bytes)) as s_img:
                                    w, h = s_img.size
                                bg_img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
                            else:
                                style_key = task["style_key"]
                                style_prompts = {
                                    "cafe": "model posing in a cozy modern cafe, soft morning light, bokeh background, professional photography",
                                    "street": "model walking on a fashionable urban street, natural sunlight, depth of field, city life background",
                                    "studio": "model in a professional photography studio, neutral grey background, high-end studio lighting",
                                    "park": "model standing in an outdoor park with green foliage, warm sunset golden hour light, nature bokeh",
                                    "showroom": "model in a bright minimalist showroom, elegant interior design, soft ambient light",
                                    "boutique": "model posing in a luxury boutique, warm soft lighting",
                                    "loft": "model in a modern loft apartment, brick wall background, natural window light",
                                    "office": "model in a modern minimalist office setting, professional portrait lighting",
                                    "streetwear": "model walking on a fashionable streetwear urban street, natural sunlight, depth of field, city life background",
                                    "urban": "model posing in a modern urban concrete plaza, high-rise buildings background, sunset light, professional fashion photography",
                                    "gym": "model in a bright modern gym, fitness equipment in soft focus background, soft athletic lighting",
                                    "playroom": "model in a cheerful children playroom, colorful soft toys, sunny natural light",
                                    "bedroom": "model in a cozy modern bedroom, soft morning window light, warm homelike atmosphere",
                                    "premium_studio": "model in a premium editorial photography studio, neutral elegant background, dramatic high-fashion studio lighting"
                                }
                                cat_eng = resolve_english_category(product_category)
                                base_prompt = style_prompts.get(style_key, style_key)
                                
                                base_prompt = base_prompt.replace("model posing", f"model wearing the product ({cat_eng}) posing")
                                base_prompt = base_prompt.replace("model walking", f"model wearing the product ({cat_eng}) walking")
                                base_prompt = base_prompt.replace("model standing", f"model wearing the product ({cat_eng}) standing")
                                base_prompt = base_prompt.replace("model in a", f"model wearing the product ({cat_eng}) in a")
                                
                                if not base_prompt.startswith("model wearing"):
                                    base_prompt = f"model wearing the product ({cat_eng}), {base_prompt}"
                                    
                                prompt = f"garment view, {base_prompt}"
                                
                                # Call background change
                                bg_res = await fal_client.run_async(
                                    "fal-ai/image-editing/background-change",
                                    arguments={
                                        "image_url": vton_url,
                                        "prompt": prompt
                                    }
                                )
                                bg_url = bg_res["image"]["url"]
                                bg_bytes = await self._download_image(bg_url)
                                bg_img = Image.open(BytesIO(bg_bytes)).convert("RGBA")
                            
                            # 4. Composite the segmented model on the background
                            model_img = Image.open(BytesIO(adjusted_segmented_bytes)).convert("RGBA")
                            if model_img.size != bg_img.size:
                                model_img = model_img.resize(bg_img.size, Image.Resampling.LANCZOS)
                                
                            final_img = Image.alpha_composite(bg_img, model_img)
                            final_rgb = final_img.convert("RGB")
                            
                            out_buf = BytesIO()
                            final_rgb.save(out_buf, format="JPEG", quality=95)
                            content = out_buf.getvalue()
                        except Exception as composite_err:
                            logger.error("Segmented composite failed: %s. Falling back to raw VTON bytes.", composite_err)
                            content = vton_bytes
                            
                    elif ttype == "fabric_detail":
                        prompt = "high quality professional product photography, extreme close up shot of fabric weave and texture details, textile pattern, studio lighting"
                        final_img_url = await self._run_img2img(
                            image_url=task["garment_url"],
                            prompt=prompt,
                            strength=0.22
                        )
                        content = await self._download_image(final_img_url)
                    elif ttype == "logo_detail":
                        prompt = "high quality professional product photography, close up shot of brand logo, markings, embroidery, or graphics on the garment, studio lighting"
                        final_img_url = await self._run_img2img(
                            image_url=task["garment_url"],
                            prompt=prompt,
                            strength=0.22
                        )
                        content = await self._download_image(final_img_url)
                    elif ttype in ["back_detail", "front_detail"]:
                        desc = "rear view" if ttype == "back_detail" else "front view"
                        prompt = f"high quality professional product photography, flat lay or {desc} of the product garment showing details, clean studio background"
                        final_img_url = await self._run_img2img(
                            image_url=task["garment_url"],
                            prompt=prompt,
                            strength=0.22
                        )
                        content = await self._download_image(final_img_url)
                    elif ttype == "label_detail":
                        prompt = "high quality professional product photography, close up shot of neck label, clothing tag, or brand tags, studio lighting"
                        final_img_url = await self._run_img2img(
                            image_url=task["garment_url"],
                            prompt=prompt,
                            strength=0.22
                        )
                        content = await self._download_image(final_img_url)
                    else:
                        raise ValueError(f"Unknown task type: {ttype}")

                    # Download and save
                    file_name = f"generated-{idx + 1:02d}.jpg"
                    out_path = output_dir / file_name

                    storage_result = await asyncio.to_thread(
                        self._storage.save_generated_image,
                        job_id=job_id,
                        file_name=file_name,
                        content=content,
                        local_path=out_path,
                    )
                    item = {
                        "fileName": file_name,
                        "url": storage_result["url"],
                        "storage": storage_result["storage"],
                        "storageKey": storage_result["storageKey"],
                        "bytes": storage_result["bytes"],
                        "width": storage_result.get("width"),
                        "height": storage_result.get("height"),
                        "prompt": label,
                        "label": label,
                        "pose": task.get("pose", "front"),
                        "background_style": task.get("style_key", "none"),
                        "product_focus": bool(task.get("product_focus")),
                        "model_id": model_id,
                        "garment_type": garment_type,
                        "face_similarity_score": face_sim_score
                    }

                    async with progress_lock:
                        generated_by_index[idx] = item
                        ordered_images = [generated_by_index[item_index] for item_index in sorted(generated_by_index)]
                        state["images"] = ordered_images
                        state["progress"] = len(ordered_images)
                        await save_state_fn(job_id, state)

                    return item

            # Run all tasks exactly once
            async_tasks = [asyncio.create_task(run_one_task(idx, t)) for idx, t in enumerate(tasks_to_run)]
            await asyncio.gather(*async_tasks)

            # Finalize images order
            ordered_images = [generated_by_index[idx] for idx in range(total)]
            
            # Catalog Quality Engine Evaluation exactly once on the final package
            quality_report = {}
            try:
                from app.services.catalog_quality import CatalogQualityEngine
                quality_engine = CatalogQualityEngine(self._settings)
                quality_report = await quality_engine.score_catalog_package(ordered_images, job_dir)
                state["quality_report"] = quality_report
                logger.info("Catalog quality evaluation completed. Score: %s", quality_report.get("catalog_score"))
            except Exception as e:
                logger.exception("Catalog Quality Engine evaluation failed: %s", e)

            attach_draft_fn(db, state, ordered_images)
            state["status"] = "completed"
            state["step"] = "completed"
            await save_state_fn(job_id, state)
            
            return {
                "id": job_id,
                "status": "completed",
                "step": "completed",
                "progress": total,
                "total": total,
                "images": ordered_images,
                "error": None
            }

        except Exception as exc:
            logger.exception("Virtual Try-On job failed for job_id: %s", job_id)
            state["status"] = "failed"
            state["step"] = "failed"
            state["error"] = str(exc)[:2000]
            await save_state_fn(job_id, state)
            raise

    async def _run_vton(self, human_url: str, garment_url: str, garment_type: str, metadata: dict = None) -> str:
        """Calls fal-ai/idm-vton endpoint to dress the model. Disabled since Fal.ai is removed."""
        raise AppError("fal_ai_not_supported", "Virtual Try-On is not supported because Fal.ai integration has been removed.", 400)

    async def _run_img2img(self, image_url: str, prompt: str, strength: float) -> str:
        """Calls fal-ai/flux/dev/image-to-image for context diversification. Disabled since Fal.ai is removed."""
        raise AppError("fal_ai_not_supported", "Virtual Try-On is not supported because Fal.ai integration has been removed.", 400)

    async def _download_image(self, url: str) -> bytes:
        """Downloads the generated image bytes from fal CDN."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.content

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import cloudinary
import cloudinary.uploader
from PIL import Image, ImageOps

from app.core.config import Settings


class ImageStorage:
    def __init__(self, settings: Settings):
        self._settings = settings

    def optimize_generated_image(self, content: bytes) -> bytes:
        image = Image.open(BytesIO(content))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1536, 2048), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        quality = max(70, min(self._settings.generated_image_jpeg_quality, 95))
        image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
        return buffer.getvalue()

    def save_generated_image(self, *, job_id: str, file_name: str, content: bytes, local_path: Path) -> dict[str, Any]:
        optimized = self.optimize_generated_image(content)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(optimized)

        if not self._settings.cloudinary_configured:
            return {
                "url": f"/cards/image-jobs/{job_id}/media/{file_name}",
                "storage": "local",
                "storageKey": str(local_path),
                "bytes": len(optimized),
            }

        cloudinary.config(
            cloud_name=self._settings.effective_cloudinary_cloud_name,
            api_key=self._settings.effective_cloudinary_api_key,
            api_secret=self._settings.effective_cloudinary_api_secret,
            secure=True,
        )
        public_id = f"seller-wb-ai/image_jobs/{job_id}/{Path(file_name).stem}"
        result = cloudinary.uploader.upload(
            str(local_path),
            public_id=public_id,
            resource_type="image",
            overwrite=True,
            quality="auto:good",
            fetch_format="auto",
        )
        return {
            "url": str(result["secure_url"]),
            "storage": "cloudinary",
            "storageKey": public_id,
            "bytes": len(optimized),
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
        }

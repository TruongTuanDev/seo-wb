import io
import zipfile
import logging
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

logger = logging.getLogger(__name__)

MARKETPLACE_SPECS = {
    "wildberries": {
        "size": (900, 1200),
        "ratio": 3 / 4
    },
    "ozon": {
        "size": (1200, 1600),
        "ratio": 3 / 4
    },
    "amazon": {
        "size": (2000, 2000),
        "ratio": 1.0
    },
    "shopify": {
        "size": (2048, 2048),
        "ratio": 1.0
    }
}

class CatalogExporter:
    @staticmethod
    def crop_and_resize(img: Image.Image, target_size: tuple[int, int], target_ratio: float) -> Image.Image:
        """Crops an image from the center to match a target aspect ratio, then resizes it."""
        width, height = img.size
        current_ratio = width / height
        
        if current_ratio > target_ratio:
            # Image is wider than target ratio: crop sides
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            right = left + new_width
            top = 0
            bottom = height
        else:
            # Image is taller than target ratio: crop top/bottom
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            bottom = top + new_height
            left = 0
            right = width
            
        cropped = img.crop((left, top, right, bottom))
        return cropped.resize(target_size, Image.Resampling.LANCZOS)

    def export_marketplace_package(
        self,
        job_dir: Path,
        quality_report: Dict[str, Any],
        images: List[Dict[str, Any]],
        marketplace: str
    ) -> bytes:
        """Generates cropped/resized catalog images for a marketplace and returns them as a ZIP byte stream."""
        m_key = marketplace.strip().lower()
        if m_key not in MARKETPLACE_SPECS:
            raise ValueError(f"Unsupported marketplace: {marketplace}")
            
        spec = MARKETPLACE_SPECS[m_key]
        target_size = spec["size"]
        target_ratio = spec["ratio"]
        
        # Build mapping from role names to filenames
        role_mapping = {
            "thumbnail": quality_report.get("best_thumbnail"),
            "catalog": quality_report.get("best_catalog_image"),
            "lifestyle": quality_report.get("best_lifestyle_image"),
            "banner": quality_report.get("best_marketing_banner"),
        }
        
        # Fallbacks if some roles are missing
        all_files = [img["fileName"] for img in images]
        
        used_files = set()
        final_package_items = [] # list of (role_name, file_path)
        
        # Process primary roles first
        for role, fname in role_mapping.items():
            if fname and (job_dir / "output" / fname).is_file():
                final_package_items.append((role, job_dir / "output" / fname))
                used_files.add(fname)
            else:
                # Find a fallback file that isn't used yet
                fallback_file = None
                for f in all_files:
                    if f not in used_files:
                        fallback_file = f
                        break
                if not fallback_file and all_files:
                    fallback_file = all_files[0]
                    
                if fallback_file:
                    final_package_items.append((role, job_dir / "output" / fallback_file))
                    used_files.add(fallback_file)
                    
        # Add remaining files as numbered catalog variations
        idx = 1
        for f in all_files:
            if f not in used_files:
                final_package_items.append((f"catalog_variation_{idx}", job_dir / "output" / f))
                used_files.add(f)
                idx += 1
                
        # Write to zip stream
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for role_name, file_path in final_package_items:
                if not file_path.is_file():
                    continue
                try:
                    with Image.open(file_path) as img:
                        processed_img = self.crop_and_resize(img, target_size, target_ratio)
                        
                        # Save to in-memory bytes
                        img_bytes = io.BytesIO()
                        processed_img.save(img_bytes, format="JPEG", quality=90)
                        
                        zip_file.writestr(
                            f"{role_name}.jpg",
                            img_bytes.getvalue()
                        )
                except Exception as exc:
                    logger.error("Failed exporting image %s for %s: %s", file_path.name, role_name, exc)
                    
        return zip_buffer.getvalue()

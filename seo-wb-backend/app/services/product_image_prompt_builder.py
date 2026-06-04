from typing import Any


HERO_RULES = {
    "tops": "hero crop from head to upper thigh or closer; the top fills the frame and remains immediately identifiable",
    "bottoms": "hero crop from waist to shoes; the pants/skirt/shorts fill the frame and remain immediately identifiable",
    "bags": "hero close-up crop; the bag or accessory fills the frame and is the clear subject",
    "default": "hero crop based on product type; the product fills 75-85% of the frame and is immediately identifiable",
}

POSE_PRESETS = {
    "tops": [
        "hero front",
        "straight pose",
        "45-degree turn",
        "back view",
        "collar or pocket detail",
        "seated pose",
        "walking pose",
        "close crop",
    ],
    "bottoms": [
        "hero waist-to-shoes",
        "hands in pockets",
        "45-degree turn",
        "back view",
        "walking pose",
        "high stool seated",
        "outdoor walking",
        "waistband or pocket detail",
    ],
    "bags": [
        "hero close-up",
        "front angle",
        "side angle",
        "back angle",
        "worn by model but product dominant",
        "hand-held",
        "detail close-up",
        "minimal lifestyle",
    ],
}


def product_family(category: str) -> str:
    normalized = category.casefold()
    if any(token in normalized for token in ["брю", "джин", "шорт", "юб", "леггин", "pants", "jeans", "skirt", "short"]):
        return "bottoms"
    if any(token in normalized for token in ["сум", "bag", "аксесс", "accessor"]):
        return "bags"
    if any(token in normalized for token in ["руб", "блуз", "футбол", "топ", "кофт", "куртк", "жакет", "shirt", "top", "jacket"]):
        return "tops"
    return "default"


def build_product_image_prompt(metadata: dict[str, Any], index: int, total: int, has_model_reference: bool) -> str:
    title = str(metadata.get("title") or metadata.get("productName") or "fashion product").strip()
    category = str(metadata.get("category") or metadata.get("subjectName") or "").strip()
    color = str(metadata.get("color") or "").strip()
    material = str(metadata.get("material") or "").strip()
    brand = str(metadata.get("brand") or "").strip()
    description = str(metadata.get("description") or "").strip()[:900]
    family = product_family(category)
    presets = POSE_PRESETS.get(family, POSE_PRESETS["tops"])
    shot = "hero image" if index == 0 else presets[(index - 1) % len(presets)]
    crop_rule = HERO_RULES.get(family, HERO_RULES["default"])
    model_rule = (
        "Use the model reference only for face, hair, and model consistency."
        if has_model_reference
        else "No model identity reference is provided; use a realistic adult Eastern European / Russian marketplace fashion model if a model is needed."
    )
    market_style_rule = (
        "Use Wildberries-ready Russian marketplace styling: adult model, natural confident pose, "
        "clean grooming, neutral expression, commercial fashion catalog look, no excessive glamour."
    )

    return f"""
Create a photorealistic Wildberries product-card image from the reference images.

Product data:
- Product name: {title}
- Category: {category}
- Brand: {brand or "not visible"}
- Color: {color}
- Material: {material}
- Description context: {description}

Shot plan:
- Image {index + 1} of {total}: {shot}.
- If this is image 1, it must be the main Wildberries hero image.
- Hero crop rule: {crop_rule}.

Hero image rules:
- Product-first composition.
- The product type must be immediately clear: shirt, jeans, jacket, bag, accessory, etc.
- Do not let the whole body dominate the image when the product is only one garment or accessory.
- {market_style_rule}
- Clean white or very light neutral background.
- Soft even lighting.
- Product large, centered, sharp, and not distorted.
- No text, watermark, sale badge, unrelated logos, or clutter.

Product fidelity rules:
- Use the front image as the main product reference.
- Use the back image to preserve back details.
- {model_rule}
- Preserve exact color, silhouette, fabric, seams, stitching, pockets, buttons, zippers, collar, cuffs, waistband, straps, prints, and texture.
- Do not redesign the product.
- Do not invent new details.

Secondary image rules:
- For images after the hero, vary pose/crop while keeping product details consistent.
- Allowed secondary styles: straight pose, 45-degree turn, back view, detail-focused crop, walking pose, seated pose, or light lifestyle background.
- Lifestyle background must stay minimal and not distract from the product.

Output:
- Portrait marketplace image suitable for Wildberries.
- Minimum effective resolution 700x900.
""".strip()

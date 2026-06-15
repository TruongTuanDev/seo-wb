import json
from typing import Any

STYLE_OPTIONS = {
    "studio": "Clean light grey ecommerce studio background, real camera photography, soft natural shadows, realistic retail catalog lighting.",
    "streetwear": "Modern urban streetwear setting, clean city background, natural daylight, professional fashion photography.",
    "luxury": "Elegant boutique or professional studio background, high-end editorial fashion lighting.",
    "lifestyle": "Warm indoor lifestyle setting, natural light, clean modern interior.",
    "sports": "Bright modern gym or activewear setting, clean background, athletic lighting."
}

# Add compatibility mapping
STYLE_COMPATIBILITY_MAPPING = {
    "boutique": "luxury",
    "cafe": "lifestyle",
    "gym": "sports"
}

POSES = {
    "front": "Front-facing full-body catalog pose. Standing naturally, looking at camera, arms relaxed.",
    "side_45": "45-degree side catalog pose. Body turned slightly, face visible, full garment visible.",
    "walking": "Natural walking fashion catalog pose. One foot stepping forward, full garment visible.",
    "back": "Back-facing catalog pose. Show the back of the garment clearly. Use only if product back image exists.",
    "hand_on_hip": "One hand on hip, fashion catalog stance, full garment visible.",
    "sitting": "Sitting on a simple white cube, professional catalog pose, garment clearly visible."
}


class GPTPromptBuilder:
    @staticmethod
    def product_focus_block(garment_json: dict[str, Any], product_focus: bool) -> str:
        if not product_focus:
            return ""
        area = str(garment_json.get("garment_area") or "upper_body").lower().strip()
        if area == "lower_body":
            framing = "Frame primarily from the waist to the feet. The lower-body product must occupy most of the image."
        elif area == "full_body":
            framing = "Show the complete full-body garment from neckline to hem. The garment must occupy most of the image."
        else:
            framing = "Frame primarily from the shoulders to the hips. The upper-body product must occupy most of the image."
        return (
            "PRODUCT-FOCUSED CAMERA FRAMING:\n"
            f"{framing}\n"
            "Prioritize the product over the model's face and surrounding background.\n"
            "Keep the complete product visible and do not crop any important product edge or detail."
        )

    @staticmethod
    def _article_context_block(garment_json: dict[str, Any]) -> str:
        source_title = str(garment_json.get("source_title") or "").strip()
        source_description = str(garment_json.get("source_description") or "").strip()
        source_category = str(garment_json.get("source_category") or garment_json.get("category") or "").strip()
        lines = []
        if source_title:
            lines.append(f"- Source title: {source_title}")
        if source_category:
            lines.append(f"- Source category: {source_category}")
        if source_description:
            lines.append(f"- Source description: {source_description}")
        if not lines:
            return ""
        return "ARTICLE CONTEXT:\nUse the source listing context to understand which garment must be replaced and what details matter most.\n" + "\n".join(lines)

    @staticmethod
    def _model_profile_block(garment_json: dict[str, Any], has_model_reference: bool) -> str:
        if has_model_reference:
            return ""
        model_profile = garment_json.get("model_profile") or {}
        ethnicity = model_profile.get("ethnicity") or "russian"
        gender = model_profile.get("gender") or garment_json.get("gender") or "female"
        age_group = model_profile.get("age_group") or "adult"
        body_type = model_profile.get("body_type") or "average"
        aesthetic = model_profile.get("aesthetic") or "real russian ecommerce model"
        styling_notes = model_profile.get("styling_notes") or "make the product the main visual focus"
        return (
            "AI MODEL CASTING:\n"
            f"Generate a real photographed-looking {ethnicity} {gender} ecommerce model.\n"
            f"Age group: {age_group}.\n"
            f"Body type: {body_type}.\n"
            f"Model aesthetic: {aesthetic}.\n"
            f"Styling notes: {styling_notes}.\n"
            "The model must look suitable for Wildberries/Russian ecommerce catalog photography.\n"
            "Keep the face realistic and commercially appealing, not editorial fantasy."
        )

    @staticmethod
    def build_complex_retry_prompt(
        garment_json: dict[str, Any],
        failed_reasons: list[str],
        critical_details: list[str],
    ) -> str:
        reasons_text = "\n".join(f"- {reason}" for reason in failed_reasons if reason) or "- fidelity mismatch"
        details_text = "\n".join(f"- {detail}" for detail in critical_details if detail) or "- exact color, wash, seams, logos and embellishments"
        prompt = f"""
STRICT PRODUCT PRESERVATION MODE.

The previous image failed because:
{reasons_text}

Regenerate the image while preserving the exact product.

The garment must keep:
{details_text}

Do not simplify the garment.
Do not remove rhinestones.
Do not remove ripped or distressed patches.
Do not change the denim wash.
Do not recolor the garment.
Do not turn embellished denim into plain denim.

Only change pose, model placement, camera angle, or background.
The product itself must remain visually identical to the source.
"""
        return GPTPromptBuilder.clean_cinematic_wording(prompt.strip())

    @staticmethod
    def clean_cinematic_wording(prompt: str) -> str:
        words_to_remove = [
            "ultra realistic",
            "perfect model",
            "premium look",
            "glamorous",
            "high fashion fantasy",
            "flawless skin"
        ]
        cleaned = prompt
        import re
        for word in words_to_remove:
            cleaned = re.sub(re.escape(word), "", cleaned, flags=re.IGNORECASE)
        return cleaned

    @staticmethod
    def build_prompt(
        garment_json: dict[str, Any],
        style: str,
        pose: str,
        product_focus: bool = False,
        strict_retry_fields: list[str] | None = None,
        has_model_reference: bool = True,
        selected_model_gender: str | None = None
    ) -> str:
        # Standardize style
        style_key = style.lower().strip()
        style_key = STYLE_COMPATIBILITY_MAPPING.get(style_key, style_key)
        style_desc = STYLE_OPTIONS.get(style_key, STYLE_OPTIONS["studio"])

        # Standardize pose
        pose_key = pose.lower().strip()
        pose_desc = POSES.get(pose_key, POSES["front"])

        # Base Prompt emphasizing real photography
        if has_model_reference:
            model_reference_prompt = (
                "Use the first image as the exact model reference.\n"
                "Preserve the model's real face, identity, skin texture, body proportions, hairstyle and pose direction.\n\n"
            )
        else:
            model_reference_prompt = (
                "There is no uploaded model reference image.\n"
                "Generate a new realistic Russian ecommerce model based on the model casting instructions below.\n\n"
            )

        base_prompt = (
            model_reference_prompt
            + "Use the product images as the garment reference.\n\n"
            "Dress the model in the exact product described in garment_json.\n\n"
            "The image must look like a real ecommerce product photograph taken with a real camera.\n"
            "Natural skin texture.\n"
            "Realistic face.\n"
            "Normal human imperfections.\n"
            "Realistic body proportions.\n"
            "No CGI.\n"
            "No 3D render.\n"
            "No cartoon.\n"
            "No illustration.\n"
            "No plastic skin.\n"
            "No overly smooth AI face.\n"
            "No beauty retouching.\n"
            "No fantasy fashion campaign."
        )

        # Garment Rules (Requirement 7)
        garment_rules_prompt = (
            "Garment Rules:\n"
            "- preserve garment category\n"
            "- preserve color\n"
            "- preserve length\n"
            "- preserve texture\n"
            "- preserve pockets\n"
            "- preserve seams\n"
            "- preserve buttons/zipper\n"
            "- do not invent logos\n"
            "- do not change garment area"
        )
        color_palette = garment_json.get("color_palette") or []
        special_details = garment_json.get("special_details") or []
        secondary_color = garment_json.get("secondary_color") or ""
        color_lock_prompt = (
            "COLOR LOCK:\n"
            "The garment color must remain identical to the reference product.\n"
            "Do not recolor the garment.\n"
            "Do not change denim wash.\n"
            "Do not create grey denim.\n"
            "Do not create darker denim.\n"
            "Do not create lighter denim.\n"
            "Do not modify distressing.\n"
            "Do not modify rhinestone placement.\n"
            "Keep the exact same color, wash pattern, distressing pattern, stitching, pockets, seams, logos and embellishments.\n"
            "The generated garment must represent the same physical product."
        )
        if color_palette:
            color_lock_prompt += f"\nReference color palette: {', '.join(color_palette)}."
        if secondary_color:
            color_lock_prompt += f"\nSecondary color/accent: {secondary_color}."
        if special_details:
            color_lock_prompt += f"\nCritical special details to keep unchanged: {', '.join(special_details)}."

        # Garment Area Rules
        area = garment_json.get("garment_area", "upper_body").lower().strip()
        if area == "upper_body":
            area_prompt = (
                "Garment area: upper body.\n\n"
                "Replace only the upper-body garment with the uploaded product.\n\n"
                "Keep pants, skirt, shoes, face, hair, hands and body proportions unchanged.\n\n"
                "Do not change the lower-body clothing."
            )
        elif area == "lower_body":
            category_name = garment_json.get("category", "").lower().strip()
            skirt_rule = "If the product is a skirt, do not turn it into a top, pants, shorts or mini skirt."
            if "юбк" in category_name or "skirt" in category_name:
                skirt_rule = "The product is a skirt, do not turn it into a top, pants, shorts or mini skirt."
            pants_rule = "If the product is pants or jeans, do not turn it into a skirt."
            if any(x in category_name for x in ["брюки", "штаны", "джинсы", "pants", "jeans"]):
                pants_rule = "The product is pants or jeans, do not turn it into a skirt."

            area_prompt = (
                f"Garment area: lower body.\n\n"
                f"Replace only the lower-body garment with the uploaded product.\n\n"
                f"The garment must start at the correct waist position and extend downward according to the product length.\n\n"
                f"Keep upper-body clothing, face, hair, hands and body proportions unchanged.\n\n"
                f"{skirt_rule}\n\n"
                f"{pants_rule}\n\n"
                f"Remove or fully cover any conflicting original lower-body clothing on the model."
            )
        elif area == "full_body":
            area_prompt = (
                "Garment area: full body.\n\n"
                "Dress the model in the uploaded full-body garment.\n\n"
                "Preserve neckline, sleeves, waistline, silhouette, length, hem, fabric, color and details.\n\n"
                "Do not convert the dress into a top, skirt, pants or shorts."
            )
        else:
            area_prompt = ""

        # Garment Details description
        must_preserve = garment_json.get("must_preserve", [])
        must_not_change = garment_json.get("must_not_change", [])
        
        garment_gender = garment_json.get("gender") or "female"
        if has_model_reference and selected_model_gender:
            norm_g = selected_model_gender.lower().strip()
            if "female" in norm_g or "women" in norm_g:
                garment_gender = "Female"
            elif "male" in norm_g or "men" in norm_g or "boy" in norm_g:
                garment_gender = "Male"
            else:
                garment_gender = "Unisex"
        
        garment_info = (
            f"Garment Specifications:\n"
            f"- Product Type: {garment_json.get('product_type')}\n"
            f"- Category: {garment_json.get('category')}\n"
            f"- Gender: {garment_gender}\n"
            f"- Main Color: {garment_json.get('main_color')}\n"
            f"- Secondary Color: {secondary_color}\n"
            f"- Color Palette: {', '.join(color_palette) if color_palette else 'n/a'}\n"
            f"- Material: {garment_json.get('material')}\n"
            f"- Fabric Texture: {garment_json.get('fabric_texture')}\n"
            f"- Silhouette: {garment_json.get('silhouette')}\n"
            f"- Silhouette/Fit: {garment_json.get('fit')}\n"
            f"- Length: {garment_json.get('length')}\n"
            f"- Closure: {garment_json.get('closure')}\n"
            f"- Pockets: {garment_json.get('pockets')}\n"
            f"- Hem: {garment_json.get('hem')}\n"
            f"- Logo/Text: {garment_json.get('logo_or_text')}\n"
            f"- Summary Description: {garment_json.get('prompt_summary')}\n"
        )
        if special_details:
            garment_info += f"- Special Details: {', '.join(special_details)}\n"
        if must_preserve:
            garment_info += f"- Must Preserve: {', '.join(must_preserve)}\n"
        if must_not_change:
            garment_info += f"- Must Not Change: {', '.join(must_not_change)}\n"

        article_context_block = GPTPromptBuilder._article_context_block(garment_json)
        model_profile_block = GPTPromptBuilder._model_profile_block(garment_json, has_model_reference)

        # Construct final prompt
        parts = [
            base_prompt,
            article_context_block,
            model_profile_block,
            garment_rules_prompt,
            color_lock_prompt,
            f"Style Setting:\n{style_desc}",
            f"Pose Instruction:\n{pose_desc}",
            GPTPromptBuilder.product_focus_block(garment_json, product_focus),
            area_prompt,
            garment_info
        ]

        # Strict Retry Mode Prefix & Explicit Failures List
        if strict_retry_fields:
            failed_fields_str = ", ".join(strict_retry_fields)
            retry_prefix = (
                f"CRITICAL GARMENT FIDELITY MODE\n"
                f"Do not redesign the garment.\n"
                f"This is a product photography task, not a fashion redesign task.\n"
                f"The generated garment must be visually identical to the source garment.\n"
                f"Only change: model pose, background, camera angle.\n"
                f"Do not change the garment itself.\n"
                f"STRICT GARMENT PRESERVATION MODE!\n"
                f"WARNING: The previous generation failed validation on the following fields: {failed_fields_str}.\n"
                f"You must pay extreme attention to these fields and ensure they exactly match the uploaded garment reference images and garment specifications."
            )
            parts.insert(0, retry_prefix)

        return GPTPromptBuilder.clean_cinematic_wording("\n\n".join(parts))

    @staticmethod
    def build_strong_realism_prompt(
        garment_json: dict[str, Any],
        style: str,
        pose: str,
        has_model_reference: bool = True,
        selected_model_gender: str | None = None
    ) -> str:
        # Standardize style/pose description
        style_key = style.lower().strip()
        style_key = STYLE_COMPATIBILITY_MAPPING.get(style_key, style_key)
        style_desc = STYLE_OPTIONS.get(style_key, STYLE_OPTIONS["studio"])

        pose_key = pose.lower().strip()
        pose_desc = POSES.get(pose_key, POSES["front"])

        product_type = garment_json.get("product_type") or "garment"
        category = garment_json.get("category") or "garment"
        main_color = garment_json.get("main_color") or "original"
        secondary_color = garment_json.get("secondary_color") or "original accents"
        material = garment_json.get("material") or "original"
        fabric_texture = garment_json.get("fabric_texture") or "original"
        silhouette = garment_json.get("silhouette") or "original"
        length = garment_json.get("length") or "original"
        closure = garment_json.get("closure") or "original"
        pockets = garment_json.get("pockets") or "original"
        color_palette = garment_json.get("color_palette") or []
        special_details = garment_json.get("special_details") or []
        
        garment_area = garment_json.get("garment_area") or "upper_body"
        if garment_area == "lower_body":
            area_instruction = "Dress the model in this skirt as a lower-body garment only." if "skirt" in product_type.lower() or "юбк" in category.lower() else f"Dress the model in this {product_type} as a lower-body garment only."
            complement_rule = "Keep the upper-body clothing natural and simple."
            conversion_avoid = f"Do not turn the {product_type} into a top. Do not turn the {product_type} into pants." if "skirt" in product_type.lower() or "юбк" in category.lower() else f"Do not turn the {product_type} into a top."
        elif garment_area == "upper_body":
            area_instruction = f"Dress the model in this {product_type} as an upper-body garment only."
            complement_rule = "Keep the lower-body clothing natural and simple."
            conversion_avoid = f"Do not turn the {product_type} into a skirt. Do not turn the {product_type} into pants."
        else:
            area_instruction = f"Dress the model in this {product_type} as a full-body garment."
            complement_rule = ""
            conversion_avoid = f"Do not turn the {product_type} into a top. Do not turn the {product_type} into pants."

        # Reconstruct standard color-fabric-category phrasing
        product_desc = f"{main_color} {fabric_texture} {material} {product_type}"

        # Setup model profile with gender override
        gender_override_json = dict(garment_json)
        if has_model_reference and selected_model_gender:
            gender_override_json["gender"] = selected_model_gender
            model_profile = gender_override_json.get("model_profile") or {}
            model_profile["gender"] = selected_model_gender
            gender_override_json["model_profile"] = model_profile

        article_context_block = GPTPromptBuilder._article_context_block(gender_override_json)
        model_profile_block = GPTPromptBuilder._model_profile_block(gender_override_json, has_model_reference=has_model_reference)

        if has_model_reference:
            model_ref_inst = "Use image 1 as the exact model reference."
            product_ref_inst = "Use image 2 as the exact product reference."
        else:
            model_ref_inst = ""
            product_ref_inst = "Use image 1 as the exact product reference."

        prompt = f"""
CRITICAL GARMENT FIDELITY MODE
Do not redesign the garment.
This is a product photography task, not a fashion redesign task.
The generated garment must be visually identical to the source garment.
Only change: model pose, background, camera angle.
Do not change the garment itself.

{model_ref_inst}

{model_profile_block}

{product_ref_inst}

{article_context_block}

The product is a {product_desc}.
{area_instruction}

The {product_type} must start at the correct position and extend to {length} length.
Preserve {fabric_texture} texture, {main_color} color, {secondary_color}, {closure} closure, pockets, seams and {silhouette} silhouette.
Reference color palette: {", ".join(color_palette) if color_palette else "match the source product colors exactly"}.
Special details that must stay identical: {", ".join(special_details) if special_details else "all visible distressing, embellishments, logos and wash effects"}.
Do not recolor the garment.
Do not change denim wash.
Do not create darker or lighter denim.
Do not move rhinestones, embroidery, logos, pockets or seams.

{complement_rule}
{conversion_avoid}
Do not shorten the {product_type}.
Do not change the color.

Pose: {pose_desc}
Style: {style_desc}

The image must look like a real ecommerce product photograph taken with a real camera.
Natural skin texture.
Realistic face.
Normal human imperfections.
Realistic body proportions.
No CGI.
No 3D render.
No cartoon.
No illustration.
No plastic skin.
No overly smooth AI face.
No beauty retouching.
No fantasy fashion campaign.
""".strip()
        return GPTPromptBuilder.clean_cinematic_wording(prompt)

    @staticmethod
    def build_detail_prompt(garment_json: dict[str, Any], detail_type: str, style: str) -> str:
        category = "other"
        payload = json.dumps(garment_json, ensure_ascii=False).lower()
        if "denim" in payload or "jeans" in payload or "джин" in payload:
            category = "denim"
        elif any(kw in payload for kw in ["jacket", "coat", "куртк", "khoác"]):
            category = "jacket"
        elif any(kw in payload for kw in ["dress", "gown", "плать", "váy"]):
            category = "dress"
        elif any(kw in payload for kw in ["shirt", "рубаш", "sơ mi", "t-shirt", "tshirt"]):
            category = "shirt"

        priorities = []
        if category == "denim":
            priorities = ["distressing", "ripped areas", "wash pattern", "rhinestones", "studs"]
        elif category == "shirt":
            priorities = ["collar", "buttons", "embroidery", "logo"]
        elif category == "jacket":
            priorities = ["zipper", "pockets", "stitching", "logo"]
        elif category == "dress":
            priorities = ["fabric texture", "waist details", "embellishments"]

        detail_type_lower = detail_type.lower().strip()
        if detail_type_lower == "fabric_detail":
            focus_instr = "Extreme close-up shot focusing on fabric texture, stitching, seams, distressing, and wash effects."
        elif detail_type_lower == "logo_detail":
            focus_instr = "Extreme close-up shot focusing on logos, labels, embroidery, rhinestones, and embellishments."
        else:
            focus_instr = "Close-up shot focusing on product details: fabric, texture, logo, zipper, buttons, embroidery, rhinestones, and distressing."

        if priorities:
            focus_instr += f"\nSpecifically, prioritize showing: {', '.join(priorities)}."

        prompt = (
            "Create a professional ecommerce garment detail shot using the uploaded product reference.\n\n"
            f"{focus_instr}\n\n"
            "Focus tightly on the product. The image must show ONLY the garment itself, laid flat or as a close-up, with NO model, NO human body, NO head, hands, or limbs visible.\n\n"
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
        return GPTPromptBuilder.clean_cinematic_wording(prompt)

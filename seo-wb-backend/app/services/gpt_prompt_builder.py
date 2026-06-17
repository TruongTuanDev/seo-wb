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
    "full_front": "Full-front catalog image. Show the model full-body or three-quarter body in a clean balanced stance so the buyer understands the complete outfit styling. This must look distinct from any crop slot.",
    "side_45": "45-degree side catalog pose. Body turned slightly to reveal silhouette and side seam structure, face visible, full garment visible.",
    "walking": "Natural walking fashion catalog pose with a clean lifestyle background. One foot stepping forward, torso slightly shifting with motion, product clearly visible and visually different from a static front pose.",
    "back": "Back-facing catalog pose. Show the back of the garment clearly. Use only if product back image exists.",
    "hand_on_hip": "One hand on hip, fashion catalog stance, full garment visible.",
    "sitting": "Sitting on a simple white cube, professional catalog pose, garment clearly visible.",
    "banner_focus": "Product-focused marketplace banner crop. Clean ecommerce composition with the product as the dominant subject."
}

FOCUSED_POSES = {
    "front": "Front-facing product-focused crop. Keep the product straight to camera and let the product dominate the frame.",
    "crop_front": "Front-facing upper-abdomen-to-shoes product-focused crop. Start above the belly at the shirt hem or upper abdomen, keep visible space above the waistband, keep both legs and hems visible, and let the product dominate the frame.",
    "side_45": "45-degree product-focused crop. Keep the product visible from the side angle and let the product dominate the frame.",
    "crop_side_45": "45-degree side upper-abdomen-to-shoes product-focused crop. Start above the belly at the shirt hem or upper abdomen with visible space above the waistband. Show product width, silhouette, side seam and fit clearly. Make this look different from the front crop by rotating the hips/body to a real side angle.",
    "back": "Back-facing product-focused crop. Show the back of the product clearly and let the product dominate the frame.",
    "crop_back": "Back-facing upper-abdomen-to-shoes product-focused crop. Start above the lower back/waistband with visible space above the waistband. Show the back construction, full back waistband, pockets, seams, hem and fit clearly. Make this look different from the front crop by showing the rear view only.",
    "banner_focus": "Product-focused marketplace banner crop. Use a clean composition where the product dominates the frame."
}


class GPTPromptBuilder:
    @staticmethod
    def focused_pose_description(garment_json: dict[str, Any], pose: str) -> str:
        pose_key = pose.lower().strip()
        area = str(garment_json.get("garment_area") or "upper_body").lower().strip()

        if area == "upper_body":
            descriptions = {
                "front": "Front-facing upper-body product crop. Show neckline/collar, shoulders, sleeve length, cuffs, chest fit, front closure/print, body width and hem clearly. Crop from upper chest or shoulders to hips/upper thigh so the top dominates.",
                "crop_front": "Front-facing upper-body product crop. Show neckline/collar, shoulders, sleeve length, cuffs, chest fit, front closure/print, body width and hem clearly. Crop from upper chest or shoulders to hips/upper thigh so the top dominates.",
                "side_45": "45-degree upper-body product crop. Rotate the torso to reveal sleeve volume, armhole, side seam, fabric drape, garment thickness, hem length and fit while keeping the top dominant.",
                "crop_side_45": "45-degree upper-body product crop. Rotate the torso to reveal sleeve volume, armhole, side seam, fabric drape, garment thickness, hem length and fit while keeping the top dominant.",
                "back": "Back-facing upper-body product crop. Show back neckline/collar or hood, shoulder line, back panel, sleeves/cuffs, back hem, seams and rear details clearly.",
                "crop_back": "Back-facing upper-body product crop. Show back neckline/collar or hood, shoulder line, back panel, sleeves/cuffs, back hem, seams and rear details clearly.",
                "banner_focus": "Upper-body product banner crop. Keep the top as the main subject with clean marketplace composition and no lower-body distraction.",
            }
            return descriptions.get(pose_key, descriptions["front"])

        if area == "full_body":
            descriptions = {
                "front": "Front-facing full-garment/set product image. Keep every outfit component visible from neckline/shoulders to hem, including top part, bottom/skirt/trouser part, waist connection, sleeves/straps and full length. Minimal empty background.",
                "crop_front": "Front-facing full-garment/set product image. Keep every outfit component visible from neckline/shoulders to hem, including top part, bottom/skirt/trouser part, waist connection, sleeves/straps and full length. Minimal empty background.",
                "side_45": "45-degree full-garment/set product image. Show side silhouette, waistline or set transition, sleeve/strap shape, bottom width, garment length, hem movement and complete outfit structure.",
                "crop_side_45": "45-degree full-garment/set product image. Show side silhouette, waistline or set transition, sleeve/strap shape, bottom width, garment length, hem movement and complete outfit structure.",
                "back": "Back-facing full-garment/set product image. Show rear neckline, back panel, sleeve/strap back, waistline or set transition, bottom back shape, length, hem and complete outfit structure.",
                "crop_back": "Back-facing full-garment/set product image. Show rear neckline, back panel, sleeve/strap back, waistline or set transition, bottom back shape, length, hem and complete outfit structure.",
                "banner_focus": "Full-garment marketplace banner. Keep the complete outfit visible and dominant, using a clean composition with enough space for marketplace cropping.",
            }
            return descriptions.get(pose_key, descriptions["front"])

        return FOCUSED_POSES.get(pose_key, FOCUSED_POSES["front"])

    @staticmethod
    def product_focus_block(garment_json: dict[str, Any], product_focus: bool) -> str:
        if not product_focus:
            return ""
        area = str(garment_json.get("garment_area") or "upper_body").lower().strip()
        if area == "lower_body":
            framing = (
                "Frame primarily from the upper abdomen or shirt-hem level to the shoes. The lower-body product must occupy 75-85% of the image. "
                "The buyer should immediately understand the waist, pockets, leg width, length, hem and overall fit."
            )
            crop_rule = (
                "Do not deliver a full-body portrait for this slot. Crop out most or all of the face and most of the upper torso. "
                "Keep the shirt hem or upper belly area above the waistband visible, keep the waistband clearly below the top edge of the frame, and keep the shoes or hem near the lower part of the frame."
            )
        elif area == "full_body":
            framing = (
                "Show the complete full-body garment or coordinated set from neckline/shoulders to hem. The product must occupy 75-85% of the image. "
                "The buyer should immediately understand all outfit components: neckline/collar, sleeves/straps, top body, waistline or set transition, lower part, silhouette, length, movement and hem."
            )
            crop_rule = (
                "Do not turn this into a distant full-body portrait. Keep the entire outfit visible, but remove excessive empty space around the model. "
                "Do not crop away any component of a set, jumpsuit, dress, sarafan, or coordinated outfit."
            )
        else:
            framing = (
                "Frame primarily from upper chest/shoulders to hips or upper thigh depending on garment length. "
                "The upper-body product must occupy 75-85% of the image. The buyer should immediately understand neckline/collar/hood, shoulder line, sleeve length, cuffs, chest fit, closure or print, body width, hem and fabric details."
            )
            crop_rule = (
                "Do not deliver a distant full-body portrait for this slot. Crop out most or all of the legs when needed so the upper-body product dominates. "
                "Keep the product hem visible and do not let complementary bottoms become the main subject. Do not crop off sleeves, cuffs, collar, hood or hem."
            )
        return (
            "PRODUCT-FOCUSED CAMERA FRAMING:\n"
            f"{framing}\n"
            f"{crop_rule}\n"
            "Prioritize the product over the model's face and surrounding background.\n"
            "It is acceptable to crop out part or all of the face when needed to make the product dominant.\n"
            "Keep the complete product visible and do not crop any important product edge or detail."
        )

    @staticmethod
    def lifestyle_accessory_block(garment_json: dict[str, Any], pose: str) -> str:
        if pose.lower().strip() != "walking":
            return ""
        area = str(garment_json.get("garment_area") or "upper_body").lower().strip()
        if area == "lower_body":
            accessory_examples = "simple sneakers, loafers, school backpack, plain tote bag, or a minimal watch"
            protection = "Accessories and the top must never cover the waistband, pockets, leg silhouette, hem, or product fabric."
        elif area == "upper_body":
            accessory_examples = "simple jeans/trousers, minimal bag, watch, or clean shoes"
            protection = "Accessories and bottoms must never cover the neckline/collar/hood, shoulders, sleeves, cuffs, hem, front design, closure, print, logo, or product fabric."
        else:
            accessory_examples = "simple shoes, small bag, minimal watch, or other subtle ecommerce accessories"
            protection = "Accessories must never cover any outfit component, garment silhouette, neckline, waistline, set transition, hem, sleeves, or product fabric."
        return (
            "LIFESTYLE/WALKING STYLING:\n"
            "Use a clean real-world ecommerce background such as a minimal studio corner, school corridor, clean street, showroom, or simple interior.\n"
            f"You may add subtle relevant accessories such as {accessory_examples}.\n"
            "Accessories must be secondary and must not introduce large logos, text, luxury branding, props, clutter, or a different selling focus.\n"
            f"{protection}\n"
            "The product remains the main visual subject."
        )

    @staticmethod
    def complementary_styling_block(garment_json: dict[str, Any]) -> str:
        area = str(garment_json.get("garment_area") or "upper_body").lower().strip()
        if area == "lower_body":
            return (
                "COMPLEMENTARY OUTFIT STYLING:\n"
                "The uploaded lower-body garment is the product and must remain unchanged.\n"
                "You may replace or restyle only the model's upper-body clothing with a tasteful coordinated ecommerce top.\n"
                "The top must not cover the waistband, pockets, fit, or any product detail."
            )
        if area == "upper_body":
            return (
                "COMPLEMENTARY OUTFIT STYLING:\n"
                "The uploaded upper-body garment is the product and must remain unchanged.\n"
                "You may replace or restyle only the model's lower-body clothing with tasteful coordinated ecommerce bottoms.\n"
                "The bottoms must not cover the product hem, silhouette, side seams, cuffs, closure, print, logo, or any product detail.\n"
                "Never turn the upper-body product into a dress, jumpsuit, skirt, pants, or full outfit."
            )
        return (
            "FULL OUTFIT LOCK:\n"
            "The uploaded product is a full-body garment or coordinated set.\n"
            "Preserve every visible part of the outfit exactly and do not replace, remove, or redesign any component.\n"
            "For a coordinated set, keep the top and bottom as the same article family: same color/material logic, same trim, same fabric texture, same proportions and matching style.\n"
            "Do not split the set into unrelated clothing, do not swap only the top or only the bottom, and do not convert a dress/jumpsuit/set into separates unless the reference product is clearly separates."
        )

    @staticmethod
    def garment_identity_lock_block(garment_json: dict[str, Any]) -> str:
        area = str(garment_json.get("garment_area") or "upper_body").lower().strip()
        product_type = str(garment_json.get("product_type") or garment_json.get("category") or "garment").strip()
        if area == "lower_body":
            return (
                "LOWER-BODY PRODUCT IDENTITY LOCK:\n"
                f"The product is {product_type}. Preserve waistband height, front/back rise, leg width, length, hem, side seams, pockets, closure, pleats, darts, fabric weight and drape.\n"
                "Do not turn pants/jeans/shorts into a skirt or a top. Do not hide the waistband, pockets, leg shape, hem or fabric texture."
            )
        if area == "upper_body":
            return (
                "UPPER-BODY PRODUCT IDENTITY LOCK:\n"
                f"The product is {product_type}. Preserve neckline/collar/hood, shoulder line, sleeve length, cuffs, armholes, chest/body width, side seams, hem length, closure/buttons/zipper, pockets, print/logo/embroidery and fabric drape.\n"
                "Do not turn the top/shirt/jacket/hoodie into a dress, full outfit, pants, skirt or lower-body garment.\n"
                "Do not hide or crop off collar/hood, sleeves/cuffs, front closure, chest design, hem, side seams or product texture."
            )
        if area == "full_body":
            return (
                "FULL-BODY / SET PRODUCT IDENTITY LOCK:\n"
                f"The product is {product_type}. Preserve the complete outfit structure: neckline/collar/straps, shoulders, sleeves, torso/body section, waistline or set transition, bottom/skirt/trouser section, length, hem, closure, pockets, seams, fabric texture and matching trims.\n"
                "If this is a coordinated set, top and bottom must remain the same matching product family and neither component may be replaced by unrelated clothing.\n"
                "If this is a dress, sarafan, jumpsuit, or one-piece garment, do not split it into separate top and bottom pieces.\n"
                "Do not remove, redesign, shorten, or swap any visible component of the full-body product."
            )
        return ""

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
        variant_color_signature = garment_json.get("variant_color_signature") or {}
        is_variant_color = bool(variant_color_signature)
        color_rule = (
            f"Recolor only the target garment to the requested variant color: {garment_json.get('main_color') or 'target variant color'}."
            if is_variant_color
            else "Do not recolor the garment."
        )
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
{color_rule}
Do not turn embellished denim into plain denim.

Only change pose, model placement, camera angle, or background.
The product itself must remain visually identical to the source{" except for the requested variant color" if is_variant_color else ""}.
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
        pose_desc = (
            GPTPromptBuilder.focused_pose_description(garment_json, pose_key)
            if product_focus
            else POSES.get(pose_key, POSES["front"])
        )
        if not pose_desc:
            pose_desc = POSES.get(pose_key, POSES["front"])

        # Base Prompt emphasizing real photography
        if has_model_reference:
            model_reference_prompt = (
                "Use the first image as the exact model reference.\n"
                "Preserve the model's real face, identity, skin texture, body proportions and hairstyle.\n"
                "Do not lock the generated image to the original stance from the reference photo.\n"
                "Follow the requested pose, camera angle and framing for each output slot.\n\n"
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

        color_palette = garment_json.get("color_palette") or []
        special_details = garment_json.get("special_details") or []
        variant_color_signature = garment_json.get("variant_color_signature") or {}
        is_variant_color = bool(variant_color_signature)
        variant_palette = variant_color_signature.get("palette_hex") or color_palette
        variant_hex = variant_color_signature.get("dominant_hex") or ""
        secondary_color = garment_json.get("secondary_color") or ""
        variant_name = garment_json.get("main_color") or variant_color_signature.get("dominant_name") or "target variant color"
        variant_color_prompt = ""
        if is_variant_color:
            variant_color_prompt = (
                "VARIANT COLOR OVERRIDE:\n"
                f"- Final target garment color: {variant_name}.\n"
                f"- Target color hex/palette: {variant_hex or 'n/a'}"
                f"{', ' + ', '.join(variant_palette) if variant_palette else ''}.\n"
                "- Use the uploaded product reference images ONLY for product structure: category, silhouette, length, waist, pockets, seams, closure, fabric texture and details.\n"
                "- It is REQUIRED to recolor only the target garment from the structural reference color to the target variant color.\n"
                "- The structural reference may show an old colorway such as black, navy, white, beige, or denim blue. Ignore that old colorway and use the target variant color as final.\n"
                "- Do not recolor the model, skin, shoes, background, or complementary clothing.\n"
                "- Do not copy logos, drawstrings, short length, pockets, silhouette, or category from any color-reference image.\n"
                "- The same article must be shown; only the product color changes."
            )

        # Garment Rules (Requirement 7)
        garment_rules_prompt = (
            "Garment Rules:\n"
            "- preserve garment category\n"
            f"{'- preserve the target variant color' if is_variant_color else '- preserve color'}\n"
            "- preserve length\n"
            "- preserve texture\n"
            "- preserve pockets\n"
            "- preserve seams\n"
            "- preserve buttons/zipper\n"
            "- do not invent logos\n"
            "- do not change garment area"
        )
        if is_variant_color:
            color_lock_prompt = (
                "COLOR LOCK:\n"
                "The generated garment color must match the target variant color, not the old structural reference color.\n"
                "Recolor only the product garment to the target variant color.\n"
                "After applying the target variant color, do not make it darker, lighter, grey, black, or navy unless that is the target variant.\n"
                "Keep wash pattern, distressing pattern, stitching, pockets, seams, logos and embellishments from the original article.\n"
                "The generated garment must represent the same physical product in a different color."
            )
        else:
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
                "Preserve neckline/collar/hood, shoulder line, sleeves, cuffs, chest fit, front/back panels, closure, hem and fabric drape.\n\n"
                "Do not convert the upper-body product into a dress, jumpsuit, pants, skirt or full outfit.\n\n"
                "Keep shoes, face, hair, hands and body proportions unchanged.\n\n"
                "Lower-body clothing may be restyled only as complementary clothing and must not become the selling focus."
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
                f"Keep face, hair, hands and body proportions unchanged.\n\n"
                f"Upper-body clothing may be restyled only as complementary clothing.\n\n"
                f"{skirt_rule}\n\n"
                f"{pants_rule}\n\n"
                f"Remove or fully cover any conflicting original lower-body clothing on the model."
            )
        elif area == "full_body":
            area_prompt = (
                "Garment area: full body.\n\n"
                "Dress the model in the uploaded full-body garment.\n\n"
                "Preserve neckline/collar/straps, sleeves, torso section, waistline or set transition, bottom/skirt/trouser section, silhouette, length, hem, fabric, color and details.\n\n"
                "For coordinated sets, keep all components matching and do not replace only the top or only the bottom.\n\n"
                "Do not convert a dress, sarafan, jumpsuit, or coordinated set into an unrelated top, skirt, pants, shorts, or mixed outfit."
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
            variant_color_prompt,
            garment_rules_prompt,
            color_lock_prompt,
            GPTPromptBuilder.garment_identity_lock_block(garment_json),
            f"Style Setting:\n{style_desc}",
            f"Pose Instruction:\n{pose_desc}",
            GPTPromptBuilder.product_focus_block(garment_json, product_focus),
            GPTPromptBuilder.lifestyle_accessory_block(garment_json, pose),
            GPTPromptBuilder.complementary_styling_block(garment_json),
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
                f"The generated garment must be visually identical to the source garment{' except for the requested variant color' if is_variant_color else ''}.\n"
                f"Only change: model pose, background, camera angle, and complementary non-product clothing when explicitly allowed.\n"
                f"Do not change the garment itself{' except recoloring the target garment to the variant color' if is_variant_color else ''}.\n"
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
        selected_model_gender: str | None = None,
        product_focus: bool = False,
    ) -> str:
        # Standardize style/pose description
        style_key = style.lower().strip()
        style_key = STYLE_COMPATIBILITY_MAPPING.get(style_key, style_key)
        style_desc = STYLE_OPTIONS.get(style_key, STYLE_OPTIONS["studio"])

        pose_key = pose.lower().strip()
        pose_desc = (
            GPTPromptBuilder.focused_pose_description(garment_json, pose_key)
            if product_focus
            else POSES.get(pose_key, POSES["front"])
        )
        if not pose_desc:
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
        variant_color_signature = garment_json.get("variant_color_signature") or {}
        is_variant_color = bool(variant_color_signature)
        variant_palette = variant_color_signature.get("palette_hex") or color_palette
        variant_hex = variant_color_signature.get("dominant_hex") or ""
        variant_color_instruction = ""
        if is_variant_color:
            variant_color_instruction = (
                "VARIANT COLOR OVERRIDE:\n"
                f"The final target product color is {main_color}.\n"
                f"Target color hex/palette: {variant_hex or 'n/a'}"
                f"{', ' + ', '.join(variant_palette) if variant_palette else ''}.\n"
                "Use the product reference image for structure only and recolor only the target garment to this variant color.\n"
                "If the product reference image shows a different old colorway, ignore that old color and apply the target variant color as final.\n"
                "Do not copy logos, drawstrings, short length, silhouette or category from any separate color-reference image.\n"
            )
        
        garment_area = garment_json.get("garment_area") or "upper_body"
        if garment_area == "lower_body":
            area_instruction = "Dress the model in this skirt as a lower-body garment only." if "skirt" in product_type.lower() or "юбк" in category.lower() else f"Dress the model in this {product_type} as a lower-body garment only."
            complement_rule = "You may replace the upper-body clothing with a simple coordinated ecommerce top. Never cover the waistband or lower-body product details."
            conversion_avoid = f"Do not turn the {product_type} into a top. Do not turn the {product_type} into pants." if "skirt" in product_type.lower() or "юбк" in category.lower() else f"Do not turn the {product_type} into a top."
        elif garment_area == "upper_body":
            area_instruction = f"Dress the model in this {product_type} as an upper-body garment only."
            complement_rule = "You may replace the lower-body clothing with simple coordinated ecommerce bottoms. Never cover the upper-body product hem or details."
            conversion_avoid = f"Do not turn the {product_type} into a skirt. Do not turn the {product_type} into pants."
        else:
            area_instruction = f"Dress the model in this {product_type} as a full-body garment."
            complement_rule = "Keep the complete full-body garment or coordinated set unchanged. Do not replace any visible outfit component."
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
            model_ref_inst = (
                "Use image 1 as the exact model reference for identity, face and body proportions. "
                "Do not copy the original stance; instead follow the requested pose and framing for this slot."
            )
            product_ref_inst = (
                "Use image 2 as the exact product structure reference; apply the target variant color from garment_json."
                if is_variant_color
                else "Use image 2 as the exact product reference."
            )
        else:
            model_ref_inst = ""
            product_ref_inst = (
                "Use image 1 as the exact product structure reference; apply the target variant color from garment_json."
                if is_variant_color
                else "Use image 1 as the exact product reference."
            )

        prompt = f"""
CRITICAL GARMENT FIDELITY MODE
Do not redesign the garment.
This is a product photography task, not a fashion redesign task.
The generated garment must be visually identical to the source garment{" except for the requested variant color" if is_variant_color else ""}.
Only change: model pose, background, camera angle, and complementary non-product clothing when explicitly allowed.
Do not change the garment itself{" except recoloring the target garment to the variant color" if is_variant_color else ""}.

{model_ref_inst}

{model_profile_block}

{product_ref_inst}

{article_context_block}

{variant_color_instruction}

{GPTPromptBuilder.garment_identity_lock_block(garment_json)}

The product is a {product_desc}.
{area_instruction}

The {product_type} must start at the correct position and extend to {length} length.
Preserve {fabric_texture} texture, {main_color} color, {secondary_color}, {closure} closure, pockets, seams and {silhouette} silhouette.
Reference color palette: {", ".join(color_palette) if color_palette else "match the source product colors exactly"}.
Special details that must stay identical: {", ".join(special_details) if special_details else "all visible distressing, embellishments, logos and wash effects"}.
{"Recolor only the target garment to the variant color. Do not keep the old reference color if it differs from the target variant." if is_variant_color else "Do not recolor the garment."}
Do not change denim wash.
Do not create darker or lighter denim.
Do not move rhinestones, embroidery, logos, pockets or seams.

{complement_rule}
{conversion_avoid}
Do not shorten the {product_type}.
{"Do not change away from the target variant color." if is_variant_color else "Do not change the color."}

Pose: {pose_desc}
Style: {style_desc}

{GPTPromptBuilder.product_focus_block(garment_json, product_focus)}

{GPTPromptBuilder.lifestyle_accessory_block(garment_json, pose)}

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
        elif any(kw in payload for kw in ["pants", "trousers", "shorts", "skirt", "брюк", "джин", "шорт", "юбк"]):
            category = "bottoms"

        priorities = []
        if category == "denim":
            priorities = [
                "waistband",
                "front closure",
                "button",
                "zipper",
                "pockets",
                "side seams",
                "hem",
                "distressing",
                "ripped areas",
                "wash pattern",
                "rhinestones",
                "studs",
            ]
        elif category == "shirt":
            priorities = ["neckline", "collar", "shoulder seams", "sleeves", "cuffs", "buttons", "hem", "embroidery", "logo"]
        elif category == "jacket":
            priorities = ["collar or hood", "zipper", "buttons", "pockets", "cuffs", "hem", "lining edge", "stitching", "logo"]
        elif category == "dress":
            priorities = ["neckline", "sleeves or straps", "waist details", "skirt/body section", "hem", "fabric texture", "embellishments"]
        elif category == "bottoms":
            priorities = ["waistband", "front closure", "button", "zipper", "pockets", "side seams", "leg width", "hem", "fabric texture"]

        detail_type_lower = detail_type.lower().strip()
        if detail_type_lower == "fabric_detail":
            focus_instr = "Extreme close-up shot focusing on fabric texture, stitching, seams, distressing, and wash effects."
        elif detail_type_lower == "logo_detail":
            focus_instr = "Extreme close-up shot focusing on logos, labels, embroidery, rhinestones, and embellishments."
        else:
            focus_instr = "Close-up shot focusing on product details: fabric, texture, logo, zipper, buttons, embroidery, rhinestones, and distressing."

        if priorities:
            focus_instr += f"\nSpecifically, prioritize showing: {', '.join(priorities)}."

        area = str(garment_json.get("garment_area") or "").lower().strip()
        variant_color_signature = garment_json.get("variant_color_signature") or {}
        is_variant_color = bool(variant_color_signature)
        variant_hex = variant_color_signature.get("dominant_hex") or ""
        variant_palette = variant_color_signature.get("palette_hex") or garment_json.get("color_palette") or []
        variant_color_prompt = ""
        if is_variant_color:
            variant_color_prompt = (
                f"\nVariant color override: create the same product detail in {garment_json.get('main_color') or 'the target variant color'} "
                f"({variant_hex or 'n/a'}{', ' + ', '.join(variant_palette) if variant_palette else ''}). "
                "Use the uploaded product reference only for structure and detail placement. "
                "Do not copy any logo, drawstring, short length, category or design from a color-reference image."
            )
        if area == "lower_body":
            focus_instr += (
                "\nThis is a lower-body product detail shot. Show ONLY details from the pants, jeans, shorts, or skirt. "
                "Do not show a shirt, blouse, collar, neckline, chest, sleeves, or upper-body garment detail."
            )
        elif area == "upper_body":
            focus_instr += (
                "\nThis is an upper-body product detail shot. Show ONLY details from the shirt, top, jacket, blouse, hoodie, or sweater. "
                "Prioritize neckline/collar/hood, shoulders, sleeves/cuffs, closure, chest design, hem, fabric texture and stitching. "
                "Do not show pants, shorts, skirt, shoes, legs, or lower-body garment detail."
            )
        elif area == "full_body":
            focus_instr += (
                "\nThis is a full-body garment or coordinated-set product detail shot. Show ONLY details from the product itself. "
                "Prioritize neckline/collar/straps, sleeves, waistline or set transition, matching top/bottom trim, hem, closure, fabric texture and stitching. "
                "Do not isolate an unrelated shirt, pants, shoes, accessory, or non-product clothing item."
            )

        prompt = (
            "Create a professional ecommerce garment detail shot using the uploaded product reference.\n\n"
            f"{focus_instr}\n\n"
            "Focus tightly on the product. The image must show ONLY the garment itself, laid flat or as a close-up, with NO model, NO human body, NO head, hands, or limbs visible.\n\n"
            f"{variant_color_prompt}\n\n"
            f"{'Preserve exact variant product color' if is_variant_color else 'Preserve exact product color'}, fabric texture, logo/text, seams, pockets and closures.\n\n"
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

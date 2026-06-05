from app.services.gpt_prompt_builder import GPTPromptBuilder


def test_lower_body_catalog_poses_are_waist_down():
    garment_json = {
        "product_type": "jeans",
        "category": "pants",
        "garment_area": "lower_body",
        "main_color": "black",
        "material": "denim",
    }

    prompt = GPTPromptBuilder.build_prompt(
        garment_json=garment_json,
        style="studio",
        pose="front",
        output_type="catalog",
    )
    assert "waist down" in prompt.lower()

    side_prompt = GPTPromptBuilder.build_prompt(
        garment_json=garment_json,
        style="studio",
        pose="side_45",
        output_type="catalog",
    )
    assert "waist down" in side_prompt.lower()

    banner_prompt = GPTPromptBuilder.build_prompt(
        garment_json=garment_json,
        style="studio",
        pose="front",
        output_type="lifestyle",
    )
    assert "waist down" not in banner_prompt.lower()


def test_lower_body_retry_prompt_keeps_waist_down_catalog_crop():
    garment_json = {
        "product_type": "pants",
        "category": "pants",
        "garment_area": "lower_body",
        "main_color": "black",
        "material": "cotton",
    }

    prompt = GPTPromptBuilder.build_strong_realism_prompt(
        garment_json=garment_json,
        style="studio",
        pose="back",
        output_type="catalog",
    )

    assert "waist down" in prompt.lower()

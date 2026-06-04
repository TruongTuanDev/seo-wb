from typing import Any, Dict, List
from app.schemas.card import ProductInput

def infer_body_type(
    category: str,
    gender: str,
    title: str,
    description: str,
    sizes: List[str],
    fit_type: str
) -> str:
    cat_text = f"{category} {title} {description} {fit_type}".lower()
    
    # 1. Check plus size keywords
    if any(x in cat_text for x in ["plus size", "plus-size", "большие размеры", "большой размер", "xxl", "3xl", "4xl", "5xl"]):
        return "plus_size"
        
    # 2. Check oversized / heavy keywords
    if any(x in cat_text for x in ["oversized", "oversize", "оверсайз", "свободный крой", "loose", "baggy"]):
        return "heavy"
        
    # 3. Check athletic / sport keywords
    if any(x in cat_text for x in ["sport", "gym", "athletic", "спортивный", "фитнес", "атлетический", "muscular"]):
        return "athletic"
        
    # 4. Check petite keywords
    if any(x in cat_text for x in ["petite", "мини", "для миниатюрных", "маленький рост", "xxs", "xs"]):
        return "petite"
        
    # 5. Check slim keywords
    if any(x in cat_text for x in ["slim", "облегающий", "приталенный", "узкий"]):
        return "slim"
        
    # 6. Check sizes list
    if sizes:
        sizes_clean = [str(s).upper().strip() for s in sizes]
        if any(s in ["XXS", "XS", "32", "34", "40"] for s in sizes_clean):
            return "petite"
        if any(s in ["S", "36", "42"] for s in sizes_clean):
            return "slim"
        if any(s in ["XL", "XXL", "XXXL", "3XL", "4XL", "5XL", "50", "52", "54", "56", "58"] for s in sizes_clean):
            return "plus_size"
            
    # 7. Check solid keywords
    if any(x in cat_text for x in ["solid", "heavyweight", "плотный", "плотная ткань"]):
        return "solid"
        
    return "average"

def recommend_for_product(raw_analysis: Dict[str, Any], user_input: ProductInput) -> Dict[str, str]:
    # Extract fields
    category = (user_input.category or raw_analysis.get("category") or "").strip().lower()
    gender = (user_input.gender or raw_analysis.get("gender") or "").strip().lower()
    title = (user_input.note or raw_analysis.get("product_name") or "").strip().lower()
    description = (user_input.note or "").strip().lower()
    
    # Extract sizes and fit
    sizes = user_input.sizes or []
    if not sizes and raw_analysis.get("sizes"):
        raw_sizes = raw_analysis.get("sizes")
        if isinstance(raw_sizes, list):
            sizes = [str(x.get("techSize") or x.get("wbSize") or "") for x in raw_sizes if isinstance(x, dict)]
            
    fit_type = raw_analysis.get("fit_type") or ""
    
    # 1. Determine garmentType
    from app.services.virtual_try_on import resolve_garment_type
    garment_type = resolve_garment_type(category)
    
    # 2. Determine backgroundStyle based on keywords
    background = "streetwear"  # Default fallback
    cat_text = f"{category} {title} {description}"
    
    if any(x in cat_text for x in ["худи", "свитшот", "толстовк", "джемпер", "свитер", "пуловер", "кардиган", "hoodie", "streetwear"]):
        background = "streetwear"
    elif any(x in cat_text for x in ["куртк", "пальто", "пиджак", "жилет", "ветровк", "бомбер", "jacket", "urban"]):
        background = "urban"
    elif any(x in cat_text for x in ["рубаш", "блуз", "shirt", "office"]):
        background = "office"
    elif any(x in cat_text for x in ["плать", "сарафан", "юбк", "dress", "boutique"]):
        background = "boutique"
    elif any(x in cat_text for x in ["детск", "малыш", "kids", "child", "playroom"]):
        background = "playroom"
    elif any(x in cat_text for x in ["пижам", "халат", "ночн", "nightwear", "sleepwear", "bedroom"]):
        background = "bedroom"
    elif any(x in cat_text for x in ["спорт", "gym", "sport", "фитнес"]):
        background = "gym"
    elif any(x in cat_text for x in ["вечерн", "luxury", "premium", "торжеств"]):
        background = "premium_studio"
    else:
        # Fallback based on garment type
        if garment_type == "upper_body":
            background = "streetwear"
        elif garment_type == "lower_body":
            background = "urban"
        else:
            background = "boutique"
            
    # 3. Determine recommendedPosePack
    pose_pack = "fashion"
    
    # 4. Determine recommendedModelGender
    model_gender = "female"
    if any(x in gender for x in ["муж", "male", "boy", "men"]):
        model_gender = "male"
    elif any(x in gender for x in ["жен", "female", "girl", "women"]):
        model_gender = "female"
    else:
        if any(x in cat_text for x in ["мужск", "для мужчин", "male", "men"]):
            model_gender = "male"
            
    # 5. Infer recommendedBodyType
    body_type = infer_body_type(category, gender, title, description, sizes, fit_type)
            
    age_group = "adult"
    if any(x in cat_text for x in ["teen", "youth", "trẻ", "young", "student"]):
        age_group = "young_adult"
    elif any(x in cat_text for x in ["kids", "child", "детск", "bé", "baby"]):
        age_group = "teen"

    return {
        "garmentType": garment_type,
        "recommendedBackground": background,
        "recommendedPosePack": pose_pack,
        "recommendedModelGender": model_gender,
        "recommendedBodyType": body_type,
        "recommendedAgeGroup": age_group,
        "recommendedEthnicity": "russian",
        "recommendedModelStyle": "real russian ecommerce model"
    }

def recommend_for_product_dict(analysis_dict: Dict[str, Any]) -> Dict[str, str]:
    # Dict-only version for backwards-compatibility loads
    category = (analysis_dict.get("category") or "").strip().lower()
    gender = (analysis_dict.get("gender") or "").strip().lower()
    title = (analysis_dict.get("product_name") or "").strip().lower()
    
    raw_sizes = analysis_dict.get("sizes") or []
    sizes = []
    if isinstance(raw_sizes, list):
        sizes = [str(x.get("techSize") or x.get("wbSize") or "") for x in raw_sizes if isinstance(x, dict)]
        
    fit_type = analysis_dict.get("fit_type") or ""
    
    from app.services.virtual_try_on import resolve_garment_type
    garment_type = resolve_garment_type(category)
    
    background = "streetwear"
    cat_text = f"{category} {title}"
    
    if any(x in cat_text for x in ["худи", "свитшот", "толстовк", "джемпер", "свитер", "пуловер", "кардиган", "hoodie", "streetwear"]):
        background = "streetwear"
    elif any(x in cat_text for x in ["куртк", "пальто", "пиджак", "жилет", "ветровк", "бомбер", "jacket", "urban"]):
        background = "urban"
    elif any(x in cat_text for x in ["рубаш", "блуз", "shirt", "office"]):
        background = "office"
    elif any(x in cat_text for x in ["плать", "сарафан", "юбк", "dress", "boutique"]):
        background = "boutique"
    elif any(x in cat_text for x in ["детск", "малыш", "kids", "child", "playroom"]):
        background = "playroom"
    elif any(x in cat_text for x in ["пижам", "халат", "ночн", "nightwear", "sleepwear", "bedroom"]):
        background = "bedroom"
    elif any(x in cat_text for x in ["спорт", "gym", "sport", "фитнес"]):
        background = "gym"
    elif any(x in cat_text for x in ["вечерн", "luxury", "premium", "торжеств"]):
        background = "premium_studio"
    else:
        if garment_type == "upper_body":
            background = "streetwear"
        elif garment_type == "lower_body":
            background = "urban"
        else:
            background = "boutique"
            
    pose_pack = "fashion"
    
    model_gender = "female"
    if any(x in gender for x in ["муж", "male", "boy", "men"]):
        model_gender = "male"
    elif any(x in gender for x in ["жен", "female", "girl", "women"]):
        model_gender = "female"
    else:
        if any(x in cat_text for x in ["мужск", "для мужчин", "male", "men"]):
            model_gender = "male"
            
    body_type = infer_body_type(category, gender, title, "", sizes, fit_type)
            
    age_group = "adult"
    if any(x in cat_text for x in ["teen", "youth", "trẻ", "young", "student"]):
        age_group = "young_adult"
    elif any(x in cat_text for x in ["kids", "child", "детск", "bé", "baby"]):
        age_group = "teen"

    return {
        "garmentType": garment_type,
        "recommendedBackground": background,
        "recommendedPosePack": pose_pack,
        "recommendedModelGender": model_gender,
        "recommendedBodyType": body_type,
        "recommendedAgeGroup": age_group,
        "recommendedEthnicity": "russian",
        "recommendedModelStyle": "real russian ecommerce model"
    }

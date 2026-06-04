import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


COLOR_MAP = {
    "đen": ("черный", "DEN"),
    "den": ("черный", "DEN"),
    "black": ("черный", "BLACK"),
    "черный": ("черный", "CHERNYI"),
    "чёрный": ("черный", "CHERNYI"),
    "xám": ("серый", "XAM"),
    "xam": ("серый", "XAM"),
    "ghi": ("серый", "XAM"),
    "gray": ("серый", "GRAY"),
    "grey": ("серый", "GRAY"),
    "серый": ("серый", "SERYI"),
    "đỏ": ("красный", "DO"),
    "do": ("красный", "DO"),
    "đỏ đô": ("бордовый", "DO_DO"),
    "do do": ("бордовый", "DO_DO"),
    "red": ("красный", "RED"),
    "красный": ("красный", "KRASNYI"),
    "бордовый": ("бордовый", "DO_DO"),
    "be": ("бежевый", "BE"),
    "kem": ("кремовый", "KEM"),
    "beige": ("бежевый", "BEIGE"),
    "бежевый": ("бежевый", "BEZHEVYI"),
    "кремовый": ("кремовый", "KEM"),
    "trắng": ("белый", "TRANG"),
    "trang": ("белый", "TRANG"),
    "white": ("белый", "WHITE"),
    "белый": ("белый", "BELYI"),
    "nâu": ("коричневый", "NAU"),
    "nau": ("коричневый", "NAU"),
    "brown": ("коричневый", "BROWN"),
    "коричневый": ("коричневый", "KORICHNEVYI"),
    "xanh": ("синий", "XANH"),
    "blue": ("синий", "BLUE"),
    "синий": ("синий", "SINII"),
}


@dataclass
class ColorIntent:
    value: str
    code: str


@dataclass
class ProductIntent:
    colors: list[ColorIntent] = field(default_factory=list)
    sizes: list[dict[str, str]] = field(default_factory=list)
    dimensions: dict[str, Any] = field(default_factory=dict)
    vendor_code: str | None = None

    def merge_missing(self, other: "ProductIntent") -> "ProductIntent":
        return ProductIntent(
            colors=self.colors or other.colors,
            sizes=self.sizes or other.sizes,
            dimensions=self.dimensions or other.dimensions,
            vendor_code=self.vendor_code or other.vendor_code,
        )


class ProductIntentParser:
    @classmethod
    def from_analysis(cls, analysis: Any) -> ProductIntent:
        colors = []
        seen = set()
        for item in getattr(analysis, "variant_colors", []) or []:
            value = str(item.get("value") or "").strip()
            code = str(item.get("code") or "").strip().upper()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            colors.append(ColorIntent(value=value, code=cls._color_code(value, code)))
        sizes = []
        for item in getattr(analysis, "sizes", []) or []:
            tech_size = str(item.get("techSize") or "").strip().upper()
            wb_size = str(item.get("wbSize") or tech_size).strip().upper()
            if tech_size:
                sizes.append({"techSize": tech_size, "wbSize": wb_size})
        return ProductIntent(
            colors=colors[:30],
            sizes=sizes[:30],
            dimensions=getattr(analysis, "package", {}) or {},
            vendor_code=getattr(analysis, "vendor_code_base", None),
        )

    @classmethod
    def parse(cls, text: str | None) -> ProductIntent:
        source = text or ""
        return ProductIntent(
            colors=cls._parse_colors(source),
            sizes=cls._parse_sizes(source),
            dimensions=cls._parse_dimensions(source),
            vendor_code=cls._parse_vendor_code(source),
        )

    @classmethod
    def _parse_colors(cls, text: str) -> list[ColorIntent]:
        lowered = cls._normalize_text(text)
        found: list[ColorIntent] = []
        seen = set()
        for token, (ru_value, code) in COLOR_MAP.items():
            if re.search(rf"(?<!\w){re.escape(cls._normalize_text(token))}(?!\w)", lowered) and ru_value not in seen:
                found.append(ColorIntent(ru_value, code))
                seen.add(ru_value)
        return found[:30]

    @staticmethod
    def _color_code(value: str, preferred: str | None = None) -> str:
        return ProductIntentParser.vendor_suffix_from_color(value)

    @staticmethod
    def vendor_suffix_from_color(value: str) -> str:
        translit = {
            "а": "a",
            "б": "b",
            "в": "v",
            "г": "g",
            "д": "d",
            "е": "e",
            "ё": "e",
            "ж": "zh",
            "з": "z",
            "и": "i",
            "й": "y",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o",
            "п": "p",
            "р": "r",
            "с": "s",
            "т": "t",
            "у": "u",
            "ф": "f",
            "х": "h",
            "ц": "ts",
            "ч": "ch",
            "ш": "sh",
            "щ": "sch",
            "ы": "y",
            "э": "e",
            "ю": "yu",
            "я": "ya",
            "ь": "",
            "ъ": "",
        }
        normalized = unicodedata.normalize("NFD", value.casefold())
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        parts = []
        for char in normalized:
            if char in translit:
                parts.append(translit[char])
            elif char.isalnum():
                parts.append(char)
            elif char in {" ", "-", "_", "/"}:
                parts.append("_")
        suffix = re.sub(r"_+", "_", "".join(parts)).strip("_").upper()
        return suffix[:24] or "COLOR"

    @staticmethod
    def _parse_sizes(text: str) -> list[dict[str, str]]:
        segment_match = re.search(r"(?:size|sizes|размер(?:ы)?|kích\s*thước)\s+(.+?)(?:\.|;|$)", text, re.IGNORECASE)
        segment = segment_match.group(1) if segment_match else text
        size_pattern = re.compile(r"\b(XS|S|M|L|XL|XXL|XXXL|\d{2,3})\s*(?:[-/]\s*(\d{2,3}|XS|S|M|L|XL|XXL|XXXL))?\b", re.IGNORECASE)
        candidates: list[dict[str, str]] = []
        seen = set()
        for tech, wb in size_pattern.findall(segment):
            if tech.isdigit() and len(tech) > 2:
                continue
            tech_clean = tech.upper()
            wb_clean = (wb or tech).upper()
            key = (tech_clean, wb_clean)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"techSize": tech_clean, "wbSize": wb_clean})
        return candidates[:30]

    @staticmethod
    def _parse_dimensions(text: str) -> dict[str, Any]:
        dimensions: dict[str, Any] = {}
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*[xх*]\s*(\d+(?:[.,]\d+)?)\s*[xх*]\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE)
        if match:
            dimensions["length"] = ProductIntentParser._number(match.group(1))
            dimensions["width"] = ProductIntentParser._number(match.group(2))
            dimensions["height"] = ProductIntentParser._number(match.group(3))

        weight_match = re.search(r"(?:nặng|weight|вес)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE)
        if weight_match:
            dimensions["weightBrutto"] = ProductIntentParser._number(weight_match.group(1))
        gram_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:g|гр|грам)", text, re.IGNORECASE)
        if gram_match and "weightBrutto" not in dimensions:
            dimensions["weightBrutto"] = ProductIntentParser._number(gram_match.group(1)) / 1000
        if dimensions.get("weightBrutto", 0) > 20:
            dimensions["weightBrutto"] = round(float(dimensions["weightBrutto"]) / 1000, 3)
        return dimensions

    @staticmethod
    def _parse_vendor_code(text: str) -> str | None:
        original_match = re.search(r"(?:mã\s*hàng|ma\s*hang|vendor(?:\s*code)?|артикул)\s*[:\-]?\s*([A-Za-zА-Яа-я0-9/_-]+)", text, re.IGNORECASE)
        if original_match:
            return original_match.group(1).strip()
        normalized = ProductIntentParser._normalize_text(text)
        match = re.search(r"(?:ma\s*hang|vendor(?:\s*code)?|артикул)\s*[:\-]?\s*([A-Za-zА-Яа-я0-9/_-]+)", normalized, re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _number(value: str) -> float:
        number = float(value.replace(",", "."))
        return int(number) if number.is_integer() else number

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFD", value.casefold())
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return normalized.replace("đ", "d").replace("ё", "е")

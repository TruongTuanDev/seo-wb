from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from math import sqrt
from typing import Iterable

from PIL import Image


RGB = tuple[int, int, int]

COLOR_NAME_MAP: dict[str, RGB] = {
    "black": (30, 30, 30),
    "white": (240, 240, 240),
    "grey": (140, 140, 140),
    "silver": (192, 192, 192),
    "beige": (214, 198, 168),
    "brown": (118, 82, 58),
    "red": (187, 54, 59),
    "burgundy": (110, 34, 48),
    "orange": (217, 122, 48),
    "yellow": (220, 191, 75),
    "green": (78, 134, 87),
    "olive": (105, 112, 62),
    "teal": (63, 132, 138),
    "blue": (74, 118, 184),
    "light blue": (183, 208, 229),
    "navy": (42, 57, 97),
    "purple": (116, 86, 144),
    "pink": (216, 157, 181),
}


@dataclass
class ColorSignature:
    dominant_hex: str
    dominant_name: str
    palette_hex: list[str]
    palette_rgb: list[RGB]


def extract_color_signature(
    image_bytes: bytes,
    garment_area: str | None = None,
    max_colors: int = 3,
) -> ColorSignature:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    cropped = _crop_to_garment_area(image, garment_area)
    cropped.thumbnail((240, 240), Image.Resampling.LANCZOS)
    quantized = cropped.convert("P", palette=Image.Palette.ADAPTIVE, colors=8).convert("RGB")
    counts = quantized.getcolors(maxcolors=quantized.width * quantized.height) or []
    sorted_colors = sorted(counts, key=lambda item: item[0], reverse=True)

    palette_rgb: list[RGB] = []
    for _, color in sorted_colors:
        rgb = tuple(int(channel) for channel in color[:3])
        if _should_skip_color(rgb):
            continue
        if not any(_rgb_distance(rgb, existing) < 18 for existing in palette_rgb):
            palette_rgb.append(rgb)
        if len(palette_rgb) >= max_colors:
            break

    if not palette_rgb:
        palette_rgb = [_average_rgb(cropped.getdata())]

    palette_hex = [_rgb_to_hex(color) for color in palette_rgb]
    dominant = palette_rgb[0]
    return ColorSignature(
        dominant_hex=_rgb_to_hex(dominant),
        dominant_name=_nearest_color_name(dominant),
        palette_hex=palette_hex,
        palette_rgb=palette_rgb,
    )


def compare_color_signatures(reference: ColorSignature, candidate: ColorSignature) -> dict[str, float]:
    dominant_delta = delta_e(reference.palette_rgb[0], candidate.palette_rgb[0])
    palette_delta = average_palette_delta_e(reference.palette_rgb, candidate.palette_rgb)
    return {
        "dominant_color_delta_e": round(dominant_delta, 2),
        "palette_delta_e": round(palette_delta, 2),
    }


def average_palette_delta_e(reference_palette: list[RGB], candidate_palette: list[RGB]) -> float:
    if not reference_palette or not candidate_palette:
        return 100.0
    distances = []
    for reference in reference_palette:
        distances.append(min(delta_e(reference, candidate) for candidate in candidate_palette))
    return sum(distances) / len(distances)


def delta_e(rgb_a: RGB, rgb_b: RGB) -> float:
    lab_a = _rgb_to_lab(rgb_a)
    lab_b = _rgb_to_lab(rgb_b)
    return sqrt(sum((a - b) ** 2 for a, b in zip(lab_a, lab_b)))


def _crop_to_garment_area(image: Image.Image, garment_area: str | None) -> Image.Image:
    width, height = image.size
    area = (garment_area or "").lower().strip()
    if area == "upper_body":
        box = (int(width * 0.2), int(height * 0.12), int(width * 0.8), int(height * 0.64))
    elif area == "lower_body":
        box = (int(width * 0.18), int(height * 0.34), int(width * 0.82), int(height * 0.96))
    else:
        box = (int(width * 0.16), int(height * 0.12), int(width * 0.84), int(height * 0.96))
    return image.crop(box)


def _should_skip_color(rgb: RGB) -> bool:
    r, g, b = rgb
    max_channel = max(rgb)
    min_channel = min(rgb)
    saturation = max_channel - min_channel
    brightness = (r + g + b) / 3
    return brightness > 245 or brightness < 18 or (saturation < 10 and brightness > 225)


def _average_rgb(pixels: Iterable[RGB]) -> RGB:
    values = list(pixels)
    if not values:
        return (128, 128, 128)
    total = len(values)
    return (
        int(sum(pixel[0] for pixel in values) / total),
        int(sum(pixel[1] for pixel in values) / total),
        int(sum(pixel[2] for pixel in values) / total),
    )


def _rgb_distance(a: RGB, b: RGB) -> float:
    return sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _rgb_to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _nearest_color_name(rgb: RGB) -> str:
    closest_name = "unknown"
    closest_distance = float("inf")
    for name, candidate in COLOR_NAME_MAP.items():
        distance = delta_e(rgb, candidate)
        if distance < closest_distance:
            closest_distance = distance
            closest_name = name
    return closest_name


def _rgb_to_lab(rgb: RGB) -> tuple[float, float, float]:
    x, y, z = _rgb_to_xyz(rgb)
    xr, yr, zr = x / 95.047, y / 100.0, z / 108.883

    fx = _lab_f(xr)
    fy = _lab_f(yr)
    fz = _lab_f(zr)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _rgb_to_xyz(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = (_pivot_rgb(channel / 255.0) for channel in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) * 100
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) * 100
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) * 100
    return x, y, z


def _pivot_rgb(value: float) -> float:
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _lab_f(value: float) -> float:
    if value > 0.008856:
        return value ** (1 / 3)
    return (7.787 * value) + (16 / 116)

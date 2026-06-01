"""Distill pages.json into a design tokens JSON (palette + type scale + format).

Usage:
    python extract_design_tokens.py <workspace_dir>

Reads:  <workspace>/pages.json
Writes: <workspace>/design_tokens.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def color_distance(a: str, b: str) -> float:
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return ((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2) ** 0.5


def merge_similar_colors(counter: Counter, threshold: float = 25.0) -> list[tuple[str, int]]:
    """Merge near-identical colors so the palette doesn't have 30 shades of black."""
    merged: list[tuple[str, int]] = []
    for hex_color, count in counter.most_common():
        matched = False
        for i, (existing, existing_count) in enumerate(merged):
            if color_distance(hex_color, existing) < threshold:
                merged[i] = (existing, existing_count + count)
                matched = True
                break
        if not matched:
            merged.append((hex_color, count))
    return merged


# Heuristic mapping from PDF font family stems to Google Fonts.
# Keys are lowercased, stripped of weight suffixes and subset prefixes.
# Values are picked for similar weight, x-height, and overall feel — not exact clones.
GOOGLE_FONT_MAP = {
    # Geometric / modernist sans
    "futura": "Montserrat",
    "futuraltpro": "Montserrat",
    "futuralt": "Montserrat",
    "circular": "Mulish",
    "circularstd": "Mulish",
    "gilroy": "Mulish",
    "gtwalsheim": "Mulish",
    "proximanova": "Mulish",
    "avenir": "Nunito Sans",
    "avenirnext": "Nunito Sans",
    "cerebrisans": "Manrope",
    # Neutral / grotesque sans
    "helvetica": "Inter",
    "helveticaneue": "Inter",
    "inter": "Inter",
    "söhne": "Inter",
    "soehne": "Inter",
    "suisseintl": "Inter",
    "neuehaasunica": "Inter",
    "opensans": "Open Sans",
    "opensauceone": "DM Sans",
    "opensauce": "DM Sans",
    "roboto": "Roboto",
    "segoeui": "Inter",
    "arial": "Inter",
    "lato": "Lato",
    "robotomono": "JetBrains Mono",
    # Display / serif
    "times": "Source Serif 4",
    "timesnewroman": "Source Serif 4",
    "timesnewromanps": "Source Serif 4",
    "georgia": "Lora",
    "garamond": "Cormorant Garamond",
    "playfair": "Playfair Display",
    "playfairdisplay": "Playfair Display",
    "notoserif": "Noto Serif",
    "notoserifdisplay": "Playfair Display",
    "canela": "Cormorant Garamond",
    "gtsectra": "Playfair Display",
    # Editorial italic display (looks handwritten-ish but is a refined italic serif)
    "dreamavenue": "Cormorant Garamond",
    # True script / handwritten
    "dancingscript": "Dancing Script",
    "pacifico": "Pacifico",
    "caveat": "Caveat",
    # Mono
    "courier": "JetBrains Mono",
    "couriernew": "JetBrains Mono",
    "sfmono": "JetBrains Mono",
    "menlo": "JetBrains Mono",
    "consolas": "JetBrains Mono",
}


def normalize_font_stem(name: str) -> str:
    """Strip subset prefix and common weight/style suffixes for lookup."""
    if "+" in name:
        name = name.split("+", 1)[1]
    stem = name.lower().replace(" ", "").replace("-", "").replace("_", "")
    for suffix in (
        "italic", "oblique", "bold", "semibold", "medium", "regular",
        "light", "thin", "book", "black", "extrabold", "ultrabold",
        "heavy", "extralight", "ultralight", "psmt", "ps", "mt",
    ):
        while stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def suggest_google_font(name: str) -> str | None:
    """Return a Google Fonts suggestion for an unknown PDF font, or None."""
    stem = normalize_font_stem(name)
    if not stem:
        return None
    if stem in GOOGLE_FONT_MAP:
        return GOOGLE_FONT_MAP[stem]
    # Try prefix matches (e.g. 'futuraltpro' was not in map but 'futura' is)
    for key, val in GOOGLE_FONT_MAP.items():
        if stem.startswith(key) and len(key) >= 4:
            return val
    return None


def bucket_sizes(sizes: list[float]) -> dict:
    """Bucket font sizes into rough roles. Heuristic only."""
    if not sizes:
        return {}
    counter = Counter(round(s) for s in sizes)
    sorted_sizes = sorted(counter.keys(), reverse=True)
    body = counter.most_common(1)[0][0]
    larger = [s for s in sorted_sizes if s > body]
    buckets = {"body": body}
    if larger:
        buckets["h1"] = larger[0]
    if len(larger) >= 2:
        buckets["h2"] = larger[1]
    if len(larger) >= 3:
        buckets["h3"] = larger[2]
    return buckets


def main():
    if len(sys.argv) != 2:
        print("Usage: extract_design_tokens.py <workspace_dir>", file=sys.stderr)
        sys.exit(1)

    workspace = Path(sys.argv[1]).resolve()
    pages_path = workspace / "pages.json"
    data = json.loads(pages_path.read_text())

    text_colors: Counter = Counter()
    shape_colors: Counter = Counter()
    fonts: Counter = Counter()
    sizes: list[float] = []
    font_sizes_by_font: dict[str, list[float]] = {}

    for page in data["pages"]:
        for span in page["text_spans"]:
            text_len = max(1, len(span["text"]))
            text_colors[span["color"]] += text_len
            fonts[span["font"]] += text_len
            sizes.append(span["size"])
            font_sizes_by_font.setdefault(span["font"], []).append(span["size"])
        for d in page["drawings"]:
            if d.get("fill"):
                rect = d.get("rect") or [0, 0, 0, 0]
                area = max(1, (rect[2] - rect[0]) * (rect[3] - rect[1]))
                shape_colors[d["fill"]] += int(area)
            if d.get("stroke"):
                shape_colors[d["stroke"]] += 10

    # Combine for palette: weight text by char count, shapes by area
    combined: Counter = Counter()
    for c, w in text_colors.items():
        combined[c] += w
    for c, w in shape_colors.items():
        combined[c] += w

    palette = [
        {"hex": hex_, "weight": weight}
        for hex_, weight in merge_similar_colors(combined)[:8]
    ]

    first_page = data["pages"][0]

    family_list = [
        {"name": name, "weight": count}
        for name, count in fonts.most_common(8)
    ]
    # Auto-suggest Google Font mapping for every observed family
    auto_overrides: dict[str, str] = {}
    for entry in family_list:
        suggestion = suggest_google_font(entry["name"])
        if suggestion:
            auto_overrides[entry["name"]] = suggestion

    tokens = {
        "page_format": {
            "width_pt": first_page["width_pt"],
            "height_pt": first_page["height_pt"],
            "orientation": first_page["orientation"],
            "aspect_ratio": round(first_page["width_pt"] / first_page["height_pt"], 4),
        },
        "palette": palette,
        "fonts": {
            "families": family_list,
            "size_scale": bucket_sizes(sizes),
        },
        "font_mapping_hint": (
            "font_overrides has been auto-populated with Google Font suggestions "
            "for each PDF font. Review them in references/font_mapping.md; tweak "
            "or remove entries if a better local font is available."
        ),
        "font_overrides": auto_overrides,
    }

    (workspace / "design_tokens.json").write_text(
        json.dumps(tokens, indent=2, ensure_ascii=False)
    )
    print(f"Wrote design tokens → {workspace / 'design_tokens.json'}")
    print(f"Palette ({len(palette)}): {[c['hex'] for c in palette]}")
    print(f"Fonts: {[f['name'] for f in tokens['fonts']['families']]}")


if __name__ == "__main__":
    main()

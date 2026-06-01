"""Fetch stock-photo replacements for each original image and apply color tinting.

Usage:
    python substitute_images.py <workspace_dir>

Supports two backends: Pexels (preferred) and Unsplash. Backend is chosen
in this order:
    1. Explicit per-image override: spec["source"] = "pexels" | "unsplash"
    2. Global env: IMAGE_BACKEND=pexels|unsplash
    3. Auto: whichever of PEXELS_API_KEY / UNSPLASH_ACCESS_KEY is set
       (Pexels wins if both are set)

Reads:
    <workspace>/image_map.json       (you write this — see SKILL.md stage 3)
    <workspace>/pages.json           (for original bbox aspect ratios)
Writes:
    <workspace>/new_images/<image_id>.jpg
"""

from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageEnhance

UNSPLASH_API = "https://api.unsplash.com/search/photos"
PEXELS_API = "https://api.pexels.com/v1/search"


# ---- Fetchers -------------------------------------------------------------

def fetch_unsplash(query: str, orientation: str, access_key: str) -> bytes:
    params = {
        "query": query,
        "orientation": orientation,  # landscape | portrait | squarish
        "per_page": 1,
        "content_filter": "high",
    }
    url = f"{UNSPLASH_API}?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Client-ID {access_key}"})
    with urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    results = body.get("results", [])
    if not results:
        raise RuntimeError(f"No Unsplash result for query: {query!r}")
    img_url = results[0]["urls"]["regular"]
    with urlopen(img_url, timeout=30) as resp:
        return resp.read()


def fetch_pexels(query: str, orientation: str, api_key: str) -> bytes:
    # Pexels uses 'square' instead of Unsplash's 'squarish'
    pexels_orient = {
        "landscape": "landscape",
        "portrait": "portrait",
        "squarish": "square",
        "square": "square",
    }.get(orientation, "landscape")

    params = {
        "query": query,
        "orientation": pexels_orient,
        "per_page": 1,
        "size": "large",  # ≥ 24MP; Pexels still serves a sensible URL
    }
    url = f"{PEXELS_API}?{urlencode(params)}"
    req = Request(url, headers={"Authorization": api_key})
    with urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    photos = body.get("photos", [])
    if not photos:
        raise RuntimeError(f"No Pexels result for query: {query!r}")
    # 'large' (~940px) is the sweet spot for 16:9 slides; use 'large2x' if
    # the bbox is huge, otherwise large is plenty and faster.
    src = photos[0]["src"]
    img_url = src.get("large2x") or src.get("large") or src["original"]
    with urlopen(img_url, timeout=30) as resp:
        return resp.read()


def fetch_image(query: str, orientation: str, *, backend: str,
                pexels_key: str | None, unsplash_key: str | None) -> bytes:
    if backend == "pexels":
        if not pexels_key:
            raise RuntimeError("Pexels selected but PEXELS_API_KEY is not set.")
        return fetch_pexels(query, orientation, pexels_key)
    if backend == "unsplash":
        if not unsplash_key:
            raise RuntimeError("Unsplash selected but UNSPLASH_ACCESS_KEY is not set.")
        return fetch_unsplash(query, orientation, unsplash_key)
    raise RuntimeError(f"Unknown backend: {backend!r}")


def resolve_backend(per_image_source: str | None, pexels_key: str | None,
                    unsplash_key: str | None) -> str:
    """Pick the backend for one image. See module docstring for the order."""
    if per_image_source:
        return per_image_source.lower()
    env_backend = os.environ.get("IMAGE_BACKEND", "").lower()
    if env_backend in {"pexels", "unsplash"}:
        return env_backend
    # Auto-detect — Pexels wins if both keys present.
    if pexels_key:
        return "pexels"
    if unsplash_key:
        return "unsplash"
    return ""  # signals "no backend available"


# ---- Image processing -----------------------------------------------------

def crop_to_aspect(img: Image.Image, target_aspect: float) -> Image.Image:
    w, h = img.size
    current = w / h
    if abs(current - target_aspect) < 0.01:
        return img
    if current > target_aspect:
        new_w = int(h * target_aspect)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_aspect)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))


def apply_tint(img: Image.Image, hex_color: str, opacity: float) -> Image.Image:
    """Blend a solid color overlay on top of the image."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    overlay = Image.new("RGB", img.size, (r, g, b))
    img_rgb = img.convert("RGB")
    return Image.blend(img_rgb, overlay, max(0.0, min(1.0, opacity)))


def find_original_aspect(image_id: str, pages: list[dict]) -> float | None:
    for page in pages:
        for img in page["images"]:
            if img["id"] == image_id and img.get("bbox"):
                x0, y0, x1, y1 = img["bbox"]
                w, h = x1 - x0, y1 - y0
                if h > 0:
                    return w / h
    return None


# ---- Driver ---------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        print("Usage: substitute_images.py <workspace_dir>", file=sys.stderr)
        sys.exit(1)

    workspace = Path(sys.argv[1]).resolve()
    image_map = json.loads((workspace / "image_map.json").read_text())
    pages = json.loads((workspace / "pages.json").read_text())["pages"]
    out_dir = workspace / "new_images"
    out_dir.mkdir(exist_ok=True)

    pexels_key = os.environ.get("PEXELS_API_KEY")
    unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY")

    if not pexels_key and not unsplash_key:
        print("No image backend credentials found.\n"
              "  - Pexels (preferred): https://www.pexels.com/api/  →  export PEXELS_API_KEY=...\n"
              "  - Unsplash (alt):     https://unsplash.com/developers  →  export UNSPLASH_ACCESS_KEY=...\n"
              "\nQueries that would be fetched:")
        for img_id, spec in image_map.items():
            print(f"  {img_id}: {spec.get('query')}  ({spec.get('orientation')})")
        print("\nOr drop manually-sourced JPEGs into new_images/ using "
              "the same image IDs as filenames.")
        sys.exit(2)

    succeeded = failed = 0
    for img_id, spec in image_map.items():
        query = spec["query"]
        orientation = spec.get("orientation", "landscape")
        tint = spec.get("tint")
        per_image_source = spec.get("source")
        backend = resolve_backend(per_image_source, pexels_key, unsplash_key)
        print(f"→ {img_id} [{backend}]: {query}")

        try:
            raw = fetch_image(query, orientation, backend=backend,
                              pexels_key=pexels_key, unsplash_key=unsplash_key)
        except Exception as e:
            print(f"  ! fetch failed: {e}", file=sys.stderr)
            failed += 1
            continue

        img = Image.open(BytesIO(raw))

        aspect = find_original_aspect(img_id, pages)
        if aspect:
            img = crop_to_aspect(img, aspect)

        if tint and tint.get("hex"):
            img = apply_tint(img, tint["hex"], float(tint.get("opacity", 0.25)))

        # Slight saturation knock-down to feel more designed
        img = ImageEnhance.Color(img.convert("RGB")).enhance(0.92)

        out_path = out_dir / f"{img_id}.jpg"
        img.save(out_path, "JPEG", quality=88)
        print(f"  saved {out_path}")
        succeeded += 1

    print(f"\nDone. {succeeded} succeeded, {failed} failed → {out_dir}")
    if failed:
        sys.exit(3)


if __name__ == "__main__":
    main()

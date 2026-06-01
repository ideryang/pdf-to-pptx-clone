"""Reconstruct a PPTX from pages.json + design_tokens.json + new_images/.

Usage:
    python build_pptx.py <workspace_dir> <output.pptx>

The PPT slide dimensions match the PDF exactly (in EMU). Each text span and
image is placed at the original bbox coordinates. Vector rectangles are
recreated as native PPT shapes so they remain editable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Emu, Pt

# 1 point = 12700 EMU
PT_TO_EMU = 12700


def pt_to_emu(v: float) -> int:
    return int(round(v * PT_TO_EMU))


def hex_to_rgb_color(h: str | None) -> RGBColor | None:
    if not h:
        return None
    h = h.lstrip("#")
    if len(h) != 6:
        return None
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def resolve_font(font_name: str, overrides: dict) -> str:
    if font_name in overrides:
        return overrides[font_name]
    # Strip subset prefixes like "ABCDEF+Helvetica-Bold"
    if "+" in font_name:
        font_name = font_name.split("+", 1)[1]
    return font_name


def is_bold(flags: int) -> bool:
    # PyMuPDF flag 2^4 = 16 is bold
    return bool(flags & 16)


def is_italic(flags: int) -> bool:
    return bool(flags & 2)


def add_text_span(slide, span: dict, overrides: dict, slide_width_pt: float):
    x0, y0, x1, y1 = span["bbox"]
    width = max(1.0, x1 - x0)
    height = max(1.0, y1 - y0)

    # Substituted Google Fonts often have wider metrics than the original PDF
    # font. Without slack, big headlines clip ("REPORT" → "REPOR"). Scale slack
    # to the original width so it works for both single words and lines.
    horizontal_slack = max(20.0, width * 0.25)
    box_width = min(width + horizontal_slack, slide_width_pt - x0)

    tb = slide.shapes.add_textbox(
        pt_to_emu(x0), pt_to_emu(y0),
        pt_to_emu(box_width), pt_to_emu(height + 4),
    )
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = False
    # Let PowerPoint shrink text rather than clipping if it still overflows.
    try:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_SHAPE_HEIGHT
    except Exception:
        pass

    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = span["text"]
    run.font.name = resolve_font(span["font"], overrides)
    run.font.size = Pt(span["size"])
    run.font.bold = is_bold(span.get("flags", 0))
    run.font.italic = is_italic(span.get("flags", 0))
    color = hex_to_rgb_color(span.get("color"))
    if color:
        run.font.color.rgb = color


def _apply_clip_polygon(src_path: Path, dest_path: Path,
                        polygon_local: list[tuple[float, float]]) -> None:
    """Apply a polygon alpha mask to src_path, save to dest_path. The polygon
    is in the image's local pixel coordinates (already mapped from bbox)."""
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(polygon_local, fill=255)
    img.putalpha(mask)
    img.save(dest_path, "PNG")


def add_image(slide, img_spec: dict, workspace: Path,
              slide_w: float, slide_h: float):
    bbox = img_spec.get("bbox")
    if not bbox:
        return
    x0, y0, x1, y1 = bbox

    # Clip to slide bounds. PDFs sometimes report images extending past the
    # page edge (negative y, x past width). PowerPoint accepts those but
    # renders them positioned weirdly.
    x0c, y0c = max(0.0, x0), max(0.0, y0)
    x1c, y1c = min(slide_w, x1), min(slide_h, y1)
    if x1c - x0c < 1 or y1c - y0c < 1:
        return

    img_id = img_spec["id"]
    new_path = workspace / "new_images" / f"{img_id}.jpg"
    original_path = workspace / "original_images" / f"{img_id}.png"
    path = new_path if new_path.exists() else original_path
    if not path.exists():
        print(f"  ! image file missing for {img_id}, skipping", file=sys.stderr)
        return

    # If the source PDF clipped this image to a non-rectangular polygon
    # (parallelogram, hexagon, etc.) — apply that as a PIL alpha mask before
    # inserting. PowerPoint doesn't natively support polygon-clipped pictures.
    clip = img_spec.get("clip_polygon")
    if clip:
        bbox_w = x1 - x0
        bbox_h = y1 - y0
        with Image.open(path) as probe:
            iw, ih = probe.size
        sx = iw / bbox_w
        sy = ih / bbox_h
        # Convert polygon from page coords to image-local pixel coords
        local = [((px - x0) * sx, (py - y0) * sy) for px, py in clip]
        clipped_path = workspace / "original_images" / f"{img_id}_clipped.png"
        _apply_clip_polygon(path, clipped_path, local)
        path = clipped_path

    slide.shapes.add_picture(
        str(path),
        pt_to_emu(x0c), pt_to_emu(y0c),
        pt_to_emu(x1c - x0c), pt_to_emu(y1c - y0c),
    )


def add_drawing(slide, d: dict, slide_w: float, slide_h: float):
    """Re-create simple vector rectangles. Skip complex paths for now."""
    rect = d.get("rect")
    if not rect:
        return
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return

    # Skip tiny artifacts (often anti-aliasing leftovers)
    if w < 1 and h < 1:
        return

    # Skip full-page background fills. PDFs frequently include 1–2 invisible
    # white rects covering the whole page; rebuilding them in PPT layers
    # underneath every image and creates a phantom redraw. Slide background
    # is white by default anyway.
    fill = (d.get("fill") or "").upper()
    covers_page = (x0 <= 1 and y0 <= 1
                   and x1 >= slide_w - 1 and y1 >= slide_h - 1)
    if covers_page and fill in {"#FFFFFF", ""}:
        return

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        pt_to_emu(x0), pt_to_emu(y0),
        pt_to_emu(w), pt_to_emu(h),
    )
    shape.line.fill.background()

    fill_color = hex_to_rgb_color(d.get("fill"))
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()

    stroke_color = hex_to_rgb_color(d.get("stroke"))
    if stroke_color:
        shape.line.color.rgb = stroke_color
        if d.get("width"):
            shape.line.width = pt_to_emu(d["width"])


def main():
    if len(sys.argv) != 3:
        print("Usage: build_pptx.py <workspace_dir> <output.pptx>", file=sys.stderr)
        sys.exit(1)

    workspace = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()

    pages = json.loads((workspace / "pages.json").read_text())["pages"]
    tokens = json.loads((workspace / "design_tokens.json").read_text())
    overrides = tokens.get("font_overrides", {})

    prs = Presentation()
    # Match PDF page size exactly
    fmt = tokens["page_format"]
    prs.slide_width = Emu(pt_to_emu(fmt["width_pt"]))
    prs.slide_height = Emu(pt_to_emu(fmt["height_pt"]))

    blank_layout = prs.slide_layouts[6]  # 6 is blank in default templates

    for page in pages:
        slide = prs.slides.add_slide(blank_layout)

        slide_w, slide_h = fmt["width_pt"], fmt["height_pt"]
        # z-order: drawings (background) → images → text (foreground)
        for d in page.get("drawings", []):
            add_drawing(slide, d, slide_w, slide_h)
        for img in page.get("images", []):
            add_image(slide, img, workspace, slide_w, slide_h)
        for span in page.get("text_spans", []):
            add_text_span(slide, span, overrides, slide_w)

    prs.save(out_path)
    print(f"Saved {out_path} ({len(pages)} slides, "
          f"{fmt['width_pt']:.0f}×{fmt['height_pt']:.0f}pt)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
bake_autofit.py — Pre-compute "shrink text on overflow" font scale and bake into XML.

Adopted from the sibling `pptx-design-fix` skill. Their insight: when
python-pptx (or any tool) modifies a PPTX, PowerPoint's runtime
computation of <a:normAutofit/>'s fontScale can silently fail and
text overflows. Pre-baking the scale into the XML makes shrink-on-
overflow reliable across PowerPoint / Keynote / LibreOffice.

Why:
  PowerPoint's `<a:normAutofit/>` ("Shrink text on overflow") relies on PowerPoint's
  runtime to compute fontScale & lnSpcReduction. If the XML lacks those attributes
  (just `<a:normAutofit/>`), or python-pptx modified the file disrupting cache,
  PowerPoint may fail to shrink and text overflows visibly.

  This script measures text against box dimensions using PIL with the actual TTF,
  computes the largest fontScale that fits, and writes it back. After baking,
  PowerPoint/LibreOffice/Keynote all render the shrunk size consistently.

Usage:
  python3 bake_autofit.py --pptx <file>                    # in-place
  python3 bake_autofit.py --pptx <in> --output <out>
  python3 bake_autofit.py --pptx <file> --verbose          # show every text frame
"""

import argparse
import subprocess
from pathlib import Path

from lxml import etree
from pptx import Presentation
from PIL import ImageFont

NSMAP = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
EMU_PER_INCH = 914400
PT_TO_PX = 96 / 72  # 1 pt = 96/72 px at standard 96 DPI
# PowerPoint 实际行高 ≈ font_size_pt × 1.15 / 72 inch（默认 lineSpacing 100% + 字体 leading）
# 用 size × 1.15 比用 Pillow 的 (ascent + descent) × 1.2 更接近 PPT 真实渲染高度。
PPT_LINE_HEIGHT_FACTOR = 1.15
# 高度容差：算出 0.10 内的轻微溢出不算溢出（PowerPoint 也允许 minor overflow）
HEIGHT_TOLERANCE = 1.10

_font_cache = {}


def find_font_file(family: str, bold: bool = False, italic: bool = False) -> "str|None":
    """Use fc-match to resolve a family + style to a TTF path."""
    key = (family.lower(), bold, italic)
    if key in _font_cache:
        return _font_cache[key]

    pattern = family
    style_parts = []
    if bold:
        style_parts.append("Bold")
    if italic:
        style_parts.append("Italic")
    if style_parts:
        pattern += ":style=" + " ".join(style_parts)

    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", pattern],
            capture_output=True, text=True, check=True,
        )
        path = out.stdout.strip()
        _font_cache[key] = path or None
        return _font_cache[key]
    except Exception:
        _font_cache[key] = None
        return None


def count_wrapped_lines(
    text: str, font_path: str, size_pt: float, box_width_in: float
) -> int:
    """Use Pillow to measure how many lines text wraps to in the given width."""
    if not text or not font_path:
        return 1

    size_px = max(1, int(round(size_pt * PT_TO_PX)))
    try:
        font = ImageFont.truetype(font_path, size_px)
    except Exception:
        return 1

    box_width_px = box_width_in * 96
    total_lines = 0
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        if not words or words == [""]:
            total_lines += 1
            continue
        current = words[0]
        para_lines = 1
        for word in words[1:]:
            test = current + " " + word
            bbox = font.getbbox(test)
            if (bbox[2] - bbox[0]) <= box_width_px:
                current = test
            else:
                para_lines += 1
                current = word
        total_lines += para_lines
    return total_lines


def measure_wrapped_height(
    text: str, font_path: str, size_pt: float, box_width_in: float
) -> float:
    """Wrapped text total height in inches. Uses PowerPoint-like line height."""
    n_lines = count_wrapped_lines(text, font_path, size_pt, box_width_in)
    line_h_in = size_pt * PPT_LINE_HEIGHT_FACTOR / 72
    return n_lines * line_h_in


def find_largest_fitting_scale(
    text: str, font_path: str, base_size_pt: float,
    box_w_in: float, box_h_in: float,
) -> int:
    """Try 100, 95, ..., 25 (%). Return largest pct whose wrapped text fits
    within box height (with HEIGHT_TOLERANCE slack)."""
    allowed_h = box_h_in * HEIGHT_TOLERANCE
    for pct in range(100, 24, -5):
        scaled = base_size_pt * pct / 100
        h = measure_wrapped_height(text, font_path, scaled, box_w_in)
        if h <= allowed_h:
            return pct
    return 25  # cap min


def bake_text_frame(shape, slide_idx: int, verbose: bool = False) -> "dict|None":
    """Compute and bake fontScale for a single shape's text frame, if needed."""
    if not shape.has_text_frame:
        return None

    tf = shape.text_frame
    bodyPr = tf._txBody.find(".//a:bodyPr", NSMAP)
    if bodyPr is None:
        return None
    normAutofit = bodyPr.find("a:normAutofit", NSMAP)
    if normAutofit is None:
        return None  # not set to shrink-on-overflow

    # Collect text + dominant font info
    text_parts: list[str] = []
    sizes: list[float] = []
    is_bold = False
    font_name: "str|None" = None
    for para in tf.paragraphs:
        para_text = ""
        for run in para.runs:
            para_text += run.text
            if run.font.size:
                sizes.append(run.font.size.pt)
            if run.font.bold:
                is_bold = True
            if run.font.name and not font_name:
                font_name = run.font.name
        text_parts.append(para_text)
    text = "\n".join(text_parts)

    if not text.strip() or not sizes:
        return None

    base_size = max(sizes)
    font_path = find_font_file(font_name or "sans", bold=is_bold)
    if not font_path:
        if verbose:
            print(f"  Slide {slide_idx} [{shape.name}]: font not found ({font_name!r}), skipping")
        return None

    # Account for body insets (lIns/rIns/tIns/bIns in EMU, default 91440 = 0.1")
    def _ins(attr, default):
        v = bodyPr.get(attr)
        return int(v) if v is not None else default

    box_w_in = (shape.width - _ins("lIns", 91440) - _ins("rIns", 91440)) / EMU_PER_INCH
    box_h_in = (shape.height - _ins("tIns", 45720) - _ins("bIns", 45720)) / EMU_PER_INCH

    # Two-gate sanity check to avoid false positives:
    #
    # Gate 1 — Skip single-line text entirely. Templates often have text boxes
    # that are narrower than the font's design line height as an anchor/baseline
    # trick (e.g. "01" in a 54pt box of 0.63"). PowerPoint doesn't shrink these,
    # and neither should we — only true multi-line wrapping overflow matters.
    #
    # Gate 2 — Even with multi-line wrap, only shrink if the total height
    # actually overflows beyond HEIGHT_TOLERANCE (10% slack).
    lines_at_100 = count_wrapped_lines(text, font_path, base_size, box_w_in)
    if lines_at_100 <= 1:
        pct = 100  # leave alone; single-line never overflows vertically in PPT
    else:
        height_at_100 = lines_at_100 * base_size * PPT_LINE_HEIGHT_FACTOR / 72
        if height_at_100 <= box_h_in * HEIGHT_TOLERANCE:
            pct = 100
        else:
            pct = find_largest_fitting_scale(text, font_path, base_size, box_w_in, box_h_in)

    old_scale = normAutofit.get("fontScale", "(unset)")
    normAutofit.set("fontScale", str(pct * 1000))
    if pct < 100:
        # lnSpcReduction proportional, capped at 20% (PowerPoint's typical max)
        lnSpc = min((100 - pct) * 500, 20000)
        normAutofit.set("lnSpcReduction", str(lnSpc))
    elif "lnSpcReduction" in normAutofit.attrib:
        del normAutofit.attrib["lnSpcReduction"]

    return {
        "slide": slide_idx,
        "shape": shape.name,
        "text_preview": text[:50].replace("\n", " | "),
        "base_size_pt": base_size,
        "box_in": (round(box_w_in, 2), round(box_h_in, 2)),
        "old_scale": old_scale,
        "new_scale_pct": pct,
        "changed": old_scale != str(pct * 1000),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pptx", required=True)
    parser.add_argument("--output", help="输出路径（默认 in-place 覆盖）")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    in_path = Path(args.pptx)
    out_path = Path(args.output) if args.output else in_path

    prs = Presentation(in_path)
    results = []
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            r = bake_text_frame(shape, i, verbose=args.verbose)
            if r:
                results.append(r)

    if not results:
        print("未发现含 normAutofit 的文本框，无需 bake。")
        return

    shrunk = [r for r in results if r["new_scale_pct"] < 100]
    print(f"扫描了 {len(results)} 个 shrink-on-overflow 文本框：")
    print(f"  - {len(results) - len(shrunk)} 个原字号 fit（scale=100%）")
    print(f"  - {len(shrunk)} 个需要缩字：")
    for r in shrunk:
        print(f"    Slide {r['slide']:2d} [{r['shape']}] base={r['base_size_pt']:.0f}pt "
              f"box={r['box_in'][0]}x{r['box_in'][1]}\" "
              f"→ scale {r['new_scale_pct']}% ({r['text_preview']!r})")

    prs.save(out_path)
    print(f"\n✓ 已保存到: {out_path}")


if __name__ == "__main__":
    main()

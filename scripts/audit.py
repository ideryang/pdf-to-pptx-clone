"""Audit a generated PPTX for geometric problems — overflow, overlap,
distorted images, very small text. Inspired by analyze.py from the sibling
`pptx-design-fix` skill, simplified to a single-script reporter that
either prints a clean bill of health or a numbered list of problems.

Usage:
    python audit.py <pptx_path>

Exit codes:
    0 — no issues
    1 — issues found (printed to stdout)
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image as PILImage
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

EMU_PER_INCH = 914400
EMU_PER_PT = 12700
SMALL_FONT_PT = 9        # text under this size is unreadable when projected
DISTORT_TOLERANCE = 0.05  # 5% aspect-ratio diff → image distorted


def emu_to_pt(v: int) -> float:
    return v / EMU_PER_PT


def shape_bbox_pt(shape):
    return (emu_to_pt(shape.left), emu_to_pt(shape.top),
            emu_to_pt(shape.left + shape.width),
            emu_to_pt(shape.top + shape.height))


def overlaps(a, b, tolerance_pt: float = 2.0):
    """True if rectangle a overlaps b by more than tolerance on both axes."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ox = min(ax1, bx1) - max(ax0, bx0)
    oy = min(ay1, by1) - max(ay0, by0)
    return ox > tolerance_pt and oy > tolerance_pt


def audit_pptx(pptx_path: Path) -> list[str]:
    prs = Presentation(pptx_path)
    slide_w = emu_to_pt(prs.slide_width)
    slide_h = emu_to_pt(prs.slide_height)
    issues: list[str] = []

    for i, slide in enumerate(prs.slides, 1):
        shape_info = []
        for shape in slide.shapes:
            bbox = shape_bbox_pt(shape)
            shape_info.append((shape, bbox))

            # Canvas overflow
            x0, y0, x1, y1 = bbox
            if x1 > slide_w + 1:
                issues.append(
                    f"Slide {i} · {shape.name!r}: right edge {x1:.0f}pt "
                    f"exceeds canvas width {slide_w:.0f}pt"
                )
            if y1 > slide_h + 1:
                issues.append(
                    f"Slide {i} · {shape.name!r}: bottom {y1:.0f}pt "
                    f"exceeds canvas height {slide_h:.0f}pt"
                )
            if x0 < -1:
                issues.append(
                    f"Slide {i} · {shape.name!r}: left {x0:.0f}pt off-slide"
                )
            if y0 < -1:
                issues.append(
                    f"Slide {i} · {shape.name!r}: top {y0:.0f}pt off-slide"
                )

            # Image distortion
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    with PILImage.open(io.BytesIO(shape.image.blob)) as img:
                        iw, ih = img.size
                    if iw > 0 and ih > 0 and shape.height > 0:
                        orig = iw / ih
                        disp = shape.width / shape.height
                        # Account for any existing crop — if the user
                        # already cover-cropped, the visible aspect matches
                        # the shape, so don't double-flag.
                        crop_w_factor = max(0.0001, 1 - shape.crop_left
                                            - shape.crop_right)
                        crop_h_factor = max(0.0001, 1 - shape.crop_top
                                            - shape.crop_bottom)
                        cropped_orig = (iw * crop_w_factor) / (ih * crop_h_factor)
                        if abs(cropped_orig - disp) > DISTORT_TOLERANCE:
                            issues.append(
                                f"Slide {i} · {shape.name!r}: image will "
                                f"stretch (orig aspect {orig:.2f}, displayed "
                                f"{disp:.2f}). Apply cover-crop."
                            )
                except Exception:
                    pass

            # Small text
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        if (run.text.strip() and run.font.size
                                and run.font.size.pt < SMALL_FONT_PT):
                            issues.append(
                                f"Slide {i} · {shape.name!r}: text "
                                f"\"{run.text[:30]}…\" is "
                                f"{run.font.size.pt:.0f}pt (below "
                                f"{SMALL_FONT_PT}pt readable threshold)"
                            )
                            break
                    else:
                        continue
                    break

        # Overlap detection — N² but slides have <50 shapes typically
        for ai in range(len(shape_info)):
            shape_a, bbox_a = shape_info[ai]
            # Ignore full-slide backgrounds (covers everything by design)
            if (bbox_a[2] - bbox_a[0] > slide_w * 0.9
                    and bbox_a[3] - bbox_a[1] > slide_h * 0.9):
                continue
            for bi in range(ai + 1, len(shape_info)):
                shape_b, bbox_b = shape_info[bi]
                if (bbox_b[2] - bbox_b[0] > slide_w * 0.9
                        and bbox_b[3] - bbox_b[1] > slide_h * 0.9):
                    continue
                if overlaps(bbox_a, bbox_b, tolerance_pt=2.0):
                    # Don't flag intentional overlap (e.g. text on a card)
                    # — only flag if both elements are *substantive* text
                    # frames (most common collision mode in our builds).
                    if (shape_a.has_text_frame and shape_b.has_text_frame
                            and shape_a.text_frame.text.strip()
                            and shape_b.text_frame.text.strip()):
                        issues.append(
                            f"Slide {i}: text frames {shape_a.name!r} and "
                            f"{shape_b.name!r} overlap"
                        )

    return issues


def main():
    if len(sys.argv) != 2:
        print("Usage: audit.py <pptx_path>", file=sys.stderr)
        sys.exit(2)
    pptx_path = Path(sys.argv[1])
    issues = audit_pptx(pptx_path)
    if not issues:
        print(f"OK · no geometric issues found in {pptx_path.name}")
        sys.exit(0)
    print(f"FOUND {len(issues)} issue(s) in {pptx_path.name}:")
    for i, msg in enumerate(issues, 1):
        print(f"  {i}. {msg}")
    sys.exit(1)


if __name__ == "__main__":
    main()

"""Extract every page of a PDF into structured JSON.

Usage:
    python extract_pdf.py <pdf_path> <workspace_dir>

Outputs into <workspace_dir>:
    pages.json
    original_images/page<N>_img<M>.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz  # PyMuPDF


def extract_clip_paths(page: fitz.Page) -> list[list[tuple[float, float]]]:
    """Parse the page's content stream for clipping path operators (W, W*)
    and return their polygons in top-down page coordinates.

    PyMuPDF's get_drawings() intentionally omits clip paths — they are only
    visible by walking the raw content stream. We track the CTM stack so
    polygons land in user-space coordinates that match every other bbox in
    pages.json.

    Returned polygons are deduplicated and filtered: full-page clips and
    pure rectangles are dropped (those are uninteresting for design
    inheritance — only the truly shaped clips, like parallelograms used to
    mask photos, are returned).
    """
    try:
        content = page.read_contents().decode("latin-1", errors="replace")
    except Exception:
        return []

    tokens = content.split()
    page_h = page.rect.height
    page_area = page.rect.width * page_h

    ctm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    ctm_stack: list[tuple] = []
    current_path: list[tuple[float, float]] = []
    captured: list[list[tuple[float, float]]] = []

    def apply(x, y):
        a, b, c, d, e, f = ctm
        return (a * x + c * y + e, b * x + d * y + f)

    def mul(m1, m2):
        a1, b1, c1, d1, e1, f1 = m1
        a2, b2, c2, d2, e2, f2 = m2
        return [a1 * a2 + b1 * c2, a1 * b2 + b1 * d2,
                c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
                e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2]

    nums: list[float] = []
    for tok in tokens:
        try:
            nums.append(float(tok))
            continue
        except ValueError:
            pass
        op = tok
        if op == "q":
            ctm_stack.append(tuple(ctm))
        elif op == "Q" and ctm_stack:
            ctm = list(ctm_stack.pop())
        elif op == "cm" and len(nums) == 6:
            ctm = mul(nums, ctm)
        elif op == "m" and len(nums) == 2:
            current_path.append(apply(nums[0], nums[1]))
        elif op == "l" and len(nums) == 2:
            current_path.append(apply(nums[0], nums[1]))
        elif op == "c" and len(nums) == 6:
            current_path.append(apply(nums[4], nums[5]))
        elif op == "re" and len(nums) == 4:
            x, y, w, h = nums
            for px, py in [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]:
                current_path.append(apply(px, py))
        elif op in ("W", "W*"):
            if current_path:
                # Flip Y (PDF user space has Y up) → top-down
                poly = [(round(x, 2), round(page_h - y, 2))
                        for x, y in current_path]
                # Deduplicate consecutive identical points
                deduped: list[tuple[float, float]] = []
                for p in poly:
                    if not deduped or deduped[-1] != p:
                        deduped.append(p)
                # Drop closing duplicate
                if len(deduped) > 1 and deduped[0] == deduped[-1]:
                    deduped = deduped[:-1]
                if len(deduped) >= 3:
                    # Filter: skip pure rectangles (uninteresting)
                    xs = {round(p[0], 1) for p in deduped}
                    ys = {round(p[1], 1) for p in deduped}
                    is_rect = len(xs) <= 2 and len(ys) <= 2
                    # Filter: skip full-page clips
                    bbox_w = max(p[0] for p in deduped) - min(p[0] for p in deduped)
                    bbox_h = max(p[1] for p in deduped) - min(p[1] for p in deduped)
                    if not is_rect and bbox_w * bbox_h < page_area * 0.95:
                        captured.append(deduped)
        elif op in ("n", "f", "F", "f*", "S", "s", "B", "B*", "b", "b*"):
            current_path = []
        nums = []

    # Dedup identical polygons
    seen = set()
    unique: list[list[tuple[float, float]]] = []
    for poly in captured:
        key = tuple(poly)
        if key not in seen:
            seen.add(key)
            unique.append(poly)
    return unique


def match_clip_to_image(clip_polys: list, images: list[dict]) -> None:
    """Assign each clip polygon to its most likely image by bbox overlap.
    Mutates the image dicts in place — adds 'clip_polygon' field (list of
    [x, y] points in top-down page coordinates) when a match is found.
    """
    for poly in clip_polys:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        clip_bbox = (min(xs), min(ys), max(xs), max(ys))
        best_img = None
        best_overlap = 0.0
        for img in images:
            if img.get("clip_polygon"):
                continue  # already assigned
            ib = img.get("bbox")
            if not ib:
                continue
            ix0, iy0, ix1, iy1 = ib
            # Compute IoU-ish: intersection area / clip-bbox area
            ox0 = max(clip_bbox[0], ix0)
            oy0 = max(clip_bbox[1], iy0)
            ox1 = min(clip_bbox[2], ix1)
            oy1 = min(clip_bbox[3], iy1)
            if ox1 <= ox0 or oy1 <= oy0:
                continue
            ov = (ox1 - ox0) * (oy1 - oy0)
            clip_area = (clip_bbox[2] - clip_bbox[0]) * (clip_bbox[3] - clip_bbox[1])
            if clip_area <= 0:
                continue
            score = ov / clip_area
            if score > best_overlap:
                best_overlap = score
                best_img = img
        if best_img is not None and best_overlap > 0.5:
            best_img["clip_polygon"] = [[p[0], p[1]] for p in poly]


def rgb_int_to_hex(c: int) -> str:
    r = (c >> 16) & 0xFF
    g = (c >> 8) & 0xFF
    b = c & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def extract_text_spans(page: fitz.Page) -> list[dict]:
    spans = []
    raw = page.get_text("dict")
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                spans.append({
                    "text": text,
                    "bbox": span["bbox"],  # [x0, y0, x1, y1] in points
                    "font": span.get("font", ""),
                    "size": round(span.get("size", 0), 2),
                    "color": rgb_int_to_hex(span.get("color", 0)),
                    "flags": span.get("flags", 0),  # bold/italic flags
                })
    return spans


def extract_images(page: fitz.Page, page_num: int, out_dir: Path) -> list[dict]:
    images = []
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        smask = img[1]  # soft mask xref; 0 if none
        try:
            pix = fitz.Pixmap(page.parent, xref)
            if pix.n - pix.alpha >= 4:  # CMYK → convert to RGB
                pix = fitz.Pixmap(fitz.csRGB, pix)
            # Combine with soft mask so PNG preserves transparency. PDFs
            # store image alpha in a separate xref; without this merge,
            # gradients/star shapes/cutouts come back with black surrounds
            # that then cover the rest of the slide.
            if smask:
                try:
                    mask_pix = fitz.Pixmap(page.parent, smask)
                    pix = fitz.Pixmap(pix, mask_pix)
                    mask_pix = None
                except Exception as e:
                    print(f"  ! page {page_num} img {img_index}: smask "
                          f"merge failed ({e}), saving without alpha",
                          file=sys.stderr)
            img_id = f"page{page_num}_img{img_index}"
            img_path = out_dir / f"{img_id}.png"
            pix.save(str(img_path))
            pix = None
        except Exception as e:
            print(f"  ! failed to save image {img_index} on page {page_num}: {e}",
                  file=sys.stderr)
            continue

        # Find rendered bboxes for this xref on this page
        rects = page.get_image_rects(xref)
        bbox = list(rects[0]) if rects else None

        images.append({
            "id": img_id,
            "xref": xref,
            "bbox": bbox,
            "path": str(img_path.relative_to(out_dir.parent)),
        })
    return images


def _coerce(v):
    """Recursively convert fitz.Rect / fitz.Point / tuples into plain lists."""
    if isinstance(v, (fitz.Rect, fitz.Point, fitz.Quad)):
        return list(v)
    if isinstance(v, (list, tuple)):
        return [_coerce(x) for x in v]
    return v


def extract_drawings(page: fitz.Page) -> list[dict]:
    """Extract vector shapes (lines, rectangles, curves)."""
    drawings = []
    for d in page.get_drawings():
        fill = d.get("fill")
        stroke = d.get("color")

        def to_hex(c):
            if c is None:
                return None
            r, g, b = [int(round(x * 255)) for x in c[:3]]
            return f"#{r:02X}{g:02X}{b:02X}"

        rect = d.get("rect")
        drawings.append({
            "type": d.get("type"),  # 'f' fill, 's' stroke, 'fs' both
            "rect": list(rect) if rect is not None else None,
            "fill": to_hex(fill),
            "stroke": to_hex(stroke),
            "width": d.get("width"),
            "items": [
                {"op": item[0], "pts": _coerce(list(item[1:]))}
                for item in d.get("items", [])
            ],
        })
    return drawings


def _is_complex_drawing(d: dict) -> bool:
    """A drawing is 'complex' (likely part of an icon) if it isn't a single
    rectangle. Rectangles get reproduced as native PPT shapes; complex paths
    can't be, so we rasterize them instead."""
    items = d.get("items", [])
    if len(items) == 1 and items[0]["op"] == "re":
        return False
    return True


def _bbox_near(a: list, b: list, threshold: float) -> bool:
    """True if two bboxes are within `threshold` points of each other on any
    axis (including overlap)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 + threshold < bx0 or bx1 + threshold < ax0
                or ay1 + threshold < by0 or by1 + threshold < ay0)


def _cluster_drawings(drawings: list[dict], threshold: float = 15.0) -> list[list[int]]:
    """Union-find clustering: drawings whose bboxes touch (or are within
    `threshold`) end up in the same cluster. Pure rectangles are excluded
    because we render them as native shapes."""
    indices = [i for i, d in enumerate(drawings)
               if _is_complex_drawing(d) and d.get("rect")]
    parent = {i: i for i in indices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ii, i in enumerate(indices):
        for j in indices[ii + 1:]:
            if _bbox_near(drawings[i]["rect"], drawings[j]["rect"], threshold):
                parent[find(i)] = find(j)

    clusters: dict[int, list[int]] = {}
    for i in indices:
        clusters.setdefault(find(i), []).append(i)
    return list(clusters.values())


def extract_icons(page: fitz.Page, page_num: int, drawings: list[dict],
                  text_spans: list[dict], image_specs: list[dict],
                  out_dir: Path) -> tuple[list[dict], set[int]]:
    """Rasterize clusters of complex vector drawings as PNG 'icons'.

    Returns (icon_image_entries, drawing_indices_to_drop). The build step
    inserts the PNGs as images and skips the original drawings, so the icon
    appears as it did in the PDF instead of being replaced by a bare rectangle.

    Heuristics for filtering:
      - cluster bbox between 10 and 250 pt on its longest side
        (smaller = anti-aliasing artifact; bigger = decorative element)
      - cluster doesn't sit entirely inside an image bbox
        (avoids capturing vector overlays on top of photos)
    """
    clusters = _cluster_drawings(drawings, threshold=15.0)
    icon_entries: list[dict] = []
    to_drop: set[int] = set()

    image_bboxes = [img["bbox"] for img in image_specs if img.get("bbox")]

    for idx, cluster in enumerate(clusters):
        # Union bbox of all drawings in cluster
        xs0, ys0, xs1, ys1 = [], [], [], []
        for i in cluster:
            r = drawings[i]["rect"]
            xs0.append(r[0]); ys0.append(r[1]); xs1.append(r[2]); ys1.append(r[3])
        bbox = [min(xs0), min(ys0), max(xs1), max(ys1)]
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_side = max(w, h)

        if max_side < 10 or max_side > 250:
            continue
        if w < 4 or h < 4:
            continue

        # Skip if entirely inside an image bbox (it's an overlay on a photo)
        inside_image = any(
            ib[0] - 1 <= bbox[0] and ib[1] - 1 <= bbox[1]
            and ib[2] + 1 >= bbox[2] and ib[3] + 1 >= bbox[3]
            for ib in image_bboxes
        )
        if inside_image:
            continue

        # Rasterize. Add a 2pt margin so antialiased edges don't get clipped.
        pad = 2
        clip = fitz.Rect(bbox[0] - pad, bbox[1] - pad,
                         bbox[2] + pad, bbox[3] + pad)
        # 4× the natural resolution so the icon looks crisp at slide scale
        mat = fitz.Matrix(4, 4)
        try:
            pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
        except Exception as e:
            print(f"  ! page {page_num} icon {idx}: rasterize failed: {e}",
                  file=sys.stderr)
            continue

        icon_id = f"page{page_num}_icon{idx}"
        icon_path = out_dir / f"{icon_id}.png"
        pix.save(str(icon_path))

        icon_entries.append({
            "id": icon_id,
            "kind": "icon",
            "bbox": [bbox[0] - pad, bbox[1] - pad,
                     bbox[2] + pad, bbox[3] + pad],
            "path": str(icon_path.relative_to(out_dir.parent)),
            "source_drawing_indices": cluster,
        })
        to_drop.update(cluster)

    return icon_entries, to_drop


def main():
    if len(sys.argv) != 3:
        print("Usage: extract_pdf.py <pdf_path> <workspace_dir>", file=sys.stderr)
        sys.exit(1)

    pdf_path = Path(sys.argv[1]).resolve()
    workspace = Path(sys.argv[2]).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    img_dir = workspace / "original_images"
    img_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)
    pages = []
    total_icons = 0
    total_clips = 0
    for i, page in enumerate(doc):
        w, h = page.rect.width, page.rect.height
        text_spans = extract_text_spans(page)
        images = extract_images(page, i + 1, img_dir)
        drawings = extract_drawings(page)

        # Parse clip paths from the content stream and attach the matching
        # polygon to each image. Templates like deck 212 use parallelogram-
        # shaped clip masks on photos as a signature design move; without
        # this step, both clone and sibling lose that visual language.
        clip_polys = extract_clip_paths(page)
        match_clip_to_image(clip_polys, images)
        total_clips += sum(1 for img in images if img.get("clip_polygon"))

        # Detect, rasterize, and substitute icon-like vector clusters
        icons, drop_indices = extract_icons(
            page, i + 1, drawings, text_spans, images, img_dir,
        )
        # Drop the original drawings that became icons so build_pptx doesn't
        # render them as bare rectangles on top of the rasterized icon.
        drawings = [d for k, d in enumerate(drawings) if k not in drop_indices]
        images = images + icons
        total_icons += len(icons)

        pages.append({
            "page_number": i + 1,
            "width_pt": w,
            "height_pt": h,
            "orientation": "portrait" if h >= w else "landscape",
            "text_spans": text_spans,
            "images": images,
            "drawings": drawings,
        })

    out = {
        "source": str(pdf_path),
        "page_count": len(pages),
        "pages": pages,
    }
    (workspace / "pages.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Extracted {len(pages)} pages → {workspace / 'pages.json'}")
    total_images = sum(len(p['images']) for p in pages)
    print(f"Saved {total_images} images ({total_icons} rasterized icons, "
          f"{total_clips} with clip polygons) → {img_dir}")


if __name__ == "__main__":
    main()

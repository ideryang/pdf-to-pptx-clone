# Post-build polish — audit, cover-crop, bake autofit

After `build_pptx.py` (clone mode) or a custom `build_sibling.py` finishes, run two more passes before declaring the deck done. Both are borrowed from the sibling `pptx-design-fix` skill and address PowerPoint failure modes that are easy to ship by accident.

## 1. Audit for geometric problems

```bash
python3 scripts/audit.py <output.pptx>
```

Reports image-distortion, off-canvas elements, sub-9pt text, and substantive text-frame overlaps. Exit code 1 if any issue is found, 0 if clean.

What it catches:
- **Image distortion**: an image whose original aspect ratio is more than 5% off from its display bbox. PowerPoint will stretch the picture — faces flatten, logos squash. Fix via cover-crop (see below).
- **Off-canvas elements**: any shape whose bbox crosses a slide edge. Almost always a layout bug.
- **Tiny text**: text smaller than 9pt is unreadable when projected. Raise it or remove it.
- **Overlapping text frames**: two text-bearing shapes whose bboxes overlap, both containing actual content. Filters out card-and-body intentional overlap, but if you stack two body paragraphs on top of each other, this catches it.

Treat the report as *signal*, not a hard gate — some overlaps are intentional (text on a card). But every finding should be reviewed.

## 2. Cover-crop images instead of stretching them

`build_pptx.py` now auto-applies cover-crop when inserting an image whose aspect ratio doesn't match its bbox. The technique uses PowerPoint's native `shape.crop_left/right/top/bottom` to do `object-fit: cover` — visually crops the image without resizing the shape. The layout grid stays intact; the image stops looking squashed.

For **sibling-mode** builds (which don't go through `build_pptx.py`), apply the same pattern manually after `add_picture`:

```python
def _apply_cover_crop(pic, image_path, bbox_w, bbox_h):
    with Image.open(image_path) as probe:
        iw, ih = probe.size
    img_aspect, bbox_aspect = iw / ih, bbox_w / bbox_h
    if abs(img_aspect - bbox_aspect) < 0.005:
        return
    pic.crop_left = pic.crop_right = pic.crop_top = pic.crop_bottom = 0
    if img_aspect > bbox_aspect:
        crop = (1 - bbox_aspect / img_aspect) / 2
        pic.crop_left = pic.crop_right = crop
    else:
        crop = (1 - img_aspect / bbox_aspect) / 2
        pic.crop_top = pic.crop_bottom = crop

pic = slide.shapes.add_picture(str(path), x, y, w, h)
_apply_cover_crop(pic, path, w / 12700, h / 12700)  # widths/heights in pt
```

**Skip cover-crop when a polygon clip is already baked into the PNG via PIL** — the visible content is already non-rectangular and the cover-crop would cut into it. (`build_pptx.py` skips this case automatically.)

## 3. Bake autofit so "shrink on overflow" works reliably

```bash
python3 scripts/bake_autofit.py <output.pptx>
```

PowerPoint's `<a:normAutofit/>` ("Shrink text on overflow") is supposed to compute font scale at render time. When python-pptx writes a file, that runtime computation can silently fail and text overflows visibly. This script measures each affected text frame with Pillow + the actual TTF, finds the largest scale that fits, and writes it into the XML. The same scale then renders identically in PowerPoint, Keynote, and LibreOffice.

Run this *after* `build_pptx.py` / `build_sibling.py`. It only modifies text frames that have `<a:normAutofit/>` already set, and only shrinks below 100% when the text genuinely overflows by more than 10%. Single-line labels are skipped.

## Suggested final sequence

```bash
python3 scripts/build_pptx.py <ws> <out.pptx>     # or your build_sibling.py
python3 scripts/bake_autofit.py <out.pptx>         # in-place
python3 scripts/audit.py <out.pptx>                # report any remaining issues
```

If the audit reports any issue you care about, fix it in the build script (not in the output PPTX) so the next regeneration is clean too. Both `audit.py` and `bake_autofit.py` are idempotent — re-running them on an already-good file is a no-op.

## Credit

`bake_autofit.py` is adopted essentially verbatim from the [`pptx-design-fix`](https://github.com/...) skill. The cover-crop technique and the audit pattern (analyse → report) are also their approach. Their skill is a complementary post-processing tool for fixing existing PPTX templates; this skill generates PPTX from PDF references. The two compose naturally — `pdf-to-pptx-clone` produces output, `pptx-design-fix` polishes it further if needed.

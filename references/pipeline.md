# Pipeline Edge Cases

Notes on things that go wrong in each stage and how to handle them.

## Stage 1 — extract_pdf.py

**CID / subset fonts**: PyMuPDF returns names like `ABCDEF+RealFontName`. The build script strips the prefix, but if you're reading `pages.json` directly to debug typography, expect to see these mangled names.

**Rotated text**: spans with rotation aren't preserved (the bbox is axis-aligned). For a PDF with significant rotated text, expect the rebuild to look off — flag this to the user and consider rasterizing affected pages as fallbacks.

**Text-as-paths**: some designers convert text to outlines before exporting PDF. That text is invisible to PyMuPDF's text extraction — it will appear as vector drawings, not text spans. Symptom: stage 1 reports zero text on a page that visibly has text. Workaround: rasterize that page as a single image and include it as a full-bleed image in the PPT (no editability, but visually correct).

**Embedded images vs. masks**: `get_images(full=True)` returns all xrefs, including alpha masks that aren't independently rendered. The script filters by `get_image_rects()` returning a bbox — if there's no rect, the image still saves but won't be placed in the PPT.

## Stage 2 — extract_design_tokens.py

**Black-on-white documents**: the palette will be dominated by `#000000` and `#FFFFFF`. The brand accent might be #5 or #6 in the list. Don't auto-pick the top color as the "brand" color — let the user (or Claude) eyeball the palette and reorder if needed.

**Anti-aliased shape colors**: if you see a lot of near-identical color shades after merging, raise the `threshold` in `merge_similar_colors` from 25 to 40.

**Font size buckets**: the heuristic picks the most common size as body. For a deck where the cover and chapter pages dominate (lots of huge text), this can mis-bucket. Override `font.size_scale` in `design_tokens.json` if the body size looks wrong.

## Stage 3 — substitute_images.py

**Decorative vs. content images**: small icons, logos, page-number ornaments shouldn't be replaced with Unsplash photos. Filter the `image_map.json` to only include the substantive images. For icons, you can either leave them out of `image_map.json` (the build will fall back to the original PNG) or replace them manually.

**Aspect ratio mismatch**: Unsplash returns images in the requested orientation but not the exact aspect of your bbox. The script center-crops, which usually works but can decapitate portraits. For tall portrait crops (e.g., 1:2 bbox), include framing hints in the query like "full body" or "headshot with space above head".

**Tint calibration**: if the original PDF uses photos in duotone (e.g., everything has a blue cast), use `tint.opacity` 0.3–0.5. For subtle warmth, 0.10–0.15 with a warm hex like `#F4E4C1`. If results look muddy, lower opacity rather than changing the hex.

## Stage 4 — build_pptx.py

**Text overflow**: PPT and PDF disagree on glyph metrics even for the same font. Headings near the right edge of their bbox can clip. The build adds 6pt of horizontal slack which catches most cases. If a specific heading still clips, widen its source bbox in `pages.json` before running stage 4.

**Z-order**: drawings render first (background), then images, then text. This matches most PDFs, but some designs layer text behind images (e.g., a logo behind a photo). For those, manually reorder the shapes in the resulting PPTX with PowerPoint's "Send to Back".

**Complex vector paths**: only rectangles are recreated as native PPT shapes. Curves, custom polygons, and SVG-like illustrations are skipped — they're left out entirely. If a page leans on vector illustration, render it as a PNG via PyMuPDF and place that as a full-bleed image instead. (Future enhancement: detect "vector-heavy" pages and auto-rasterize.)

**Slide size limits**: PowerPoint caps slide dimensions at 56 inches. If a PDF is larger than that (rare, but happens for printed posters), the build will fail. Scale down `width_pt` and `height_pt` proportionally in `design_tokens.json` and update `pages.json` coordinates by the same factor.

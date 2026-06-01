# Sibling Mode — Designing a New Deck from a Reference

The default pipeline (stages 1–4 in SKILL.md) is **clone mode**: pixel-faithful reconstruction. This document covers the other mode: building a *new* deck that is a clear design sibling of the reference — same level of polish, same storytelling rhythm, same visual sophistication — but with original content and tasteful variation. Trigger this when the user says things like "make a similar-style deck about X", "use this PDF's look but write new content", "inspired by this design".

## The core principle

A sibling deck inherits **structure** and **vocabulary** from the reference, while introducing **fresh choices** in the details:

| Inherit (keep recognizable) | Vary (keep fresh) |
|---|---|
| Layout patterns and compositional logic | Color palette (shifted, not copied) |
| Pacing — cover, section dividers, content density rhythm | Typography pairings |
| Visual sophistication and polish level | Spacing rhythm |
| Mood (corporate / editorial / playful / minimal) | Localized layout variations per slide |
| Image treatment style (full-bleed vs. cards, duotone, etc.) | Specific content and copy |

The result should feel like the reference's sibling — same designer's sensibility, different brief. Not a copy. Not unrelated.

## Workflow

1. **Run stages 1 + 2** of the clone pipeline on the reference PDF. You get `pages.json` (per-page structure) and `design_tokens.json` (palette, fonts, page format). Even if you're not going to clone, you need these as the design-language source of truth.

2. **Inventory layout patterns** from the reference. Open `pages.json` and look at each page's combination of (number of text spans, image bboxes, drawing geometry). Common categories:
   - **Cover**: dominant centered or left-aligned title, often with one supporting graphic; minimal nav
   - **Section divider**: a single huge label (often numbered "01 / 02 / 03") on a tinted or full-image background
   - **Content-with-image**: two-column or asymmetric split — text on one side, image on the other
   - **Data**: charts, numbers as hero elements, tight grid
   - **Quote / pull-out**: oversized italic or display type, attribution underneath
   - **Closing / contact**: contact info layout, often mirroring the cover
   
   Write this inventory down (mentally or in a note) as you'll reuse the count and rhythm in the new deck.

3. **Draft the narrative** for the new deck. Aim for ~15 slides. Build a coherent arc — what's the problem, why it matters, what we're proposing, how it works, what proof / metrics, what comes next, call to action. Keep the slide count and rhythm proportional to the reference (if reference had 3 section dividers across 10 slides, you have 4–5 across 15).

4. **Generate a new palette** that's a relative of the reference, not a clone. Concrete moves:
   - Shift the accent hue 20–60° on the color wheel (electric blue → teal or violet)
   - Keep the lightness contrast pattern (if reference is high-contrast white + bold accent, new deck should be too)
   - Add a single tertiary accent if the reference used only two colors
   - **Never** ship a deck where the palette is so close to the reference that they look interchangeable

5. **Pick typography** that pairs with the same family genre but isn't identical:
   - If reference is geometric sans → pick a different geometric sans (Futura → DM Sans, Mulish, Manrope)
   - If reference is editorial serif → pick a different editorial serif (Playfair → Cormorant Garamond, Fraunces)
   - Pair with a contrasting secondary (if reference paired bold display + neutral body, do the same with different choices)

6. **Source images** via Pexels (preferred) or Unsplash, using `scripts/substitute_images.py` with the same `image_map.json` schema as clone mode. For sibling decks, write queries that match the *new* topic, not the reference's subjects — same composition genre (close-up portrait / wide landscape / overhead workspace / etc.), different content. Insert images **thoughtfully** — they should drive layout decisions, not fill placeholder boxes after the fact. Pexels generally returns more design-considered photography than Unsplash for editorial / agency / studio decks, which is why it's the default backend; flip per-image with `"source": "unsplash"` when a specific query lands better there.

7. **Build the PPTX** using python-pptx directly. There is no scripted "build_sibling_pptx.py" because sibling-mode layouts are too varied to template; you compose each slide yourself referencing the tokens. The `scripts/build_pptx.py` is a useful library to crib from (page sizing in EMU, font/color helpers).

## Anti-patterns to actively avoid

Claude has a strong default aesthetic that drifts toward editorial, contemplative, magazine-style design. For a sibling deck of a *non-editorial* reference, this default is wrong. Even for editorial references, the default can feel generic.

**Do NOT** unless the reference visibly demands it:

- ❌ Anthropic-style editorial branding (warm tones + lots of breathing room + serif-driven hierarchy)
- ❌ Serif-first typography systems (default serif headings on every slide)
- ❌ Space Grotesk as the title face (overused; pick something with more character)
- ❌ Oversized contemplative layouts (single sentence centered on slide with mountains of whitespace)
- ❌ Excessive whitespace as a default — let the reference dictate density
- ❌ Poetic magazine-style composition (pull-quotes, dropcaps, gutter rules) unless the reference is literally a magazine
- ❌ Warm ivory or beige-heavy palettes (#F5F0E8 background, etc.)
- ❌ Muted editorial neutrals as the dominant palette
- ❌ Paper-like background tones (the "Substack newsletter" look)
- ❌ Soft luxury-tech color grading (everything desaturated, low-contrast pastels)

If the reference IS that aesthetic, fine — but then introduce variation through pacing, layout breaks, or photographic choices, not by leaning further into it.

## Content rules (always, never optional)

All placeholder rules from the user's brief apply unconditionally:

- People: **John Doe** (never invent realistic-looking names)
- Companies: **Acme Corp**
- Schools: **Example University**
- Phone: **+1 (234) 567-8910**
- Email: **no_reply@example.com**
- Address: **123 Your Street, Your City, USA**
- ZIP: **00000**
- No real brands, no real URLs, no real social handles, no recognizable third-party visual identities.

Even if the reference PDF contains real-looking names (e.g. "Presented by Pedro Ferrandes"), the new deck must use placeholders. Don't paraphrase the reference's names — replace them with the placeholder set above.

## Prefetch every photo in parallel before composing slides

Serial `urlretrieve(...)` for 15+ photos is the single biggest cause of slow sibling builds. Always declare every photo seed your build will need at the top of the script, then prefetch them all in a thread pool. After that, every `make_*_photo()` call hits a local file — instant.

```python
from concurrent.futures import ThreadPoolExecutor

PHOTO_SPECS = [
    ("cover_a",          1200, 1080),
    ("founder_office",    840,  960),
    ("product_card_1",    840,  440),
    # ... declare every photo you'll need
]

def prefetch_all():
    work = [(f"https://picsum.photos/seed/{s}/{w}/{h}",
             IMG_DIR / f"photo_{s}_{w}x{h}.jpg")
            for s, w, h in PHOTO_SPECS]
    work = [(u, d) for u, d in work if not d.exists()]
    if not work:
        return
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda uv: urlretrieve(uv[0], uv[1]), work))

prefetch_all()  # before any slide_xxx() calls
```

If you use Pexels instead of Picsum, the same pattern applies — fan the search requests out via a thread pool. Pexels free tier allows 200 requests/hour, far more than any single deck needs.

## Photo clip shapes are part of the design language

Designed PDFs frequently clip photos into non-rectangular shapes — parallelograms, hexagons, rounded rectangles, hard-edged cutouts. The clip shape carries as much design DNA as the palette or typography. A sibling deck that places plain rectangular photos against a reference that used parallelogram-clipped photos looks "off" in a way that's hard to articulate but immediately visible to designers.

**What the skill does for you**: `extract_pdf.py` parses the PDF content stream for `W` and `W*` operators, tracks the CTM stack, and attaches the resulting polygons to the images they clip. Each image entry in `pages.json` may include a `clip_polygon` field with vertices in top-down page coordinates. In **clone mode**, `build_pptx.py` automatically applies that polygon as a PIL alpha mask before inserting the picture — fidelity comes for free.

**What you do in sibling mode**: inspect `pages.json` for representative images. If their `clip_polygon` fields show a consistent shape vocabulary (e.g. parallelograms across multiple pages), reuse that vocabulary in your sibling build:

```python
def make_clipped_photo(seed, w, h, *, shape="parallelogram_right",
                        skew_frac=0.18):
    base = make_bw_photo(seed, w, h)
    img = Image.open(base).convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    skew = int(h * skew_frac)
    if shape == "parallelogram_right":
        points = [(skew, 0), (w, 0), (w - skew, h), (0, h)]
    elif shape == "parallelogram_left":
        points = [(0, 0), (w - skew, 0), (w, h), (skew, h)]
    # ...add hexagon, corner_cut, etc. as needed
    draw.polygon(points, fill=255)
    img.putalpha(mask)
    img.save(dest, "PNG")
```

The sibling doesn't have to copy the reference polygon vertex-for-vertex — that would be too literal. Match the shape *family* (parallelogram → parallelogram, hexagon → hexagon) and the lean direction, and the deck will read as a sibling rather than a clone or an unrelated piece.

## Imagery is not optional

A sibling deck that contains only PIL-generated shapes (rectangles, parallelograms, gradients, line drawings) reads as empty — even when the typography and layout are correct. Designers will say "it has no images." Always audit the deck against the reference: count how many slides in the reference have actual photography or substantive illustration. The sibling should hit at least that ratio.

Concrete moves:

- **Cover and closing**: always include a real image (B&W or toned photo) as a hero block, not just shape decoration.
- **Section / pillar / agenda pages**: pair the structural geometry with one photographic anchor — a banner strip, a side card, or a small block inside a colored card.
- **Match the reference's image treatment**: if the reference uses B&W high-contrast photography (deck 212), do the same. If it uses warm-toned editorial (deck 211), do warm-toned. If it uses dark cinematic (deck 215), do dark cinematic. Don't ship a sibling with photography in a treatment the reference didn't use.

Implementation pattern using Picsum (no API key) + PIL:

```python
def make_bw_photo(seed, w, h, contrast_cutoff=2):
    urlretrieve(f"https://picsum.photos/seed/{seed}/{w}/{h}", src)
    img = Image.open(src).convert("L")
    img = ImageOps.autocontrast(img, cutoff=contrast_cutoff)
    img.convert("RGB").save(dest, "JPEG", quality=90)
```

For higher fidelity use Pexels via `substitute_images.py` with topic-relevant queries (data center / studio / venue / etc.) — Picsum random works for atmosphere but won't match topic.

## PIL gradient gotcha (learned the hard way)

When generating soft radial gradients with PIL (e.g., editorial peach/blue blobs as background accents), Gaussian blur needs **room outside the visible blob to fade into**. If the ellipse is drawn near the canvas edge, the blur kernel runs out of canvas and the gradient ends in a sharp visible line — looks "cropped".

**Fix recipe:**

1. Draw the gradient on an **RGBA transparent canvas**, not on an opaque cream/background-color canvas. Use alpha-equipped fill colors so the gradient decays into transparency.
2. Pad the canvas by **`3 × blur_sigma`** beyond the visible peak area. This is the 3-sigma rule: 99% of a Gaussian's energy is within 3σ.
3. Place the resulting PNG in the slide such that the **bright peak center** lands where you want it visually. The transparent halo bleeds invisibly past slide bounds.

```python
def make_blob(seed, peak_w, peak_h, blur=80):
    pad = blur * 3
    w, h = peak_w + 2 * pad, peak_h + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))  # fully transparent
    cx, cy = w / 2, h / 2
    draw = ImageDraw.Draw(img)
    # Nested ellipses with alpha — outer ring semi-transparent, inner core opaque
    draw.ellipse(..., fill=(*color, 140))  # outer
    draw.ellipse(..., fill=(*color, 230))  # inner
    img = img.filter(ImageFilter.GaussianBlur(blur))
    return img, w, h  # caller centers it where the peak should land
```

This applies to any decorative gradient — covers, section dividers, corner accents.

## Layout gotchas (learned the hard way)

python-pptx textboxes do **not** clip overflowing text. If you set `height=100` on a textbox and the rendered text is 180pt tall, it still renders — just spills 80pt past the bottom of the box, which lands on whatever you placed below it. The bug looks like *the title is colliding with the body*.

Before placing the next element below a textbox, compute the actual rendered height:

```
rendered_height ≈ font_size_pt × num_lines × line_spacing_factor + ~20pt buffer
```

For a 96pt title with two lines and `line_spacing=0.95`: `96 × 2 × 0.95 ≈ 182pt`, so the textbox needs `height ≥ 200pt` and the next element should start at `y_title + 220` minimum. Multi-line titles in particular need explicit room; single-line titles can use tighter heights.

Watch for these especially:
- Titles with an explicit `\n` (you wrote a line break, render will honor it)
- Titles with long phrases at small widths (they wrap silently)
- Two stacked huge display words on section dividers (180pt + 180pt → need ~200pt gap between their `y` positions)

If you can't predict whether a title will wrap (e.g., copy is still being iterated), set the height generously and push the body down accordingly — wasted whitespace is fixable later; collisions look broken.

## Variation taxonomy (a checklist before you ship)

Before declaring the sibling deck done, audit it against the reference:

- [ ] Palette: similar mood, distinguishable on a side-by-side glance
- [ ] Typography: different families, similar pairing logic (display + body roles preserved)
- [ ] Layout: at least 2 slides reuse the reference's layout pattern; at least 2 introduce a localized variation; none is an exact bbox copy
- [ ] Pacing: section dividers fall at proportional positions (e.g., reference had a divider at slide 4/10 → new deck has one near slide 6/15)
- [ ] Imagery: visual style (b&w vs color, full-bleed vs framed, photographic vs illustration) matches the reference's; specific subjects differ
- [ ] No accidental copy: no text, name, or visual asset from the reference appears in the new deck
- [ ] Anti-pattern check: none of the bullet list above describes the result

If two of those audit items fail, the deck has drifted out of "sibling" range — either too far (unrelated) or too close (copy). Adjust before declaring done.

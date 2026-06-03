---
name: pdf-to-pptx-clone
description: Clone a design-rich PDF into a pixel-faithful, editable PPTX, or build a fresh "design sibling" deck that inherits the reference's palette/typography/layout vocabulary while inventing new content. Handles font substitution via Google Fonts (auto-mapped + installed), photo replacement via Unsplash/Pexels with palette-matched tinting, and the full extract → tokenize → rebuild pipeline. Trigger whenever the user wants to turn a designed PDF (annual report, brand book, brochure, magazine spread, pitch deck PDF, infographic) into a PowerPoint deck — even if they only say "convert this PDF to PPT", "make a slide version of this", "I like this PDF's style, recreate it as a deck", "make a sibling deck inspired by this PDF", or share a design-heavy PDF and ask to reuse its look. Also triggers when the user wants to extract a PDF's design system (palette, typography, layout grid) for reuse elsewhere.
---

# PDF → Styled PPTX

This skill turns a design-rich PDF into an editable PPTX, in one of two modes — pixel-faithful **Clone** or design-inheriting **Sibling**.

## How to invoke this skill

> **Speed matters.** Read `references/performance.md` before you start. The wrong pattern turns a 1-minute build into a 9-minute build. The two biggest wins: parallelize stock-photo HTTP fetches via `ThreadPoolExecutor`, and *do not* render source-PDF pages or read multiple sample images "for context" — Claude can describe the design from `pages.json` and `design_tokens.json`.

When this skill activates, the first thing to do is figure out **which mode** the user wants. If their request makes it obvious (e.g. "clone this PDF as a PPT" → Clone, "make a sibling deck inspired by this" → Sibling, "make a deck inspired by but about X" → Sibling with topic already set), **proceed directly — do not ask redundant questions.** Otherwise ask using `AskUserQuestion` with these two options:

> **How should I process this PDF?**
>
> - **Clone mode** — Rebuild the PDF as a pixel-faithful editable PPTX. Same page proportions, element positions, typography, colors, and embedded images. Use this when you want to recover or edit the *actual content* of the reference.
> - **Sibling mode** — Generate a fresh ~15-slide 16:9 deck that inherits the reference's design language (palette, typography, layout vocabulary) but with new English content on a topic of your choice, plus placeholder names per `references/sibling_mode.md`. Use this when you want a *new* deck "inspired by" the reference.

### If the user picks Sibling mode → ask for the topic

`AskUserQuestion` caps at 4 options, so present the topic list as a regular chat message and accept any reply (a number, the label, or a freeform topic the user types). The first option is always **Custom** so the user can supply their own without scrolling. List them like this:

> **What's the topic for the sibling deck?** Reply with a number from the list, or describe your own topic in one line.
>
> 0. **Custom** — type your own (e.g. "Series B fundraising for a fintech")
> 1. 品牌营销 — Global Brand Campaign Strategy
> 2. 内容营销 — Social Media Content Planning System
> 3. 产品发布 — Next-Generation Product Launch Presentation
> 4. 产品协作 — Cross-Team Product Development Workflow
> 5. 会议协作 — Hybrid Meeting Experience Platform
> 6. 文档协同 — Collaborative Documentation Workspace
> 7. 设计系统 — Scalable Design System Governance
> 8. 创业融资 — Early-Stage Startup Investor Pitch
> 9. 销售运营 — Enterprise Sales Enablement Platform
> 10. 客户增长 — Customer Acquisition & Retention Strategy
> 11. 工程效率 — Developer Productivity Infrastructure
> 12. 技术架构 — Cloud Engineering Operations Framework
> 13. 在线教育 — Digital Learning Experience Platform
> 14. 教学培训 — Corporate Training & Teaching System
> 15. 金融分析 — Modern Financial Planning Dashboard
> 16. 投资策略 — Personal Wealth & Investment Insights
> 17. 兴趣社区 — Creative Hobby Community Platform
> 18. 摄影旅行 — Travel Photography Storytelling Deck
> 19. 旅行体验 — Smart Travel Planning Service
> 20. 娱乐媒体 — Streaming Entertainment Growth Strategy
> 21. 音乐内容 — Digital Music Experience Platform
> 22. 游戏社区 — Online Gaming Community Ecosystem

If the user already named a topic in their original request, skip this question — proceed to the build.

### Routing after the question(s) are answered

- **Clone mode** → run stages 1, 2, 2a, (optionally 3), and 4 as documented below. This is the default body of this file.
- **Sibling mode** → run stages 1 and 2 to extract the reference's design tokens, then follow `references/sibling_mode.md` for composition (do **not** use `build_pptx.py` — sibling layouts are composed by hand in python-pptx, not templated).

### Fast path

For most invocations, do this:

```bash
python3 scripts/run_pipeline.py <pdf_path> <workspace>
```

That single command does extract + tokens + font install in one Python process. Then read `design_tokens.json` and proceed. Don't render source-PDF pages or read sample images unless the user explicitly asks to see them.

---

## What clone mode does

Take the designed PDF and rebuild it as an editable PPTX that looks as close to the original as possible — same page proportions, same element positions, same typography, same colors — while optionally swapping every embedded photo for a same-category stock image tinted to match the source palette.

## Why this is hard (and how this skill handles it)

Auto-converters (Adobe, Smallpdf, etc.) shred PDFs into misaligned text frames and broken images. They fail because they treat the PDF as a bag of glyphs instead of a designed artifact.

This skill takes a different approach: it **deconstructs the PDF into a structured design model first**, then **reconstructs from that model**. Every intermediate artifact is a JSON file, so each stage is debuggable and re-runnable in isolation.

The pipeline has four stages, each backed by a script in `scripts/`:

```
PDF ──▶ extract_pdf.py ──▶ pages.json
                                  │
                                  ├──▶ extract_design_tokens.py ──▶ design_tokens.json
                                  │
                                  └──▶ substitute_images.py ──▶ image_map.json + new_images/
                                                                          │
            pages.json + design_tokens.json + image_map.json ──▶ build_pptx.py ──▶ output.pptx
```

## Dependencies

The scripts need four Python libraries. Install them once with:

```bash
pip install PyMuPDF python-pptx Pillow fonttools
```

`fonttools` is used by `install_google_fonts.py` to generate static Regular/Bold/Italic instances from variable fonts (many newer Google Fonts ship only as variable; PowerPoint and Keynote can name them as a family but often fail to render specific weights, so static instances are extracted alongside).

If `pip` complains about an externally-managed environment (common on macOS), either use a venv or pass `--break-system-packages`. The image-substitution step needs one of these API keys in env:

- `PEXELS_API_KEY` — preferred. Free at https://www.pexels.com/api/ (no card, no rate-limit headaches for design work)
- `UNSPLASH_ACCESS_KEY` — fallback. Free at https://unsplash.com/developers

If both are set, Pexels wins. Override per-image with `"source": "unsplash"` inside `image_map.json` if a specific query lands better on Unsplash.

## Working directory

Always create a workspace folder next to the input PDF and put every intermediate artifact there. Example layout:

```
my_pdf.pdf
my_pdf_workspace/
├── pages.json              # raw extraction
├── design_tokens.json      # palette + fonts + grid
├── image_map.json          # original image → Unsplash query + tint
├── original_images/        # extracted as-is (for Claude to view)
├── new_images/             # Unsplash + tinted, ready for PPT
└── my_pdf.pptx             # final output
```

This separation matters: if image substitution looks wrong, re-run stage 3 only. If typography is off, fix `design_tokens.json` and re-run stage 4. Don't redo the full pipeline on every tweak.

## Stage 1 — Extract structure

Run `scripts/extract_pdf.py <pdf_path> <workspace>`. It uses PyMuPDF to walk every page and write `pages.json` with:

- Page dimensions (in points) and aspect ratio
- Text spans with bounding box, font name, font size, color, text content
- Embedded raster images with bounding box, saved to `original_images/page<N>_img<M>.png`
- Vector drawings (rects, lines, curves) with their fill/stroke color

Read the resulting `pages.json` to verify nothing is missing. Pay special attention to fonts — if the PDF embeds a custom font you don't have locally, plan to map it to a close substitute (see `references/font_mapping.md`).

## Stage 2 — Distill the design system

Run `scripts/extract_design_tokens.py <workspace>`. It reads `pages.json` and aggregates:

- **Palette**: top ~8 colors by frequency, with weight and HEX
- **Type scale**: font families used, with size buckets (e.g. 32pt for h1, 11pt for body)
- **Page format**: dimensions, orientation, margin guesses
- **font_overrides**: auto-populated with a Google Fonts suggestion for each PDF font (Futura → Montserrat, Times → Source Serif, etc.). This matters because PDFs almost always embed proprietary subsetted fonts the user doesn't have locally; without overrides, PowerPoint silently falls back to Calibri or Times and the typography goes to garbage.

Read `design_tokens.json` and sanity-check it against the PDF. This is the moment to override anything the heuristic got wrong — e.g., if a brand color is rare in pixel count but clearly the accent, edit the JSON manually before stage 4. Same for `font_overrides`: if the auto-suggested Google Font feels off, swap it.

### 2a — Install the substitute fonts

After fixing `font_overrides`, run `scripts/install_google_fonts.py <workspace>`. It pulls each mapped family as TTF from the official `google/fonts` GitHub repo and drops them into `~/Library/Fonts` (macOS), `~/.fonts` (Linux), or the user font dir (Windows). PowerPoint / Keynote pick them up after a restart.

Why this step is necessary: the Google Fonts CSS API serves only WOFF2, which Office cannot use; the GitHub repo has TTFs. Without this step, the build still names the right font in the PPTX, but the rendering app falls back to a default because the file isn't on the user's machine.

**Variable font caveat**: many modern Google Fonts (Fraunces, Inter, DM Sans, Cormorant Garamond, ...) only ship as variable fonts with axes like `[wght]` or `[opsz,wght]`. PowerPoint and Keynote can find the family but often fail to render specific weights from a variable axis — bold headlines come back as regular, italics fall back to sans-serif. `install_google_fonts.py` detects variable fonts (their filenames contain `[`) and uses `fonttools.varLib.instancer` to generate static `Family-Regular.ttf`, `Family-Bold.ttf`, `Family-Italic.ttf`, `Family-BoldItalic.ttf` alongside the variable file. If `fonttools` isn't installed, this step is skipped with a warning and the user may see weight/italic fallback issues.

## Stage 3 — Replace photos with same-category stock images (Pexels or Unsplash)

This stage is **agent-driven, not purely scripted**. The script handles fetching and tinting; you (Claude) supply the semantic queries by *looking at* each extracted image.

Workflow:

1. List `original_images/` and view each one with the Read tool (it accepts PNG).
2. For each image, write a short, concrete Unsplash query that captures the *same subject and composition*. Examples:
   - portrait close-up of an older man laughing
   - aerial shot of a coastline at sunset
   - minimalist desk with laptop and coffee, overhead
   - hands holding a ceramic bowl, warm light
3. Decide whether the image should get a color filter. If the PDF uses a dominant brand color across photos (e.g. duotone blue), set `tint` to that HEX with an opacity (0.0–0.6). Otherwise leave `tint: null`.
4. Write `image_map.json` with this structure:

```json
{
  "page1_img0": {
    "query": "portrait close-up older man laughing, natural light",
    "orientation": "portrait",
    "tint": {"hex": "#1E3A5F", "opacity": 0.25}
  },
  "page2_img0": {
    "query": "aerial coastline sunset, warm tones",
    "orientation": "landscape",
    "tint": null,
    "source": "unsplash"
  }
}
```

The optional `"source"` field forces a specific backend for that image (`"pexels"` or `"unsplash"`). Omit it to use the default backend resolution: per-image `source` → `$IMAGE_BACKEND` env var → whichever key is set (Pexels wins if both).

5. Run `scripts/substitute_images.py <workspace>`. It fetches each image from the resolved backend, crops it to the original bounding box's aspect ratio, applies the tint via PIL, and writes the result to `new_images/<image_id>.jpg`.

**API keys**: the script reads `PEXELS_API_KEY` and/or `UNSPLASH_ACCESS_KEY` from env. Pexels (`https://www.pexels.com/api/`) tends to produce more design-considered photography — that's why it's preferred for sibling-mode decks. If no key is set, the script prints the queries and stops — fall back to asking the user to provide keys, or ask them to drop replacement images into `new_images/` manually using the same filenames.

## Stage 4 — Rebuild as PPTX

Run `scripts/build_pptx.py <workspace> <output.pptx>`. It reads all three JSONs and `new_images/`, then constructs a python-pptx Presentation where:

- Slide dimensions match the PDF page (in EMU), preserving exact aspect ratio. If the PDF is portrait/A4, the PPT will be portrait too — do NOT force 16:9.
- Each text span becomes a text frame placed at the original bbox, with the original (or mapped) font, size, color.
- Each image is inserted at its bbox, using the substituted file from `new_images/` if available, otherwise the original.
- Vector shapes are recreated as native PPT shapes where possible (rectangles, lines), so they remain editable.

Open the resulting PPTX and spot-check 2–3 pages. Common issues and where to fix them:

| Symptom | Likely cause | Fix |
|---|---|---|
| Text is wrong font / falls back to default | The font isn't installed | Edit `design_tokens.json` font mapping, or install the font |
| Text overflows its box | Font metric mismatch between PDF and PPT | Slightly widen text frames in `build_pptx.py` or use mapped font with similar x-height |
| Image is wrong subject | Bad Unsplash query | Edit query in `image_map.json`, rerun stage 3 |
| Colors look washed out | Tint opacity too high | Lower `tint.opacity` in `image_map.json` |
| Layout looks shifted | Wrong unit conversion | Verify `extract_pdf.py` outputs in points and `build_pptx.py` converts to EMU correctly |

## When to deviate from the pipeline

The pipeline targets the **像素级还原** mode — keep original proportions and positions. If the user later says "actually I want this as a 16:9 deck", that's a different job: don't try to remap the same layout into 16:9 algorithmically (it never looks good). Instead, treat the extracted `design_tokens.json` as the design system and rebuild the content into a fresh 16:9 layout per slide. The token file is the bridge between the two modes.

## References

- `references/font_mapping.md` — common PDF font → PPT-safe font substitutions
- `references/pipeline.md` — deeper notes on each stage's edge cases (CID fonts, clipped images, embedded SVG)
- `references/sibling_mode.md` — when the user wants a *new* deck inspired by the PDF (different content, similar design language), follow this. Includes anti-patterns ("don't drift into the default Claude editorial aesthetic"), variation rules, and the audit checklist.
- `references/performance.md` — how to make the skill feel fast. **Read this first.** The single biggest win is parallel photo fetching; the second biggest is not over-narrating during execution.
- `references/post_build_fixes.md` — run `audit.py` and `bake_autofit.py` after building. Catches image distortion, off-canvas elements, sub-9pt text, and text-frame overlap; bakes the autofit fontScale so PowerPoint reliably shrinks text. Both adopted from the sibling `pptx-design-fix` skill.

# Changelog

All notable changes to this skill. Newest first.

## v0.4 — 2026-06-01

### Added
- **Invocation flow at the top of SKILL.md.** When the skill triggers, Claude first asks the user to pick Clone vs Sibling mode via `AskUserQuestion`. If Sibling mode is picked, Claude then presents a list of 22 themed topic suggestions (with `0. Custom` as the first option so the user can supply their own).
- **`scripts/install_google_fonts.py`** now extracts static `-Regular.ttf` / `-Bold.ttf` / `-Italic.ttf` / `-BoldItalic.ttf` instances from variable fonts via `fonttools.varLib.instancer`. Required because PowerPoint and Keynote often fail to render specific weights from variable axes (Fraunces, Inter, DM Sans, Cormorant Garamond, etc.). Adds `fonttools` to dependencies.
- **`references/sibling_mode.md`** PIL-gradient gotcha section: how to generate soft radial gradients on transparent RGBA canvases with 3σ padding so blur edges don't get clipped.

### Changed
- `scripts/substitute_images.py` now supports both Pexels (preferred) and Unsplash backends, with per-image `"source"` override and auto-detection by env var.

## v0.3 — earlier

### Added
- Icon rasterization in `extract_pdf.py` — detects clusters of complex (non-rectangle) vector drawings and renders them at 4× DPI via clip; PowerPoint inserts the resulting PNG instead of losing them entirely.
- PDF image alpha-channel recovery via SMask xref merging.
- `references/sibling_mode.md` layout gotchas — formula for computing rendered text height so multi-line titles don't collide with the body below.
- Image bbox clipping to slide bounds.
- Full-page background drawing filter (skips invisible white-fill page rects).

### Changed
- `build_pptx.py` textbox slack adjusted from fixed 6pt to `max(20, width × 0.25)` plus `MSO_AUTO_SIZE.TEXT_TO_SHAPE_HEIGHT` to handle font metric mismatches between PDF source and Google Font substitutes.

## v0.2 — earlier

### Added
- `scripts/install_google_fonts.py` — downloads static TTFs from `google/fonts` GitHub repo (the Google Fonts CSS API only serves WOFF2, which Office can't use).
- Auto-suggested Google Font mappings in `design_tokens.json` based on PDF font family stems.
- `references/sibling_mode.md` — design philosophy, anti-patterns, variation checklist for new decks inspired by the reference.

## v0.1 — initial

- Four-stage pipeline: extract → tokenize → image substitute → build.
- Pixel-faithful Clone mode targeting matching the PDF's exact layout.
- `references/font_mapping.md` and `references/pipeline.md` with edge-case notes.

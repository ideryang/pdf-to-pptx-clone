# pdf-to-pptx-clone

A Claude Code skill for turning design-rich PDFs into editable PPTX — either as **pixel-faithful clones** or as **design siblings** (new content, inherited design language).

`.skill` file: **`pdf-to-pptx-clone.skill`** (drop into Claude Code, or unzip into `~/.claude/skills/`)

---

## Background: this started from your prompt

You wrote a strong prompt that gave Claude a clear brief for generating "design sibling" decks. The framing — *inherit structure and vocabulary, vary the details, avoid the default Claude editorial aesthetic* — is the conceptual backbone of this skill. The anti-patterns list (no serif-first, no Space Grotesk, no warm ivory, no poetic magazine composition...) is reproduced verbatim in `references/sibling_mode.md`.

So a lot of what this skill does well, **it does because your prompt named the right targets**.

What the skill adds is everything that a prompt structurally **can't** do — it has to be code.

---

## What changed, and why

### 1. The reference PDF is actually deconstructed, not just "looked at"

**Prompt approach**: "Inspired by the reference presentation" — Claude reads the PDF as one big visual, infers the design system from gestalt.

**Skill approach**: `extract_pdf.py` uses PyMuPDF to walk every page and produce `pages.json` — every text span with its exact bbox / font name / font size / color, every image with its bbox, every vector shape with its fill. Then `extract_design_tokens.py` aggregates this into `design_tokens.json`: the actual top 8 colors by pixel weight, font families with usage counts, real page dimensions.

**Why it matters**: When Claude has to infer the palette from a thumbnail-size visual, accents get mis-identified and dominant neutrals get overweighted. Pulling colors from pixel-area-weighted real data is more reliable. Same for typography — knowing the PDF says `font="FuturaLTPro-Bold"` is better than Claude guessing "looks like a geometric sans".

### 2. Fonts actually get installed, not just named

**Prompt approach**: The output PPTX says `font.name = "Futura"`. PowerPoint and Keynote silently fall back to Calibri because the font isn't on the user's machine. The deck looks generic.

**Skill approach**: 
- `extract_design_tokens.py` auto-suggests a Google Font equivalent for every PDF font (built-in mapping table: Futura → Montserrat, Times → Source Serif, OpenSauceOne → DM Sans, etc.)
- `install_google_fonts.py` downloads the actual TTF from the `google/fonts` GitHub repo (the Google Fonts CSS API only serves WOFF2, which Office can't use — this is a known footgun) and installs into the OS font directory
- Output PPTX uses the now-installed font, so it renders correctly on the machine

**Why it matters**: This was the single biggest fidelity issue in our first iteration of your prompt. Solving it requires actual file-system access and HTTP fetching — pure prompting can't get there.

### 3. Two modes, sharing one extraction

**Prompt approach**: Sibling mode only. The prompt assumes you want a *new* deck.

**Skill approach**:
- **Clone mode** rebuilds the PDF as a pixel-faithful editable PPTX (Phase A)
- **Sibling mode** uses the same `design_tokens.json` as the design-language source of truth, but composes new content (Phase B)
- The two modes share the entire deconstruction pipeline. Sibling mode just diverges at stage 4.

**Why it matters**: Clone mode is the empirical ground truth — if the clone looks right, you *know* the extraction captured the design correctly, so sibling mode has firm footing. Without clone mode, sibling mode is flying on inference.

### 4. PDF image edge-cases that prompts can't fix

Things the skill handles that a prompt structurally can't:

- **Alpha channel recovery**: PDFs store image transparency in a separate "soft mask" xref. PyMuPDF's `Pixmap(doc, xref)` doesn't apply it automatically — the extracted PNG ends up with black where it should be transparent (peach gradient → peach-on-black blob). The skill explicitly fetches the SMask xref and merges with `Pixmap(pix, mask_pix)`.
- **Icon recovery**: Auto-converters drop complex vector paths entirely. The skill detects clusters of non-rectangle vector drawings, computes their bbox, and rasterizes via `page.get_pixmap(clip=rect, dpi=300)` at 4× resolution. Icons come back crisp.
- **Image bbox clipping**: PDFs sometimes report images extending past the page edge (y = -0.4, x past 1440). The skill clips to slide bounds; otherwise PowerPoint positions things weirdly.
- **Full-page background filter**: PDFs often include 1-2 invisible white-fill full-page rects. Skipping them avoids phantom redraws layered under every image.

None of this can be done by writing a better prompt. It requires reading the PDF's xref table.

### 5. Programmatic anti-pattern enforcement, not just narrated

**Prompt approach**: "Don't use Space Grotesk." "Don't use warm ivory." Claude follows when it remembers, drifts when it doesn't.

**Skill approach**: The same anti-pattern list (verbatim from your prompt) lives in `references/sibling_mode.md` — but it also has a *variation taxonomy checklist* at the bottom: "✅ Palette different enough", "✅ Typography pairing logic preserved with different families", "✅ At least 2 slides use a localized layout variation". Claude has to audit against the checklist before declaring the deck done.

It's still not enforced by code — but it's structured as a final-step audit rather than a "remember this from earlier" suggestion.

### 6. Empirical lessons baked back into the doc

Mid-iteration we discovered that **python-pptx textboxes don't clip overflowing text** — set `height=100` on a textbox with 180pt of rendered content and it spills 80pt past the bottom, landing on whatever's below. The contact slide collision you saw.

That gotcha is now permanent in `references/sibling_mode.md` with the formula `rendered_height ≈ font_size × num_lines × line_spacing_factor + ~20pt buffer`. Future runs avoid the bug automatically.

The prompt has no place to put this kind of operational wisdom — it lives in the skill's reference docs.

---

## Honest comparison: what the prompt does that the skill doesn't (yet)

| Capability | Prompt | This skill |
|---|---|---|
| Works without a PDF file on disk | ✅ | ❌ needs a file path |
| Pexels as image source | ✅ (named in prompt) | ✅ Pexels-first, Unsplash as fallback, per-image override |
| One-shot use from chat | ✅ | needs the skill installed |
| Generic across reference types | ✅ | ✅ (tested on 3 different decks) |
| Topic-templated | ✅ via `[topic]` | requires similar param at invoke time |

The prompt is **easier to deploy** (paste and go). The skill is **higher fidelity** (real PDF deconstruction, real font installation, real edge-case handling) but needs setup.

For a one-off "I want a deck inspired by this PDF" the prompt may be enough. For repeated use, or for cases where typography fidelity matters, the skill is the better tool.

---

## Installation

```bash
# Option A: drop the .skill file into Claude Code via the UI
# Option B: unzip directly into your skills directory
unzip pdf-to-pptx-clone.skill -d ~/.claude/skills/

# Install Python dependencies (one-time)
pip install --user PyMuPDF python-pptx Pillow

# (Optional) Get a free Unsplash API key for stage 3 photo replacement
# https://unsplash.com/developers
export UNSPLASH_ACCESS_KEY=...
```

The skill auto-activates whenever you mention converting a PDF to PPT, cloning a deck, or building a "design sibling" / "inspired-by" deck. Force-trigger with: *"use the pdf-to-pptx-clone skill on ..."*

---

## Usage flow

When the skill triggers, Claude will:

1. **Ask the mode** — Clone (pixel-faithful) or Sibling (new content, inherited design language). If the user's request is unambiguous, this step is skipped.
2. **If Sibling, ask the topic** — Claude shows a list of 22 themed presets covering brand/marketing/product/engineering/finance/lifestyle/entertainment, with option `0. Custom` so the user can type any topic. The user picks a number or supplies their own one-line topic.
3. **Run the pipeline** — extract → tokens → install fonts → either build the clone PPTX (Clone mode) or compose ~15 slides via python-pptx referencing `references/sibling_mode.md` (Sibling mode).

### Example invocations

```
> I want to clone /Users/me/decks/reference.pdf as a PPT.

Claude will:
1. extract_pdf.py → pages.json + original_images/
2. extract_design_tokens.py → palette + fonts + page format
3. install_google_fonts.py → TTFs into ~/Library/Fonts (incl. static
   instances extracted from variable fonts via fonttools)
4. build_pptx.py → reference.pptx (pixel-faithful clone)
```

```
> Make a sibling deck inspired by /Users/me/decks/reference.pdf
> [Topic: 8 — Early-Stage Startup Investor Pitch]

Claude will:
1. Reuse design_tokens.json
2. Read references/sibling_mode.md for anti-patterns + checklist
3. Compose ~15 slides via python-pptx using the tokens
4. Run the variation taxonomy audit before declaring done
```

---

## Credits

Conceptual framing and anti-patterns: based on a prompt by a friend (you know who you are). The skill is the prompt + the things a prompt couldn't do.

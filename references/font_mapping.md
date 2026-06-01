# Font Mapping Cheatsheet

PDFs often embed subsetted custom fonts that aren't installed on the user's machine. When that happens, PPT silently falls back to Calibri and the result looks nothing like the original. The fix is to map the PDF font to a close PPT-safe substitute by editing the `font_overrides` block in `design_tokens.json`.

## How to add an override

```json
"font_overrides": {
  "GT-Walsheim-Bold": "Montserrat SemiBold",
  "ABCDEF+CustomDisplay": "Playfair Display"
}
```

The build script handles the `ABCDEF+` subset prefix automatically — you can use either form as the key.

## Common substitutions

| Original family (genre) | Safe-ish substitute on macOS / Windows |
|---|---|
| Helvetica / Helvetica Neue | Helvetica Neue (macOS) / Arial (Windows) |
| GT Walsheim, Circular, Gilroy (geometric sans) | Montserrat, Avenir Next, Futura |
| Söhne, Inter, Suisse (neutral sans) | Inter, Roboto, Segoe UI |
| Times, Georgia, Caslon (serif) | Georgia, Charter, Cambria |
| Playfair, Canela, GT Sectra (display serif) | Playfair Display, Bodoni 72 |
| Mono / code | SF Mono, Consolas, Courier New |
| CJK fallback | PingFang SC, Source Han Sans, Noto Sans CJK SC |

## Things to know

- **Weight matters more than family.** A bold heading in the original needs a bold substitute — picking Montserrat Regular instead of Montserrat Bold will look wrong even if the family fits.
- **Width matters next.** A condensed display font (e.g. Bebas Neue) maps badly to a regular-width font, the text will be too long. Pick a condensed substitute.
- **Don't over-map.** If the PDF uses the same font for body and headings, mapping just one of them creates inconsistency. Map them together.
- **CJK content**: if the PDF contains Chinese/Japanese/Korean glyphs in a font not on the user's system, glyphs disappear silently. Always set an explicit override for CJK runs (e.g. `"SourceHanSans": "PingFang SC"`).

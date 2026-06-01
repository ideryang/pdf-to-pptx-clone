# Performance — making the skill feel fast

The pipeline can easily take 5–10 minutes if you do it the obvious way. Most of that is **wasted on serial HTTP fetches** for stock photos. The fix is small but high-impact.

Concrete numbers from a recent 15-slide sibling build on a 10-page reference:
- Total: 9 minutes (slow path)
- After applying everything in this doc: 2–3 minutes

## 1. Parallelize stock-photo downloads (the single biggest win)

Picsum and Pexels are sequential by default. Use `concurrent.futures.ThreadPoolExecutor` to fan them out — most decks need 10–20 photos, and each one takes 1–3 seconds. Done sequentially, that's a flat 30s. Parallel, it's about 3s.

```python
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlretrieve

def parallel_fetch(specs):
    """specs is a list of (url, dest_path) tuples. Skips already-cached."""
    work = [(u, d) for u, d in specs if not d.exists()]
    if not work:
        return
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda uv: urlretrieve(uv[0], uv[1]), work))

# At the top of your build_sibling.py, pre-declare every photo seed you'll
# need, then prefetch them all before any slide-building begins:
SEEDS = [
    ("cover_a", 1200, 1080),
    ("founder_office", 840, 960),
    ("product_card_plan", 840, 440),
    ("product_card_track", 840, 440),
    ("product_card_decide", 840, 440),
    # ... etc.
]
parallel_fetch([
    (f"https://picsum.photos/seed/{s}/{w}/{h}",
     IMG_DIR / f"photo_{s}_{w}x{h}.jpg")
    for s, w, h in SEEDS
])
```

Now `make_bw_photo("cover_a", 1200, 1080)` etc. hit local files immediately. Build time drops from minutes to seconds.

## 2. Skip work that doesn't change the user-visible output

When the skill triggers, don't:

- Render every page of the source PDF to PNG "for context". Claude can describe the design language from `pages.json` + `design_tokens.json` without seeing every page. Render only if the user explicitly asks.
- Read 5+ sample pages with the Read tool to "show the user the reference." Each Read is a model turn. If the user wants to see the reference, they can open the PDF themselves.
- Re-extract or re-install fonts that already cached on disk. Both `extract_pdf.py` and `install_google_fonts.py` are already idempotent — `if dest.exists(): return` short-circuits.

## 3. Use `run_pipeline.py` instead of three subprocess calls

```bash
python3 scripts/run_pipeline.py <pdf> <workspace>
```

This is one Python process running all three stages in-order. Same outputs as the three separate scripts, ~1s faster (subprocess + interpreter startup amortised) and one notification instead of three.

## 4. Skip the mode/topic question when the user already said

The SKILL.md invocation flow says to ask Clone-vs-Sibling and (in sibling mode) the topic. **Only ask when the user hasn't already said.** If their request is "clone /Users/me/x.pdf to PPT" → skip the question. If their request is "make a sibling deck inspired by /Users/me/x.pdf about Series B fundraising" → skip both. Each `AskUserQuestion` is at least 5–10 seconds of wall-clock time.

## 5. Build first, render-thumbnail second, open last

Render `clone.pptx.png` or `sibling.pptx.png` with `qlmanage` AFTER saving the PPTX and BEFORE opening it. Don't render multiple intermediate thumbnails — one final preview is enough. The user is faster than `qlmanage` at flipping through slides in Keynote.

## 6. Cache photo variants

Toning, rounding, clipping, and avatar generation all write deterministic PNGs to `sibling_images/`. The file name should include every parameter that affects the output (seed, size, blur, tint, radius, shape). If you change the function, change the cache key — don't just edit the source. Examples:

```python
out = IMG_DIR / f"blob_{seed}_{peak_w}x{peak_h}_b{blur}.png"
out = IMG_DIR / f"clipped_{seed}_{w}x{h}_{shape}.png"
out = IMG_DIR / f"avatar_{seed}_{size}.png"
```

This makes re-runs after small edits effectively free.

## 7. Don't over-narrate

Each chat turn from the model has latency. Resist the impulse to:

- Read multiple files just to give the user a "summary of what I'll do"
- Render multiple thumbnails to show progress
- Read the source PDF's pages serially "for context"

The user can ask for any of those if they want them. Default to silent execution.

## 8. Pexels keyword fetches in batch

If using Pexels (preferred for topic-relevant photography), construct **all** query URLs upfront, then run `substitute_images.py` with parallelism. The skill's current `substitute_images.py` iterates serially — for a build that hits 20 images, parallelize the API calls via threads. Pexels rate-limits at 200 requests/hour on free tier, plenty for any single deck.

## Order-of-magnitude budget

Where the time should go in a good run:

| Stage | Budget |
|---|---|
| Mode + topic Q&A | 5–15s (zero if both pre-declared in user request) |
| Extract + tokens + fonts | 5–15s (cached: <2s) |
| Build with parallel photo fetch | 10–30s |
| Render thumbnail + open | 3–5s |
| **Total** | **~30–60s** |

If a step takes longer than this, suspect serial HTTP or unnecessary re-rendering.

"""Install Google Fonts referenced in a workspace's design_tokens.json.

Usage:
    python install_google_fonts.py <workspace_dir>

Downloads each font from the official github.com/google/fonts repo (TTF, which
PowerPoint and Keynote can use; the Google Fonts CSS API only serves WOFF2
which is not supported by Office). Saves into the OS user font directory.
Restart PowerPoint / Keynote after running to pick up the new fonts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

# Most families live under ofl/, but a handful are in apache/ or ufl/.
LICENSE_DIRS = ["ofl", "apache", "ufl"]


def fonts_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Fonts"
    if sys.platform.startswith("linux"):
        return Path.home() / ".fonts"
    if sys.platform.startswith("win"):
        import os
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Fonts"
    return Path.home() / ".fonts"


def http_get(url: str) -> bytes | None:
    """Return body bytes, or None on 404. Raises on other errors."""
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read()
    except HTTPError as e:
        if e.code == 404:
            return None
        raise


def github_list(family_dir: str) -> list[str]:
    """List filenames in a google/fonts subdirectory via the GitHub API."""
    api = f"https://api.github.com/repos/google/fonts/contents/{family_dir}"
    body = http_get(api)
    if body is None:
        return []
    entries = json.loads(body)
    return [e["name"] for e in entries if isinstance(e, dict)]


def find_family_dir(family: str) -> str | None:
    """Return the path 'ofl/montserrat' (etc.) for a given family name."""
    slug = family.lower().replace(" ", "")
    for license_dir in LICENSE_DIRS:
        path = f"{license_dir}/{slug}"
        if github_list(path):
            return path
    return None


def maybe_extract_static_variants(ttf_path: Path) -> int:
    """If `ttf_path` is a variable font, also generate static Regular and
    Bold TTFs next to it. PowerPoint and Keynote handle static instances
    much more reliably than variable fonts with multiple axes — the family
    name still works, but the weight axis isn't always honored.

    Returns the count of static files newly written.
    """
    if "[" not in ttf_path.name:
        return 0
    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
    except ImportError:
        print(f"  i fontTools not installed — skipping static instance "
              f"extraction for {ttf_path.name}. PowerPoint may not pick up "
              f"the variable font weights. Install with: pip install fonttools",
              file=sys.stderr)
        return 0

    stem = ttf_path.stem.split("[")[0]
    is_italic = stem.lower().endswith("italic") or "-italic" in stem.lower()
    base = stem.replace("-Italic", "").replace("-italic", "")

    # Conventional Google Font subfamily naming:
    #   400 upright = Regular | 400 italic = Italic
    #   700 upright = Bold    | 700 italic = BoldItalic
    suffix_for = {
        (400, False): "Regular",
        (700, False): "Bold",
        (400, True): "Italic",
        (700, True): "BoldItalic",
    }

    count = 0
    for weight in (400, 700):
        suffix = suffix_for[(weight, is_italic)]
        out_name = f"{base}-{suffix}.ttf"
        out_path = ttf_path.parent / out_name
        if out_path.exists():
            continue
        font = TTFont(str(ttf_path))
        try:
            instance = instantiateVariableFont(font, {"wght": weight},
                                                 overlap=True)
            instance.save(str(out_path))
            count += 1
            print(f"    ↳ extracted static {out_name}")
        except Exception as e:
            print(f"    ! could not extract {out_name}: {e}",
                  file=sys.stderr)
        finally:
            font.close()
    return count


def install_family(family: str, target_dir: Path) -> int:
    family_dir = find_family_dir(family)
    if not family_dir:
        print(f"  ! {family}: not found in google/fonts repo", file=sys.stderr)
        return 0

    files = [f for f in github_list(family_dir) if f.endswith(".ttf")]
    if not files:
        print(f"  ! {family}: no .ttf files in {family_dir}", file=sys.stderr)
        return 0

    # Prefer variable fonts (single file covers all weights) when present.
    variable = [f for f in files if "[" in f]
    chosen = variable if variable else files

    installed = 0
    for fname in chosen:
        dest = target_dir / fname
        if not dest.exists():
            raw = f"https://raw.githubusercontent.com/google/fonts/main/{family_dir}/{quote(fname)}"
            print(f"  ↓ {fname}")
            data = http_get(raw)
            if data:
                dest.write_bytes(data)
            else:
                continue
        installed += 1
        # For variable fonts, also derive static Regular/Bold instances
        # so PPT/Keynote can use them by weight name.
        installed += maybe_extract_static_variants(dest)
    return installed


def main():
    if len(sys.argv) != 2:
        print("Usage: install_google_fonts.py <workspace_dir>", file=sys.stderr)
        sys.exit(1)

    workspace = Path(sys.argv[1]).resolve()
    tokens = json.loads((workspace / "design_tokens.json").read_text())
    overrides = tokens.get("font_overrides", {})
    families = sorted(set(overrides.values()))
    if not families:
        print("No font_overrides defined — nothing to install.")
        return

    target = fonts_dir()
    target.mkdir(parents=True, exist_ok=True)

    print(f"Installing {len(families)} Google Font families into {target}:")
    total = 0
    for fam in families:
        try:
            total += install_family(fam, target)
        except (HTTPError, URLError) as e:
            print(f"  ! {fam}: network error: {e}", file=sys.stderr)

    print(f"\nDone — {total} font files in place.")
    if sys.platform == "darwin":
        print("Restart PowerPoint / Keynote so it picks up the new fonts.")


if __name__ == "__main__":
    main()

"""Single-process driver that runs extract → tokens → install_fonts in one
Python invocation. Saves ~1s of subprocess + interpreter startup overhead
per stage, and (more importantly) lets Claude see "the pipeline is done"
as one event instead of three.

Usage:
    python run_pipeline.py <pdf_path> <workspace_dir>

Equivalent to running:
    extract_pdf.py <pdf> <ws>
    extract_design_tokens.py <ws>
    install_google_fonts.py <ws>
"""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("Usage: run_pipeline.py <pdf_path> <workspace_dir>",
              file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    workspace = sys.argv[2]
    Path(workspace).mkdir(parents=True, exist_ok=True)

    # Inject this script's directory onto the path so siblings import cleanly
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    t0 = time.time()

    # Stage 1: extract
    import extract_pdf as e
    saved_argv = sys.argv
    sys.argv = ["extract_pdf.py", pdf_path, workspace]
    e.main()
    t1 = time.time()
    print(f"  ({t1 - t0:.1f}s)")

    # Stage 2: tokens
    import extract_design_tokens as t
    sys.argv = ["extract_design_tokens.py", workspace]
    t.main()
    t2 = time.time()
    print(f"  ({t2 - t1:.1f}s)")

    # Stage 2a: fonts (this is the variable bit — first run is slow due
    # to GitHub fetches; subsequent runs hit local cache)
    import install_google_fonts as f
    sys.argv = ["install_google_fonts.py", workspace]
    try:
        f.main()
    except SystemExit:
        pass
    t3 = time.time()
    print(f"  ({t3 - t2:.1f}s)")

    sys.argv = saved_argv
    print(f"\nPipeline complete in {t3 - t0:.1f}s "
          f"→ {workspace}/pages.json + design_tokens.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the full SEO pipeline: image alt metadata → apply alts → sitemaps (no body copy changes)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parent


def run(script: str) -> None:
    subprocess.run([sys.executable, str(ARCHIVE / script)], check=True)


def main() -> int:
    run("seo_image_metadata.py")
    run("apply_image_seo.py")
    try:
        from seo_heads import write_sitemap_with_lastmod
        from seo_utils import PAGES_DIR

        page_paths = sorted(PAGES_DIR.glob("*.html"))
        write_sitemap_with_lastmod(page_paths)
        print(f"Wrote sitemap.xml, sitemap-images.xml, robots.txt ({len(page_paths)} pages)")
    except ImportError as exc:
        print("seo_heads unavailable:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

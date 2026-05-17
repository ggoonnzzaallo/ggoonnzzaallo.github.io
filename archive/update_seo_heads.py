#!/usr/bin/env python3
"""
Refresh SEO metadata across the live site without changing visible body content.

Updates <head> tags (title, description, Open Graph, Twitter, JSON-LD, favicon),
optional non-visible media attributes (iframe title, video aria-label, filename alts),
and sitemap.xml lastmod dates.

    python archive/update_seo_heads.py
    python archive/update_seo_heads.py --dry-run
    python archive/update_seo_heads.py --slug SO_100_Experiments_2025
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ARCHIVE = Path(__file__).resolve().parent
if str(_ARCHIVE) not in sys.path:
    sys.path.insert(0, str(_ARCHIVE))

from seo_heads import INDEX_FILE, PAGES_DIR, patch_html_file, write_sitemap_with_lastmod


def main() -> None:
    parser = argparse.ArgumentParser(description="Update SEO <head> blocks on live HTML pages.")
    parser.add_argument("--slug", action="append", help="Only update pages/{slug}.html")
    parser.add_argument(
        "--media-attrs",
        action="store_true",
        help="Also update iframe titles, video aria-labels, and filename-like img alts in bodies.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files")
    args = parser.parse_args()

    targets: list[Path] = [INDEX_FILE]
    if args.slug:
        for slug in args.slug:
            p = PAGES_DIR / f"{slug}.html"
            if not p.is_file():
                print(f"Missing page: {p}", file=sys.stderr)
                sys.exit(1)
            targets.append(p)
    else:
        targets.extend(sorted(PAGES_DIR.glob("*.html")))

    changed: list[str] = []
    for path in targets:
        if args.dry_run:
            before = path.read_text(encoding="utf-8")
            from seo_heads import patch_page_seo, patch_media_accessibility, h1_plain

            after = patch_page_seo(before, path=path, is_home=path == INDEX_FILE)
            if args.media_attrs and path != INDEX_FILE:
                after = patch_media_accessibility(after, page_title=h1_plain(after))
            if after != before:
                changed.append(path.name)
        else:
            if patch_html_file(path, touch_media=args.media_attrs):
                changed.append(path.name)

    if not args.dry_run:
        write_sitemap_with_lastmod(sorted(PAGES_DIR.glob("*.html")))

    if changed:
        print(f"Updated SEO: {', '.join(changed)}")
    else:
        print("No SEO changes needed.")
    if not args.dry_run:
        print("Wrote sitemap.xml with lastmod dates.")


if __name__ == "__main__":
    main()

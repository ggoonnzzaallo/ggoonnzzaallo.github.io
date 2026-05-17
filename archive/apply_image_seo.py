#!/usr/bin/env python3
"""Apply seo/image_alt.json to img alt/title attributes (no visible body text changes)."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from seo_utils import (
    IMAGE_ALT_FILE,
    INDEX_FILE,
    PAGES_DIR,
    ROOT,
    is_weak_alt,
    load_image_alt_db,
    normalize_src,
)

IMG_TAG_RE = re.compile(r"<img\s([^>]*?)\s*/?>", re.IGNORECASE | re.DOTALL)
ALT_RE = re.compile(r'\balt="([^"]*)"', re.IGNORECASE)
TITLE_RE = re.compile(r'\btitle="([^"]*)"', re.IGNORECASE)


def set_attr(attrs: str, name: str, value: str) -> str:
    esc = html.escape(value, quote=True)
    pat = re.compile(rf'\s{re.escape(name)}="[^"]*"', re.IGNORECASE)
    if pat.search(attrs):
        return pat.sub(f' {name}="{esc}"', attrs, count=1)
    return f'{attrs} {name}="{esc}"'


def patch_img_tag(match: re.Match, alt_map: dict[str, str], force: bool) -> str:
    full = match.group(0)
    attrs = match.group(1)
    self_closing = full.rstrip().endswith("/>")
    if self_closing:
        attrs = attrs.rstrip()
        if attrs.endswith("/"):
            attrs = attrs[:-1].rstrip()
    src_m = re.search(r'\bsrc="([^"]+)"', attrs, re.IGNORECASE)
    if not src_m:
        return match.group(0)
    key = normalize_src(src_m.group(1))
    new_alt = alt_map.get(key)
    if not new_alt:
        return match.group(0)
    alt_m = ALT_RE.search(attrs)
    current = alt_m.group(1) if alt_m else ""
    if not force and not is_weak_alt(current):
        return match.group(0)
    attrs = set_attr(attrs, "alt", new_alt)
    if not TITLE_RE.search(attrs):
        attrs = set_attr(attrs, "title", new_alt)
    closing = " />" if self_closing else ">"
    return f"<img {attrs.strip()}{closing}"


def apply_to_file(path: Path, alt_by_src: dict[str, str], force: bool, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    changed = 0

    def repl(m: re.Match) -> str:
        nonlocal changed
        new = patch_img_tag(m, alt_by_src, force)
        if new != m.group(0):
            changed += 1
        return new

    new_text = IMG_TAG_RE.sub(repl, text)
    if changed and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Dry run; print counts only")
    parser.add_argument("--force", action="store_true", help="Overwrite non-weak alts too")
    args = parser.parse_args()

    db = load_image_alt_db()
    alt_by_src = {k: v["alt"] for k, v in db.get("images", {}).items()}

    targets = [INDEX_FILE, *sorted(PAGES_DIR.glob("*.html"))]
    total = 0
    for path in targets:
        if not path.is_file():
            continue
        n = apply_to_file(path, alt_by_src, args.force, args.check)
        if n:
            rel = path.relative_to(ROOT)
            print(f"{'would update' if args.check else 'updated'} {n} img tags in {rel}")
            total += n

    print(f"Total: {total} img tag(s)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())

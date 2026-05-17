#!/usr/bin/env python3
"""
Update content_manifest.json from curated pages/*.html (site → manifest).

The live HTML is the source of truth. Run this after editing section pages so the
manifest stays in sync for search, tooling, or optional --regenerate-pages runs.

    python archive/sync_manifest_from_pages.py
    python archive/sync_manifest_from_pages.py --slug Ninja_Delivery_20212022
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "pages"
MANIFEST_FILE = ROOT / "content_manifest.json"

MEDIA_SRC_RE = re.compile(
    r'<(?:img|video)\b[^>]*\bsrc="([^"]+)"', re.IGNORECASE
)
IFRAME_SRC_RE = re.compile(
    r'<iframe\b[^>]*\bsrc="([^"]+)"', re.IGNORECASE
)
LINK_RE = re.compile(
    r'<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL
)


def root_relative_asset(src: str) -> str | None:
    src = src.strip()
    if src.startswith("../"):
        return src[3:]
    if src.startswith("assets/"):
        return src
    return None


def inline_html_to_text(fragment: str) -> str:
    """Convert simple inline HTML back to manifest-friendly text with markdown links."""
    out: list[str] = []
    pos = 0
    for match in LINK_RE.finditer(fragment):
        out.append(html.unescape(re.sub(r"<[^>]+>", "", fragment[pos : match.start()])))
        href = match.group(1)
        label = html.unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        if href.startswith(("http://", "https://")):
            out.append(f"[{label}]({href})")
        elif href.endswith(".html"):
            out.append(f"[{label}]({href})")
        else:
            out.append(label)
        pos = match.end()
    out.append(html.unescape(re.sub(r"<[^>]+>", "", fragment[pos:])))
    text = "".join(out)
    return " ".join(text.split())


def blocks_from_article(inner: str) -> list[dict]:
    blocks: list[dict] = []
    inner = inner.strip()
    if not inner:
        return blocks

    if re.search(r'class="media-(?:pair|triplet|quad)', inner, re.IGNORECASE):
        for src in MEDIA_SRC_RE.findall(inner):
            local = root_relative_asset(src)
            if local:
                blocks.append({"type": "media", "url": "", "local_path": local})
        return blocks

    if re.search(r'class="media-pair--embed-mov"', inner, re.IGNORECASE):
        for src in IFRAME_SRC_RE.findall(inner):
            blocks.append({"type": "embed", "url": src})
        for src in MEDIA_SRC_RE.findall(inner):
            local = root_relative_asset(src)
            if local:
                blocks.append({"type": "media", "url": "", "local_path": local})
        return blocks

    embed = IFRAME_SRC_RE.search(inner)
    if embed and "embed-wrap" in inner:
        blocks.append({"type": "embed", "url": embed.group(1)})
        return blocks

    for src in MEDIA_SRC_RE.findall(inner):
        local = root_relative_asset(src)
        if local:
            blocks.append({"type": "media", "url": "", "local_path": local})
        return blocks

    for tag in ("h2", "h3", "h4", "p"):
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", inner, re.DOTALL | re.IGNORECASE)
        if m:
            text = inline_html_to_text(m.group(1))
            if text:
                blocks.append({"type": "text", "text": text, "tag": tag})
            return blocks

    if "press-list" in inner:
        text = inline_html_to_text(inner)
        if text:
            blocks.append({"type": "text", "text": text, "tag": "p"})
        return blocks

    return blocks


def blocks_from_page(page_path: Path) -> list[dict]:
    raw = page_path.read_text(encoding="utf-8")
    section = re.search(
        r'<section class="media-list[^"]*">(.*?)</section>', raw, re.DOTALL | re.IGNORECASE
    )
    if not section:
        return []
    blocks: list[dict] = []
    for inner in re.findall(
        r'<article class="content-item[^"]*">(.*?)</article>',
        section.group(1),
        re.DOTALL | re.IGNORECASE,
    ):
        blocks.extend(blocks_from_article(inner))
    return blocks


def sync_manifest(slugs: list[str] | None = None, dry_run: bool = False) -> None:
    if not MANIFEST_FILE.is_file():
        raise SystemExit(f"Manifest not found: {MANIFEST_FILE}")

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    pages: list[dict] = manifest.get("pages", [])
    by_slug = {p.get("slug"): p for p in pages if p.get("slug")}

    targets = slugs or sorted(p.stem for p in PAGES_DIR.glob("*.html"))
    updated: list[str] = []

    for slug in targets:
        page_path = PAGES_DIR / f"{slug}.html"
        if not page_path.is_file():
            print(f"[skip] No page file: {page_path.name}")
            continue
        new_blocks = blocks_from_page(page_path)
        if not new_blocks:
            print(f"[skip] No content blocks parsed: {slug}")
            continue
        entry = by_slug.get(slug)
        if not entry:
            entry = {
                "slug": slug,
                "url": f"https://www.gonzalobuilds.com/pages/{slug}.html",
                "blocks": [],
            }
            pages.append(entry)
            by_slug[slug] = entry
        entry["blocks"] = new_blocks
        updated.append(slug)
        print(f"[sync] {slug}: {len(new_blocks)} blocks")

    if not updated:
        print("Nothing updated.")
        return

    manifest["pages"] = pages
    if dry_run:
        print(f"Dry run: would update {len(updated)} page(s).")
        return

    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST_FILE} ({len(updated)} page(s)).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync content_manifest.json from pages/*.html")
    parser.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        help="Sync only this section slug (repeatable). Default: all pages/*.html",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing manifest")
    args = parser.parse_args()
    sync_manifest(slugs=args.slugs, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build seo/image_alt.json from on-page figcaptions, index cards, and manifest fallbacks."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from seo_utils import (
    IMAGE_ALT_FILE,
    INDEX_FILE,
    PAGES_DIR,
    ROOT,
    build_alt,
    manifest_figcaption_by_asset,
    normalize_src,
    page_short_title_from_html,
    parse_labeled_caption,
    strip_tags,
)

GALLERY_RE = re.compile(
    r'<div class="media-(?:pair|triplet|quad)[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
IMG_SRC_RE = re.compile(r'<img\s[^>]*src="([^"]+)"', re.IGNORECASE)
ARTICLE_RE = re.compile(
    r'<article class="content-item[^"]*">(.*?)</article>',
    re.DOTALL | re.IGNORECASE,
)
FIGCAPTION_RE = re.compile(r"<figcaption[^>]*>.*?</figcaption>", re.DOTALL | re.IGNORECASE)
CARD_RE = re.compile(
    r'<a class="card" href="pages/([^"]+)">\s*'
    r'<div class="card-hero"><img\s[^>]*src="([^"]+)"',
    re.DOTALL | re.IGNORECASE,
)
CARD_H2_RE = re.compile(
    r'<a class="card" href="pages/([^"]+)">.*?<h2>(.*?)</h2>',
    re.DOTALL | re.IGNORECASE,
)


def extract_gallery_alts(article_html: str, page_title: str) -> dict[str, str]:
    out: dict[str, str] = {}
    gm = GALLERY_RE.search(article_html)
    if not gm:
        return out
    gallery_html = gm.group(1)
    srcs = IMG_SRC_RE.findall(gallery_html)
    if not srcs:
        return out
    fig_m = FIGCAPTION_RE.search(article_html)
    if not fig_m:
        return out
    labels = parse_labeled_caption(fig_m.group(0))
    if not labels:
        return out
    if len(labels) == 1:
        label, text = labels[0]
        for src in srcs:
            out[normalize_src(src)] = build_alt(page_title, label or None, text)
        return out
    for i, src in enumerate(srcs):
        if i < len(labels):
            label, text = labels[i]
            out[normalize_src(src)] = build_alt(page_title, label or None, text)
        else:
            label, text = labels[-1]
            out[normalize_src(src)] = build_alt(page_title, label or None, text)
    return out


def extract_page_images(html: str, page_path: str, manifest_caps: dict[str, str]) -> dict[str, dict]:
    page_title = page_short_title_from_html(html)
    images: dict[str, dict] = {}
    standalone_idx = 0

    for am in ARTICLE_RE.finditer(html):
        article = am.group(1)
        gallery_alts = extract_gallery_alts(article, page_title)
        for src in IMG_SRC_RE.findall(article):
            key = normalize_src(src)
            if key in gallery_alts:
                images[key] = {
                    "alt": gallery_alts[key],
                    "page": page_path,
                    "source": "figcaption",
                }
                continue
            if key in images:
                continue
            standalone_idx += 1
            cap = manifest_caps.get(key)
            if cap:
                alt = build_alt(page_title, None, cap)
                source = "manifest"
            else:
                alt = f"{page_title} — project photo {standalone_idx}"
                source = "fallback"
            images[key] = {"alt": alt, "page": page_path, "source": source}

    return images


def extract_index_cards(index_html: str) -> dict[str, dict]:
    h2_by_slug: dict[str, str] = {}
    for slug, h2 in CARD_H2_RE.findall(index_html):
        h2_by_slug[slug] = strip_tags(h2)
    images: dict[str, dict] = {}
    for slug, src in CARD_RE.findall(index_html):
        key = normalize_src(src)
        title = h2_by_slug.get(slug, slug.replace("_", " "))
        images[key] = {
            "alt": f"{title} — project thumbnail",
            "page": "index.html",
            "source": "index_card",
        }
    return images


def main() -> int:
    manifest_caps = manifest_figcaption_by_asset()
    all_images: dict[str, dict] = {}

    for page_path in sorted(PAGES_DIR.glob("*.html")):
        html = page_path.read_text(encoding="utf-8")
        rel = f"pages/{page_path.name}"
        all_images.update(extract_page_images(html, rel, manifest_caps))

    if INDEX_FILE.is_file():
        index_html = INDEX_FILE.read_text(encoding="utf-8")
        all_images.update(extract_index_cards(index_html))

    db = {
        "site_origin": "https://www.gonzalobuilds.com",
        "images": all_images,
    }
    IMAGE_ALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_ALT_FILE.write_text(
        json.dumps(db, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(all_images)} image entries to {IMAGE_ALT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())

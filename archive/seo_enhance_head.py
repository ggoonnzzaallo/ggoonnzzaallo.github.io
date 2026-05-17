#!/usr/bin/env python3
"""Inject JSON-LD, polish meta descriptions, og:image:alt, and video titles (head/metadata only)."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from seo_utils import (
    INDEX_FILE,
    PAGES_DIR,
    ROOT,
    load_image_alt_db,
    page_short_title_from_html,
    strip_tags,
)

JSONLD_MARKER = "<!-- SEO_JSONLD -->"
META_DESC_RE = re.compile(
    r'<meta name="description" content="([^"]*)"', re.IGNORECASE
)
OG_IMAGE_RE = re.compile(
    r'<meta property="og:image" content="([^"]*)"', re.IGNORECASE
)
FIRST_P_RE = re.compile(
    r'<article class="content-item"><p>(.*?)</p></article>',
    re.DOTALL | re.IGNORECASE,
)
VIDEO_RE = re.compile(
    r"<video\s([^>]*?)>(.*?)</video>", re.DOTALL | re.IGNORECASE
)
IMG_SRC_RE = re.compile(r'\ssrc="([^"]+)"', re.IGNORECASE)


def clip_description(text: str, max_len: int = 158) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "\u2026"


def site_origin_from_db() -> str:
    db = load_image_alt_db()
    return str(db.get("site_origin") or "https://www.gonzalobuilds.com").rstrip("/")


def abs_url(origin: str, path: str) -> str:
    if path.startswith("http"):
        return path
    rel = path.lstrip("/")
    if rel.startswith("../"):
        rel = rel[3:]
    return urljoin(origin + "/", rel)


def remove_jsonld(text: str) -> str:
    return re.sub(
        rf"\s*{re.escape(JSONLD_MARKER)}.*?{re.escape(JSONLD_MARKER)}\s*",
        "\n",
        text,
        flags=re.DOTALL,
    )


def inject_jsonld(text: str, payload: dict) -> str:
    text = remove_jsonld(text)
    block = (
        f"  {JSONLD_MARKER}\n"
        f'  <script type="application/ld+json">\n'
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        f"  </script>\n"
        f"  {JSONLD_MARKER}\n"
    )
    return re.sub(r"</head>", block + "</head>", text, count=1, flags=re.IGNORECASE)


def index_jsonld(origin: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "name": "Gonzalo Graham",
                "url": origin + "/",
                "description": "Engineering portfolio — robotics, drones, and hardware projects.",
            },
            {
                "@type": "Person",
                "name": "Gonzalo Graham",
                "url": origin + "/",
                "sameAs": [
                    "https://www.linkedin.com/in/gonzaloesp/",
                    "https://x.com/geepytee",
                    "https://www.youtube.com/@geepytee",
                ],
            },
        ],
    }


def page_jsonld(
    origin: str,
    page_html: str,
    page_file: Path,
    alt_db: dict,
) -> dict:
    title_m = re.search(r"<title>([^<]+)</title>", page_html, re.IGNORECASE)
    headline = strip_tags(title_m.group(1)) if title_m else page_file.stem
    desc_m = META_DESC_RE.search(page_html)
    description = desc_m.group(1) if desc_m else headline
    canonical = abs_url(
        origin, f"pages/{page_file.name}"
    )
    images: list[str] = []
    prefix = f"pages/{page_file.name}"
    for path, meta in alt_db.get("images", {}).items():
        if meta.get("page") == prefix:
            images.append(abs_url(origin, path))
    if not images:
        og = OG_IMAGE_RE.search(page_html)
        if og:
            images.append(og.group(1))
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": description,
        "url": canonical,
        "author": {"@type": "Person", "name": "Gonzalo Graham"},
        "image": images[:12],
    }


def improve_meta_description(page_html: str) -> str:
    m = META_DESC_RE.search(page_html)
    if not m:
        return page_html
    current = html.unescape(m.group(1))
    if len(current) >= 80 and not current.endswith("\u2026"):
        return page_html
    pm = FIRST_P_RE.search(page_html)
    if not pm:
        return page_html
    plain = strip_tags(pm.group(1))
    if len(plain) < 40:
        return page_html
    new_desc = clip_description(plain)
    if new_desc == current:
        return page_html
    esc = html.escape(new_desc, quote=True)
    return META_DESC_RE.sub(
        f'<meta name="description" content="{esc}"',
        page_html,
        count=1,
    )


def add_og_image_alt(page_html: str, alt_db: dict, page_path: str) -> str:
    og = OG_IMAGE_RE.search(page_html)
    if not og or 'property="og:image:alt"' in page_html:
        return page_html
    og_url = og.group(1)
    rel = og_url.split("gonzalobuilds.com/")[-1] if "gonzalobuilds.com" in og_url else ""
    alt = None
    for path, meta in alt_db.get("images", {}).items():
        if meta.get("page") != page_path:
            continue
        if rel.endswith(path) or path in og_url:
            alt = meta.get("alt")
            break
    if not alt:
        first = next(
            (m["alt"] for k, m in alt_db.get("images", {}).items() if m.get("page") == page_path),
            None,
        )
        alt = first
    if not alt:
        return page_html
    esc = html.escape(alt, quote=True)
    insert = f'  <meta property="og:image:alt" content="{esc}">\n'
    return OG_IMAGE_RE.sub(
        lambda m: m.group(0) + "\n" + insert.rstrip(),
        page_html,
        count=1,
    )


def patch_videos(page_html: str, page_title: str) -> tuple[str, int]:
    count = 0
    vid_idx = 0

    def repl(m: re.Match) -> str:
        nonlocal count, vid_idx
        attrs = m.group(1)
        inner = m.group(2)
        src_m = re.search(
            r'(?:src|data-src)="([^"]+\.mp4)"', attrs + inner, re.IGNORECASE
        )
        if not src_m:
            src_m = re.search(r'<source[^>]+src="([^"]+\.mp4)"', inner, re.IGNORECASE)
        vid_idx += 1
        label = f"{page_title} — video {vid_idx}"
        if src_m:
            name = Path(src_m.group(1)).stem.replace("_", " ")
            label = f"{page_title} — {name}"
        if 'title="' not in attrs:
            attrs = f'{attrs} title="{html.escape(label, quote=True)}"'
            count += 1
        if 'aria-label="' not in attrs:
            attrs = f'{attrs} aria-label="{html.escape(label, quote=True)}"'
        return f"<video {attrs.strip()}>{inner}</video>"

    return VIDEO_RE.sub(repl, page_html), count


def process_file(path: Path, origin: str, alt_db: dict, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    has_jsonld = "application/ld+json" in text
    if path.name == "index.html":
        if not has_jsonld:
            text = inject_jsonld(text, index_jsonld(origin))
    elif path.parent.name == "pages":
        if not has_jsonld:
            text = inject_jsonld(
                text, page_jsonld(origin, text, path, alt_db)
            )
        text = improve_meta_description(text)
        text = add_og_image_alt(text, alt_db, f"pages/{path.name}")
        title = page_short_title_from_html(text)
        text, vc = patch_videos(text, title)
        if vc:
            print(f"  video metadata: {vc} on {path.relative_to(ROOT)}")
    if text != original and not dry_run:
        path.write_text(text, encoding="utf-8")
    elif text != original:
        print(f"would enhance head: {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    origin = site_origin_from_db()
    alt_db = load_image_alt_db()
    if INDEX_FILE.is_file():
        process_file(INDEX_FILE, origin, alt_db, args.check)
    for p in sorted(PAGES_DIR.glob("*.html")):
        process_file(p, origin, alt_db, args.check)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())

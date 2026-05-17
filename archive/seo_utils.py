"""Shared helpers for portfolio SEO scripts (alt text, sitemaps, JSON-LD)."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "pages"
INDEX_FILE = ROOT / "index.html"
MANIFEST_FILE = ROOT / "content_manifest.json"
IMAGE_ALT_FILE = ROOT / "seo" / "image_alt.json"

SITE_SUFFIX_RE = re.compile(
    r"\s*[-–|]\s*Gonzalo Builds\s*$", re.IGNORECASE
)
FILENAME_ALT_RE = re.compile(
    r"^[\w./-]+\.(webp|jpe?g|png|gif)$", re.IGNORECASE
)


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


def is_weak_alt(alt: str | None) -> bool:
    if alt is None:
        return True
    alt = alt.strip()
    if not alt:
        return True
    if FILENAME_ALT_RE.match(alt):
        return True
    if re.search(r"\s—\s*(project photo|photo)(\s+\d+)?$", alt, re.IGNORECASE):
        return True
    if alt.endswith(" — project thumbnail"):
        return False
    return False


def page_short_title_from_html(page_html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", page_html, re.IGNORECASE)
    if m:
        title = strip_tags(m.group(1))
        title = SITE_SUFFIX_RE.sub("", title).strip()
        if title:
            return title
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.IGNORECASE | re.DOTALL)
    if m:
        t = strip_tags(m.group(1))
        t = re.sub(r"\s*\(\d{4}[^)]*\)\s*$", "", t).strip()
        if t:
            return t
    return "Portfolio project"


def normalize_src(src: str) -> str:
    src = src.strip()
    if src.startswith("../"):
        return src[3:]
    if src.startswith("./"):
        return src[2:]
    return src.lstrip("/")


def build_alt(page_title: str, label: str | None, caption: str) -> str:
    caption = " ".join(caption.split())
    if label:
        bit = f"{label}: {caption}"
    else:
        bit = caption
    alt = f"{page_title} — {bit}"
    if len(alt) > 250:
        alt = alt[:247].rsplit(" ", 1)[0] + "…"
    return alt


def parse_labeled_caption(fig_html: str) -> list[tuple[str, str]]:
    """Return [(label, text), ...] from figcaption with caption-label spans."""
    m = re.search(r"<figcaption[^>]*>(.*)</figcaption>", fig_html, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    chunk = m.group(1)
    parts: list[tuple[str, str]] = []
    for lm in re.finditer(
        r'<span class="caption-label">(Left|Center|Right):</span>\s*'
        r"(.*?)(?=<span class=\"caption-label\">|$)",
        chunk,
        re.DOTALL | re.IGNORECASE,
    ):
        label = lm.group(1).strip()
        text = strip_tags(lm.group(2))
        if text:
            parts.append((label, text))
    if parts:
        return parts
    plain = strip_tags(chunk)
    if plain:
        return [("", plain)]
    return []


def manifest_figcaption_by_asset() -> dict[str, str]:
    if not MANIFEST_FILE.is_file():
        return {}
    data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for page in data.get("pages", []):
        blocks = page.get("blocks") or []
        pending_fig: str | None = None
        for b in blocks:
            btype = b.get("type")
            if btype == "text" and str(b.get("tag", "")).lower() == "figcaption":
                pending_fig = strip_tags(str(b.get("text") or ""))
            elif btype == "media" and b.get("local_path"):
                path = str(b["local_path"])
                if pending_fig:
                    out[path] = pending_fig
                pending_fig = None
            elif btype == "text" and str(b.get("tag", "")).lower() == "p":
                pending_fig = None
    return out


def load_image_alt_db() -> dict:
    if IMAGE_ALT_FILE.is_file():
        return json.loads(IMAGE_ALT_FILE.read_text(encoding="utf-8"))
    return {"site_origin": "https://www.gonzalobuilds.com", "images": {}}

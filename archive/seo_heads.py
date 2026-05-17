"""
Head-only SEO helpers for gonzalobuilds.com.

Updates titles, meta tags, Open Graph / Twitter cards, JSON-LD, favicon links,
and sitemap lastmod — without changing visible page body copy or gallery layout.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "pages"
INDEX_FILE = ROOT / "index.html"
IMAGE_ALT_FILE = ROOT / "seo" / "image_alt.json"

SITE_ORIGIN = "https://www.gonzalobuilds.com"
SITE_NAME = "Gonzalo Graham"
AUTHOR = "Gonzalo Graham"
TWITTER_SITE = "@geepytee"
FAVICON_SVG = "favicon.svg"
FAVICON_PNG_32 = "favicon-32x32.png"
FAVICON_ICO = "favicon.ico"
APPLE_TOUCH_ICON = "apple-touch-icon.png"
DEFAULT_OG_IMAGE = "assets/Thumbnail/thumbnail_light.jpg"
INDEX_OG_IMAGE_DIMS = (3168, 1344)

DESCRIPTION_MAX = 158
SHORT_DESCRIPTION_THRESHOLD = 80


def clip_description(text: str, max_len: int = DESCRIPTION_MAX) -> str:
    text = " ".join(html.unescape(text).split())
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "\u2026"


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return " ".join(html.unescape(text).split())


def absolute_url(path_or_url: str, *, page_depth: int = 0) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    rel = path_or_url
    if rel.startswith("../"):
        rel = rel[3:]
    elif rel.startswith("./"):
        rel = rel[2:]
    return f"{SITE_ORIGIN.rstrip('/')}/{rel.lstrip('/')}"


def favicon_link_tags(*, page_depth: int) -> str:
    prefix = "../" * page_depth
    esc = html.escape
    svg = f"{prefix}{FAVICON_SVG}"
    png = f"{prefix}{FAVICON_PNG_32}"
    ico = f"{prefix}{FAVICON_ICO}"
    apple = f"{prefix}{APPLE_TOUCH_ICON}"
    return "\n".join(
        [
            f'  <link rel="icon" href="{esc(svg)}" type="image/svg+xml">',
            f'  <link rel="icon" href="{esc(png)}" type="image/png" sizes="32x32">',
            f'  <link rel="icon" href="{esc(ico)}" sizes="any">',
            f'  <link rel="apple-touch-icon" href="{esc(apple)}">',
        ]
    )


def _paragraph_previews(body_html: str) -> list[str]:
    m = re.search(
        r'<section class="media-list[^"]*">(.*?)</section>',
        body_html,
        re.DOTALL | re.IGNORECASE,
    )
    section = m.group(1) if m else body_html
    out: list[str] = []
    for p_match in re.finditer(r"<p[^>]*>(.*?)</p>", section, re.DOTALL | re.IGNORECASE):
        text = strip_tags(p_match.group(1))
        if len(text) >= 40:
            out.append(text)
    return out


def first_paragraph_preview(body_html: str) -> str:
    paras = _paragraph_previews(body_html)
    return paras[0] if paras else ""


def h1_plain(body_html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", body_html, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    return strip_tags(m.group(1))


def first_hero_image_src(body_html: str) -> str | None:
    m = re.search(r'<img\s[^>]*src="([^"]+)"', body_html, re.IGNORECASE)
    return m.group(1) if m else None


def load_image_alt_map() -> dict[str, str]:
    if not IMAGE_ALT_FILE.is_file():
        return {}
    data = json.loads(IMAGE_ALT_FILE.read_text(encoding="utf-8"))
    return {
        k: str(v.get("alt") or "")
        for k, v in (data.get("images") or {}).items()
        if v.get("alt")
    }


def normalize_asset_path(src: str) -> str:
    if src.startswith("../"):
        return src[3:]
    if src.startswith("./"):
        return src[2:]
    return src.lstrip("/")


def alt_for_image_src(src: str | None, alt_map: dict[str, str], fallback: str) -> str:
    if not src:
        return fallback
    key = normalize_asset_path(src)
    return alt_map.get(key) or fallback


def parse_title_tag(head_html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", head_html, re.DOTALL | re.IGNORECASE)
    return strip_tags(m.group(1)) if m else ""


def parse_meta_description(head_html: str) -> str:
    m = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        head_html,
        re.IGNORECASE,
    )
    if not m:
        return ""
    return html.unescape(m.group(1))


def choose_meta_description(
    current: str,
    body_preview: str,
    title_plain: str,
    *,
    is_home: bool,
    body_html: str = "",
) -> str:
    if is_home:
        return current or clip_description(
            "Born in Peru, forged at uWaterloo. Highlight reel of robotics, drones, and builds outside of work."
        )

    preview = body_preview.strip()
    cur = current.strip()

    if not cur:
        if preview:
            return clip_description(preview)
        return clip_description(
            f"{title_plain} — photos, video, and notes from Gonzalo Graham's engineering portfolio."
        )

    if cur.endswith("\u2026") and preview:
        candidate = clip_description(preview)
        if candidate != cur:
            return candidate
        paras = _paragraph_previews(body_html)
        # Fallback when the first paragraph clips to the same truncated meta string.
        for extra in paras[1:]:
            alt = clip_description(extra)
            if alt != cur:
                return alt
        sentences = re.split(r"(?<=[.!?])\s+", preview)
        if len(sentences) > 1:
            return clip_description(" ".join(sentences[1:]))
        return candidate

    if len(cur) < SHORT_DESCRIPTION_THRESHOLD and preview:
        if preview.lower().startswith(cur.lower().rstrip(".")):
            return clip_description(preview)
        return clip_description(f"{cur} {preview}")

    return cur


def share_title_from_document_title(document_title: str, *, is_home: bool) -> str:
    if is_home:
        return SITE_NAME
    if " - Gonzalo Builds" in document_title:
        return document_title
    return f"{document_title} - Gonzalo Builds"


def json_ld_script(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f'  <script type="application/ld+json">\n{payload}\n  </script>'


def json_ld_for_home(canonical_url: str, description: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": f"{canonical_url}#website",
                "url": canonical_url,
                "name": SITE_NAME,
                "description": description,
                "inLanguage": "en",
                "publisher": {"@id": f"{canonical_url}#person"},
            },
            {
                "@type": "Person",
                "@id": f"{canonical_url}#person",
                "name": AUTHOR,
                "url": canonical_url,
                "sameAs": [
                    "https://www.linkedin.com/in/gonzaloesp/",
                    "https://x.com/geepytee",
                    "https://www.youtube.com/@geepytee",
                ],
            },
        ],
    }
    return json_ld_script(data)


def json_ld_for_article(
    *,
    canonical_url: str,
    headline: str,
    description: str,
    image_url: str | None,
    date_modified: str | None,
) -> str:
    article: dict = {
        "@type": "Article",
        "@id": f"{canonical_url}#article",
        "headline": headline,
        "description": description,
        "author": {"@type": "Person", "name": AUTHOR, "url": SITE_ORIGIN + "/"},
        "publisher": {
            "@type": "Person",
            "name": AUTHOR,
            "url": SITE_ORIGIN + "/",
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "inLanguage": "en",
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_ORIGIN + "/"},
    }
    if image_url:
        article["image"] = [image_url]
    if date_modified:
        article["dateModified"] = date_modified
    data = {"@context": "https://schema.org", **article}
    return json_ld_script(data)


def build_seo_head_block(
    *,
    document_title: str,
    description: str,
    canonical_url: str,
    og_image_url: str | None,
    og_image_alt: str,
    og_type: str,
    is_home: bool,
    page_depth: int,
    json_ld: str,
    og_image_width: int | None = None,
    og_image_height: int | None = None,
) -> str:
    esc = html.escape
    share_title = share_title_from_document_title(document_title, is_home=is_home)
    lines = [
        f"  <title>{esc(document_title)}</title>",
        f'  <meta name="description" content="{esc(description)}">',
        '  <meta name="robots" content="index, follow">',
        f'  <meta name="author" content="{esc(AUTHOR)}">',
        f'  <link rel="canonical" href="{esc(canonical_url)}">',
        favicon_link_tags(page_depth=page_depth),
        f'  <meta property="og:locale" content="en_US">',
        f'  <meta property="og:type" content="{esc(og_type)}">',
        f'  <meta property="og:url" content="{esc(canonical_url)}">',
        f'  <meta property="og:site_name" content="{esc(SITE_NAME)}">',
        f'  <meta property="og:title" content="{esc(share_title)}">',
        f'  <meta property="og:description" content="{esc(description)}">',
    ]
    if og_image_url:
        lines.append(f'  <meta property="og:image" content="{esc(og_image_url)}">')
        if og_image_width and og_image_height:
            lines.append(f'  <meta property="og:image:width" content="{og_image_width}">')
            lines.append(f'  <meta property="og:image:height" content="{og_image_height}">')
        lines.append(f'  <meta property="og:image:alt" content="{esc(og_image_alt)}">')
    lines.extend(
        [
            '  <meta name="twitter:card" content="summary_large_image">',
            f'  <meta name="twitter:site" content="{esc(TWITTER_SITE)}">',
            f'  <meta name="twitter:creator" content="{esc(TWITTER_SITE)}">',
            f'  <meta name="twitter:title" content="{esc(share_title)}">',
            f'  <meta name="twitter:description" content="{esc(description)}">',
        ]
    )
    if og_image_url:
        lines.append(f'  <meta name="twitter:image" content="{esc(og_image_url)}">')
        lines.append(f'  <meta name="twitter:image:alt" content="{esc(og_image_alt)}">')
    lines.append(json_ld)
    return "\n".join(lines) + "\n"


def head_assets_tail(*, page_depth: int) -> str:
    prefix = "../" * page_depth
    return (
        f'  <script src="{prefix}theme.js"></script>\n'
        f'  <link rel="stylesheet" href="{prefix}site.css">\n'
        f'  <script src="{prefix}posthog-config.js"></script>\n'
        f'  <script src="{prefix}posthog-analytics.js"></script>\n'
    )


def patch_page_seo(raw: str, *, path: Path, is_home: bool = False) -> str:
    page_depth = 0 if is_home else 1
    head_match = re.search(r"<head>(.*?)</head>", raw, re.DOTALL | re.IGNORECASE)
    if not head_match:
        raise ValueError(f"No <head> in {path}")

    head_inner = head_match.group(1)
    body_match = re.search(r"<body[^>]*>(.*)</body>", raw, re.DOTALL | re.IGNORECASE)
    body_html = body_match.group(1) if body_match else ""

    document_title = parse_title_tag(head_inner)
    if not document_title:
        document_title = SITE_NAME if is_home else strip_tags(h1_plain(body_html)) or path.stem

    title_plain = h1_plain(body_html) or document_title.replace(" - Gonzalo Builds", "")
    current_desc = parse_meta_description(head_inner)
    body_preview = first_paragraph_preview(body_html)
    description = choose_meta_description(
        current_desc, body_preview, title_plain, is_home=is_home, body_html=body_html
    )

    hero = first_hero_image_src(body_html)
    if is_home:
        canonical_url = f"{SITE_ORIGIN}/"
        og_image_rel = DEFAULT_OG_IMAGE
        og_w, og_h = INDEX_OG_IMAGE_DIMS
        og_type = "website"
        json_ld = json_ld_for_home(canonical_url, description)
    else:
        slug = path.stem
        canonical_url = f"{SITE_ORIGIN}/pages/{slug}.html"
        og_image_rel = hero or DEFAULT_OG_IMAGE
        og_w, og_h = None, None
        og_type = "article"
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )
        json_ld = json_ld_for_article(
            canonical_url=canonical_url,
            headline=title_plain,
            description=description,
            image_url=absolute_url(og_image_rel),
            date_modified=mtime,
        )

    og_image_url = absolute_url(og_image_rel)
    alt_map = load_image_alt_map()
    og_image_alt = alt_for_image_src(hero if not is_home else None, alt_map, title_plain)
    if is_home:
        og_image_alt = SITE_NAME

    seo_block = build_seo_head_block(
        document_title=document_title,
        description=description,
        canonical_url=canonical_url,
        og_image_url=og_image_url,
        og_image_alt=og_image_alt,
        og_type=og_type,
        is_home=is_home,
        page_depth=page_depth,
        json_ld=json_ld,
        og_image_width=og_w,
        og_image_height=og_h,
    )

    new_head_inner = re.sub(
        r"<meta charset=\"UTF-8\">\s*"
        r"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\s*",
        '<meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n',
        head_inner,
        count=1,
        flags=re.IGNORECASE,
    )
    new_head_inner = re.sub(
        r"<title>.*?</title>\s*"
        r"(?:<!--.*?-->\s*)*"
        r"(?:<meta[^>]+>\s*|<link[^>]+>\s*|"
        r'<script type="application/ld\+json">.*?</script>\s*)*',
        seo_block,
        new_head_inner,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    new_head_inner = re.sub(
        r"<script src=\"[^\"]*theme\.js\"></script>\s*"
        r"<link rel=\"stylesheet\" href=\"[^\"]*site\.css\">\s*"
        r"<script src=\"[^\"]*posthog-config\.js\"></script>\s*"
        r"<script src=\"[^\"]*posthog-analytics\.js\"></script>\s*",
        head_assets_tail(page_depth=page_depth),
        new_head_inner,
        count=1,
        flags=re.IGNORECASE,
    )

    return raw[: head_match.start(1)] + new_head_inner + raw[head_match.end(1) :]


def patch_media_accessibility(raw: str, *, page_title: str) -> str:
    """Non-visible attrs only: iframe titles, video aria-labels, filename-like img alts."""

    def iframe_title_repl(m: re.Match[str]) -> str:
        tag = m.group(0)
        if re.search(r'\btitle="(?!YouTube video)', tag, re.IGNORECASE):
            return tag
        label = f"{page_title} — embedded video"
        if re.search(r'\btitle="', tag, re.IGNORECASE):
            return re.sub(
                r'\btitle="[^"]*"',
                f'title="{html.escape(label, quote=True)}"',
                tag,
                count=1,
                flags=re.IGNORECASE,
            )
        return tag.replace("<iframe ", f'<iframe title="{html.escape(label)}" ', 1)

    raw = re.sub(r"<iframe\b[^>]*>", iframe_title_repl, raw, flags=re.IGNORECASE)

    def video_repl(m: re.Match[str]) -> str:
        tag = m.group(0)
        if re.search(r"\baria-label=", tag, re.IGNORECASE):
            return tag
        label = f"{page_title} — video"
        return tag.replace("<video ", f'<video aria-label="{html.escape(label)}" ', 1)

    raw = re.sub(r"<video\b[^>]*>", video_repl, raw, flags=re.IGNORECASE)

    def weak_img_alt(m: re.Match[str]) -> str:
        alt = m.group(1)
        if not alt or not re.search(r"\.(webp|jpe?g|png|gif|avif)$", alt, re.IGNORECASE):
            return m.group(0)
        new_alt = f"{page_title} — photo"
        return m.group(0).replace(f'alt="{alt}"', f'alt="{html.escape(new_alt)}"', 1)

    raw = re.sub(
        r'<img\b[^>]*\salt="([^"]+)"[^>]*class="media"',
        weak_img_alt,
        raw,
        flags=re.IGNORECASE,
    )
    return raw


def patch_html_file(path: Path, *, touch_media: bool = True) -> bool:
    raw = path.read_text(encoding="utf-8")
    is_home = path.name == "index.html" and path.parent == ROOT
    updated = patch_page_seo(raw, path=path, is_home=is_home)
    if touch_media and not is_home:
        title = h1_plain(updated) or parse_title_tag(updated)
        updated = patch_media_accessibility(updated, page_title=title)
    if updated != raw:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def write_image_sitemap(alt_entries: dict[str, dict]) -> None:
    by_page: dict[str, list[tuple[str, str]]] = {}
    for asset_path, meta in alt_entries.items():
        page = str(meta.get("page") or "")
        alt = str(meta.get("alt") or "").strip()
        if not page or not alt:
            continue
        page_url = f"{SITE_ORIGIN}/" if page == "index.html" else f"{SITE_ORIGIN}/{page}"
        by_page.setdefault(page_url, []).append((asset_path, alt))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    for page_url in sorted(by_page):
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(page_url)}</loc>")
        for asset_path, alt in by_page[page_url]:
            img_url = absolute_url(asset_path)
            parts.append("    <image:image>")
            parts.append(f"      <image:loc>{xml_escape(img_url)}</image:loc>")
            parts.append(f"      <image:title>{xml_escape(alt)}</image:title>")
            parts.append(f"      <image:caption>{xml_escape(alt)}</image:caption>")
            parts.append("    </image:image>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")
    (ROOT / "sitemap-images.xml").write_text("\n".join(parts), encoding="utf-8")


def write_sitemap_with_lastmod(page_paths: list[Path]) -> None:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    entries: list[tuple[str, float]] = [(f"{SITE_ORIGIN}/", INDEX_FILE.stat().st_mtime)]
    for p in sorted(page_paths, key=lambda x: x.name.lower()):
        entries.append(
            (f"{SITE_ORIGIN}/pages/{p.stem}.html", p.stat().st_mtime)
        )
    for loc, mtime in entries:
        lastmod = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        parts.append(
            f"  <url><loc>{xml_escape(loc)}</loc><lastmod>{lastmod}</lastmod></url>"
        )
    parts.append("</urlset>")
    parts.append("")
    (ROOT / "sitemap.xml").write_text("\n".join(parts), encoding="utf-8")

    if IMAGE_ALT_FILE.is_file():
        data = json.loads(IMAGE_ALT_FILE.read_text(encoding="utf-8"))
        images = data.get("images") or {}
        if images:
            write_image_sitemap(images)

    robots = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "",
            f"Sitemap: {SITE_ORIGIN}/sitemap.xml",
            f"Sitemap: {SITE_ORIGIN}/sitemap-images.xml",
            "",
        ]
    )
    (ROOT / "robots.txt").write_text(robots, encoding="utf-8")

#!/usr/bin/env python3
"""
Generate a static GitHub Pages structure from downloaded assets.
"""

from __future__ import annotations

import html
import json
import os
import re
import socket
from pathlib import Path

from dotenv import load_dotenv
from posthog import Posthog

load_dotenv()

_posthog = Posthog(
    os.environ.get("POSTHOG_PROJECT_TOKEN", ""),
    host=os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com"),
    enable_exception_autocapture=True,
) if os.environ.get("POSTHOG_PROJECT_TOKEN") else None

_DISTINCT_ID = socket.gethostname()


ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
PAGES_DIR = ROOT / "pages"
MARKDOWNS_DIR = ROOT / "markdowns"
STYLE_FILE = ROOT / "site.css"
INDEX_FILE = ROOT / "index.html"
MANIFEST_FILE = ROOT / "content_manifest.json"

# Social links (index top + section page footers). Keep in sync with index.html when curated.
_SOCIAL_LINK_ROWS = """        <a class="social-btn social-btn--linkedin" href="https://www.linkedin.com/in/gonzaloesp/" target="_blank" rel="noopener noreferrer">
          <span class="social-btn__icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></span>
          <span class="social-btn__text">Connect on LinkedIn</span>
        </a>
        <a class="social-btn social-btn--x" href="https://x.com/geepytee" target="_blank" rel="noopener noreferrer">
          <span class="social-btn__icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></span>
          <span class="social-btn__text">Follow me on X</span>
        </a>
        <a class="social-btn social-btn--youtube" href="https://www.youtube.com/@geepytee" target="_blank" rel="noopener noreferrer">
          <span class="social-btn__icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg></span>
          <span class="social-btn__text">See my YouTube channel</span>
        </a>"""

SOCIAL_NAV_TOP = f"""    <nav class="social-nav social-nav--top" aria-label="Social links">
{_SOCIAL_LINK_ROWS}
    </nav>"""

SOCIAL_FOOTER = f"""    <footer class="site-footer">
      <nav class="social-nav social-nav--footer" aria-label="Social links">
{_SOCIAL_LINK_ROWS}
      </nav>
    </footer>"""

IMAGE_LIGHTBOX_MARKUP = """  <div class="image-lightbox" id="image-lightbox" aria-hidden="true">
    <button class="image-lightbox__close" type="button" aria-label="Close image viewer">&times;</button>
    <img class="image-lightbox__img" alt="">
  </div>
  <script>
    (function () {
      var lightbox = document.getElementById("image-lightbox");
      if (!lightbox) return;
      var closeBtn = lightbox.querySelector(".image-lightbox__close");
      var lightboxImg = lightbox.querySelector(".image-lightbox__img");
      var activeTrigger = null;

      function closeLightbox() {
        lightbox.classList.remove("is-open");
        lightbox.setAttribute("aria-hidden", "true");
        document.body.classList.remove("lightbox-open");
        if (activeTrigger) activeTrigger.focus();
      }

      function openLightbox(trigger) {
        var src = trigger.currentSrc || trigger.getAttribute("src");
        if (!src || !lightboxImg) return;
        activeTrigger = trigger;
        lightboxImg.src = src;
        lightboxImg.alt = trigger.getAttribute("alt") || "";
        lightbox.classList.add("is-open");
        lightbox.setAttribute("aria-hidden", "false");
        document.body.classList.add("lightbox-open");
      }

      document.addEventListener("click", function (event) {
        var target = event.target;
        if (!(target instanceof HTMLImageElement)) return;
        if (!target.closest(".media-figure, .media-item, .hero-media-figure")) return;
        if (target.closest("a")) return;
        openLightbox(target);
      });

      if (closeBtn) {
        closeBtn.addEventListener("click", closeLightbox);
      }

      lightbox.addEventListener("click", function (event) {
        if (event.target === lightbox) closeLightbox();
      });

      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && lightbox.classList.contains("is-open")) {
          closeLightbox();
        }
      });
    })();
  </script>"""

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".ogv"}


def title_from_slug(slug: str) -> str:
    return slug.replace("_", " ").strip()


def styled_title(title: str) -> str:
    match = re.match(r"^(.*?)(\s*\([^()]+\))$", title.strip())
    if not match:
        return html.escape(title)
    base, year = match.groups()
    return f'{html.escape(base.strip())} <span class="card-year">{html.escape(year.strip())}</span>'


def parse_numeric_suffix(filename: str) -> int:
    match = re.search(r"_(\d+)\.[^.]+$", filename)
    if match:
        return int(match.group(1))
    return 10**9


def relpath(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace("\\", "/")


def parse_index_section_titles() -> dict[str, tuple[str, str]]:
    """
    When index.html is curated, map section slug -> (h1_inner_html, plain_title_for_document_title).

    The index card <h2> inner HTML is reused as the section page <h1> (source of truth).
    """
    if not INDEX_FILE.exists():
        return {}
    raw = INDEX_FILE.read_text(encoding="utf-8")
    if "INDEX_CURATED" not in raw[:800]:
        return {}
    pattern = re.compile(
        r'<a class="card" href="pages/([^"]+)">\s*'
        r'<div class="card-hero">.*?</div>\s*'
        r'<div class="card-body"><h2>(.*?)</h2></div>\s*</a>',
        re.DOTALL,
    )
    out: dict[str, tuple[str, str]] = {}
    for href_file, h2_inner in pattern.findall(raw):
        slug = Path(href_file).stem
        inner_html = " ".join(h2_inner.split())
        plain = re.sub(r"<[^>]+>", "", h2_inner)
        plain = " ".join(plain.split())
        out[slug] = (inner_html, plain)
    return out


def index_card_hero_src(section_slug: str) -> str | None:
    """First <img> on a section page (hero), path relative to site root."""
    page = PAGES_DIR / f"{section_slug}.html"
    if not page.exists():
        return None
    text = page.read_text(encoding="utf-8")
    match = re.search(r'<img\s[^>]*src="([^"]+)"', text)
    if not match:
        return None
    src = match.group(1)
    if src.startswith("../"):
        return src[3:]
    return src


def media_markup(media_rel_path: str, media_name: str, *, wrap_in_figure: bool = True) -> str:
    ext = Path(media_name).suffix.lower()
    escaped_alt = html.escape(media_name)

    def wrap_media(inner: str) -> str:
        if not wrap_in_figure:
            return inner
        return f'<figure class="media-figure">{inner}</figure>'

    if ext in VIDEO_EXTENSIONS:
        inner = (
            f'<video controls preload="metadata" playsinline class="media">'
            f'<source src="{media_rel_path}">'
            "Your browser does not support the video tag."
            "</video>"
        )
        return wrap_media(inner)
    if ext in IMAGE_EXTENSIONS:
        inner = f'<img src="{media_rel_path}" alt="{escaped_alt}" loading="lazy" class="media">'
        return wrap_media(inner)
    return (
        f'<a href="{media_rel_path}" class="file-link" target="_blank" rel="noopener noreferrer">'
        f"{escaped_alt}</a>"
    )


def build_index(sections: list[tuple[str, str, int]]) -> None:
    if INDEX_FILE.exists():
        head = INDEX_FILE.read_text(encoding="utf-8")[:800]
        if "INDEX_CURATED" in head:
            return
    cards = []
    for section_slug, section_title, _count in sections:
        hero_src = index_card_hero_src(section_slug)
        hero_html = ""
        if hero_src:
            hero_html = (
                "<div class=\"card-hero\">"
                f"<img src=\"{html.escape(hero_src)}\" alt=\"\" width=\"800\" height=\"450\" "
                "loading=\"lazy\" class=\"card-hero-img\">"
                "</div>"
            )
        cards.append(
            "<a class=\"card\" href=\"pages/{slug}.html\">"
            "{hero}"
            "<div class=\"card-body\"><h2>{title}</h2></div>"
            "</a>".format(
                slug=html.escape(section_slug),
                title=styled_title(section_title),
                hero=hero_html,
            )
        )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gonzalo Graham</title>
  <link rel="stylesheet" href="site.css">
</head>
<body>
  <main class="container">
    <header class="header">
      <h1>Gonzalo Graham</h1>
      <p>Welcome to my portfolio. Here are some personal projects I’ve enjoyed working on in my free time.</p>
    </header>
{SOCIAL_NAV_TOP}
    <section class="grid grid--compact-cards">
      {"".join(cards)}
    </section>
  </main>
{IMAGE_LIGHTBOX_MARKUP}
</body>
</html>
"""
    INDEX_FILE.write_text(page, encoding="utf-8")


def build_section_page(section_dir: Path) -> tuple[str, str, int]:
    section_slug = section_dir.name
    section_title = title_from_slug(section_slug)
    index_titles = parse_index_section_titles()
    if section_slug in index_titles:
        h1_inner, title_plain = index_titles[section_slug]
    else:
        h1_inner = styled_title(section_title)
        title_plain = section_title
    output_file = PAGES_DIR / f"{section_slug}.html"

    media_files = [p for p in section_dir.iterdir() if p.is_file()]
    media_files.sort(key=lambda p: (parse_numeric_suffix(p.name), p.name.lower()))

    blocks = []
    for media in media_files:
        media_rel = relpath(output_file, media)
        item_number = parse_numeric_suffix(media.name)
        label = f"{section_title} #{item_number}" if item_number < 10**9 else media.name
        blocks.append(
            "<article class=\"media-item\">"
            f"<h3>{html.escape(label)}</h3>"
            f"{media_markup(media_rel, media.name, wrap_in_figure=False)}"
            "</article>"
        )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title_plain)} - Gonzalo Builds</title>
  <link rel="stylesheet" href="../site.css">
</head>
<body>
  <main class="container">
    <header class="header">
      <a class="back-link" href="../index.html">&larr; All Sections</a>
      <h1>{h1_inner}</h1>
    </header>
    <section class="media-list">
      {"".join(blocks)}
    </section>
{SOCIAL_FOOTER}
  </main>
{IMAGE_LIGHTBOX_MARKUP}
</body>
</html>
"""
    output_file.write_text(page, encoding="utf-8")
    return section_slug, section_title, len(media_files)


def block_to_markup(output_file: Path, block: dict) -> str:
    block_type = block.get("type")
    if block_type == "raw_html":
        return str(block.get("html", ""))
    if block_type == "text":
        text = render_text_with_inline_links(block.get("text", ""))
        tag = block.get("tag", "p").lower()
        if tag not in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "figcaption"}:
            tag = "p"
        # The source manifest contains trailing prev/next navigation labels as h2.
        # We intentionally drop h2 text blocks to avoid rendering duplicate section titles.
        if tag == "h2":
            return ""
        if tag == "li":
            tag = "p"
        return f"<article class=\"content-item\"><{tag}>{text}</{tag}></article>"
    if block_type == "link":
        raw_url = block.get("url", "") or ""
        if re.search(r"gonzalobuilds\.com", raw_url, re.IGNORECASE):
            return ""
        url = html.escape(raw_url)
        text = html.escape(block.get("text", raw_url))
        return (
            "<article class=\"content-item\">"
            f"<p><a class=\"file-link\" href=\"{url}\" target=\"_blank\" rel=\"noopener noreferrer\">{text}</a></p>"
            "</article>"
        )
    if block_type == "embed":
        raw_embed = block.get("url", "") or ""
        if re.search(r"gonzalobuilds\.com", raw_embed, re.IGNORECASE):
            return ""
        url = html.escape(raw_embed)
        if not url:
            return ""
        return (
            "<article class=\"content-item\">"
            "<div class=\"embed-wrap\">"
            f"<iframe src=\"{url}\" loading=\"lazy\" allowfullscreen referrerpolicy=\"no-referrer-when-downgrade\"></iframe>"
            "</div>"
            "</article>"
        )
    if block_type == "media":
        local = block.get("local_path")
        source = local if local else block.get("url", "")
        if not source:
            return ""
        media_path = ROOT / source if local else Path(source)
        media_rel = relpath(output_file, media_path) if local else source
        media_name = Path(source).name
        return (
            "<article class=\"content-item\">"
            f"{media_markup(media_rel, media_name)}"
            "</article>"
        )
    return ""


def render_text_with_inline_links(raw_text: str) -> str:
    """Escape text while honoring markdown-style inline links."""
    text = str(raw_text or "")
    parts: list[str] = []
    cursor = 0
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+|[A-Za-z0-9_][A-Za-z0-9_.-]*\.html)\)")
    for match in pattern.finditer(text):
        parts.append(html.escape(text[cursor : match.start()]))
        label = html.escape(match.group(1))
        href = html.escape(match.group(2), quote=True)
        if href.startswith(("http://", "https://")):
            parts.append(
                f'<a class="file-link" href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'
            )
        else:
            parts.append(f'<a class="file-link" href="{href}">{label}</a>')
        cursor = match.end()
    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def merge_following_link_into_text(blocks: list[dict]) -> list[dict]:
    """
    If a paragraph already mentions the following link text, convert that mention
    into an inline markdown link and drop the standalone link block.
    """
    updated_blocks = [dict(b) for b in blocks]
    remove_indices: set[int] = set()

    for i, current in enumerate(updated_blocks):
        if current.get("type") != "text" or (current.get("tag", "p") or "p").lower() != "p":
            continue

        paragraph = str(current.get("text", "") or "")
        if not paragraph:
            continue

        j = i + 1
        while j < len(updated_blocks) and updated_blocks[j].get("type") == "link":
            link_block = updated_blocks[j]
            raw_url = str(link_block.get("url", "") or "")
            link_text = str(link_block.get("text", "") or "")
            if (
                raw_url
                and link_text
                and not re.search(r"gonzalobuilds\.com", raw_url, re.IGNORECASE)
                and link_text in paragraph
            ):
                paragraph = paragraph.replace(link_text, f"[{link_text}]({raw_url})", 1)
                remove_indices.add(j)
            j += 1

        current["text"] = paragraph

    return [block for idx, block in enumerate(updated_blocks) if idx not in remove_indices]


def group_specific_media_triplet(
    output_file: Path,
    blocks: list[dict],
    local_paths: tuple[str, str, str],
    extra_class: str = "",
) -> list[dict]:
    """Replace one exact 3-media run with a responsive triplet block."""
    grouped: list[dict] = []
    i = 0
    while i < len(blocks):
        if i + 2 < len(blocks):
            b0, b1, b2 = blocks[i], blocks[i + 1], blocks[i + 2]
            if (
                b0.get("type") == "media"
                and b1.get("type") == "media"
                and b2.get("type") == "media"
                and b0.get("local_path") == local_paths[0]
                and b1.get("local_path") == local_paths[1]
                and b2.get("local_path") == local_paths[2]
            ):
                media_cells = []
                for local_path in local_paths:
                    media_rel = relpath(output_file, ROOT / local_path)
                    media_cells.append(
                        f"<figure class=\"media-figure\">{media_markup(media_rel, Path(local_path).name, wrap_in_figure=False)}</figure>"
                    )
                class_suffix = f" {extra_class}" if extra_class else ""
                grouped.append(
                    {
                        "type": "raw_html",
                        "html": (
                            "<article class=\"content-item\">"
                            f"<div class=\"media-triplet{class_suffix}\">"
                            f"{''.join(media_cells)}"
                            "</div>"
                            "</article>"
                        ),
                    }
                )
                i += 3
                continue
        grouped.append(blocks[i])
        i += 1
    return grouped


def group_specific_media_quad(
    output_file: Path,
    blocks: list[dict],
    local_paths: tuple[str, str, str, str],
    extra_class: str = "",
) -> list[dict]:
    """Replace one exact 4-media run with a responsive quad block."""
    grouped: list[dict] = []
    i = 0
    while i < len(blocks):
        if i + 3 < len(blocks):
            b0, b1, b2, b3 = blocks[i], blocks[i + 1], blocks[i + 2], blocks[i + 3]
            if (
                b0.get("type") == "media"
                and b1.get("type") == "media"
                and b2.get("type") == "media"
                and b3.get("type") == "media"
                and b0.get("local_path") == local_paths[0]
                and b1.get("local_path") == local_paths[1]
                and b2.get("local_path") == local_paths[2]
                and b3.get("local_path") == local_paths[3]
            ):
                media_cells = []
                for local_path in local_paths:
                    media_rel = relpath(output_file, ROOT / local_path)
                    media_cells.append(
                        f"<figure class=\"media-figure\">{media_markup(media_rel, Path(local_path).name, wrap_in_figure=False)}</figure>"
                    )
                class_suffix = f" {extra_class}" if extra_class else ""
                grouped.append(
                    {
                        "type": "raw_html",
                        "html": (
                            "<article class=\"content-item\">"
                            f"<div class=\"media-quad{class_suffix}\">"
                            f"{''.join(media_cells)}"
                            "</div>"
                            "</article>"
                        ),
                    }
                )
                i += 4
                continue
        grouped.append(blocks[i])
        i += 1
    return grouped


def group_specific_media_pair(
    output_file: Path,
    blocks: list[dict],
    local_paths: tuple[str, str],
    extra_class: str = "",
) -> list[dict]:
    """Replace one exact 2-media run with a responsive pair block."""
    grouped: list[dict] = []
    i = 0
    while i < len(blocks):
        if i + 1 < len(blocks):
            b0, b1 = blocks[i], blocks[i + 1]
            if (
                b0.get("type") == "media"
                and b1.get("type") == "media"
                and b0.get("local_path") == local_paths[0]
                and b1.get("local_path") == local_paths[1]
            ):
                media_cells = []
                for local_path in local_paths:
                    media_rel = relpath(output_file, ROOT / local_path)
                    media_cells.append(
                        f"<figure class=\"media-figure\">{media_markup(media_rel, Path(local_path).name, wrap_in_figure=False)}</figure>"
                    )
                class_suffix = f" {extra_class}" if extra_class else ""
                grouped.append(
                    {
                        "type": "raw_html",
                        "html": (
                            "<article class=\"content-item\">"
                            f"<div class=\"media-pair{class_suffix}\">"
                            f"{''.join(media_cells)}"
                            "</div>"
                            "</article>"
                        ),
                    }
                )
                i += 2
                continue
        grouped.append(blocks[i])
        i += 1
    return grouped


def split_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Optional YAML-like frontmatter between --- lines; values are single-line strings."""
    raw = raw.lstrip("\ufeff")
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        return {}, raw
    body = raw[end + 5 :]
    meta: dict[str, str] = {}
    for line in raw[4:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        meta[key.strip()] = rest.strip().strip('"').strip("'")
    return meta, body


def postprocess_markdown_html(html: str) -> str:
    """Match site conventions: external link classes, lazy images, figures for standalone images."""

    def unwrap_img_in_p(m: re.Match) -> str:
        inner = m.group(1)
        if "loading=" not in inner.lower():
            inner = inner.replace("<img ", '<img loading="lazy" ', 1)
        if "class=" not in inner.lower():
            inner = inner.replace("<img ", '<img class="media" ', 1)
        return f'<figure class="media-figure">{inner}</figure>'

    html = re.sub(r"<p>\s*(<img\b[^>]+>)\s*</p>", unwrap_img_in_p, html, flags=re.IGNORECASE)

    html = html.replace(
        '<a href="https://',
        '<a class="file-link" target="_blank" rel="noopener noreferrer" href="https://',
    )
    html = html.replace(
        '<a href="http://',
        '<a class="file-link" target="_blank" rel="noopener noreferrer" href="http://',
    )
    # Same-site section pages (sibling `pages/*.html` links from markdown)
    html = re.sub(
        r'<a href="([A-Za-z0-9_][A-Za-z0-9_.-]*\.html)"',
        r'<a class="file-link" href="\1"',
        html,
    )
    return html


def build_section_page_from_markdown(section_slug: str) -> tuple[str, str, int] | None:
    """
    If markdowns/{slug}.md exists, render it into pages/{slug}.html and skip manifest blocks for that page.
    Image paths in Markdown should be relative to the output HTML (e.g. ../assets/Double_Yc/foo.webp).
    """
    md_path = MARKDOWNS_DIR / f"{section_slug}.md"
    if not md_path.is_file():
        return None

    try:
        import markdown
    except ImportError as e:
        raise SystemExit(
            "Building from markdowns/ requires the 'markdown' package. "
            "Install dependencies: pip install -r requirements.txt"
        ) from e

    _meta, body = split_frontmatter(md_path.read_text(encoding="utf-8"))
    if not body.strip():
        raise SystemExit(f"Markdown body is empty: {md_path}")

    md = markdown.Markdown(extensions=["extra", "sane_lists"])
    body_html = postprocess_markdown_html(md.convert(body))

    section_title = title_from_slug(section_slug)
    index_titles = parse_index_section_titles()
    if section_slug in index_titles:
        h1_inner, title_plain = index_titles[section_slug]
    else:
        h1_inner = styled_title(section_title)
        title_plain = section_title

    output_file = PAGES_DIR / f"{section_slug}.html"
    blocks_html = (
        '<article class="content-item content-item--markdown">'
        f'<div class="markdown-body">{body_html}</div>'
        "</article>"
    )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title_plain)} - Gonzalo Builds</title>
  <link rel="stylesheet" href="../site.css">
</head>
<body>
  <main class="container">
    <header class="header">
      <a class="back-link" href="../index.html">&larr; All Sections</a>
      <h1>{h1_inner}</h1>
    </header>
    <section class="media-list media-list--tight">
      {blocks_html}
    </section>
{SOCIAL_FOOTER}
  </main>
{IMAGE_LIGHTBOX_MARKUP}
</body>
</html>
"""
    output_file.write_text(page, encoding="utf-8")
    return section_slug, section_title, 1


def build_section_page_from_manifest(page_data: dict) -> tuple[str, str, int]:
    section_slug = page_data["slug"]
    section_title = title_from_slug(section_slug)
    index_titles = parse_index_section_titles()
    if section_slug in index_titles:
        h1_inner, title_plain = index_titles[section_slug]
    else:
        h1_inner = styled_title(section_title)
        title_plain = section_title
    output_file = PAGES_DIR / f"{section_slug}.html"
    normalized_blocks = merge_following_link_into_text(page_data.get("blocks", []))
    if section_slug == "Red_Bull_Flugtag_2022":
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_2.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_3.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_4.webp",
            ),
            "media-triplet--flugtag-a",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_5.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_6.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_7.webp",
            ),
            "media-triplet--flugtag-a2",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_8.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_9.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_10.webp",
            ),
            "media-triplet--flugtag-b",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_11.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_12.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_13.webp",
            ),
            "media-triplet--flugtag-c",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_14.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_15.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_16.webp",
            ),
            "media-triplet--flugtag-d",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_17.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_18.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_19.webp",
            ),
            "media-triplet--flugtag-e",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_20.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_21.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_22.webp",
            ),
            "media-triplet--flugtag-f",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_23.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_24.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_25.webp",
            ),
            "media-triplet--flugtag-g",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_26.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_27.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_28.webp",
            ),
            "media-triplet--flugtag-h",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_29.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_30.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_31.webp",
            ),
            "media-triplet--flugtag-i",
        )
        normalized_blocks = group_specific_media_quad(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_32.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_33.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_34.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_35.webp",
            ),
            "media-quad--flugtag-a",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_36.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_37.webp",
                "assets/Red_Bull_Flugtag_2022/Red_Bull_Flugtag_2022_38.webp",
            ),
            "media-triplet--flugtag-j",
        )
    if section_slug == "Amy_20152016":
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_2.webp",
                "assets/Amy_20152016/Amy_20152016_3.webp",
            ),
            "media-pair--amy-a",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_4.webp",
                "assets/Amy_20152016/Amy_20152016_5.webp",
                "assets/Amy_20152016/Amy_20152016_6.webp",
            ),
            "media-triplet--amy-b",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_7.webp",
                "assets/Amy_20152016/Amy_20152016_8.webp",
                "assets/Amy_20152016/Amy_20152016_9.webp",
            ),
            "media-triplet--amy-c",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_10.webp",
                "assets/Amy_20152016/Amy_20152016_11.webp",
            ),
            "media-pair--amy-d",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_12.webp",
                "assets/Amy_20152016/Amy_20152016_13.webp",
                "assets/Amy_20152016/Amy_20152016_14.webp",
            ),
            "media-triplet--amy-e",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_15.webp",
                "assets/Amy_20152016/Amy_20152016_16.webp",
            ),
            "media-pair--amy-f",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_17.webp",
                "assets/Amy_20152016/Amy_20152016_18.webp",
            ),
            "media-pair--amy-g",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Amy_20152016/Amy_20152016_19.webp",
                "assets/Amy_20152016/Amy_20152016_20.webp",
            ),
            "media-pair--amy-h",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Home/Home_13.webp",
                "assets/Amy_20152016/Amy_20152016_22.webp",
            ),
            "media-pair--amy-i",
        )
    if section_slug == "Bolt_20162017":
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_3.webp",
                "assets/Bolt_20162017/Bolt_20162017_4.webp",
            ),
            "media-pair--bolt-a",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_5.webp",
                "assets/Bolt_20162017/Bolt_20162017_6.webp",
            ),
            "media-pair--bolt-b",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_7.webp",
                "assets/Bolt_20162017/Bolt_20162017_8.webp",
                "assets/Bolt_20162017/Bolt_20162017_9.webp",
            ),
            "media-triplet--bolt-c",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_10.webp",
                "assets/Bolt_20162017/Bolt_20162017_11.webp",
                "assets/Bolt_20162017/Bolt_20162017_12.webp",
            ),
            "media-triplet--bolt-d",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_13.webp",
                "assets/Bolt_20162017/Bolt_20162017_14.webp",
                "assets/Bolt_20162017/Bolt_20162017_15.webp",
            ),
            "media-triplet--bolt-e",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_16.webp",
                "assets/Bolt_20162017/Bolt_20162017_17.webp",
            ),
            "media-pair--bolt-f",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_18.webp",
                "assets/Bolt_20162017/Bolt_20162017_19.webp",
                "assets/Bolt_20162017/Bolt_20162017_20.webp",
            ),
            "media-triplet--bolt-g",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_21.webp",
                "assets/Bolt_20162017/Bolt_20162017_22.webp",
            ),
            "media-pair--bolt-h",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_23.webp",
                "assets/Bolt_20162017/Bolt_20162017_24.webp",
                "assets/Bolt_20162017/Bolt_20162017_25.webp",
            ),
            "media-triplet--bolt-i",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_26.webp",
                "assets/Bolt_20162017/Bolt_20162017_27.webp",
                "assets/Bolt_20162017/Bolt_20162017_28.webp",
            ),
            "media-triplet--bolt-j",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_29.webp",
                "assets/Bolt_20162017/Bolt_20162017_30.webp",
            ),
            "media-pair--bolt-k",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_31.webp",
                "assets/Bolt_20162017/Bolt_20162017_32.webp",
                "assets/Bolt_20162017/Bolt_20162017_33.webp",
            ),
            "media-triplet--bolt-l",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Bolt_20162017/Bolt_20162017_34.webp",
                "assets/Bolt_20162017/Bolt_20162017_35.webp",
            ),
            "media-pair--bolt-m",
        )
    if section_slug == "Clare_20172019":
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_2.webp",
                "assets/Clare_20172019/Clare_20172019_3.webp",
            ),
            "media-pair--clare-a",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_4.webp",
                "assets/Clare_20172019/Clare_20172019_5.webp",
            ),
            "media-pair--clare-b",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_6.webp",
                "assets/Clare_20172019/Clare_20172019_7.webp",
            ),
            "media-pair--clare-c",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_8.webp",
                "assets/Clare_20172019/Clare_20172019_9.webp",
                "assets/Clare_20172019/Clare_20172019_10.webp",
            ),
            "media-triplet--clare-d",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_11.webp",
                "assets/Clare_20172019/Clare_20172019_12.webp",
                "assets/Clare_20172019/Clare_20172019_13.webp",
            ),
            "media-triplet--clare-e",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_14.webp",
                "assets/Clare_20172019/Clare_20172019_15.webp",
                "assets/Clare_20172019/Clare_20172019_16.webp",
            ),
            "media-triplet--clare-f",
        )
        normalized_blocks = group_specific_media_quad(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_17.webp",
                "assets/Clare_20172019/Clare_20172019_18.webp",
                "assets/Clare_20172019/Clare_20172019_19.webp",
                "assets/Clare_20172019/Clare_20172019_20.webp",
            ),
            "media-quad--clare-g",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_21.webp",
                "assets/Clare_20172019/Clare_20172019_22.webp",
            ),
            "media-pair--clare-h",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_23.webp",
                "assets/Clare_20172019/Clare_20172019_24.webp",
                "assets/Clare_20172019/Clare_20172019_25.webp",
            ),
            "media-triplet--clare-i",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_26.webp",
                "assets/Clare_20172019/Clare_20172019_27.webp",
                "assets/Clare_20172019/Clare_20172019_28.webp",
            ),
            "media-triplet--clare-j",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_29.webp",
                "assets/Clare_20172019/Clare_20172019_30.webp",
                "assets/Clare_20172019/Clare_20172019_31.webp",
            ),
            "media-triplet--clare-k",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_32.webp",
                "assets/Clare_20172019/Clare_20172019_33.webp",
                "assets/Clare_20172019/Clare_20172019_34.webp",
            ),
            "media-triplet--clare-l",
        )
        normalized_blocks = group_specific_media_triplet(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_35.webp",
                "assets/Clare_20172019/Clare_20172019_36.webp",
                "assets/Clare_20172019/Clare_20172019_37.webp",
            ),
            "media-triplet--clare-m",
        )
        normalized_blocks = group_specific_media_pair(
            output_file,
            normalized_blocks,
            (
                "assets/Clare_20172019/Clare_20172019_38.webp",
                "assets/Clare_20172019/Clare_20172019_39.webp",
            ),
            "media-pair--clare-n",
        )
    blocks = [block_to_markup(output_file, block) for block in normalized_blocks]
    blocks = [b for b in blocks if b]
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title_plain)} - Gonzalo Builds</title>
  <link rel="stylesheet" href="../site.css">
</head>
<body>
  <main class="container">
    <header class="header">
      <a class="back-link" href="../index.html">&larr; All Sections</a>
      <h1>{h1_inner}</h1>
    </header>
    <section class="media-list">
      {"".join(blocks)}
    </section>
{SOCIAL_FOOTER}
  </main>
{IMAGE_LIGHTBOX_MARKUP}
</body>
</html>
"""
    output_file.write_text(page, encoding="utf-8")
    return section_slug, section_title, len(blocks)


def write_styles() -> None:
    if STYLE_FILE.exists():
        head = STYLE_FILE.read_text(encoding="utf-8")[:800]
        if "SITE_CSS_LOCKED" in head:
            return
    css = """* { box-sizing: border-box; }
body {
  margin: 0;
  padding-inline: clamp(24px, 12vw, 220px);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #0d1117;
  color: #e6edf3;
}
.container {
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 0 48px;
}
.header h1 {
  margin: 0 0 10px;
  font-size: clamp(1.8rem, 3vw, 2.6rem);
  color: #58a6ff;
}
.header h1 .card-year {
  font-size: 0.85em;
  color: #9ea7b3;
  font-weight: 500;
}
.header p {
  margin: 0;
  color: #9ea7b3;
}
.back-link {
  color: #8cc7ff;
  text-decoration: none;
  display: inline-block;
  margin-bottom: 14px;
}
.grid {
  margin-top: 26px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.card {
  display: flex;
  flex-direction: column;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 0;
  overflow: hidden;
  text-decoration: none;
  color: inherit;
}
.card:hover {
  border-color: #58a6ff;
  transform: translateY(-1px);
}
.card-hero {
  aspect-ratio: 16 / 9;
  background: #0d1117;
}
.card-hero-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.grid--compact-cards {
  align-items: flex-start;
  gap: 12px;
}
.grid--compact-cards .card {
  width: fit-content;
  max-width: min(560px, 100%);
  align-self: flex-start;
}
.grid--compact-cards .card-hero {
  aspect-ratio: unset;
  height: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 14px;
  background: #0d1117;
  box-sizing: border-box;
}
.grid--compact-cards .card-hero-img {
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: clamp(168px, 28vh, 300px);
  object-fit: contain;
  border-radius: 8px;
  display: block;
}
.grid--compact-cards .card-body {
  padding: 10px 14px 12px;
  max-width: 100%;
  box-sizing: border-box;
}
.grid--compact-cards .card-body h2 {
  overflow-wrap: break-word;
  word-wrap: break-word;
}
.card-body {
  padding: 14px 16px 16px;
}
.card h2 {
  margin: 0;
  font-size: 1.05rem;
}
.card p {
  margin: 0;
  color: #9ea7b3;
}
.media-list {
  margin-top: 26px;
  display: grid;
  gap: 16px;
}
.media-item {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 14px;
}
.media-item h3 {
  margin: 0 0 10px;
  font-size: 0.95rem;
  color: #9ea7b3;
}
.media {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 10px;
  overflow: hidden;
  background: #0d1117;
  max-height: 80vh;
  object-fit: contain;
}
.file-link {
  color: #8cc7ff;
}
.content-item p,
.content-item blockquote,
.content-item figcaption,
.content-item h1,
.content-item h2,
.content-item h3,
.content-item h4,
.content-item h5,
.content-item h6 {
  margin: 0;
  line-height: 1.6;
}
.embed-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
}
.embed-wrap iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
  border-radius: 8px;
}
"""
    STYLE_FILE.write_text(css, encoding="utf-8")


def main() -> None:
    if not ASSETS_DIR.exists():
        raise SystemExit("assets folder not found. Run crawl first.")

    if _posthog:
        _posthog.capture(
            distinct_id=_DISTINCT_ID,
            event="site_generation_started",
            properties={},
        )

    try:
        PAGES_DIR.mkdir(parents=True, exist_ok=True)
        write_styles()

        sections = []
        if MANIFEST_FILE.exists():
            manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
            pages = manifest.get("pages", [])
            for page_data in sorted(pages, key=lambda p: p.get("slug", "").lower()):
                slug = page_data.get("slug", "")
                from_md = build_section_page_from_markdown(slug) if slug else None
                if from_md:
                    sections.append(from_md)
                else:
                    sections.append(build_section_page_from_manifest(page_data))
        else:
            for section_dir in sorted([d for d in ASSETS_DIR.iterdir() if d.is_dir()], key=lambda p: p.name.lower()):
                sections.append(build_section_page(section_dir))

        build_index(sections)
        print(f"Generated {len(sections)} section pages in {PAGES_DIR}")

        if _posthog:
            _posthog.capture(
                distinct_id=_DISTINCT_ID,
                event="site_generation_completed",
                properties={"pages_generated": len(sections)},
            )
    except Exception as exc:
        if _posthog:
            _posthog.capture_exception(exc, _DISTINCT_ID)
        raise
    finally:
        if _posthog:
            _posthog.shutdown()


if __name__ == "__main__":
    main()

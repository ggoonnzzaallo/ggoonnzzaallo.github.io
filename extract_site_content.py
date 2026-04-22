#!/usr/bin/env python3
"""
Extract ordered website content (text, links, embeds, media) and save a manifest.
Also downloads media assets locally with deduplication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".ogv"}
MIME_EXTENSION_OVERRIDES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "video/ogg": ".ogv",
}
SKIP_PATH_PATTERNS = (
    r"^/cart/?$",
    r"^/account/?$",
    r"^/checkout/?$",
    r"^/config/?$",
    r"^/search/?$",
)


def normalize_url(raw_url: str, base_url: str) -> str | None:
    if not raw_url:
        return None
    raw_url = raw_url.strip()
    if raw_url.startswith("data:"):
        return None
    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url
    absolute = urljoin(base_url, raw_url)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def is_internal_link(url: str, root_netloc: str) -> bool:
    return urlparse(url).netloc == root_netloc


def should_skip_url(url: str, root_netloc: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc != root_netloc:
        return True
    path = parsed.path.rstrip("/") or "/"
    for pattern in SKIP_PATH_PATTERNS:
        if re.match(pattern, path, flags=re.IGNORECASE):
            return True
    return False


def is_image_like(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return True
    query = parsed.query.lower()
    return "format=jpg" in query or "format=png" in query or "format=webp" in query


def is_video_like(url: str) -> bool:
    return any(urlparse(url).path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)


def is_media_like(url: str) -> bool:
    return is_image_like(url) or is_video_like(url)


def select_best_from_srcset(srcset: str, base_url: str) -> str | None:
    best_url = None
    best_score = -1.0
    for item in srcset.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split()
        candidate = normalize_url(parts[0], base_url)
        if not candidate:
            continue
        score = 0.0
        if len(parts) >= 2:
            descriptor = parts[1].strip().lower()
            if descriptor.endswith("w"):
                try:
                    score = float(descriptor[:-1])
                except ValueError:
                    score = 0.0
            elif descriptor.endswith("x"):
                try:
                    score = float(descriptor[:-1]) * 1000
                except ValueError:
                    score = 0.0
        if score >= best_score:
            best_score = score
            best_url = candidate
    return best_url


def upscale_squarespace_url(url: str, target_width: int = 5000) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    changed = False
    for key in ("width", "imwidth"):
        if key in query:
            try:
                if int(query[key][0]) < target_width:
                    query[key] = [str(target_width)]
                    changed = True
            except ValueError:
                pass
    if "format" in query:
        m = re.match(r"(\d+)w$", query["format"][0], flags=re.IGNORECASE)
        if m and int(m.group(1)) < target_width:
            query["format"] = [f"{target_width}w"]
            changed = True
    if not changed:
        return url
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(query, doseq=True), ""))


def slugify_page_name(page_url: str, root_netloc: str) -> str:
    parsed = urlparse(page_url)
    if parsed.netloc != root_netloc:
        return "External"
    path = parsed.path.strip("/")
    if not path:
        return "Home"
    words = [w for w in re.split(r"[-_/]+", path.split("/")[-1]) if w]
    label = "_".join(word.capitalize() for word in words)
    return re.sub(r"[^a-zA-Z0-9_]", "", label) or "Page"


def detect_youtube_embed(url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    return "youtube.com" in netloc or "youtu.be" in netloc


def extract_page_blocks(page, current_url: str) -> tuple[list[dict], set[str]]:
    payload = page.evaluate(
        """
        () => {
          const blocks = [];
          const links = [];
          let idx = 0;
          const selectors = "h1,h2,h3,h4,h5,h6,p,li,blockquote,figcaption,a[href],iframe[src],img,picture source[srcset],video,video source[src]";
          document.querySelectorAll(selectors).forEach((el) => {
            const rect = el.getBoundingClientRect();
            const top = Number.isFinite(rect.top) ? rect.top : 0;
            const tag = el.tagName.toLowerCase();
            const text = (el.textContent || "").trim().replace(/\\s+/g, " ");
            if (tag === "a") {
              blocks.push({kind: "link", url: el.getAttribute("href"), text, top, idx});
            } else if (tag === "iframe") {
              blocks.push({kind: "embed", url: el.getAttribute("src"), text, top, idx});
            } else if (tag === "img") {
              blocks.push({kind: "media", url: el.currentSrc || el.src, srcset: el.srcset || "", top, idx});
            } else if (tag === "source") {
              const srcset = el.srcset || "";
              const src = el.getAttribute("src") || "";
              blocks.push({kind: "media", url: src, srcset, top, idx});
            } else if (tag === "video") {
              blocks.push({kind: "media", url: el.getAttribute("src") || "", srcset: "", top, idx});
            } else if (text.length > 0) {
              blocks.push({kind: "text", text, tag, top, idx});
            }
            idx += 1;
          });
          document.querySelectorAll("a[href]").forEach((a) => links.push(a.getAttribute("href")));
          return {blocks, links};
        }
        """
    )
    out_blocks: list[dict] = []
    seen_keys: set[str] = set()
    for block in sorted(payload["blocks"], key=lambda b: (float(b.get("top", 0)), int(b.get("idx", 0)))):
        kind = block.get("kind")
        if kind == "media":
            media_url = None
            srcset = block.get("srcset") or ""
            if srcset:
                media_url = select_best_from_srcset(srcset, current_url)
            if not media_url and block.get("url"):
                media_url = normalize_url(block.get("url"), current_url)
            if not media_url:
                continue
            media_url = upscale_squarespace_url(media_url) if is_image_like(media_url) else media_url
            if not is_media_like(media_url):
                continue
            key = f"media:{media_url}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out_blocks.append({"type": "media", "url": media_url})
        elif kind == "embed":
            url = normalize_url(block.get("url"), current_url)
            if not url:
                continue
            key = f"embed:{url}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out_blocks.append({"type": "embed", "url": url, "provider": "youtube" if detect_youtube_embed(url) else "iframe"})
        elif kind == "link":
            url = normalize_url(block.get("url"), current_url)
            text = (block.get("text") or "").strip()
            if not url or not text:
                continue
            key = f"link:{url}:{text}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out_blocks.append({"type": "link", "url": url, "text": text})
        elif kind == "text":
            text = (block.get("text") or "").strip()
            if len(text) < 2:
                continue
            key = f"text:{text}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out_blocks.append({"type": "text", "text": text, "tag": block.get("tag", "p")})

    internal_links: set[str] = set()
    root_netloc = urlparse(current_url).netloc
    for href in payload["links"]:
        normalized = normalize_url(href, current_url)
        if normalized and is_internal_link(normalized, root_netloc):
            internal_links.add(normalized)
    return out_blocks, internal_links


def extension_for_content_type(content_type: str | None) -> str:
    if not content_type:
        return ".bin"
    normalized = content_type.split(";")[0].strip().lower()
    return MIME_EXTENSION_OVERRIDES.get(normalized) or mimetypes.guess_extension(normalized) or ".bin"


def crawl_site(start_url: str, max_pages: int, page_timeout_ms: int, delay_seconds: float) -> list[dict]:
    root_netloc = urlparse(start_url).netloc
    seen_pages: set[str] = set()
    queue: deque[str] = deque([start_url])
    pages: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"], slow_mo=50)
        context = browser.new_context(viewport=None)
        page = context.new_page()
        while queue and len(seen_pages) < max_pages:
            url = queue.popleft()
            if url in seen_pages:
                continue
            print(f"[crawl] Visiting {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=page_timeout_ms)
                page.wait_for_timeout(1200)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(900)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(600)
            except PlaywrightTimeoutError:
                print(f"[warn] Timed out loading {url}")
                seen_pages.add(url)
                time.sleep(delay_seconds)
                continue
            blocks, links = extract_page_blocks(page, url)
            for link in links:
                if should_skip_url(link, root_netloc):
                    continue
                if is_internal_link(link, root_netloc) and link not in seen_pages:
                    queue.append(link)
            pages.append({"url": url, "slug": slugify_page_name(url, root_netloc), "blocks": blocks})
            seen_pages.add(url)
            print(
                f"[crawl] captured {len(blocks)} ordered blocks "
                f"({len(seen_pages)}/{max_pages} pages)"
            )
            time.sleep(delay_seconds)
        context.close()
        browser.close()
    return pages


def download_media_for_manifest(pages: list[dict], output_dir: Path, timeout_seconds: int, delay_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    seen_hash_to_path: dict[str, str] = {}
    source_url_to_path: dict[str, str] = {}
    page_seq: dict[str, int] = {}
    total_media_blocks = sum(
        1 for page in pages for block in page["blocks"] if block.get("type") == "media"
    )
    processed_media = 0
    for page in pages:
        slug = page["slug"]
        for block in page["blocks"]:
            if block.get("type") != "media":
                continue
            processed_media += 1
            source_url = block["url"]
            print(f"[download] media {processed_media}/{total_media_blocks}: {source_url}")
            if source_url in source_url_to_path:
                block["local_path"] = source_url_to_path[source_url]
                continue
            try:
                response = session.get(source_url, timeout=timeout_seconds, stream=True)
                response.raise_for_status()
            except requests.RequestException as exc:
                print(f"[warn] download failed: {source_url} ({exc})")
                continue
            content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
            if not (content_type.startswith("image/") or content_type.startswith("video/")):
                response.close()
                continue
            ext = extension_for_content_type(content_type)
            page_folder = output_dir / slug
            page_folder.mkdir(parents=True, exist_ok=True)
            page_seq[slug] = page_seq.get(slug, 0) + 1
            filename = f"{slug}_{page_seq[slug]}{ext}"
            destination = page_folder / filename
            tmp_destination = destination.with_suffix(destination.suffix + ".part")
            digest = hashlib.sha256()
            try:
                with tmp_destination.open("wb") as fh:
                    for chunk in response.iter_content(chunk_size=1024 * 128):
                        if chunk:
                            digest.update(chunk)
                            fh.write(chunk)
            finally:
                response.close()
            file_hash = digest.hexdigest()
            if file_hash in seen_hash_to_path:
                tmp_destination.unlink(missing_ok=True)
                local_path = seen_hash_to_path[file_hash]
            else:
                tmp_destination.rename(destination)
                local_path = str(destination.relative_to(output_dir.parent)).replace("\\", "/")
                seen_hash_to_path[file_hash] = local_path
            source_url_to_path[source_url] = local_path
            block["local_path"] = local_path
            time.sleep(delay_seconds)


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract ordered text/links/media/embed content from a site.")
    parser.add_argument("--url", default="https://www.gonzalobuilds.com/", help="Start URL")
    parser.add_argument("--output", default="assets", help="Assets output folder")
    parser.add_argument("--manifest", default="content_manifest.json", help="Output manifest JSON file")
    parser.add_argument("--max-pages", type=int, default=120, help="Maximum internal pages to crawl")
    parser.add_argument("--page-timeout-ms", type=int, default=45000, help="Per-page timeout")
    parser.add_argument("--request-timeout", type=int, default=30, help="Per-download timeout")
    parser.add_argument("--delay", type=float, default=1.6, help="Delay between requests")
    return parser.parse_args()


def main() -> None:
    args = build_args()
    start_url = args.url.rstrip("/") + "/"
    pages = crawl_site(start_url, args.max_pages, args.page_timeout_ms, args.delay)
    assets_dir = Path(args.output).expanduser().resolve()
    download_media_for_manifest(pages, assets_dir, args.request_timeout, args.delay)
    manifest = {"site_url": start_url, "pages": pages}
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[done] wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()

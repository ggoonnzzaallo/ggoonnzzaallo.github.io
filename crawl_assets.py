#!/usr/bin/env python3
"""
Crawl a website and download image assets (including GIFs) locally.

Designed for Squarespace-like sites where higher-resolution image URLs may be
available by adjusting width parameters.
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse, urlencode

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".svg",
    ".avif",
    ".bmp",
    ".tif",
    ".tiff",
}
MIME_EXTENSION_OVERRIDES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
}


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
    parsed = urlparse(url)
    return parsed.netloc == root_netloc


def is_image_like(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return True
    query = parsed.query.lower()
    if "format=jpg" in query or "format=png" in query or "format=webp" in query:
        return True
    return False


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

    if "format" in query:
        val = query["format"][0]
        match = re.match(r"(\d+)w$", val, flags=re.IGNORECASE)
        if match:
            if int(match.group(1)) < target_width:
                query["format"] = [f"{target_width}w"]
                changed = True

    if "width" in query:
        try:
            width = int(query["width"][0])
            if width < target_width:
                query["width"] = [str(target_width)]
                changed = True
        except ValueError:
            pass

    if "imwidth" in query:
        try:
            imwidth = int(query["imwidth"][0])
            if imwidth < target_width:
                query["imwidth"] = [str(target_width)]
                changed = True
        except ValueError:
            pass

    if not changed:
        return url
    updated_query = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", updated_query, ""))


def ensure_unique_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    idx = 1
    while True:
        candidate = parent / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def filename_for_url(url: str, content_type: str | None = None) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        name = f"asset_{digest}"

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    ext = Path(safe_name).suffix.lower()

    if not ext:
        guessed = None
        if content_type:
            content_type = content_type.split(";")[0].strip().lower()
            guessed = MIME_EXTENSION_OVERRIDES.get(content_type)
            if not guessed:
                guessed = mimetypes.guess_extension(content_type)
        if not guessed:
            guessed = ".bin"
        safe_name += guessed
    return safe_name


def extract_assets_and_links(page, current_url: str) -> tuple[set[str], set[str]]:
    payload = page.evaluate(
        """
        () => {
            const images = [];
            const links = [];

            document.querySelectorAll("img").forEach((img) => {
                if (img.currentSrc) images.push({kind: "src", value: img.currentSrc});
                if (img.src) images.push({kind: "src", value: img.src});
                if (img.srcset) images.push({kind: "srcset", value: img.srcset});
            });

            document.querySelectorAll("picture source[srcset]").forEach((source) => {
                images.push({kind: "srcset", value: source.srcset});
            });

            document.querySelectorAll("video source[src], video[src]").forEach((v) => {
                if (v.src) images.push({kind: "src", value: v.src});
            });

            document.querySelectorAll("*").forEach((el) => {
                const bg = getComputedStyle(el).backgroundImage;
                if (!bg || bg === "none") return;
                const matches = [...bg.matchAll(/url\\((['"]?)(.*?)\\1\\)/g)];
                matches.forEach((m) => {
                    if (m[2]) images.push({kind: "src", value: m[2]});
                });
            });

            document.querySelectorAll("a[href]").forEach((a) => {
                links.push(a.getAttribute("href"));
            });

            return {images, links};
        }
        """
    )

    asset_urls: set[str] = set()
    internal_links: set[str] = set()

    for entry in payload["images"]:
        kind = entry["kind"]
        value = entry["value"]
        if kind == "srcset":
            best = select_best_from_srcset(value, current_url)
            if best:
                asset_urls.add(best)
        else:
            normalized = normalize_url(value, current_url)
            if normalized:
                asset_urls.add(normalized)

    root_netloc = urlparse(current_url).netloc
    for href in payload["links"]:
        normalized = normalize_url(href, current_url)
        if normalized and is_internal_link(normalized, root_netloc):
            internal_links.add(normalized)

    return asset_urls, internal_links


def fetch_asset_urls_with_browser(
    start_url: str,
    max_pages: int,
    page_timeout_ms: int,
    delay_seconds: float,
) -> set[str]:
    root_netloc = urlparse(start_url).netloc
    seen_pages: set[str] = set()
    queue: deque[str] = deque([start_url])
    assets: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
            slow_mo=50,
        )
        context = browser.new_context(
            viewport=None,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
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
            except Exception as exc:
                print(f"[warn] Failed to load {url}: {exc}")
                seen_pages.add(url)
                time.sleep(delay_seconds)
                continue

            page_assets, page_links = extract_assets_and_links(page, url)

            for asset in page_assets:
                upgraded = upscale_squarespace_url(asset)
                assets.add(upgraded)
                assets.add(asset)

            for link in page_links:
                if is_internal_link(link, root_netloc) and link not in seen_pages:
                    queue.append(link)

            seen_pages.add(url)
            print(
                f"[crawl] {len(page_assets)} assets from page "
                f"({len(seen_pages)}/{max_pages} pages scanned)"
            )
            time.sleep(delay_seconds)

        context.close()
        browser.close()

    image_assets = {a for a in assets if is_image_like(a)}
    return image_assets


def download_assets(
    urls: Iterable[str],
    output_dir: Path,
    timeout_seconds: int,
    delay_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.gonzalobuilds.com/",
        }
    )

    downloaded = 0
    skipped = 0

    for idx, url in enumerate(sorted(set(urls)), start=1):
        print(f"[download] ({idx}) {url}")
        try:
            response = session.get(url, timeout=timeout_seconds, stream=True)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"[warn] Failed: {exc}")
            skipped += 1
            time.sleep(delay_seconds)
            continue

        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        if content_type and not content_type.startswith("image/"):
            if "gif" not in content_type:
                print(f"[skip] Not an image content type: {content_type}")
                skipped += 1
                response.close()
                time.sleep(delay_seconds)
                continue

        filename = filename_for_url(url, content_type)
        destination = ensure_unique_path(output_dir / filename)

        try:
            with destination.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        fh.write(chunk)
            downloaded += 1
        except OSError as exc:
            print(f"[warn] File write failed for {destination.name}: {exc}")
            skipped += 1
        finally:
            response.close()

        time.sleep(delay_seconds)

    print(f"[done] Downloaded: {downloaded}, skipped: {skipped}, total: {downloaded + skipped}")


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl website pages and download image/GIF assets."
    )
    parser.add_argument(
        "--url",
        default="https://www.gonzalobuilds.com/",
        help="Starting URL (default: https://www.gonzalobuilds.com/)",
    )
    parser.add_argument(
        "--output",
        default="assets",
        help="Output folder for downloaded assets (default: assets)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=120,
        help="Maximum internal pages to crawl (default: 120)",
    )
    parser.add_argument(
        "--page-timeout-ms",
        type=int,
        default=45000,
        help="Per-page browser load timeout in ms (default: 45000)",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=30,
        help="Per-asset download timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.6,
        help="Delay between page visits/downloads in seconds (default: 1.6)",
    )
    return parser.parse_args()


def main() -> None:
    args = build_args()
    start_url = args.url.rstrip("/") + "/"
    output_dir = Path(args.output).expanduser().resolve()

    print(f"[start] Crawling {start_url}")
    print(f"[start] Saving assets into: {output_dir}")

    asset_urls = fetch_asset_urls_with_browser(
        start_url=start_url,
        max_pages=args.max_pages,
        page_timeout_ms=args.page_timeout_ms,
        delay_seconds=args.delay,
    )
    print(f"[crawl] Collected {len(asset_urls)} unique image-like asset URLs")

    download_assets(
        urls=asset_urls,
        output_dir=output_dir,
        timeout_seconds=args.request_timeout,
        delay_seconds=args.delay,
    )


if __name__ == "__main__":
    main()

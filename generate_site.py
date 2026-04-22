#!/usr/bin/env python3
"""
Generate a static GitHub Pages structure from downloaded assets.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
PAGES_DIR = ROOT / "pages"
STYLE_FILE = ROOT / "site.css"
INDEX_FILE = ROOT / "index.html"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".ogv"}


def title_from_slug(slug: str) -> str:
    return slug.replace("_", " ").strip()


def parse_numeric_suffix(filename: str) -> int:
    match = re.search(r"_(\d+)\.[^.]+$", filename)
    if match:
        return int(match.group(1))
    return 10**9


def relpath(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace("\\", "/")


def media_markup(media_rel_path: str, media_name: str) -> str:
    ext = Path(media_name).suffix.lower()
    escaped_alt = html.escape(media_name)
    if ext in VIDEO_EXTENSIONS:
        return (
            f'<video controls preload="metadata" playsinline class="media">'
            f'<source src="{media_rel_path}">'
            "Your browser does not support the video tag."
            "</video>"
        )
    if ext in IMAGE_EXTENSIONS:
        return f'<img src="{media_rel_path}" alt="{escaped_alt}" loading="lazy" class="media">'
    return (
        f'<a href="{media_rel_path}" class="file-link" target="_blank" rel="noopener noreferrer">'
        f"{escaped_alt}</a>"
    )


def build_index(sections: list[tuple[str, str, int]]) -> None:
    cards = []
    for section_slug, section_title, count in sections:
        cards.append(
            "<a class=\"card\" href=\"pages/{slug}.html\">"
            "<h2>{title}</h2>"
            "<p>{count} assets</p>"
            "</a>".format(
                slug=html.escape(section_slug),
                title=html.escape(section_title),
                count=count,
            )
        )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gonzalo Builds</title>
  <link rel="stylesheet" href="site.css">
</head>
<body>
  <main class="container">
    <header class="header">
      <h1>Gonzalo Builds</h1>
      <p>Recovered Squarespace structure and assets.</p>
    </header>
    <section class="grid">
      {"".join(cards)}
    </section>
  </main>
</body>
</html>
"""
    INDEX_FILE.write_text(page, encoding="utf-8")


def build_section_page(section_dir: Path) -> tuple[str, str, int]:
    section_slug = section_dir.name
    section_title = title_from_slug(section_slug)
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
            f"{media_markup(media_rel, media.name)}"
            "</article>"
        )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(section_title)} - Gonzalo Builds</title>
  <link rel="stylesheet" href="../site.css">
</head>
<body>
  <main class="container">
    <header class="header">
      <a class="back-link" href="../index.html">&larr; All Sections</a>
      <h1>{html.escape(section_title)}</h1>
      <p>{len(media_files)} assets</p>
    </header>
    <section class="media-list">
      {"".join(blocks)}
    </section>
  </main>
</body>
</html>
"""
    output_file.write_text(page, encoding="utf-8")
    return section_slug, section_title, len(media_files)


def write_styles() -> None:
    css = """* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #0d1117;
  color: #e6edf3;
}
.container {
  width: min(1100px, 92%);
  margin: 0 auto;
  padding: 32px 0 48px;
}
.header h1 {
  margin: 0 0 10px;
  font-size: clamp(1.8rem, 3vw, 2.6rem);
  color: #58a6ff;
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
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 14px;
}
.card {
  display: block;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 16px;
  text-decoration: none;
  color: inherit;
}
.card:hover {
  border-color: #58a6ff;
  transform: translateY(-1px);
}
.card h2 {
  margin: 0 0 8px;
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
  border-radius: 8px;
  background: #0d1117;
  max-height: 80vh;
  object-fit: contain;
}
.file-link {
  color: #8cc7ff;
}
"""
    STYLE_FILE.write_text(css, encoding="utf-8")


def main() -> None:
    if not ASSETS_DIR.exists():
        raise SystemExit("assets folder not found. Run crawl first.")

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    write_styles()

    sections = []
    for section_dir in sorted([d for d in ASSETS_DIR.iterdir() if d.is_dir()], key=lambda p: p.name.lower()):
        sections.append(build_section_page(section_dir))

    build_index(sections)
    print(f"Generated {len(sections)} section pages in {PAGES_DIR}")


if __name__ == "__main__":
    main()

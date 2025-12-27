#!/usr/bin/env python3
"""
Anime Subtitle to EPUB Converter

Converts ZIP/7z archives containing .srt subtitle files into EPUB format
with cover images fetched from MyAnimeList via Jikan API.
"""

import os
import re
import sys
import zipfile
import tempfile
import shutil
import urllib.request
import urllib.parse
import json
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

# Check for required packages and install if missing
def ensure_packages():
    """Ensure required packages are installed."""
    required = {
        'ebooklib': 'ebooklib',
        'py7zr': 'py7zr'
    }

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"Installing required packages: {', '.join(missing)}")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Packages installed successfully!")

ensure_packages()

from ebooklib import epub
import py7zr


# Configuration
SCRIPT_DIR = Path(__file__).parent
ORIGINAL_DIR = SCRIPT_DIR / "Original"
MERGED_DIR = SCRIPT_DIR / "Merged"

# Jikan API (MyAnimeList unofficial API - free, no auth needed)
JIKAN_SEARCH_URL = "https://api.jikan.moe/v4/anime"


def extract_anime_name(filename: str) -> str:
    """Extract anime name from archive filename for searching."""
    # Remove extension
    name = Path(filename).stem

    # Common patterns to clean up (order matters!)
    patterns = [
        r'\s*\([\d\-]+\)\s*',              # (01-26)
        r'\s*\([^)]*\)\s*',                 # (anything in parentheses)
        r'\s*\[[^\]]*\]\s*',                # [anything in brackets]
        r'\s*S\d+E\d+.*$',                  # S01E01 and everything after
        r'\s*\d{4}\s*',                     # Year like 2009
        r'\.S\d+E\d+.*$',                   # .S01E01 pattern
        r'\s*Webrip.*$',                    # Webrip and after
        r'\.Netflix.*$',                    # .Netflix pattern
        r'\.jpn\.srt.*$',                   # .jpn.srt pattern
        r'\.JA\[cc\].*$',                   # .JA[cc] pattern
    ]

    for pattern in patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Replace dots and underscores with spaces
    name = name.replace('.', ' ').replace('_', ' ')

    # Remove common trailing words (after removing parentheses may leave these attached)
    trailing_patterns = [
        r'\s*complete.*$',                  # "complete for Judas" etc
        r'\s+for\s+\w+.*$',                 # "for Judas" etc
        r'\s+batch.*$',                     # "batch" etc
        r'\s+season\s*\d*.*$',              # "season 1" etc
    ]

    for pattern in trailing_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove trailing/leading special characters
    name = re.sub(r'^[\s\(\)\[\]\-\.]+|[\s\(\)\[\]\-\.]+$', '', name)

    # Clean up extra whitespace
    name = ' '.join(name.split())

    return name.strip()


def parse_srt_content(content: str) -> list[str]:
    """Parse SRT content and extract subtitle text lines."""
    lines = []

    # Some Netflix SRTs have literal \n instead of actual newlines - convert them
    if '\\n' in content and '\n' not in content[:1000]:
        content = content.replace('\\n', '\n')

    # Also handle case where both exist
    content = content.replace('\\n', '\n')

    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Remove HTML entities
    content = content.replace('&lrm;', '')  # Left-to-right mark
    content = content.replace('&rlm;', '')  # Right-to-left mark
    content = content.replace('&nbsp;', ' ')

    # Remove Unicode directional formatting characters
    content = content.replace('\u202a', '')  # LTR embedding
    content = content.replace('\u202b', '')  # RTL embedding
    content = content.replace('\u202c', '')  # Pop directional formatting
    content = content.replace('\u200e', '')  # LTR mark
    content = content.replace('\u200f', '')  # RTL mark
    content = content.replace('\ufeff', '')  # BOM

    # Split into blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', content)

    for block in blocks:
        block_lines = block.strip().split('\n')

        for line in block_lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip subtitle index numbers (pure digits)
            if re.match(r'^\d+$', line):
                continue

            # Skip timestamp lines (00:01:24,918 --> 00:01:29,047)
            if re.match(r'^\d{1,2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,\.]\d{3}', line):
                continue

            # Remove HTML tags and formatting
            clean_line = re.sub(r'<[^>]+>', '', line)
            clean_line = re.sub(r'\{[^}]+\}', '', clean_line)  # Remove {formatting}
            clean_line = clean_line.strip()

            # Skip music-only lines (just musical notes, with optional tilde)
            if re.match(r'^[♪♫♬♩～〜~\s\-_\.]+$', clean_line):
                continue

            # Skip lines that are only punctuation/symbols
            if re.match(r'^[\s\.\-_\!\?\,\。\、\！\？]+$', clean_line):
                continue

            # Skip lines that are only speaker labels with nothing after
            # e.g., "（爽子）" or "(Sawako)"
            if re.match(r'^[\(（][^)）]+[\)）]$', clean_line):
                continue

            if clean_line:
                lines.append(clean_line)

    return lines


def extract_archive(archive_path: Path, temp_dir: Path) -> list[Path]:
    """Extract SRT files from ZIP or 7z archive."""
    srt_files = []

    if archive_path.suffix.lower() == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.srt'):
                    zf.extract(name, temp_dir)
                    srt_files.append(temp_dir / name)

    elif archive_path.suffix.lower() == '.7z':
        with py7zr.SevenZipFile(archive_path, 'r') as szf:
            all_files = szf.getnames()
            srt_names = [n for n in all_files if n.lower().endswith('.srt')]
            if srt_names:
                szf.extract(path=temp_dir, targets=srt_names)
                for name in srt_names:
                    srt_files.append(temp_dir / name)

    # Sort files by episode number
    def get_episode_num(path: Path) -> int:
        match = re.search(r'[ES]?(\d+)', path.name, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    srt_files.sort(key=get_episode_num)
    return srt_files


def fetch_anime_info(anime_name: str) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Fetch anime cover image, synopsis, and canonical title from Jikan API (MyAnimeList).

    Returns: (cover_data, synopsis, mal_title)
    """
    try:
        # Search for the anime
        query = urllib.parse.quote(anime_name)
        url = f"{JIKAN_SEARCH_URL}?q={query}&limit=1"

        req = urllib.request.Request(url, headers={'User-Agent': 'SubtitleToEPUB/1.0'})

        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data.get('data') and len(data['data']) > 0:
            anime = data['data'][0]

            # Get the romanized title (prefer title over title_english)
            mal_title = anime.get('title', '')

            # Get synopsis
            synopsis = anime.get('synopsis', '')

            # Get the large image URL
            image_url = anime.get('images', {}).get('jpg', {}).get('large_image_url')

            if not image_url:
                image_url = anime.get('images', {}).get('jpg', {}).get('image_url')

            cover_data = None
            if image_url:
                print(f"  Found: {mal_title}")
                req = urllib.request.Request(image_url, headers={'User-Agent': 'SubtitleToEPUB/1.0'})
                with urllib.request.urlopen(req, timeout=15) as img_response:
                    cover_data = img_response.read()

            return cover_data, synopsis, mal_title

    except Exception as e:
        print(f"  Warning: Could not fetch info for '{anime_name}': {e}")

    return None, None, None


def create_default_cover(anime_name: str) -> bytes:
    """Create a simple SVG cover if no image is found."""
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600" viewBox="0 0 400 600">
  <rect width="400" height="600" fill="#2c3e50"/>
  <text x="200" y="280" font-family="Arial, sans-serif" font-size="28" fill="white" text-anchor="middle">
    {anime_name[:30]}
  </text>
  <text x="200" y="320" font-family="Arial, sans-serif" font-size="16" fill="#bdc3c7" text-anchor="middle">
    Japanese Subtitles
  </text>
</svg>'''
    return svg.encode('utf-8')


def create_epub(anime_name: str, subtitle_lines: list[str], cover_data: Optional[bytes],
                output_path: Path, synopsis: Optional[str] = None) -> None:
    """Create EPUB file from subtitle content."""
    book = epub.EpubBook()

    # Metadata
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(anime_name)
    book.set_language('ja')
    book.add_author('Subtitle Extractor')

    # Use MAL synopsis if available, otherwise generic description
    if synopsis:
        book.add_metadata('DC', 'description', synopsis)
    else:
        book.add_metadata('DC', 'description', f'Japanese subtitles for {anime_name}')

    # Add cover
    if cover_data:
        # Detect image type
        if cover_data.startswith(b'<?xml') or cover_data.startswith(b'<svg'):
            book.set_cover("cover.svg", cover_data)
        else:
            book.set_cover("cover.jpg", cover_data)

    # Create content chapter
    content_html = ['<html><head><meta charset="utf-8"/></head><body>']
    content_html.append(f'<h1>{anime_name}</h1>')
    content_html.append('<div class="subtitles">')

    for line in subtitle_lines:
        # Escape HTML entities
        escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        content_html.append(f'<p>{escaped}</p>')

    content_html.append('</div></body></html>')

    chapter = epub.EpubHtml(title=anime_name, file_name='content.xhtml', lang='ja')
    chapter.content = '\n'.join(content_html)

    # Add CSS for better formatting
    style = '''
    body { font-family: serif; line-height: 1.6; padding: 1em; }
    h1 { text-align: center; margin-bottom: 2em; }
    .subtitles p { margin: 0.5em 0; text-indent: 0; }
    '''
    nav_css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
    book.add_item(nav_css)
    chapter.add_item(nav_css)

    book.add_item(chapter)

    # Navigation - only include the content chapter, no nav page
    book.toc = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [chapter]  # Remove 'nav' to avoid "1.Subtitles" prefix

    # Write EPUB
    epub.write_epub(str(output_path), book, {})


def process_archive(archive_path: Path, output_dir: Path) -> bool:
    """Process a single archive file."""
    search_name = extract_anime_name(archive_path.name)

    # Use ASCII-safe printing for filenames with special characters
    try:
        print(f"\nProcessing: {archive_path.name}")
    except UnicodeEncodeError:
        print(f"\nProcessing: {archive_path.name.encode('ascii', 'replace').decode()}")
    print(f"  Searching for: {search_name}")

    # Fetch cover, synopsis, and canonical title from MAL first
    print("  Fetching anime info...")
    cover_data, synopsis, mal_title = fetch_anime_info(search_name)

    # Use MAL title if available, otherwise fall back to extracted name
    anime_name = mal_title if mal_title else search_name

    # Sanitize filename (remove characters not allowed in Windows filenames)
    safe_filename = re.sub(r'[<>:"/\\|?*]', '', anime_name)
    output_file = output_dir / f"{safe_filename}.epub"

    # Skip if already exists
    if output_file.exists():
        print(f"  Skipping (already exists): {output_file.name}")
        return False

    # Create temp directory for extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Extract SRT files
        print("  Extracting subtitles...")
        srt_files = extract_archive(archive_path, temp_path)

        if not srt_files:
            print("  No SRT files found!")
            return False

        print(f"  Found {len(srt_files)} subtitle files")

        # Parse all SRT files
        all_lines = []
        for srt_file in srt_files:
            try:
                # Try different encodings
                for encoding in ['utf-8', 'utf-8-sig', 'shift-jis', 'cp932', 'euc-jp']:
                    try:
                        content = srt_file.read_text(encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    content = srt_file.read_text(encoding='utf-8', errors='ignore')

                lines = parse_srt_content(content)
                all_lines.extend(lines)
            except Exception as e:
                print(f"  Warning: Could not parse {srt_file.name}: {e}")

        print(f"  Extracted {len(all_lines)} subtitle lines")

        if not cover_data:
            print("  Using default cover")
            cover_data = create_default_cover(anime_name)

        # Create EPUB
        print("  Creating EPUB...")
        create_epub(anime_name, all_lines, cover_data, output_file, synopsis)
        print(f"  Created: {output_file.name}")

        return True


def main():
    """Main entry point."""
    print("=" * 60)
    print("Anime Subtitle to EPUB Converter")
    print("=" * 60)

    # Ensure directories exist
    ORIGINAL_DIR.mkdir(exist_ok=True)
    MERGED_DIR.mkdir(exist_ok=True)

    # Find all archives
    archives = []
    for ext in ['*.zip', '*.7z']:
        archives.extend(ORIGINAL_DIR.glob(ext))

    if not archives:
        print(f"\nNo ZIP or 7z files found in {ORIGINAL_DIR}")
        print("Please add subtitle archives to the Original folder.")
        return

    print(f"\nFound {len(archives)} archive(s) in {ORIGINAL_DIR}")

    # Process each archive
    processed = 0
    skipped = 0

    for archive in sorted(archives):
        try:
            if process_archive(archive, MERGED_DIR):
                processed += 1
            else:
                skipped += 1
        except Exception as e:
            try:
                print(f"  Error processing {archive.name}: {e}")
            except UnicodeEncodeError:
                print(f"  Error processing archive: {e}")

    print("\n" + "=" * 60)
    print(f"Done! Processed: {processed}, Skipped: {skipped}")
    print(f"EPUBs saved to: {MERGED_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()

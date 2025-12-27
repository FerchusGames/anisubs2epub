# subs2epub

Convert anime subtitle archives into EPUB files for vocabulary tracking with [Migaku Reader](https://reader.migaku.com/).

## What is this?

This tool takes ZIP/7z archives containing full seasons of anime subtitles and converts them into EPUB files. Each EPUB includes:

- All episodes merged into a single file
- Cover image fetched from MyAnimeList
- Proper anime title from MAL database
- Clean text optimized for vocabulary analysis

## Why?

Migaku Reader can analyze EPUB files and show you what percentage of words you already know. By converting anime subtitles to EPUB format, you can:

- **Track your progress** - See exactly how much of an anime you can understand
- **Choose what to watch** - Pick shows that match your current level
- **Measure improvement** - Watch your comprehension percentage grow over time

<!--
## Screenshot

![Migaku Reader showing vocabulary percentages](screenshot.png)

TODO: Add your screenshot here showing Migaku Reader with anime subtitle EPUBs
-->

## Supported Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| SubRip | `.srt` | Most common subtitle format |
| Advanced SubStation Alpha | `.ass` | Popular for anime fansubs |
| SubStation Alpha | `.ssa` | Older version of ASS |
| WebVTT | `.vtt` | Web-based subtitle format |

Archives can be `.zip` or `.7z` files.

## Usage

1. Place your subtitle archives in the `Original/` folder
2. Double-click `Convert Subtitles.bat` (or run `python subtitle_to_epub.py`)
3. Find your EPUBs in the `Merged/` folder
4. Import the EPUBs into Migaku Reader

```
subs2epub/
├── Original/          <- Put your ZIP/7z files here
│   ├── Anime Name S01.zip
│   └── Another Anime.7z
├── Merged/            <- EPUBs appear here
│   ├── Anime Name.epub
│   └── Another Anime.epub
├── subtitle_to_epub.py
├── Convert Subtitles.bat
└── README.md
```

## Requirements

- Python 3.9+
- Internet connection (for fetching covers from MyAnimeList)

Dependencies are installed automatically on first run:
- `ebooklib` - EPUB generation
- `py7zr` - 7z archive support

## Features

- Automatic anime detection via MyAnimeList API
- Portrait cover images from MAL
- Proper romanized titles (e.g., "Shingeki no Kyojin" instead of "Attack on Titan")
- Filters out music symbols, timestamps, and formatting
- Handles multiple subtitle formats
- Incremental updates (skips already-converted files)

## How It Works

1. Scans `Original/` for subtitle archives
2. Extracts the anime name from the filename
3. Searches MyAnimeList for the official title and cover
4. Parses all subtitle files, extracting clean dialogue text
5. Generates an EPUB with the cover and all episode text
6. Saves to `Merged/` folder

## License

MIT

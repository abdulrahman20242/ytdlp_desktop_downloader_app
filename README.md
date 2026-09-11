# YT Downloader

A Windows desktop application for downloading YouTube videos, audio, and playlists using `yt-dlp`.

## Overview

YT Downloader provides a graphical interface for downloading YouTube content. It runs `yt-dlp` as a subprocess for downloads and uses the Python `yt_dlp` API only for extracting video metadata. The UI is built with `customtkinter` and supports Arabic and English.

## Features

- **Video downloads** — up to 4K (2160p) with H.264 codec preference for compatibility
- **Audio downloads** — MP3 (192 kbps) or M4A (no audio re-encode, with metadata/thumbnail processing)
- **Playlist support** — fetch, browse, and download all or selected items from a playlist
- **Quality selection** — Best, 2160p, 1440p, 1080p, 720p, 480p, 360p (filtered to available resolutions)
- **Download modes** — video, mp4_only, or audio
- **Cookie support** — import from Chrome, Firefox, Edge, or Brave; or load a `cookies.txt` file
- **SponsorBlock** — optional removal of sponsor segments
- **Throttling recovery** — automatic recovery when YouTube throttles download speed
- **JavaScript challenge handling** — via `yt-dlp-ejs` plugin and Node.js
- **Progress tracking** — real-time progress bar with speed and ETA
- **Download cancellation** — cancel any in-progress download
- **Logs panel** — collapsible log viewer with debug information
- **Startup dependency check** — validates FFmpeg, FFprobe, Node.js, and yt-dlp at launch
- **Settings dialog** — configure theme, language, download defaults, cookies, and advanced options
- **Arabic / English UI** — right-to-left interface with full Arabic support
- **Dark / Light / System theme** — switchable from settings

## Screenshots

No screenshots are currently available in the repository.

## Requirements

### Required

| Dependency | Details |
|---|---|
| **OS** | Windows 10/11 (x64) |
| **Python** | 3.11 or later |
| **yt-dlp** | Python package (`yt-dlp[default]==2026.08.19`) |
| **FFmpeg** | `bin/ffmpeg.exe` — video/audio merging |
| **FFprobe** | `bin/ffprobe.exe` — media probing |

### Optional

| Dependency | Purpose |
|---|---|
| **Node.js** | `bin/node.exe` — JavaScript runtime for `yt-dlp-ejs` plugin (some videos require this) |
| **cookies.txt** | For age-restricted or private content |

### Python Packages

```
yt-dlp[default]==2026.08.19
yt-dlp-ejs>=0.8.0
customtkinter>=5.2.0
Pillow>=10.0.0
requests>=2.31.0
```

> The `yt-dlp` version is pinned to match the bundled `bin/yt-dlp.exe` release so the metadata extractor and the downloader stay aligned.

> `yt-dlp-ejs` is a yt-dlp plugin, not a standalone Python import. It is activated at download time.

### Binaries (`bin/`)

| File | Source | Required |
|---|---|---|
| `yt-dlp.exe` | yt-dlp releases | Yes |
| `ffmpeg.exe` | yt-dlp/FFmpeg-Builds | Yes |
| `ffprobe.exe` | yt-dlp/FFmpeg-Builds | Yes |
| `node.exe` | Node.js standalone | No |

The `bin/` directory is not committed to Git. You must place the required binaries there before running the application.

## Installation

```powershell
git clone https://github.com/abdulrahman20242/ytdlp_desktop_downloader_app.git
cd ytdlp_desktop_downloader_app

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

Then place the required binaries (`yt-dlp.exe`, `ffmpeg.exe`, `ffprobe.exe`) in the `bin/` directory. Optionally place `node.exe` in `bin/` for JavaScript challenge support.

## Usage

1. Run `python app.py`
2. The startup check validates your dependencies. Click **Continue** when ready.
3. Paste a YouTube URL into the input field.
4. Click **Fetch** to load video information (title, thumbnail, available qualities, duration, channel).
5. Select a download mode (**video**, **mp4_only**, or **audio**) and a quality level.
6. Choose a save folder (defaults to `~/Downloads/YTDownloader`).
7. Click **Download** to start.
8. Monitor progress via the progress bar, speed, and ETA indicators.
9. Click **Open Folder** to open the download location.

### Playlist Usage

1. Paste a playlist URL and click **Fetch**.
2. The playlist panel appears showing all videos with thumbnails, titles, and durations.
3. Use **Select All** / **Deselect All** to choose which items to download.
4. Click **Download All** or **Download Selected**.
5. Each playlist is saved into a subfolder named after the playlist.
6. Individual item status (waiting, downloading, completed, failed) is shown in the panel.

### Settings

Open the settings dialog from the main window.

| Tab | Options |
|---|---|
| **General** | Theme (dark/light/system), Language (ar/en), Save folder |
| **Download** | Default quality, Default mode, Concurrent fragments, Retries |
| **Advanced** | Cookie source (none/browser/file), Browser selection, Debug logs, SponsorBlock removal |

## Configuration

Settings are stored in `%APPDATA%\YTDownloader\config.json` (e.g. `C:\Users\<you>\AppData\Roaming\YTDownloader\config.json`). The file is only written once you change a setting — a fresh install runs entirely on defaults. If the file is ever corrupted or truncated, the app falls back to defaults automatically and preserves the unusable file as `config.json.bak` next to it.

### Default Configuration

```json
{
  "version": "1.0",
  "ui": {
    "theme": "dark",
    "language": "ar",
    "window_width": 800,
    "window_height": 600
  },
  "download": {
    "default_dir": "<home>/Downloads/YTDownloader",
    "default_quality": "1080p",
    "default_mode": "video",
    "concurrent_fragments": 4,
    "retries": 10,
    "merge_output_format": "mp4"
  },
  "cookies": {
    "source": "none",
    "browser": "chrome",
    "file_path": "%APPDATA%\\YTDownloader\\cookies.txt"
  },
  "advanced": {
    "show_debug_logs": false,
    "sponsorblock_remove": false,
    "sponsorblock_categories": ["sponsor"]
  }
}
```

Older config files may contain additional keys (e.g. `audio.*`, `download.embed_*`, `advanced.ffmpeg_location`, `advanced.node_path`, `advanced.use_nightly_yt_dlp`). These are not part of the current code defaults and are ignored.

## Cookies and Authentication

Cookie support is disabled by default (`cookies.source = "none"`).

When enabled:

- **Browser source** — extracts cookies directly from Chrome, Firefox, Edge, or Brave. The browser must be closed during extraction because Chrome locks its cookie database while running.
- **File source** — loads a Netscape-format `cookies.txt` file (e.g. exported via a browser extension).

Cookies may be needed for age-restricted content or region-locked videos.

## Architecture

The application uses a single `CTk` root window. All screens (startup check, main window) are `CTkFrame` subclasses embedded in the same root.

```
app.py
  └── ctk.CTk()  (single persistent window)
        ├── StartupCheckFrame  (dependency check screen)
        └── MainWindow  (main download interface)
              ├── QualitySelector
              ├── ProgressWidget
              ├── PlaylistPanel
              ├── LogsPanel
              └── SettingsDialog  (CTkToplevel)
```

### Layer Structure

```
UI Layer
  │  customtkinter widgets, events via queue.Queue
  ▼
Controller Layer
  │  DownloadController, InfoExtractor, ConfigManager
  │
  ├── yt-dlp (Python API — info extraction only, download=False)
  ├── yt-dlp.exe (subprocess — actual downloads, stdout parsed)
  ├── FFmpeg / FFprobe (media processing)
  └── Node.js / yt-dlp-ejs (JavaScript challenge solving)
```

Downloads run `bin/yt-dlp.exe` as a subprocess and parse its stdout line-by-line for progress, speed, and ETA. The Python `yt_dlp.YoutubeDL` API is used only for extracting metadata.

## Project Structure

```
.
├── app.py                     # Entry point
├── ui/                        # GUI components
│   ├── main_window.py         # Main window (CTkFrame)
│   ├── settings_dialog.py     # Settings dialog (3 tabs)
│   ├── startup_check.py       # Dependency check screen
│   ├── progress_widget.py     # Progress bar + speed/ETA
│   ├── logs_panel.py          # Collapsible log viewer
│   ├── playlist_panel.py      # Playlist items panel
│   └── quality_selector.py    # Quality + mode selector
├── core/                      # Business logic
│   ├── config_manager.py      # JSON config with deep merge
│   ├── dep_checker.py         # Binary dependency validation
│   ├── download_controller.py # Threaded subprocess downloads
│   ├── info_extractor.py      # Video/playlist metadata extraction
│   └── format_builder.py      # yt-dlp format strings + options
├── utils/                     # Shared utilities
│   ├── ui_logger.py           # Thread-safe logger for UI
│   ├── paths.py               # App/UserData/Bin directory resolution
│   ├── validators.py          # YouTube URL validation
│   └── file_utils.py          # File/folder helpers
├── assets/                    # Static assets (fonts)
├── bin/                       # Binaries (not in Git)
├── tests/                     # Test suite
├── docx/                      # Design documents (PRD, reference)
├── FAQ.md                     # Frequently asked questions
├── requirements.txt           # Python dependencies
└── README.md
```

## Development

### Setup

```powershell
git clone https://github.com/abdulrahman20242/ytdlp_desktop_downloader_app.git
cd ytdlp_desktop_downloader_app

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

### Running

```powershell
python app.py
```

### Building a Portable Release

```powershell
.\build_windows.bat
```

The build compiles the launcher (`dotnet publish`), freezes the app with
PyInstaller (`ytdownloader.spec`), assembles `Release\YT Downloader.exe` +
`Release\YT Downloader\...` (launcher, `_internal\`, `assets\`, `bin\`), then
runs a packaged self-test via `YTDLP_DESKTOP_SELFTEST=1` before reporting a
summary. User data (config, cookies) always lives under `%APPDATA%\YTDownloader\`,
never inside the install folder, so the release is portable and upgradeable
in place.

### Testing

```powershell
pytest -q
```

The test suite covers `core/`, `utils/`, and `ui/` modules with stubs for `customtkinter`, `tkinter`, and `yt_dlp`.

## Troubleshooting

### "No supported JavaScript runtime could be found"

The `yt-dlp-ejs` plugin requires Node.js. Place `node.exe` in the `bin/` directory or ensure Node.js is on your system PATH.

### "Could not copy Chrome cookie database"

Chrome locks its cookie database while running. Close Chrome before enabling browser cookie extraction, or switch to the file-based cookie source in Settings.

### Download stuck at 0% with very slow speed

This is YouTube throttling. The application automatically detects and recovers from throttled speeds. The download speed should recover after re-extraction.

### Startup check shows missing dependencies

The application checks for FFmpeg, FFprobe, Node.js (optional), and yt-dlp at launch. Place the required binaries in the `bin/` directory and install the Python package (`pip install -r requirements.txt`).

### "invalid command name" console errors

This was a bug in earlier versions using multiple `CTk` instances. The current single-root architecture resolves this. Ensure you are running the latest code.

## License

No license file is currently present in this repository.

## Support

Report issues at <https://github.com/abdulrahman20242/ytdlp_desktop_downloader_app/issues>.

## Additional Documentation

- [FAQ.md](FAQ.md) — frequently asked questions about architecture, behavior, and setup
- `docx/` — design documents (PRD, project reference, implementation diff)

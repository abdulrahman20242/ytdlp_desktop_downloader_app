# YT Downloader — Project Reference

**Version:** 2.0 | **Platform:** Windows 10/11 x64 | **Python:** 3.11+
**Repository:** ReizanTech | **Last Updated:** May 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [File Reference](#3-file-reference)
4. [Configuration](#4-configuration)
5. [yt-dlp Options Reference](#5-yt-dlp-options-reference)
6. [Data Flow](#6-data-flow)
7. [Threading Model](#7-threading-model)
8. [Error Handling](#8-error-handling)
9. [Build & Deployment](#9-build--deployment)
10. [Development Guide](#10-development-guide)
11. [Testing Scenarios](#11-testing-scenarios)
12. [Dependencies](#12-dependencies)
13. [Appendix: Complete Change Log](#13-appendix-complete-change-log)

---

## 1. Project Overview

YT Downloader is a Windows desktop application for downloading YouTube videos and audio. It uses `yt-dlp` as the download engine via its Python API (not subprocess), `customtkinter` for the GUI, and `yt-dlp-ejs` + Node.js for solving YouTube's JavaScript challenges.

### Purpose

Provide a simple, reliable YouTube downloader with:
- Highest quality available (up to 4K 2160p)
- Professional audio conversion (MP3 192kbps / M4A AAC)
- Modern YouTube support (n-sig challenges, age-restricted content)
- Arabic/English bilingual interface
- Throttling recovery
- Cookie support (browser import or file)

### Target Users

- **Casual users:** Paste URL → Download → Done
- **Advanced users:** Manual quality/format selection, playlist download, cookie configuration, detailed logs

---

## 2. Architecture

### 2.1 Single-Root Window Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ctk.CTk() [root]                         │
│  Window: 800x600, min 700x500, theme-based                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  StartupCheckFrame (CTkFrame)                       │    │
│  │  - DependencyChecker results                        │    │
│  │  - "Continue" button                                │    │
│  │  - Destroyed on continue                            │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  MainWindow (CTkFrame)                              │    │
│  │  ┌───────────────────────────────────────────────┐  │    │
│  │  │ URL Input + Fetch Button                      │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ Video Info (thumbnail, title, channel, time)  │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ QualitySelector (mode + quality)              │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ Save Directory + Action Buttons               │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ ProgressWidget (bar, speed, ETA)              │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ LogsPanel (collapsible, auto-scroll)          │  │    │
│  │  └───────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UI LAYER                                  │
│  customtkinter-based                                         │
│                                                             │
│  MainWindow (CTkFrame)           SettingsDialog (Toplevel)  │
│  ├── Builds all widgets          ├── 4 tabs                │
│  ├── Manages user input          ├── Reads/writes config   │
│  ├── Calls InfoExtractor         └── Modal (grab_set)      │
│  ├── Controls DownloadController                             │
│  └── Updates progress/logs                                  │
│                                                             │
│  ProgressWidget       LogsPanel         QualitySelector     │
│  └── Progress bar     └── Textbox        └── Mode/Quality   │
│      Speed/ETA          Collapsible          dropdowns      │
│      Filename           Auto-scroll                         │
└────────────────────────────────┬────────────────────────────┘
                                 │ events via queue.Queue
┌────────────────────────────────▼────────────────────────────┐
│                  CONTROLLER LAYER                            │
│                                                             │
│  DownloadController          InfoExtractor                  │
│  ├── Queue-based threading   ├── extract_info(url)          │
│  ├── start_download()        ├── get_available_qualities()  │
│  ├── cancel()                └── extract_thumbnail()        │
│  └── Event callbacks                                        │
│                                                             │
│  ConfigManager               DependencyChecker              │
│  ├── get(key_path)           ├── check_all()                │
│  ├── set(key_path, value)    ├── FFmpeg, FFprobe, Node.js   │
│  └── data/config.json        └── yt-dlp                     │
│                                                             │
│  FormatBuilder               Validators / FileUtils         │
│  ├── FORMAT_MAP              ├── is_valid_youtube_url()     │
│  ├── build_format_opts()     ├── is_playlist_url()          │
│  └── get_common_opts()       └── open_folder()              │
└────────────────────────────────┬────────────────────────────┘
                                 │ yt-dlp Python API
┌────────────────────────────────▼────────────────────────────┐
│                   DOWNLOAD ENGINE                           │
│                                                             │
│  yt_dlp.YoutubeDL                                           │
│  ├── format_sort (codec pref)                               │
│  ├── throttledratelimit                                     │
│  ├── js_runtimes (node)                                     │
│  ├── extractor_args (youtube-ejs)                           │
│  ├── progress_hooks → queue                                 │
│  ├── logger → queue                                         │
│  └── postprocessors (FFmpegExtractAudio, Metadata, Thumb)   │
│                                                             │
│  External processes (spawned by yt-dlp):                    │
│  ├── bin/ffmpeg.exe — merging, audio extraction             │
│  └── bin/node.exe — JS challenge solving                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Key Design Decisions (ADRs)

| ADR | Decision | Rationale |
|---|---|---|
| ADR-001 | Python API (not subprocess) | Full control over hooks/logger, exception handling |
| ADR-002 | Threading + queue.Queue (not asyncio) | tkinter thread-safety, simpler debugging |
| ADR-003 | PyInstaller `--onedir` (not `--onefile`) | Faster startup, antivirus-friendly |
| ADR-004 | yt-dlp nightly channel | YouTube changes fast, stable lags behind |
| ADR-005 | yt-dlp-ejs + Node.js | JavaScript challenge solving |
| ADR-006 | format_sort: h264 > vp9 > av01 | Better compatibility, practical quality |
| ADR-007 | Single-root CTkFrame architecture | Avoids `after` callback conflicts |

---

## 3. File Reference

### 3.1 `app.py` — Application Entry Point

```python
# Signature
def main() -> None

# Flow
1. os.environ["PATH"] += PROJECT_ROOT / "bin"     # Line 11
2. config = ConfigManager()                          # Line 17
3. ctk.set_appearance_mode(config.get("ui.theme"))  # Line 19
4. root = ctk.CTk()                                  # Line 21
5. root.iconbitmap("assets/logo.ico")                # Line 30
6. StartupCheckFrame(root, on_startup_done)          # Line 38
7. root.mainloop()                                   # Line 39
```

**Critical detail:** `PATH` must be set before `import customtkinter` or any yt-dlp import because `yt-dlp-ejs` probes for `node` at module load time.

### 3.2 `ui/main_window.py` — MainWindow (CTkFrame)

```python
class MainWindow(ctk.CTkFrame):
    def __init__(self, master, config)
    def _setup_window(self)
    def _build_ui(self)           # Builds all widgets in grid layout
    def _setup_callbacks(self)    # Wires DownloadController events
    def _load_config_state(self)  # Restores saved paths
    def _on_url_change(self, *_)  # Validates URL → enable/disable fetch
    def _fetch_info(self)         # Threaded info extraction
    def _display_info(self, info) # Updates labels, thumbnail, qualities
    def _load_thumbnail(self, url) # Downloads thumbnail in thread
    def _browse_dir(self)         # Folder picker dialog
    def _start_download(self)     # Builds opts, starts controller
    def _cancel_download(self)    # Cancels and resets UI
    def _open_folder(self)        # Opens save dir in Explorer
    def _open_settings(self)      # Opens SettingsDialog
```

**Grid layout (rows 0-3 on self, rows 0-8 on main_frame):**
```
row 0: Header "YT Downloader"
row 1: Subtitle
row 2: main_frame (sticky nsew)
│   row 0: URL input + Fetch button
│   row 1: Info display (thumbnail + metadata)
│   row 2: Separator
│   row 3: QualitySelector
│   row 4: Save directory
│   row 5: Action buttons (Download, Cancel, Open Folder, Settings)
│   row 6: ProgressWidget
│   row 7: Separator
│   row 8: LogsPanel (weight=1, expands)
row 3: Status bar
```

### 3.3 `ui/startup_check.py` — StartupCheckFrame (CTkFrame)

```python
class StartupCheckFrame(ctk.CTkFrame):
    def __init__(self, master, on_done: Callable)
    def _run_checks(self)           # Synchronous dependency check
    def _display_results(self, results: list[DepResult])  # Shows icons + versions
    def _on_continue(self)          # Disables button, calls on_done, destroys self
```

**Note:** Checks run synchronously (no threading) because they're fast (file existence + `--version` subprocess calls). The UI updates via `self.update()` between phases.

### 3.4 `ui/settings_dialog.py` — SettingsDialog (CTkToplevel)

```python
class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, config)
    def _build_ui(self)           # 4-tab notebook
    def _build_general_tab(self)  # Theme, language, save dir
    def _build_download_tab(self) # Default quality, mode, fragments, retries
    def _build_audio_tab(self)    # Audio format, MP3 quality
    def _build_advanced_tab(self) # Cookies source/browser, debug logs
    def _load_config(self)        # Populates fields from config
    def _save(self)               # Writes all fields to config, closes
    def _browse_dir(self)         # File dialog for save dir
```

**Tab contents:**

| Tab | Widgets | Config Keys |
|---|---|---|
| General | Theme OptionMenu, Language OptionMenu, Save Dir Entry+Browse | `ui.theme`, `ui.language`, `download.default_dir` |
| Download | Quality OptionMenu, Mode OptionMenu, Fragments Entry, Retries Entry | `download.default_quality`, `download.default_mode`, `download.concurrent_fragments`, `download.retries` |
| Audio | Format OptionMenu, MP3 Quality OptionMenu | `audio.default_format`, `audio.mp3_quality` |
| Advanced | Cookies Source OptionMenu, Browser OptionMenu, Debug Checkbox | `cookies.source`, `cookies.browser`, `advanced.show_debug_logs` |

### 3.5 `ui/progress_widget.py` — ProgressWidget (CTkFrame)

```python
class ProgressWidget(ctk.CTkFrame):
    def __init__(self, master)
    def reset(self)                    # Clears all to initial state
    def update_progress(self, d: dict) # Handles 'downloading', 'finished', 'error'
    def set_done(self)                 # Shows completion state
    def set_error(self, message)       # Shows error state
    def _safe_percent(self, d) -> float  # Bytes-based with string fallback
```

**Widgets:**
- `CTkProgressBar` (row 0) — value 0.0 → 1.0
- Label (row 1) — "45.3% · 2.3 MB/s · ETA 00:32"
- Filename label (row 2) — current file being downloaded

### 3.6 `ui/logs_panel.py` — LogsPanel (CTkFrame)

```python
class LogsPanel(ctk.CTkFrame):
    def __init__(self, master)
    def _toggle(self)    # Show/hide textbox
    def _clear(self)     # Clears all text
    def append_log(self, message)  # Inserts at end, auto-scrolls
```

- Toggle button: "▼ Logs" / "▲ Logs"
- Clear button: "Clear"
- Font: Consolas 10 for readable logs

### 3.7 `ui/quality_selector.py` — QualitySelector (CTkFrame)

```python
class QualitySelector(ctk.CTkFrame):
    def __init__(self, master)
    def _on_mode_change(self, mode)        # Audio → show MP3/M4A, Video → show qualities
    def set_qualities(self, qualities)      # Update available video qualities
    @property
    def quality(self) -> str               # Returns lowercase quality string
    @property
    def mode(self) -> str                  # Returns mode string
```

**Mode options:** `["video", "mp4_only", "audio"]`

**Quality options (video):** `["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]`

**Quality options (audio):** `["MP3", "M4A"]`

### 3.8 `core/config_manager.py` — ConfigManager

```python
class ConfigManager:
    def __init__(self)
    def _load(self) -> dict          # Loads + merges with defaults
    def _merge(self, base, override) # Deep merge, preserves missing keys
    def get(self, key_path, default) # Dot-notation: "download.default_quality"
    def set(self, key_path, value)   # Dot-notation write + auto-save
    def _save(self)                  # Writes JSON to data/config.json
    def reset_to_defaults(self)      # Restores factory defaults
```

**Config file:** `data/config.json` (auto-created with defaults on first run)

**Default values:**

```json
{
  "version": "1.0",
  "ui": {"theme": "dark", "language": "ar", "window_width": 800, "window_height": 600},
  "download": {
    "default_dir": "C:/Users/%USER%/Downloads/YTDownloader",
    "default_quality": "1080p", "default_mode": "video",
    "concurrent_fragments": 4, "retries": 10,
    "merge_output_format": "mp4",
    "embed_thumbnail": false, "embed_metadata": true,
    "write_subs": false, "sub_langs": "ar,en"
  },
  "audio": {"default_format": "mp3", "mp3_quality": "192", "embed_thumbnail": true},
  "cookies": {"source": "none", "browser": "chrome", "file_path": "data/cookies.txt"},
  "advanced": {
    "ffmpeg_location": "bin", "js_runtime": "node", "node_path": "bin/node.exe",
    "use_nightly_yt_dlp": true, "show_debug_logs": false,
    "sponsorblock_remove": false, "sponsorblock_categories": ["sponsor"]
  }
}
```

### 3.9 `core/dep_checker.py` — DependencyChecker

```python
@dataclass
class DepResult:
    name: str
    found: bool
    path: str | None
    version: str | None
    required: bool

class DependencyChecker:
    BIN_DIR: Path = Path(__file__).resolve().parent.parent / "bin"

    def check_all(self) -> list[DepResult]
    def _check_ffmpeg(self) -> DepResult   # bin/ffmpeg.exe → --version
    def _check_ffprobe(self) -> DepResult  # bin/ffprobe.exe → --version
    def _check_node(self) -> DepResult     # bin/node.exe → --version (optional)
    def _check_ytdlp(self) -> DepResult    # import yt_dlp → __version__
```

**Note:** `BIN_DIR` uses absolute path (`Path(__file__).resolve()`) to work regardless of CWD.

### 3.10 `core/download_controller.py` — DownloadController

```python
class DownloadController:
    def __init__(self, config)
    def set_app(self, app)              # Sets tk root for after() calls
    def on(self, event, callback)       # Register event handler
    def start_download(self, url, opts, save_dir)  # Spawns thread
    def _download_worker(self, url, opts, save_dir) # yt-dlp in thread
    def _progress_hook(self, d)         # Puts progress to queue
    def _get_logger(self)               # Creates UILogger → queue
    def _poll_queue(self)               # Reads queue every 100ms via after()
    def cancel(self)                    # Sets stop event + cancels after()
    def is_downloading(self) -> bool    # Thread alive check
```

**Event system:**

| Event | Data | Trigger |
|---|---|---|
| `progress` | `dict` (yt-dlp progress hook) | Every fragment chunk |
| `done` | `None` | Download completed successfully |
| `error` | `str` (error ID or message) | Any exception in worker |
| `log` | `str` (log message) | yt-dlp logger output |

**Error mapping in `_download_worker`:**
```
DownloadError
  ├── "Sign in" or "age" → "age_restricted"
  ├── "unavailable" → "unavailable"
  ├── "429" → "rate_limited"
  ├── "cookie" or "Could not copy" → cookie error (Arabic)
  └── else → "download_error:{msg}"
ExtractorError → "extractor:{e}"
UnsupportedError → "unsupported_url"
Exception → "unknown:{e}"
```

### 3.11 `core/format_builder.py` — FormatBuilder

```python
def build_format_opts(quality: str, mode: str) -> dict
def _audio_postprocessors(fmt: str) -> list[dict]
def get_common_opts(bin_dir: str, config) -> dict
```

**`get_common_opts` output:**
```python
{
    "ffmpeg_location": str(resolved_bin_dir),
    "concurrent_fragments": config.get("download.concurrent_fragments", 4),
    "retries": config.get("download.retries", 10),
    "fragment_retries": config.get("download.retries", 10),
    "throttledratelimit": 102400,
    "format_sort": ["vcodec:h264,vp9,av01", "res", "br"],
    "ignoreerrors": False,
    "quiet": True,
    "no_warnings": True,
    "js_runtimes": {"node": {}},
    "extractor_args": {"youtube-ejs": {}},
}
```

**`FORMAT_MAP` — Format strings:**
```python
{
    "best":   "bv[ext=mp4]+ba[ext=m4a]/bv+ba/b",
    "2160p":  "bv[height<=2160][ext=mp4]+ba[ext=m4a]/bv[height<=2160]+ba/b[height<=2160]",
    "1440p":  "bv[height<=1440][ext=mp4]+ba[ext=m4a]/bv[height<=1440]+ba/b[height<=1440]",
    "1080p":  "bv[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]",
    "720p":   "bv[height<=720][ext=mp4]+ba[ext=m4a]/bv[height<=720]+ba/b[height<=720]",
    "480p":   "bv[height<=480][ext=mp4]+ba[ext=m4a]/bv[height<=480]+ba/b[height<=480]",
    "360p":   "bv[height<=360][ext=mp4]+ba[ext=m4a]/bv[height<=360]+ba/b[height<=360]",
    "mp3":    "m4a/bestaudio/best",
    "m4a":    "m4a/bestaudio/best",
}
```

**`FORMAT_MAP_MP4` — MP4-only mode:**
```python
{
    "best":   "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
    "2160p":  "bv[height<=2160][ext=mp4]+ba[ext=m4a]/b[height<=2160]",
    "1440p":  "bv[height<=1440][ext=mp4]+ba[ext=m4a]/b[height<=1440]",
    "1080p":  "bv[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
    "720p":   "bv[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
    "480p":   "bv[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]",
    "360p":   "bv[height<=360][ext=mp4]+ba[ext=m4a]/b[height<=360]",
}
```

**Audio postprocessors:**
- MP3: `FFmpegExtractAudio` (mp3, 192kbps) + `FFmpegMetadata` + `EmbedThumbnail`
- M4A: `FFmpegMetadata` + `EmbedThumbnail` (no re-encode)

### 3.12 `core/info_extractor.py` — InfoExtractor

```python
def extract_info(url: str) -> dict | None
def get_available_qualities(url: str) -> list[str]
def extract_thumbnail(info: dict) -> str | None
def extract_title(info: dict) -> str
def extract_duration(info: dict) -> int
def extract_uploader(info: dict) -> str
```

### 3.13 `utils/ui_logger.py` — UILogger

```python
class UILogger:
    def __init__(self, q: queue.Queue)
    def debug(self, msg)    # Filters out "[debug] " prefixed messages
    def info(self, msg)     # → ("log", "[INFO] {msg}")
    def warning(self, msg)  # → ("log", "[WARN] {msg}")
    def error(self, msg)    # → ("log", "[ERROR] {msg}")
```

Implements yt-dlp's logger interface. All messages prefixed with level and put in queue.

### 3.14 `utils/validators.py` — Validators

```python
YOUTUBE_RE = re.compile(...)    # Matches youtube.com, youtu.be, shorts, playlists
PLAYLIST_RE = re.compile(...)   # Matches list= parameter

def is_valid_youtube_url(url: str) -> bool
def is_playlist_url(url: str) -> bool
def extract_video_id(url: str) -> str | None
```

### 3.15 `utils/file_utils.py` — File Utils

```python
def ensure_dir(path: Path) -> Path
def open_folder(path: Path)           # os.startfile()
def get_downloads_dir() -> Path       # ~/Downloads/YTDownloader
def safe_filename(name: str) -> str   # Removes <>:"/\|?*
```

---

## 4. Configuration

### 4.1 All Config Keys

| Key Path | Type | Default | Description |
|---|---|---|---|
| `version` | string | `"1.0"` | Config schema version |
| `ui.theme` | string | `"dark"` | `"dark"`, `"light"`, or `"system"` |
| `ui.language` | string | `"ar"` | `"ar"` or `"en"` |
| `ui.window_width` | int | `800` | Initial window width |
| `ui.window_height` | int | `600` | Initial window height |
| `download.default_dir` | string | `~/Downloads/YTDownloader` | Default save directory |
| `download.default_quality` | string | `"1080p"` | `"Best"`, `"2160p"`, ..., `"360p"` |
| `download.default_mode` | string | `"video"` | `"video"`, `"mp4_only"`, `"audio"` |
| `download.concurrent_fragments` | int | `4` | Parallel fragment downloads |
| `download.retries` | int | `10` | Download retry count |
| `download.merge_output_format` | string | `"mp4"` | Container format for merged output |
| `download.embed_thumbnail` | bool | `false` | Embed thumbnail in video |
| `download.embed_metadata` | bool | `true` | Embed metadata in video |
| `download.write_subs` | bool | `false` | Download subtitles |
| `download.sub_langs` | string | `"ar,en"` | Subtitle languages |
| `audio.default_format` | string | `"mp3"` | `"mp3"` or `"m4a"` |
| `audio.mp3_quality` | string | `"192"` | MP3 bitrate: `"128"`, `"192"`, `"320"` |
| `audio.embed_thumbnail` | bool | `true` | Embed thumbnail in audio |
| `cookies.source` | string | `"none"` | `"none"`, `"browser"`, `"file"` |
| `cookies.browser` | string | `"chrome"` | `"chrome"`, `"firefox"`, `"edge"`, `"brave"` |
| `cookies.file_path` | string | `"data/cookies.txt"` | Path to cookies.txt |
| `advanced.show_debug_logs` | bool | `false` | Show debug-level logs |
| `advanced.sponsorblock_remove` | bool | `false` | Remove sponsor segments |
| `advanced.sponsorblock_categories` | list | `["sponsor"]` | SponsorBlock categories |

### 4.2 Config File Location

`data/config.json` (relative to project root / EXE directory)

### 4.3 ConfigManager Deep Merge

When loading a saved config, `ConfigManager._merge()` recursively merges saved values with defaults. Any keys present in defaults but missing in saved config are preserved from defaults. This ensures forward compatibility when new config keys are added.

---

## 5. yt-dlp Options Reference

### 5.1 All Options Used

| Option | Value | Purpose |
|---|---|---|
| `format` | See FORMAT_MAP | Quality/format selection |
| `merge_output_format` | `"mp4"` | Container for merged video+audio |
| `outtmpl` | `save_dir / "%(title)s [%(id)s].%(ext)s"` | Output file naming |
| `ffmpeg_location` | `bin/` (absolute) | FFmpeg binary location |
| `concurrent_fragments` | `4` | Parallel DASH/HLS fragment download |
| `retries` | `10` | Download retries |
| `fragment_retries` | `10` | Fragment retries |
| `throttledratelimit` | `102400` (100 KB/s) | Auto re-extract on throttling |
| `format_sort` | `["vcodec:h264,vp9,av01", "res", "br"]` | Codec preference |
| `js_runtimes` | `{"node": {}}` | Node.js for JS challenges |
| `extractor_args` | `{"youtube-ejs": {}}` | YouTube EJS extractor |
| `cookiesfrombrowser` | `("chrome",)` etc. | Browser cookie import |
| `cookiefile` | `data/cookies.txt` | Cookies file path |
| `sponsorblock_remove` | `["sponsor"]` etc. | SponsorBlock filtering |
| `writethumbnail` | `True` | Save thumbnail for audio embedding |
| `postprocessors` | See 3.11 | Audio extraction, metadata, thumbnail |
| `progress_hooks` | `[callback]` | Real-time progress updates |
| `logger` | `UILogger` instance | Thread-safe log capture |
| `ignoreerrors` | `False` | Stop on first error |
| `quiet` | `True` | Reduce console output |
| `no_warnings` | `True` | Suppress warnings in console |

### 5.2 Format String Reference

yt-dlp format string syntax used:

| Symbol | Meaning |
|---|---|
| `bv` | Best video-only stream |
| `ba` | Best audio-only stream |
| `*` | Allow multiple (use best of available) |
| `+` | Download separately then merge |
| `/` | Fallback chain (try left first) |
| `[ext=mp4]` | Filter by container extension |
| `[height<=1080]` | Filter by max height |
| `b` | Best combined (video+audio) stream |

### 5.3 format_sort Reference

```python
["vcodec:h264,vp9,av01", "res", "br"]
```

This is a list of sort keys. Each key is a field name with optional value ordering:

- `vcodec:h264,vp9,av01` — Sort by video codec: prefer H.264 first, then VP9, then AV01
- `res` — Sort by resolution (higher is better)
- `br` — Sort by bitrate (higher is better)

### 5.4 throttledratelimit Reference

```python
"throttledratelimit": 102400  # 100 KB/s in bytes/sec
```

When yt-dlp detects download speed consistently below this threshold, it assumes YouTube is throttling the connection and automatically re-extracts the video info to get fresh URLs. This typically recovers speed from ~50 KB/s back to 1-5 MB/s within seconds.

---

## 6. Data Flow

### 6.1 Startup Flow

```
[User runs python app.py]
    │
    ▼
app.py: os.environ["PATH"] += PROJECT_ROOT / "bin"
    │
    ▼
app.py: ConfigManager.__init__() → loads data/config.json
    │
    ▼
app.py: ctk.set_appearance_mode(theme)
    │
    ▼
app.py: ctk.CTk() → root window (800x600, min 700x500)
    │
    ▼
app.py: StartupCheckFrame(root, on_startup_done)
    │
    ├── StartupCheckFrame.__init__()
    │   ├── Builds UI (title, status_frame, action_frame)
    │   └── _run_checks()
    │       ├── DependencyChecker.check_all()
    │       │   ├── _check_ffmpeg() → bin/ffmpeg.exe --version
    │       │   ├── _check_ffprobe() → bin/ffprobe.exe --version
    │       │   ├── _check_node() → bin/node.exe --version
    │       │   └── _check_ytdlp() → import yt_dlp
    │       ├── _display_results(results) → update UI with ✅/❌/⚠️
    │       └── Enable "Continue" button
    │
    ▼
[User clicks "Continue"]
    │
    ├── _on_continue()
    │   ├── Disable button
    │   ├── Call on_done → app.py creates MainWindow(root, config)
    │   └── Destroy StartupCheckFrame
    │
    ▼
MainWindow.__init__(root, config)
    ├── _build_ui() → URL input, info display, quality selector,
    │                  directory picker, action buttons, progress bar, logs
    ├── _setup_callbacks() → wire DownloadController events
    └── _load_config_state() → restore saved directory
    │
    ▼
app.py: root.mainloop() → event loop starts
```

### 6.2 Download Flow

```
[User pastes URL → auto-validate]
    │
    ▼
[User clicks "Fetch Info"]
    │
    ├── MainWindow._fetch_info()
    │   ├── Disable fetch button, show "Fetching..."
    │   ├── Thread(target=fetch, daemon=True).start()
    │   │   └── InfoExtractor.extract_info(url)
    │   │       ├── yt_dlp.YoutubeDL(quiet=True, ffmpeg_location=...)
    │   │       ├── ydl.extract_info(url, download=False)
    │   │       └── ydl.sanitize_info(info)
    │   └── self.after(0, self._display_info, info)  # Back to main thread
    │
    ▼
MainWindow._display_info(info)
    ├── Title label: "🎬 {title}"
    ├── Info label: "Channel: {uploader}\nDuration: {m}:{s}"
    ├── QualitySelector.set_qualities() → update dropdown
    ├── Thumbnail: Thread(target=load_thumbnail).start()
    └── Enable "⬇ Download" button
    │
    ▼
[User selects quality/mode/save dir → clicks "⬇ Download"]
    │
    ├── MainWindow._start_download()
    │   ├── Build save_dir = Path(dir_var) / "downloads"
    │   ├── quality = QualitySelector.quality
    │   ├── mode = QualitySelector.mode
    │   ├── base_opts = FormatBuilder.get_common_opts("bin", config)
    │   ├── format_opts = FormatBuilder.build_format_opts(quality, mode)
    │   ├── opts = {**base_opts, **format_opts}
    │   ├── Add cookies: browser import or file
    │   ├── Add sponsorblock if configured
    │   ├── Reset UI, disable buttons
    │   └── DownloadController.start_download(url, opts, save_dir)
    │
    ▼
DownloadController.start_download(url, opts, save_dir)
    ├── _stop_event.clear()
    ├── _thread = Thread(target=_download_worker, daemon=True)
    ├── _thread.start()
    └── _poll_queue()
    │
    ├── (on main thread, via app.after(100, _poll_queue))
    │
    ▼
DownloadController._download_worker(url, opts, save_dir)  [THREAD]
    ├── opts["progress_hooks"] = [self._progress_hook]
    ├── opts["logger"] = UILogger(self._queue)
    ├── opts["outtmpl"] = str(save_dir / "%(title)s [%(id)s].%(ext)s")
    │
    ├── with YoutubeDL(opts) as ydl:
    │   ├── ydl.download([url])
    │   │   ├── yt-dlp extracts video info
    │   │   ├── yt-dlp-ejs solves JS challenges via node.exe
    │   │   ├── Downloads video fragment (e.g., f137.mp4)
    │   │   │   └── progress_hook fires every chunk → queue.put(("progress", d))
    │   │   ├── Downloads audio fragment (e.g., f140.m4a)
    │   │   │   └── progress_hook fires every chunk → queue.put(("progress", d))
    │   │   ├── FFmpeg merges → final .mp4
    │   │   └── Post-processors: metadata, thumbnail
    │   │
    │   └── self._queue.put(("done", None))
    │
    ├── OR on exception:
    │   ├── DownloadError → map to error ID → queue.put(("error", id))
    │   ├── ExtractorError → queue.put(("error", f"extractor:{e}"))
    │   ├── UnsupportedError → queue.put(("error", "unsupported_url"))
    │   └── Exception → queue.put(("error", f"unknown:{e}"))
    │
    ▼
DownloadController._poll_queue()  [MAIN THREAD, every 100ms]
    ├── while True: queue.get_nowait()
    │   ├── ("progress", d) → ProgressWidget.update_progress(d)
    │   ├── ("done", None)  → MainWindow.on_done callback
    │   │   ├── ProgressWidget.set_done()
    │   │   ├── Reset buttons to normal state
    │   │   └── Enable "📂 Open Folder"
    │   ├── ("error", msg)  → MainWindow.on_error callback
    │   │   ├── ProgressWidget.set_error(msg)
    │   │   ├── Reset buttons
    │   │   └── Log error message
    │   └── ("log", msg)    → LogsPanel.append_log(msg)
    │
    └── app.after(100, self._poll_queue)  # Schedule next poll
```

---

## 7. Threading Model

### 7.1 Thread Diagram

```
MAIN THREAD                        DOWNLOAD THREAD
─────────────                      ──────────────
    │                                      │
    │  MainWindow runs here                │
    │  tkinter mainloop                    │
    │                                      │
    │  _poll_queue() ◄── every 100ms ──┐   │
    │      │                           │   │
    │      ├── progress ──────────────►│   │  yt-dlp downloads
    │      ├── log ───────────────────►│   │  chunks → progress
    │      ├── done ──────────────────►│   │  hook fires
    │      └── error ─────────────────►│   │
    │                                  │   │
    │  SettingsDialog (modal)          │   │
    │  File dialogs                    │   │
    │                                  │   │
    │  _fetch_info() spawns            │   │
    │  short-lived thread for info     │   │
    │  extraction (not shown)          │   │
    │                                  │   │
```

### 7.2 Thread Safety Rules

1. **UI objects** (`CTk*`, `tk.*`) — created and modified ONLY in main thread
2. **yt-dlp** — runs ONLY in download thread (it blocks)
3. **Queue** — only shared mutable state between threads (thread-safe)
4. **Config** — read-only during download (safe to read from any thread)
5. **Stop event** — `threading.Event`, set from main thread, checked in download thread (not currently used, but available)

### 7.3 Queue Protocol

```python
# Producer (download thread) → queue.put():
queue.put(("progress", progress_dict))   # yt-dlp progress hook data
queue.put(("done", None))                # Download completed
queue.put(("error", error_string))        # Download failed
queue.put(("log", log_string))            # yt-dlp log message

# Consumer (main thread) → queue.get_nowait():
event, data = queue.get_nowait()
```

### 7.4 Cancellation

The `cancel()` method:
1. Sets `_stop_event` (for future use with periodic checks)
2. Cancels the `after()` callback via `app.after_cancel(_after_id)`
3. UI resets to ready state

**Note:** yt-dlp doesn't support clean cancellation mid-download. The download thread continues but produces an incomplete file. The `_stop_event` is available for future implementation of fragment-level cancellation.

---

## 8. Error Handling

### 8.1 Error Catalog

| Error ID | Condition | User Message | User Action |
|---|---|---|---|---|
| `age_restricted` | "Sign in" or "age" in DownloadError | "Login required — use cookies" | Enable cookies in Settings |
| `unavailable` | "unavailable" in DownloadError | "Video is unavailable or deleted" | Check URL validity |
| `rate_limited` | "429" in DownloadError | "Too many requests — retrying..." | Wait before retrying |
| `cookie_error` | "cookie" or "Could not copy" | "Failed to extract cookies — close the browser" | Close browser or switch source |
| `extractor:{e}` | ExtractorError raised | "Video extraction error — update yt-dlp" | Run pip update |
| `unsupported_url` | UnsupportedError raised | "This URL is not supported" | Check URL format |
| `download_error:{msg}` | Other DownloadError | "Download error: {msg}" | Check logs |
| `unknown:{e}` | Unhandled Python exception | "An unexpected error occurred" | Report to developer |

### 8.2 Log Levels

| Prefix | Source | Color |
|---|---|---|
| `[INFO]` | UILogger.info() / filtered debug | None |
| `[WARN]` | UILogger.warning() | None |
| `[ERROR]` | UILogger.error() / error events | None |

### 8.3 yt-dlp Error Handling Strategy

The `_download_worker` catches specific yt-dlp exceptions:
- `DownloadError` — Wraps all download failures (HTTP errors, network issues, etc.)
- `ExtractorError` — Video extraction failures (YouTube API changes)
- `UnsupportedError` — Non-YouTube URLs or invalid URLs
- `GeoRestrictedError` — Available for future use

---

## 9. Build & Deployment

### 9.1 Development Setup

```powershell
# Prerequisites
pip install -r requirements.txt

# Verify
python -c "import yt_dlp; import customtkinter; print('OK')"
python -c "import yt_dlp_ejs; print(f'yt-dlp-ejs: OK')"

# Run
python app.py
```

### 9.2 Production Build

```powershell
pip install pyinstaller
pyinstaller build.spec --clean
# Output: dist/YTDownloader/
```

**Build output structure:**
```
dist/YTDownloader/
├── YTDownloader.exe          ← Main executable
├── base_library.zip
├── python3*.dll
├── *.pyd                     ← Compiled Python modules
├── bin/                      ← Binaries
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   ├── node.exe
│   └── yt-dlp.exe
├── core/                     ← Core modules
├── ui/                       ← UI modules
├── utils/                    ← Utility modules
├── assets/                   ← Icons, fonts
└── data/                     ← Runtime data (created on first run)
```

### 9.3 PyInstaller Spec Details

```python
# build.spec key aspects:
Analysis:
  - binaries: ffmpeg.exe, ffprobe.exe, node.exe (→ bin/)
  - datas: assets/, ui/, core/
  - hiddenimports: yt_dlp, yt_dlp.extractor, yt_dlp.extractor.youtube,
                   yt_dlp.postprocessor, customtkinter
EXE:
  - console: False (no terminal window)
  - icon: assets/logo.ico
  - onedir (not onefile)
```

### 9.4 Distribution

1. Build with `pyinstaller build.spec --clean`
2. Zip the `dist/YTDownloader/` folder
3. User unzips and runs `YTDownloader.exe`

**Expected size:** < 150 MB (includes ffmpeg ~80MB + node.exe ~50MB)

---

## 10. Development Guide

### 10.1 Adding a New Feature

1. **UI component** → Add new file in `ui/` or extend existing widget
2. **Core logic** → Add new file in `core/` or extend existing controller
3. **Utility** → Add new file in `utils/`
4. **Config** → Add defaults in `config_manager.py._DEFAULTS`
5. **PRD** → Update `PRD_YTDownloader_v2.md`
6. **Connect** → Wire UI events to controller in `main_window.py`

### 10.2 Code Style

- Type hints for all function signatures
- Arabic UI strings (no hardcoded English in UI code)
- Docstrings in Arabic for user-facing methods, English for technical
- `snake_case` for functions/variables, `PascalCase` for classes
- Constants in `UPPER_CASE`

### 10.3 Testing

Current testing approach: manual (run app and test features)

Recommended test scenarios:
1. **Basic download**: Paste valid YouTube URL → fetch info → download → verify file
2. **Audio only**: Switch to audio mode → download MP3 → verify .mp3 file
3. **Quality selection**: Test each quality level → verify resolution
4. **Throttling**: Download large video → verify speed recovery
5. **Cookies**: Enable browser cookies → test age-restricted content
6. **Invalid URL**: Paste garbage text → verify error handling
7. **Cancel**: Start download → click cancel → verify clean state
8. **Settings**: Change all settings → restart → verify persistence

---

## 11. Testing Scenarios

### 11.1 Unit Test Candidates

| Module | Test | Expected |
|---|---|---|
| `validators.py` | `is_valid_youtube_url("https://youtube.com/watch?v=xyz")` | `True` |
| `validators.py` | `is_valid_youtube_url("not a url")` | `False` |
| `validators.py` | `extract_video_id("https://youtu.be/abc123def45")` | `"abc123def45"` |
| `file_utils.py` | `safe_filename('file:<>"name')` | `'file____name'` |
| `config_manager.py` | `get("download.default_quality")` | `"1080p"` |
| `config_manager.py` | `set("test.key", "val"); get("test.key")` | `"val"` |
| `format_builder.py` | `build_format_opts("1080p", "video")["format"]` | Contains `"mp4"` |
| `format_builder.py` | `build_format_opts("mp3", "audio")["postprocessors"]` | Contains FFmpegExtractAudio |

### 11.2 Integration Test

Full download flow:
1. Launch app
2. Verify startup check passes
3. Paste: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
4. Click "Fetch Info" → verify title appears
5. Select "1080p" + "video"
6. Click "⬇ Download"
7. Wait for completion
8. Verify `downloads/Rick Astley - Never Gonna Give You Up [...].mp4` exists
9. Verify file plays in media player

---

## 12. Dependencies

### 12.1 Python Packages

```
yt-dlp[default]>=2025.1.1   # Download engine
yt-dlp-ejs>=0.8.0            # JavaScript runtime for YouTube challenges
customtkinter>=5.2.0          # Modern tkinter widgets
Pillow>=10.0.0                # Image processing (thumbnails)
requests>=2.31.0              # HTTP client (thumbnail download)
```

### 12.2 External Binaries

```
bin/ffmpeg.exe      # ~70MB — Video/audio merging, extraction, metadata
bin/ffprobe.exe     # ~10MB — Media file probing
bin/node.exe        # ~45MB — JavaScript runtime for yt-dlp-ejs
bin/yt-dlp.exe      # ~15MB — CLI version (for auto-update, unused directly)
```

### 12.3 Runtime Requirements

- Windows 10/11 x64
- Python 3.11+ (if running from source)
- ~500MB disk space (with binaries)
- Internet connection (for YouTube access)
- Administrator privileges NOT required

---

## 13. Appendix: Complete Change Log

### v2.0 Initial Implementation → Current (May 2026)

| Date | Change | Files Affected |
|---|---|---|
| May 2026 | **Single-Root Architecture**: Changed from multi-CTk to single CTk root with CTkFrame screens | `app.py`, `ui/main_window.py`, `ui/startup_check.py` |
| May 2026 | **CTkSeparator → tk.Frame**: Replaced unavailable `CTkSeparator` with `tk.Frame(height=1)` | `ui/main_window.py` |
| May 2026 | **format_sort**: Added codec preference H.264 > VP9 > AV01 | `core/format_builder.py` |
| May 2026 | **throttledratelimit**: Added 100 KB/s throttle detection | `core/format_builder.py` |
| May 2026 | **yt-dlp-ejs**: Enabled via `js_runtimes` and `extractor_args` | `core/format_builder.py`, `requirements.txt` |
| May 2026 | **PATH at startup**: Added `bin/` to PATH before all imports | `app.py` |
| May 2026 | **Cookie default**: Changed from `"browser"` to `"none"` | `core/config_manager.py` |
| May 2026 | **Cookie error handling**: Added Arabic error message for Chrome DB lock | `core/download_controller.py` |
| May 2026 | **DepChecker absolute paths**: `BIN_DIR` uses `Path(__file__).resolve()` | `core/dep_checker.py` |
| May 2026 | **FFprobe check added**: Missing in original PRD | `core/dep_checker.py` |
| May 2026 | **Node.js optional**: Changed from `required=True` to `required=False` | `core/dep_checker.py` |
| May 2026 | **Format map update**: Prioritize `mp4+m4a` in all format strings | `core/format_builder.py` |
| May 2026 | **Startup check synchronous**: Removed threading from startup check | `ui/startup_check.py` |

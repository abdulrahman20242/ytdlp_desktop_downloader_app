# YT Downloader — Project Reference

**Version:** 3.0 | **Platform:** Windows 10/11 x64 | **Python:** 3.11+
**Repository:** ReizanTech | **Last Updated:** Sep 2026

> **Engine note (v3):** Downloads run `bin/yt-dlp.exe` as an external subprocess.
> The `yt_dlp` Python package is used **only** for info extraction (`download=False`).
> The older "Python API engine" description was incorrect and has been removed.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [File Reference](#3-file-reference)
4. [Configuration](#4-configuration)
5. [yt-dlp CLI Options Reference](#5-yt-dlp-cli-options-reference)
6. [Data Flow](#6-data-flow)
7. [Threading Model](#7-threading-model)
8. [Error Handling](#8-error-handling)
9. [Build & Deployment](#9-build--deployment)
10. [Development Guide](#10-development-guide)
11. [Testing](#11-testing)
12. [Dependencies](#12-dependencies)
13. [Appendix: Complete Change Log](#13-appendix-complete-change-log)

---

## 1. Project Overview

YT Downloader is a Windows desktop application for downloading YouTube videos, audio, and playlists. It downloads via **`bin/yt-dlp.exe` run as a subprocess** (stdout parsed with regex), uses `customtkinter` for the GUI, and `yt-dlp-ejs` + Node.js for solving YouTube's JavaScript challenges.

### Purpose

Provide a simple, reliable YouTube downloader with:
- Highest quality available (up to 4K 2160p)
- Professional audio conversion (MP3 192kbps / M4A AAC)
- Playlist download (all or selected items, per-item progress)
- Modern YouTube support (n-sig challenges, age-restricted content)
- Arabic/English bilingual interface
- Throttling recovery
- Cookie support (browser import or file)
- SponsorBlock segment removal (optional)

### Target Users

- **Casual users:** Paste URL → Fetch → Download → Done
- **Advanced users:** Manual quality/format selection, playlist download, cookie configuration, detailed logs

---

## 2. Architecture

### 2.1 Single-Root Window Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ctk.CTk() [root]                         │
│  Window: config size (default 800x600), min 700x500         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  StartupCheckFrame (CTkFrame)                       │    │
│  │  - DependencyChecker results (4 checks)             │    │
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
│  │  │ Video Info (title, thumbnail, channel, time)  │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ PlaylistPanel (row 2, weight 2, hidden)       │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ QualitySelector (mode + quality)              │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ Save Directory + Action Buttons               │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ ProgressWidget (bar, speed, ETA)              │  │    │
│  │  ├───────────────────────────────────────────────┤  │    │
│  │  │ LogsPanel (row 9, weight 1, collapsible)      │  │    │
│  │  └───────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UI LAYER                                  │
│  customtkinter-based (Arabic UI strings)                     │
│                                                             │
│  MainWindow (CTkFrame)          SettingsDialog (Toplevel)   │
│  ├── Builds all widgets        ├── 3 tabs (General,        │
│  ├── Manages user input          Download, Advanced)        │
│  ├── Calls InfoExtractor       ├── Reads/writes config      │
│  ├── Controls DownloadController└── Modal (grab_set)       │
│  └── Updates progress/logs                                   │
│                                                             │
│  PlaylistPanel         ProgressWidget       LogsPanel       │
│  ├── item checkboxes  ├── Progress bar    ├── Textbox        │
│  ├── Select all/None  ├── Speed/ETA       ├── Collapsible    │
│  └── Download All/Selected └── Filename    └── Auto-scroll   │
│                                                             │
│  QualitySelector (video/mp4_only/audio; Best..360p/MP3/M4A) │
└────────────────────────────────┬────────────────────────────┘
                                 │ events via queue.Queue (100ms poll)
┌────────────────────────────────▼────────────────────────────┐
│                  CONTROLLER LAYER                            │
│                                                             │
│  DownloadController          InfoExtractor                  │
│  ├── start_download()       ├── extract_info(url)           │
│  ├── start_playlist_download()├── extract_playlist(url)     │
│  ├── _run_single()          ├── get_available_qualities()   │
│  ├── events: progress/done/error/log/playlist_item/         │
│  │           playlist_done   └── extract_title/duration/... │
│  └── cancel() → stop_event + proc.terminate()               │
│                                                             │
│  ConfigManager               DependencyChecker              │
│  ├── get(key_path)           ├── check_all() (4 checks)     │
│  ├── set(key_path, value)    ├── FFmpeg, FFprobe required   │
│  └── data/config.json        ├── Node.js optional           │
│                              └── yt-dlp (import yt_dlp)     │
│                                                             │
│  FormatBuilder               Validators / FileUtils         │
│  ├── FORMAT_MAP / _MP4       ├── is_valid_youtube_url()     │
│  ├── build_format_opts()     ├── is_playlist_url()          │
│  └── get_common_opts()       └── open_folder() / ensure_dir │
└────────────────────────────────┬────────────────────────────┘
                                 │ subprocess.Popen + stdout regex
┌────────────────────────────────▼────────────────────────────┐
│                   DOWNLOAD ENGINE                           │
│                                                             │
│  bin/yt-dlp.exe  (built CLI argv, --newline --progress)     │
│  ├── stdout parsed: progress %, speed, ETA, destination     │
│  ├── ERROR:/WARNING: lines → [ERROR]/[WARN] log events      │
│  │                                                          │
│  External processes (invoked by yt-dlp):                    │
│  ├── bin/ffmpeg.exe — merging, audio extraction, metadata   │
│  └── bin/node.exe — JS challenge solving (yt-dlp-ejs)       │
│                                                             │
│  Info extraction only: yt_dlp.YoutubeDL(download=False)     │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Key Design Decisions (ADRs)

| ADR | Decision | Rationale |
|---|---|---|
| ADR-001 | **Subprocess engine** (`bin/yt-dlp.exe`) — not Python API | `proc.terminate()` for real cancellation; OS process isolation; CLI errors map cleanly to error IDs; matches how yt-dlp logs progress |
| ADR-002 | Threading + `queue.Queue` (not asyncio) | tkinter thread-safety, simpler debugging |
| ADR-003 | PyInstaller `--onedir` (planned, not yet built) | Faster startup, antivirus-friendly |
| ADR-004 | ~~yt-dlp nightly channel~~ **Removed** | Conflicting with pip-installed yt-dlp; no nightly config key exists — use pinned `yt-dlp[default]>=X` |
| ADR-005 | yt-dlp-ejs + Node.js | JavaScript challenge solving via `--js-runtimes node:<bin>/node.exe` |
| ADR-006 | `format_sort`: h264 > vp9 > av01 | Better compatibility, practical quality |
| ADR-007 | Single-root CTkFrame architecture | Avoids `after` callback conflicts |
| ADR-008 | In-app playlist downloads (per-item subprocess) | Per-item progress via `playlist_item` events; only `list=` URLs trigger playlist mode |

---

## 3. File Reference

### 3.1 `app.py` — Application Entry Point

```python
def main() -> None
```

**Flow (verified line numbers):**
```python
1. os.environ["PATH"] = str(PROJECT_ROOT / "bin") + os.pathsep + PATH   # Line 11 — BEFORE any imports
2. config = ConfigManager()                                             # Line 20
3. ctk.set_appearance_mode(config.get("ui.theme", "dark"))              # Line 22
4. root = ctk.CTk()                                                     # Line 24
5. root.title("YT Downloader")                                          # Line 25
6. root.geometry(f"{w}x{h}")   # from ui.window_width/height            # Line 28
7. root.minsize(700, 500)                                               # Line 29
8. root.iconbitmap("assets/logo.ico")   # guarded (exists check)        # Line 34
9. StartupCheckFrame(root, on_startup_done)                             # Line 41
10. root.mainloop()                                                      # Line 42
```
`on_startup_done` (created at line 39): destroys `StartupCheckFrame`, constructs `MainWindow(root, config)`.

**Critical detail:** `PATH` must include `bin/` **before any imports** because `yt-dlp-ejs` probes for `node` at module load time.

### 3.2 `ui/main_window.py` — MainWindow (CTkFrame)

`class MainWindow(ctk.CTkFrame)` at line 48. Grid-row constants:

| Constant | Value | Meaning |
|---|---|---|
| `_MAIN_FRAME_ROW` | `2` | main_frame row on `self` |
| `_STATUS_ROW` | `3` | status bar row on `self` |
| `_PLAYLIST_ROW` | `2` | PlaylistPanel row inside main_frame |
| `_LOGS_ROW` | `9` | LogsPanel row inside main_frame |
| `_PLAYLIST_MIN_HEIGHT` | `244` | minsize for playlist row |
| `_LOGS_MIN_HEIGHT` | `126` | minsize for logs row |

**Grid layout:**
```
self (rows 0-3):
  row 0: header "YT Downloader"
  row 1: subtitle
  row 2: main_frame (weight=1, sticky nsew)
  row 3: status_bar

main_frame (rows 0-9):
  row 0: URL input + Fetch button
  row 1: info display (title, thumbnail, channel, duration)
  row 2: PlaylistPanel        (hidden; weight 2, minsize 244)
  row 3: separator (tk.Frame, height=1, bg="#555")
  row 4: QualitySelector
  row 5: save directory (entry + "تصفح" browse button)
  row 6: action buttons (Download, Cancel, Open Folder, Settings)
  row 7: ProgressWidget
  row 8: separator (tk.Frame, height=1)
  row 9: LogsPanel            (weight 1, minsize 126)
```

**Methods:** `_build_ui`, `_setup_callbacks`, `_load_config_state`, `_on_url_change`, `_fetch_info`, `_display_info`, `_display_playlist`, `_set_playlist_layout_active`, `_leave_playlist_mode`, `_load_thumbnail`, `_browse_dir`, `_on_close`, `_build_download_opts`, `_prepare_download_ui`, `_resolve_save_dir`, `_playlist_save_dir`, `_start_download`, `_start_playlist_download`, `_cancel_download`, `_open_folder`, `_open_settings`.

### 3.3 `ui/startup_check.py` — StartupCheckFrame (CTkFrame)

```python
class StartupCheckFrame(ctk.CTkFrame):
    def __init__(self, master, on_done: Callable)
    def _run_checks(self)            # Synchronous dependency check
    def _display_results(self, results)  # green/red + version rows
    def _on_continue(self)           # Disables button, calls on_done, destroys self
```

Checks run synchronously (file probing + `--version` subprocess calls are fast); UI updates via `self.update()` between phases.

### 3.4 `ui/settings_dialog.py` — SettingsDialog (CTkToplevel)

**Three tabs** (notebook + button row; no separate audio tab — audio format is chosen in the main window's QualitySelector):

| Tab | Widgets | Config Keys |
|---|---|---|
| عام (General) | Theme, Language, Save Dir Entry + "..."/Browse | `ui.theme`, `ui.language`, `download.default_dir` |
| التحميل (Download) | Default Quality, Default Mode, Concurrent Fragments spinbox, Retries spinbox | `download.default_quality`, `download.default_mode`, `download.concurrent_fragments`, `download.retries` |
| متقدم (Advanced) | Cookies Source, Browser, Debug Logs checkbox | `cookies.source`, `cookies.browser`, `advanced.show_debug_logs` |

### 3.5 `ui/progress_widget.py` — ProgressWidget (CTkFrame)

```python
class ProgressWidget(ctk.CTkFrame):
    def reset(self)                    # Clears all to initial state
    def update_progress(self, d: dict) # Handles 'downloading', 'finished', 'error'
    def set_done(self)                 # Shows completion state
    def set_error(self, message)       # Shows error state
    def _safe_percent(self, d) -> float  # Bytes-based with string fallback
```

**Widgets:**
- `CTkProgressBar` (row 0) — value 0.0 → 1.0
- Info label (row 1) — e.g. "45.3% · 2.3 MB/s · ETA 00:32"
- Filename label (row 2) — current file being downloaded

### 3.6 `ui/logs_panel.py` — LogsPanel (CTkFrame)

```python
class LogsPanel(ctk.CTkFrame):
    def _toggle(self)    # Show/hide textbox
    def _clear(self)     # Clears all text
    def append_log(self, message)  # Inserts at end, auto-scrolls
```

Toggle button "▼/▲", clear button, monospace font for readable CLI lines.

### 3.7 `ui/quality_selector.py` — QualitySelector (CTkFrame)

```python
class QualitySelector(ctk.CTkFrame):
    def set_qualities(self, qualities)  # Restrict video quality list to available
    @property quality -> str            # Lowercase quality string
    @property mode -> str               # Mode string
```

- **Modes:** `["video", "mp4_only", "audio"]` (`MODE_OPTIONS`)
- **Video qualities:** `["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]` (`QUALITY_OPTIONS`)
- **Audio formats:** `["MP3", "M4A"]` (`AUDIO_FORMATS`)
- Switching to `audio` swaps the quality dropdown to MP3/M4A.

### 3.8 `core/config_manager.py` — ConfigManager

```python
class ConfigManager:
    def __init__(self)
    def _load(self) -> dict          # Loads + deep-merges with defaults
    def _merge(self, base, override) # Recursive merge, preserves missing keys
    def get(self, key_path, default=None)  # Dot-notation read
    def set(self, key_path, value)   # Dot-notation write + auto-save
    def _save(self)                  # Writes JSON to data/config.json
    def reset_to_defaults(self)      # Restores factory defaults
```

**Config file:** `data/config.json` (auto-created with defaults on first run). `CONFIG_PATH` at `core/config_manager.py:4`.

**Default values (`_DEFAULTS`, lines 6-32):**

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
    "file_path": "data/cookies.txt"
  },
  "advanced": {
    "show_debug_logs": false,
    "sponsorblock_remove": false,
    "sponsorblock_categories": ["sponsor"]
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
    def _check_ffmpeg(self) -> DepResult   # bin/ffmpeg.exe (or PATH) → -version, required
    def _check_ffprobe(self) -> DepResult  # bin/ffprobe.exe (or PATH) → -version, required
    def _check_node(self) -> DepResult     # bin/node.exe (or PATH) → --version, OPTIONAL
    def _check_ytdlp(self) -> DepResult    # import yt_dlp → yt_dlp.version.__version__, required
```

**Note 1:** `BIN_DIR` is absolute (`Path(__file__).resolve()`) so it works regardless of CWD.

**Note 2 (v3 correction):** the startup check validates the **Python** `yt_dlp` package, because `info_extractor` imports it. The actual download engine is `bin/yt-dlp.exe`, which is **not** version-checked at startup.

### 3.10 `core/download_controller.py` — DownloadController

```python
class DownloadController:
    def __init__(self, config)
    def set_app(self, app)                    # tk root for after() scheduling
    def on(self, event, callback)             # Register event handler
    def start_download(self, url, opts, save_dir: Path)
    def start_playlist_download(self, entries: list[dict], opts, save_dir: Path)
    def _run_single(self, url, opts, save_dir, index=None) -> str
    def _download_worker(self, url, opts, save_dir)     # spawns _run_single
    def _playlist_worker(self, entries, opts, save_dir) # iterates items
    def _poll_queue(self)                     # drains queue every 100ms via after()
    def cancel(self)                          # stop_event + proc.terminate() + after_cancel
    def is_downloading(self) -> bool
```

**Module-level helpers:** `_strip_ansi`, `_strip_ytdlp_report_suffix`, `_classify_error`, `_parse_progress` (regexes `_PROGRESS_RE`/`_SPEED_RE`/`_ETA_RE`), `_parse_destination`, `_build_argv`.

**Event system:**

| Event | Data | Trigger |
|---|---|---|
| `progress` | `dict` (percent, speed, eta, filename, index) | `[download]` stdout line |
| `done` | `None` | Single download returned `"ok"` |
| `error` | `str` (error ID) | `_run_single` returned non-ok |
| `log` | `str` (line) | stdout lines: `[...]`→`[INFO]`, `WARNING:`→`[WARN]`, `ERROR:`→`[ERROR]` |
| `playlist_item` | `dict` (index, id, status, error, position, total) | Each playlist item start/finish |
| `playlist_done` | `None` | After all playlist items |

**`_run_single` subprocess execution:**
1. Prepend `ffmpeg_location` to `os.environ["PATH"]`
2. `subprocess.Popen([bin/yt-dlp.exe, *argv], stdout=PIPE, stderr=STDOUT, text=True, encoding="utf-8", errors="replace")`
3. Stream `proc.stdout` line by line; stop early if `_stop_event` set
4. Remember first `ERROR:` line; classify via `_classify_error`
5. Return `"ok"` (rc=0 + no error), `"cancelled"`, or a classified error ID; `unknown:{e}` on Popen failure
6. `finally`: `proc.terminate()` if still running

**Error mapping in `_classify_error` (v3):**

```
contains "sign in" or "age" → "age_restricted"
"unavailable"              → "unavailable"
"429"                      → "rate_limited"
"cookiefile" / "cookies-from-browser"
  + Arabic cookie message  → cookie error (Arabic, browser closed message)
"not supported"/"unsupported"
  /"no such extractor"     → "unsupported_url"
"[youtube]" extractor part → "extractor:{msg}"   (suffix stripped)
otherwise                  → "download_error:{msg}"
```

### 3.11 `core/format_builder.py` — FormatBuilder

```python
QUALITY_OPTIONS = ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
MODE_OPTIONS   = ["video", "mp4_only", "audio"]

def build_format_opts(quality: str, mode: str, config=None) -> dict
def _merge_output_format(config) -> str
def _audio_postprocessors(fmt: str) -> list[dict]
def get_common_opts(bin_dir: str, config) -> dict
```

**`get_common_opts` output (verified):**

```python
{
    "ffmpeg_location": str(Path(bin_dir).resolve()),
    "concurrent_fragments": config.get("download.concurrent_fragments", 4),
    "retries": config.get("download.retries", 10),
    "fragment_retries": config.get("download.retries", 10),
    "throttledratelimit": 102400,
    "format_sort": ["vcodec:h264,vp9,av01", "res", "br"],
    "ignoreerrors": False,
    "quiet": False,
    "no_warnings": True,
    "verbose": bool(config.get("advanced.show_debug_logs", False)),
    "noplaylist": True,
    "js_runtimes": {"node": {}},
    "extractor_args": {"youtube-ejs": {}},   # merged with advanced.extractor_args
}
```
Side effect: prepends the resolved `bin/` dir to `os.environ["PATH"]` (so yt-dlp finds `node.exe`/`ffmpeg.exe`).

**`FORMAT_MAP` — video mode format strings:**

```python
{
    "Best":  "bv[ext=mp4]+ba[ext=m4a]/bv+ba/b",
    "2160p": "bv[height<=2160][ext=mp4]+ba[ext=m4a]/bv[height<=2160]+ba/b[height<=2160]",
    "1440p": "bv[height<=1440][ext=mp4]+ba[ext=m4a]/bv[height<=1440]+ba/b[height<=1440]",
    "1080p": "bv[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]",
    "720p":  "bv[height<=720][ext=mp4]+ba[ext=m4a]/bv[height<=720]+ba/b[height<=720]",
    "480p":  "bv[height<=480][ext=mp4]+ba[ext=m4a]/bv[height<=480]+ba/b[height<=480]",
    "360p":  "bv[height<=360][ext=mp4]+ba[ext=m4a]/bv[height<=360]+ba/b[height<=360]",
    "mp3":   "m4a/bestaudio/best",
    "m4a":   "m4a/bestaudio/best",
}
```

**`FORMAT_MAP_MP4` — MP4-only mode:**

```python
{
    "Best":  "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
    "2160p": "bv[height<=2160][ext=mp4]+ba[ext=m4a]/b[height<=2160]",
    # ... same pattern for 1440p/1080p/720p/480p/360p
}
```

**Mode behavior (`build_format_opts`):**
- `audio`: format from `FORMAT_MAP` for mp3/m4a; `postprocessors` from `_audio_postprocessors`; `writethumbnail=True`
- `mp4_only`: format from `FORMAT_MAP_MP4` (no `merge_output_format`; constrained to mp4/m4a already)
- `video`: format from `FORMAT_MAP` + `merge_output_format` from config (default `"mp4"`)

**Audio postprocessors:**
- MP3: `FFmpegExtractAudio(mp3, 192)` + `FFmpegMetadata` + `EmbedThumbnail`
- M4A: `FFmpegMetadata` + `EmbedThumbnail` (no re-encode)

### 3.12 `core/info_extractor.py` — InfoExtractor

Uses the **Python** `yt_dlp.YoutubeDL` API with `download=False` (metadata only). Function list:

```python
def extract_info(url: str) -> dict | None                    # single video metadata
def extract_playlist(url: str) -> dict | None                # playlist {id,title,uploader,count,entries:[{index,id,title,...}]}
def get_available_qualities(url: str) -> list[str]           # ["Best", ...] from available heights
def extract_thumbnail(info: dict) -> str | None
def extract_title(info: dict) -> str                         # info.get("title") or ""
def extract_duration(info: dict) -> int
def extract_uploader(info: dict) -> str
```

### 3.13 `utils/ui_logger.py` — UILogger

```python
class UILogger:
    def __init__(self, q: queue.Queue)
    def debug(self, msg)    # Skips messages starting with "[debug] "
    def info(self, msg)     # → ("log", f"[INFO] {msg}")
    def warning(self, msg)  # → ("log", f"[WARN] {msg}")
    def error(self, msg)    # → ("log", f"[ERROR] {msg}")
```

Implements yt-dlp's logger interface. **v3 note:** the parallel subprocess path captures stdout and emits `[INFO]`/`[WARN]`/`[ERROR]` lines directly, so `UILogger` is currently exercised by `tests/test_ui_logger.py` rather than the download path.

### 3.14 `utils/validators.py` — Validators

```python
def is_valid_youtube_url(url: str) -> bool
def is_playlist_url(url: str) -> bool        # list= in URL
def is_explicit_playlist_url(url: str) -> bool  # standalone list-only URL
def classify_url(url: str) -> str            # "video" | "playlist" | "invalid"
def extract_video_id(url: str) -> str | None
```

### 3.15 `utils/file_utils.py` — File Utils

```python
def ensure_dir(path: Path) -> Path
def open_folder(path: Path)           # os.startfile()
def get_downloads_dir() -> Path       # ~/Downloads/YTDownloader
def safe_filename(name: str) -> str   # Removes <>:"/\|?*
def sanitize_folder_name(name: str) -> str  # Safe Windows folder name for playlists
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
| `download.default_quality` | string | `"1080p"` | `"Best"`, `"2160p"` … `"360p"` |
| `download.default_mode` | string | `"video"` | `"video"`, `"mp4_only"`, `"audio"` |
| `download.concurrent_fragments` | int | `4` | Parallel fragment downloads |
| `download.retries` | int | `10` | Download + fragment retries |
| `download.merge_output_format` | string | `"mp4"` | Container for merged output |
| `cookies.source` | string | `"none"` | `"none"`, `"browser"`, `"file"` |
| `cookies.browser` | string | `"chrome"` | `"chrome"`, `"firefox"`, `"edge"`, `"brave"` |
| `cookies.file_path` | string | `"data/cookies.txt"` | Path to cookies.txt |
| `advanced.show_debug_logs` | bool | `false` | Pass `--verbose` to yt-dlp |
| `advanced.sponsorblock_remove` | bool | `false` | Remove sponsor segments |
| `advanced.sponsorblock_categories` | list | `["sponsor"]` | SponsorBlock categories |
| `advanced.extractor_args` | dict | `{}` (not in defaults) | Extra `--extractor-args` merged over `{"youtube-ejs": {}}` |

### 4.2 Config File Location

`data/config.json` (relative to project root). Created automatically with defaults on first run.

### 4.3 ConfigManager Deep Merge

`_merge()` recursively combines saved values with `_DEFAULTS` so newly added keys appear with default values even when missing from an older saved file. `reset_to_defaults()` restores factory defaults.

### 4.4 Stale Keys (v3)

On-disk `data/config.json` may still contain obsolete keys from earlier versions (`audio.*`, `download.embed_*`, `download.write_subs`, `download.sub_langs`, `advanced.ffmpeg_location`, `advanced.js_runtime`, `advanced.node_path`, `advanced.use_nightly_yt_dlp`). The code **ignores** them — they can be deleted safely. They are not part of the v3 schema shown above.

---

## 5. yt-dlp CLI Options Reference

Downloads build a CLI argv (`_build_argv`) and execute `bin/yt-dlp.exe`. This section maps common-options dict keys to the emitted CLI flags.

### 5.1 Flags Emitted (verified, `_build_argv` lines 73-184)

| Python opt key | CLI flag | Notes |
|---|---|---|
| `format` | `-f <fmt>` | From `FORMAT_MAP` / `FORMAT_MAP_MP4` |
| `postprocessors[FFmpegExtractAudio]` | `-x --audio-format <codec>` (+ `--audio-quality <q>` if set) | e.g. mp3 + 192 |
| `postprocessors[FFmpegMetadata]` | `--add-metadata` | |
| `postprocessors[EmbedThumbnail]` | `--embed-thumbnail` | |
| `writethumbnail` | `--write-thumbnail` | Audio mode |
| `merge_output_format` | `--merge-output-format mp4` | Video mode |
| `noplaylist` | `--no-playlist` | Always set |
| `ffmpeg_location` | `--ffmpeg-location <dir>` | |
| `concurrent_fragments` | `--concurrent-fragments <n>` | Default 4 |
| `retries` | `--retries <n>` | Default 10 |
| `fragment_retries` | `--fragment-retries <n>` | Default 10 |
| `throttledratelimit` | `--throttled-rate 102400` | 100 KB/s throttle re-extract |
| `format_sort` | `--format-sort vcodec:h264,vp9,av01,res,br` | Joined with `,` |
| `js_runtimes` | `--js-runtimes node:<bin>/node.exe` | Node.js for JS challenges |
| `extractor_args` | `--extractor-args <key>:<k=v;...>` | `youtube-ejs` |
| `cookiesfrombrowser` | `--cookies-from-browser chrome` | Browser cookie import |
| `cookiefile` | `--cookies <path>` | cookies.txt |
| `sponsorblock_remove` | `--sponsorblock-remove sponsor` (or configured cats) | |
| `outtmpl` (or default) | `-o "<save_dir>/%(title)s [%(id)s].%(ext)s"` | |
| `quiet` | `--quiet` | Default False → NOT passed |
| `no_warnings` | `--no-warnings` | Default True |
| `verbose` | `--verbose` | Only when `advanced.show_debug_logs` |
| — | `--newline --progress` then `<url>` | Always last |

### 5.2 Format String Reference

yt-dlp format string syntax used:

| Symbol | Meaning |
|---|---|
| `bv` | Best video-only stream |
| `ba` | Best audio-only stream |
| `+` | Download separately then merge |
| `/` | Fallback chain (try left first) |
| `[ext=mp4]` | Filter by container extension |
| `[height<=1080]` | Filter by max height |
| `b` | Best combined (video+audio) stream |

### 5.3 `format_sort` Reference

```python
["vcodec:h264,vp9,av01", "res", "br"]
```

- `vcodec:h264,vp9,av01` — prefer H.264, then VP9, then AV01
- `res` — higher resolution first
- `br` — higher bitrate first

### 5.4 `throttledratelimit` Reference

`102400` bytes/sec (100 KB/s). When yt-dlp detects download speed persistently below this threshold it re-extracts fresh URLs — typically recovering from ~50 KB/s back to 1-5 MB/s.

### 5.5 Stdout Parsing

`_parse_progress` (regexes in `download_controller.py:9-12`):

```
_ANSI_RE     = \x1b\[[0-9;]*m            (strip ANSI color codes)
_PROGRESS_RE = \[download\]\s+([\d.]+)%   → percent
_SPEED_RE    = \bat\s+([^\s]+)\s+ETA       → speed
_ETA_RE      = ETA\s+([^\s)]+)             → ETA
```

Lines matching `[download] ...%` become `progress` events; a destination line (`[download] Destination: <path>`) sets the current filename.

---

## 6. Data Flow

### 6.1 Startup Flow

```
[User runs python app.py]
    │
    ▼
app.py (L11): PATH = bin + PATH   (before all imports)
    │
    ▼
app.py (L20): ConfigManager() → loads data/config.json (deep-merges defaults)
    │
    ▼
app.py (L22): ctk.set_appearance_mode(theme)
    │
    ▼
app.py (L24-34): ctk.CTk() root; title; geometry(config size); minsize(700,500); iconbitmap
    │
    ▼
app.py (L41): StartupCheckFrame(root, on_startup_done)
    │   ├── _run_checks():
    │   │   ├── _check_ffmpeg   → bin/ffmpeg.exe --version   (required)
    │   │   ├── _check_ffprobe  → bin/ffprobe.exe --version  (required)
    │   │   ├── _check_node     → bin/node.exe --version     (optional)
    │   │   └── _check_ytdlp    → import yt_dlp → __version__ (required)
    │   ├── _display_results() → ✅/❌ rows + versions
    │   └── enable "Continue"
    │
    ▼
[User clicks Continue]
    ├── _on_continue() → on_done → app.py creates MainWindow(root, config)
    └── Destroy StartupCheckFrame
    │
    ▼
MainWindow.__init__ → _build_ui → _setup_callbacks → _load_config_state
    │
    ▼
app.py (L42): root.mainloop()
```

### 6.2 Info Fetch / Playlist Fetch Flow

```
[Paste URL → _on_url_change validates + toggles Fetch]
    │
    ▼
MainWindow._fetch_info()  [short-lived daemon thread]
    └── URL is playlist?  → InfoExtractor.extract_playlist(url)
    │       ├── fill PlaylistPanel entries (checkbox rows, thumbnails, badges)
    │       └── _set_playlist_layout_active(True)  → playlist row weight 2
    └── else              → InfoExtractor.extract_info(url)
            ├── _display_info: title/thumbnail/channel/duration
            └── QualitySelector.set_qualities(available)
```

### 6.3 Single Download Flow

```
[User clicks Download]
    │
    ▼
MainWindow._start_download()
    ├── opts = FormatBuilder.get_common_opts("bin", config)
    ├── opts.update(FormatBuilder.build_format_opts(quality, mode, config))
    ├── cookies: browser → opts["cookiesfrombrowser"]; file → opts["cookiefile"]
    ├── sponsorblock if configured (advanced.sponsorblock_remove)
    └── DownloadController.start_download(url, opts, save_dir)
    │
    ▼  [download thread]
DownloadController._download_worker
    └── _run_single(url, opts, save_dir)
        ├── PATH += ffmpeg_location
        ├── argv = _build_argv(opts, url, save_dir)
        ├── proc = Popen([bin/yt-dlp.exe, *argv], stdout=PIPE, stderr=STDOUT, ...)
        ├── for line in proc.stdout:
        │   ├── "ERROR:"  → first_error + ("log", "[ERROR] ...")
        │   ├── "WARNING:"→ ("log", "[WARN] ...")
        │   ├── Destination → current filename
        │   ├── [download]% → ("progress", {...}) via _parse_progress
        │   └── "[..."     → ("log", "[INFO] ...")
        ├── on stop_event → proc.terminate() → "cancelled"
        └── rc==0 and no error → "ok"  else classified error
    ├── result "ok"   → ("done", None)
    └── else          → ("error", result)
    │
    ▼  [main thread, _poll_queue every 100ms]
    ├── progress → ProgressWidget.update_progress
    ├── done     → reset UI, enable folder/settings; ProgressWidget.set_done
    ├── error    → ProgressWidget.set_error + Arabic message; reset UI
    └── log      → LogsPanel.append_log
```

### 6.4 Playlist Download Flow

```
[User clicks Download All / Download Selected]
    │
    ▼
MainWindow._start_playlist_download(entries)
    └── DownloadController.start_playlist_download(entries, opts, save_dir)
    │
    ▼  [playlist thread]
_playlist_worker
    ├── for each entry (position/total):
    │   ├── ("playlist_item", {status:"downloading", ...})
    │   ├── item_url = entry.url or watch?v=<id>
    │   ├── result = _run_single(item_url, opts, save_dir, index=index)
    │   └── ("playlist_item", {status:"completed"|"failed", error, ...})
    └── ("playlist_done", None)
```

---

## 7. Threading Model

### 7.1 Threads

| Thread | Lives In | Purpose |
|---|---|---|
| Main thread | UI | tkinter mainloop; `_poll_queue` every 100ms via `after()` |
| Info/playlist fetch | short `daemon` thread | `extract_info` / `extract_playlist` (Python API, `download=False`) |
| Download thread | `daemon` thread | `_run_single` → `subprocess.Popen` of `bin/yt-dlp.exe` |
| Playlist thread | `daemon` thread | Iterates items, calls `_run_single` per item |

### 7.2 Thread Safety Rules

1. **UI objects** (`CTk*`, `tk.*`) — created and modified ONLY in main thread
2. **`subprocess.Popen`** — runs ONLY in download/playlist thread
3. **Queue** — the only shared mutable state between threads (thread-safe)
4. **Config** — read-only during download (safe to read from any thread)
5. **Stop event** — `threading.Event`, set from main thread, checked in `_run_single`'s stdout loop and in workers

### 7.3 Queue Protocol

```python
# Producer (worker threads):
queue.put(("progress", dict))       # parsed [download] line (+ filename, optional index)
queue.put(("done", None))           # single download succeeded
queue.put(("error", str))           # classified error ID
queue.put(("log", str))             # log line (already level-prefixed)
queue.put(("playlist_item", dict))  # per-item status
queue.put(("playlist_done", None))  # all items finished

# Consumer (main thread, every 100ms via root.after):
event, data = queue.get_nowait()
```

### 7.4 Cancellation

`cancel()` (download_controller.py:400):
1. `self._stop_event.set()`
2. `self._proc.terminate()` if a process is running (pcancel mid-`subprocess`; the process is killed so no incomplete merge)
3. `app.after_cancel(self._after_id)` stops the next poll
4. UI resets to ready state; worker posts `"cancelled"` and returns without `done`/`error`

---

## 8. Error Handling

### 8.1 Error Catalog (v3)

| Error ID | Condition (message contains) | User Message | User Action |
|---|---|---|---|
| `age_restricted` | `"sign in"` or `"age"` + `[youtube]` | Login required — enable cookies | Settings → Advanced → cookies |
| `unavailable` | `"unavailable"` | Video unavailable or deleted | Check URL validity |
| `rate_limited` | `"429"` | Rate limited — retry after a pause | Wait, then retry |
| cookie error | `cookiefile`/`cookies-from-browser` handling | Arabic: "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات" | Close browser or switch to cookies file |
| `unsupported_url` | `"not supported"` / `"unsupported"` / `"no such extractor"` | This URL is not supported | Check URL format |
| `extractor:{msg}` | `[youtube]` extractor error | Extraction error (report suffix stripped) | Update yt-dlp / try later |
| `download_error:{msg}` | any other `ERROR:` line | Download error with details | Check logs |
| `unknown:{e}` | Popen/exception path | Unknown error | Report to developer |

Map `_classify_error` (download_controller.py:26), suffix stripper `_strip_ytdlp_report_suffix` (line 19).

### 8.2 Log Line Levels

| Prefix | Source |
|---|---|
| `[INFO]` | stdout lines starting with `[` (e.g. `[download]`, `[youtube]`) |
| `[WARN]` | stdout lines starting with `WARNING:` |
| `[ERROR]` | stdout lines starting with `ERROR:` |

### 8.3 Strategy

Because downloads are a subprocess, yt-dlp exceptions cannot propagate into Python. All failure modes surface as `ERROR:` lines on stdout, captured verbatim and classified to a stable error ID. This eliminates the old `DownloadError`/`ExtractorError`/`UnsupportedError` exception branches (removed in the v3 engine rewrite).

---

## 9. Build & Deployment

### 9.1 Development Setup

```powershell
pip install -r requirements.txt
python -c "import yt_dlp; import customtkinter; print('OK')"

# Run
python app.py
```

### 9.2 Production Build (Planned)

There is **no `build.spec`** in the repository yet — the PyInstaller build is planned, not shipped. Intended command:

```powershell
pip install pyinstaller
pyinstaller --onedir --noconsole --name YTDownloader --icon assets/logo.ico app.py
# Output: dist/YTDownloader/
```

**Expected structure:**
```
dist/YTDownloader/
├── YTDownloader.exe          ← Main executable (no console)
├── _internal/                ← PyInstaller bundles Python + packages
├── bin/                      ← Hand-shipped binaries
│   ├── ffmpeg.exe  ffprobe.exe  node.exe  yt-dlp.exe
├── assets/
│   └── logo.ico
└── data/                     ← Created at first run (config.json)
```

**Build considerations (from verified code):**
- The engine launches `bin/yt-dlp.exe` by path (`_exe_path` resolves `bin/` next to the source), so `bin/` must sit next to the executable in the distribution
- `app.py` prepends `PROJECT_ROOT / "bin"` to `PATH` before imports (node.exe for yt-dlp-ejs)
- `data/config.json` is written relative to the CWD (`Path("data/config.json")`) — run from the EXE's folder, or a launcher script should set CWD
- `dep_checker.BIN_DIR` is absolute (`Path(__file__).resolve().parent.parent / "bin"`) — works from any CWD
- `yt-dlp-ejs` is a **plugin** (loaded by the yt-dlp binary from its own plugin paths), not imported by Python — ensure it is installed into the same environment/plugin dir as the download engine

### 9.3 Distribution

1. Build with PyInstaller `--onedir`
2. Copy `bin/`, `assets/`, and `data/` (template) next to the EXE
3. Zip `dist/YTDownloader/`; user unzips and runs `YTDownloader.exe`

**Expected size:** < 150 MB (includes ffmpeg ~80MB + node.exe ~50MB + yt-dlp.exe)

---

## 10. Development Guide

### 10.1 Adding a New Feature

1. **UI component** → Add file in `ui/` or extend an existing widget
2. **Core logic** → Add file in `core/` or extend the controller/format builder
3. **Utility** → Add file in `utils/`
4. **Config** → Add defaults in `config_manager.py._DEFAULTS`
5. **PRD** → Update `docx/PRD_YTDownloader_v3.md`
6. **Reference** → Update `docx/PROJECT_REFERENCE.md` (keep in sync)
7. **Connect** → Wire UI events to the controller in `main_window.py`
8. **Tests** → Add/update `tests/` (see §11) and run pytest

### 10.2 Code Style

- Type hints on all function signatures
- Arabic UI strings (no hardcoded English in UI code)
- Module-level constants in `UPPER_CASE`; `snake_case` functions/variables; `PascalCase` classes
- Config read through `ConfigManager.get("dot.notation")`

### 10.3 Verification Checklist

Run before finishing any change:

```powershell
pytest tests/ -q
ruff check core/ utils/ ui/ tests/
```

---

## 11. Testing

The project has a **pytest suite** (currently **272 passing tests**, ruff clean). `tests/conftest.py` stubs `customtkinter`/tkinter and `yt_dlp` so UI/controller logic can be tested headlessly.

| File | Focus |
|---|---|
| `test_validators.py` | URL validation, playlist/video/invalid classification, video id extraction |
| `test_file_utils.py` | `safe_filename`, `sanitize_folder_name`, `get_downloads_dir`, `ensure_dir` |
| `test_config_manager.py` | Defaults, deep merge, get/set, reset |
| `test_format_builder.py` | `build_format_opts` for video/mp4_only/audio, `get_common_opts`, maps |
| `test_download_controller.py` | argv building, stdout parsing (progress/speed/ETA), error classification, cancel, single + playlist worker flows |
| `test_dep_checker.py` | Check results under mocked binaries (missing/found/paths) |
| `test_info_extractor.py` | Metadata extraction incl. `None`-safe defaults |
| `test_progress_widget.py` | Percent math / string fallback |
| `test_settings_flow.py` | Settings dialog ↔ config round-trip |
| `test_playlist_panel.py` | Playlist row model, select all, selections → entries |
| `test_ui_logger.py` | UILogger queue protocol + debug filter |

### Manual Smoke Test

1. Launch app → startup check passes (FFmpeg, FFprobe, Node.js, yt-dlp)
2. Paste a valid YouTube URL → Fetch → title/thumbnail/qualities appear
3. Download 1080p video into the chosen save dir → file `<title> [<id>].mp4`
4. Switch to audio mode → download MP3 192kbps
5. Paste a playlist URL → PlaylistPanel shows items → Download Selected → watch per-item progress
6. Start a download → Cancel → clean reset, no orphan process
7. Settings → change theme/quality → restart → verify persistence

---

## 12. Dependencies

### 12.1 Python Packages (`requirements.txt` — all used)

```
yt-dlp[default]>=2025.1.1   # Download engine + info extraction (yt_dlp package)
yt-dlp-ejs>=0.8.0            # yt-dlp plugin (JS challenge solver) — NOT Python-imported
customtkinter>=5.2.0          # GUI widgets
Pillow>=10.0.0                # Image processing (thumbnails)
requests>=2.31.0              # HTTP client (thumbnail download)
```

### 12.2 External Binaries (`bin/`)

```
bin/ffmpeg.exe      # Video/audio merging, extraction, metadata (required)
bin/ffprobe.exe     # Media file probing (required — checked at startup)
bin/node.exe        # JavaScript runtime for yt-dlp-ejs (OPTIONAL — auto-solved otherwise)
bin/yt-dlp.exe      # The download engine — run as a subprocess for every download
```

### 12.3 Runtime Requirements

- Windows 10/11 x64
- Python 3.11+ (if running from source)
- ~500MB disk space (with binaries)
- Internet connection (for YouTube access)
- Administrator privileges NOT required

---

## 13. Appendix: Complete Change Log

### v3.0 (Sep 2026) — Subprocess engine + docs corrections

| Change | Files |
|---|---|
| **Download engine switched to subprocess**: `bin/yt-dlp.exe` runs with built CLI argv; stdout parsed by regex (`_ANSI_RE`, `_PROGRESS_RE`, `_SPEED_RE`, `_ETA_RE`); old `DownloadError`/`ExtractorError`/`UnsupportedError` exception branches removed | `core/download_controller.py` |
| **Real cancellation**: `cancel()` = stop_event + `proc.terminate()` (was best-effort with Python API) | `core/download_controller.py` |
| **Playlist downloads in-app**: PlaylistPanel item rows; `start_playlist_download` + `playlist_item`/`playlist_done` events | `ui/main_window.py`, `ui/playlist_panel.py`, `core/download_controller.py` |
| **Settings dialog 3 tabs** (no audio tab — format selected in main window) | `ui/settings_dialog.py`, `ui/quality_selector.py` |
| **Config schema corrected**: stale keys removed from docs (`audio.*`, `download.embed_*`, `advanced.ffmpeg_location/js_runtime/node_path/use_nightly_yt_dlp`); `_DEFAULTS` is source of truth | `core/config_manager.py`, all `docx/*` |
| **DepChecker truth**: checks binaries + `import yt_dlp`; only Node.js is optional | `core/dep_checker.py`, docs |
| **Error catalog aligned** with `_classify_error` (age_restricted, unavailable, rate_limited, Arabic cookie message, unsupported_url, extractor:{msg}, download_error:{msg}) | `core/download_controller.py`, docs |
| **`get_common_opts` corrected**: `quiet=False`, `noplaylist=True`, `verbose` from config, `extractor_args` merged | `core/format_builder.py`, docs |
| **`build_format_opts(quality, mode, config=None)`** signature; `merge_output_format` only in video mode | `core/format_builder.py`, docs |
| **ADR-001 reversed** (Python API → subprocess); ADR-004 (nightly channel) removed | this doc, `README.md`, PRDs |
| Requirements verified (5 lines, all used) | `requirements.txt`, docs |
| Documentation rewritten to 3.0 (README, PROJECT_SUMMARY, PRD v3, this reference) | `README.md`, `docx/*` |
| Install/update flows and Python API claims corrected across all docs | `docx/*` |

### v2.0 (May 2026) — Prior documented baseline

| Change | Files |
|---|---|
| Single-root CTkFrame architecture (StartupCheckFrame → MainWindow) | `app.py`, `ui/*` |
| `CTkSeparator` → `tk.Frame(height=1)` | `ui/main_window.py` |
| `format_sort` codec preference h264 > vp9 > av01; `throttledratelimit` 100 KB/s | `core/format_builder.py` |
| yt-dlp-ejs via `js_runtimes`/`extractor_args` | `core/format_builder.py`, `requirements.txt` |
| `bin/` added to PATH before imports | `app.py` |
| Cookie default `"browser"` → `"none"`; Arabic cookie error message | `core/config_manager.py`, `core/download_controller.py` |
| DepChecker absolute `BIN_DIR`; FFprobe check added; Node.js made optional | `core/dep_checker.py` |
| Format maps prioritize mp4+m4a | `core/format_builder.py` |
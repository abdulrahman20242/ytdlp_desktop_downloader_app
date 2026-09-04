# YT Downloader Desktop Application

**Version:** 2.0 (May 2026)
**Author:** ReizanTech
**Platform:** Windows 10/11 (x64)
**Language:** Python 3.11+

---

## 📋 Overview

YT Downloader is a desktop application for downloading YouTube videos and audio with high efficiency. Built with Python, `customtkinter` for GUI, and `yt-dlp` as the core download engine.

### Key Features

- **Video Download** — up to 4K (2160p) with H.264 (avc1) preference for maximum compatibility
- **Audio Download** — MP3 (192kbps) or M4A (no re-encode, faster)
- **Format Selection** — Auto-select best format with `mp4+m4a` priority
- **Throttling Recovery** — Automatic recovery when YouTube throttles speed
- **JavaScript Challenges** — Solved via `yt-dlp-ejs` + Node.js (included `node.exe`)
- **Cookie Support** — Browser import (Chrome/Firefox/Edge/Brave) or cookies.txt file
- **Threaded Downloads** — UI never freezes during download
- **Progress Tracking** — Real-time progress bar with speed and ETA
- **Logs Panel** — Collapsible log viewer with debug information
- **Startup Dependency Check** — Validates FFmpeg, Node.js, yt-dlp at launch
- **Arabic/English UI** — Right-to-left interface with full Arabic support

---

## 🏗 Architecture

### Single-Root Architecture

The application uses **one** persistent `CTk` root window. All screens (startup check, main window) are `CTkFrame` subclasses embedded in the same root. This avoids conflicts with customtkinter's internal `after` callbacks.

```
app.py
  └── ctk.CTk() ─── root (single persistent window)
        ├── StartupCheckFrame ─── dependency check screen
        └── MainWindow ────────── main download interface
              ├── QualitySelector
              ├── ProgressWidget
              └── LogsPanel
```

### Layer Structure

```
┌─────────────────────────────────────────────────────┐
│                    UI Layer                          │
│  MainWindow (CTkFrame) · SettingsDialog (CTkToplevel)│
│  ProgressWidget · LogsPanel · QualitySelector        │
│  StartupCheckFrame                                    │
└────────────────────┬────────────────────────────────┘
                     │  events / callbacks via queue.Queue
┌────────────────────▼────────────────────────────────┐
│                Controller Layer                      │
│  DownloadController · InfoExtractor                  │
│  ConfigManager · DependencyChecker                   │
│  FormatBuilder · Validators                          │
└──────┬─────────────────────┬──────────────────────── ┘
       │                     │
┌──────▼──────┐    ┌─────────▼─────────┐
│  Download   │    │   Info Extractor  │
│  Engine     │    │   (no download)   │
│  yt-dlp API │    │   yt-dlp API      │
└──────┬──────┘    └─────────┬─────────┘
       │                     │
┌──────▼──────────────────────▼────────┐
│           yt_dlp.YoutubeDL           │
│  progress_hooks · postprocessors     │
│  logger · js_runtimes                │
└──────┬───────────────────────────────┘
       │  spawns external processes
┌──────▼──────────────────────────────┐
│  bin/ffmpeg.exe   bin/node.exe      │
└─────────────────────────────────────┘
```

---

## 📁 Project Structure

```
yt-downloader/
│
├── app.py                     ← Entry point (PATH setup + single root CTk)
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py         ← Main window (CTkFrame) — URL input, info, controls
│   ├── settings_dialog.py     ← Settings window (CTkToplevel) — 4 tabs
│   ├── startup_check.py       ← Dependency check frame (CTkFrame)
│   ├── progress_widget.py     ← Progress bar + speed/ETA stats
│   ├── logs_panel.py          ← Collapsible log textbox
│   └── quality_selector.py    ← Quality + mode dropdown selector
│
├── core/
│   ├── __init__.py
│   ├── config_manager.py      ← JSON config management with deep merge
│   ├── dep_checker.py         ← Binary existence + version check
│   ├── download_controller.py ← Threaded download with queue.Queue polling
│   ├── info_extractor.py      ← YouTube info extraction (no download)
│   └── format_builder.py      ← Format string builder + common opts
│
├── utils/
│   ├── __init__.py
│   ├── ui_logger.py           ← Logger → queue for thread-safe UI updates
│   ├── validators.py          ← YouTube URL regex validation
│   └── file_utils.py          ← File/folder helper functions
│
├── assets/
│   ├── logo.ico
│   ├── logo.png
│   └── fonts/
│
├── bin/                       ← Binaries (not committed to Git)
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   ├── node.exe               ← Node.js 24.16.0 standalone
│   └── yt-dlp.exe             ← For auto-update
│
├── data/                      ← Runtime files
│   ├── config.json            ← Auto-generated on first run
│   ├── history.json
│   ├── archive.txt
│   └── cookies.txt            ← Optional
│
├── downloads/                 ← Default download directory
├── logs/
├── build.spec                 ← PyInstaller spec (--onedir)
├── requirements.txt
└── PRD_YTDownloader_v2.md     ← Product Requirements Document
```

---

## 🧩 Core Components

### app.py (Entry Point)

```python
# 1. Add bin/ to PATH before any imports
os.environ["PATH"] = str(PROJECT_ROOT / "bin") + os.pathsep + os.environ.get("PATH", "")

# 2. Create single persistent root CTk
root = ctk.CTk()

# 3. Show startup check as embedded frame
StartupCheckFrame(root, on_startup_done)

# 4. On continue → destroy StartupCheckFrame → create MainWindow
def on_startup_done():
    MainWindow(root, config)

# 5. Single mainloop call
root.mainloop()
```

### config_manager.py

Manages `data/config.json` with deep merge (preserves defaults for missing keys). Supports dot-notation access: `config.get("download.default_quality")`.

**Default config:**
```json
{
  "version": "1.0",
  "ui": { "theme": "dark", "language": "ar", "window_width": 800, "window_height": 600 },
  "download": {
    "default_dir": "C:/Users/User/Downloads/YTDownloader",
    "default_quality": "1080p",
    "default_mode": "video",
    "concurrent_fragments": 4, "retries": 10,
    "merge_output_format": "mp4", "embed_thumbnail": false, "embed_metadata": true
  },
  "audio": { "default_format": "mp3", "mp3_quality": "192", "embed_thumbnail": true },
  "cookies": { "source": "none", "browser": "chrome", "file_path": "data/cookies.txt" },
  "advanced": {
    "ffmpeg_location": "bin", "js_runtime": "node", "node_path": "bin/node.exe",
    "show_debug_logs": false, "sponsorblock_remove": false,
    "sponsorblock_categories": ["sponsor"]
  }
}
```

### download_controller.py

Threaded download engine using `threading.Thread` + `queue.Queue` + `app.after()` polling.

- **`start_download(url, opts, save_dir)`** — spawns daemon thread
- **`_download_worker()`** — runs `YoutubeDL.download()` with progress hooks
- **`_poll_queue()`** — called every 100ms via `after()` to read events from queue
- **`cancel()`** — sets stop event
- **Event types:** `progress`, `done`, `error`, `log`

**Error handling:**
| Error | User Message |
|---|---|
| Age restricted | `age_restricted` → "Login required" |
| Unavailable | `unavailable` → "Video unavailable" |
| Rate limited | `rate_limited` → "Retrying..." |
| Cookie error | Clear Arabic message with instructions |
| ExtractorError | `extractor:{msg}` |
| UnsupportedError | `unsupported_url` |
| Generic | `unknown:{msg}` |

### format_builder.py

Builds format strings and common opts for yt-dlp.

**Format priority:** `mp4+m4a` first → any video+audio → combined fallback

**Format sort (codec preference):**
```python
"format_sort": ["vcodec:h264,vp9,av01", "res", "br"]
# H.264 (avc1) > VP9 > AV01
```

**Throttling recovery:**
```python
"throttledratelimit": 102400  # 100 KB/s — triggers re-extraction
```

**JavaScript runtime (yt-dlp-ejs):**
```python
"js_runtimes": {"node": {}}
"extractor_args": {"youtube-ejs": {}}
```

**Format map:**
| Quality | Format String |
|---|---|
| Best | `bv[ext=mp4]+ba[ext=m4a]/bv+ba/b` |
| 2160p | `bv[height<=2160][ext=mp4]+ba[ext=m4a]/...` |
| 1080p | `bv[height<=1080][ext=mp4]+ba[ext=m4a]/...` |
| 720p | `bv[height<=720][ext=mp4]+ba[ext=m4a]/...` |
| MP3 | `m4a/bestaudio/best` + FFmpegExtractAudio pp |
| M4A | `m4a/bestaudio/best` + FFmpegMetadata pp |

### dep_checker.py

Checks for required binaries using absolute paths (`Path(__file__).resolve()`).

| Dependency | Required | Check Method |
|---|---|---|
| FFmpeg | ✅ Yes | `bin/ffmpeg.exe` → `--version` |
| FFprobe | ✅ Yes | `bin/ffprobe.exe` → `--version` |
| Node.js | ⚠️ Optional | `bin/node.exe` → `--version` |
| yt-dlp | ✅ Yes | `import yt_dlp` |

### info_extractor.py

Extracts video metadata without downloading. Used for thumbnail preview, quality detection, and info display.

---

## 🔧 Installation & Setup

### Prerequisites

- Python 3.11+
- Windows 10/11 (x64)

### Setup

```powershell
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Run the application
python app.py
```

### Requirements

```
yt-dlp[default]>=2025.1.1
yt-dlp-ejs>=0.8.0
customtkinter>=5.2.0
Pillow>=10.0.0
requests>=2.31.0
```

### Binaries (in `bin/`)

| File | Source | Purpose |
|---|---|---|
| `ffmpeg.exe` | yt-dlp/FFmpeg-Builds | Video/audio merging |
| `ffprobe.exe` | yt-dlp/FFmpeg-Builds | Media probing |
| `node.exe` | Node.js standalone | JavaScript runtime for yt-dlp-ejs |
| `yt-dlp.exe` | yt-dlp releases | Auto-update (not used for downloads) |

---

## 🚀 Usage

1. Run `python app.py`
2. Startup check validates dependencies → click **Continue**
3. Paste a YouTube URL in the input field
4. Click **Fetch** to get video info (title, thumbnail, qualities)
5. Select quality (Best / 2160p / 1440p / 1080p / 720p / 480p / 360p)
6. Select mode (Video / MP4 Only / Audio)
7. Choose save folder (default: `downloads/`)
8. Click **⬇ Download** to start download
9. Monitor progress bar, speed, ETA, and logs
10. Click **📂 Open Folder** to open the download location

### Settings (⚙ Settings)

| Tab | Options |
|---|---|
| General | Theme (dark/light/system), Language (ar/en), Save folder |
| Download | Default quality, mode, concurrent fragments, retries |
| Audio | Audio format (mp3/m4a), MP3 quality (128/192/320 kbps) |
| Advanced | Cookies source (none/browser/file), Browser selection, Debug logs |

---

## 📦 Building EXE

```powershell
pip install pyinstaller
pyinstaller build.spec --clean
# Output: dist/YTDownloader/YTDownloader.exe
```

> Uses `--onedir` (not `--onefile`) for faster startup and antivirus compatibility.

---

## ⚙️ yt-dlp Configuration

### Common Options (get_common_opts)

```python
{
    "ffmpeg_location": str(bin_path),
    "concurrent_fragments": 4,        # Parallel fragment download
    "retries": 10,                    # Download retries
    "fragment_retries": 10,           # Fragment retries
    "throttledratelimit": 102400,     # 100 KB/s throttle detection
    "format_sort": ["vcodec:h264,vp9,av01", "res", "br"],  # Codec preference
    "js_runtimes": {"node": {}},      # Enable yt-dlp-ejs
    "extractor_args": {"youtube-ejs": {}},  # YouTube EJS extractor
    "ignoreerrors": False,
    "quiet": True,
    "no_warnings": True,
}
```

### PATH Configuration

`app.py` adds `bin/` to `PATH` **before any imports** to ensure yt-dlp-ejs finds `node.exe` at load time:

```python
os.environ["PATH"] = str(PROJECT_ROOT / "bin") + os.pathsep + os.environ.get("PATH", "")
```

---

## 📊 Status

| Feature | Status |
|---|---|
| Format selection (136+140 = avc1+m4a) | ✅ |
| Audio download (MP3/M4A) | ✅ |
| Throttling recovery | ✅ |
| Node.js JS challenges (yt-dlp-ejs) | ✅ |
| Cookie support | ✅ |
| Thumbnail preview | ✅ |
| Settings dialog | ✅ |
| Startup dependency check | ✅ |
| Arabic/English UI | ✅ |
| Playlist download | 🚧 Future |
| Queue system | 🚧 Future |

---

## 🔄 Changes from PRD (Before vs After)

### Architecture

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Window Architecture** | `StartupCheckDialog` as `CTkToplevel` + `MainWindow` as separate `CTk` | **Single-Root:** One `CTk` root, all screens are `CTkFrame` |
| **Startup Check** | `StartupCheckDialog(CTkToplevel)` with threading + `after()` | `StartupCheckFrame(CTkFrame)` synchronous checks |
| **MainWindow** | `class MainWindow(ctk.CTk)` | `class MainWindow(ctk.CTkFrame)` — embedded in root |
| **Separator Widget** | `ctk.CTkSeparator` (not available in 5.2.2) | `tk.Frame(height=1, bg="#555")` |

### Cookie Handling

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Default Source** | `"file"` | `"none"` (avoids Chrome lock errors) |
| **Error Handling** | Not specified | Arabic error message with fix instructions |

### Format Selection

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Format Map** | `bv*+ba/b` (no mp4 preference) | `bv[ext=mp4]+ba[ext=m4a]/bv+ba/b` |
| **Codec Priority** | yt-dlp default (av01 > vp9 > avc1) | `format_sort: ["vcodec:h264,vp9,av01", "res", "br"]` |
| **Throttling** | Not specified | `throttledratelimit: 102400` |
| **Result** | `398+251` (av01+opus) | `136+140` (avc1+m4a) ✅ |

### yt-dlp-ejs Integration

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **JS Runtime** | Only `extractor_args` with `android_vr` client | `js_runtimes: {"node": {}}` + `extractor_args: {"youtube-ejs": {}}` |
| **PATH Setup** | In `get_common_opts` (too late) | In `app.py` before all imports |
| **requirements.txt** | Not listed | `yt-dlp-ejs>=0.8.0` |

### Error Handling

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Cookie Error** | Not handled | Specific check + Arabic message |
| **Error Display** | Generic error dialog | Specific Arabic messages per error type |

### Dependency Checker

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **BIN_DIR** | `Path("bin")` (relative to CWD) | `Path(__file__).resolve().parent.parent / "bin"` (absolute) |
| **FFprobe** | Not checked | Added `_check_ffprobe()` |
| **Node.js Required** | `required=True` | `required=False` (optional — fallback to android_vr) |

---

## 🧵 Threading Model

```
Main Thread (UI)                    Download Thread (yt-dlp)
─────────────────                   ────────────────────────
      │                                      │
      │  start_download(url, opts)           │
      │ ──────────────────────────────────►  │
      │                                      │
      │  _poll_queue() ◄── every 100ms ──┐   │
      │      │                           │   │
      │      ├── progress ──► update UI  │   │
      │      ├── log ──────► append log  │   │
      │      ├── done ─────► on_success  │   │
      │      └── error ────► on_error    │   │
      │                                  │   │
      │  cancel()                        │   │
      │ ───────────────────────────────► │   │
      │                                  │   │
```

### Communication Pattern

The UI thread and download thread communicate through a **thread-safe `queue.Queue`**:

```python
# In download thread:
self._queue.put(("progress", d))    # Send progress update
self._queue.put(("done", None))      # Send completion
self._queue.put(("error", msg))      # Send error

# In UI thread (polled every 100ms):
def _poll_queue(self):
    try:
        while True:
            event, data = self._queue.get_nowait()
            if event == "progress": self._progress_widget.update_progress(data)
            elif event == "done":   self._on_success()
            elif event == "error":  self._on_error(data)
            elif event == "log":    self._logs_panel.append_log(data)
    except queue.Empty:
        pass
    self.master.after(100, self._poll_queue)  # Schedule next poll
```

### Thread Safety Rules

1. **UI updates** only in main thread (via `_poll_queue`)
2. **yt-dlp calls** only in download thread
3. **Queue** is the only shared mutable state (thread-safe by design)
4. **Stop event** (`threading.Event`) for cancellation

---

## 🔄 Download Flow (Detailed)

```
1. User pastes URL
       │
2. Validate URL (regex check)
       │
3. User clicks "Fetch Info"
       │
4. InfoExtractor.extract_info(url)
   ├── Creates YoutubeDL with download=False
   ├── Extracts: title, thumbnail, duration, uploader, formats
   └── Returns sanitized info dict
       │
5. Display info in UI
   ├── Title label
   ├── Thumbnail image (downloaded in background thread)
   ├── Channel name + duration
   └── Available qualities dropdown
       │
6. User clicks "⬇ Download"
       │
7. Build opts
   ├── get_common_opts() → base options
   ├── build_format_opts() → format + postprocessors
   ├── Add cookies if configured
   └── Add sponsorblock if configured
       │
8. DownloadController.start_download()
   ├── Creates daemon thread
   ├── Sets progress_hooks → queue
   ├── Sets logger → queue
   └── Starts _poll_queue()
       │
9. Download thread runs YoutubeDL.download()
   ├── yt-dlp downloads video fragment (e.g., .f137.mp4)
   ├── yt-dlp downloads audio fragment (e.g., .f140.m4a)
   ├── FFmpeg merges video + audio → .mp4
   └── FFmpegMetadata + EmbedThumbnail post-processors
       │
10. On success → "Download complete successfully"
     └── Enable "📂 Open Folder" button
```

---

## 🚀 Startup Flow

```
python app.py
    │
    ├── 1. Add bin/ to PATH
    │       (ensures node.exe found by yt-dlp-ejs at import time)
    │
    ├── 2. Create ConfigManager
    │       (loads data/config.json, falls back to defaults)
    │
    ├── 3. Set appearance mode (dark/light/system)
    │
    ├── 4. Create single CTk root window
    │       (800x600, min 700x500, themed)
    │
    ├── 5. Create StartupCheckFrame (embedded CTkFrame)
    │       ├── Run DependencyChecker.check_all()
    │       ├── Display results (✅/❌/⚠️)
    │       └── Enable "Continue" button
    │
    ├── 6. User clicks "Continue"
    │       ├── Destroy StartupCheckFrame
    │       └── Create MainWindow (CTkFrame)
    │
    └── 7. root.mainloop()
            (single event loop for entire app lifetime)
```

---

## ❌ Error Catalog

| Error ID | Cause | User Message | UI Action |
|---|---|---|---|
| `age_restricted` | Video requires age verification | "Login required — use cookies" | Enable cookies in settings |
| `unavailable` | Video deleted/private | "Video is unavailable or deleted" | Check URL, try another video |
| `rate_limited` | Too many requests (HTTP 429) | "Too many requests — retrying..." | Wait before retrying |
| `cookie_error` | Chrome open / DB locked | "Failed to extract cookies from browser — close the browser or use a cookies file" | Close browser or switch to file |
| `extractor:{msg}` | YouTube API changed | "Video extraction error — update yt-dlp" | Run `pip install --pre --upgrade yt-dlp[default]` |
| `unsupported_url` | Non-YouTube or invalid URL | "This URL is not supported" | Check URL format |
| `ffmpeg_not_found` | FFmpeg missing | "FFmpeg is required to merge video and audio" | Download FFmpeg from yt-dlp/FFmpeg-Builds |
| `no_such_format` | Selected quality unavailable | "Selected quality is not available — try a lower quality" | Auto-fallback to Best |
| `unknown:{msg}` | Unhandled exception | "An unexpected error occurred: {msg}" | Check logs for details |

---

## 📄 Key Files Reference

### `app.py` — Entry Point
- Sets `os.environ["PATH"]` with `bin/` directory
- Creates single `ctk.CTk()` root
- Manages StartupCheckFrame → MainWindow transition
- Single `root.mainloop()` call

### `ui/main_window.py` — MainWindow (CTkFrame)
- **Fields:** `_url_var`, `_dir_var`, `_current_info`, `_current_save_dir`
- **Methods:** `_fetch_info()`, `_display_info()`, `_start_download()`, `_cancel_download()`, `_open_settings()`, `_open_folder()`
- **Events:** URL change → validate → enable/disable fetch button

### `ui/startup_check.py` — StartupCheckFrame (CTkFrame)
- Runs `DependencyChecker.check_all()` synchronously
- Displays results with icons (✅/❌/⚠️)
- Calls `on_done` callback on continue

### `ui/settings_dialog.py` — SettingsDialog (CTkToplevel)
- 4 tabs: General, Download, Audio, Advanced
- Reads/writes config via `ConfigManager.set()`
- File browser for save directory

### `ui/progress_widget.py` — ProgressWidget (CTkFrame)
- `CTkProgressBar` + info label + filename label
- `update_progress(d)`, `set_done()`, `set_error()`, `reset()`
- Safe percent calculation with fallback

### `ui/logs_panel.py` — LogsPanel (CTkFrame)
- Collapsible `CTkTextbox` with toggle button
- `append_log(message)`, `_clear()`
- Auto-scrolls to bottom on new log

### `ui/quality_selector.py` — QualitySelector (CTkFrame)
- Mode dropdown (video / mp4_only / audio)
- Quality dropdown (changes based on mode)
- `set_qualities(qualities)` updates available options

### `core/download_controller.py` — DownloadController
- **State:** `_queue`, `_thread`, `_stop_event`, `_after_id`
- **Methods:** `start_download()`, `cancel()`, `is_downloading()`
- **Events:** `on("progress", cb)`, `on("done", cb)`, `on("error", cb)`, `on("log", cb)`
- **Worker:** `_download_worker()` runs `YoutubeDL.download()` in thread
- **Polling:** `_poll_queue()` reads queue every 100ms via `after()`
- **Error handling:** Maps `DownloadError` → specific error IDs

### `core/format_builder.py` — Format Builder
- `FORMAT_MAP` — Quality → format string (mp4+m4a priority)
- `FORMAT_MAP_MP4` — MP4-only mode format strings
- `build_format_opts(quality, mode)` — Returns format + postprocessor opts
- `get_common_opts(bin_dir, config)` — Common options (throttledratelimit, format_sort, js_runtimes, extractor_args)

### `core/info_extractor.py` — Info Extractor
- `extract_info(url)` → sanitized info dict
- `get_available_qualities(url)` → filtered quality list
- `extract_thumbnail(info)`, `extract_title(info)`, `extract_duration(info)`, `extract_uploader(info)`

### `core/config_manager.py` — ConfigManager
- `get(key_path, default)` — Dot-notation read: `get("download.default_quality")`
- `set(key_path, value)` — Dot-notation write + auto-save
- `_merge(base, override)` — Deep merge preserving defaults
- Config file: `data/config.json`

### `core/dep_checker.py` — DependencyChecker
- `BIN_DIR` = absolute path via `Path(__file__).resolve()`
- `check_all()` → `[DepResult, ...]`
- Checks: FFmpeg, FFprobe, Node.js (optional), yt-dlp

### `utils/ui_logger.py` — UILogger
- Implements yt-dlp's logger interface (`debug`, `info`, `warning`, `error`)
- Puts all messages into a `queue.Queue` for thread-safe UI updates
- Filters `[debug]` prefixed messages

### `utils/validators.py` — URL Validators
- `is_valid_youtube_url(url)` — Regex match for youtube.com and youtu.be
- `is_playlist_url(url)` — Checks for `list=` parameter
- `extract_video_id(url)` — Extracts 11-char video ID

### `utils/file_utils.py` — File Helpers
- `ensure_dir(path)` — Creates directory if not exists
- `open_folder(path)` — Opens folder in Explorer
- `get_downloads_dir()` — Default download path
- `safe_filename(name)` — Removes invalid characters

---

## 🐛 Common Issues & Solutions

### "No supported JavaScript runtime could be found"
- **Cause:** yt-dlp-ejs not installed or node.exe not in PATH
- **Fix:** `pip install yt-dlp-ejs` and ensure `bin/node.exe` exists
- **Note:** Already handled by `app.py` adding `bin/` to PATH at startup

### "Could not copy Chrome cookie database"
- **Cause:** Chrome is open, locking the cookie database
- **Fix:** Close Chrome, or switch to "none" in Settings → Advanced → Cookies source
- **Alternative:** Export cookies.txt from extension and use file source

### "invalid command name" errors in console
- **Cause:** Multiple `CTk` instances created/destroyed (old architecture)
- **Fix:** Already resolved — now uses single-root architecture
- **Note:** If seen, ensure you're running the latest code

### Download stuck at 0% with very slow speed
- **Cause:** YouTube throttling
- **Fix:** `throttledratelimit: 102400` handles this automatically
- **Expected:** Speed will recover after re-extraction

### Format shows 398+251 instead of 136+140
- **Cause:** yt-dlp default codec preference (av01 > vp9 > avc1)
- **Fix:** `format_sort: ["vcodec:h264,vp9,av01", "res", "br"]`
- **Expected:** Should show 136+140 (avc1+m4a)

### Audio downloads as webm/opus instead of m4a
- **Cause:** Format string doesn't prioritize m4a
- **Fix:** `format: "m4a/bestaudio/best"` (already set)
- **Expected:** Downloads as .m4a (AAC) codec

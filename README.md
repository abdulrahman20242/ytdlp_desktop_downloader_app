# YT Downloader Desktop Application

**Version:** 3.0 (Sep 2026)
**Author:** ReizanTech
**Platform:** Windows 10/11 (x64)
**Language:** Python 3.11+

---

## 📋 Overview

YT Downloader is a desktop application for downloading YouTube videos, audio, and playlists with high efficiency. Built with Python, `customtkinter` for GUI, and `yt-dlp` as the core download engine.

### Key Features

- **Video Download** — up to 4K (2160p) with H.264 (avc1) preference for maximum compatibility
- **Audio Download** — MP3 (192kbps) or M4A (no re-encode, faster)
- **Format Selection** — Auto-select best format with `mp4+m4a` priority (or MP4-only mode)
- **Playlist Download** — full playlist support with per-item status and an embedded playlist panel
- **Throttling Recovery** — Automatic recovery when YouTube throttles speed
- **JavaScript Challenges** — Solved via `yt-dlp-ejs` + Node.js (included `node.exe`)
- **Cookie Support** — Browser import (Chrome/Firefox/Edge/Brave) or cookies.txt file
- **Threaded Downloads** — UI never freezes during download
- **Progress Tracking** — Real-time progress bar with speed and ETA
- **Logs Panel** — Collapsible log viewer with debug information
- **Startup Dependency Check** — Validates FFmpeg, FFprobe, Node.js, yt-dlp at launch
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
              ├── PlaylistPanel
              └── LogsPanel
```

### Layer Structure

```
┌──────────────────────────────────────────────────────────┐
│                        UI Layer                           │
│  MainWindow (CTkFrame) · SettingsDialog (CTkToplevel)     │
│  ProgressWidget · LogsPanel · QualitySelector             │
│  PlaylistPanel · StartupCheckFrame                        │
└─────────────────────┬────────────────────────────────────┘
                      │  events / callbacks via queue.Queue
┌─────────────────────▼────────────────────────────────────┐
│                  Controller Layer                         │
│  DownloadController · InfoExtractor                       │
│  ConfigManager · DependencyChecker · FormatBuilder        │
└──────┬──────────────────────────────┬────────────────────┘
       │ subprocess.Popen             │ python yt_dlp API
┌──────▼───────────────┐    ┌─────────▼─────────────┐
│  Download Engine     │    │  Info Extraction      │
│  bin/yt-dlp.exe      │    │  yt_dlp.YoutubeDL     │
│  (CLI, stdout parsed │    │  (download=False,     │
│  via regex)          │    │   no subprocess)      │
└──────┬───────────────┘    └─────────┬─────────────┘
       │                              │
┌──────▼──────────────────────────────▼──────────────┐
│   bin/ffmpeg.exe  bin/ffprobe.exe  bin/node.exe     │
└─────────────────────────────────────────────────────┘
```

**Important:** Downloads run `bin/yt-dlp.exe` as a **subprocess** (`subprocess.Popen`) and
parse its `--newline --progress` stdout with regexes. The Python `yt_dlp.YoutubeDL` API
is used **only** for extracting metadata/info (no download).

---

## 📁 Project Structure

```
yt-downloader/
│
├── app.py                     ← Entry point (PATH setup + single root CTk)
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py         ← Main window (CTkFrame) — URL input, info, controls, playlist
│   ├── settings_dialog.py     ← Settings window (CTkToplevel) — 3 tabs
│   ├── startup_check.py       ← Dependency check frame (CTkFrame)
│   ├── progress_widget.py     ← Progress bar + speed/ETA stats
│   ├── logs_panel.py          ← Collapsible log textbox
│   ├── playlist_panel.py      ← Playlist items list + download-all/selected buttons
│   └── quality_selector.py    ← Quality + mode dropdown selector
│
├── core/
│   ├── __init__.py
│   ├── config_manager.py      ← JSON config management with deep merge
│   ├── dep_checker.py         ← Binary existence + version check
│   ├── download_controller.py ← Threaded subprocess download + queue.Queue polling
│   ├── info_extractor.py      ← YouTube info extraction (Python API, no download)
│   └── format_builder.py      ← Format string builder + common opts
│
├── utils/
│   ├── __init__.py
│   ├── ui_logger.py           ← Logger → queue for thread-safe UI updates
│   ├── validators.py          ← YouTube URL/playlist regex validation
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
│   ├── node.exe               ← Node.js standalone (JS runtime for yt-dlp-ejs)
│   └── yt-dlp.exe             ← Download engine (invoked as subprocess)
│
├── data/                      ← Runtime files
│   ├── config.json            ← Auto-generated on first run
│   └── cookies.txt            ← Optional
│
├── requirements.txt
└── docx/                      ← PRDs, reference, summary, diff docs
```

Default download folder: `~/Downloads/YTDownloader` (see **config defaults** below). There is **no** `build.spec`, `data/history.json`, `data/archive.txt`, `downloads/`, or `logs/` directory — those referenced paths do not exist in the current tree.

---

## 🧩 Core Components

### app.py (Entry Point)

```python
# 1. Add bin/ to PATH before any imports
os.environ["PATH"] = str(PROJECT_ROOT / "bin") + os.pathsep + os.environ.get("PATH", "")

# 2. Create ConfigManager (loads data/config.json, falls back to defaults)

# 3. Create single persistent root CTk
root = ctk.CTk()

# 4. Show startup check as embedded frame
StartupCheckFrame(root, on_startup_done)

# 5. On continue → destroy StartupCheckFrame → create MainWindow
def on_startup_done():
    MainWindow(root, config)

# 6. Single mainloop call
root.mainloop()
```

### config_manager.py

Manages `data/config.json` with deep merge (preserves defaults for missing keys). Supports dot-notation access: `config.get("download.default_quality")`.

**Default config (from `_DEFAULTS` in `core/config_manager.py`):**
```json
{
  "version": "1.0",
  "ui": { "theme": "dark", "language": "ar", "window_width": 800, "window_height": 600 },
  "download": {
    "default_dir": "<home>/Downloads/YTDownloader",
    "default_quality": "1080p",
    "default_mode": "video",
    "concurrent_fragments": 4,
    "retries": 10,
    "merge_output_format": "mp4"
  },
  "cookies": { "source": "none", "browser": "chrome", "file_path": "data/cookies.txt" },
  "advanced": {
    "show_debug_logs": false,
    "sponsorblock_remove": false,
    "sponsorblock_categories": ["sponsor"]
  }
}
```

> Note: older `data/config.json` files may carry extra keys (e.g. `audio.*`, `download.embed_*`,
> `advanced.ffmpeg_location`, `advanced.node_path`, `advanced.use_nightly_yt_dlp`). These are
> **not** part of the code defaults and are ignored. There is **no** `audio.*` settings section.

### download_controller.py

Threaded download engine. Downloads run `bin/yt-dlp.exe` as a subprocess; stdout is parsed
line-by-line for `[download] N%`, speed, and ETA.

- **`start_download(url, opts, save_dir)`** — spawns `_download_worker` (single video)
- **`start_playlist_download(entries, opts, save_dir)`** — spawns `_playlist_worker` (maps each playlist entry → `_run_single`)
- **`_run_single()`** — runs `subprocess.Popen([bin/yt-dlp.exe, ...argv])`, parses stdout (progress/destination/ERROR/WARNING), returns `"ok"`, `"cancelled"`, or an error ID
- **`cancel()`** — sets stop event (terminates the running process)
- **`on(event, callback)`** — `progress`, `done`, `error`, `log`, `playlist_item`, `playlist_done`
- **`_poll_queue()`** — called every 100ms via `after()` to read events from queue

**Error classification (`_classify_error`):**
| Condition | Result |
|---|---|
| Age restricted | `age_restricted` |
| "Video unavailable" | `unavailable` |
| Rate limited / 429 | `rate_limited` |
| Cookie browser failure | Arabic message: "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات" |
| Unsupported URL (`UnsupportedError`) | `unsupported_url` |
| Other extractor error | `extractor:{msg}` |
| Download error | `download_error:{msg}` |
| Process could not start | `unknown:{exc}` |

### format_builder.py

Builds format strings and common opts for yt-dlp.

**`build_format_opts(quality, mode, config=None)` — modes:**
| Mode | Behavior |
|---|---|
| `video` | `FORMAT_MAP` + `merge_output_format` (default `mp4`) |
| `mp4_only` | `FORMAT_MAP_MP4` (stricter mp4 fallback chain) |
| `audio` | `FORMAT_MAP["mp3"|"m4a"]` + audio postprocessors + `writethumbnail` |

**Format priority (video):** `mp4+m4a` first → any video+audio → combined fallback

**Format map (`FORMAT_MAP`):**
| Quality | Format String |
|---|---|
| Best | `bv[ext=mp4]+ba[ext=m4a]/bv+ba/b` |
| 2160p | `bv[height<=2160][ext=mp4]+ba[ext=m4a]/bv[height<=2160]+ba/b[height<=2160]` |
| 1440p | `bv[height<=1440][ext=mp4]+ba[ext=m4a]/bv[height<=1440]+ba/b[height<=1440]` |
| 1080p | `bv[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]` |
| 720p | `bv[height<=720][ext=mp4]+ba[ext=m4a]/bv[height<=720]+ba/b[height<=720]` |
| 480p | `bv[height<=480][ext=mp4]+ba[ext=m4a]/bv[height<=480]+ba/b[height<=480]` |
| 360p | `bv[height<=360][ext=mp4]+ba[ext=m4a]/bv[height<=360]+ba/b[height<=360]` |
| MP3 / M4A | `m4a/bestaudio/best` |

**MP4-only map (`FORMAT_MAP_MP4`):**
| Quality | Format String |
|---|---|
| Best | `bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b` |
| Np | `bv[height<=N][ext=mp4]+ba[ext=m4a]/b[height<=N]` |

**Audio postprocessors (`_audio_postprocessors`):**
- MP3: `FFmpegExtractAudio` (preferredcodec `mp3`, quality `192`) + `FFmpegMetadata` + `EmbedThumbnail`
- M4A: `FFmpegMetadata` + `EmbedThumbnail` (no re-encode)

**`get_common_opts(bin_dir, config)` — base options:**
```python
{
    "ffmpeg_location": str(bin_path),          # also prepends bin/ to PATH
    "concurrent_fragments": config.get("download.concurrent_fragments", 4),
    "retries": 10,                             # and fragment_retries
    "throttledratelimit": 102400,              # 100 KB/s — triggers re-extraction
    "format_sort": ["vcodec:h264,vp9,av01", "res", "br"],  # H.264 > VP9 > AV01
    "ignoreerrors": False,
    "quiet": False,                            # progress line is parsed from stdout
    "no_warnings": True,
    "verbose": config advanced.show_debug_logs,
    "noplaylist": True,                        # never pull a playlist from a video link
    "js_runtimes": {"node": {}},               # map to node:{bin}/node.exe in argv
    "extractor_args": {"youtube-ejs": {}},     # yt-dlp-ejs plugin
}
```

### dep_checker.py

Checks for required binaries using absolute paths (`Path(__file__).resolve().parent.parent / "bin"`).

| Dependency | Required | Check Method |
|---|---|---|
| FFmpeg | ✅ Yes | `bin/ffmpeg.exe` → `--version` |
| FFprobe | ✅ Yes | `bin/ffprobe.exe` → `--version` |
| Node.js | ⚠️ Optional | `bin/node.exe` (or in PATH) → `--version` |
| yt-dlp | ✅ Yes | `import yt_dlp` → `yt_dlp.version.__version__` |

### info_extractor.py

Extracts video metadata using the **Python** `yt_dlp.YoutubeDL` API (`download=False`).
Used for thumbnail preview, quality detection, and info display.

- `extract_info(url)`, `extract_playlist(url)` — metadata (no download)
- `get_available_qualities(url)` → `["Best", ...]` filtered from available heights
- `extract_thumbnail / extract_title / extract_duration / extract_uploader`

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

> `yt-dlp-ejs` is a yt-dlp **plugin** (not a Python import). It is enabled at download time
> via `--extractor-args youtube-ejs` plus `--js-runtimes node:<bin>/node.exe`.

### Binaries (in `bin/`)

| File | Source | Purpose |
|---|---|---|
| `ffmpeg.exe` | yt-dlp/FFmpeg-Builds | Video/audio merging |
| `ffprobe.exe` | yt-dlp/FFmpeg-Builds | Media probing |
| `node.exe` | Node.js standalone | JavaScript runtime for yt-dlp-ejs |
| `yt-dlp.exe` | yt-dlp releases | **Download engine** (invoked as subprocess) |

---

## 🚀 Usage

1. Run `python app.py`
2. Startup check validates dependencies → click **Continue** ("متابعة")
3. Paste a YouTube URL in the input field (video or playlist)
4. Click **Fetch** to get video info (title, thumbnail, qualities, duration, uploader)
5. Select mode (**Video / MP4 Only / Audio**) and quality (**Best / 2160p / 1440p / 1080p / 720p / 480p / 360p**, or **MP3 / M4A** for audio)
6. Choose save folder (default: `~/Downloads/YTDownloader`)
7. Click **⬇ Download** — playlists download into a per-playlist folder and populate the playlist panel
8. Monitor progress bar, speed, ETA, and logs
9. Click **📂 Open Folder** to open the download location

### Settings (⚙ الإعدادات)

| Tab | Options |
|---|---|
| عام (General) | Theme (dark/light/system), Language (ar/en), Save folder |
| التحميل (Download) | Default quality, Default mode (video/mp4_only/audio), Concurrent fragments, Retries |
| متقدم (Advanced) | Cookies source (none/browser/file), Browser selection, Debug logs, SponsorBlock removal |

---

## 📦 Building EXE

A PyInstaller spec (`build.spec`) is **not yet present** in the repository. Until it is added,
run the app from source (`python app.py`). Planned packaging approach: PyInstaller `--onedir`
(target `dist/YTDownloader/YTDownloader.exe`).

---

## ⚙️ yt-dlp Configuration

### PATH Configuration

`app.py` adds `bin/` to `PATH` **before any imports** to ensure yt-dlp-ejs finds `node.exe` at load time. `get_common_opts()` also ensures `bin/` is on PATH for the subprocess.

### CLI Flags Emitted by `_build_argv`

Downloads invoke `bin/yt-dlp.exe` with flags built from the opts dict, including:
`-f <format>`, `-x --audio-format/--audio-quality` (audio), `--add-metadata`,
`--embed-thumbnail`, `--write-thumbnail`, `--merge-output-format mp4`,
`--no-playlist`, `--ffmpeg-location`, `--concurrent-fragments`, `--retries`,
`--fragment-retries`, `--throttled-rate`, `--format-sort`, `--js-runtimes node:<bin>/node.exe`,
`--extractor-args youtube-ejs`, `--cookies` / `--cookies-from-browser`,
`--sponsorblock-remove`, `-o "<save_dir>/%(title)s [%(id)s].%(ext)s"`,
`--newline --progress`, plus `--quiet`, `--no-warnings`, `--verbose` as configured.

---

## 📊 Status

| Feature | Status |
|---|---|
| Format selection (H.264 + m4a priority) | ✅ |
| Audio download (MP3/M4A) | ✅ |
| Playlist download | ✅ |
| Throttling recovery | ✅ |
| Node.js JS challenges (yt-dlp-ejs) | ✅ |
| Cookie support (browser/file) | ✅ |
| Thumbnail preview | ✅ |
| Settings dialog | ✅ |
| Startup dependency check | ✅ |
| SponsorBlock removal (optional) | ✅ |
| Queue system (multiple concurrent downloads) | 🚧 Future |

---

## 🔄 Changes from PRD (Before vs After)

### Architecture

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Window Architecture** | `StartupCheckDialog` as `CTkToplevel` + `MainWindow` as separate `CTk` | **Single-Root:** One `CTk` root, all screens are `CTkFrame` |
| **Startup Check** | `StartupCheckDialog(CTkToplevel)` with threading + `after()` | `StartupCheckFrame(CTkFrame)` synchronous checks |
| **MainWindow** | `class MainWindow(ctk.CTk)` | `class MainWindow(ctk.CTkFrame)` — embedded in root |
| **Separator Widget** | `ctk.CTkSeparator` (not available in 5.2.2) | `tk.Frame(height=1, bg="#555")` |

### Download Engine

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Engine** | yt-dlp Python API (`YoutubeDL.download()`) | **Subprocess** `bin/yt-dlp.exe` + stdout regex parsing |
| **Status Feed** | `progress_hooks` / `logger` objects | `--newline --progress` stdout lines parsed with `_PROGRESS_RE` / `_SPEED_RE` / `_ETA_RE` |
| **Playlist** | 🚧 Future | `_playlist_worker` + `playlist_item` / `playlist_done` events + PlaylistPanel |

### Cookie Handling

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Default Source** | `"file"` | `"none"` (avoids Chrome lock errors) |
| **Error Handling** | Not specified | Arabic error message with fix instructions |

### Format Selection

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **Format Map** | `bv*+ba/b` (no mp4 preference) | `bv[ext=mp4]+ba[ext=m4a]/bv+ba/b` (+ `FORMAT_MAP_MP4`) |
| **Codec Priority** | yt-dlp default (av01 > vp9 > avc1) | `format_sort: ["vcodec:h264,vp9,av01", "res", "br"]` |
| **Throttling** | Not specified | `throttledratelimit: 102400` |
| **Result** | `398+251` (av01+opus) | `136+140` (avc1+m4a) ✅ |

### yt-dlp-ejs Integration

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **JS Runtime** | Only `extractor_args` with `android_vr` client | `js_runtimes: {"node": {}}` + `extractor_args: {"youtube-ejs": {}}` |
| **PATH Setup** | In `get_common_opts` (too late) | In `app.py` before all imports |
| **requirements.txt** | Not listed | `yt-dlp-ejs>=0.8.0` |

### Dependency Checker

| Aspect | PRD (Before) | Implementation (After) |
|---|---|---|
| **BIN_DIR** | `Path("bin")` (relative to CWD) | `Path(__file__).resolve().parent.parent / "bin"` (absolute) |
| **FFprobe** | Not checked | Added `_check_ffprobe()` |
| **Node.js Required** | `required=True` | `required=False` (optional) |

---

## 🧵 Threading Model

```
Main Thread (UI)                    Worker Thread (downloader)
─────────────────                   ──────────────────────────
      │                                      │
      │  start_download(url, opts) /         │
      │  start_playlist_download(...)        │
      │ ──────────────────────────────────►  │
      │  _poll_queue() ◄── every 100ms ──┐   │
      │      │                           │   │
      │      ├── progress ──► update UI  │   │
      │      ├── log ──────► append log  │   │
      │      ├── done ─────► on_success  │   │
      │      ├── error ────► on_error    │   │
      │      ├── playlist_item ─► panel  │   │
      │      └── playlist_done ──► final │   │
      │                                  │   │
      │  cancel()            (terminates  │
      │ ───────────────►  the subprocess) │
```

### Communication Pattern

The UI thread and worker thread communicate through a **thread-safe `queue.Queue`**:

```python
# In worker thread (DownloadController._run_single):
self._queue.put(("progress", prog))     # parsed [download] N%
self._queue.put(("log", f"[INFO] {line}"))
self._queue.put(("done", None))         # single video finished
self._queue.put(("error", result))      # classified error ID

# Playlist worker:
self._queue.put(("playlist_item", {...}))
self._queue.put(("playlist_done", None))

# In UI thread (polled every 100ms): _poll_queue → dispatch per event
```

### Thread Safety Rules

1. **UI updates** only in main thread (via `_poll_queue`)
2. **yt-dlp calls** run as a **subprocess** in the worker thread
3. **Queue** is the only shared mutable state (thread-safe by design)
4. **Stop event** (`threading.Event`) for cancellation; `proc.terminate()` ends the subprocess

---

## 🔄 Download Flow (Detailed)

```
1. User pastes URL (video or playlist)
       │
2. Validate URL (regex check)
       │
3. User clicks "Fetch Info"
       │
4. InfoExtractor.extract_info(url)  [Python yt_dlp API, download=False]
   ├── Extracts: title, thumbnail, duration, uploader, formats
   └── get_available_qualities() → ["Best", ...]
       │
5. Display info in UI (title, thumbnail, channel, duration, qualities)
       │
6. User clicks "⬇ Download"
       │
7. Build opts
   ├── get_common_opts() → base options (incl. youtube-ejs extractor args)
   ├── build_format_opts() → format + postprocessors (or audio PPs)
   ├── Add cookies if configured
   └── Add sponsorblock if configured
       │
8. DownloadController.start_download() / start_playlist_download()
   ├── Creates daemon thread (worker)
   ├── _build_argv() → CLI flags
   └── subprocess.Popen([bin/yt-dlp.exe, ...argv])
       │
9. Worker parses stdout lines:
   ├── [download] N% → progress event
   ├── Destination → filename
   ├── ERROR: / WARNING: / [info] → log events
   ├── FFmpeg merges video + audio → <title> [<id>].mp4
   └── Metadata + thumbnail embedding post-processors
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

Error IDs produced by `DownloadController._classify_error` / `_run_single`:

| Error ID | Cause | Guidance |
|---|---|---|
| `age_restricted` | Video requires age verification ("Sign in to confirm your age") | Enable cookies in settings |
| `unavailable` | Video deleted/private ("Video unavailable") | Check URL, try another video |
| `rate_limited` | Too many requests (HTTP 429) | Wait before retrying |
| cookie browser failure | Chrome open / DB locked | "أغلق المتصفح أو استخدم ملف cookies في الإعدادات" — close browser or use cookies file |
| `unsupported_url` | Non-YouTube or invalid URL | Check URL format |
| `extractor:{msg}` | YouTube API changed / extraction error | Update `yt-dlp` / `yt-dlp-ejs` |
| `download_error:{msg}` | Other yt-dlp non-zero exit | Check logs for details |
| `unknown:{exc}` | Process could not be started | See exception text |
| `cancelled` | User cancelled | — |

---

## 📄 Key Files Reference

### `app.py` — Entry Point
- Sets `os.environ["PATH"]` with `bin/` directory
- Creates `ConfigManager`, single `ctk.CTk()` root
- Manages StartupCheckFrame → MainWindow transition
- Single `root.mainloop()` call

### `ui/main_window.py` — MainWindow (CTkFrame)
- **Fields:** `_url_var`, `_dir_var`, `_current_info`, `_current_save_dir`, config
- **Methods:** `_fetch_info()`, `_display_info()`, `_start_download()`, `_start_playlist_download()`, `_cancel_download()`, `_open_settings()`, `_open_folder()`
- **Events:** URL change → validate → enable/disable Fetch button; `playlist_item` / `playlist_done` → PlaylistPanel updates
- **Layout:** `_PLAYLIST_ROW = 2` (weight 2, min 244px), `_LOGS_ROW = 9`; playlist/logs rows collapse when not needed

### `ui/playlist_panel.py` — PlaylistPanel (CTkFrame)
- Per-item status list, **Download All** and **Download Selected** buttons
- Update methods driven by `playlist_item` events (state: waiting/downloading/done/error)

### `ui/startup_check.py` — StartupCheckFrame (CTkFrame)
- Runs `DependencyChecker.check_all()` synchronously
- Displays results with icons (✅/❌/⚠️)
- Calls `on_done` callback on continue

### `ui/settings_dialog.py` — SettingsDialog (CTkToplevel)
- 3 tabs: عام (General), التحميل (Download), متقدم (Advanced)
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
- Mode dropdown (`video` / `mp4_only` / `audio`) — `MODE_OPTIONS`
- Quality dropdown (`Best/2160p/1440p/1080p/720p/480p/360p`, or `MP3/M4A` for audio)
- `set_qualities()`, `apply_defaults(mode, default_quality)` via `resolve_initial_selection`

### `core/download_controller.py` — DownloadController
- **State:** `_queue`, `_thread`, `_stop_event`, `_proc`, callbacks dict
- **Methods:** `start_download()`, `start_playlist_download()`, `cancel()`, `is_downloading()`, `set_app()`
- **Events:** `on("progress", cb)`, `on("done", cb)`, `on("error", cb)`, `on("log", cb)`, `on("playlist_item", cb)`, `on("playlist_done", cb)`
- **Workers:** `_download_worker()`, `_playlist_worker()` (both call `_run_single()`)
- **Parsing:** `_build_argv()`, `_run_single()` (Popen + stdout loop), `_parse_progress()`, `_parse_destination()`, `_classify_error()`, `_strip_ansi()`, `_strip_ytdlp_report_suffix()`

### `core/format_builder.py` — Format Builder
- `QUALITY_OPTIONS`, `MODE_OPTIONS` (exported; used by the UI)
- `FORMAT_MAP`, `FORMAT_MAP_MP4`, `_audio_postprocessors()`
- `build_format_opts(quality, mode, config=None)`, `get_common_opts(bin_dir, config)`

### `core/info_extractor.py` — Info Extractor
- `extract_info(url)`, `extract_playlist(url)` → sanitized info dicts
- `get_available_qualities(url)` → `["Best", ...]`
- `extract_thumbnail(info)`, `extract_title(info)`, `extract_duration(info)`, `extract_uploader(info)`

### `core/config_manager.py` — ConfigManager
- `get(key_path, default)`, `set(key_path, value)` — dot-notation + auto-save
- `reset_to_defaults()`, `_merge(base, override)` — deep merge preserving defaults
- Config file: `data/config.json`

### `core/dep_checker.py` — DependencyChecker
- `BIN_DIR` = absolute path via `Path(__file__).resolve().parent.parent / "bin"`
- `check_all()` → `[DepResult, ...]`; checks FFmpeg, FFprobe, Node.js (optional), yt-dlp

### `utils/ui_logger.py` — UILogger
- Implements yt-dlp's logger interface (`debug`, `info`, `warning`, `error`)
- Puts all messages into a `queue.Queue` for thread-safe UI updates
- Filters `[debug]` prefixed messages

### `utils/validators.py` — URL Validators
- `is_valid_youtube_url(url)`, `extract_video_id(url)` — 11-char ID regex
- `is_playlist_url(url)`, `is_explicit_playlist_url(url)`, `classify_url(url)` — playlist detection

### `utils/file_utils.py` — File Helpers
- `ensure_dir(path)`, `open_folder(path)`, `get_downloads_dir()`
- `safe_filename(name)`, `sanitize_folder_name(name, fallback="Playlist")` — playlist folder naming

---

## 🐛 Common Issues & Solutions

### "No supported JavaScript runtime could be found"
- **Cause:** yt-dlp-ejs not installed or node.exe not found
- **Fix:** `pip install yt-dlp-ejs` and ensure `bin/node.exe` exists
- **Note:** Already handled by `app.py` adding `bin/` to PATH at startup

### "Could not copy Chrome cookie database"
- **Cause:** Chrome is open, locking the cookie database
- **Fix:** Close Chrome, or switch to "none" in Settings → متقدم (Advanced) → Cookies source
- **Alternative:** Export cookies.txt from an extension and use file source

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
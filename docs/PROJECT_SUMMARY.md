# YT Downloader — Project Summary

**Version:** 3.0 | **Platform:** Windows 10/11 | **Language:** Python 3.11+

---

## Overview

Desktop application for downloading YouTube videos, audio, and playlists with an Arabic GUI. Uses `customtkinter` for the interface. The **download engine is `bin/yt-dlp.exe` launched as a subprocess** (stdout parsed via regex); the Python `yt_dlp.YoutubeDL` API is used **only** for extracting video info (`download=False`).

---

## Project Structure

```
ytdlp_desktop_downloader_app/
│
├── app.py                     ← Entry point (PATH setup + single CTk root)
├── requirements.txt           ← Python dependencies
│
├── core/                      ← Core logic
│   ├── config_manager.py      ← Config management (config.json, deep merge)
│   ├── dep_checker.py         ← Dependency checking (4 checks)
│   ├── download_controller.py ← Download control (subprocess) + threading
│   ├── format_builder.py      ← Format strings + opts (FORMAT_MAP/MP4)
│   └── info_extractor.py      ← Video info extraction (Python API)
│
├── ui/                        ← User interface
│   ├── main_window.py         ← Main window (single CTk root, playlist wiring)
│   ├── settings_dialog.py     ← Settings window (3 tabs)
│   ├── startup_check.py       ← Dependency check at startup
│   ├── progress_widget.py     ← Progress bar (percent/speed/ETA)
│   ├── logs_panel.py          ← Collapsible log panel
│   ├── playlist_panel.py      ← Playlist list + download-all/selected
│   └── quality_selector.py    ← Quality/mode selector
│
├── utils/                     ← Utilities
│   ├── ui_logger.py           ← yt-dlp logger → queue → UI
│   ├── validators.py          ← URL + playlist validation/classification
│   └── file_utils.py          ← File operations + playlist folder names
│
├── bin/                       ← Binaries
│   ├── ffmpeg.exe             ← Video/audio muxing
│   ├── ffprobe.exe            ← Media probing
│   ├── node.exe               ← Node.js for JS challenges (yt-dlp-ejs)
│   └── yt-dlp.exe             ← Download engine (subprocess)
│
├── data/                      ← Runtime data
│   ├── config.json            ← Settings file
│   └── cookies.txt            ← Cookie file (optional)
│
└── docx/                      ← Documentation
    ├── README.md              ← User guide (mirror of root README)
    ├── PROJECT_REFERENCE.md   ← Full technical reference
    ├── PRD_DIFF.md            ← PRD v1/v2 vs v3 implementation diff
    ├── PRD_YTDownloader_v2.md ← Historical PRD v2 (superseded)
    ├── PRD_YTDownloader_v2 - نسخة قديمة.md ← Historical (superseded)
    ├── PRD_YTDownloader_v3.md ← Current PRD
    └── PROJECT_SUMMARY.md     ← This file
```

> Default download folder: `~/Downloads/YTDownloader`. There is **no** `build.spec`,
> `downloads/`, `logs/`, `data/history.json`, or `data/archive.txt` in the current tree.

---

## Tech Stack

| Component | Technology |
|---|---|
| GUI Framework | customtkinter 5.x |
| Download Engine | `bin/yt-dlp.exe` (subprocess, stdout regex parsing) |
| Info Extraction | yt-dlp Python API (`yt_dlp.YoutubeDL`, no download) |
| JS Challenge Solver | yt-dlp-ejs plugin + Node.js (`bin/node.exe`) |
| Media Processing | FFmpeg + FFprobe |
| Packaging | PyInstaller (planned `--onedir`; no spec yet) |

---

## Data Flow

### 1. Startup
```
app.py
  │
  ├── 1. Append bin/ to PATH (for node.exe discovery)
  ├── 2. Load config from data/config.json
  ├── 3. Create single CTk window (800×600)
  ├── 4. Show dependency check screen
  │      ├── ✅ yt-dlp       (bin/yt-dlp.exe --version)
  │      ├── ✅ FFmpeg       (bin/ffmpeg.exe --version)
  │      ├── ✅ FFprobe      (bin/ffprobe.exe --version)
  │      └── ⚠️ Node.js      (optional — bin/node.exe or PATH)
  ├── 5. User clicks "متابعة"
  └── 6. Create MainWindow → mainloop()
```

### 2. Download Flow
```
[Paste URL] → [Fetch] → [Select quality/mode] → [⬇ Download]
                                                   │
                                             [Worker Thread]
                                                   │
                  subprocess.Popen([bin/yt-dlp.exe, ...argv])  --newline --progress
                  │
                  stdout parsed line-by-line:
                  [download] N% → progress  ·  ERROR:/WARNING: → log  ·  ERROR: → error
                  │
                  FFmpeg muxes video+audio → <title> [<id>].mp4
                  │
                                            [Download complete]
```

### 3. Playlist Flow
```
[Playlist URL] → classify_url() → extract_playlist() (no download)
      → PlaylistPanel lists items → "تنزيل الكل" / "تنزيل المحدد"
      → start_playlist_download(entries, opts, save_dir)
      → _playlist_worker runs _run_single() per item (per-playlist subfolder)
      → playlist_item events update status per row → playlist_done
```

### 4. Threading Model
```
Main Thread (UI)                      Worker Thread
      │                                        │
      │  start_download() /                    │
      │  start_playlist_download()             │
      │ ───────────────────────────────────────►│
      │                                        │  subprocess.Popen(yt-dlp.exe)
      │  _poll_queue() ← every 100ms ──────────│  stdout → events
      │      │                                 │
      │      ├── progress → ProgressBar        │
      │      ├── log → LogsPanel               │
      │      ├── done → "Download Complete"    │
      │      ├── error → classified error      │
      │      ├── playlist_item → PlaylistPanel │
      │      └── playlist_done → final state   │
      │                                        │
      │  cancel() → stop_event                 │
      │            → proc.terminate()          │
```

---

## Key Decisions vs PRD

### 1. Download Engine (v3 — core change)
**v2 PRD:** `YoutubeDL.download()` via Python API
**v3 actual:** `bin/yt-dlp.exe` **subprocess** + regex stdout parsing (`download_controller._run_single`)
Python API remains only for **info extraction** (`info_extractor`).

### 2. Single-Root Architecture
**Before:** Two `CTk` windows → orphaned `after` callbacks → `invalid command name` errors
**After:** One `CTk` root + `CTkFrame` screens → no errors

### 3. H.264 Preference
**Before:** `398+251` (av01+opus) — limited compatibility
**After:** `136+140` (avc1+m4a) — widest compatibility ✅

### 4. Throttling Recovery
**Before:** Downloads stall at 90%+ with 30min+ ETA
**After:** Auto-recovery when speed drops below 100KB/s (`throttledratelimit: 102400`)

### 5. Playlist Download
**v2 PRD:** 🚧 Future
**v3 actual:** ✅ Implemented (`_playlist_worker` + `PlaylistPanel` + per-item status events)

### 6. Config File (actual `_DEFAULTS`)
```json
{
  "ui": { "theme": "dark", "language": "ar", "window_width": 800, "window_height": 600 },
  "download": { "default_quality": "1080p", "default_mode": "video",
                "concurrent_fragments": 4, "retries": 10, "merge_output_format": "mp4" },
  "cookies": { "source": "none", "browser": "chrome", "file_path": "data/cookies.txt" },
  "advanced": { "show_debug_logs": false, "sponsorblock_remove": false }
}
```
No `audio.*` section. Cookies disabled by default (`source: none`) to avoid Chrome DB lock errors.

### 7. Settings Dialog
**Before:** 4 tabs (incl. Audio)
**After:** **3 tabs** — عام (General), التحميل (Download), متقدم (Advanced). Audio format
(MP3/M4A) is chosen in the main window's quality selector, not in settings.

---

## How to Run

```powershell
pip install -r requirements.txt
python app.py
```

## Build EXE

Not yet possible — `build.spec` is not present in the repository. Run from source until
the PyInstaller `--onedir` packaging config is added.

---

## Completed Features

| Feature | Status |
|---|---|
| Video download up to 4K (+ MP4-only mode) | ✅ |
| Audio download MP3/M4A | ✅ |
| Playlist download (all/selected) | ✅ |
| Quality and mode selection | ✅ |
| Progress bar with speed + ETA | ✅ |
| Log panel | ✅ |
| Thumbnail preview + video info panel | ✅ |
| Cookie support (browser/file) | ✅ |
| Dependency checking (4 checks) | ✅ |
| Settings dialog (3 tabs) | ✅ |
| Arabic interface | ✅ |
| Throttling auto-recovery | ✅ |
| H.264 preference | ✅ |
| Node.js JS challenge solving (yt-dlp-ejs) | ✅ |
| SponsorBlock (optional) | ✅ |

## Future Features

| Feature | Status |
|---|---|
| Queue system (multiple concurrent downloads) | 🚧 |
| Auto-subtitling | 🚧 |
| Download history (history.json) | 🚧 |
| yt-dlp auto-update | 🚧 |
| PyInstaller build.spec + build script | 🚧 |

---

## docx/ Files

| File | Description |
|---|---|
| `README.md` | User & developer guide (mirror of root README) |
| `PROJECT_REFERENCE.md` | Full technical reference (all functions, settings, data flow, threading model, error catalog) |
| `PRD_DIFF.md` | PRD v1/v2 vs v3 implementation comparison |
| `PRD_YTDownloader_v2.md` | Historical PRD v2 (superseded by v3) |
| `PRD_YTDownloader_v2 - نسخة قديمة.md` | Historical, archived (superseded) |
| `PRD_YTDownloader_v3.md` | Current PRD (matches implementation) |
| `PROJECT_SUMMARY.md` | This file — concise project summary |
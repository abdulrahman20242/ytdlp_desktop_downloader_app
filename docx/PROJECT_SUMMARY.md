# YT Downloader — Project Summary

**Version:** 2.0 | **Platform:** Windows 10/11 | **Language:** Python 3.11+

---

## Overview

Desktop application for downloading YouTube videos and audio with an Arabic GUI. Uses `yt-dlp` via its Python API (not subprocess) with `customtkinter` for the interface.

---

## Project Structure

```
ytdlp_desktop_downloader_app/
│
├── app.py                     ← Entry point
├── build.spec                 ← PyInstaller spec
├── requirements.txt           ← Python dependencies
│
├── core/                      ← Core logic
│   ├── config_manager.py      ← Config management (config.json)
│   ├── dep_checker.py         ← Dependency checking
│   ├── download_controller.py ← Download control + threading
│   ├── format_builder.py      ← Format strings + opts
│   └── info_extractor.py      ← Video info extraction
│
├── ui/                        ← User interface
│   ├── main_window.py         ← Main window
│   ├── settings_dialog.py     ← Settings window
│   ├── startup_check.py       ← Dependency check at startup
│   ├── progress_widget.py     ← Progress bar
│   ├── logs_panel.py          ← Collapsible log panel
│   └── quality_selector.py    ← Quality/mode selector
│
├── utils/                     ← Utilities
│   ├── ui_logger.py           ← yt-dlp logger → queue → UI
│   ├── validators.py          ← URL validation
│   └── file_utils.py          ← File operations
│
├── bin/                       ← Binaries
│   ├── ffmpeg.exe             ← Video/audio muxing
│   ├── ffprobe.exe            ← Media probing
│   ├── node.exe               ← Node.js for JS challenges
│   └── yt-dlp.exe             ← For auto-update
│
├── data/                      ← Runtime data
│   ├── config.json            ← Settings file
│   └── cookies.txt            ← Cookie file (optional)
│
├── downloads/                 ← Default download directory
├── logs/                      ← Application logs
│
└── docx/                      ← Documentation
    ├── README.md              ← User guide
    ├── PROJECT_REFERENCE.md   ← Full technical reference
    ├── PRD_DIFF.md            ← PRD vs implementation diff
    └── PROJECT_SUMMARY.md     ← This file
```

---

## Tech Stack

| Component | Technology |
|---|---|
| GUI Framework | customtkinter 5.x |
| Download Engine | yt-dlp (Python API) |
| JS Challenge Solver | yt-dlp-ejs + Node.js |
| Media Processing | FFmpeg + FFprobe |
| Packaging | PyInstaller (--onedir) |

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
  │      ├── ✅ yt-dlp
  │      ├── ✅ FFmpeg
  │      ├── ✅ FFprobe
  │      └── ⚠️ Node.js (optional)
  ├── 5. User clicks "Continue"
  └── 6. Create MainWindow → mainloop()
```

### 2. Download Flow
```
[Paste URL] → [Query] → [Select quality] → [⬇ Download]
                                               │
                                         [Background Thread]
                                               │
                                     yt-dlp downloads video
                                     + yt-dlp-ejs solves JS challenges
                                     + FFmpeg muxes video+audio
                                               │
                                         [Download complete]
```

### 3. Threading Model
```
Main Thread (UI)                      Download Thread (yt-dlp)
      │                                        │
      │  start_download()                      │
      │ ───────────────────────────────────────►│
      │                                        │
      │  _poll_queue() ← every 100ms ──────────│  progress_hook → queue
      │      │                                 │  logger → queue
      │      ├── progress → ProgressBar        │
      │      ├── log → LogsPanel               │
      │      ├── done → "Download Complete"    │
      │      └── error → error message         │
```

---

## Key Decisions vs PRD

### 1. Single-Root Architecture
**Before:** Two `CTk` windows → orphaned `after` callbacks → `invalid command name` errors
**After:** One `CTk` root + `CTkFrame` screens → no errors

### 2. H.264 Preference
**Before:** `398+251` (av01+opus) — limited compatibility
**After:** `136+140` (avc1+m4a) — widest compatibility ✅

### 3. Throttling Recovery
**Before:** Downloads stall at 90%+ with 30min+ ETA
**After:** Auto-recovery when speed drops below 100KB/s

### 4. yt-dlp-ejs Enablement
**Before:** Only android_vr fallback with warnings
**After:** Node.js officially configured + android_vr as fallback

### 5. Config File
```json
{
  "ui": { "theme": "dark", "language": "ar" },
  "download": { "default_quality": "1080p", "default_mode": "video" },
  "audio": { "default_format": "mp3" },
  "cookies": { "source": "none" }
}
```
Cookies disabled by default (`source: none`) to avoid Chrome DB lock errors.

---

## How to Run

```powershell
pip install -r requirements.txt
python app.py
```

## Build EXE

```powershell
pip install pyinstaller
pyinstaller build.spec --clean
# Output: dist/YTDownloader/YTDownloader.exe
```

---

## Completed Features

| Feature | Status |
|---|---|
| Video download up to 4K | ✅ |
| Audio download MP3/M4A | ✅ |
| Quality and mode selection | ✅ |
| Progress bar with speed + ETA | ✅ |
| Log panel | ✅ |
| Thumbnail preview | ✅ |
| Cookie support | ✅ |
| Dependency checking | ✅ |
| Settings dialog (4 tabs) | ✅ |
| Arabic interface | ✅ |
| Throttling auto-recovery | ✅ |
| H.264 preference | ✅ |
| Node.js JS challenge solving | ✅ |

## Future Features

| Feature | Status |
|---|---|
| Playlist download | 🚧 |
| Queue system | 🚧 |
| Auto-subtitling | 🚧 |
| SponsorBlock integration | 🚧 |
| yt-dlp auto-update | 🚧 |

---

## docx/ Files

| File | Description |
|---|---|
| `README.md` | User & developer guide |
| `PROJECT_REFERENCE.md` | Full technical reference (all functions, settings, data flow, threading model, error catalog) |
| `PRD_DIFF.md` | PRD vs actual implementation comparison |
| `PROJECT_SUMMARY.md` | This file — concise project summary |

# PRD Diff — YT Downloader v3.0

## What Changed Between PRD (design intent) and Actual Implementation

**Compared against:** `PRD_YTDownloader_v2.md` (design, May 2026) → current implementation (Sep 2026).
For the corrected spec see `PRD_YTDownloader_v3.md`.

---

## 1. Architecture — Single-Root Window

### Before (PRD):
```
app.py
├── ctk.CTk() [splash screen]
│   └── StartupCheckDialog (CTkToplevel) → show() → destroy()
└── ctk.CTk() [main window]
    └── MainWindow (ctk.CTk) → mainloop()
```

**Problem:** Two separate `CTk` windows. When the first is `destroy()`ed, customtkinter's internal `after` callbacks remain pending → `invalid command name` errors in console, occasional freezing.

### After (Implementation):
```
app.py
└── ctk.CTk() [single persistent root]
    ├── StartupCheckFrame (CTkFrame) → _on_continue() → destroys self
    └── MainWindow (CTkFrame) → embedded in same root → mainloop()
```

**Fix:** Single `CTk` root. Both startup check and main window are `CTkFrame` subclasses in the same root.

### Files changed:
- `app.py` — complete rewrite
- `ui/main_window.py` — `class MainWindow(ctk.CTk)` → `class MainWindow(ctk.CTkFrame)`
- `ui/startup_check.py` — Toplevel dialog → embedded `CTkFrame`

---

## 2. CustomTkinter CTkSeparator

### Before (PRD):
```python
sep = ctk.CTkSeparator(main_frame, orientation="horizontal")
```

### After (Implementation):
```python
sep = tk.Frame(main_frame, height=1, bg="#555")
```

**Reason:** customtkinter 5.2.2 has no `CTkSeparator`. Replaced with 1px `tk.Frame` (two instances in `main_window` rows 3 and 8).

---

## 3. Format Selection

### Before (PRD):
```python
# Fallback chain: any available format (no codec preference)
'best':  'bv*+ba/b',
'1080p': 'bv*[height<=1080]+ba/b[height<=1080]',
# No format_sort → yt-dlp picks av01 > vp9 > avc1
```

### After (Implementation):
```python
# Fallback chain: mp4+m4a first, then anything, then combined
'best':  'bv[ext=mp4]+ba[ext=m4a]/bv+ba/b',
'1080p': 'bv[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]',

# Codec preference: H.264 first
'format_sort': ['vcodec:h264,vp9,av01', 'res', 'br'],
```

Audio: `mp3`/`m4a` both use `m4a/bestaudio/best`; MP3 PP uses `FFmpegExtractAudio(mp3, 192)`, M4A is metadata + thumbnail only (no re-encode).

### Files changed:
- `core/format_builder.py` — `FORMAT_MAP` / `FORMAT_MAP_MP4`, `format_sort` in `get_common_opts()`

---

## 4. Throttling Recovery

Not specified in PRD.

### After (Implementation):
```python
'throttledratelimit': 102400  # 100 KB/s → re-extract fresh URLs
```
Emitted as `--throttled-rate 102400`. Recovers downloads that stall mid-video.

### Files changed:
- `core/format_builder.py` — `get_common_opts()`

---

## 5. yt-dlp-ejs + Node.js

### Before (PRD):
- No `js_runtimes`, no yt-dlp-ejs in requirements; used `player_client` fallbacks only.
- yt-dlp nightly channel for extractor fixes.

### After (Implementation):
```python
# Explicitly enable yt-dlp-ejs (stable yt-dlp, not nightly)
"js_runtimes": {"node": {}}
"extractor_args": {"youtube-ejs": {}}   # merged with advanced.extractor_args
```
The `js_runtimes` dict is converted to `--js-runtimes node:<bin>/node.exe` in `_build_argv`.
No `player_client` config is hardcoded anymore — the yt-dlp-ejs plugin handles JS challenges.

### PATH in app.py (before any imports):
```python
os.environ["PATH"] = str(PROJECT_ROOT / "bin") + os.pathsep + os.environ.get("PATH", "")
```
yt-dlp-ejs probes for `node` at module load time, so `bin/` must be on PATH first.

### Files changed:
- `core/format_builder.py`, `app.py`, `requirements.txt`

---

## 6. Cookie Handling

### Before (PRD):
```json
"cookies": { "source": "file", "browser": "chrome", "file_path": "data/cookies.txt" }
```

### After (Implementation):
```json
"cookies": { "source": "none", ... }
```
Default is `"none"` — cookies only when the user explicitly enables them (Settings → متقدم).

**Reason:** `Extracting cookies from chrome` fails with `Could not copy Chrome cookie database` while the browser is open.

**Error handling:** emits the Arabic message **"فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"**.

### Files changed:
- `core/config_manager.py`, `core/download_controller.py`

---

## 7. DependencyChecker

### Before (PRD):
```python
BIN_DIR = Path('bin')      # relative
# no FFprobe check
Node.js required = True
# yt-dlp check via exe
```

### After (Implementation):
```python
BIN_DIR = Path(__file__).resolve().parent.parent / 'bin'   # absolute (CWD-independent)
# + _check_ffprobe()
Node.js required = False    # optional
# _check_ytdlp() → import yt_dlp → yt_dlp.version.__version__  (Python package)
```
4 checks: FFmpeg (required), FFprobe (required), Node.js (optional), yt-dlp package (required, via import).

### Files changed:
- `core/dep_checker.py`

---

## 8. Startup Check Flow

### Before (PRD):
```python
def _run_checks(self):
    threading.Thread(target=check, daemon=True).start()
```
Threading + `after()` → `main thread is not in main loop` errors.

### After (Implementation):
```python
def _run_checks(self):
    results = DependencyChecker().check_all()   # synchronous, fast
    self._display_results(results); self.update()
```

### Files changed:
- `ui/startup_check.py`

---

## 9. Download Engine — Python API → Subprocess (biggest v3 change)

### Before (PRD):
```python
with yt_dlp.YoutubeDL(opts) as ydl:
    ydl.download([url])          # in-process Python API
```
Rationale in v2 ADR-001: full hook/logger control; subprocess was rejected as "hard to control".

### After (Implementation):
```python
proc = subprocess.Popen(
    [str(bin_dir / "yt-dlp.exe"), *argv],   # CLI flags built by _build_argv
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace",
)
for line in proc.stdout:  # parse progress/speed/ETA/errors via regex
```

**Why it won:** real cancellation (`proc.terminate()`), OS-level isolation, error classification from `ERROR:` lines instead of exception subclasses, and yt-dlp CLI updates are independent of the bundled Python API. The Python `yt_dlp.YoutubeDL` API is retained **only** for info extraction (`download=False`) in `core/info_extractor.py`.

### Files changed (v3):
- `core/download_controller.py` — full rewrite: `_build_argv`, `_run_single`, `_parse_progress`, `_classify_error`, per-item playlist workers
- `_build_argv` emits `--newline --progress`, `--no-playlist`, `-o "<dir>/%(title)s [%(id)s].%(ext)s"`, and all mapped options (see PROJECT_REFERENCE §5)

---

## 10. Playlist Downloads — Future → Implemented

### Before (PRD):
Listed under *الميزات المستقبلية*; design intent was `--yes-playlist` on the CLI with a simple counter.

### After (Implementation):
- `classify_url()` detects `list=` URLs → `extract_playlist()` (no download) → items shown in a dedicated `PlaylistPanel` (window rows: playlist row 2, weight 2, min 244px)
- **Download All / Download Selected / select-all / deselect-all** buttons
- `start_playlist_download()` runs `_playlist_worker`, invoking `_run_single` once per item with `playlist_item` status events (`downloading` / `completed` / `failed`) and a final `playlist_done`
- Per-playlist folder via `_playlist_save_dir()` (safe name via `sanitize_folder_name`)

### Files changed:
- `core/info_extractor.py` (`extract_playlist`), `ui/playlist_panel.py`, `ui/main_window.py`, `core/download_controller.py`, `utils/validators.py`

---

## 11. Settings Dialog — 4 Tabs → 3 Tabs

### Before (PRD):
4 tabs including a dedicated **Audio** tab (audio format, MP3 quality).

### After (Implementation):
**3 tabs** — عام (General), التحميل (Download), متقدم (Advanced).
Audio format is chosen in the main window's **QualitySelector** (`AUDIO_FORMATS = ["MP3", "M4A"]`), not in settings.

### Files changed:
- `ui/settings_dialog.py`, `ui/quality_selector.py`

---

## 12. Config Schema — Aligned to Actual `_DEFAULTS`

### Before (PRD):
The v2 PRD documented keys that never existed in code or are now stale:
`audio.*`, `download.embed_thumbnail`, `download.embed_metadata`, `download.write_subs`, `download.sub_langs`, `advanced.ffmpeg_location`, `advanced.js_runtime`, `advanced.node_path`, `advanced.use_nightly_yt_dlp`.

### After (Implementation):
The schema in all docs now mirrors `core/config_manager._DEFAULTS` exactly (verified; see `docx/PROJECT_REFERENCE.md` §4). Also:
- **Auto-update feature removed** (no more `pip install --pre --upgrade`; no nightly channel)
- `advanced.show_debug_logs` → adds `--verbose` to the subprocess argv
- `advanced.extractor_args` (optional, merged over `{"youtube-ejs": {}}`)

### Files changed:
- docs only (README, PROJECT_REFERENCE, PROJECT_SUMMARY, PRD v3)

---

## 13. Build Config (no build.spec)

### Before (PRD):
A `build.spec` with binaries (`ffmpeg/ffprobe/node`) was assumed; `yt-dlp.exe` was stated as "unused directly (update only)".

### After (Implementation):
- **No `build.spec` exists** in the repo — PyInstaller `--onedir --noconsole` is **planned, not shipped**
- **`bin/yt-dlp.exe` is the download engine** (subprocess, every download), so the distribution must ship it
- Required runtime tree next to the EXE: `bin/` (ffmpeg, ffprobe, node, yt-dlp), `assets/logo.ico`, `data/` (created on first run)

---

## 14. Additions / Differences Not in the v2 PRD

| Feature | v2 PRD | Current implementation |
|---|---|---|
| Download engine = `bin/yt-dlp.exe` subprocess | ❌ (Python API) | ✅ `_run_single` + regex stdout parsing |
| Real cancellation (`proc.terminate()`) | ❌ | ✅ |
| Playlist downloads (all / selected, per-item status) | ❌ (future) | ✅ |
| Format sort (H.264 preference) | ❌ | ✅ |
| Throttling recovery (`--throttled-rate`) | ❌ | ✅ |
| yt-dlp-ejs `js_runtimes` | ❌ | ✅ |
| Cookie default `"none"` + Arabic cookie error | ❌ | ✅ |
| FFprobe startup check | ❌ | ✅ |
| Single-root CTkFrame architecture | ❌ | ✅ |
| Absolute `BIN_DIR` (`Path(__file__).resolve()`) | ❌ (relative) | ✅ |
| `bin/` on PATH at startup (before imports) | ❌ | ✅ |
| Node.js optional | ❌ (required) | ✅ |
| Settings: 3 tabs (no Audio tab) | ❌ (4 tabs) | ✅ |
| SponsorBlock removal (optional) | ❌ | ✅ (`sponsorblock_remove` → `--sponsorblock-remove`) |
| 272 passing pytest tests + ruff clean | ❌ (manual) | ✅ `tests/` |
| Auto-update yt-dlp / nightly channel | ✅ planned | ❌ removed |

---

## Summary

**Key improvements over the v2 PRD era:**
1. **Engine:** subprocess-based `bin/yt-dlp.exe` with real cancellation and clean error IDs
2. **Playlists:** fully implemented with per-item progress in the UI
3. **Stability:** no `invalid command name` errors (single-root architecture)
4. **Compatibility:** mp4+m4a preferred with H.264-first `format_sort`
5. **Speed:** automatic throttling recovery
6. **Reliability:** yt-dlp-ejs + Node.js for JS challenges
7. **UX:** clear Arabic error messages; cookies off by default
8. **Robustness:** absolute paths, `bin/` on PATH at startup
9. **Documentation:** all docs corrected to match the real implementation (config schema, 3-tab settings, error catalog, dependencies)
# FAQ — YT Downloader

Frequently asked questions about the project's architecture, behavior, and setup.

---

## General

### 1. What is this project?
A Windows desktop application for downloading YouTube videos, audio, and playlists. It has an Arabic GUI built with `customtkinter`, runs the download engine as a subprocess, and uses a Python API for extracting video info only.

### 2. Does it always show an Arabic interface?
Yes — the UI is Arabic only, and there is no language switch. The `ui.language` key was removed from the config schema (asserted absent in `tests/test_config_manager.py`), and `Settings → عام` only exposes the theme and the save folder. Widget labels and the cookie/browser error message are Arabic; config keys, log lines, and error IDs are English.

### 3. What does the app do on startup?
`app.py` prepares `bin/` on PATH and loads the config if present (a fresh install has no config file yet — the app just runs on defaults). A `StartupCheckFrame` then opens immediately and runs the dependency checks (FFmpeg, FFprobe, the bundled `yt-dlp.exe` and the yt-dlp Python package required; Node.js optional) on a background thread, so the window renders without freezing while the checks run. The results are posted back to the UI thread with `after(0)` when they finish. On success it swaps to the embedded `MainWindow`.

---

## Download engine

### 4. How does the download actually work?
Every download runs `bin/yt-dlp.exe` as a `subprocess.Popen` with CLI arguments built by `_build_argv` (`core/download_controller.py:233`). Its stdout (`--newline --progress`) is parsed line-by-line with regexes to extract percent, speed, and ETA. The result is reported through `progress` / `done` / `error` events.

### 5. Why a subprocess instead of `yt_dlp.YoutubeDL.download()`?
See `docs/PRD_DIFF.md` §9. A subprocess gives:
- Real cancellation — cancel runs `taskkill /PID <pid> /T /F` to kill the whole yt-dlp/ffmpeg process tree (3s timeout), falling back to `proc.terminate()` when taskkill is unavailable or does not confirm cleanup (`_terminate_tree` in `core/download_controller.py`).
- Clean error classification from `ERROR:` lines instead of exception subclasses.
- Engine updates that are independent of the bundled Python `yt_dlp` package.
- OS-level isolation — a crash in the engine never takes down the GUI.

The Python API (`yt_dlp.YoutubeDL`, `download=False`) is used only for info extraction in `core/info_extractor.py`.

### 6. How is progress parsed from the subprocess?
With regexes at `core/download_controller.py:12-15`:
- `_PROGRESS_RE`: `\[download\]\s+([\d.]+)%`
- `_SPEED_RE`: `bat\s+([^\s]+)\s+ETA`
- `_ETA_RE`: `ETA\s+([^\s)]+)`
- `_ANSI_RE`: strips ANSI escapes
The status bar and logs are updated from the parsed values.

### 7. What do the error IDs mean?
`_classify_error` maps failures to stable IDs: `age_restricted` (`sign in`/`age` in the message), `unavailable`, `rate_limited` (the message contains `429`), `unsupported_url`, `extractor:<msg>` (suffix `; please report this issue ...` stripped), or `download_error:<msg>` as the catch-all. Cookie/browser errors raise the Arabic message **"فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"**.

---

## Formats and quality

### 8. Which qualities and modes exist?
- Qualities: `Best, 2160p, 1440p, 1080p, 720p, 480p, 360p` (`QUALITY_OPTIONS`).
- Modes: `video`, `mp4_only`, `audio` (`MODE_OPTIONS`).

### 9. Why does video mode prefer mp4+m4a?
`FORMAT_MAP` gives the fallback chain `bv[ext=mp4]+ba[ext=m4a]/bv+ba/b`, and `format_sort` prefers H.264 over vp9/av01 (`["vcodec:h264,vp9,av01", "res", "br"]`). The result is high compatibility (avc1+m4a) instead of av01+opus, which some players can't handle.

### 10. How does audio mode work?
Audio mode picks `m4a/bestaudio/best` and then:
- **MP3** → re-encode via `FFmpegExtractAudio(preferredcodec=mp3, preferredquality=192)` + metadata + embedded thumbnail.
- **M4A** → no re-encode (metadata + thumbnail only, faster).

MP3 output lives in `_audio_postprocessors` in `core/format_builder.py`.

### 11. What is `mp4_only` mode?
Same qualities as video mode but forces an mp4 container: `bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b`. No separate audio/video files are produced.

---

## Playlists

### 12. Can the app download playlists?
Yes. Only an explicit `/playlist?list=` link counts: `classify_url` returns `"playlist"` for those, while a `watch`, `shorts`, or `embed` URL that merely carries a `list=` parameter is classified as a single video, so the download never expands to the whole playlist. A playlist URL is extracted with `extract_playlist()` (no download) and listed in the `PlaylistPanel`. Buttons: **Download All / Download Selected / select-all / deselect-all**.

### 13. How is a playlist downloaded?
`start_playlist_download` runs `_playlist_worker`, which calls `_run_single` once per item, emitting `playlist_item` events (`downloading` / `completed` / `failed`) and a final `playlist_done`. Each playlist goes into its own folder named after the playlist (safe name via `sanitize_folder_name`).

### 14. Why is the playlist panel sometimes hidden?
It is shown only when a playlist URL is loaded; it occupies main-frame row 2 with `weight=2` and a minimum height of 244px (`_PLAYLIST_ROW = 2`, `_PLAYLIST_MIN_HEIGHT = 244`).

---

## Configuration

### 15. Where is the configuration stored?
`%APPDATA%\YTDownloader\config.json` (e.g. `C:\Users\<you>\AppData\Roaming\YTDownloader\config.json`), resolved via `utils/paths.py`. The file is written only when a setting is first changed — it is never created just by running the app. Saves are atomic (write to `config.json.tmp`, then replace), and a corrupted file on load is backed up to `config.json.bak` while the app falls back to `_DEFAULTS`.

### 16. What are the defaults?
- `ui`: theme `dark`, window `800x600`.
- `download`: default_dir `~/Downloads/YTDownloader`, default_quality `1080p`, default_mode `video`, concurrent_fragments `4`, retries `10`, merge_output_format `mp4`.
- `cookies`: source `none` (file path `%APPDATA%\YTDownloader\cookies.txt` if used).
- `advanced`: show_debug_logs `false`, sponsorblock_remove `false` (categories `["sponsor"]`). `advanced.extractor_args` is *not* in `_DEFAULTS`; `get_common_opts` always enables `{"youtube-ejs": {}}` and merges any keys found there (`core/format_builder.py:117-128`).

Keys that exist only in older docs (e.g. `ui.language`, `audio.*`, `embed_*`, `ffmpeg_location`, `js_runtime`, `node_path`, `use_nightly_yt_dlp`) are ignored — `_DEFAULTS` is the only source of truth, and `tests/test_config_manager.py` asserts each of them resolves to `None`.

### 17. What is in the Settings dialog?
Three tabs:
- **عام (General):** theme, default save directory.
- **التحميل (Download):** default quality, mode, concurrent fragments, retries, merge output format.
- **متقدم (Advanced):** cookie source (none/browser/file), browser picker, show debug logs, SponsorBlock toggle + categories.

### 18. How do cookies work?
`cookies.source` is `none` by default — cookies are only used when enabled. Browser extraction requires the browser to be closed (Chrome's DB is locked while open, producing `Could not copy Chrome cookie database`). A file source reads `%APPDATA%\YTDownloader\cookies.txt` (Netscape format).

---

## Dependencies and build

### 19. What needs to be in `bin/`?
- `yt-dlp.exe` — the download engine (required).
- `ffmpeg.exe` / `ffprobe.exe` — merging + audio conversion (required).
- `node.exe` — used by the `yt-dlp-ejs` plugin to solve JavaScript challenges (optional; the app falls back if missing).

`bin/` is prepended to `PATH` in `app.py:19` before imports so `yt-dlp-ejs` can find `node` at module load time.

### 20. What does the startup dependency check verify?
`core/dep_checker.py` runs 5 synchronous checks: FFmpeg (required), FFprobe (required), Node.js (optional), the bundled `yt-dlp.exe` (required), and the yt-dlp Python package (`import yt_dlp` → `yt_dlp.version.__version__`, required). It then appends a non-fatal "yt-dlp version sync" warning when the bundled executable and the Python package report different versions. `BIN_DIR` is an absolute path derived from `utils.paths.bin_dir()`, not CWD.

### 21. Does the app auto-update yt-dlp?
No. Automatic update and the nightly yt-dlp channel were dropped; the app ships with a bundled `bin/yt-dlp.exe` that you update manually if needed. `requirements.txt` pins the matching Python package to `yt-dlp[default]==2026.08.19` so the info-extraction path and the subprocess downloader stay on the same engine version.

### 22. How is the app packaged?
`build_windows.bat` drives `build_windows.ps1`: it runs the test suite, generates the icon, freezes `app.py` with PyInstaller (`ytdownloader.spec`, `--onedir --noconsole`), then flattens the generated bundle into the portable layout under `Release\`:

```
Release\
├── YT Downloader.exe     <- the PyInstaller application itself
├── _internal\            <- frozen Python run-time, libraries, base_library.zip
├── bin\yt-dlp.exe ffmpeg.exe ffprobe.exe node.exe
└── assets\logo.ico, fonts\
```

There is no outer launcher: `Release\YT Downloader.exe` *is* the frozen app. `bin\` and `assets\` are siblings of the executable (never inside `_internal\`) because `utils/paths.app_root()` resolves them from the executable's own directory, which keeps the folder relocatable.

The build finishes with a layout validation, a packaged self-test (`YTDLP_DESKTOP_SELFTEST=1`, run from an unrelated working directory, must exit 0) and smoke tests of the packaged `yt-dlp.exe --version` / `ffmpeg.exe -version`. User data is never written into the install folder — everything goes to `%APPDATA%\YTDownloader\` — so the folder can be moved, copied, or upgraded in place.

---

## Tests & known behaviors

### 23. What is the test setup?
491 passing pytest tests across `tests/` (with `customtkinter`/`tkinter` and `yt_dlp` stubbed out). `ruff check` is **not** clean: it reports 15 pre-existing findings, all `E402` module-level-import-not-at-top-of-file in `app.py` and `ui/playlist_panel.py` (both files deliberately import after the path/PATH bootstrap).

### 24. Where should new links be validated?
`utils/validators.py`:
- Short links `youtu.be/<id>` are accepted (must be exactly 11 chars, followed by a non-word char).
- `watch?v=<id>` requires a well-formed 11-char ID (rejects `watch?v=short`, empty, or overlong IDs).
- Only an explicit `/playlist?list=` link is classified as a playlist. A `watch`, `shorts`, or `embed` URL that merely carries an extra `list=` param is classified as a single video, so the download never expands to the whole playlist.

### 25. What known limitations remain?
- `bin/` is prepended to `PATH` at `app.py:19` (unconditionally) and again by `get_common_opts` (which skips the prepend when the path is already present); it is never restored afterwards. Low impact — it is the app's own bundle directory.
- Quality tiers are not capped at 360p: `get_available_qualities` offers every tier at or below the source's max height, so a 1080p video also offers `240p`. `240p` has no entry in `FORMAT_MAP`/`FORMAT_MAP_MP4`, so picking it silently downloads the `Best` chain. Tiers above the source height (1440p/2160p for a 1080p video) are omitted.
- Video ID validation is deliberately strict (11 chars) — treat non-YouTube IDs as unsupported rather than guessing.

---

## Legacy documents

### 26. Where is the old bug log and PRD?
This file (`FAQ.md`) replaces the previous `BUGS.md` bug log; the fixes it documented are now covered by Q&A above (§24-25) and all 491 tests pass. The superseded design document is `docs/PRD_YTDownloader_v2.md` (kept for history); the current spec is `docs/PRD_YTDownloader_v3.md` and the implementation diff is in `docs/PRD_DIFF.md`.

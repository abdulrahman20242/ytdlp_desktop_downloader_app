# FAQ — YT Downloader

Frequently asked questions about the project's architecture, behavior, and setup.

---

## General

### 1. What is this project?
A Windows desktop application for downloading YouTube videos, audio, and playlists. It has an Arabic/English GUI built with `customtkinter`, runs the download engine as a subprocess, and uses a Python API for extracting video info only.

### 2. Does it always show an Arabic interface?
The UI defaults to Arabic (`ui.theme.language = "ar"`) but can be switched to English from Settings → عام. On-disk config and internal messages are English; user-facing errors are localized.

### 3. What does the app do on startup?
`app.py` prepares `bin/` on PATH, loads `data/config.json`, then shows a `StartupCheckFrame` that runs the dependency check synchronously (FFmpeg, FFprobe required; Node.js optional; yt-dlp package required). On success it swaps to the embedded `MainWindow`.

---

## Download engine

### 4. How does the download actually work?
Every download runs `bin/yt-dlp.exe` as a `subprocess.Popen` with CLI arguments built by `_build_argv` (`core/download_controller.py:73`). Its stdout (`--newline --progress`) is parsed line-by-line with regexes to extract percent, speed, and ETA. The result is reported through `progress` / `done` / `error` events.

### 5. Why a subprocess instead of `yt_dlp.YoutubeDL.download()`?
See `docx/PRD_DIFF.md` §9. A subprocess gives:
- Real cancellation — `proc.terminate()` kills the OS process (`core/download_controller.py` cancel flow).
- Clean error classification from `ERROR:` lines instead of exception subclasses.
- Engine updates that are independent of the bundled Python `yt_dlp` package.
- OS-level isolation — a crash in the engine never takes down the GUI.

The Python API (`yt_dlp.YoutubeDL`, `download=False`) is used only for info extraction in `core/info_extractor.py`.

### 6. How is progress parsed from the subprocess?
With regexes at `core/download_controller.py:9-12`:
- `_PROGRESS_RE`: `\[download\]\s+([\d.]+)%`
- `_SPEED_RE`: `bat\s+([^\s]+)\s+ETA`
- `_ETA_RE`: `ETA\s+([^\s)]+)`
- `_ANSI_RE`: strips ANSI escapes
The status bar and logs are updated from the parsed values.

### 7. What do the error IDs mean?
`_classify_error` maps failures to stable IDs: `age_restricted`, `unavailable`, `rate_limited` (HTTP 429), `unsupported_url`, `extractor:<msg>` (suffix `; please report this issue ...` stripped), `download_error:<msg>`, or `unknown:<exception>`. Cookie/browser errors raise the Arabic message **"فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"**.

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
Yes. URLs containing `list=` are detected by `classify_url`, extracted with `extract_playlist()` (no download), and listed in the `PlaylistPanel`. Buttons: **Download All / Download Selected / select-all / deselect-all**.

### 13. How is a playlist downloaded?
`start_playlist_download` runs `_playlist_worker`, which calls `_run_single` once per item, emitting `playlist_item` events (`downloading` / `completed` / `failed`) and a final `playlist_done`. Each playlist goes into its own folder named after the playlist (safe name via `sanitize_folder_name`).

### 14. Why is the playlist panel sometimes hidden?
It is shown only when a playlist URL is loaded; it occupies main-frame row 2 with `weight=2` and a minimum height of 244px (`_PLAYLIST_ROW = 2`, `_PLAYLIST_MIN_HEIGHT = 244`).

---

## Configuration

### 15. Where is the configuration stored?
`data/config.json`, resolved relative to the current working directory (`Path("data/config.json")`). It is created on first run from `config_manager._DEFAULTS`.

### 16. What are the defaults?
- `ui`: theme `dark`, language `ar`, window `800x600`.
- `download`: default_dir `~/Downloads/YTDownloader`, default_quality `1080p`, default_mode `video`, concurrent_fragments `4`, retries `10`, merge_output_format `mp4`.
- `cookies`: source `none` (file path `data/cookies.txt` if used).
- `advanced`: show_debug_logs `false`, sponsorblock_remove `false` (categories `["sponsor"]`), extractor_args optional override for `{"youtube-ejs": {}}`.

Keys that exist only in older docs (e.g. `audio.*`, `embed_*`, `ffmpeg_location`, `node_path`, `use_nightly_yt_dlp`) are ignored — `_DEFAULTS` is the only source of truth.

### 17. What is in the Settings dialog?
Three tabs:
- **عام (General):** theme, language, default save directory.
- **التحميل (Download):** default quality, mode, concurrent fragments, retries, merge output format.
- **متقدم (Advanced):** cookie source (none/browser/file), browser picker, show debug logs, SponsorBlock toggle + categories.

### 18. How do cookies work?
`cookies.source` is `none` by default — cookies are only used when enabled. Browser extraction requires the browser to be closed (Chrome's DB is locked while open, producing `Could not copy Chrome cookie database`). A file source reads `data/cookies.txt` (Netscape format).

---

## Dependencies and build

### 19. What needs to be in `bin/`?
- `yt-dlp.exe` — the download engine (required).
- `ffmpeg.exe` / `ffprobe.exe` — merging + audio conversion (required).
- `node.exe` — used by the `yt-dlp-ejs` plugin to solve JavaScript challenges (optional; the app falls back if missing).

`bin/` is prepended to `PATH` in `app.py:11` before imports so `yt-dlp-ejs` can find `node` at module load time.

### 20. What does the startup dependency check verify?
`core/dep_checker.py` runs 4 synchronous checks: FFmpeg (required), FFprobe (required), Node.js (optional), and the yt-dlp Python package (`import yt_dlp` → `yt_dlp.version.__version__`). `BIN_DIR` is an absolute path derived from the file location, not CWD.

### 21. Does the app auto-update yt-dlp?
No. Automatic update and the nightly yt-dlp channel were dropped; the app ships with a bundled `bin/yt-dlp.exe` that you update manually if needed. Requirements pin `yt-dlp[default]>=2025.1.1`.

### 22. How is the app packaged?
There is **no `build.spec`** in the repo. PyInstaller `--onedir --noconsole` is planned; the EXE must be shipped next to `bin/`, `assets/logo.ico`, and a writable `data/` folder.

---

## Tests & known behaviors

### 23. What is the test setup?
272 passing pytest tests across `tests/` (12 test files + `conftest.py`), with `customtkinter`/`tkinter` and `yt_dlp` stubbed out. `ruff check` is clean on `core/ utils/ ui/ tests/`.

### 24. Where should new links be validated?
`utils/validators.py`:
- Short links `youtu.be/<id>` are accepted (must be exactly 11 chars, followed by a non-word char).
- `watch?v=<id>` requires a well-formed 11-char ID (rejects `watch?v=short`, empty, or overlong IDs).
- Playlists are recognized on `youtube.com` only; a `youtu.be/<id>?list=...` URL is not classified as a playlist.

### 25. What known limitations remain?
- `extract_video_id` uses `re.search` without a trailing negative lookahead, so an overlong ID on `youtu.be/<id>` returns the first 11 characters.
- `bin/` is added to `PATH` without restoring it afterwards (guarded against duplicates; low impact).
- Extractors: a 1080p video shows qualities `Best, 1080p, 720p, ...` (threshold "≤ max height") — 1440p/2160p are intentionally absent.
- Video ID validation is deliberately strict (11 chars) — treat non-YouTube IDs as unsupported rather than guessing.

---

## Legacy documents

### 26. Where is the old bug log and PRD?
This file (`FAQ.md`) replaces the previous `BUGS.md` bug log; the fixes it documented are now covered by Q&A above (§24-25) and tests 272/272 pass. The superseded design document is `docx/PRD_YTDownloader_v2.md` (kept for history); the current spec is `docx/PRD_YTDownloader_v3.md` and the implementation diff is in `docx/PRD_DIFF.md`.
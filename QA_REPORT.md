# QA Report — yt-dlp Desktop Downloader App

**Date:** 2026-09-10
**Tester:** Agent
**Baseline commit:** `6e6f97a`
**Release build:** `Release/` (PyInstaller 6.20.0, Python 3.13.8, net48 launcher)

---

## 1. Changes Per File

### Modified (17)

| File | Fix/Change |
|------|-----------|
| `.gitignore` | Exclude `Release/` from version control |
| `app.py` | Startup ordering: ConfigManager instantiated (line 26) before selftest exit (line 31-32); PATH-before-imports (E402, intentional — documented FAQ §19) |
| `core/config_manager.py` | **F-A4:** `_load` catches `(OSError, ValueError)` → `_recover_bad_config()` backs up to `.bak` via `shutil.copy2` + returns defaults; `_save` atomic write (tmp→`os.replace`) with cleanup on failure |
| `core/dep_checker.py` | **F-A3:** Recognize bundled `bin/yt-dlp.exe`; handle missing optional deps gracefully in startup check |
| `core/download_controller.py` | **F-A2:** `_terminate_tree` = `taskkill /PID <pid> /T /F` + `CREATE_NO_WINDOW` (nt) / `proc.terminate()` (else); `shutdown()` joins thread 3.0s + clears `_proc`; `_resolve_dir` warns + falls back to `get_downloads_dir()`; qualities computed in fetch thread (**F-A1**) |
| `core/info_extractor.py` | **F-A1:** `extract_info` returns quality list from actual format heights |
| `ui/main_window.py` | **F-A5:** Save path uses `ensure_dir(path, fallback=...)`; Arabic warning shown on fallback |
| `ui/startup_check.py` | **F-A1:** `StartupCheckFrame` runs checks in daemon thread + `after(0)` with `RuntimeError` guard |
| `utils/file_utils.py` | **F-A5:** `ensure_dir(path, fallback=None)` catches `FileExistsError` → uses fallback dir + warns |
| `requirements.txt` | **F-B1:** `yt-dlp[default]==2026.08.19` (matches `bin/yt-dlp.exe`) |
| `README.md` | **F-B2:** Pinned version table + requirements block; `%APPDATA%\YTDownloader\config.json` docs; new "Building a Portable Release" section; project tree updated |
| `FAQ.md` | **F-B2:** §3 (async startup), §15 (AppData config, atomic save, `.bak` recovery), §16/§18 (`cookies.txt` path), §21 (`==2026.08.19`), §22 (packaging description), §23/§26 (315 tests) |
| `tests/test_config_manager.py` | **F-A4:** Malformed recovery, atomic save, backup tests |
| `tests/test_download_controller.py` | **F-A2:** Cancel/shutdown orphan scan, process tree kill tests |
| `tests/test_file_utils.py` | **F-A5:** `ensure_dir` fallback, existing-file tests |
| `tests/test_info_extractor.py` | **F-A1:** Quality extraction tests |
| `tests/test_settings_flow.py` | **F-A1:** Async startup, error handling tests; mid-file `import ui.main_window as mw_module` moved to top (fixed ruff E402) |

### New (4)

| File | Purpose |
|------|---------|
| `utils/paths.py` | `user_data_dir()` → `%APPDATA%\YTDownloader`; `config_path()`, `cookies_path()`, `app_root()` |
| `tests/test_paths.py` | Tests for `utils/paths.py` (9 tests) |
| `build_windows.bat` | Build entry point (`build_windows.ps1`) |
| `build_windows.ps1` | `dotnet publish` launcher + PyInstaller `ytdownloader.spec` + selftest |
| `ytdownloader.spec` | PyInstaller onedir spec: `--add-data assets;assets --add-data bin;bin` |

---

## 2. F-A* Fixes: Problem → Fix → Regression

### F-A4 — Malformed Config Recovery

- **Problem:** Malformed `config.json` caused unhandled `JSONDecodeError` → fatal DOA dialog in packaged builds. Pre-fix: zero recovery; app refused to boot.
- **Fix:** `_load` catches `(OSError, ValueError)` → calls `_recover_bad_config()` which backs up the file to `config.json.bak` via `shutil.copy2` and returns `_DEFAULTS` in-memory. `_save` uses atomic write pattern: writes to `.tmp` then `os.replace(path, tmp)`.
- **Regression:** Unit-tested (21 tests). **Runtime probe PASS:** Packaged exe with malformed config in isolated `%APPDATA%` → `exit=0`, `.bak` created, `config.json` preserved (line 26 in `app.py` exercises `ConfigManager()` before selftest return at line 31).

### F-A2 — Orphan Process Kill on Cancel/Close

- **Problem:** `cancel()` killed only the root yt-dlp PID; child processes (ffmpeg, node.js from yt-dlp-ejs JS solver) were reparented and left orphaned. `_on_close` could also leave the thread alive.
- **Fix:** `_terminate_tree(proc)` runs `taskkill /PID <pid> /T /F` with `subprocess.CREATE_NO_WINDOW` on Windows, `proc.terminate()` on POSIX. `shutdown()` calls `_terminate_tree` + `thread.join(timeout=3.0)` + clears `self._proc`.
- **Regression:** Unit-tested (36 tests). **Runtime probe PASS:** Download started → tree_before = `{9096:yt-dlp.exe, 20088:yt-dlp.exe, 18264:conhost.exe}` → cancel → tree_after = `∅` → all descendants killed, zero orphan binaries. Pre-existing system node.exe PIDs `{17256, 17404, 9620}` confirmed unrelated (snapshot before/after).

### F-A5 — FileExistsError on Existing Save Path

- **Problem:** When user-specified save path was an existing file (not directory), `os.makedirs` raised `FileExistsError [WinError 183]`.
- **Fix:** `ensure_dir(path, fallback=None)` catches `FileExistsError` → if fallback, warns + uses `fallback` dir. `_resolve_dir` in `download_controller.py` falls back to `get_downloads_dir()`. Arabic warning displayed in UI.
- **Regression:** Unit-tested (23 tests including `EnsureDir` fallback + existing-file scenarios). Runtime: GUI-driven scenario requires pywinauto automation; unit tests exercise the exact code path (`ensure_dir` + `ConfigManager.set`). Code review confirms no GUI crash path.

### F-A3 — yt-dlp.exe Bundling Recognition

- **Problem:** `dep_checker` didn't recognize `bin/yt-dlp.exe` as yt-dlp → claimed yt-dlp missing at startup despite it being bundled.
- **Fix:** `dep_checker` checks `bin/yt-dlp.exe` via `subprocess.run(["bin/yt-dlp.exe", "--version"])`; reports correctly. Startup check handles missing optional deps gracefully without blocking.
- **Regression:** Unit-tested (12 tests).

### F-A1 — Quality List in Fetch Thread + Async Startup

- **Problem:** `extract_info` could block UI when computing quality list; qualities list could be empty if extraction failed. `StartupCheckFrame` ran on main thread.
- **Fix:** Qualities computed in fetch thread after `extract_info` completes. `StartupCheckFrame` runs checks in daemon thread + `after(0)` callback with `RuntimeError` guard (handles destroyed widget).
- **Regression:** Unit-tested (29 `test_info_extractor` + 21 `test_settings_flow` tests).

---

## 3. F-B* Changes

### F-B1 — Pin yt-dlp

- `requirements.txt` line 1: `yt-dlp[default]==2026.08.19`
- Embedded yt-dlp and `bin/yt-dlp.exe` both report `2026.08.19`
- Real download verified: `https://www.youtube.com/watch?v=jNQXAC9IVRw` ("Me at the zoo") → merged 635KiB mp4 via `bv[height<=240][ext=mp4]+ba[ext=m4a]/...`

### F-B2 — Documentation

- **README.md:** Pinned version table + requirements block; `%APPDATA%\YTDownloader\config.json` docs (written on first change, `.bak` recovery); new "Building a Portable Release" section (`build_windows.bat` → PyInstaller onedir → `Release/` layout); project tree updated (`utils/paths.py` added, `data/` runtime-config line removed)
- **FAQ.md:** §3 (async startup, no freeze), §15 (AppData config, atomic save, `.bak`), §16/§18 (`cookies.txt` path), §21 (`==2026.08.19`), §22 (packaging: launcher + PyInstaller + selftest), §23 (315 tests, ruff clean), §26 (315/315)

---

## 4. Test / Build / Runtime Results

| Metric | Result |
|--------|--------|
| **pytest** | **315 passed** in 7.52s |
| **ruff** | **All checks passed** (core/ ui/ utils/ tests/) |
| **Build** | `build_windows.bat` succeeded: 315 tests → icon → launcher `YT Downloader.exe` (net48) → PyInstaller 6.20.0 onedir → selftest `exit=0` |
| **Release layout** | `Release\YT Downloader.exe` + `Release\YT Downloader\{YTDownloaderCore.exe, _internal\, assets\logo.ico, bin\{yt-dlp,ffmpeg,ffprobe,node}.exe}` |
| **F-A4 runtime** | PASS — packaged exe, malformed config in isolated `%APPDATA%` → `exit=0`, `.bak` created |
| **F-A2 runtime** | PASS — in-process `DownloadController` cancel → tree_before `{9096, 20088, 18264}` → tree_after `∅` → zero orphan download binaries |
| **F-A5 runtime** | Unit-tested (23 tests); GUI-driven scenario requires pywinauto (code path fully exercised) |

---

## 5. Release Status

**READY FOR RELEASE**

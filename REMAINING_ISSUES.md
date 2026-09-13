# Remaining Issues — Fix Handoff for AI Agent

Repo: `F:\projects\Python Projects\yt-dlp\ytdlp_desktop_downloader_app`
Python + customtkinter desktop downloader wrapping yt-dlp (Windows).

Baseline: `python -m pytest -q` → **338 passed** before these changes. Keep it green.
Code style conventions: type hints on all signatures, `LOGGER = logging.getLogger(__name__)` per module, docstrings in English, UI strings are Arabic (do not translate), target files are UTF-8.

---

## Important — F1: `_run_single()` forcibly kills the process tree on the success path

**File:** `core/download_controller.py:368-370`

**Current code:**

```python
        finally:
            self._proc = None
            _terminate_tree(proc)
```

**The termination is unconditional.** The `for raw in proc.stdout` loop ends at stdout EOF, which can happen a moment *before* yt-dlp finishes post-processing (ffmpeg merge of video+audio streams). At that instant `_terminate_tree(proc)` sees the process still alive and runs `taskkill /PID <pid> /T /F` (`_terminate_tree` → `download_controller.py:121-146`), killing a download that was about to succeed. The run is then reported as failed via `rc = proc.wait()` (`_terminate_tree` force-kills → non-zero exit code → `_classify_error`).

Note that `cancel()` (`download_controller.py:482-489`) and `shutdown()` (`494-507`) **already** call `_terminate_tree(self._proc)` themselves, so gating the `finally` on the cancel flag loses nothing on the cancel path.

**Fix:**

```python
        finally:
            self._proc = None
            if self._stop_event.is_set():
                _terminate_tree(proc)
```

**Tests:**
- Add `tests/test_download_controller.py` test: fake proc object whose `poll()` returns `None` (simulates "stdout EOF but process still running"), fake stop event that is *not* set → assert `proc.terminate` was **never** called and `_run_single` returns `"ok"` (need to monkeypatch the Popen fake so stdout yields lines, then exits — follow the existing fake-proc pattern in the file around lines 25-70 / 650-750).
- Keep the existing cancel tests green (`test_cancel_kills_process_tree_via_taskkill:650`, `test_cancel_terminates_worker_mid_download:221`) — cancel() itself terminates the tree, so the gate must not regress them.

**Acceptance:** a successful download where the process is still alive at EOF returns `"ok"` and never calls taskkill/terminate.

---

## Important — F2: `MainWindow._load_thumbnail()` swallows all exceptions silently

**File:** `ui/main_window.py:542-554`

**Current code:**

```python
    def _load_thumbnail(self, url: str):
        def load():
            try:
                resp = requests.get(url, timeout=10)
                img = Image.open(BytesIO(resp.content))
                img = img.resize((160, 90), Image.LANCZOS)
                photo = ctk.CTkImage(img, size=(160, 90))
                self.after(0, lambda: self._thumb_label.configure(image=photo, text=""))
                self.after(0, lambda: setattr(self, "_thumb_photo", photo))
            except Exception:
                pass

        threading.Thread(target=load, daemon=True).start()
```

**Problems:**
1. `except Exception: pass` is fully silent — no log, so network errors *and* genuine bugs (e.g. a malformed image in our resize/convert path) are indistinguishable. The equivalent method in the playlist panel (`ui/playlist_panel.py:508-521`) was already fixed the same way — mirror that fix here for consistency.
2. Unbounded thread spawn: every `_load_thumbnail` call starts a brand-new `threading.Thread`, each doing a blocking `requests.get(timeout=10)`. Fetching a playlist/video with many entries spawns one thread per thumbnail.

**Fix (mirror `playlist_panel.py:503-526`):**

```python
    def _load_thumbnail(self, url: str):
        def _fetch():
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                img = Image.open(BytesIO(resp.content))
                img = img.resize((160, 90), Image.LANCZOS)
                photo = ctk.CTkImage(img, size=(160, 90))
                self.after(0, lambda: self._thumb_label.configure(image=photo, text=""))
                self.after(0, lambda: setattr(self, "_thumb_photo", photo))
            except (requests.RequestException, OSError) as exc:
                LOGGER.debug("Could not load thumbnail %s: %s", url, exc)

        threading.Thread(target=_fetch, daemon=True).start()
```

Add `import logging` + `LOGGER = logging.getLogger(__name__)` to `ui/main_window.py` (check if already present).

Bounding the concurrency (worker pool or `after`-serialized queue) is a stretch goal, not required — the playlist panel ships with the same unbounded pattern. At minimum: narrow the exception and log it.

**Acceptance:** a failing thumbnail request logs at debug level and never raises out of the worker thread; a non-`requests`/`OSError` exception (real bug) is no longer silently discarded.

---

## Important — F3: `info_extractor` still catches broad `Exception` at the extraction boundary

**File:** `core/info_extractor.py:24-26` and `102-104`

**Current code:**

```python
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return ydl.sanitize_info(info)
    except Exception as exc:
        LOGGER.warning("Could not extract info for %s: %s", url, exc)
        return None
```

(and the `extract_playlist` analogue.)

**Problems:**
- The `None` contract is the *correct UX* — the caller shows "❌ فشل استخراج المعلومات" and offers retry. But catching bare `Exception` means a real programming error (bug in our opts, a type error inside our handling) also becomes a user-facing "extraction failed" with only a one-line warning and no traceback (`LOGGER.warning` without `exc_info`).
- Every config/`YoutubeDL` error that is genuinely unrecoverable should *not* masquerade as "bad URL / offline".

**Fix:** catch the recoverable yt-dlp error type and let the rest propagate. yt-dlp raises `yt_dlp.utils.DownloadError` for failed extraction/downloads (verify the exact import path against the installed yt-dlp: `from yt_dlp.utils import DownloadError`). If in doubt, at minimum switch `warning` → `exception` so the traceback is retained:

```python
    try:
        ...
    except Exception:
        LOGGER.exception("Could not extract info for %s", url)
        return None
```

Preferred version (recommended):

```python
from yt_dlp.utils import DownloadError

    try:
        ...
    except DownloadError:
        LOGGER.warning("Could not extract info for %s", url)
        return None
```

Apply the same change to both `extract_info` (line 24) and `extract_playlist` (line 102). If choosing the `DownloadError` path, use `LOGGER.warning` or drop to `LOGGER.info` (no traceback needed — it's an expected failure).

**Tests:** `tests/test_info_extractor.py` — `test_extract_info_returns_none_on_extractor_failure:46` monkeypatches `extract_info` to `raise self._fail`; update the helper's `_fail` to raise `DownloadError` if the narrow catch is adopted. Optionally add a test asserting a non-`DownloadError` exception propagates.

**Acceptance:** a genuine yt-dlp extraction failure still returns `None`; an unexpected exception now surfaces (traceback) instead of being swallowed into a "failed extraction" message.

---

## Nit — N1: Dead code (`UILogger`, `safe_filename`)

**Files:** `utils/ui_logger.py` (whole file), `utils/file_utils.py:35-50` (`safe_filename`).

**Evidence:** `UILogger` has exactly one reference in the codebase — its class definition. `safe_filename` is defined but never called; `sanitize_folder_name` (the used function) supersedes it.

**Fix:** delete `utils/ui_logger.py`, the `safe_filename` function in `utils/file_utils.py`, and the corresponding tests: `tests/test_ui_logger.py` and the `safe_filename` params/cases in `tests/test_file_utils.py:5,22-23` (keep `sanitize_folder_name` tests). Confirm nothing imports either (`Select-String UILogger/safe_filename -Path *.py,core,ui,utils`).

**Acceptance:** `grep -r "UILogger\|safe_filename" --include=*.py .` returns no matches, tests still pass.

---

## Nit — N2: `PlaylistPanel.finish_download()` ignores all three arguments

**File:** `ui/playlist_panel.py:351-353`

```python
    def finish_download(self, completed: int, failed: int, total: int):
        """Re-enable selection controls after a playlist run."""
        self._enable_controls()
```

Call sites pass real counts (`ui/main_window.py:399`, `763`) that are discarded; the completion summary is instead assembled in `main_window._playlist_completed`. Either:
- **Drop the params**: `def finish_download(self):` and update both call sites (`main_window.py:399` and `763`, the latter currently `finish_download(0, 0, 0)`), **or**
- **Use them**: set a status label in the playlist panel, e.g. `نجح {completed} / فشل {failed} (من {total})`.

Prefer the first option (the panel already exposes a custom status callback contract; the summary belongs with the other summary UI). Update any test that calls the old signature in `tests/test_playlist_panel.py`.

**Acceptance:** no unused-parameter stub; either the panel shows the summary or the signature is parameterless and call sites updated.

---

## Nit — N3: Settings dialog cookie default mismatches the real config default

**File:** `ui/settings_dialog.py:126`

```python
        self._cookies_source_var.set(self.config.get("cookies.source", "browser"))
```

The authoritative merged default is `"none"` (`core/config_manager.py` `_DEFAULTS` → `"cookies.source": "none"`). Because `ConfigManager.get()` always merges defaults first, the `"browser"` fallback here is dead and misleading.

**Fix:** change `"browser"` → `"none"`.

**Tests:** existing cookie flow tests use stubs (`tests/test_settings_flow.py:359,396`) and set values explicitly — assert none depends on the `"browser"` fallback, then update or add one asserting the default selected value is `"none"`.

**Acceptance:** on a fresh config the cookies dropdown opens on "none", matching the doc and the underlying default.

---

## Nit — N4: `node.exe` path derived by coupling two files

**Files:** `core/format_builder.py:113` → `core/download_controller.py:195-207`

`format_builder.get_common_opts()` emits `"js_runtimes": {"node": {}}`, and `_append_runtime_and_extractor_args()` special-cases:

```python
            if name == "node":
                runtimes.append(f"node:{ffmpeg_dir / 'node.exe'}")
```

so the `node.exe`-beside-`ffmpeg` knowledge lives in `download_controller`, while the empty dict comes from `format_builder`. If `node.exe` is missing the arg is still emitted as `<ffmpegdir>\node.exe`.

**Fix (preferred):** have `format_builder` emit the resolved runtime wrapper itself:

```python
"js_runtimes": {"node": {"path": str(BIN_DIR / "node.exe")}},
```

then `_build_argv`'s node special-case collapses into the generic `cfg.get("path")` branch (the `if name == "node"` block at `download_controller.py:200-201` is deleted).

**Tests:** update `tests/test_download_controller.py:348-356` (`test_build_argv_js_runtimes_point_at_node_in_ffmpeg_bin`) — it currently asserts the derived `node:{tmp}/node.exe` string; it must still hold with the source-dict change (the generic branch yields the same string), and add a `format_builder` test asserting `js_runtimes["node"]["path"]` points at the bin dir.

**Acceptance:** removing the `node` special-case in `download_controller` produces byte-identical argv for the wrapped format.

---

## Nit — N5: Video page uses magic row numbers while playlist page uses constants

**File:** `ui/main_window.py`

Playlist page uses named constants, defined at lines 42-43:
```python
_PLAYLIST_ROW = 2
_LOGS_ROW = 8
```
referenced at `main_window.py:256` and `310`. The video page instead hard-codes rows: `rowconfigure(7, weight=1)` at `:118`, widget `grid(row=0..7)` calls at `:143,159,172,175,188,215,217,220`.

**Fix:** introduce constants for the video page rows (e.g. `_VIDEO_INFO_ROW = 1`, `_VIDEO_DIR_ROW = 3`, `_VIDEO_ACTION_ROW = 4`, `_VIDEO_PROGRESS_ROW = 5`, `_VIDEO_LOGS_ROW = 7`) and use them in `_build_video_page` and the `grid_rowconfigure(7, weight=1)` call. Convention per the existing short `pt` docstrings/comments in this file.

**Acceptance:** no bare grid row literals for the video page's structural widgets; geometry tweaks are single-point edits.

---

## Nit — N6: `PlaylistPanel._scale()` still catches bare `Exception`

**File:** `ui/playlist_panel.py:142-145`

```python
        try:
            return max(1, round(px / ScalingTracker.get_widget_scaling(self)))
        except Exception:
            return px
```

This mirrors `_measure_font()` / `_truncate` guards, which were already narrowed to `(tk.TclError, RuntimeError)`/`(tk.TclError, ValueError, AttributeError)` in this same file (see `:604-612`, `:620-626`, `:631-634`). For consistency and to stop masking non-Tcl bugs in our own scaling code:

```python
        except (tk.TclError, RuntimeError):
            return px
```

(module already imports `tk`).

**Acceptance:** no bare `except Exception` remains in `ui/playlist_panel.py` (except, if kept intentionally, at the extraction boundary — but that one is covered by F3).

---

## Retracted (do NOT fix)

- `core/format_builder.py` — the `"Best"` alias keys in `FORMAT_MAP` / `FORMAT_MAP_MP4` (`format_builder.py:23,36`). They are **intentional and covered by a regression test**: `tests/test_format_builder.py:20-24` (`test_format_maps_expose_best_alias`) exists because a past commit removed them and broke direct indexing with the UI's "Best" label. `QUALITY_OPTIONS[0] = "Best"` is a display label. Leave the alias keys in place.

---

## Suggested execution order

1. **F1** (correctness race, highest value) → 2. **F2** (silent swallow in UI) → 3. **F3** (boundary swallow + traceback) → 4. N1–N6 (cheap cleanups, touching files you already understand). Run `python -m pytest -q` after each change; 338 tests must stay green, plus any new ones added.
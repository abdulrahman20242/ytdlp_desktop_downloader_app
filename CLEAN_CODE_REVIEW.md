# Code review: whole project (app.py, core/, ui/, utils/ — 17 files, ~3,320 LoC)

## Summary
Solid, unusually careful small desktop app: atomic config persistence, thoughtful process-tree cancellation, and deliberate Tk geometry work, with tests for every core module. The main issues are the AI-failure-mode class: broad exception swallowing at the extraction boundary, one risky unconditional process-kill on the success path, and dead code left behind. Verdict: **needs work** (no blocker on shipping a v1.0.0, but the swallow patterns and the kill-in-`finally` deserve fixing).
Counts: 1 critical, 4 important, 8 nits (must equal the findings listed below)

## Critical findings
- `core/info_extractor.py:20,97` — **swallowed exception**: both `extract_info()` and `extract_playlist()` wrap the entire body in `except Exception: return None`. A network error, a YouTube API rejection, *and* a genuine bug inside the function all become `None`, so the UI shows "❌ فشل استخراج المعلومات" and the user cannot distinguish "bad URL / no network" from "app bug". Per Karpathy's rule, catch only the recoverable type. Fix: `except yt_dlp.utils.DownloadError: return None` (this is the type yt-dlp raises for failed extraction) and let every other exception propagate, or log at `LOGGER.exception` before returning `None` if a silent-fallback contract is really wanted.

## Important findings
- `core/download_controller.py:361-363` — **cleanup kills a healthy process**: the `finally` block calls `_terminate_tree(proc)` unconditionally, including the normal success path. If the last stdout line is consumed a moment before the process finishes post-processing (ffmpeg merge), `taskkill /F` force-kills a download that was about to succeed, and the run is reported as failed. The terminate is only needed on the cancel path. Fix:
  ```python
  finally:
      self._proc = None
      if self._stop_event.is_set():
          _terminate_tree(proc)
  ```
  then rely on `proc.wait()` (which Popen already reaps) on the success path.
- `core/download_controller.py:328` — **broad catch with silent-ish result**: `except Exception as e: return f"unknown:{e}"` around `subprocess.Popen` converts any programming error in argv construction into a user-facing `download_error:` message. The only recoverable failures here are `OSError` (missing exe, bad path). Fix: `except OSError as e: return f"unknown:{e}"`; let everything else raise.
- `core/dep_checker.py:62-112` — **triplicated probe logic (DRY)**: `_check_ffmpeg`, `_check_ffprobe`, and `_check_node` are three ~15-line copies of "locate binary, run `--version`, split first line, fall back to 'unknown'". Only the binary name, the version flag, and `required` differ. Fix: extract one helper, e.g. `_probe(name, binary_name, version_args, required)` and have the three checks call it. While there, narrow `except Exception: version = "unknown"` to `subprocess.SubprocessError` so a genuine bug in the probe isn't masked as an unknown version.
- `ui/playlist_panel.py:504-522`, `ui/main_window.py:542-554` — **unbounded thread spawn per thumbnail**: `_load_thumb`/`_load_thumbnail` launch one `threading.Thread` per image with no cap; a 500-entry playlist opens 500 concurrent `requests.get(timeout=10)` threads. Combined with the `except Exception: pass` at `playlist_panel.py:515,519` and `main_window.py:551`, even internal bugs in resize/convert code are silently discarded. Fix: bound concurrency (a small fixed worker pool or one fetch-per-second `after` loop) and catch `requests.RequestException` specifically.

## Nits
- Dead code: `utils/ui_logger.py` (class `UILogger` has no caller anywhere), `utils/file_utils.py:35` (`safe_filename` unused — and it's a weaker copy of `sanitize_folder_name`), `ui/startup_check.py:12` (`self._result` never read). Fix: delete all three.
- `core/format_builder.py:20,33` — `"Best"` keys in `FORMAT_MAP`/`FORMAT_MAP_MP4` are unreachable: every lookup path lowercases `quality` and uses `"best"`. Fix: drop the two `"Best"` entries, keep `"best"`.
- `ui/playlist_panel.py:348` — `finish_download(self, completed, failed, total)` ignores all three arguments (body is just `self._enable_controls()`); `main_window.py:399,763` passes real counts that are discarded, and the summary message is instead built in `main_window`. Fix: either drop the parameters or use them (e.g. set the panel's status label to `نجح X / فشل Y (من Z)`).
- `ui/settings_dialog.py:126` — `self.config.get("cookies.source", "browser")` has a misleading default: the real merged default is `"none"` (`core/config_manager.py:32`), so the `"browser"` fallback can never fire. Fix: default to `"none"` for consistency.
- `app.py:52` — `except Exception: pass` on icon loading swallows everything, including scaling/format bugs in our own code. Fix: narrow to `OSError` (missing/corrupt icon file); a real bug should surface.
- `core/download_controller.py:199-210` + `core/format_builder.py:113` — cross-module convention coupling: `format_builder` emits `"js_runtimes": {"node": {}}` and `_build_argv` special-cases the `node` key to hard-code a `node.exe` path beside `ffmpeg`. Two files have to stay in agreement for this to work. Fix: have `format_builder` emit the resolved path (e.g. `{"node": {"path": str(bin_dir() / "node.exe")}}`) so `_build_argv`'s special-case disappears.
- `ui/main_window.py:141-310` — mixed row-number style: some rows use named constants (`_PLAYLIST_ROW`, `_LOGS_ROW`) while others are bare literals (`row=7` at line 220, `row=2` at line 172) with a comment explaining the floor values. Fix: give the video page's load-bearing rows the same named-constant treatment so the geometry stays adjustable in one place.
- `ui/progress_widget.py:48` — `import os` inside `update_progress`; the module has no other imports to protect, so hoist it to the top for consistency with every other file in the repo.

## What's good
- `core/config_manager.py` — atomic save (`tmp` + `os.replace`), malformed-config backup to `.bak`, and a migration path for legacy `data/` files: this is the correct posture for data that matters, and it's rare to see it this complete in a small app.
- `core/download_controller.py:31-46` — `_classify_error` + `_strip_ytdlp_report_suffix` give users an actionable, human-facing message instead of a raw stack line; that's the right way to handle the yt-dlp error surface.
- `ui/validators.py` — the explicit-playlist classification (separating `/playlist` from watch URLs that merely carry `list=`) is a subtle correctness call, well documented, and re-used consistently in `classify_url`.

## Coverage
- Section A (naming & functions): 2 findings — `finish_download` unused params (nit), display/load functions otherwise stay small; no generic identifiers of the banned set found.
- Section B (comments & formatting): `clean` — comments explain *why* (layout floors, scrollregion races) and match the Arabic/English mixed UI style; no paraphrasing or step-scaffolding found.
- Section C (SOLID): `clean` — no subclass-contract violations, no type-tag dispatch, no premature interfaces.
- Section D (DRY/KISS/YAGNI): 1 important (triplicated dep probe), plus dead-code nits (`UILogger`, `safe_filename`, `_result`, `"Best"` keys), `finish_download` parameter contract — each listed above.
- Section E (AI failure modes): 1 critical, 3 important — swallowed exceptions at the extraction boundary (mode 1), unconditional kill-on-success race, broad `except Exception` on `Popen` and thumbnails, unbounded thread spawn; no hardcoded success mocks, no hallucinated APIs (all customtkinter/yt-dlp calls match the installed surface), no dead branching beyond the nits.

Note: the app and its tests were not executed (`pytest.ini` exists; `tests/` cover every module). The `finally`-kill finding is timing-dependent and not reproduced — confirm on a real merge-heavy download before treating it as a confirmed bug.
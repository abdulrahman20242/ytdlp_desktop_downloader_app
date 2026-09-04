# PRD Diff — YT Downloader v2.0

## What Changed Between PRD and Actual Implementation

---

## 1. Architecture

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

**Fix:** Single `CTk` root. Both `StartupCheckFrame` and `MainWindow` are `CTkFrame` subclasses embedded in the same root. No `destroy()` on root until after `mainloop()` exits.

### Files changed:
- `app.py` — Complete rewrite
- `ui/main_window.py` — `class MainWindow(ctk.CTk)` → `class MainWindow(ctk.CTkFrame)`
- `ui/startup_check.py` — `class StartupCheckDialog(CTkToplevel)` → `class StartupCheckFrame(CTkFrame)`

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

**Reason:** customtkinter 5.2.2 does not include `CTkSeparator`. Replaced with 1px `tk.Frame`.

### Files changed:
- `ui/main_window.py` — 2 instances replaced

---

## 3. Format Selection

### Before (PRD):
```python
# Fallback chain: any available format
'best':  'bv*+ba/b',
'1080p': 'bv*[height<=1080]+ba/b[height<=1080]',

# No format_sort → yt-dlp picks av01 > vp9 > avc1
# Result: 398+251 (av01+opus)
```

### After (Implementation):
```python
# Fallback chain: mp4+m4a first
'best':  'bv[ext=mp4]+ba[ext=m4a]/bv+ba/b',
'1080p': 'bv[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]',

# format_sort → H.264 first
'format_sort': ['vcodec:h264,vp9,av01', 'res', 'br'],
# Result: 136+140 (avc1+m4a) ✅
```

### Files changed:
- `core/format_builder.py` — `FORMAT_MAP` and `FORMAT_MAP_MP4` updated, `get_common_opts()` now includes `format_sort`

---

## 4. Throttling Recovery

### Before (PRD):
Not specified — absent from the PRD.

### After (Implementation):
```python
'throttledratelimit': 102400  # 100 KB/s
```

When download speed drops below 100KB/s, yt-dlp automatically re-extracts video info to get fresh URLs. This fixes downloads that stall at 90%+ with ETA exceeding 30+ minutes.

### Files changed:
- `core/format_builder.py` — `get_common_opts()`

---

## 5. yt-dlp-ejs Integration

### Before (PRD):
```python
# Only android_vr as fallback
opts['extractor_args'] = {
    'youtube': {'player_client': ['android_vr', 'web_safari']}
}
# No js_runtimes
# No yt-dlp-ejs in requirements.txt
```

### After (Implementation):
```python
# Explicitly enable yt-dlp-ejs
opts['js_runtimes'] = {'node': {}}
opts['extractor_args'] = {'youtube-ejs': {}}

# android_vr kept as fallback
opts['extractor_args']['youtube'] = {
    'player_client': ['android_vr', 'web_safari']
}

# requirements.txt
yt-dlp-ejs>=0.8.0
```

### PATH in app.py:
```python
# Before: in get_common_opts() — too late, yt-dlp-ejs needs it at module load
# After: in app.py before any imports
os.environ["PATH"] = str(PROJECT_ROOT / "bin") + os.pathsep + os.environ.get("PATH", "")
```

### Files changed:
- `core/format_builder.py` — `get_common_opts()` + `extractor_args`
- `app.py` — PATH setup
- `requirements.txt` — New dependency

---

## 6. Cookie Handling

### Before (PRD):
```json
"cookies": {
    "source": "file",
    "browser": "chrome",
    "file_path": "data/cookies.txt"
}
```
Default was `"file"` — reads from `cookies.txt`.

### After (Implementation):
```json
"cookies": {
    "source": "none",
    ...
}
```
Default is now `"none"` — no cookies unless user explicitly enables them in Settings.

**Reason:** `Extracting cookies from chrome` fails with `Could not copy Chrome cookie database` when the browser is open. Regular users don't need cookies for most public videos.

### Error Handling:
```python
# Before: generic "download_error:..."
# After: clear user-friendly message
"Failed to extract cookies from browser — Close the browser or use a cookies file in Settings"
```

### Files changed:
- `core/config_manager.py` — Default changed
- `core/download_controller.py` — Cookie error handling added

---

## 7. DependencyChecker

### Before (PRD):
```python
class DependencyChecker:
    BIN_DIR = Path('bin')  # Relative path
    # No FFprobe check
    Node.js required = True
```

### After (Implementation):
```python
class DependencyChecker:
    BIN_DIR = Path(__file__).resolve().parent.parent / 'bin'  # Absolute path
    # + _check_ffprobe()
    Node.js required = False  # Optional - fallback to android_vr
```

### Files changed:
- `core/dep_checker.py` — `BIN_DIR` path, added `_check_ffprobe()`, Node.js optional

---

## 8. Startup Check Flow

### Before (PRD):
```python
def _run_checks(self):
    threading.Thread(target=check, daemon=True).start()
    # check() → self.after(0, self._display_results, results)
```
Threading + `after()` → `main thread is not in main loop` errors.

### After (Implementation):
```python
def _run_checks(self):
    checker = DependencyChecker()
    results = checker.check_all()
    self._display_results(results)
    self.update()
```
Synchronous — fast (just `--version` subprocess calls) + no threading issues.

### Files changed:
- `ui/startup_check.py` — Complete rewrite

---

## 9. Build Config (build.spec)

### Before (PRD):
```python
binaries=[
    ('bin/ffmpeg.exe', 'bin'),
    ('bin/ffprobe.exe', 'bin'),
    ('bin/node.exe', 'bin'),
],
```

### After (Implementation):
Same, but `yt-dlp.exe` is now in `bin/` (not in PyInstaller config — uses Python API, not the exe).

---

## 10. Additions Not in PRD

| Feature | PRD | Implementation |
|---|---|---|
| Format sort (H.264 preference) | ❌ | ✅ `format_sort: ["vcodec:h264,vp9,av01", "res", "br"]` |
| Throttling recovery | ❌ | ✅ `throttledratelimit: 102400` |
| yt-dlp-ejs js_runtimes | ❌ | ✅ `js_runtimes: {"node": {}}` |
| Cookie default "none" | ❌ (was "file") | ✅ |
| Cookie error message | ❌ | ✅ Clear Arabic message |
| FFprobe check | ❌ | ✅ `_check_ffprobe()` |
| Single-root architecture | ❌ | ✅ CTkFrame-based |
| Absolute bin paths | ❌ (relative) | ✅ `Path(__file__).resolve()` |
| PATH at app startup | ❌ | ✅ In `app.py` before all imports |
| Node.js optional | ❌ (required) | ✅ optional |

---

## Summary

**Key improvements over PRD:**
1. **Stability:** `invalid command name` errors eliminated (Single-Root Architecture)
2. **Compatibility:** `136+140` (avc1+m4a) instead of `398+251` (av01+opus)
3. **Speed:** Automatic throttling recovery
4. **Reliability:** yt-dlp-ejs properly configured and working
5. **UX:** Clear error messages in Arabic
6. **Robustness:** Absolute paths, PATH configured at startup

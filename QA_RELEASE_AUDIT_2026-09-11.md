# Pre-publication Release Audit — 2026-09-11

## A. Executive Verdict

**CONDITIONALLY READY**

The freshly built portable package starts, relocates, runs from arbitrary working directories, uses an onedir layout, and contains functioning bundled binaries. However, P2 recovery defects and a non-functional language setting remain. Real YouTube downloads, playlist processing, cancellation, and interactive settings testing are **BLOCKED** by this host's network policy and unavailable desktop automation—not passed.

## B. Test Statistics

```text
Total: 315
PASS: 315
FAIL: 0
BLOCKED: 0
N/A: 0
Warnings: 1 pytest cache-permission warning
Duration: 8.15s
```

The first unisolated run produced 249 passed / 66 setup errors because the inherited pytest temp directory was inaccessible. Re-running with a disposable project temp directory passed all 315 tests.

## C. Critical Findings

No confirmed P0 or P1 findings.

## D. Source Code Findings

### AUD-001

```text
ID: AUD-001
Classification: VERIFIED CODE BUG
Severity: P2 — Major
Area: Configuration recovery
File: core/config_manager.py:142
Function/Class: ConfigManager.set
Observed: A valid JSON config with a section stored as a scalar crashes on the first nested setting save.
Expected: Malformed configuration schema should be normalized, rejected, or recovered without crashing Settings.
Evidence: ConfigManager accepts {"download":"not-an-object"} in _merge(), then obj.setdefault("download", {}) returns a string and obj[keys[-1]] = value raises TypeError.
Reproduction: Created disposable %APPDATA%\YTDownloader\config.json containing {"download":"not-an-object"}; ConfigManager().set("download.default_dir", ...) exited 1 with TypeError.
Impact: Users with partially corrupted but valid JSON configuration cannot save settings.
Recommendation: Validate/normalize section types during load; make set() replace non-dict intermediate nodes safely.
Confidence: High
```

### AUD-002

```text
ID: AUD-002
Classification: VERIFIED CODE BUG
Severity: P2 — Major
Area: Dependency checker
File: core/dep_checker.py:83
Function/Class: DependencyChecker._check_ytdlp
Observed: The required yt-dlp check validates the embedded Python package, not bin\yt-dlp.exe used by downloads.
Expected: Startup Check must validate the exact bundled executable used by DownloadController.
Evidence: DownloadController launches bin\yt-dlp.exe at core/download_controller.py:281–283, while _check_ytdlp imports yt_dlp instead.
Reproduction: With an empty BIN_DIR and PATH, FFmpeg/FFprobe/Node reported missing but yt-dlp reported found through the installed Python module.
Impact: A damaged/missing yt-dlp.exe passes Startup Check, then downloads fail with an opaque Popen file-not-found error.
Recommendation: Probe bin\yt-dlp.exe --version and mark it required; keep the Python-package check separately if metadata extraction needs it.
Confidence: High
```

### AUD-003

```text
ID: AUD-003
Classification: VERIFIED CODE BUG
Severity: P2 — Major
Area: Settings / localization
File: ui/settings_dialog.py:47,155
Function/Class: SettingsDialog._load_config / _save
Observed: The language selector writes ui.language, but no application code reads it to change UI behavior.
Expected: Choosing English or Arabic should affect displayed UI text, or the control should not be presented.
Evidence: Repository search found ui.language only in ConfigManager defaults and SettingsDialog load/save.
Reproduction: Static trace of every ui.language reference.
Impact: A visible settings option is non-functional.
Recommendation: Implement locale resources and apply them, or remove/disable the selector until supported.
Confidence: High
```

### AUD-004

```text
ID: AUD-004
Classification: VERIFIED CODE BUG
Severity: P2 — Major
Area: Source-mode migration
File: data/config.json:10; core/config_manager.py:104–108
Function/Class: ConfigManager._migrate_legacy_user_data
Observed: First source-mode launch migrates a tracked developer-specific default directory into user configuration.
Expected: Public source-mode first run should use portable defaults, not a developer workstation path.
Evidence: data/config.json contains F:/projects/Python Projects/yt-dlp/ytdlp_desktop_downloader_app/downloads.
Reproduction: Fresh disposable APPDATA caused ConfigManager to copy that exact path into %APPDATA%\YTDownloader\config.json.
Impact: Source users inherit an invalid/unexpected output location. The released package is unaffected because data/ is not assembled into Release.
Recommendation: Remove/sanitize tracked legacy config before publication, or reject machine-specific legacy paths during migration.
Confidence: High
```

### AUD-005

```text
ID: AUD-005
Classification: VERIFIED CODE BUG
Severity: P2 — Major
Area: Configuration save errors / logging
File: core/config_manager.py:150–167; ui/settings_dialog.py:153–165
Function/Class: ConfigManager._save / SettingsDialog._save
Observed: Write failures are caught and only sent to an unconfigured logger; SettingsDialog then closes as if the save succeeded.
Expected: Failed settings persistence should remain visible to the user and keep the dialog recoverable.
Evidence: _save catches OSError and returns no result; SettingsDialog always calls destroy(). UILogger has no production references and no file logging is configured.
Reproduction: Code-path trace; existing test intentionally tolerates os.replace failure but does not test user feedback.
Impact: Settings can silently fail to persist on permission/disk errors.
Recommendation: Return success/failure from _save/set, show an error dialog, and configure durable application logging.
Confidence: High
```

### AUD-006

```text
ID: AUD-006
Classification: POTENTIAL RISK
Severity: P2 — Major
Area: Cancellation / process cleanup
File: core/download_controller.py:93–103
Function/Class: _terminate_tree
Observed: taskkill returning a nonzero exit code is treated as success; proc.terminate() is not attempted.
Expected: A failed taskkill should fall back to terminating the direct child and report failure if cleanup remains incomplete.
Evidence: subprocess.run() has no check=True and its return code is ignored before returning.
Reproduction: Code inspection; existing Windows test only simulates a zero exit code.
Impact: Under taskkill failure, yt-dlp/FFmpeg may remain running after cancellation or shutdown.
Recommendation: Check returncode; on failure call terminate(), then wait with a bounded timeout.
Confidence: High
```

## E. Build / Packaging Findings

The official build completed successfully: 315/315 tests passed, the .NET Framework 4.8 x64 launcher rebuilt, PyInstaller 6.20.0 produced an onedir core, the release was freshly assembled, and launcher self-test exited 0. Source/release bundled binary SHA-256 hashes matched.

PyInstaller warnings were inspected in a disposable build. They are dominated by optional platform-specific imports and static-analysis false positives from third-party packages. No warning was confirmed as a release-breaking missing runtime dependency; packaged GUI bootstrap succeeded.

### AUD-007

```text
ID: AUD-007
Classification: VERIFIED CODE BUG
Severity: P4 — Cosmetic
Area: Documentation / build claims
File: FAQ.md:121,139
Function/Class: N/A
Observed: FAQ claims PyInstaller uses --add-data for assets/bin and that Ruff is clean.
Expected: Documentation should match the actual build and static-check state.
Evidence: ytdownloader.spec has datas=[] and build_windows.ps1 manually copies assets/bin. python -m ruff check core utils ui tests app.py reports four E402 errors in app.py.
Reproduction: Executed the documented Ruff check and inspected spec/build script.
Impact: Misleading developer/release documentation; no direct packaged-runtime failure.
Recommendation: Correct FAQ wording and either add intentional E402 suppressions or stop claiming Ruff is clean.
Confidence: High
```

## F. Runtime Findings

- Packaged outer launcher: PASS — self-test exit 0.
- Relocated package: PASS — a copied package under a Unicode/space/parentheses path launched from `C:\Windows`.
- GUI startup: PASS — relocated core created a responsive `YT Downloader` window.
- No onefile extraction: PASS — isolated TEMP remained empty after launcher/core bootstrap.
- Real network operations: BLOCKED — bundled yt-dlp received `WinError 10013` connecting to YouTube.
- Interactive UI operation: BLOCKED — desktop automation runtime was unavailable and could not be started due local quota exhaustion.
- Clean-machine VM/profile: BLOCKED — no isolated Windows environment without developer dependencies was available.

## G. Functional Test Matrix

| Area | Result | Evidence |
|---|---:|---|
| Source execution | PASS | `python app.py` self-test from `C:\Windows` exited 0 |
| Unit tests | PASS | 315 passed |
| Path handling | PASS | Centralized frozen/source paths traced; relocation succeeded |
| Configuration | FAIL | AUD-001 and AUD-005 |
| Migration | FAIL | AUD-004 |
| Launcher | PASS | Outer launcher self-test exit 0 |
| CWD independence | PASS | Launcher verified from `C:\Windows` |
| Relocation | PASS | Unicode/space/parentheses relocation launched |
| No TEMP extraction | PASS | No payload entries created in isolated TEMP |
| Assets | PASS | logo.ico present and fresh |
| Dependency checker | FAIL | AUD-002 |
| yt-dlp | BLOCKED | Binary/version valid; real network probe blocked |
| FFmpeg | PASS | Bundled executable launched with expected version |
| FFprobe | PASS | Bundled executable launched with expected version |
| Node | PASS | Bundled Node 24.16.0 launched |
| yt-dlp-ejs | PASS | Packaged `yt_dlp_ejs` solver assets present |
| Single download | BLOCKED | Host blocks outbound YouTube sockets |
| All implemented download modes | BLOCKED | Network blocked before transfer |
| Playlist | BLOCKED | Network and interactive UI unavailable |
| Cancellation | BLOCKED | No real download could start |
| Error handling | FAIL | Config/dependency recovery defects confirmed |
| Cookies | BLOCKED | Path logic reviewed; interactive file/browser flow unavailable |
| Output paths | BLOCKED | Real output creation blocked by network |
| Restart | BLOCKED | Interactive UI automation unavailable |
| Process cleanup | BLOCKED | Real download/post-processing lifecycle unavailable |
| Clean build | PASS | Official build completed and rebuilt Release |
| Release integrity | PASS | Expected files, x64 PE architecture, matching hashes |
| Clean machine | BLOCKED | No clean Windows VM/profile available |

## H. Code Coverage Gaps

- No test for scalar/malformed nested config sections followed by Settings save.
- No test that Startup Check validates `bin\yt-dlp.exe`, rather than only `yt_dlp` Python importability.
- No test for nonzero `taskkill` fallback behavior.
- No built-release/launcher integration test in pytest.
- No real dependency execution or network download test.
- No real frozen-mode metadata, playlist, audio, video, MP4-only, cancellation, or restart tests.
- No migration test covering the actual tracked `data/config.json`.
- UI tests heavily stub CustomTkinter/Tkinter and do not exercise real control interactions.

## I. Exact Commands

```powershell
python -m pytest -q
python -m ruff check core utils ui tests app.py
cmd /c build_windows.bat
python -m PyInstaller --noconfirm --clean ytdownloader.spec --distpath <audit-dist> --workpath <audit-work>
Release\YT Downloader\bin\yt-dlp.exe --version
Release\YT Downloader\bin\ffmpeg.exe -version
Release\YT Downloader\bin\ffprobe.exe -version
Release\YT Downloader\bin\node.exe --version
Release\YT Downloader\bin\yt-dlp.exe --no-playlist --skip-download --print "%(id)s|%(title)s|%(duration)s" --ffmpeg-location <release-bin> --js-runtimes "node:<release-bin>\node.exe" https://www.youtube.com/watch?v=BaW_jenozKc
```

## J. Release Artifact

- Release path: `Release\`
- Launcher: `Release\YT Downloader.exe` — x64, 15,872 bytes
- Core: `Release\YT Downloader\YTDownloaderCore.exe` — x64, 15,828,368 bytes
- Bundled yt-dlp: 17,840,399 bytes, version `2026.08.19`
- Bundled FFmpeg: 101,704,192 bytes
- Bundled FFprobe: 101,499,904 bytes
- Bundled Node: 92,279,112 bytes, version `24.16.0`

## K. Remaining Risks

- Public download functionality remains unverified against live YouTube because this environment blocks outbound sockets.
- Playlist, post-processing, cancellation, and process-tree cleanup need real-machine execution before unconditional certification.
- Interactive Settings, controls, dialogs, and visual regressions need manual or restored desktop-automation QA.
- A clean Windows machine without Python/developer PATH was not available.
- Resolve AUD-001 through AUD-005 before publication; AUD-006 should be addressed before relying on cancellation guarantees.

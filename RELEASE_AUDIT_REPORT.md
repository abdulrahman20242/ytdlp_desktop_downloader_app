# Pre-publication Release Audit — 2026-09-11

## A. Executive Verdict

**CONDITIONALLY READY**

The fresh portable package starts, relocates, runs from arbitrary CWDs, uses an onedir layout, and contains functioning bundled binaries. However, recovery defects and a non-functional language setting remain. Real YouTube downloads, playlist processing, cancellation, and interactive settings testing are **BLOCKED**, not passed, by this host’s network policy and unavailable desktop automation.

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

The first unisolated run produced 249 passed / 66 setup errors because the inherited pytest temp directory was inaccessible. The isolated re-run passed all 315 tests.

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
Observed: A valid JSON config whose section is a scalar crashes on the first nested setting save.
Expected: Malformed configuration schema is normalized, rejected, or recovered without crashing Settings.
Evidence: _merge accepts {"download":"not-an-object"}; obj.setdefault("download", {}) then returns a string and item assignment raises TypeError.
Reproduction: A disposable %APPDATA%\YTDownloader\config.json containing {"download":"not-an-object"} caused ConfigManager().set("download.default_dir", ...) to exit 1 with TypeError.
Impact: A partially corrupted but valid JSON configuration prevents users from saving settings.
Recommendation: Validate/normalize section types during load and replace non-dict intermediate nodes safely in set().
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
Observed: The required yt-dlp check validates the Python package, not bin\yt-dlp.exe used for downloads.
Expected: Startup Check validates the exact bundled executable used by DownloadController.
Evidence: DownloadController launches bin\yt-dlp.exe at core/download_controller.py:281–283; _check_ytdlp imports yt_dlp instead.
Reproduction: With an empty BIN_DIR and PATH, FFmpeg/FFprobe/Node were missing but yt-dlp still reported found through the Python module.
Impact: A damaged/missing yt-dlp.exe passes Startup Check and later fails downloads with an opaque Popen file-not-found error.
Recommendation: Probe bin\yt-dlp.exe --version and mark it required; retain a separate Python-package check for metadata extraction.
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
Observed: The language selector writes ui.language, but no other application code reads it.
Expected: Choosing English or Arabic changes displayed UI text, or the selector is not presented.
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
Observed: First source-mode launch migrates a tracked developer-specific default directory into per-user configuration.
Expected: Public source-mode first run uses portable defaults, not a developer workstation path.
Evidence: data/config.json contains F:/projects/Python Projects/yt-dlp/ytdlp_desktop_downloader_app/downloads.
Reproduction: Fresh disposable APPDATA copied that exact path into %APPDATA%\YTDownloader\config.json.
Impact: Source users inherit an invalid/unexpected output location. The assembled Release is unaffected because data/ is not copied there.
Recommendation: Remove/sanitize tracked legacy config or reject machine-specific paths during migration.
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
Observed: Write failures are caught only by an unconfigured logger; SettingsDialog then closes as if the save succeeded.
Expected: Failed settings persistence is visible and leaves the dialog recoverable.
Evidence: _save catches OSError and returns no result; SettingsDialog always destroys itself. UILogger has no production references and no file logging is configured.
Reproduction: Code-path trace; the existing failure test does not test user feedback.
Impact: Settings can silently fail to persist on permission or disk errors.
Recommendation: Return success/failure from _save/set, show an error dialog, and configure durable logging.
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
Observed: taskkill returning a nonzero exit code is treated as success and proc.terminate() is not attempted.
Expected: A failed taskkill falls back to terminating the direct child and reports incomplete cleanup.
Evidence: subprocess.run() has no check=True and returncode is ignored before return.
Reproduction: Code inspection; the Windows test only simulates successful taskkill.
Impact: yt-dlp/FFmpeg may remain running after cancellation or shutdown if taskkill fails.
Recommendation: Check returncode; on failure call terminate() and wait with a bounded timeout.
Confidence: High
```

## E. Build / Packaging Findings

The official build completed successfully: 315 tests passed, the x64 .NET Framework 4.8 launcher rebuilt, PyInstaller 6.20.0 produced an onedir core, Release was reassembled, and the launcher self-test exited 0. Source and Release copies of the four bundled executables had matching SHA-256 hashes.

PyInstaller warnings were inspected in a disposable build. They were mainly optional platform imports and third-party static-analysis noise; no warning was confirmed as a release-breaking missing runtime dependency.

### AUD-007

```text
ID: AUD-007
Classification: VERIFIED CODE BUG
Severity: P4 — Cosmetic
Area: Documentation / build claims
File: FAQ.md:121,139
Function/Class: N/A
Observed: FAQ claims PyInstaller uses --add-data for assets/bin and that Ruff is clean.
Expected: Documentation matches the actual build and static-check state.
Evidence: ytdownloader.spec has datas=[]; build_windows.ps1 manually copies assets/bin. python -m ruff check core utils ui tests app.py reports four E402 errors in app.py.
Reproduction: Executed Ruff and inspected spec/build script.
Impact: Misleading developer/release documentation, with no direct packaged-runtime failure.
Recommendation: Correct FAQ wording and either add intentional E402 suppressions or stop claiming Ruff is clean.
Confidence: High
```

## F. Runtime Findings

- Outer launcher: PASS; self-test exit 0.
- Relocated package: PASS; launched from `C:\Windows` under a Unicode/space/parentheses path.
- GUI startup: PASS; a responsive `YT Downloader` core window was observed.
- No onefile extraction: PASS; isolated TEMP remained empty after bootstrap.
- Real network actions: BLOCKED; bundled yt-dlp received `WinError 10013` connecting to YouTube.
- Interactive UI operation: BLOCKED; desktop automation runtime was unavailable and could not be started due local quota exhaustion.
- Clean-machine VM/profile: BLOCKED; unavailable.

## G. Functional Test Matrix

| Area | Result | Evidence |
|---|---:|---|
| Source execution | PASS | `python app.py` self-test from `C:\Windows` exited 0 |
| Unit tests | PASS | 315 passed |
| Path handling | PASS | Centralized paths traced; relocation succeeded |
| Configuration | FAIL | AUD-001 and AUD-005 |

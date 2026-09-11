# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for the YTDownloaderCore payload.

Layout produced by the build pipeline (see build_windows.ps1)::

    Release\\YT Downloader\\YTDownloaderCore.exe   <- this bundle root
    Release\\YT Downloader\\_internal\\           <- Python run-time, modules
    Release\\YT Downloader\\bin\\                 <- yt-dlp/ffmpeg/ffprobe/node (copied by script)
    Release\\YT Downloader\\assets\\              <- icon/fonts (copied by script)

Resources live *next to* the executable (resolved by utils/paths.app_root),
never inside ``_internal``, so relocation keeps working.
"""

import os

icon = os.path.join(SPECPATH, "build_assets", "build", "logo.ico")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "test",
        "pytest",
        "unittest",
        "tcl8",
        "devscripts",
        "ytdlp_plugins",
        "bundle",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YTDownloaderCore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="YTDownloaderCore",
)
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for the YT Downloader application.

``app.py`` is frozen directly into the single release executable — there is no
outer launcher. The build pipeline (see build_windows.ps1) flattens the bundle
PyInstaller generates into ``dist\\YT Downloader`` into the final layout::

    Release\\YT Downloader.exe   <- this bundle root, the real application
    Release\\_internal\\         <- Python run-time, libraries, base_library.zip
    Release\\bin\\               <- yt-dlp/ffmpeg/ffprobe/node (copied by script)
    Release\\assets\\            <- icon/fonts (copied by script)

``bin`` and ``assets`` deliberately stay *next to* the executable rather than
inside ``_internal``: ``utils.paths.app_root()`` resolves them from the
executable's own directory, so the whole Release folder stays relocatable.
"""

import os

icon = os.path.join(SPECPATH, "build_assets", "build", "logo.ico")
if not os.path.exists(icon):
    try:
        import sys
        if SPECPATH not in sys.path:
            sys.path.insert(0, SPECPATH)
        from build_assets.make_icon import main as make_icon_main
        make_icon_main()
    except Exception:
        icon = None

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
    name="YT Downloader",
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
    name="YT Downloader",
)
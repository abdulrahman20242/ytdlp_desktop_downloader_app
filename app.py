#!/usr/bin/env python3
import os
import sys

# Resolve application paths from the executable location *before* importing
# anything else. In the frozen onedir build the resources live beside
# YTDownloaderCore.exe (never inside _internal), in a source checkout they
# live at the project root.
from utils.paths import assets_dir, bin_dir

app_root = bin_dir().parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

# Prepend bin/ to PATH before importing anything — guarantees node.exe is
# found when yt-dlp loads its bundled yt-dlp-ejs JavaScript solver.
os.environ["PATH"] = str(bin_dir()) + os.pathsep + os.environ.get("PATH", "")

import customtkinter as ctk  # noqa: E402
from core.config_manager import ConfigManager  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.startup_check import StartupCheckFrame  # noqa: E402


def main():
    config = ConfigManager()

    # Packaging self-test: when YTDLP_DESKTOP_SELFTEST is set the app performs
    # its imports/config bootstrap and exits with 0 — used by the build
    # pipeline to validate the frozen bundle without opening a GUI window.
    if os.environ.get("YTDLP_DESKTOP_SELFTEST"):
        return

    ctk.set_appearance_mode(config.get("ui.theme", "dark"))

    root = ctk.CTk()
    root.title("YT Downloader")
    w = config.get("ui.window_width", 800)
    h = config.get("ui.window_height", 600)
    root.geometry(f"{w}x{h}")
    root.minsize(700, 500)
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    try:
        logo = next(assets_dir().glob("*.ico"), None)
        if logo:
            root.iconbitmap(str(logo))
    except Exception:
        pass

    def on_startup_done():
        MainWindow(root, config)

    StartupCheckFrame(root, on_startup_done)
    root.mainloop()


if __name__ == "__main__":
    main()
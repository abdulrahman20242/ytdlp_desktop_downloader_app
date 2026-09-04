#!/usr/bin/env python3
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# أضف bin/ للـ PATH قبل أي شيء — يضمن العثور على node.exe وقت تحميل yt-dlp-ejs
os.environ["PATH"] = str(PROJECT_ROOT / "bin") + os.pathsep + os.environ.get("PATH", "")

import customtkinter as ctk
from core.config_manager import ConfigManager
from ui.startup_check import StartupCheckFrame
from ui.main_window import MainWindow


def main():
    config = ConfigManager()

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
        root.iconbitmap("assets/logo.ico")
    except Exception:
        pass

    def on_startup_done():
        MainWindow(root, config)

    StartupCheckFrame(root, on_startup_done)
    root.mainloop()


if __name__ == "__main__":
    main()

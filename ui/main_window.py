import customtkinter as ctk
import tkinter as tk
from pathlib import Path
import tkinter.filedialog as fd
from PIL import Image
from io import BytesIO
import requests

from ui.progress_widget import ProgressWidget
from ui.logs_panel import LogsPanel
from ui.quality_selector import QualitySelector
from ui.settings_dialog import SettingsDialog
from core.download_controller import DownloadController
from core.format_builder import build_format_opts, get_common_opts
from core.info_extractor import extract_info, get_available_qualities, extract_thumbnail, extract_title, extract_duration, extract_uploader
from utils.validators import is_valid_youtube_url
from utils.file_utils import open_folder


class MainWindow(ctk.CTkFrame):
    def __init__(self, master, config):
        super().__init__(master)
        self.master = master
        self.config = config
        self._controller = DownloadController(config)
        self._controller.set_app(master)
        self._current_info: dict | None = None
        self._current_save_dir: Path | None = None

        self.grid(sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_ui()
        self._setup_callbacks()
        self._load_config_state()
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        header = ctk.CTkLabel(
            self, text="YT Downloader", font=("", 20, "bold")
        )
        header.grid(row=0, column=0, pady=(15, 5))

        sub_header = ctk.CTkLabel(
            self, text="YouTube Video & Audio Downloader", font=("", 12),
            text_color="gray"
        )
        sub_header.grid(row=1, column=0, pady=(0, 10))

        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=5)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(7, weight=1)

        url_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        url_frame.grid(row=0, column=0, sticky="ew", pady=(10, 5))
        url_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(url_frame, text="رابط YouTube:").grid(row=0, column=0, padx=(5, 5))
        self._url_var = ctk.StringVar()
        self._url_var.trace_add("write", self._on_url_change)
        self._url_entry = ctk.CTkEntry(url_frame, textvariable=self._url_var)
        self._url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self._url_entry.bind("<Return>", lambda e: self._fetch_info())

        self._fetch_btn = ctk.CTkButton(
            url_frame, text="استعلام", width=80, command=self._fetch_info
        )
        self._fetch_btn.grid(row=0, column=2)

        info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", pady=5)
        info_frame.grid_columnconfigure(1, weight=1)

        self._title_label = ctk.CTkLabel(info_frame, text="", anchor="w", font=("", 13))
        self._title_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5)

        self._thumb_label = ctk.CTkLabel(info_frame, text="", width=160, height=90)
        self._thumb_label.grid(row=1, column=0, padx=5, pady=5)
        self._info_label = ctk.CTkLabel(info_frame, text="", anchor="w", justify="left")
        self._info_label.grid(row=1, column=1, sticky="nw", padx=5, pady=5)

        tk.Frame(main_frame, height=1, bg="#555").grid(row=2, column=0, sticky="ew", pady=8)

        self._quality_selector = QualitySelector(main_frame)
        self._quality_selector.grid(row=3, column=0, sticky="ew", pady=5)

        dir_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        dir_frame.grid(row=4, column=0, sticky="ew", pady=5)
        dir_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dir_frame, text="مجلد الحفظ:").grid(row=0, column=0, padx=(5, 5))
        self._dir_var = ctk.StringVar()
        self._dir_entry = ctk.CTkEntry(dir_frame, textvariable=self._dir_var)
        self._dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(dir_frame, text="تصفح", width=60, command=self._browse_dir).grid(row=0, column=2)

        action_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_frame.grid(row=5, column=0, sticky="ew", pady=10)

        self._download_btn = ctk.CTkButton(
            action_frame, text="⬇ تحميل", command=self._start_download,
            state="disabled", fg_color="#2d7a3a", hover_color="#236b2e",
            height=35, font=("", 13, "bold"),
        )
        self._download_btn.pack(side="left", padx=5)

        self._cancel_btn = ctk.CTkButton(
            action_frame, text="إلغاء", command=self._cancel_download,
            state="disabled"
        )
        self._cancel_btn.pack(side="left", padx=5)

        self._open_folder_btn = ctk.CTkButton(
            action_frame, text="📂 فتح المجلد", command=self._open_folder,
            state="disabled"
        )
        self._open_folder_btn.pack(side="left", padx=5)

        self._settings_btn = ctk.CTkButton(
            action_frame, text="⚙ إعدادات", command=self._open_settings
        )
        self._settings_btn.pack(side="right", padx=5)

        self._progress_widget = ProgressWidget(main_frame)
        self._progress_widget.grid(row=6, column=0, sticky="ew", pady=5)

        tk.Frame(main_frame, height=1, bg="#555").grid(row=7, column=0, sticky="ew", pady=0)

        self._logs_panel = LogsPanel(main_frame)
        self._logs_panel.grid(row=8, column=0, sticky="nsew", pady=5)

        status_bar = ctk.CTkLabel(self, text="جاهز", anchor="w", font=("", 10))
        status_bar.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 5))

    def _setup_callbacks(self):
        def on_progress(d):
            self._progress_widget.update_progress(d)

        def on_done():
            self._progress_widget.set_done()
            self._download_btn.configure(state="normal")
            self._cancel_btn.configure(state="disabled")
            self._open_folder_btn.configure(state="normal")
            self._fetch_btn.configure(state="normal")
            self._url_entry.configure(state="normal")
            self._logs_panel.append_log("[INFO] اكتمل التحميل بنجاح")

        def on_error(data):
            self._progress_widget.set_error(data)
            self._download_btn.configure(state="normal")
            self._cancel_btn.configure(state="disabled")
            self._fetch_btn.configure(state="normal")
            self._url_entry.configure(state="normal")
            self._logs_panel.append_log(f"[ERROR] {data}")

        def on_log(msg):
            self._logs_panel.append_log(msg)

        self._controller.on("progress", on_progress)
        self._controller.on("done", on_done)
        self._controller.on("error", on_error)
        self._controller.on("log", on_log)

    def _load_config_state(self):
        default_dir = self.config.get("download.default_dir", "")
        if default_dir:
            self._dir_var.set(default_dir)

    def _on_url_change(self, *_):
        url = self._url_var.get().strip()
        if is_valid_youtube_url(url):
            self._fetch_btn.configure(state="normal")
        else:
            self._fetch_btn.configure(state="disabled")

    def _fetch_info(self):
        url = self._url_var.get().strip()
        if not url:
            return

        self._fetch_btn.configure(state="disabled", text="جارٍ...")
        self._title_label.configure(text="جارٍ استخراج المعلومات...")
        self._info_label.configure(text="")

        def fetch():
            info = extract_info(url)
            self.after(0, self._display_info, info)

        import threading
        threading.Thread(target=fetch, daemon=True).start()

    def _display_info(self, info: dict | None):
        self._fetch_btn.configure(state="normal", text="استعلام")

        if not info:
            self._title_label.configure(text="❌ فشل استخراج المعلومات — تحقق من الرابط")
            self._download_btn.configure(state="disabled")
            return

        self._current_info = info
        title = extract_title(info)
        self._title_label.configure(text=f"🎬 {title}")

        duration = extract_duration(info)
        mins, secs = divmod(duration, 60)
        uploader = extract_uploader(info) or "غير معروف"
        self._info_label.configure(
            text=f"القناة: {uploader}\nالمدة: {mins}:{secs:02d}"
        )

        qualities = get_available_qualities(self._url_var.get().strip())
        self._quality_selector.set_qualities(qualities)

        thumb_url = extract_thumbnail(info)
        if thumb_url:
            self._load_thumbnail(thumb_url)

        self._download_btn.configure(state="normal")

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

        import threading
        threading.Thread(target=load, daemon=True).start()

    def _browse_dir(self):
        path = fd.askdirectory(
            title="اختر مجلد الحفظ",
            initialdir=self._dir_var.get() or str(Path.home() / "Downloads")
        )
        if path:
            self._dir_var.set(path)
            self.config.set("download.default_dir", path)

    def _on_close(self):
        current = self._dir_var.get().strip()
        saved = self.config.get("download.default_dir", "")
        if current and current != saved:
            self.config.set("download.default_dir", current)
        self.master.destroy()

    def _start_download(self):
        url = self._url_var.get().strip()
        if not url:
            return

        save_dir = Path(self._dir_var.get() or "downloads")
        save_dir.mkdir(parents=True, exist_ok=True)
        self._current_save_dir = save_dir

        quality = self._quality_selector.quality
        mode = self._quality_selector.mode

        base_opts = get_common_opts("bin", self.config)
        format_opts = build_format_opts(quality, mode)
        opts = {**base_opts, **format_opts}

        cookies_source = self.config.get("cookies.source", "none")
        if cookies_source == "browser":
            browser = self.config.get("cookies.browser", "chrome")
            opts["cookiesfrombrowser"] = (browser,)
        elif cookies_source == "file":
            cookie_path = Path(self.config.get("cookies.file_path", "data/cookies.txt"))
            if cookie_path.exists():
                opts["cookiefile"] = str(cookie_path)

        if self.config.get("advanced.sponsorblock_remove", False):
            opts["sponsorblock_remove"] = self.config.get("advanced.sponsorblock_categories", ["sponsor"])

        self._progress_widget.reset()
        self._logs_panel.append_log(f"[INFO] بدء التحميل: {url}")
        self._logs_panel.append_log(f"[INFO] الجودة: {quality} | الوضع: {mode}")

        self._download_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._fetch_btn.configure(state="disabled")
        self._url_entry.configure(state="disabled")
        self._open_folder_btn.configure(state="disabled")

        self._controller.start_download(url, opts, save_dir)

    def _cancel_download(self):
        self._controller.cancel()
        self._logs_panel.append_log("[INFO] تم إلغاء التحميل")
        self._progress_widget.reset()
        self._download_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._fetch_btn.configure(state="normal")
        self._url_entry.configure(state="normal")

    def _open_folder(self):
        if self._current_save_dir and self._current_save_dir.exists():
            open_folder(self._current_save_dir)

    def _open_settings(self):
        SettingsDialog(self.master, self.config)

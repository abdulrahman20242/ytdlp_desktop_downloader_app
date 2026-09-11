import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as messagebox
import threading
from pathlib import Path
import tkinter.filedialog as fd
from PIL import Image
from io import BytesIO
import requests

from ui.progress_widget import ProgressWidget
from ui.logs_panel import LogsPanel
from ui.quality_selector import QualitySelector
from ui.settings_dialog import SettingsDialog
from ui.playlist_panel import PlaylistPanel
from core.download_controller import DownloadController
from core.format_builder import build_format_opts, get_common_opts
from core.info_extractor import (
    extract_info, qualities_from_info,
    extract_thumbnail, extract_title, extract_duration, extract_uploader,
    extract_playlist,
)
from utils.validators import is_valid_youtube_url, classify_url
from utils.file_utils import (
    open_folder,
    sanitize_folder_name,
    get_downloads_dir,
    ensure_dir,
)
from utils.paths import bin_dir, cookies_path

# Name of the two pages inside the single ``CTkTabview``.
_VIDEO_TAB = "تحميل الفيديو"
_PLAYLIST_TAB = "Playlist"
# Which page currently owns the shared download controller.
_RUN_VIDEO = "video"
_RUN_PLAYLIST = "playlist"

# Rows inside the playlist page's content frame that carry flexible weight:
# the PlaylistPanel (row 2) and the LogsPanel (row 8).
_PLAYLIST_ROW = 2
_LOGS_ROW = 8
# Flexible-space split inside the playlist page: the playlist list gets more
# of any slack (2 parts) than the logs (1 part) so the playlist keeps its size
# advantage, while the logs still grow on tall windows.
_PLAYLIST_ROW_WEIGHT = 2
_LOGS_ROW_WEIGHT = 1
# Hard floors (screen px) kept on both flexible rows of the playlist page so
# neither collapses to zero on short windows.  They match the measured
# internal structure at the default 800x600 / 125% window: the playlist floor
# covers the compact header + toolbar + roughly two media rows, and the logs
# floor keeps the panel header plus ~4 text lines.  On very short windows each
# row stops at its floor and the list/logs scroll internally instead.
_PLAYLIST_MIN_HEIGHT = 244
_LOGS_MIN_HEIGHT = 126
# Rows on the outer window: the TabView should be the only flexible row so any
# extra window height feeds the active page instead of the near-empty status
# bar.
_TABVIEW_ROW = 2
_STATUS_ROW = 3


class MainWindow(ctk.CTkFrame):
    def __init__(self, master, config):
        super().__init__(master)
        self.master = master
        self.config = config
        self._controller = DownloadController(config)
        self._controller.set_app(master)
        self._current_info: dict | None = None
        self._current_video_dir: Path | None = None
        self._current_playlist_dir: Path | None = None
        self._current_playlist: dict | None = None
        self._playlist_run: dict = {"completed": 0, "failed": 0, "total": 0}
        self._active_page = _VIDEO_TAB
        self._active_run: str | None = None

        # Anchor explicitly to the root's single grid cell (row 0 / column 0).
        # ``StartupCheckFrame`` still occupies that cell while ``MainWindow`` is
        # constructed, and ``grid(sticky=...)`` without ``row``/``column`` would
        # otherwise auto-place this frame one row below it.  The root keeps its
        # flexible weight on row 0, so an empty row 0 above it would swallow all
        # slack and push the whole window content downward.
        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(_TABVIEW_ROW, weight=1)
        self.grid_rowconfigure(_STATUS_ROW, weight=0)

        self._build_ui()
        self._setup_callbacks()
        self._load_config_state()
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    #  UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        header = ctk.CTkLabel(
            self, text="YT Downloader", font=("", 20, "bold")
        )
        header.grid(row=0, column=0, pady=(5, 2))

        sub_header = ctk.CTkLabel(
            self, text="YouTube Video & Audio Downloader", font=("", 12),
            text_color="gray"
        )
        sub_header.grid(row=1, column=0, pady=(0, 3))

        self._tabview = ctk.CTkTabview(self, command=self._on_tab_changed)
        self._tabview.grid(
            row=_TABVIEW_ROW, column=0, sticky="nsew", padx=15, pady=4,
        )

        self._video_tab = self._tabview.add(_VIDEO_TAB)
        self._video_tab.grid_columnconfigure(0, weight=1)
        self._video_tab.grid_rowconfigure(7, weight=1)

        self._playlist_tab = self._tabview.add(_PLAYLIST_TAB)
        self._playlist_tab.grid_columnconfigure(0, weight=1)
        self._playlist_tab.grid_rowconfigure(
            _PLAYLIST_ROW, weight=_PLAYLIST_ROW_WEIGHT,
            minsize=_PLAYLIST_MIN_HEIGHT,
        )
        self._playlist_tab.grid_rowconfigure(
            _LOGS_ROW, weight=_LOGS_ROW_WEIGHT, minsize=_LOGS_MIN_HEIGHT,
        )

        self._build_video_page(self._video_tab)
        self._build_playlist_page(self._playlist_tab)

        self._tabview.set(_VIDEO_TAB)
        self._active_page = _VIDEO_TAB

        self._status_bar = ctk.CTkLabel(self, text="جاهز", anchor="w", font=("", 10))
        self._status_bar.grid(
            row=_STATUS_ROW, column=0, sticky="ew", padx=15, pady=(0, 3),
        )

    def _build_video_page(self, page):
        url_frame = ctk.CTkFrame(page, fg_color="transparent")
        url_frame.grid(row=0, column=0, sticky="ew", pady=(1, 0))
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

        info_frame = ctk.CTkFrame(page, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", pady=5)
        info_frame.grid_columnconfigure(1, weight=1)
        self._info_frame = info_frame

        self._title_label = ctk.CTkLabel(info_frame, text="", anchor="w", font=("", 13))
        self._title_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5)

        self._thumb_label = ctk.CTkLabel(info_frame, text="", width=160, height=90)
        self._thumb_label.grid(row=1, column=0, padx=5, pady=5)
        self._info_label = ctk.CTkLabel(info_frame, text="", anchor="w", justify="left")
        self._info_label.grid(row=1, column=1, sticky="nw", padx=5, pady=5)

        self._quality_selector = QualitySelector(page)
        self._quality_selector.grid(row=2, column=0, sticky="ew", pady=1)

        dir_frame = ctk.CTkFrame(page, fg_color="transparent")
        dir_frame.grid(row=3, column=0, sticky="ew", pady=1)
        dir_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dir_frame, text="مجلد الحفظ:").grid(row=0, column=0, padx=(5, 5))
        self._dir_var = ctk.StringVar()
        self._dir_entry = ctk.CTkEntry(dir_frame, textvariable=self._dir_var)
        self._dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(
            dir_frame, text="تصفح", width=60,
            command=lambda: self._browse_dir(self._dir_var),
        ).grid(row=0, column=2)

        action_frame = ctk.CTkFrame(page, fg_color="transparent")
        action_frame.grid(row=4, column=0, sticky="ew", pady=2)

        self._download_btn = ctk.CTkButton(
            action_frame, text="⬇ تحميل", command=self._start_download,
            state="disabled", fg_color="#2d7a3a", hover_color="#236b2e",
            height=32, font=("", 13, "bold"),
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

        self._video_progress = ProgressWidget(page)
        self._video_progress.grid(row=5, column=0, sticky="ew", pady=1)

        tk.Frame(page, height=1, bg="#555").grid(row=6, column=0, sticky="ew", pady=0)

        self._video_logs = LogsPanel(page)
        self._video_logs.grid(row=7, column=0, sticky="nsew", pady=4)

    def _build_playlist_page(self, page):
        pl_url_frame = ctk.CTkFrame(page, fg_color="transparent")
        pl_url_frame.grid(row=0, column=0, sticky="ew", pady=(1, 0))
        pl_url_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(pl_url_frame, text="رابط القائمة:").grid(row=0, column=0, padx=(5, 5))
        self._playlist_url_var = ctk.StringVar()
        self._playlist_url_entry = ctk.CTkEntry(
            pl_url_frame, textvariable=self._playlist_url_var
        )
        self._playlist_url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self._playlist_url_entry.bind("<Return>", lambda e: self._fetch_playlist())

        self._playlist_fetch_btn = ctk.CTkButton(
            pl_url_frame, text="استعلام", width=80, command=self._fetch_playlist
        )
        self._playlist_fetch_btn.grid(row=0, column=2)

        self._playlist_msg_label = ctk.CTkLabel(
            page, text="", anchor="w", font=("", 11),
            text_color="#ffb84d",
        )
        self._playlist_msg_label.grid(row=1, column=0, sticky="ew", padx=5, pady=(1, 0))

        self._playlist_panel = PlaylistPanel(
            page,
            on_download_all=lambda: self._start_playlist_download(
                list(self._current_playlist.get("entries", []))
                if self._current_playlist else []
            ),
            on_download_selected=lambda: self._start_playlist_download(
                self._playlist_panel.selected_entries()
            ),
        )
        self._playlist_panel.grid(row=_PLAYLIST_ROW, column=0, sticky="nsew", pady=(0, 2))
        self._playlist_panel.set_playlist({"entries": []})

        self._playlist_quality_selector = QualitySelector(page)
        self._playlist_quality_selector.grid(row=3, column=0, sticky="ew", pady=1)

        pl_dir_frame = ctk.CTkFrame(page, fg_color="transparent")
        pl_dir_frame.grid(row=4, column=0, sticky="ew", pady=1)
        pl_dir_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(pl_dir_frame, text="مجلد الحفظ:").grid(row=0, column=0, padx=(5, 5))
        self._playlist_dir_var = ctk.StringVar()
        self._playlist_dir_entry = ctk.CTkEntry(
            pl_dir_frame, textvariable=self._playlist_dir_var
        )
        self._playlist_dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(
            pl_dir_frame, text="تصفح", width=60,
            command=lambda: self._browse_dir(self._playlist_dir_var),
        ).grid(row=0, column=2)

        pl_action_frame = ctk.CTkFrame(page, fg_color="transparent")
        pl_action_frame.grid(row=5, column=0, sticky="ew", pady=2)

        self._playlist_download_btn = ctk.CTkButton(
            pl_action_frame, text="⬇ تنزيل القائمة",
            command=self._start_playlist_download_all,
            fg_color="#2d7a3a", hover_color="#236b2e",
            height=32, font=("", 13, "bold"),
        )
        self._playlist_download_btn.pack(side="left", padx=5)

        self._playlist_cancel_btn = ctk.CTkButton(
            pl_action_frame, text="إلغاء", command=self._cancel_download,
            state="disabled"
        )
        self._playlist_cancel_btn.pack(side="left", padx=5)

        self._playlist_open_folder_btn = ctk.CTkButton(
            pl_action_frame, text="📂 فتح المجلد",
            command=self._open_playlist_folder, state="disabled"
        )
        self._playlist_open_folder_btn.pack(side="left", padx=5)

        ctk.CTkButton(
            pl_action_frame, text="⚙ إعدادات", command=self._open_settings
        ).pack(side="right", padx=5)

        self._playlist_progress = ProgressWidget(page)
        self._playlist_progress.grid(row=6, column=0, sticky="ew", pady=1)

        tk.Frame(page, height=1, bg="#555").grid(row=7, column=0, sticky="ew", pady=0)

        self._playlist_logs = LogsPanel(page)
        self._playlist_logs.grid(row=_LOGS_ROW, column=0, sticky="nsew", pady=4)
        # Pin the playlist page's logs request to its floor so the grid shrink
        # pass can't cut through it on short windows; the playlist row then
        # always keeps room for at least two media rows.
        self._playlist_logs.set_natural_height(_LOGS_MIN_HEIGHT)

        mode = self.config.get("download.default_mode", "video")
        quality = self.config.get("download.default_quality", "1080p")
        self._playlist_quality_selector.apply_defaults(mode, quality)
        default_dir = self.config.get("download.default_dir", "")
        if default_dir:
            self._playlist_dir_var.set(default_dir)

    def _on_tab_changed(self, *_):
        self._active_page = self._tabview.get()
        if self._active_page == _PLAYLIST_TAB:
            # Re-sync the playlist scroll region after the tab becomes visible.
            self._playlist_panel.show()

    # ------------------------------------------------------------------ #
    #  Controller callbacks
    # ------------------------------------------------------------------ #

    def _setup_callbacks(self):
        def on_progress(d):
            if self._active_run is None:
                return
            progress, logs = self._page_widgets(self._active_run)
            progress.update_progress(d)

        def on_done():
            run = self._active_run
            self._active_run = None
            progress, logs = self._page_widgets(run or _RUN_VIDEO)
            progress.set_done()
            logs.append_log("[INFO] اكتمل التحميل بنجاح")
            if run == _RUN_PLAYLIST:
                self._restore_playlist_ui()
            else:
                self._restore_video_ui()

        def on_error(data):
            run = self._active_run
            self._active_run = None
            progress, logs = self._page_widgets(run or _RUN_VIDEO)
            progress.set_error(data)
            logs.append_log(f"[ERROR] {data}")
            if run == _RUN_PLAYLIST:
                self._restore_playlist_ui()
            else:
                self._restore_video_ui()

        def on_log(msg):
            if self._active_run is None:
                return
            progress, logs = self._page_widgets(self._active_run)
            logs.append_log(msg)

        def on_playlist_item(data):
            self._playlist_panel.update_item(
                data.get("index"), data.get("status", ""), data.get("error"),
            )
            total = data.get("total", 0)
            position = data.get("position", 0)
            if data.get("status") == "downloading":
                self._playlist_progress.reset()
                self._playlist_progress.set_message(
                    f"الفيديو {position} من {total} — جارٍ التنزيل…"
                )
                self._playlist_run["total"] = total
            elif data.get("status") == "completed":
                self._playlist_run["completed"] += 1
                self._playlist_logs.append_log(
                    f"[INFO] playlist: الفيديو {data.get('index')} تم بنجاح"
                )
            elif data.get("status") == "failed":
                self._playlist_run["failed"] += 1
                err = data.get("error") or "خطأ"
                self._playlist_logs.append_log(
                    f"[ERROR] playlist: الفيديو {data.get('index')} فشل — {err}"
                )

        def on_playlist_done():
            s = self._playlist_run
            total = s.get("total", 0)
            self._playlist_progress.set_done()
            self._playlist_progress.set_message(
                f"اكتملت القائمة ✓ — نجح {s['completed']} / فشل {s['failed']} (من {total})"
            )
            self._playlist_panel.finish_download(
                s["completed"], s["failed"], total,
            )
            self._restore_playlist_ui()
            self._playlist_run = {"completed": 0, "failed": 0, "total": 0}
            self._active_run = None

        self._controller.on("progress", on_progress)
        self._controller.on("done", on_done)
        self._controller.on("error", on_error)
        self._controller.on("log", on_log)
        self._controller.on("playlist_item", on_playlist_item)
        self._controller.on("playlist_done", on_playlist_done)

    def _page_widgets(self, run: str):
        if run == _RUN_VIDEO:
            return self._video_progress, self._video_logs
        return self._playlist_progress, self._playlist_logs

    # ------------------------------------------------------------------ #
    #  Config / defaults
    # ------------------------------------------------------------------ #

    def _load_config_state(self):
        default_dir = self.config.get("download.default_dir", "")
        if default_dir:
            self._dir_var.set(default_dir)

        mode = self.config.get("download.default_mode", "video")
        quality = self.config.get("download.default_quality", "1080p")
        self._quality_selector.apply_defaults(mode, quality)

    def _on_url_change(self, *_):
        url = self._url_var.get().strip()
        if is_valid_youtube_url(url):
            self._fetch_btn.configure(state="normal")
        else:
            self._fetch_btn.configure(state="disabled")

    # ------------------------------------------------------------------ #
    #  Extraction
    # ------------------------------------------------------------------ #

    def _fetch_info(self):
        url = self._url_var.get().strip()
        if not url:
            return

        if classify_url(url) == "playlist":
            self._route_to_playlist(url)
            return

        self._fetch_btn.configure(state="disabled", text="جارٍ...")
        self._title_label.configure(text="جارٍ استخراج المعلومات...")
        self._info_label.configure(text="")
        self._download_btn.configure(state="disabled")

        def fetch():
            info = extract_info(url)
            # Derive the quality list here, in the worker thread, so the UI
            # thread never performs a second slow extraction (the old path
            # called get_available_qualities() inside _display_info).
            qualities = qualities_from_info(info)
            self.after(0, self._display_info, info, qualities)

        threading.Thread(target=fetch, daemon=True).start()

    def _route_to_playlist(self, url: str):
        self._playlist_url_var.set(url)
        self._tabview.set(_PLAYLIST_TAB)
        self._active_page = _PLAYLIST_TAB
        self._playlist_panel.show()
        self._fetch_playlist()

    def _fetch_playlist(self):
        url = self._playlist_url_var.get().strip()
        if not url:
            return

        if classify_url(url) != "playlist":
            self._playlist_msg_label.configure(
                text="⚠ الرابط ليس قائمة تشغيل — استخدم رابط /playlist?list=..."
            )
            return

        self._playlist_msg_label.configure(text="")
        self._playlist_fetch_btn.configure(state="disabled", text="جارٍ...")
        self._playlist_panel.set_playlist({"entries": []})
        self._playlist_download_btn.configure(state="disabled")

        def fetch():
            data = extract_playlist(url)
            self.after(0, self._display_playlist, data)

        threading.Thread(target=fetch, daemon=True).start()

    def _display_info(self, info: dict | None, qualities: list[str] | None = None):
        self._fetch_btn.configure(state="normal", text="استعلام")

        if qualities is None:
            qualities = ["Best"]

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

        qualities = qualities or ["Best"]
        self._quality_selector.set_qualities(qualities)

        thumb_url = extract_thumbnail(info)
        if thumb_url:
            self._load_thumbnail(thumb_url)

        self._download_btn.configure(state="normal")

    def _display_playlist(self, playlist: dict | None):
        self._playlist_fetch_btn.configure(state="normal", text="استعلام")

        if not playlist or not playlist.get("entries"):
            self._playlist_msg_label.configure(
                text="❌ فشل استخراج القائمة — تحقق من الرابط"
            )
            self._playlist_download_btn.configure(state="disabled")
            return

        self._current_playlist = playlist
        self._playlist_msg_label.configure(text="")
        self._playlist_panel.set_playlist(playlist)
        self._playlist_panel.show()
        self._playlist_download_btn.configure(state="normal")

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

    # ------------------------------------------------------------------ #
    #  Directories / settings
    # ------------------------------------------------------------------ #

    def _browse_dir(self, var):
        path = fd.askdirectory(
            title="اختر مجلد الحفظ",
            initialdir=var.get() or str(Path.home() / "Downloads")
        )
        if path:
            var.set(path)
            self.config.set("download.default_dir", path)

    def _on_close(self):
        saved = self.config.get("download.default_dir", "")
        for var in (self._dir_var, self._playlist_dir_var):
            current = var.get().strip()
            if current and current != saved:
                self.config.set("download.default_dir", current)
                break
        # Kill any active yt-dlp/ffmpeg tree and drain the worker before the
        # window goes away, so closing mid-download leaves no orphans behind.
        self._controller.shutdown()
        self.master.destroy()

    def _open_settings(self):
        saved = self.config.get("download.default_dir", "")
        for var in (self._dir_var, self._playlist_dir_var):
            current = var.get().strip()
            if current and current != saved:
                self.config.set("download.default_dir", current)
                saved = current
        dialog = SettingsDialog(self.master, self.config)
        self.wait_window(dialog)
        saved_dir = self.config.get("download.default_dir", "")
        for var in (self._dir_var, self._playlist_dir_var):
            if saved_dir and var.get().strip() != saved_dir:
                var.set(saved_dir)

    # ------------------------------------------------------------------ #
    #  Download options / execution
    # ------------------------------------------------------------------ #

    def _build_download_opts(self, selector=None):
        selector = selector or self._quality_selector
        quality = selector.quality
        mode = selector.mode

        base_opts = get_common_opts(bin_dir(), self.config)
        format_opts = build_format_opts(quality, mode, self.config)
        opts = {**base_opts, **format_opts}

        cookies_source = self.config.get("cookies.source", "none")
        if cookies_source == "browser":
            browser = self.config.get("cookies.browser", "chrome")
            opts["cookiesfrombrowser"] = (browser,)
        elif cookies_source == "file":
            cookie_path = Path(self.config.get("cookies.file_path", str(cookies_path())))
            if not cookie_path.is_absolute():
                cookie_path = cookies_path()
            if cookie_path.exists():
                opts["cookiefile"] = str(cookie_path)

        if self.config.get("advanced.sponsorblock_remove", False):
            opts["sponsorblock_remove"] = self.config.get("advanced.sponsorblock_categories", ["sponsor"])

        return opts, quality, mode

    def _prepare_video_ui(self):
        self._video_progress.reset()
        self._download_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._fetch_btn.configure(state="disabled")
        self._url_entry.configure(state="disabled")
        self._open_folder_btn.configure(state="disabled")

    def _restore_video_ui(self):
        self._download_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._open_folder_btn.configure(state="normal")
        self._fetch_btn.configure(state="normal")
        self._url_entry.configure(state="normal")

    def _prepare_playlist_ui(self):
        self._playlist_progress.reset()
        self._playlist_download_btn.configure(state="disabled")
        self._playlist_cancel_btn.configure(state="normal")
        self._playlist_fetch_btn.configure(state="disabled")
        self._playlist_url_entry.configure(state="disabled")
        self._playlist_open_folder_btn.configure(state="disabled")

    def _restore_playlist_ui(self):
        self._playlist_download_btn.configure(state="normal")
        self._playlist_cancel_btn.configure(state="disabled")
        self._playlist_open_folder_btn.configure(state="normal")
        self._playlist_fetch_btn.configure(state="normal")
        self._playlist_url_entry.configure(state="normal")

    def _resolve_dir(self, var, log=None) -> Path:
        raw = var.get().strip()
        if not raw:
            raw = self.config.get("download.default_dir", "")
        save_dir = Path(raw or get_downloads_dir())
        try:
            return ensure_dir(save_dir)
        except OSError as e:
            fallback = self._fallback_save_dir()
            msg = f"تعذّر إنشاء مجلد الحفظ «{save_dir}» — سيتم الحفظ في «{fallback}»"
            if log is not None:
                log.append_log(f"[ERROR] {msg} ({e})")
            messagebox.showwarning("مجلد الحفظ", f"{msg}\n\n{type(e).__name__}: {e}")
            return fallback

    def _fallback_save_dir(self) -> Path:
        fb = get_downloads_dir()
        try:
            return ensure_dir(fb)
        except OSError:
            return fb

    def _resolve_save_dir(self) -> Path:
        return self._resolve_dir(self._dir_var, getattr(self, "_video_logs", None))

    def _playlist_save_dir(self, base: Path) -> Path:
        """Subfolder named after the playlist inside the chosen destination."""
        title = (self._current_playlist or {}).get("title") or ""
        folder = sanitize_folder_name(title, fallback="Playlist")
        target = base / folder
        try:
            return ensure_dir(target)
        except OSError as e:
            msg = f"تعذّر إنشاء مجلد القائمة «{target}» — سيتم الحفظ مباشرة في «{base}»"
            self._playlist_logs.append_log(f"[ERROR] {msg} ({e})")
            messagebox.showwarning("مجلد القائمة", f"{msg}\n\n{type(e).__name__}: {e}")
            return base

    def _start_download(self):
        if self._controller.is_downloading():
            self._video_logs.append_log("[INFO] يوجد تحميل جارٍ — انتظر انتهاءه ثم أعد المحاولة")
            return

        url = self._url_var.get().strip()
        if not url:
            return

        save_dir = self._resolve_save_dir()
        self._current_video_dir = save_dir

        opts, quality, mode = self._build_download_opts()

        self._active_run = _RUN_VIDEO
        self._video_logs.append_log(f"[INFO] بدء التحميل: {url}")
        self._video_logs.append_log(f"[INFO] الجودة: {quality} | الوضع: {mode}")
        if "list=" in url:
            self._video_logs.append_log(
                "[INFO] الرابط يحتوي على قائمة تشغيل — سيتم تنزيل الفيديو فقط"
            )

        self._prepare_video_ui()
        self._controller.start_download(url, opts, save_dir)

    def _start_playlist_download_all(self):
        self._start_playlist_download(
            list(self._current_playlist.get("entries", []))
            if self._current_playlist else []
        )

    def _start_playlist_download(self, entries: list[dict]):
        if self._controller.is_downloading():
            self._playlist_logs.append_log("[INFO] يوجد تحميل جارٍ — انتظر انتهاءه ثم أعد المحاولة")
            return

        if not entries:
            self._playlist_logs.append_log("[INFO] لا توجد مقاطع محددة")
            return

        save_dir = self._resolve_dir(self._playlist_dir_var, self._playlist_logs)
        if self._current_playlist:
            save_dir = self._playlist_save_dir(save_dir)
        self._current_playlist_dir = save_dir

        opts, quality, mode = self._build_download_opts(self._playlist_quality_selector)

        self._active_run = _RUN_PLAYLIST
        self._playlist_run = {"completed": 0, "failed": 0, "total": len(entries)}
        self._playlist_progress.reset()
        title = (self._current_playlist or {}).get("title") or "قائمة التشغيل"
        self._playlist_logs.append_log(
            f"[INFO] بدء تنزيل القائمة «{title}»: {len(entries)} فيديو"
        )
        self._playlist_logs.append_log(f"[INFO] الوجهة: {save_dir}")
        self._playlist_logs.append_log(f"[INFO] الجودة: {quality} | الوضع: {mode}")

        subset_indices = [e.get("index", i + 1) for i, e in enumerate(entries)]
        self._playlist_panel.begin_download(subset_indices)
        self._prepare_playlist_ui()
        self._playlist_open_folder_btn.configure(state="normal")

        self._controller.start_playlist_download(entries, opts, save_dir)

    def _cancel_download(self):
        self._controller.cancel()
        run = self._active_run
        self._active_run = None
        if run == _RUN_PLAYLIST:
            self._playlist_logs.append_log("[INFO] تم إلغاء التحميل")
            self._playlist_progress.reset()
            self._playlist_panel.finish_download(0, 0, 0)
            self._playlist_run = {"completed": 0, "failed": 0, "total": 0}
            self._restore_playlist_ui()
        else:
            self._video_logs.append_log("[INFO] تم إلغاء التحميل")
            self._video_progress.reset()
            self._restore_video_ui()

    def _open_folder(self):
        if self._current_video_dir and self._current_video_dir.exists():
            open_folder(self._current_video_dir)

    def _open_playlist_folder(self):
        if self._current_playlist_dir and self._current_playlist_dir.exists():
            open_folder(self._current_playlist_dir)
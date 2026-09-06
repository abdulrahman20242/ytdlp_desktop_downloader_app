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
from ui.playlist_panel import PlaylistPanel
from core.download_controller import DownloadController
from core.format_builder import build_format_opts, get_common_opts, QUALITY_OPTIONS
from core.info_extractor import (
    extract_info, get_available_qualities,
    extract_thumbnail, extract_title, extract_duration, extract_uploader,
    extract_playlist,
)
from utils.validators import is_valid_youtube_url, classify_url
from utils.file_utils import open_folder, sanitize_folder_name

# Rows inside ``main_frame`` that carry flexible weight while playlist mode
# is active: the PlaylistPanel (row 2) and the LogsPanel (row 9).
_PLAYLIST_ROW = 2
_LOGS_ROW = 9
# Flexible-space split inside ``main_frame``: the playlist list gets more of
# any slack (2 parts) than the logs (1 part) so the playlist keeps its size
# advantage, while the logs still grow on tall windows.
_PLAYLIST_ROW_WEIGHT = 2
_LOGS_ROW_WEIGHT = 1
# Hard floors (screen px) kept on both flexible rows so neither collapses to
# zero on short windows.  They match the measured internal structure at the
# default 800x600 / 125% window: the playlist floor covers the compact header
# + toolbar + roughly two media rows, and the logs floor keeps the panel
# header plus ~4 text lines.  On very short windows each row stops at its
# floor and the list/logs scroll internally instead.
_PLAYLIST_MIN_HEIGHT = 244
_LOGS_MIN_HEIGHT = 126
# Rows on the outer window while playlist mode is active: ``main_frame``
# should be the only flexible row so any extra window height feeds the
# content (playlist + logs) instead of the near-empty status bar.
_MAIN_FRAME_ROW = 2
_STATUS_ROW = 3


class MainWindow(ctk.CTkFrame):
    def __init__(self, master, config):
        super().__init__(master)
        self.master = master
        self.config = config
        self._controller = DownloadController(config)
        self._controller.set_app(master)
        self._current_info: dict | None = None
        self._current_save_dir: Path | None = None
        self._current_playlist: dict | None = None
        self._playlist_mode = False
        self._playlist_run: dict = {"completed": 0, "failed": 0, "total": 0}

        # Anchor explicitly to the root's single grid cell (row 0 / column 0).
        # ``StartupCheckFrame`` still occupies that cell while ``MainWindow`` is
        # constructed, and ``grid(sticky=...)`` without ``row``/``column`` would
        # otherwise auto-place this frame one row below it.  The root keeps its
        # flexible weight on row 0, so an empty row 0 above it would swallow all
        # slack and push the whole window content downward.
        self.grid(row=0, column=0, sticky="nsew")
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
        header.grid(row=0, column=0, pady=(5, 2))

        sub_header = ctk.CTkLabel(
            self, text="YouTube Video & Audio Downloader", font=("", 12),
            text_color="gray"
        )
        sub_header.grid(row=1, column=0, pady=(0, 3))

        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=4)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(9, weight=1)
        self._main_frame = main_frame

        url_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
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

        info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", pady=5)
        info_frame.grid_columnconfigure(1, weight=1)
        self._info_frame = info_frame

        self._title_label = ctk.CTkLabel(info_frame, text="", anchor="w", font=("", 13))
        self._title_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5)

        self._thumb_label = ctk.CTkLabel(info_frame, text="", width=160, height=90)
        self._thumb_label.grid(row=1, column=0, padx=5, pady=5)
        self._info_label = ctk.CTkLabel(info_frame, text="", anchor="w", justify="left")
        self._info_label.grid(row=1, column=1, sticky="nw", padx=5, pady=5)

        self._playlist_panel = PlaylistPanel(
            main_frame,
            on_download_all=lambda: self._start_playlist_download(
                list(self._current_playlist.get("entries", []))
                if self._current_playlist else []
            ),
            on_download_selected=lambda: self._start_playlist_download(
                self._playlist_panel.selected_entries()
            ),
        )
        self._playlist_panel.grid(row=2, column=0, sticky="nsew", pady=(0, 2))
        self._playlist_panel.hide()

        tk.Frame(main_frame, height=1, bg="#555").grid(row=3, column=0, sticky="ew", pady=0)

        self._quality_selector = QualitySelector(main_frame)
        self._quality_selector.grid(row=4, column=0, sticky="ew", pady=1)

        dir_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        dir_frame.grid(row=5, column=0, sticky="ew", pady=1)
        dir_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dir_frame, text="مجلد الحفظ:").grid(row=0, column=0, padx=(5, 5))
        self._dir_var = ctk.StringVar()
        self._dir_entry = ctk.CTkEntry(dir_frame, textvariable=self._dir_var)
        self._dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(dir_frame, text="تصفح", width=60, command=self._browse_dir).grid(row=0, column=2)

        action_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_frame.grid(row=6, column=0, sticky="ew", pady=2)

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

        self._progress_widget = ProgressWidget(main_frame)
        self._progress_widget.grid(row=7, column=0, sticky="ew", pady=1)

        tk.Frame(main_frame, height=1, bg="#555").grid(row=8, column=0, sticky="ew", pady=0)

        self._logs_panel = LogsPanel(main_frame)
        self._logs_panel.grid(row=9, column=0, sticky="nsew", pady=4)

        status_bar = ctk.CTkLabel(self, text="جاهز", anchor="w", font=("", 10))
        status_bar.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 3))

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

        def on_playlist_item(data):
            self._playlist_panel.update_item(
                data.get("index"), data.get("status", ""), data.get("error"),
            )
            total = data.get("total", 0)
            position = data.get("position", 0)
            if data.get("status") == "downloading":
                self._progress_widget.reset()
                self._progress_widget.set_message(
                    f"الفيديو {position} من {total} — جارٍ التنزيل…"
                )
                self._playlist_run["total"] = total
            elif data.get("status") == "completed":
                self._playlist_run["completed"] += 1
                self._logs_panel.append_log(
                    f"[INFO] playlist: الفيديو {data.get('index')} تم بنجاح"
                )
            elif data.get("status") == "failed":
                self._playlist_run["failed"] += 1
                err = data.get("error") or "خطأ"
                self._logs_panel.append_log(
                    f"[ERROR] playlist: الفيديو {data.get('index')} فشل — {err}"
                )

        def on_playlist_done():
            s = self._playlist_run
            total = s.get("total", 0)
            self._progress_widget.set_done()
            self._progress_widget.set_message(
                f"اكتملت القائمة ✓ — نجح {s['completed']} / فشل {s['failed']} (من {total})"
            )
            self._download_btn.configure(state="normal")
            self._cancel_btn.configure(state="disabled")
            self._open_folder_btn.configure(state="normal")
            self._fetch_btn.configure(state="normal")
            self._url_entry.configure(state="normal")
            self._playlist_panel.finish_download(
                s["completed"], s["failed"], total,
            )
            self._playlist_run = {"completed": 0, "failed": 0, "total": 0}
            if self._playlist_mode:
                self._download_btn.configure(state="disabled")

        self._controller.on("progress", on_progress)
        self._controller.on("done", on_done)
        self._controller.on("error", on_error)
        self._controller.on("log", on_log)
        self._controller.on("playlist_item", on_playlist_item)
        self._controller.on("playlist_done", on_playlist_done)

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

    def _fetch_info(self):
        url = self._url_var.get().strip()
        if not url:
            return

        self._fetch_btn.configure(state="disabled", text="جارٍ...")
        self._title_label.configure(text="جارٍ استخراج المعلومات...")
        self._info_label.configure(text="")
        self._download_btn.configure(state="disabled")
        self._leave_playlist_mode()

        mode = classify_url(url)

        def fetch():
            if mode == "playlist":
                data = extract_playlist(url)
                self.after(0, self._display_playlist, data)
            else:
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

    def _display_playlist(self, playlist: dict | None):
        self._fetch_btn.configure(state="normal", text="استعلام")

        if not playlist or not playlist.get("entries"):
            self._title_label.configure(text="❌ فشل استخراج القائمة — تحقق من الرابط")
            self._download_btn.configure(state="disabled")
            return

        self._current_playlist = playlist
        self._playlist_mode = True

        # The playlist header (thumbnail / title / channel / count) lives
        # inside PlaylistPanel — hide the generic info area so nothing is
        # displayed twice.
        if hasattr(self, "_info_frame"):
            self._info_frame.grid_remove()
        self._title_label.configure(text="")
        self._info_label.configure(text="")

        self._quality_selector.set_qualities(QUALITY_OPTIONS)
        self._playlist_panel.set_playlist(playlist)
        self._set_playlist_layout_active(True)
        self._playlist_panel.show()
        self._download_btn.configure(state="disabled")

    def _set_playlist_layout_active(self, active: bool):
        """Share the window's flexible vertical space with the playlist.

        While playlist mode is active the PlaylistPanel row and the LogsPanel
        row inside ``main_frame`` both carry flexible weight, so extra window
        height is used naturally instead of the fixed controls below growing
        stale gaps.  The playlist list receives a larger flexible share
        (2 parts) than the logs (1 part), and the logs row additionally keeps
        a minimum height (``_LOGS_MIN_HEIGHT``) so it never collapses to an
        unreadable strip: on short windows the playlist list absorbs the
        shrink and scrolls internally instead.  ``main_frame`` itself also
        becomes flexible so taller windows mostly feed the content area rather
        than the near-empty status bar.  All weights are reset once playlist
        mode ends so the normal single-video layout is untouched.
        """
        if not hasattr(self, "_main_frame"):
            return
        if active:
            self._main_frame.grid_rowconfigure(
                _PLAYLIST_ROW, weight=_PLAYLIST_ROW_WEIGHT,
                minsize=_PLAYLIST_MIN_HEIGHT,
            )
            self._main_frame.grid_rowconfigure(
                _LOGS_ROW, weight=_LOGS_ROW_WEIGHT, minsize=_LOGS_MIN_HEIGHT,
            )
            self.grid_rowconfigure(_MAIN_FRAME_ROW, weight=1)
            self.grid_rowconfigure(_STATUS_ROW, weight=0)
            # Pin the logs panel's requested height to its floor so the grid
            # shrink pass can't cut through it on short windows; the playlist
            # row then always keeps room for at least two media rows.
            self._logs_panel.set_natural_height(_LOGS_MIN_HEIGHT)
        else:
            self._main_frame.grid_rowconfigure(
                _PLAYLIST_ROW, weight=0, minsize=0,
            )
            self._main_frame.grid_rowconfigure(_LOGS_ROW, weight=1, minsize=0)
            self.grid_rowconfigure(_MAIN_FRAME_ROW, weight=0)
            self.grid_rowconfigure(_STATUS_ROW, weight=1)
            self._logs_panel.set_natural_height(None)

    def _leave_playlist_mode(self):
        self._playlist_mode = False
        self._current_playlist = None
        self._set_playlist_layout_active(False)
        if hasattr(self, "_playlist_panel"):
            self._playlist_panel.hide()
        if hasattr(self, "_info_frame"):
            self._info_frame.grid()

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

    def _build_download_opts(self):
        quality = self._quality_selector.quality
        mode = self._quality_selector.mode

        base_opts = get_common_opts("bin", self.config)
        format_opts = build_format_opts(quality, mode, self.config)
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

        return opts, quality, mode

    def _prepare_download_ui(self):
        self._progress_widget.reset()
        self._download_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._fetch_btn.configure(state="disabled")
        self._url_entry.configure(state="disabled")
        self._open_folder_btn.configure(state="disabled")

    def _resolve_save_dir(self) -> Path:
        raw = self._dir_var.get().strip()
        if not raw:
            raw = self.config.get("download.default_dir", "")
        save_dir = Path(raw or "downloads")
        save_dir.mkdir(parents=True, exist_ok=True)
        return save_dir

    def _playlist_save_dir(self, base: Path) -> Path:
        """Subfolder named after the playlist inside the chosen destination."""
        title = (self._current_playlist or {}).get("title") or ""
        folder = sanitize_folder_name(title, fallback="Playlist")
        target = base / folder
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _start_download(self):
        if self._playlist_mode:
            return

        url = self._url_var.get().strip()
        if not url:
            return

        save_dir = self._resolve_save_dir()
        self._current_save_dir = save_dir

        opts, quality, mode = self._build_download_opts()

        self._logs_panel.append_log(f"[INFO] بدء التحميل: {url}")
        self._logs_panel.append_log(f"[INFO] الجودة: {quality} | الوضع: {mode}")
        if "list=" in url:
            self._logs_panel.append_log(
                "[INFO] الرابط يحتوي على قائمة تشغيل — سيتم تنزيل الفيديو فقط"
            )

        self._prepare_download_ui()
        self._controller.start_download(url, opts, save_dir)

    def _start_playlist_download(self, entries: list[dict]):
        if not entries:
            self._logs_panel.append_log("[INFO] لا توجد مقاطع محددة")
            return

        save_dir = self._resolve_save_dir()
        if self._current_playlist:
            save_dir = self._playlist_save_dir(save_dir)
        self._current_save_dir = save_dir

        opts, quality, mode = self._build_download_opts()

        self._playlist_run = {"completed": 0, "failed": 0, "total": len(entries)}
        self._progress_widget.reset()
        title = (self._current_playlist or {}).get("title") or "قائمة التشغيل"
        self._logs_panel.append_log(
            f"[INFO] بدء تنزيل القائمة «{title}»: {len(entries)} فيديو"
        )
        self._logs_panel.append_log(f"[INFO] الوجهة: {save_dir}")
        self._logs_panel.append_log(f"[INFO] الجودة: {quality} | الوضع: {mode}")

        subset_indices = [e.get("index", i + 1) for i, e in enumerate(entries)]
        self._playlist_panel.begin_download(subset_indices)
        self._prepare_download_ui()
        self._open_folder_btn.configure(state="normal")

        self._controller.start_playlist_download(entries, opts, save_dir)

    def _cancel_download(self):
        self._controller.cancel()
        self._logs_panel.append_log("[INFO] تم إلغاء التحميل")
        self._progress_widget.reset()
        self._download_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._fetch_btn.configure(state="normal")
        self._url_entry.configure(state="normal")
        if self._playlist_mode:
            self._download_btn.configure(state="disabled")
            self._playlist_panel.finish_download(0, 0, 0)
            self._playlist_run = {"completed": 0, "failed": 0, "total": 0}

    def _open_folder(self):
        if self._current_save_dir and self._current_save_dir.exists():
            open_folder(self._current_save_dir)

    def _open_settings(self):
        current = self._dir_var.get().strip()
        if current and current != self.config.get("download.default_dir", ""):
            self.config.set("download.default_dir", current)
        dialog = SettingsDialog(self.master, self.config)
        self.wait_window(dialog)
        saved_dir = self.config.get("download.default_dir", "")
        if saved_dir and self._dir_var.get().strip() != saved_dir:
            self._dir_var.set(saved_dir)

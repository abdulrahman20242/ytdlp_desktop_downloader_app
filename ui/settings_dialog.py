import customtkinter as ctk
from pathlib import Path
import tkinter.filedialog as fd


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("الإعدادات")
        self.geometry("550x500")
        self.resizable(False, False)
        self.config = config
        self.grab_set()

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        notebook = ctk.CTkTabview(self)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.grid_rowconfigure(0, weight=1)

        self._general_tab = notebook.add("عام")
        self._download_tab = notebook.add("التحميل")
        self._audio_tab = notebook.add("الصوت")
        self._advanced_tab = notebook.add("متقدم")

        self._build_general_tab()
        self._build_download_tab()
        self._build_audio_tab()
        self._build_advanced_tab()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, pady=(0, 10))

        ctk.CTkButton(btn_frame, text="حفظ", command=self._save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="إلغاء", command=self.destroy).pack(side="left", padx=5)

    def _build_general_tab(self):
        self._theme_var = ctk.StringVar()
        ctk.CTkLabel(self._general_tab, text="السمة:").grid(row=0, column=0, sticky="w", pady=5)
        self._theme_menu = ctk.CTkOptionMenu(
            self._general_tab, variable=self._theme_var, values=["dark", "light", "system"]
        )
        self._theme_menu.grid(row=0, column=1, sticky="ew", pady=5, padx=(5, 0))

        self._lang_var = ctk.StringVar()
        ctk.CTkLabel(self._general_tab, text="اللغة:").grid(row=1, column=0, sticky="w", pady=5)
        self._lang_menu = ctk.CTkOptionMenu(
            self._general_tab, variable=self._lang_var, values=["ar", "en"]
        )
        self._lang_menu.grid(row=1, column=1, sticky="ew", pady=5, padx=(5, 0))

        self._dir_var = ctk.StringVar()
        ctk.CTkLabel(self._general_tab, text="مجلد الحفظ:").grid(row=2, column=0, sticky="w", pady=5)
        dir_frame = ctk.CTkFrame(self._general_tab, fg_color="transparent")
        dir_frame.grid(row=2, column=1, sticky="ew", pady=5, padx=(5, 0))
        dir_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(dir_frame, textvariable=self._dir_var).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(dir_frame, text="...", width=30, command=self._browse_dir).grid(row=0, column=1)

    def _build_download_tab(self):
        self._quality_var = ctk.StringVar()
        ctk.CTkLabel(self._download_tab, text="الجودة الافتراضية:").grid(row=0, column=0, sticky="w", pady=5)
        self._quality_menu = ctk.CTkOptionMenu(
            self._download_tab, variable=self._quality_var,
            values=["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
        )
        self._quality_menu.grid(row=0, column=1, sticky="ew", pady=5, padx=(5, 0))

        self._mode_var = ctk.StringVar()
        ctk.CTkLabel(self._download_tab, text="الوضع الافتراضي:").grid(row=1, column=0, sticky="w", pady=5)
        self._mode_menu = ctk.CTkOptionMenu(
            self._download_tab, variable=self._mode_var,
            values=["video", "mp4_only", "audio"]
        )
        self._mode_menu.grid(row=1, column=1, sticky="ew", pady=5, padx=(5, 0))

        self._fragments_var = ctk.StringVar()
        ctk.CTkLabel(self._download_tab, text="تحميل متوازي (fragments):").grid(row=2, column=0, sticky="w", pady=5)
        self._fragments_spin = ctk.CTkEntry(self._download_tab, textvariable=self._fragments_var, width=60)
        self._fragments_spin.grid(row=2, column=1, sticky="w", pady=5, padx=(5, 0))

        self._retries_var = ctk.StringVar()
        ctk.CTkLabel(self._download_tab, text="عدد إعادة المحاولة:").grid(row=3, column=0, sticky="w", pady=5)
        self._retries_spin = ctk.CTkEntry(self._download_tab, textvariable=self._retries_var, width=60)
        self._retries_spin.grid(row=3, column=1, sticky="w", pady=5, padx=(5, 0))

    def _build_audio_tab(self):
        self._audio_fmt_var = ctk.StringVar()
        ctk.CTkLabel(self._audio_tab, text="صيغة الصوت:").grid(row=0, column=0, sticky="w", pady=5)
        self._audio_fmt_menu = ctk.CTkOptionMenu(
            self._audio_tab, variable=self._audio_fmt_var, values=["mp3", "m4a"]
        )
        self._audio_fmt_menu.grid(row=0, column=1, sticky="ew", pady=5, padx=(5, 0))

        self._mp3_quality_var = ctk.StringVar()
        ctk.CTkLabel(self._audio_tab, text="جودة MP3:").grid(row=1, column=0, sticky="w", pady=5)
        self._mp3_quality_menu = ctk.CTkOptionMenu(
            self._audio_tab, variable=self._mp3_quality_var, values=["128", "192", "320"]
        )
        self._mp3_quality_menu.grid(row=1, column=1, sticky="ew", pady=5, padx=(5, 0))

    def _build_advanced_tab(self):
        self._cookies_source_var = ctk.StringVar()
        ctk.CTkLabel(self._advanced_tab, text="مصدر cookies:").grid(row=0, column=0, sticky="w", pady=5)
        self._cookies_source_menu = ctk.CTkOptionMenu(
            self._advanced_tab, variable=self._cookies_source_var, values=["browser", "file", "none"],
            command=self._on_cookies_source_change
        )
        self._cookies_source_menu.grid(row=0, column=1, sticky="ew", pady=5, padx=(5, 0))

        self._browser_var = ctk.StringVar()
        ctk.CTkLabel(self._advanced_tab, text="المتصفح:").grid(row=1, column=0, sticky="w", pady=5)
        self._browser_menu = ctk.CTkOptionMenu(
            self._advanced_tab, variable=self._browser_var, values=["chrome", "firefox", "edge", "brave"]
        )
        self._browser_menu.grid(row=1, column=1, sticky="ew", pady=5, padx=(5, 0))

        self._debug_var = ctk.BooleanVar()
        ctk.CTkCheckBox(self._advanced_tab, text="إظهار سجلات التصحيح (debug)", variable=self._debug_var)\
            .grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

    def _on_cookies_source_change(self, source: str):
        if source == "none":
            self._browser_menu.configure(state="disabled")
        else:
            self._browser_menu.configure(state="normal")

    def _browse_dir(self):
        path = fd.askdirectory(title="اختر مجلد الحفظ", initialdir=self._dir_var.get() or str(Path.home() / "Downloads"))
        if path:
            self._dir_var.set(path)

    def _load_config(self):
        self._theme_var.set(self.config.get("ui.theme", "dark"))
        self._lang_var.set(self.config.get("ui.language", "ar"))
        self._dir_var.set(self.config.get("download.default_dir", ""))
        self._quality_var.set(self.config.get("download.default_quality", "1080p"))
        self._mode_var.set(self.config.get("download.default_mode", "video"))
        self._fragments_var.set(str(self.config.get("download.concurrent_fragments", 4)))
        self._retries_var.set(str(self.config.get("download.retries", 10)))
        self._audio_fmt_var.set(self.config.get("audio.default_format", "mp3"))
        self._mp3_quality_var.set(str(self.config.get("audio.mp3_quality", "192")))
        self._cookies_source_var.set(self.config.get("cookies.source", "browser"))
        self._browser_var.set(self.config.get("cookies.browser", "chrome"))
        self._debug_var.set(self.config.get("advanced.show_debug_logs", False))

    def _save(self):
        self.config.set("ui.theme", self._theme_var.get())
        self.config.set("ui.language", self._lang_var.get())
        self.config.set("download.default_dir", self._dir_var.get())
        self.config.set("download.default_quality", self._quality_var.get())
        self.config.set("download.default_mode", self._mode_var.get())
        self.config.set("download.concurrent_fragments", int(self._fragments_var.get()))
        self.config.set("download.retries", int(self._retries_var.get()))
        self.config.set("audio.default_format", self._audio_fmt_var.get())
        self.config.set("audio.mp3_quality", self._mp3_quality_var.get())
        self.config.set("cookies.source", self._cookies_source_var.get())
        self.config.set("cookies.browser", self._browser_var.get())
        self.config.set("advanced.show_debug_logs", self._debug_var.get())
        self.destroy()

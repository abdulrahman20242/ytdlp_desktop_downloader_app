import customtkinter as ctk
from core.format_builder import QUALITY_OPTIONS, MODE_OPTIONS

AUDIO_FORMATS = ["MP3", "M4A"]


def resolve_initial_selection(mode: str, default_quality: str) -> tuple[str, str]:
    """خريطة الإعدادات المحفوظة إلى حالة (الوضع، الجودة) الفعلية للمنتقي."""
    if mode not in MODE_OPTIONS:
        mode = "video"
    if mode == "audio":
        # اختيار MP3/M4A محصور في أداة التحكم الرئيسية فقط (لا إعداد صوت منفصل)
        return mode, "MP3"
    if default_quality not in QUALITY_OPTIONS:
        default_quality = "1080p"
    return mode, default_quality


class QualitySelector(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="الوضع:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self._mode_var = ctk.StringVar(value="video")
        self._mode_menu = ctk.CTkOptionMenu(
            self,
            variable=self._mode_var,
            values=MODE_OPTIONS,
            command=self._on_mode_change,
        )
        self._mode_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        ctk.CTkLabel(self, text="الجودة:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self._quality_var = ctk.StringVar(value="1080p")
        self._quality_menu = ctk.CTkOptionMenu(
            self,
            variable=self._quality_var,
            values=QUALITY_OPTIONS,
        )
        self._quality_menu.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    def _on_mode_change(self, mode: str):
        if mode == "audio":
            self._quality_menu.configure(values=AUDIO_FORMATS)
            if self._quality_var.get() not in AUDIO_FORMATS:
                self._quality_var.set("MP3")
        else:
            self._quality_menu.configure(values=QUALITY_OPTIONS)
            if self._quality_var.get() not in QUALITY_OPTIONS:
                self._quality_var.set("1080p")

    def apply_defaults(self, mode: str, default_quality: str):
        mode, quality = resolve_initial_selection(mode, default_quality)
        self._mode_var.set(mode)
        if mode == "audio":
            self._quality_menu.configure(values=AUDIO_FORMATS)
        else:
            self._quality_menu.configure(values=QUALITY_OPTIONS)
        self._quality_var.set(quality)

    def set_qualities(self, qualities: list[str]):
        current = self._quality_var.get()
        mode = self._mode_var.get()
        if mode == "audio":
            return
        if current not in qualities and qualities:
            self._quality_var.set(qualities[0])
        self._quality_menu.configure(values=qualities)

    @property
    def quality(self) -> str:
        return self._quality_var.get().lower()

    @property
    def mode(self) -> str:
        return self._mode_var.get()

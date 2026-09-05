import customtkinter as ctk
from core.format_builder import QUALITY_OPTIONS, MODE_OPTIONS


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
            self._quality_menu.configure(values=["MP3", "M4A"])
            if self._quality_var.get() not in ("MP3", "M4A"):
                self._quality_var.set("MP3")
        else:
            self._quality_menu.configure(values=QUALITY_OPTIONS)
            if self._quality_var.get() not in QUALITY_OPTIONS:
                self._quality_var.set("1080p")

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

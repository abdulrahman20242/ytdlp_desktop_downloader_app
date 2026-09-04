import customtkinter as ctk


class ProgressWidget(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1)

        self._progress_bar = ctk.CTkProgressBar(self)
        self._progress_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))
        self._progress_bar.set(0)

        self._info_label = ctk.CTkLabel(self, text="", anchor="w")
        self._info_label.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 2))

        self._filename_label = ctk.CTkLabel(self, text="", anchor="w", font=("", 10))
        self._filename_label.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

        self.reset()

    def reset(self):
        self._progress_bar.set(0)
        self._info_label.configure(text="جاهز للتحميل")
        self._filename_label.configure(text="")

    def update_progress(self, d: dict):
        status = d.get("status", "")

        if status == "downloading":
            percent = self._safe_percent(d)
            self._progress_bar.set(percent)

            speed = d.get("_speed_str", "N/A")
            eta = d.get("_eta_str", "N/A")
            pct_str = f"{percent * 100:.1f}%"
            self._info_label.configure(
                text=f"{pct_str}  ·  {speed}  ·  ETA {eta}"
            )

            filename = d.get("filename", "")
            if filename:
                import os
                self._filename_label.configure(text=os.path.basename(filename))

        elif status == "finished":
            self._progress_bar.set(1.0)
            self._info_label.configure(text="تم التحميل — جارٍ المعالجة...")

        elif status == "error":
            self._info_label.configure(text="حدث خطأ أثناء التحميل")

    def set_done(self):
        self._progress_bar.set(1.0)
        self._info_label.configure(text="اكتمل التحميل بنجاح ✓")

    def set_error(self, message: str):
        self._info_label.configure(text=f"خطأ: {message}")

    def _safe_percent(self, d: dict) -> float:
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)
        if total:
            return min(downloaded / total, 1.0)
        raw = d.get("_percent_str", "0%").strip().rstrip("%")
        try:
            return float(raw) / 100
        except ValueError:
            return 0.0

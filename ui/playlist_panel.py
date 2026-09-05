import customtkinter as ctk
import threading
from io import BytesIO

import requests
from PIL import Image


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return ""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class PlaylistPanel(ctk.CTkFrame):
    """Panel that lists playlist entries with checkboxes, thumbnails, and
    per-item download status.  Shown only when the URL is an explicit
    playlist link and hidden otherwise."""

    # status → colour
    _STATUS_COLOUR = {
        "waiting": "#888888",
        "downloading": "#4a9eda",
        "completed": "#2d7a3a",
        "failed": "#c0392b",
    }

    def __init__(
        self,
        master,
        on_download_all=None,
        on_download_selected=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._on_download_all = on_download_all
        self._on_download_selected = on_download_selected
        self._entries: list[dict] = []
        self._rows: list[dict] = []

        self.grid_columnconfigure(0, weight=1)

        # ---- toolbar ----
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

        self._count_label = ctk.CTkLabel(toolbar, text="", font=("", 11))
        self._count_label.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            toolbar, text="تحديد الكل", width=80,
            command=self._select_all,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            toolbar, text="إلغاء التحديد", width=100,
            command=self._deselect_all,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            toolbar, text="⬇ تنزيل المحدد", width=120,
            command=lambda: self._on_download_selected() if self._on_download_selected else None,
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            toolbar, text="⬇ تنزيل الكل", width=100,
            command=lambda: self._on_download_all() if self._on_download_all else None,
        ).pack(side="right", padx=2)

        # ---- scrollable list ----
        self._list = ctk.CTkScrollableFrame(self, height=200)
        self._list.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.grid_rowconfigure(1, weight=1)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def set_playlist(self, playlist: dict):
        """Populate the panel with a normalised playlist dict."""
        self._clear()
        self._entries = playlist.get("entries", [])
        self._count_label.configure(
            text=f"{len(self._entries)} فيديو"
        )
        for entry in self._entries:
            self._add_row(entry)

    def show(self):
        self.grid()

    def hide(self):
        self.grid_remove()

    def selected_entries(self) -> list[dict]:
        return [
            self._entries[i]
            for i, row in enumerate(self._rows)
            if row["var"].get()
        ]

    def begin_download(self, subset_indices: list[int] | None = None):
        """Mark which rows are queued, disable controls."""
        for i, row in enumerate(self._rows):
            idx = self._entries[i].get("index", i + 1)
            if subset_indices is None or idx in subset_indices:
                row["status_var"].set("⏳ انتظار")
                row["status_lbl"].configure(text_color=self._STATUS_COLOUR["waiting"])
            else:
                row["status_var"].set("")
                row["status_lbl"].configure(text_color=self._STATUS_COLOUR["waiting"])

        self._disable_controls()

    def finish_download(self, completed: int, failed: int, total: int):
        """Re-enable controls after a playlist run."""
        self._enable_controls()

    def update_item(
        self, index: int, status: str, error: str | None = None,
    ):
        """Update a row's status label."""
        for row in self._rows:
            if row["entry"].get("index") == index:
                label_map = {
                    "downloading": "⬇ جارٍ التنزيل…",
                    "completed": "✓ تم",
                    "failed": "✗ فشل",
                }
                text = label_map.get(status, "")
                row["status_var"].set(text)
                row["status_lbl"].configure(
                    text_color=self._STATUS_COLOUR.get(
                        status, self._STATUS_COLOUR["waiting"],
                    ),
                )
                break

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _clear(self):
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()
        self._entries.clear()

    def _add_row(self, entry: dict):
        var = ctk.BooleanVar(value=False)
        status_var = ctk.StringVar(value="")

        frame = ctk.CTkFrame(self._list, fg_color="transparent")
        frame.grid_columnconfigure(3, weight=1)

        cb = ctk.CTkCheckBox(frame, text="", variable=var, width=28)
        cb.grid(row=0, column=0, padx=(4, 0))

        idx = ctk.CTkLabel(
            frame, text=f"{entry.get('index', '?')}",
            width=30, anchor="e", font=("", 11),
        )
        idx.grid(row=0, column=1, padx=4)

        thumb_lbl = ctk.CTkLabel(frame, text="", width=120, height=68)
        thumb_lbl.grid(row=0, column=2, padx=4, pady=4)

        title = entry.get("title") or "بدون عنوان"
        dur = _fmt_duration(entry.get("duration") or 0)
        title_text = f"{title}  ({dur})" if dur else title
        title_lbl = ctk.CTkLabel(
            frame, text=title_text, anchor="w",
            font=("", 12), wraplength=350, justify="left",
        )
        title_lbl.grid(row=0, column=3, sticky="ew", padx=4)

        status_lbl = ctk.CTkLabel(
            frame, text="", anchor="w", width=130, font=("", 11),
            textvariable=status_var,
        )
        status_lbl.grid(row=0, column=4, padx=4)

        frame.grid(sticky="ew", pady=1)

        row = {
            "frame": frame,
            "var": var,
            "cb": cb,
            "thumb_lbl": thumb_lbl,
            "title_lbl": title_lbl,
            "status_var": status_var,
            "status_lbl": status_lbl,
            "entry": entry,
        }
        self._rows.append(row)

        thumb_url = entry.get("thumbnail")
        if thumb_url:
            self._load_thumb(row, thumb_url)

    def _load_thumb(self, row: dict, url: str):
        def _fetch():
            try:
                resp = requests.get(url, timeout=10)
                img = Image.open(BytesIO(resp.content))
                img = img.resize((120, 68), Image.LANCZOS)
                photo = ctk.CTkImage(img, size=(120, 68))

                def _apply():
                    try:
                        row["thumb_lbl"].configure(image=photo, text="")
                    except Exception:
                        pass  # frame was rebuilt/closed before the image arrived

                self.after(0, _apply)
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _disable_controls(self):
        for row in self._rows:
            row["cb"].configure(state="disabled")

    def _enable_controls(self):
        for row in self._rows:
            row["cb"].configure(state="normal")

    def _select_all(self):
        for row in self._rows:
            row["var"].set(True)

    def _deselect_all(self):
        for row in self._rows:
            row["var"].set(False)

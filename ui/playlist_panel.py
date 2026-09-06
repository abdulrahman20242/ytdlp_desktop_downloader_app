import customtkinter as ctk
import threading
import tkinter as tk
import tkinter.font as tkfont
from io import BytesIO

from customtkinter import ScalingTracker

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


_STATUS_STYLE = {
    "waiting": {
        "badge_fg": "#2a2a2a",
        "text_fg": "#9a9a9a",
        "label": "⏳ انتظار",
    },
    "downloading": {
        "badge_fg": "#1f3a52",
        "text_fg": "#6fc3ff",
        "label": "⬇ جارٍ التنزيل…",
    },
    "completed": {
        "badge_fg": "#1d3325",
        "text_fg": "#7fd18a",
        "label": "✓ تم",
    },
    "failed": {
        "badge_fg": "#3a2522",
        "text_fg": "#ff958c",
        "label": "✗ فشل",
    },
}


def status_style(status: str) -> dict:
    return _STATUS_STYLE.get(status, _STATUS_STYLE["waiting"])


def _ellipsize(text: str, max_px: int, measure=None) -> str:
    """Fit ``text`` on one line by truncating with an ellipsis.

    ``measure`` is a ``str -> int`` pixel-width callable.  When omitted a
    character-count approximation is used so the helper stays headless-safe.
    """
    if not text or max_px <= 0:
        return text
    if measure is None:
        def _approx(s: str) -> int:
            return len(s) * 8

        measure = _approx
    ell = "…"
    if measure(text) <= max_px:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if measure(text[:mid] + ell) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ell


class PlaylistPanel(ctk.CTkFrame):
    """Compact media-queue style playlist panel.

    Layout: playlist header (thumbnail / title / channel / count),
    action toolbar (selection + download actions), then a dense scrollable
    media list.  Rows follow ``checkbox | index | thumbnail | title+meta |
    status badge``.
    """

    _THUMB_SIZE = (80, 45)
    _LIST_BG = "#202020"
    _THUMB_BG = "#2b2b2b"
    _ROW_HOVER_BG = "#2e2e2e"
    _ROW_SELECT_BG = "#2b3a52"
    _TITLE_FONT = ("", 12)
    _META_FONT = ("", 10)
    _MUTED = "#9a9a9a"
    # Requested height of the scrollable list.  The row is made flexible
    # while playlist mode is active, so this is only the starting size: the
    # list grows on tall windows and shrinks before the window runs out of
    # room.  Kept modest so the panel's requested size doesn't dwarf the
    # LogsPanel below it at the default window size.
    _LIST_BASE_HEIGHT = 110
    # Horizontal space consumed by everything except the flexible title area.
    _FIXED_ROW_WIDTH = 318
    _FALLBACK_TITLE_PX = 400

    def __init__(
        self,
        master,
        on_download_all=None,
        on_download_selected=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_download_all = on_download_all
        self._on_download_selected = on_download_selected
        self._entries: list[dict] = []
        self._rows: list[dict] = []
        self._header_title_full = ""
        self._measure_font_cache = None
        self._measure_bold_font_cache = None
        self._truncate_after = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_toolbar()
        self._build_list()

    # ------------------------------------------------------------------ #
    #  Construction
    # ------------------------------------------------------------------ #

    def _scale(self, px: int) -> int:
        """Pixel value that requests ``px`` after CustomTkinter's DPI scaling.

        CustomTkinter multiplies declared label sizes by the current widget
        scaling (e.g. 1.25 on a 125 % display), so divide back so the widget
        keeps its designed footprint on any display.
        """
        try:
            return max(1, round(px / ScalingTracker.get_widget_scaling(self)))
        except Exception:
            return px

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
        header.grid_columnconfigure(1, weight=1)

        thumb_host = ctk.CTkFrame(
            header,
            width=self._THUMB_SIZE[0],
            height=self._THUMB_SIZE[1],
            corner_radius=6,
            fg_color=self._THUMB_BG,
        )
        thumb_host.grid(row=0, column=0, rowspan=3, padx=(0, 10), sticky="w")
        thumb_host.grid_propagate(False)

        self._panel_thumb = ctk.CTkLabel(
            thumb_host,
            text="▶",
            width=self._THUMB_SIZE[0],
            height=self._THUMB_SIZE[1],
            font=("", 16),
        )
        self._panel_thumb.grid(row=0, column=0)

        self._meta_title = ctk.CTkLabel(
            header,
            text="",
            anchor="w",
            font=("", 14, "bold"),
            height=19,
            wraplength=480,
        )
        self._meta_title.grid(row=0, column=1, sticky="ew", padx=(0, 4))

        self._meta_channel = ctk.CTkLabel(
            header,
            text="",
            anchor="w",
            font=("", 11),
            height=15,
            text_color=self._MUTED,
        )
        self._meta_channel.grid(row=1, column=1, sticky="ew", padx=(0, 4))

        self._meta_count = ctk.CTkLabel(
            header,
            text="",
            anchor="w",
            font=("", 11),
            height=15,
            text_color=self._MUTED,
        )
        self._meta_count.grid(row=2, column=1, sticky="ew", padx=(0, 4))

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 2))
        bar.grid_columnconfigure(2, weight=1)

        self._count_label = ctk.CTkLabel(
            bar, text="", font=("", 12, "bold"), anchor="w",
        )
        self._count_label.grid(row=0, column=0, sticky="w", padx=(0, 12))

        self._sel_label = ctk.CTkLabel(
            bar, text="", font=("", 11), text_color=self._MUTED, anchor="w",
        )
        self._sel_label.grid(row=0, column=1, sticky="w", padx=(0, 8))

        self._select_all_btn = self._secondary_button(
            bar, "تحديد الكل", self._select_all,
        )
        self._select_all_btn.grid(row=0, column=3, padx=2)

        self._deselect_all_btn = self._secondary_button(
            bar, "إلغاء التحديد", self._deselect_all,
        )
        self._deselect_all_btn.grid(row=0, column=4, padx=2)

        self._dl_all_btn = ctk.CTkButton(
            bar,
            text="⬇ تنزيل الكل",
            width=92,
            height=28,
            font=("", 11),
            fg_color="transparent",
            border_width=1,
            border_color="#5a5a5a",
            text_color="#e8e8e8",
            hover_color="#333333",
            command=lambda: self._on_download_all() if self._on_download_all else None,
        )
        self._dl_all_btn.grid(row=0, column=5, padx=2)

        self._dl_selected_btn = ctk.CTkButton(
            bar,
            text="⬇ تنزيل المحدد",
            width=118,
            height=28,
            font=("", 11, "bold"),
            fg_color="#2d7a3a",
            hover_color="#236b2e",
            command=lambda: self._on_download_selected()
            if self._on_download_selected
            else None,
        )
        self._dl_selected_btn.grid(row=0, column=6, padx=2)

    def _secondary_button(self, master, text, command):
        return ctk.CTkButton(
            master,
            text=text,
            width=82,
            height=28,
            font=("", 11),
            fg_color="transparent",
            text_color="#cfcfcf",
            hover_color="#333333",
            command=command,
        )

    def _build_list(self):
        self._list = ctk.CTkScrollableFrame(
            self,
            fg_color=self._LIST_BG,
            corner_radius=6,
            height=self._LIST_BASE_HEIGHT,
        )
        self._list.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        # The list is stretched by the surrounding grid when playlist mode is
        # active, so fix its *requested* height to the base rather than the
        # content height: the internal scrollbar scales its requested height
        # to the whole scroll region, which would inflate the panel's natural
        # size and overflow the window, defeating the minsize floors on the
        # playlist/logs rows.  ``_parent_frame`` is the widget the panel's
        # grid actually manages (the outer CTkScrollableFrame is just the
        # canvas window item that must keep propagating its content height).
        # (CTkScrollableFrame's own ``grid_propagate`` drops the flag
        # argument, so call the ``tkinter.Frame`` base method directly.)
        tk.Frame.grid_propagate(self._list._parent_frame, False)
        self._list._parent_frame.configure(height=self._LIST_BASE_HEIGHT)
        self._list.grid_columnconfigure(0, weight=1)
        self._list.bind("<Configure>", lambda e: self._schedule_truncation())
        # Keep the canvas scroll region in sync even when the widget is laid
        # out while unmapped or during a resize: CTkScrollableFrame's own
        # handler can race to an empty bbox and leave ``scrollregion`` empty,
        # which freezes the viewport (yview always ``(0.0, 1.0)``) so wheel
        # and scrollbar scrolling silently stop working.
        self._list.bind(
            "<Configure>", lambda e: self._sync_list_scrollregion(), add="+",
        )
        self._list._parent_canvas.bind(
            "<Configure>", lambda e: self._sync_list_scrollregion(), add="+",
        )

        self._empty_lbl = ctk.CTkLabel(
            self._list,
            text="لا توجد فيديوهات في هذه القائمة",
            font=("", 12),
            text_color=self._MUTED,
        )

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def set_playlist(self, playlist: dict):
        """Populate the panel with a normalised playlist dict."""
        self._clear()
        self._entries = playlist.get("entries", [])
        self._refresh_header(playlist)
        self._update_selection_label()
        for entry in self._entries:
            self._add_row(entry)
        self._refresh_row_truncation()
        self._update_empty_state()
        self._sync_list_scrollregion()
        if self.winfo_ismapped():
            self.after(0, self._sync_list_scrollregion)

    def show(self):
        self.grid()
        self.after(1, self._sync_list_scrollregion)

    def hide(self):
        self.grid_remove()

    def selected_entries(self) -> list[dict]:
        return [
            self._entries[i]
            for i, row in enumerate(self._rows)
            if row["var"].get()
        ]

    def begin_download(self, subset_indices: list[int] | None = None):
        """Mark which rows are queued, disable selection controls."""
        for i, row in enumerate(self._rows):
            idx = self._entries[i].get("index", i + 1)
            if subset_indices is None or idx in subset_indices:
                self._set_status(row, "waiting")
            else:
                self._set_status(row, "")
        self._disable_controls()

    def finish_download(self, completed: int, failed: int, total: int):
        """Re-enable selection controls after a playlist run."""
        self._enable_controls()

    def update_item(
        self, index: int, status: str, error: str | None = None,
    ):
        """Update a row's status badge."""
        for row in self._rows:
            if row["entry"].get("index") == index:
                self._set_status(row, status)
                break

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _refresh_header(self, playlist: dict):
        title = playlist.get("title") or "قائمة تشغيل"
        self._header_title_full = title
        uploader = playlist.get("uploader") or ""
        count = len(playlist.get("entries", []))

        self._meta_title.configure(text=title, wraplength=480)
        self._meta_count.configure(text=f"{count} فيديو")

        if uploader:
            self._meta_channel.configure(text=uploader)
            self._meta_channel.grid()
        else:
            self._meta_channel.grid_remove()

        thumb_url = playlist.get("thumbnail")
        if thumb_url:
            self._load_thumb(self._panel_thumb, thumb_url, self._THUMB_SIZE)

    def _clear(self):
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()
        self._entries.clear()

    def _sync_list_scrollregion(self):
        """Set the list canvas scrollregion from the content frame size.

        Falls back to the content frame's requested size so the region is
        correct even during layout races where ``bbox("all")`` is empty.
        """
        canvas = self._list._parent_canvas
        content = self._list
        height = content.winfo_height() or content.winfo_reqheight()
        width = max(canvas.winfo_width(), content.winfo_reqwidth(), 10)
        if height > 40:
            canvas.configure(scrollregion=(0, 0, width, height))

    def _update_empty_state(self):
        if self._entries:
            self._empty_lbl.grid_remove()
        else:
            self._empty_lbl.grid(row=0, column=0, pady=24)

    def _add_row(self, entry: dict):
        var = ctk.BooleanVar(value=False)
        status_var = ctk.StringVar(value="")

        frame = ctk.CTkFrame(self._list, fg_color="transparent")
        frame.grid_columnconfigure(3, weight=1)
        frame.grid(sticky="ew", padx=3, pady=1)

        cb = ctk.CTkCheckBox(frame, text="", variable=var, width=28)

        idx = ctk.CTkLabel(
            frame,
            text=str(entry.get("index", "?")),
            width=32,
            anchor="e",
            font=("", 10),
            text_color=self._MUTED,
        )

        thumb_lbl = ctk.CTkLabel(
            frame,
            text="▶",
            width=self._THUMB_SIZE[0],
            height=self._scale(self._THUMB_SIZE[1]),
            fg_color=self._THUMB_BG,
            corner_radius=4,
        )

        text_frame = ctk.CTkFrame(frame, fg_color="transparent")
        text_frame.grid_columnconfigure(0, weight=1)

        title = entry.get("title") or "بدون عنوان"
        title_lbl = ctk.CTkLabel(
            text_frame,
            text=title,
            anchor="w",
            font=self._TITLE_FONT,
            height=15,
            wraplength=self._FALLBACK_TITLE_PX,
        )

        dur = _fmt_duration(entry.get("duration") or 0)
        meta_lbl = ctk.CTkLabel(
            text_frame,
            text=dur,
            anchor="w",
            font=self._META_FONT,
            height=12,
            text_color=self._MUTED,
        )

        badge = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=6)
        status_lbl = ctk.CTkLabel(
            badge, text="", textvariable=status_var, font=("", 11), padx=8,
        )

        cb.grid(row=0, column=0, padx=(4, 2), pady=3)
        idx.grid(row=0, column=1, padx=(2, 8), pady=3)
        thumb_lbl.grid(row=0, column=2, padx=3, pady=3)
        text_frame.grid(row=0, column=3, sticky="ew", padx=(2, 6), pady=5)
        if dur:
            meta_lbl.grid(row=1, column=0, sticky="ew")
        else:
            meta_lbl.grid_remove()
        title_lbl.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        badge.grid(row=0, column=4, padx=(4, 4), pady=5)
        status_lbl.grid(row=0, column=0)

        row = {
            "frame": frame,
            "var": var,
            "cb": cb,
            "thumb_lbl": thumb_lbl,
            "title_lbl": title_lbl,
            "meta_lbl": meta_lbl,
            "badge": badge,
            "status_lbl": status_lbl,
            "status_var": status_var,
            "entry": entry,
            "full_title": title,
            "hovered": False,
        }
        self._rows.append(row)

        cb.configure(command=lambda r=row: self._on_row_toggle(r))
        for widget in (frame, cb, idx, thumb_lbl, text_frame, title_lbl,
                       meta_lbl, badge, status_lbl):
            self._bind_hover(row, widget)

        self._set_status(row, "")

        thumb_url = entry.get("thumbnail")
        if thumb_url:
            self._load_thumb(thumb_lbl, thumb_url, self._THUMB_SIZE)

    def _load_thumb(self, label, url: str, size: tuple[int, int]):
        def _fetch():
            try:
                resp = requests.get(url, timeout=10)
                img = Image.open(BytesIO(resp.content))
                img = img.resize(size, Image.LANCZOS)
                photo = ctk.CTkImage(img, size=size)

                def _apply():
                    try:
                        label.configure(image=photo, text="")
                    except Exception:
                        pass  # frame was rebuilt/closed before the image arrived

                self.after(0, _apply)
            except Exception:
                pass  # keep the placeholder on failure

        threading.Thread(target=_fetch, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  Selection / interaction
    # ------------------------------------------------------------------ #

    def _bind_hover(self, row: dict, widget):
        widget.bind("<Enter>", lambda e: self._on_row_enter(row))
        widget.bind("<Leave>", lambda e: self._on_row_leave(row))

    def _on_row_enter(self, row: dict):
        row["hovered"] = True
        self._update_row_bg(row)

    def _on_row_leave(self, row: dict):
        row["hovered"] = False
        self._update_row_bg(row)

    def _on_row_toggle(self, row: dict):
        self._update_row_bg(row)
        self._update_selection_label()

    def _update_row_bg(self, row: dict):
        if row["var"].get():
            fg = self._ROW_SELECT_BG
        elif row["hovered"]:
            fg = self._ROW_HOVER_BG
        else:
            fg = "transparent"
        row["frame"].configure(fg_color=fg)

    def _set_status(self, row: dict, status: str):
        if not status:
            row["badge"].configure(fg_color="transparent")
            row["status_lbl"].configure(text_color=self._MUTED)
            row["status_var"].set("")
            return
        style = status_style(status)
        row["badge"].configure(fg_color=style["badge_fg"])
        row["status_lbl"].configure(text_color=style["text_fg"])
        row["status_var"].set(style["label"])

    def _select_all(self):
        for row in self._rows:
            row["var"].set(True)
            self._update_row_bg(row)
        self._update_selection_label()

    def _deselect_all(self):
        for row in self._rows:
            row["var"].set(False)
            self._update_row_bg(row)
        self._update_selection_label()

    def _update_selection_label(self):
        total = len(self._entries)
        selected = sum(1 for row in self._rows if row["var"].get())
        self._count_label.configure(text=f"{total} فيديو")
        self._sel_label.configure(text=f"{selected} محددة")

    def _disable_controls(self):
        for row in self._rows:
            row["cb"].configure(state="disabled")
        self._select_all_btn.configure(state="disabled")
        self._deselect_all_btn.configure(state="disabled")

    def _enable_controls(self):
        for row in self._rows:
            row["cb"].configure(state="normal")
        self._select_all_btn.configure(state="normal")
        self._deselect_all_btn.configure(state="normal")

    # ------------------------------------------------------------------ #
    #  Truncation
    # ------------------------------------------------------------------ #

    def _measure_font(self):
        if self._measure_font_cache is None:
            try:
                self._measure_font_cache = tkfont.Font(font=self._TITLE_FONT)
            except Exception:
                self._measure_font_cache = False
        return self._measure_font_cache or None

    def _measure_bold_font(self):
        if self._measure_bold_font_cache is None:
            try:
                self._measure_bold_font_cache = tkfont.Font(font=("", 14, "bold"))
            except Exception:
                self._measure_bold_font_cache = False
        return self._measure_bold_font_cache or None

    def _schedule_truncation(self):
        if self._truncate_after is not None:
            try:
                self.after_cancel(self._truncate_after)
            except Exception:
                pass
        self._truncate_after = self.after(50, self._refresh_row_truncation)

    def _refresh_row_truncation(self):
        try:
            width = self._list.winfo_width()
        except Exception:
            return
        if width <= 40:
            return

        avail = max(80, width - self._FIXED_ROW_WIDTH)
        measure = self._measure_font()
        for row in self._rows:
            row["title_lbl"].configure(wraplength=avail)
            if measure is not None:
                title_lbl_text = _ellipsize(row["full_title"], avail, measure.measure)
            else:
                title_lbl_text = row["full_title"]
            row["title_lbl"].configure(text=title_lbl_text)

        bold = self._measure_bold_font()
        header_avail = max(120, width - (self._THUMB_SIZE[0] + 16))
        if bold is not None:
            self._meta_title.configure(
                text=_ellipsize(self._header_title_full, header_avail, bold.measure)
            )

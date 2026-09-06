import customtkinter as ctk
import tkinter as tk

from customtkinter import ScalingTracker


class LogsPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        self._header_frame.grid_columnconfigure(0, weight=1)

        self._toggle_btn = ctk.CTkButton(
            self._header_frame,
            text="▼ السجلات",
            width=100,
            command=self._toggle,
            font=("", 11),
        )
        self._toggle_btn.grid(row=0, column=0, sticky="w")

        self._clear_btn = ctk.CTkButton(
            self._header_frame,
            text="مسح",
            width=60,
            command=self._clear,
            font=("", 10),
        )
        self._clear_btn.grid(row=0, column=1, sticky="e")

        self._textbox = ctk.CTkTextbox(
            self,
            font=("Consolas", 10),
            height=100,
        )
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._textbox.configure(state="disabled")

        self._visible = True

    def set_natural_height(self, px: int):
        """Pin this panel's *requested* height to ``px``.

        With playlist mode active the logs row sits under the playlist and, if
        this panel kept asking for its full content height (~180px), the grid
        shrink pass on a short window would eat straight through the logs
        minsize floor.  Capping the natural height to the floor makes the
        window math add up, while the internal grid still stretches the
        textbox fully on taller windows (row 1 keeps its weight).  Passing
        ``None`` restores the content-driven request, so single-video mode is
        unaffected.
        """
        if px is None:
            tk.Frame.grid_propagate(self, True)
            return
        declared = max(1, round(px / ScalingTracker.get_widget_scaling(self)))
        tk.Frame.grid_propagate(self, False)
        self.configure(height=declared)

    def _toggle(self):
        if self._visible:
            self._textbox.grid_remove()
            self._toggle_btn.configure(text="▲ السجلات")
        else:
            self._textbox.grid()
            self._toggle_btn.configure(text="▼ السجلات")
        self._visible = not self._visible

    def _clear(self):
        self._textbox.configure(state="normal")
        self._textbox.delete("0.0", "end")
        self._textbox.configure(state="disabled")

    def append_log(self, message: str):
        self._textbox.configure(state="normal")
        self._textbox.insert("end", message + "\n")
        self._textbox.see("end")
        self._textbox.configure(state="disabled")

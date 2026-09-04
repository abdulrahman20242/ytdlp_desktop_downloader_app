import customtkinter as ctk
from core.dep_checker import DependencyChecker


class StartupCheckFrame(ctk.CTkFrame):
    def __init__(self, master, on_done):
        super().__init__(master)
        self.master = master
        self._on_done = on_done
        self._result = False

        self.grid(sticky="nsew")
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="YT Downloader — فحص المكونات",
            font=("", 16, "bold"),
        ).grid(row=0, column=0, pady=(20, 10))

        self._status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._status_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self._status_frame.grid_columnconfigure(0, weight=1)

        self._action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._action_frame.grid(row=2, column=0, pady=(10, 20))

        self._continue_btn = ctk.CTkButton(
            self._action_frame,
            text="متابعة",
            command=self._on_continue,
            state="disabled",
        )
        self._continue_btn.pack(side="left", padx=5)

        self._run_checks()

    def _run_checks(self):
        self.update()
        checker = DependencyChecker()
        results = checker.check_all()
        self._display_results(results)
        self.update()

    def _display_results(self, results):
        for widget in self._status_frame.winfo_children():
            widget.destroy()

        all_found = True

        for dep in results:
            if dep.found:
                icon = "✅"
                text = f"{dep.name}  {dep.version or ''}"
            elif dep.required:
                icon = "❌"
                text = f"{dep.name}  غير موجود — مطلوب"
                all_found = False
            else:
                icon = "⚠️"
                text = f"{dep.name}  غير موجود — اختياري (قد لا تعمل بعض الفيديوهات)"

            label = ctk.CTkLabel(
                self._status_frame,
                text=f"{icon}  {text}",
                anchor="w",
                font=("", 12),
            )
            label.pack(fill="x", pady=2)

        if not all_found:
            ctk.CTkLabel(
                self._status_frame,
                text="\nبعض المكونات الأساسية مفقودة. قد لا يعمل التطبيق بشكل صحيح.",
                text_color="orange",
                font=("", 10),
            ).pack(pady=(10, 0))

        self._continue_btn.configure(state="normal")

    def _on_continue(self):
        self._continue_btn.configure(state="disabled")
        self._on_done()
        self.destroy()

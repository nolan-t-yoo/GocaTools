"""Tkinter desktop UI for GocaTools."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import ROOT, __version__
from .codes import DEFAULT_EXPIRY, GocaError
from .generator import process_codes
from .pdf import build_pdf, find_default_background

APP_NAME = "GocaTools"
PAD = 10

CSV_TYPES = [("Code lists", "*.csv *.txt"), ("All files", "*.*")]
TEMPLATE_TYPES = [("Text files", "*.txt"), ("All files", "*.*")]
IMAGE_TYPES = [("Images", "*.png *.jpg *.jpeg"), ("All files", "*.*")]
PDF_TYPES = [("PDF files", "*.pdf"), ("All files", "*.*")]


def _enable_dpi_awareness() -> None:
    """Keep fonts crisp on high-DPI Windows displays."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _open_folder(path: str) -> None:
    """Reveal *path* in the platform file manager."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class GocaApp(ttk.Frame):
    """Two-step workflow: generate card data, then build the printable PDF."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=PAD)
        self._queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._poll_id: str | None = None

        self.csv_var = tk.StringVar(value=self._first_existing("codes.csv"))
        self.template_var = tk.StringVar(value=self._first_existing("template.txt"))
        self.expiry_var = tk.StringVar(value=DEFAULT_EXPIRY)
        self.outdir_var = tk.StringVar(value=os.path.join(ROOT, "output"))
        self.pdf_var = tk.StringVar(value=os.path.join(ROOT, "cards.pdf"))
        self.bg_var = tk.StringVar(value=find_default_background(ROOT) or "")
        self.status_var = tk.StringVar(value="Ready.")

        self._build_widgets()
        self._append_log(
            f"{APP_NAME} {__version__} ready. Choose your files, then press "
            "'Generate + Build PDF'."
        )
        self.bind("<Destroy>", self._on_destroy)
        self._poll_id = self.after(100, self._poll)
        self.csv_entry.focus_set()

    # ── layout ───────────────────────────────────────────────────────────────
    @staticmethod
    def _first_existing(name: str) -> str:
        path = os.path.join(ROOT, name)
        return path if os.path.isfile(path) else ""

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        source = ttk.LabelFrame(self, text="1 · Redemption codes", padding=PAD)
        source.grid(row=0, column=0, sticky="ew")
        source.columnconfigure(1, weight=1)

        row = 0
        self.csv_entry, row = self._path_row(
            source, row, "Codes file:", self.csv_var, "open", CSV_TYPES,
            hint="CSV or TXT - one code per cell or line",
        )
        _, row = self._path_row(
            source, row, "Message template:", self.template_var, "open", TEMPLATE_TYPES,
            hint="${CODE} and ${EXPIRY} are replaced",
        )

        ttk.Label(source, text="Expiry date:").grid(row=row, column=0, sticky="w", padx=(0, PAD), pady=4)
        ttk.Entry(source, textvariable=self.expiry_var, width=28).grid(row=row, column=1, sticky="w", pady=4)
        ttk.Label(source, text="replaces ${EXPIRY}").grid(row=row, column=2, sticky="w", padx=(6, 0))
        row += 1

        self._path_row(
            source, row, "Cards folder:", self.outdir_var, "dir", None,
            hint="emptied each run, then one sub-folder per code is created",
        )

        target = ttk.LabelFrame(self, text="2 · Printable PDF", padding=PAD)
        target.grid(row=1, column=0, sticky="ew", pady=(PAD, 0))
        target.columnconfigure(1, weight=1)

        row = 0
        _, row = self._path_row(target, row, "PDF output:", self.pdf_var, "save", PDF_TYPES)
        self._path_row(
            target, row, "Background image:", self.bg_var, "open", IMAGE_TYPES,
            hint="optional, centred behind each card", clear=True,
        )

        log_frame = ttk.LabelFrame(self, text="Log", padding=(PAD, PAD, PAD, 0))
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(PAD, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame, height=10, wrap="none", state="disabled",
            background="#1e1e1e", foreground="#d4d4d4", insertbackground="#d4d4d4",
            borderwidth=0, font=("Consolas", 9) if sys.platform == "win32" else ("Menlo", 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        self.progress = ttk.Progressbar(log_frame, mode="determinate", maximum=100, value=0)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", pady=(PAD, 0))
        actions.columnconfigure(0, weight=1)

        ttk.Button(actions, text="Open cards folder", command=self._on_open_output).grid(row=0, column=0, sticky="w")
        self.build_button = ttk.Button(actions, text="Build PDF only", command=self._on_build)
        self.build_button.grid(row=0, column=2, padx=(0, 6))
        self.generate_button = ttk.Button(actions, text="Generate cards only", command=self._on_generate)
        self.generate_button.grid(row=0, column=3, padx=(0, 6))
        self.run_button = ttk.Button(actions, text="Generate + Build PDF", command=self._on_run_all)
        self.run_button.grid(row=0, column=4)

        ttk.Label(self, textvariable=self.status_var, anchor="w", relief="sunken", padding=(6, 3)).grid(
            row=4, column=0, sticky="ew", pady=(PAD, 0)
        )

    def _path_row(
        self,
        parent: ttk.Widget,
        row: int,
        label: str,
        var: tk.StringVar,
        kind: str,
        filetypes: list[tuple[str, str]] | None,
        hint: str = "",
        clear: bool = False,
    ) -> tuple[ttk.Entry, int]:
        """Add a labelled path field; return the entry and the next free row."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, PAD), pady=4)
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", pady=4)

        buttons = ttk.Frame(parent)
        buttons.grid(row=row, column=2, sticky="w", padx=(6, 0), pady=4)
        ttk.Button(
            buttons, text="Browse...", width=10,
            command=lambda: self._browse(var, kind, filetypes),
        ).pack(side="left")
        if clear:
            ttk.Button(buttons, text="Clear", width=7, command=lambda: var.set("")).pack(side="left", padx=(4, 0))

        if not hint:
            return entry, row + 1

        ttk.Label(parent, text=hint, foreground="#666666", font=("TkDefaultFont", 8)).grid(
            row=row + 1, column=1, columnspan=2, sticky="w", pady=(0, 2)
        )
        return entry, row + 2

    # ── browsing ─────────────────────────────────────────────────────────────
    def _browse(self, var: tk.StringVar, kind: str, filetypes) -> None:
        current = var.get().strip()
        initial = os.path.dirname(current) if current else ROOT
        if not os.path.isdir(initial):
            initial = ROOT

        if kind == "dir":
            chosen = filedialog.askdirectory(initialdir=initial, mustexist=False, title="Choose a folder")
        elif kind == "save":
            chosen = filedialog.asksaveasfilename(
                initialdir=initial,
                title="Save PDF as",
                defaultextension=".pdf",
                initialfile=os.path.basename(current) or "cards.pdf",
                filetypes=filetypes or PDF_TYPES,
            )
        else:
            chosen = filedialog.askopenfilename(
                initialdir=initial,
                title="Choose a file",
                filetypes=filetypes or [("All files", "*.*")],
            )

        if chosen:
            var.set(os.path.normpath(chosen))

    # ── actions ──────────────────────────────────────────────────────────────
    def _read_settings(self) -> dict:
        """Snapshot the form values (main thread only - worker must not touch Tk)."""
        return {
            "csv": self.csv_var.get().strip(),
            "template": self.template_var.get().strip(),
            "expiry": self.expiry_var.get().strip() or DEFAULT_EXPIRY,
            "outdir": self.outdir_var.get().strip() or os.path.join(ROOT, "output"),
            "pdf": self.pdf_var.get().strip() or os.path.join(ROOT, "cards.pdf"),
            "bg": self.bg_var.get().strip() or None,
        }

    def _generate(self, settings: dict) -> dict:
        return process_codes(
            settings["csv"],
            settings["template"],
            settings["outdir"],
            settings["expiry"],
            clean=True,
            log=self._log,
        )

    def _build(self, settings: dict) -> int:
        return build_pdf(settings["outdir"], settings["pdf"], settings["bg"], log=self._log)

    def _validate_generate(self, settings: dict) -> str | None:
        if not settings["csv"]:
            return "Please choose a codes file first."
        if not settings["template"]:
            return "Please choose a message template first."
        return None

    def _validate_build(self, settings: dict) -> str | None:
        if not settings["outdir"]:
            return "Please choose a cards folder first."
        if not settings["pdf"]:
            return "Please choose where to save the PDF."
        return None

    def _on_generate(self) -> None:
        settings = self._read_settings()
        problem = self._validate_generate(settings)
        if problem:
            messagebox.showwarning(APP_NAME, problem, parent=self)
            return
        self._start([lambda: self._generate(settings)], "Generating cards...")

    def _on_build(self) -> None:
        settings = self._read_settings()
        problem = self._validate_build(settings)
        if problem:
            messagebox.showwarning(APP_NAME, problem, parent=self)
            return
        self._start([lambda: self._build(settings)], "Building PDF...")

    def _on_run_all(self) -> None:
        settings = self._read_settings()
        problem = self._validate_generate(settings) or self._validate_build(settings)
        if problem:
            messagebox.showwarning(APP_NAME, problem, parent=self)
            return
        self._start(
            [lambda: self._generate(settings), lambda: self._build(settings)],
            "Generating cards and building PDF...",
        )

    def _on_open_output(self) -> None:
        path = self.outdir_var.get().strip()
        if not os.path.isdir(path):
            messagebox.showwarning(APP_NAME, f"Folder not found yet:\n{path}", parent=self)
            return
        _open_folder(path)

    # ── worker plumbing ──────────────────────────────────────────────────────
    def _log(self, message: str) -> None:
        self._queue.put(("log", message))

    def _start(self, tasks, label: str) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._append_log(f"--- {label} ---")
        self._set_busy(True, label)
        self._worker = threading.Thread(target=self._run_tasks, args=(tasks,), daemon=True)
        self._worker.start()

    def _run_tasks(self, tasks) -> None:
        results = []
        try:
            for task in tasks:
                results.append(task())
        except GocaError as exc:
            self._queue.put(("error", str(exc)))
        except Exception as exc:
            self._queue.put(("error", f"{type(exc).__name__}: {exc}"))
        else:
            self._queue.put(("done", results))

    def _poll(self) -> None:
        self._poll_id = None
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "error":
                    self._append_log(f"Error: {payload}")
                    self._set_busy(False, "Failed.")
                    messagebox.showerror(APP_NAME, payload, parent=self)
                elif kind == "done":
                    self._set_busy(False, self._summary(payload))
        except queue.Empty:
            pass
        self._poll_id = self.after(80, self._poll)

    def _on_destroy(self, event: tk.Event) -> None:
        """Stop the poll loop so the widget can be collected with its interpreter."""
        if event.widget is not self or self._poll_id is None:
            return
        try:
            self.after_cancel(self._poll_id)
        except tk.TclError:
            pass
        self._poll_id = None

    @staticmethod
    def _summary(results) -> str:
        parts = []
        for result in results:
            if isinstance(result, dict):
                parts.append(f"{result['written']} cards written")
                if result["skipped"]:
                    parts.append(f"{len(result['skipped'])} skipped")
            elif isinstance(result, int):
                parts.append(f"{result} cards -> PDF" if result else "no cards found")
        return "Finished: " + ", ".join(parts) + "." if parts else "Finished."

    def _set_busy(self, busy: bool, status: str) -> None:
        state = "disabled" if busy else "normal"
        for button in (self.generate_button, self.build_button, self.run_button):
            button.configure(state=state)
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
        self.status_var.set(status)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def _build_menu(root: tk.Tk) -> None:
    menubar = tk.Menu(root)

    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Exit", command=root.destroy)
    menubar.add_cascade(label="File", menu=file_menu)

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(
        label=f"About {APP_NAME}",
        command=lambda: messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME} {__version__}\n\n"
            "Generate Pokemon GO redemption cards with QR codes\n"
            "and lay them out on a printable business-card PDF.\n\n"
            "Not affiliated with Nintendo, The Pokemon Company or Niantic.",
            parent=root,
        ),
    )
    menubar.add_cascade(label="Help", menu=help_menu)
    root.configure(menu=menubar)


def main() -> None:
    """Run the desktop UI."""
    _enable_dpi_awareness()
    root = tk.Tk()
    root.title(f"{APP_NAME} {__version__}")

    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")

    _build_menu(root)
    app = GocaApp(root)
    app.pack(fill="both", expand=True)

    root.update_idletasks()
    # Sizes below are logical pixels; scale them so the window matches the display DPI.
    scale = max(root.winfo_fpixels("1i") / 96.0, 1.0)
    width = int(min(880 * scale, root.winfo_screenwidth() - 80))
    height = int(min(720 * scale, root.winfo_screenheight() - 120))
    root.minsize(min(int(700 * scale), width), min(int(560 * scale), height))

    x = max((root.winfo_screenwidth() - width) // 2, 0)
    y = max((root.winfo_screenheight() - height) // 3, 0)
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()

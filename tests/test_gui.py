"""Tests for the tkinter UI (skipped when no display is available)."""

import time
import tkinter as tk

import pytest

from goca import gui
from goca.gui import GocaApp


@pytest.fixture()
def root():
    widget = None
    error = None
    # Tk initialisation occasionally fails on first use in a fresh interpreter,
    # so give it a couple of tries before treating the display as unavailable.
    for _ in range(3):
        try:
            widget = tk.Tk()
            break
        except tk.TclError as exc:  # pragma: no cover - headless machines
            error = exc
            time.sleep(0.2)

    if widget is None:  # pragma: no cover - headless machines
        pytest.skip(f"tkinter display unavailable: {error}")

    widget.withdraw()
    try:
        yield widget
    finally:
        widget.destroy()


@pytest.fixture(autouse=True)
def no_dialogs(monkeypatch):
    """Replace modal dialogs so a failure cannot block the test run."""
    shown = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a, **k: shown.append(("error",) + a))
    monkeypatch.setattr(gui.messagebox, "showwarning", lambda *a, **k: shown.append(("warning",) + a))
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: shown.append(("info",) + a))
    return shown


@pytest.fixture()
def inputs(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("AAAA1111,BBBB2222", encoding="utf-8")

    template_path = tmp_path / "template.txt"
    template_path.write_text("Code:\n${CODE}\nExpires:\n${EXPIRY}\n", encoding="utf-8")

    return {
        "csv": csv_path,
        "template": template_path,
        "out": tmp_path / "output",
        "pdf": tmp_path / "cards.pdf",
    }


def make_app(root, inputs=None):
    app = GocaApp(root)
    app.pack()
    if inputs:
        app.csv_var.set(str(inputs["csv"]))
        app.template_var.set(str(inputs["template"]))
        app.outdir_var.set(str(inputs["out"]))
        app.pdf_var.set(str(inputs["pdf"]))
        app.expiry_var.set("Soon")
    root.update_idletasks()
    return app


def pump(root, stop_when, timeout=20.0):
    """Run the Tk event loop until *stop_when* is true or the timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        root.update()
        if stop_when():
            return True
        time.sleep(0.02)
    return False


def drain(queue):
    """Return every message currently sitting in the UI queue."""
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def test_app_builds_its_widgets(root):
    app = make_app(root)

    assert app.status_var.get() == "Ready."
    assert app.template_var.get().endswith("template.txt")
    assert app.expiry_var.get() == "N/A"
    assert app.outdir_var.get().endswith("output")
    assert app.pdf_var.get().endswith("cards.pdf")
    assert str(app.log_text.cget("state")) == "disabled"


def test_log_stays_read_only_when_writing(root):
    app = make_app(root)

    app._append_log("hello")

    assert "hello" in app.log_text.get("1.0", "end")
    assert str(app.log_text.cget("state")) == "disabled"


def test_settings_snapshot_uses_defaults(root):
    app = make_app(root)
    app.outdir_var.set("")
    app.pdf_var.set("")
    app.expiry_var.set("")

    settings = app._read_settings()

    assert settings["outdir"].endswith("output")
    assert settings["pdf"].endswith("cards.pdf")
    assert settings["expiry"] == "N/A"
    assert settings["bg"] is None


def test_generate_and_build_write_cards_and_pdf(root, inputs):
    app = make_app(root, inputs)
    settings = app._read_settings()

    summary = app._generate(settings)
    count = app._build(settings)

    assert summary["written"] == 2
    assert (inputs["out"] / "AAAA1111" / "message.txt").read_text(encoding="utf-8") == (
        "Code:\nAAAA1111\nExpires:\nSoon\n"
    )
    assert count == 2
    assert inputs["pdf"].read_bytes().startswith(b"%PDF")


def test_worker_reports_completion(root, inputs):
    app = make_app(root, inputs)
    settings = app._read_settings()

    app._run_tasks([lambda: app._generate(settings), lambda: app._build(settings)])
    messages = drain(app._queue)

    assert messages[-1][0] == "done"
    generated, built = messages[-1][1]
    assert generated["written"] == 2
    assert built == 2
    assert any(kind == "log" for kind, _ in messages)


def test_worker_reports_input_errors(root, tmp_path):
    app = make_app(root)
    app.csv_var.set(str(tmp_path / "missing.csv"))
    app.template_var.set(str(tmp_path / "missing.txt"))
    settings = app._read_settings()

    app._run_tasks([lambda: app._generate(settings)])
    messages = drain(app._queue)

    assert messages[-1][0] == "error"
    assert "Codes file not found" in messages[-1][1]


def test_run_all_button_completes_from_a_worker_thread(root, inputs, no_dialogs):
    """The button path must not touch Tk variables from the worker thread."""
    app = make_app(root, inputs)

    app._on_run_all()
    finished = pump(root, lambda: app.status_var.get().startswith("Finished"))

    assert finished, f"run did not finish, status={app.status_var.get()!r}"
    assert app.status_var.get() == "Finished: 2 cards written, 2 cards -> PDF."
    assert no_dialogs == []
    assert (inputs["out"] / "BBBB2222" / "QR.png").is_file()
    assert inputs["pdf"].is_file()
    assert "RuntimeError" not in app.log_text.get("1.0", "end")


def test_missing_inputs_warn_instead_of_running(root, no_dialogs):
    app = make_app(root)
    app.csv_var.set("")

    app._on_generate()

    assert no_dialogs and no_dialogs[0][0] == "warning"
    assert "codes file" in no_dialogs[0][2]
    assert app.status_var.get() == "Ready."


def test_summary_variants():
    assert GocaApp._summary([{"written": 3, "skipped": []}]) == "Finished: 3 cards written."
    assert GocaApp._summary([{"written": 2, "skipped": ["x"]}]) == (
        "Finished: 2 cards written, 1 skipped."
    )
    assert GocaApp._summary([3]) == "Finished: 3 cards -> PDF."
    assert GocaApp._summary([0]) == "Finished: no cards found."
    assert GocaApp._summary([]) == "Finished."

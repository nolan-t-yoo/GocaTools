"""Tests for the tkinter UI (skipped when no display is available)."""

import time

import pytest

from goca import gui
from goca.gui import PLACEHOLDER_CODE, GocaApp


@pytest.fixture()
def root(clean_tk):
    """Share one interpreter, but drop this test's widgets while it is still alive."""
    yield clean_tk


@pytest.fixture(autouse=True)
def no_side_effects(monkeypatch):
    """Replace modal dialogs and the shell-open call so tests stay self-contained."""
    shown = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a, **k: shown.append(("error",) + a))
    monkeypatch.setattr(gui.messagebox, "showwarning", lambda *a, **k: shown.append(("warning",) + a))
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: shown.append(("info",) + a))
    # Never launch a real PDF viewer or file manager from a test.
    monkeypatch.setattr(gui, "_open_path", lambda path: None)
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


def test_generate_clears_the_cards_folder(root, inputs):
    app = make_app(root, inputs)
    stale = inputs["out"] / "OLDCARD0000"
    stale.mkdir(parents=True)
    (stale / "message.txt").write_text("old", encoding="utf-8")

    summary = app._generate(app._read_settings())

    assert summary["cleaned"] == 1
    assert not stale.exists()
    assert (inputs["out"] / "AAAA1111" / "QR.png").is_file()


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


def test_run_all_button_completes_from_a_worker_thread(root, inputs, no_side_effects):
    """The button path must not touch Tk variables from the worker thread."""
    app = make_app(root, inputs)

    app._on_run_all()
    finished = pump(root, lambda: app.status_var.get().startswith("Finished"))

    assert finished, f"run did not finish, status={app.status_var.get()!r}"
    assert app.status_var.get() == "Finished: 2 cards written, 2 cards -> PDF."
    assert no_side_effects == []
    assert (inputs["out"] / "BBBB2222" / "QR.png").is_file()
    assert inputs["pdf"].is_file()
    assert "RuntimeError" not in app.log_text.get("1.0", "end")


def test_missing_inputs_warn_instead_of_running(root, no_side_effects):
    app = make_app(root)
    app.csv_var.set("")

    app._on_generate()

    assert no_side_effects and no_side_effects[0][0] == "warning"
    assert "codes file" in no_side_effects[0][2]
    assert app.status_var.get() == "Ready."


# ── "open the PDF when finished" ─────────────────────────────────────────────
def test_open_pdf_is_on_by_default(root):
    app = make_app(root)

    assert app.open_pdf_var.get() is True
    assert app._read_settings()["open_pdf"] is True


def test_build_asks_to_open_the_pdf_when_the_box_is_ticked(root, inputs, monkeypatch):
    opened = []
    monkeypatch.setattr(gui, "_open_path", opened.append)
    app = make_app(root, inputs)
    settings = app._read_settings()

    app._generate(settings)
    app._build(settings)
    messages = drain(app._queue)

    assert ("open", str(inputs["pdf"])) in messages

    app._open_pdf(str(inputs["pdf"]))

    assert opened == [str(inputs["pdf"])]
    assert f"Opened {inputs['pdf']}" in app.log_text.get("1.0", "end")


def test_build_leaves_the_pdf_closed_when_the_box_is_cleared(root, inputs, monkeypatch):
    opened = []
    monkeypatch.setattr(gui, "_open_path", opened.append)
    app = make_app(root, inputs)
    app.open_pdf_var.set(False)
    settings = app._read_settings()

    app._generate(settings)
    app._build(settings)

    assert [m for m in drain(app._queue) if m[0] == "open"] == []
    assert opened == []


def test_open_failure_is_logged_not_raised(root, inputs, monkeypatch):
    def boom(path):
        raise OSError("no association")

    monkeypatch.setattr(gui, "_open_path", boom)
    app = make_app(root, inputs)

    app._open_pdf(str(inputs["pdf"]))

    assert "Could not open the PDF" in app.log_text.get("1.0", "end")


def test_empty_build_does_not_ask_to_open(root, inputs):
    app = make_app(root, inputs)
    inputs["out"].mkdir(parents=True, exist_ok=True)

    count = app._build(app._read_settings())

    assert count == 0
    assert [m for m in drain(app._queue) if m[0] == "open"] == []


# ── preview ──────────────────────────────────────────────────────────────────
def card_texts(app):
    return [
        app.preview.canvas.itemcget(item, "text")
        for item in app.preview.canvas.find_all()
        if app.preview.canvas.type(item) == "text"
    ]


def test_preview_renders_the_template(root, inputs):
    app = make_app(root, inputs)

    app._refresh_preview()

    assert card_texts(app) == ["Code:", "AAAA1111", "Expires:", "Soon"]


def test_preview_follows_the_expiry_field(root, inputs):
    app = make_app(root, inputs)

    app.expiry_var.set("Next week")
    app._refresh_preview()

    assert "Next week" in card_texts(app)


def test_preview_shows_a_hint_without_a_template(root, tmp_path):
    app = make_app(root)
    app.template_var.set(str(tmp_path / "missing.txt"))

    app._refresh_preview()

    assert " ".join(card_texts(app)) == "Choose a message template to see a card preview."


def test_preview_includes_the_background_image(root, inputs, tmp_path):
    from PIL import Image

    background = tmp_path / "bg.png"
    Image.new("RGB", (300, 300), (0, 90, 160)).save(background)
    app = make_app(root, inputs)
    app.bg_var.set(str(background))

    app._refresh_preview()

    kinds = {app.preview.canvas.type(item) for item in app.preview.canvas.find_all()}
    assert "image" in kinds


def test_sample_code_uses_the_first_code_in_the_file(root, inputs):
    app = make_app(root, inputs)

    assert app.sample_code() == "AAAA1111"


def test_sample_code_falls_back_when_there_is_no_file(root, tmp_path):
    app = make_app(root)
    app.csv_var.set(str(tmp_path / "missing.csv"))

    assert app.sample_code() == PLACEHOLDER_CODE


def test_sample_code_ignores_headers_and_comments(root, tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("code\n# note\n\nZZZZ9999\n", encoding="utf-8")
    app = make_app(root)
    app.csv_var.set(str(csv_path))

    assert app.sample_code() == "ZZZZ9999"


def test_preview_refreshes_when_the_template_changes(root, inputs, tmp_path):
    app = make_app(root, inputs)
    other = tmp_path / "other.txt"
    other.write_text("Hello ${CODE}", encoding="utf-8")

    app.template_var.set(str(other))
    assert pump(root, lambda: card_texts(app) == ["Hello AAAA1111"], timeout=5)


def test_summary_variants():
    assert GocaApp._summary([{"written": 3, "skipped": []}]) == "Finished: 3 cards written."
    assert GocaApp._summary([{"written": 2, "skipped": ["x"]}]) == (
        "Finished: 2 cards written, 1 skipped."
    )
    assert GocaApp._summary([3]) == "Finished: 3 cards -> PDF."
    assert GocaApp._summary([0]) == "Finished: no cards found."
    assert GocaApp._summary([]) == "Finished."

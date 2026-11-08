"""Tests for the single-card preview widget."""

import pytest
from PIL import Image

from goca.preview import EMPTY_HINT, CardPreview


@pytest.fixture()
def preview(clean_tk):
    widget = CardPreview(clean_tk, width=380)
    widget.pack()
    clean_tk.update_idletasks()
    return widget


def texts(preview):
    return [
        preview.canvas.itemcget(item, "text")
        for item in preview.canvas.find_all()
        if preview.canvas.type(item) == "text"
    ]


def images(preview):
    return [item for item in preview.canvas.find_all() if preview.canvas.type(item) == "image"]


def test_starts_with_a_hint(preview):
    assert " ".join(texts(preview)) == EMPTY_HINT
    assert images(preview) == []


def test_card_is_three_point_five_by_two(preview):
    width = int(preview.canvas.cget("width"))
    height = int(preview.canvas.cget("height"))
    assert width == 380
    assert abs(height / width - 2 / 3.5) < 0.01


def test_show_draws_every_line(preview):
    lines = ["DEMOA001XYZW", "Expires", "Dec 31, 2026", "Thanks for playing!"]

    preview.show("DEMOA001XYZW", lines)

    assert texts(preview) == lines
    assert preview.canvas.find_all()  # border rectangle too


def test_show_draws_a_qr_code(preview):
    preview.show("DEMOA001XYZW", ["DEMOA001XYZW"])

    assert len(images(preview)) == 1


def test_qr_image_is_cached_between_refreshes(preview):
    preview.show("DEMOA001XYZW", ["DEMOA001XYZW"])
    assert len(preview._qr_cache) == 1
    cached = next(iter(preview._qr_cache.values()))

    preview.refresh()

    assert len(preview._qr_cache) == 1
    assert next(iter(preview._qr_cache.values())) is cached


def test_long_lines_are_trimmed_to_the_message_area(preview):
    long_line = "X" * 200

    preview.show("DEMOA001XYZW", [long_line])

    drawn = texts(preview)[0]
    assert 0 < len(drawn) < len(long_line)


def test_short_lines_are_kept_intact(preview):
    preview.show("DEMOA001XYZW", ["Hi"])

    assert texts(preview) == ["Hi"]


def test_background_image_becomes_the_card_backdrop(clean_tk, tmp_path):
    background = tmp_path / "bg.png"
    Image.new("RGB", (400, 200), (10, 120, 200)).save(background)

    widget = CardPreview(clean_tk, width=380)
    widget.show("DEMOA001XYZW", ["DEMOA001XYZW"], str(background))

    # background + QR code
    assert len(images(widget)) == 2


def test_missing_background_image_is_ignored(clean_tk, tmp_path):
    widget = CardPreview(clean_tk, width=380)

    widget.show("DEMOA001XYZW", ["Hi"], str(tmp_path / "missing.png"))

    assert len(images(widget)) == 1  # QR only, no crash


def test_show_message_replaces_the_card(preview):
    preview.show("DEMOA001XYZW", ["Hi"])

    preview.show_message("No template")

    assert texts(preview) == ["No template"]
    assert images(preview) == []


def test_show_after_message_restores_the_card(preview):
    preview.show_message("No template")

    preview.show("DEMOA001XYZW", ["Hi"])

    assert texts(preview) == ["Hi"]


# ── card numbering ───────────────────────────────────────────────────────────
def text_items(preview):
    return {
        preview.canvas.itemcget(item, "text"): preview.canvas.coords(item)
        for item in preview.canvas.find_all()
        if preview.canvas.type(item) == "text"
    }


def test_no_number_label_unless_asked(preview):
    preview.show("DEMOA001XYZW", ["Hi"])

    assert texts(preview) == ["Hi"]


def test_number_label_sits_under_the_qr_code(preview):
    preview.show("DEMOA001XYZW", ["Hi"], number="[1/125]")

    items = text_items(preview)
    assert "[1/125]" in items
    label_x, label_y = items["[1/125]"]
    width = int(preview.canvas.cget("width"))
    height = int(preview.canvas.cget("height"))
    qr_left, qr_top, qr_size = preview._qr_box(width / 252.0)

    # Horizontally centred on the QR code, vertically between it and the bottom edge.
    assert abs(label_x - (qr_left + qr_size / 2)) < 1
    assert qr_top + qr_size < label_y < height
    assert label_x > width * 2 / 3


def test_number_label_is_drawn_over_a_background(clean_tk, tmp_path):
    background = tmp_path / "bg.png"
    Image.new("RGB", (400, 200), (10, 120, 200)).save(background)
    widget = CardPreview(clean_tk, width=380)

    widget.show("DEMOA001XYZW", ["Hi"], str(background), number="[7/9]")

    assert len(images(widget)) == 2
    assert "[7/9]" in texts(widget)


def test_number_label_is_cleared_on_the_next_show(preview):
    preview.show("DEMOA001XYZW", ["Hi"], number="[1/2]")

    preview.show("DEMOA001XYZW", ["Hi"])

    assert texts(preview) == ["Hi"]

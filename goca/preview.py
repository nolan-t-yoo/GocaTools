"""Live preview of a single card.

The drawing mirrors :mod:`goca.pdf` closely - same fractions, padding, font size and
line spacing - so what the user sees here is what lands in the PDF.
"""

from __future__ import annotations

import textwrap
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .codes import redemption_url
from .pdf import (
    CARD_H,
    CARD_W,
    FONT_SIZE,
    LINE_SPACING,
    MSG_FRAC,
    NUMBER_FONT_SIZE,
    PADDING,
    QR_FRAC,
)

try:  # Pillow arrives with qrcode[pil]; the preview still works without it.
    from PIL import Image, ImageDraw, ImageTk
except ImportError:  # pragma: no cover - exercised only on broken installs
    Image = ImageDraw = ImageTk = None

try:
    import qrcode
except ImportError:  # pragma: no cover - exercised only on broken installs
    qrcode = None

CARD_ASPECT = CARD_H / CARD_W
BOX_ALPHA = 0.75
BOX_RADIUS = 3
BORDER_COLOUR = "#bfbfbf"
HINT_COLOUR = "#666666"
EMPTY_HINT = "Choose a message template to see a card preview."


def _fit_line(font: tkfont.Font, text: str, max_width: float) -> str:
    """Trim *text* to the longest prefix that fits inside *max_width*."""
    if font.measure(text) <= max_width:
        return text

    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if font.measure(text[:mid]) <= max_width:
            low = mid
        else:
            high = mid - 1
    return text[:low]


class CardPreview(ttk.Frame):
    """A scaled-down rendering of one business card."""

    def __init__(self, master: tk.Misc, width: int = 380) -> None:
        super().__init__(master)
        self._width = width
        self._height = round(width * CARD_ASPECT)
        self.canvas = tk.Canvas(
            self,
            width=self._width,
            height=self._height,
            background="#ffffff",
            highlightthickness=1,
            highlightbackground=BORDER_COLOUR,
        )
        self.canvas.pack()

        self._images: list = []
        self._qr_cache: dict[tuple[str, int], object] = {}
        self._code: str | None = None
        self._lines: list[str] = []
        self._background: str | None = None
        self._number: str | None = None
        self._message: str | None = None
        self._font_cache: dict[int, tkfont.Font] = {}

        self.show_message(EMPTY_HINT)

    # ── public API ───────────────────────────────────────────────────────────
    def show(
        self,
        code: str,
        lines: list[str],
        background: str | None = None,
        number: str | None = None,
    ) -> None:
        """Preview *lines* rendered for *code* over *background*.

        *number* is an optional label such as ``[1/125]`` drawn under the QR code.
        """
        self._message = None
        self._code = code
        self._lines = list(lines)
        self._background = background or None
        self._number = number or None
        self.refresh()

    def show_message(self, message: str) -> None:
        """Replace the card with a centred hint."""
        self._message = message
        self._code = None
        self._lines = []
        self.refresh()

    def refresh(self) -> None:
        """Redraw the canvas from the last content."""
        self.canvas.delete("all")
        self._images.clear()

        if self._message is not None or not self._code:
            self._draw_hint(self._message or EMPTY_HINT)
            return

        scale = self._width / CARD_W
        font = self._font(round(FONT_SIZE * scale))
        line_height = LINE_SPACING * scale
        message_w = (CARD_W * MSG_FRAC - PADDING * 2) * scale
        lines = [_fit_line(font, line, message_w) for line in self._lines]
        block_height = len(lines) * line_height
        top = (self._height - block_height) / 2
        pad = PADDING * scale

        label = self._number_geometry(scale)
        self._draw_background(top, block_height, pad, message_w, label)
        self._draw_qr(scale)
        if label is not None:
            label_font, label_x, label_y, _ = label
            self.canvas.create_text(
                label_x, label_y, text=self._number, font=label_font, anchor="center", fill="#000000"
            )
        for index, line in enumerate(lines):
            self.canvas.create_text(
                pad,
                top + index * line_height,
                text=line,
                font=font,
                anchor="nw",
                fill="#000000",
            )
        self.canvas.create_rectangle(
            0.5, 0.5, self._width - 0.5, self._height - 0.5, outline=BORDER_COLOUR
        )

    def destroy(self) -> None:
        # Tk image objects belong to one interpreter; drop them with the widget.
        self._qr_cache.clear()
        self._images.clear()
        super().destroy()

    # ── drawing helpers ──────────────────────────────────────────────────────
    def _font(self, size_px: int) -> tkfont.Font:
        size_px = max(size_px, 8)
        if size_px not in self._font_cache:
            # Helvetica maps to Arial on Windows and to a close match elsewhere.
            self._font_cache[size_px] = tkfont.Font(family="Helvetica", size=-size_px)
        return self._font_cache[size_px]

    def _qr_box(self, scale: float) -> tuple[float, float, float]:
        """Return ``(left, top, size)`` of the QR code in canvas pixels."""
        qr_area_w = CARD_W * QR_FRAC * scale
        qr_size = min(qr_area_w, self._height) - PADDING * 2 * scale
        left = self._width - qr_area_w + (qr_area_w - qr_size) / 2
        return left, (self._height - qr_size) / 2, qr_size

    def _number_geometry(self, scale: float) -> tuple[tkfont.Font, float, float, float] | None:
        """Font, centre x, centre y and text width of the card-number label."""
        if not self._number:
            return None
        font = self._font(round(NUMBER_FONT_SIZE * scale))
        left, top, size = self._qr_box(scale)
        # Centred in the strip between the QR code and the bottom edge, as in the PDF.
        centre_y = top + size + (self._height - top - size) / 2
        return font, left + size / 2, centre_y, font.measure(self._number)

    def _draw_background(
        self,
        top: float,
        block_height: float,
        pad: float,
        message_w: float,
        label: tuple[tkfont.Font, float, float, float] | None = None,
    ) -> None:
        has_image = bool(self._background) and Image is not None
        if not has_image:
            return

        try:
            with Image.open(self._background) as source:
                image = source.convert("RGB")
        except (OSError, ValueError):
            return

        # Scale to fill the card (preserving aspect), then centre-crop.
        scale = max(self._width / image.width, self._height / image.height)
        resized = image.resize(
            (max(round(image.width * scale), 1), max(round(image.height * scale), 1)),
            Image.LANCZOS,
        )
        left = (resized.width - self._width) // 2
        top_crop = (resized.height - self._height) // 2
        card = resized.crop((left, top_crop, left + self._width, top_crop + self._height)).convert("RGBA")

        # The PDF draws a 75% white box behind the message; composite the same.
        overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rounded_rectangle(
            [pad * 0.4, top - pad * 0.3, pad + message_w + pad * 0.6, top + block_height + pad * 0.3],
            radius=round(BOX_RADIUS * self._width / CARD_W),
            fill=(255, 255, 255, round(BOX_ALPHA * 255)),
        )
        if label is not None:
            label_font, label_x, label_y, label_w = label
            half_h = label_font.metrics("linespace") / 2
            draw.rounded_rectangle(
                [label_x - label_w / 2 - 3, label_y - half_h, label_x + label_w / 2 + 3, label_y + half_h],
                radius=2,
                fill=(255, 255, 255, round(BOX_ALPHA * 255)),
            )
        composed = Image.alpha_composite(card, overlay).convert("RGB")

        photo = ImageTk.PhotoImage(composed)
        self._images.append(photo)
        self.canvas.create_image(0, 0, image=photo, anchor="nw")

    def _draw_qr(self, scale: float) -> None:
        if qrcode is None or ImageTk is None or not self._code:
            return

        left, top, qr_size = self._qr_box(scale)
        size_px = max(round(qr_size), 8)

        key = (self._code, size_px)
        photo = self._qr_cache.get(key)
        if photo is None:
            image = qrcode.make(redemption_url(self._code))
            photo = ImageTk.PhotoImage(image.resize((size_px, size_px), Image.NEAREST))
            self._qr_cache[key] = photo
            if len(self._qr_cache) > 32:
                self._qr_cache.pop(next(iter(self._qr_cache)))

        self._images.append(photo)
        self.canvas.create_image(left, top, image=photo, anchor="nw")

    def _draw_hint(self, message: str) -> None:
        font = self._font(round(11 * self._width / CARD_W))
        chars = max(int(self._width / max(font.measure("n"), 1)) - 4, 12)
        wrapped = textwrap.wrap(message, width=chars) or [message]
        line_height = font.metrics("linespace")
        top = (self._height - len(wrapped) * line_height) / 2
        for index, line in enumerate(wrapped):
            self.canvas.create_text(
                self._width / 2,
                top + index * line_height,
                text=line,
                font=font,
                anchor="n",
                fill=HINT_COLOUR,
            )

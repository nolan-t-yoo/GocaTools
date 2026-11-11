"""Render a single card as a PNG image.

The layout mirrors :func:`goca.pdf.draw_card` - same card size, fractions,
padding, font sizes and line spacing - so a card image matches what the PDF
prints. Text is set in a Helvetica-compatible sans face when one is installed
(Arial, Liberation Sans, Helvetica); otherwise the Bitstream Vera Sans font
that ships with ReportLab is used.
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

from .pdf import (
    CARD_H,
    CARD_W,
    FONT_SIZE,
    LINE_SPACING,
    MSG_FRAC,
    NUMBER_BOX_PAD,
    NUMBER_BOX_RADIUS,
    NUMBER_FONT_SIZE,
    PADDING,
    QR_FRAC,
)

CARD_IMAGE_NAME = "card.png"
DEFAULT_DPI = 300
BOX_ALPHA = 0.75
BOX_RADIUS = 3.0
BORDER_RGB = (191, 191, 191)

_FONT_CANDIDATES = {
    "win32": ["arial.ttf", r"C:\Windows\Fonts\arial.ttf"],
    "darwin": [
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
}
_LINUX_FONT_CANDIDATES = [
    "LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_font_path: str | None = None


def _bundled_font() -> str:
    import reportlab

    return os.path.join(os.path.dirname(reportlab.__file__), "fonts", "Vera.ttf")


def find_font() -> str:
    """Return the path of the TrueType font used for card images."""
    global _font_path
    if _font_path is not None:
        return _font_path

    candidates = _FONT_CANDIDATES.get(sys.platform, _LINUX_FONT_CANDIDATES)
    for candidate in candidates:
        try:
            ImageFont.truetype(candidate, 10)
        except OSError:
            continue
        _font_path = candidate
        return candidate

    _font_path = _bundled_font()
    return _font_path


def _font(size_px: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(find_font(), max(round(size_px), 1))


def _fit_text(font: ImageFont.FreeTypeFont, text: str, max_width: float) -> str:
    """Trim *text* to the longest prefix that fits inside *max_width* pixels."""
    if font.getlength(text) <= max_width:
        return text

    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.getlength(text[:mid]) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]


def _white_box(overlay: Image.Image, box: list[float], radius: float) -> None:
    ImageDraw.Draw(overlay).rounded_rectangle(
        box, radius=max(round(radius), 0), fill=(255, 255, 255, round(BOX_ALPHA * 255))
    )


def render_card_image(
    card: dict,
    bg_path: str | None = None,
    number: str | None = None,
    dpi: int = DEFAULT_DPI,
) -> Image.Image:
    """Return *card* (``{msg_path, qr_path}``) drawn as an RGB image at *dpi*."""
    scale = dpi / 72.0
    width = round(CARD_W * scale)
    height = round(CARD_H * scale)

    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))

    # ── background (scaled to fill, centre-cropped) ──────────────────────────
    if bg_path:
        with Image.open(bg_path) as source:
            background = source.convert("RGBA")
        fill = max(width / background.width, height / background.height)
        resized = background.resize(
            (max(round(background.width * fill), 1), max(round(background.height * fill), 1)),
            Image.LANCZOS,
        )
        left = (resized.width - width) // 2
        top = (resized.height - height) // 2
        image.alpha_composite(resized.crop((left, top, left + width, top + height)))

    # ── message text (left two-thirds, vertically centred) ───────────────────
    font = _font(FONT_SIZE * scale)
    line_spacing = LINE_SPACING * scale
    pad = PADDING * scale
    msg_area_w = (CARD_W * MSG_FRAC - PADDING * 2) * scale

    with open(card["msg_path"], encoding="utf-8") as f:
        lines = f.read().splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    lines = [_fit_text(font, line, msg_area_w) for line in lines]

    total_text_h = len(lines) * line_spacing
    block_top = (height - total_text_h) / 2
    box_pad = pad * 0.6

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    _white_box(
        overlay,
        [pad - box_pad, block_top - box_pad * 0.5, pad + msg_area_w + box_pad, block_top + total_text_h + box_pad * 0.5],
        BOX_RADIUS * scale,
    )

    # ── QR code (right third) ────────────────────────────────────────────────
    qr_area_w = CARD_W * QR_FRAC * scale
    qr_size = min(qr_area_w, height) - pad * 2
    qr_left = width - qr_area_w + (qr_area_w - qr_size) / 2
    qr_top = (height - qr_size) / 2

    # ── card number (bottom right, centred under the QR code) ────────────────
    label: tuple[ImageFont.FreeTypeFont, float, float] | None = None
    if number:
        number_font = _font(NUMBER_FONT_SIZE * scale)
        label_w = number_font.getlength(number)
        label_x = qr_left + qr_size / 2
        strip_h = height - (qr_top + qr_size)
        number_h = NUMBER_FONT_SIZE * scale
        # Baseline measured up from the bottom edge, exactly as the PDF does.
        label_baseline = height - ((strip_h - number_h) / 2 + number_h * 0.25)
        _white_box(
            overlay,
            [
                label_x - label_w / 2 - NUMBER_BOX_PAD * scale,
                label_baseline - number_h,
                label_x + label_w / 2 + NUMBER_BOX_PAD * scale,
                label_baseline + number_h * 0.3,
            ],
            NUMBER_BOX_RADIUS * scale,
        )
        label = (number_font, label_x, label_baseline)

    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)

    with Image.open(card["qr_path"]) as qr_source:
        qr = qr_source.convert("RGBA").resize((round(qr_size), round(qr_size)), Image.NEAREST)
    image.alpha_composite(qr, (round(qr_left), round(qr_top)))

    for index, line in enumerate(lines):
        baseline = block_top + line_spacing * (index + 1)
        draw.text((pad, baseline), line, font=font, fill=(0, 0, 0, 255), anchor="ls")

    if label is not None:
        number_font, label_x, label_baseline = label
        draw.text((label_x, label_baseline), number, font=number_font, fill=(0, 0, 0, 255), anchor="ms")

    # ── border ───────────────────────────────────────────────────────────────
    border = max(round(0.5 * scale), 1)
    draw.rectangle([0, 0, width - 1, height - 1], outline=BORDER_RGB + (255,), width=border)

    return image.convert("RGB")


def save_card_image(
    card: dict,
    path: str,
    bg_path: str | None = None,
    number: str | None = None,
    dpi: int = DEFAULT_DPI,
) -> str:
    """Render *card* and write it to *path* as a PNG; returns *path*."""
    image = render_card_image(card, bg_path, number, dpi)
    image.save(path, "PNG", dpi=(dpi, dpi))
    return path

"""Lay out generated cards as a printable business-card PDF."""

from __future__ import annotations

import os
from typing import Callable

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .codes import GocaError

# ── Business card dimensions (standard 3.5" x 2") ────────────────────────────
CARD_W = 3.5 * inch
CARD_H = 2.0 * inch

# Layout inside a card
PADDING = 0.12 * inch
QR_FRAC = 1 / 3          # QR takes right third of the card
MSG_FRAC = 1 - QR_FRAC   # Message takes left two-thirds

# Grid on the page
COLS = 2
ROWS = 5                 # 10 cards per Letter page

# Font
FONT_NAME = "Helvetica"
FONT_SIZE = 9.0
LINE_SPACING = FONT_SIZE * 1.4

CARDS_PER_PAGE = COLS * ROWS

DEFAULT_BACKGROUND_NAMES = ("background.png", "background.jpg", "background.jpeg")

Log = Callable[[str], None]


def find_default_background(folder: str) -> str | None:
    """Return a ``background.*`` image in *folder*, if one exists."""
    for name in DEFAULT_BACKGROUND_NAMES:
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return None


def collect_cards(output_root: str) -> list[dict]:
    """Return a sorted list of ``{code, msg_path, qr_path}`` dicts."""
    if not os.path.isdir(output_root):
        raise GocaError(f"Cards folder not found: {output_root}")

    cards = []
    for name in sorted(os.listdir(output_root)):
        card_dir = os.path.join(output_root, name)
        if not os.path.isdir(card_dir):
            continue
        msg_path = os.path.join(card_dir, "message.txt")
        qr_path = os.path.join(card_dir, "QR.png")
        if os.path.isfile(msg_path) and os.path.isfile(qr_path):
            cards.append({"code": name, "msg_path": msg_path, "qr_path": qr_path})
    return cards


def _fit_text(c: canvas.Canvas, text: str, max_width: float) -> str:
    """Trim *text* to the longest prefix that fits inside *max_width*."""
    if c.stringWidth(text, FONT_NAME, FONT_SIZE) <= max_width:
        return text

    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if c.stringWidth(text[:mid], FONT_NAME, FONT_SIZE) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]


def draw_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    card: dict,
    bg_path: str | None = None,
) -> None:
    """Draw a single business card with its bottom-left corner at (x, y)."""
    # ── background image (centred, fills card, aspect ratio maintained) ───────
    if bg_path:
        img = ImageReader(bg_path)
        iw, ih = img.getSize()
        scale = max(CARD_W / iw, CARD_H / ih)
        draw_w = iw * scale
        draw_h = ih * scale
        bg_x = x + (CARD_W - draw_w) / 2
        bg_y = y + (CARD_H - draw_h) / 2
        c.saveState()
        # clip to card bounds to prevent visual overflow
        p = c.beginPath()
        p.rect(x, y, CARD_W, CARD_H)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(
            bg_path,
            bg_x,
            bg_y,
            draw_w,
            draw_h,
            preserveAspectRatio=False,
            mask="auto",
        )
        c.restoreState()

    # ── border ────────────────────────────────────────────────────────────────
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.setLineWidth(0.5)
    c.rect(x, y, CARD_W, CARD_H)

    # ── QR code (right third) ─────────────────────────────────────────────────
    qr_area_w = CARD_W * QR_FRAC
    qr_size = min(qr_area_w, CARD_H) - PADDING * 2
    qr_x = x + CARD_W - qr_area_w + (qr_area_w - qr_size) / 2
    qr_y = y + (CARD_H - qr_size) / 2
    c.drawImage(
        ImageReader(card["qr_path"]),
        qr_x,
        qr_y,
        qr_size,
        qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )

    # ── message text (left two-thirds, vertically centred) ────────────────────
    msg_area_w = CARD_W * MSG_FRAC - PADDING * 2
    with open(card["msg_path"], encoding="utf-8") as f:
        lines = f.read().splitlines()

    while lines and not lines[-1].strip():
        lines.pop()

    total_text_h = len(lines) * LINE_SPACING
    text_start_y = y + (CARD_H + total_text_h) / 2 - LINE_SPACING  # top baseline

    # White backing box with a small inner margin
    BOX_PAD = PADDING * 0.6
    box_x = x + PADDING - BOX_PAD
    box_y = text_start_y - total_text_h + LINE_SPACING - BOX_PAD * 0.5
    box_w = msg_area_w + BOX_PAD * 2
    box_h = total_text_h + BOX_PAD
    c.saveState()
    c.setFillColorRGB(1, 1, 1, alpha=0.75)
    c.roundRect(box_x, box_y, box_w, box_h, radius=3, fill=1, stroke=0)
    c.restoreState()

    c.setFont(FONT_NAME, FONT_SIZE)
    c.setFillColorRGB(0, 0, 0)

    for i, line in enumerate(lines):
        c.drawString(x + PADDING, text_start_y - i * LINE_SPACING, _fit_text(c, line, msg_area_w))


def build_pdf(
    output_root: str,
    pdf_path: str,
    bg_path: str | None = None,
    log: Log = print,
) -> int:
    """Render every card under *output_root* into *pdf_path*.

    Returns the number of cards written (0 when no cards were found).
    """
    if bg_path and not os.path.isfile(bg_path):
        raise GocaError(f"Background image not found: {bg_path}")

    cards = collect_cards(output_root)
    if not cards:
        log(f"No cards found in {output_root}")
        return 0

    page_w, page_h = LETTER
    grid_w = COLS * CARD_W
    grid_h = ROWS * CARD_H
    origin_x = (page_w - grid_w) / 2
    origin_y = (page_h - grid_h) / 2

    parent = os.path.dirname(os.path.abspath(pdf_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    c = canvas.Canvas(pdf_path, pagesize=LETTER)

    for page_idx in range(0, len(cards), CARDS_PER_PAGE):
        page_cards = cards[page_idx: page_idx + CARDS_PER_PAGE]

        for slot, card in enumerate(page_cards):
            col = slot % COLS
            row = slot // COLS
            # ReportLab y=0 is bottom; fill rows top-to-bottom
            x = origin_x + col * CARD_W
            y = origin_y + (ROWS - 1 - row) * CARD_H
            draw_card(c, x, y, card, bg_path)

        c.showPage()

    c.save()
    log(f"Saved {len(cards)} cards to: {pdf_path}")
    return len(cards)

"""Tests for the optional per-card PNG export."""

import os

from PIL import Image, ImageFont

from goca.cardimage import CARD_IMAGE_NAME, DEFAULT_DPI, find_font, render_card_image, save_card_image
from goca.pdf import CARD_H, CARD_W, QR_FRAC, build_pdf, collect_cards
from tests.test_pdf import make_cards


def card_size(dpi=DEFAULT_DPI):
    return round(CARD_W * dpi / 72), round(CARD_H * dpi / 72)


def ink(image, box):
    """Count dark pixels inside *box*."""
    histogram = image.crop(box).convert("L").histogram()
    return sum(histogram[:100])


def test_find_font_returns_a_loadable_truetype_font():
    ImageFont.truetype(find_font(), 12)


def test_render_card_image_has_business_card_proportions(tmp_path):
    card = collect_cards(str(make_cards(tmp_path, 1)))[0]

    image = render_card_image(card)

    assert image.size == card_size()
    assert image.mode == "RGB"


def test_qr_code_lands_in_the_right_third(tmp_path):
    card = collect_cards(str(make_cards(tmp_path, 1)))[0]

    image = render_card_image(card)
    width, height = image.size
    split = round(width * (1 - QR_FRAC))

    qr_ink = ink(image, (split, 0, width, height))
    message_ink = ink(image, (10, 10, split - 40, height - 10))
    assert qr_ink > 0.1 * (width - split) * height
    assert 0 < message_ink < qr_ink


def test_number_label_adds_ink_under_the_qr_code(tmp_path):
    card = collect_cards(str(make_cards(tmp_path, 1)))[0]

    plain = render_card_image(card)
    numbered = render_card_image(card, number="[1/125]")
    width, height = plain.size
    qr_size = min(width * QR_FRAC, height)
    strip = (round(width * (1 - QR_FRAC)), round((height + qr_size) / 2) + 2, width - 4, height - 4)

    assert ink(plain, strip) == 0
    assert ink(numbered, strip) > 0


def test_background_fills_the_card(tmp_path):
    card = collect_cards(str(make_cards(tmp_path, 1)))[0]
    bg = tmp_path / "bg.png"
    Image.new("RGB", (40, 40), (10, 120, 200)).save(bg)

    image = render_card_image(card, bg_path=str(bg))

    # A pixel inside the border but away from text, box and QR shows the background.
    assert image.getpixel((12, 12)) == (10, 120, 200)


def test_save_card_image_writes_a_png_with_dpi(tmp_path):
    card = collect_cards(str(make_cards(tmp_path, 1)))[0]
    path = tmp_path / "card.png"

    save_card_image(card, str(path))

    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.size == card_size()
        assert tuple(round(v) for v in image.info["dpi"]) == (DEFAULT_DPI, DEFAULT_DPI)


def test_build_pdf_writes_card_images_when_asked(tmp_path):
    out = make_cards(tmp_path, 3)
    messages = []

    count = build_pdf(str(out), str(tmp_path / "cards.pdf"), log=messages.append, images=True)

    assert count == 3
    for card in collect_cards(str(out)):
        assert os.path.isfile(os.path.join(os.path.dirname(card["msg_path"]), CARD_IMAGE_NAME))
    assert messages[-1] == f"Saved a {CARD_IMAGE_NAME} for each card under: {out}"


def test_build_pdf_skips_card_images_by_default(tmp_path):
    out = make_cards(tmp_path, 2)

    build_pdf(str(out), str(tmp_path / "cards.pdf"), log=lambda _: None)

    assert not list(out.rglob(CARD_IMAGE_NAME))


def test_card_images_do_not_become_cards_themselves(tmp_path):
    out = make_cards(tmp_path, 2)
    build_pdf(str(out), str(tmp_path / "cards.pdf"), log=lambda _: None, images=True)

    # A second build still finds exactly the original two cards.
    assert build_pdf(str(out), str(tmp_path / "again.pdf"), log=lambda _: None) == 2

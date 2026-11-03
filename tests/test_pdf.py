"""Tests for the business-card PDF renderer."""

import re

import pytest
from PIL import Image

from goca.codes import GocaError
from goca.generator import process_codes
from goca.pdf import CARDS_PER_PAGE, build_pdf, collect_cards, find_default_background

_PAGE_RE = re.compile(rb"/Type\s*/Page[^s]")


def make_cards(root, count):
    csv_path = root / "codes.csv"
    codes = [f"CODE{i:04d}" for i in range(count)]
    csv_path.write_text(",".join(codes), encoding="utf-8")

    template_path = root / "template.txt"
    template_path.write_text("Code:\n${CODE}\n", encoding="utf-8")

    out = root / "output"
    process_codes(str(csv_path), str(template_path), str(out), log=lambda _: None)
    return out


def page_count(pdf_path):
    return len(_PAGE_RE.findall(pdf_path.read_bytes()))


def test_collect_cards_returns_sorted_entries(tmp_path):
    out = make_cards(tmp_path, 3)

    cards = collect_cards(str(out))

    assert [card["code"] for card in cards] == ["CODE0000", "CODE0001", "CODE0002"]
    assert all(card["msg_path"].endswith("message.txt") for card in cards)
    assert all(card["qr_path"].endswith("QR.png") for card in cards)


def test_collect_cards_ignores_incomplete_folders(tmp_path):
    out = make_cards(tmp_path, 1)
    (out / "HALFCARD").mkdir()

    assert len(collect_cards(str(out))) == 1


def test_collect_cards_missing_folder_raises(tmp_path):
    with pytest.raises(GocaError, match="Cards folder not found"):
        collect_cards(str(tmp_path / "nope"))


def test_build_pdf_creates_one_page(tmp_path):
    out = make_cards(tmp_path, 3)
    pdf_path = tmp_path / "cards.pdf"

    count = build_pdf(str(out), str(pdf_path), log=lambda _: None)

    assert count == 3
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert page_count(pdf_path) == 1


def test_build_pdf_paginates(tmp_path):
    out = make_cards(tmp_path, CARDS_PER_PAGE + 2)
    pdf_path = tmp_path / "cards.pdf"

    count = build_pdf(str(out), str(pdf_path), log=lambda _: None)

    assert count == CARDS_PER_PAGE + 2
    assert page_count(pdf_path) == 2


def test_build_pdf_creates_missing_parent_folder(tmp_path):
    out = make_cards(tmp_path, 1)
    pdf_path = tmp_path / "nested" / "deeper" / "cards.pdf"

    build_pdf(str(out), str(pdf_path), log=lambda _: None)

    assert pdf_path.is_file()


def test_build_pdf_uses_background_image(tmp_path):
    out = make_cards(tmp_path, 2)
    bg = tmp_path / "background.png"
    Image.new("RGB", (400, 200), (10, 120, 200)).save(bg)
    pdf_path = tmp_path / "cards.pdf"

    count = build_pdf(str(out), str(pdf_path), bg_path=str(bg), log=lambda _: None)

    assert count == 2
    assert pdf_path.stat().st_size > 1000


def test_build_pdf_missing_background_raises(tmp_path):
    out = make_cards(tmp_path, 1)

    with pytest.raises(GocaError, match="Background image not found"):
        build_pdf(str(out), str(tmp_path / "cards.pdf"), str(tmp_path / "nope.png"), log=lambda _: None)


def test_build_pdf_without_cards_returns_zero_and_writes_nothing(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    pdf_path = tmp_path / "cards.pdf"
    messages = []

    count = build_pdf(str(out), str(pdf_path), log=messages.append)

    assert count == 0
    assert not pdf_path.exists()
    assert messages == [f"No cards found in {out}"]


def test_build_pdf_logs_destination(tmp_path):
    out = make_cards(tmp_path, 1)
    pdf_path = tmp_path / "cards.pdf"
    messages = []

    build_pdf(str(out), str(pdf_path), log=messages.append)

    assert messages == [f"Saved 1 cards to: {pdf_path}"]


def test_clean_run_keeps_only_the_current_codes(tmp_path):
    out = make_cards(tmp_path, 3)

    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("CODE9999", encoding="utf-8")
    template_path = tmp_path / "template.txt"
    template_path.write_text("Code:\n${CODE}\n", encoding="utf-8")

    process_codes(str(csv_path), str(template_path), str(out), clean=True, log=lambda _: None)

    assert [card["code"] for card in collect_cards(str(out))] == ["CODE9999"]
    assert build_pdf(str(out), str(tmp_path / "cards.pdf"), log=lambda _: None) == 1


def test_find_default_background(tmp_path):
    assert find_default_background(str(tmp_path)) is None

    png = tmp_path / "background.png"
    png.write_bytes(b"\x89PNG")
    assert find_default_background(str(tmp_path)) == str(png)

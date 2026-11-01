"""Tests for the card generation pipeline."""

import pytest
from PIL import Image

from goca.codes import GocaError
from goca.generator import process_codes

TEMPLATE = "Code:\n${CODE}\nExpires:\n${EXPIRY}\nThanks for coming!\n"


@pytest.fixture()
def workspace(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("AAAA1111,BBBB2222\nCCCC3333\n", encoding="utf-8")

    template_path = tmp_path / "template.txt"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    return tmp_path, csv_path, template_path


def test_process_codes_writes_message_and_qr(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"

    summary = process_codes(str(csv_path), str(template_path), str(out), "July 31st 2026", log=lambda _: None)

    assert summary["total"] == 3
    assert summary["written"] == 3
    assert summary["skipped"] == []

    for code in ("AAAA1111", "BBBB2222", "CCCC3333"):
        card_dir = out / code
        assert card_dir.is_dir()
        assert (card_dir / "message.txt").read_text(encoding="utf-8") == (
            f"Code:\n{code}\nExpires:\nJuly 31st 2026\nThanks for coming!\n"
        )
        with Image.open(card_dir / "QR.png") as qr:
            assert qr.format == "PNG"
            assert qr.width == qr.height > 0


def test_process_codes_is_idempotent(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"

    process_codes(str(csv_path), str(template_path), str(out), log=lambda _: None)
    summary = process_codes(str(csv_path), str(template_path), str(out), log=lambda _: None)

    assert summary["written"] == 3
    assert len(list(out.iterdir())) == 3


def test_process_codes_skips_unsafe_codes(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("AAAA1111,../escape\n", encoding="utf-8")
    template_path = tmp_path / "template.txt"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    messages = []
    summary = process_codes(
        str(csv_path), str(template_path), str(tmp_path / "out"), log=messages.append
    )

    assert summary["written"] == 1
    assert summary["skipped"] == ["../escape"]
    assert not (tmp_path / "escape").exists()
    assert any("Skipping invalid code" in message for message in messages)


def test_process_codes_without_codes_raises(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("", encoding="utf-8")
    template_path = tmp_path / "template.txt"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    with pytest.raises(GocaError, match="No codes found"):
        process_codes(str(csv_path), str(template_path), str(tmp_path / "out"), log=lambda _: None)


def test_process_codes_logs_progress(workspace):
    root, csv_path, template_path = workspace
    messages = []

    process_codes(str(csv_path), str(template_path), str(root / "out"), log=messages.append)

    assert messages[0] == "Processing 3 codes..."
    assert messages[-1] == "Done."

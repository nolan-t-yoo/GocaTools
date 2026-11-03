"""Tests for the card generation pipeline."""

import os

import pytest
from PIL import Image

from goca import ROOT
from goca.codes import GocaError
from goca.generator import clean_cards_folder, process_codes

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


def test_process_codes_leaves_existing_folders_alone_by_default(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"
    stale = out / "OLDCARD0000"
    stale.mkdir(parents=True)
    (stale / "message.txt").write_text("old", encoding="utf-8")

    summary = process_codes(str(csv_path), str(template_path), str(out), log=lambda _: None)

    assert summary["cleaned"] == 0
    assert stale.is_dir()


def test_process_codes_clean_removes_stale_cards_and_files(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"
    stale = out / "OLDCARD0000"
    stale.mkdir(parents=True)
    (stale / "message.txt").write_text("old", encoding="utf-8")
    (stale / "QR.png").write_bytes(b"old")
    (out / "notes.txt").write_text("keep out", encoding="utf-8")

    summary = process_codes(
        str(csv_path), str(template_path), str(out), clean=True, log=lambda _: None
    )

    assert summary["cleaned"] == 2
    assert not stale.exists()
    assert not (out / "notes.txt").exists()
    assert sorted(p.name for p in out.iterdir()) == ["AAAA1111", "BBBB2222", "CCCC3333"]


def test_process_codes_clean_logs_what_it_removed(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"
    (out / "OLDCARD0000").mkdir(parents=True)
    messages = []

    process_codes(str(csv_path), str(template_path), str(out), clean=True, log=messages.append)

    assert messages[0] == f"Cleaned 1 old item from {out}"
    assert messages[1] == "Processing 3 codes..."


def test_clean_skipped_when_the_codes_file_is_invalid(tmp_path):
    out = tmp_path / "output"
    keep = out / "KEEP0000"
    keep.mkdir(parents=True)
    template_path = tmp_path / "template.txt"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    with pytest.raises(GocaError, match="Codes file not found"):
        process_codes(
            str(tmp_path / "missing.csv"), str(template_path), str(out),
            clean=True, log=lambda _: None,
        )

    assert keep.is_dir()


def test_clean_skipped_when_the_list_is_empty(tmp_path):
    out = tmp_path / "output"
    keep = out / "KEEP0000"
    keep.mkdir(parents=True)
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("# nothing here\n", encoding="utf-8")
    template_path = tmp_path / "template.txt"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    with pytest.raises(GocaError, match="No codes found"):
        process_codes(
            str(csv_path), str(template_path), str(out), clean=True, log=lambda _: None
        )

    assert keep.is_dir()


def test_clean_cards_folder_missing_folder_is_a_no_op(tmp_path):
    assert clean_cards_folder(str(tmp_path / "does-not-exist"), log=lambda _: None) == 0


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(lambda: ROOT, id="project-folder"),
        pytest.param(lambda: os.path.dirname(ROOT), id="parent-of-project"),
        pytest.param(lambda: os.path.expanduser("~"), id="home-folder"),
        pytest.param(lambda: os.path.realpath(os.sep), id="drive-root"),
    ],
)
def test_clean_cards_folder_refuses_dangerous_folders(target):
    with pytest.raises(GocaError, match="Refusing to clean"):
        clean_cards_folder(target(), log=lambda _: None)

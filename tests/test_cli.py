"""Tests for the command line entry points."""

import pytest

import createpdf
import pokemon

TEMPLATE = "Code:\n${CODE}\nExpires:\n${EXPIRY}\n"


@pytest.fixture()
def workspace(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("AAAA1111,BBBB2222", encoding="utf-8")

    template_path = tmp_path / "template.txt"
    template_path.write_text(TEMPLATE, encoding="utf-8")

    return tmp_path, csv_path, template_path


def test_pokemon_cli_generates_cards(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"

    assert pokemon.main([str(csv_path), str(template_path), "-o", str(out), "-e", "Soon"]) == 0

    assert (out / "AAAA1111" / "message.txt").read_text(encoding="utf-8") == (
        "Code:\nAAAA1111\nExpires:\nSoon\n"
    )
    assert (out / "BBBB2222" / "QR.png").is_file()


def test_pokemon_cli_cleans_the_cards_folder_by_default(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"
    stale = out / "OLDCARD0000"
    stale.mkdir(parents=True)
    (stale / "message.txt").write_text("old", encoding="utf-8")

    assert pokemon.main([str(csv_path), str(template_path), "-o", str(out)]) == 0

    assert not stale.exists()
    assert (out / "AAAA1111" / "message.txt").is_file()


def test_pokemon_cli_keeps_existing_folders_with_no_clean(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"
    stale = out / "OLDCARD0000"
    stale.mkdir(parents=True)
    (stale / "message.txt").write_text("old", encoding="utf-8")

    assert pokemon.main([str(csv_path), str(template_path), "-o", str(out), "--no-clean"]) == 0

    assert stale.is_dir()
    assert (out / "AAAA1111" / "message.txt").is_file()


def test_pokemon_cli_reports_missing_csv(workspace, capsys):
    root, _, template_path = workspace

    with pytest.raises(SystemExit) as excinfo:
        pokemon.main([str(root / "nope.csv"), str(template_path)])

    assert excinfo.value.code == 2
    assert "Codes file not found" in capsys.readouterr().err


def test_createpdf_cli_builds_pdf(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"
    pokemon.main([str(csv_path), str(template_path), "-o", str(out)])

    pdf_path = root / "cards.pdf"
    assert createpdf.main([str(out), "-p", str(pdf_path)]) == 0

    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_createpdf_cli_reports_missing_folder(workspace, capsys):
    root, _, _ = workspace

    with pytest.raises(SystemExit) as excinfo:
        createpdf.main([str(root / "nope"), "-p", str(root / "cards.pdf")])

    assert excinfo.value.code == 2
    assert "Cards folder not found" in capsys.readouterr().err


def test_createpdf_cli_numbers_cards_when_asked(workspace, monkeypatch):
    from reportlab import rl_config

    monkeypatch.setattr(rl_config, "pageCompression", 0)
    root, csv_path, template_path = workspace
    out = root / "output"
    pokemon.main([str(csv_path), str(template_path), "-o", str(out)])
    total = 2  # AAAA1111, BBBB2222

    plain = root / "plain.pdf"
    assert createpdf.main([str(out), "-p", str(plain)]) == 0
    assert f"[1/{total}]".encode() not in plain.read_bytes()

    numbered = root / "numbered.pdf"
    assert createpdf.main([str(out), "-p", str(numbered), "--numbered"]) == 0
    assert f"[1/{total}]".encode() in numbered.read_bytes()


def test_createpdf_cli_writes_card_pngs_when_asked(workspace):
    root, csv_path, template_path = workspace
    out = root / "output"
    pokemon.main([str(csv_path), str(template_path), "-o", str(out)])

    assert createpdf.main([str(out), "-p", str(root / "cards.pdf")]) == 0
    assert not (out / "AAAA1111" / "card.png").exists()

    assert createpdf.main([str(out), "-p", str(root / "cards.pdf"), "--png"]) == 0
    assert (out / "AAAA1111" / "card.png").is_file()
    assert (out / "BBBB2222" / "card.png").is_file()

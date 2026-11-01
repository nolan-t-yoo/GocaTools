"""Tests for CSV/template parsing and message rendering."""

import pytest

from goca.codes import (
    DEFAULT_EXPIRY,
    GocaError,
    is_safe_dir_name,
    load_codes,
    load_template,
    redemption_url,
    render_message,
)


def test_load_codes_splits_csv_cells(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("AAAA1111, BBBB2222,CCCC3333\n", encoding="utf-8")

    assert load_codes(str(csv_path)) == ["AAAA1111", "BBBB2222", "CCCC3333"]


def test_load_codes_splits_newlines_inside_a_cell(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text('"AAAA1111\nBBBB2222"\nCCCC3333\n', encoding="utf-8")

    assert load_codes(str(csv_path)) == ["AAAA1111", "BBBB2222", "CCCC3333"]


def test_load_codes_ignores_header_comments_and_blanks(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text(
        "code\nAAAA1111\n# a note\n\n  BBBB2222  \n", encoding="utf-8"
    )

    assert load_codes(str(csv_path)) == ["AAAA1111", "BBBB2222"]


def test_load_codes_handles_utf8_bom(tmp_path):
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("AAAA1111", encoding="utf-8-sig")

    assert load_codes(str(csv_path)) == ["AAAA1111"]


def test_load_codes_missing_file_raises(tmp_path):
    with pytest.raises(GocaError, match="Codes file not found"):
        load_codes(str(tmp_path / "nope.csv"))


def test_load_template_roundtrip(tmp_path):
    path = tmp_path / "template.txt"
    path.write_text("Code: ${CODE}", encoding="utf-8")

    assert load_template(str(path)) == "Code: ${CODE}"


def test_load_template_missing_file_raises(tmp_path):
    with pytest.raises(GocaError, match="Template file not found"):
        load_template(str(tmp_path / "nope.txt"))


def test_render_message_substitutes_both_placeholders():
    template = "Code:\n${CODE}\nExpires:\n${EXPIRY}\n"

    rendered = render_message(template, "AAAA1111", "July 31st 2026")

    assert rendered == "Code:\nAAAA1111\nExpires:\nJuly 31st 2026\n"


def test_default_expiry_is_na():
    assert DEFAULT_EXPIRY == "N/A"


def test_redemption_url_embeds_the_code():
    assert redemption_url("AAAA1111") == (
        "https://store.pokemongo.com/offer-redemption?passcode=AAAA1111"
    )


@pytest.mark.parametrize(
    "name",
    ["AAAA1111", "abc-def", "abc_def", "123", "a" * 40],
)
def test_is_safe_dir_name_accepts_codes(name):
    assert is_safe_dir_name(name)


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "../escape", "a/b", "a\\b", "with space", "nul*", "ünicode"],
)
def test_is_safe_dir_name_rejects_unsafe_names(name):
    assert not is_safe_dir_name(name)

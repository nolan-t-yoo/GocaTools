"""Reading code lists and templates, and rendering messages and QR images."""

from __future__ import annotations

import csv
import os
import re

DEFAULT_EXPIRY = "N/A"
REDEMPTION_URL = "https://store.pokemongo.com/offer-redemption?passcode={code}"

# Codes are used as directory names, so keep them to a safe character set.
_SAFE_CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# A first CSV cell matching one of these is treated as a column header.
_HEADER_WORDS = {
    "code",
    "codes",
    "passcode",
    "passcodes",
    "redemption code",
    "redemption codes",
    "qr",
    "qrcode",
}


class GocaError(Exception):
    """Raised for input problems that should be shown to the user as-is."""


def is_safe_dir_name(name: str) -> bool:
    """Return True when *name* is safe to use as a single directory name."""
    return name not in {".", ".."} and bool(_SAFE_CODE_RE.match(name))


def load_codes(csv_path: str) -> list[str]:
    """Read codes from a CSV, one per cell or one per line inside a cell."""
    if not os.path.isfile(csv_path):
        raise GocaError(f"Codes file not found: {csv_path}")

    codes: list[str] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            for cell in row:
                for part in cell.splitlines():
                    code = part.strip().strip('"').strip("'").strip()
                    if not code or code.startswith("#"):
                        continue
                    if not codes and code.lower() in _HEADER_WORDS:
                        continue
                    codes.append(code)
    return codes


def load_template(template_path: str) -> str:
    """Read the message template file."""
    if not os.path.isfile(template_path):
        raise GocaError(f"Template file not found: {template_path}")
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def render_message(template: str, code: str, expiry: str) -> str:
    """Substitute ``${CODE}`` and ``${EXPIRY}`` placeholders in *template*."""
    return template.replace("${CODE}", code).replace("${EXPIRY}", expiry)


def redemption_url(code: str) -> str:
    """Build the store redemption URL for *code*."""
    return REDEMPTION_URL.format(code=code)


def generate_qr(url: str, output_path: str) -> None:
    """Write a PNG QR code encoding *url* to *output_path*."""
    import qrcode

    qrcode.make(url).save(output_path)

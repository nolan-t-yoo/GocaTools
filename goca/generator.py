"""Turn a list of codes into per-code folders holding a message and a QR code."""

from __future__ import annotations

import os
from typing import Callable

from .codes import (
    DEFAULT_EXPIRY,
    GocaError,
    generate_qr,
    is_safe_dir_name,
    load_codes,
    load_template,
    redemption_url,
    render_message,
)

Log = Callable[[str], None]


def process_codes(
    csv_path: str,
    template_path: str,
    output_dir: str,
    expiry: str = DEFAULT_EXPIRY,
    log: Log = print,
) -> dict:
    """Create ``<output_dir>/<CODE>/{message.txt,QR.png}`` for every code.

    Returns a summary with ``total``, ``written``, ``skipped`` and
    ``output_dir`` keys.
    """
    codes = load_codes(csv_path)
    template = load_template(template_path)

    if not codes:
        raise GocaError(f"No codes found in {csv_path}")

    log(f"Processing {len(codes)} codes...")

    written = 0
    skipped: list[str] = []

    for code in codes:
        if not is_safe_dir_name(code):
            skipped.append(code)
            log(f"  Skipping invalid code {code!r} (letters, digits, '-' and '_' only)")
            continue

        code_dir = os.path.join(output_dir, code)
        os.makedirs(code_dir, exist_ok=True)

        msg_path = os.path.join(code_dir, "message.txt")
        with open(msg_path, "w", encoding="utf-8") as f:
            f.write(render_message(template, code, expiry))

        qr_path = os.path.join(code_dir, "QR.png")
        generate_qr(redemption_url(code), qr_path)

        written += 1
        log(f"  [{code}] -> {code_dir}")

    if skipped:
        log(f"Done. {written} cards written, {len(skipped)} codes skipped.")
    else:
        log("Done.")

    return {
        "total": len(codes),
        "written": written,
        "skipped": skipped,
        "output_dir": output_dir,
    }

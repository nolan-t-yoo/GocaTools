"""Turn a list of codes into per-code folders holding a message and a QR code."""

from __future__ import annotations

import os
import shutil
from typing import Callable

from . import ROOT
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


def clean_cards_folder(output_dir: str, log: Log = print) -> int:
    """Delete everything inside *output_dir*; return how many entries were removed.

    Only the contents are removed, so the folder itself survives. Paths that would
    be dangerous to empty (drive root, home folder, the project folder or any
    parent of it) are refused.
    """
    if not os.path.isdir(output_dir):
        return 0

    target = os.path.realpath(output_dir)
    project = os.path.realpath(ROOT)
    protected = {
        os.path.realpath(os.sep),
        os.path.realpath(os.path.expanduser("~")),
        project,
    }

    if target in protected or project.startswith(target + os.sep):
        raise GocaError(
            f"Refusing to clean {output_dir}. Pick a dedicated cards folder "
            "instead of your home folder, a drive root or the project folder."
        )

    removed = 0
    for name in os.listdir(output_dir):
        entry = os.path.join(output_dir, name)
        try:
            if os.path.isdir(entry) and not os.path.islink(entry):
                shutil.rmtree(entry)
            else:
                os.remove(entry)
        except OSError as exc:
            raise GocaError(f"Could not clean {entry}: {exc}") from exc
        removed += 1

    log(f"Cleaned {removed} old item{'s' if removed != 1 else ''} from {output_dir}")
    return removed


def process_codes(
    csv_path: str,
    template_path: str,
    output_dir: str,
    expiry: str = DEFAULT_EXPIRY,
    clean: bool = False,
    log: Log = print,
) -> dict:
    """Create ``<output_dir>/<CODE>/{message.txt,QR.png}`` for every code.

    When *clean* is true the cards folder is emptied first, so a PDF built
    afterwards only contains the codes from this run.

    Returns a summary with ``total``, ``written``, ``skipped``, ``cleaned`` and
    ``output_dir`` keys.
    """
    codes = load_codes(csv_path)
    template = load_template(template_path)

    if not codes:
        raise GocaError(f"No codes found in {csv_path}")

    # Only touch the folder once the inputs are known to be usable.
    removed = clean_cards_folder(output_dir, log=log) if clean else 0

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
        "cleaned": removed,
        "output_dir": output_dir,
    }

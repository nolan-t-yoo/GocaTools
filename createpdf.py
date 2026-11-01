#!/usr/bin/env python3
"""CLI: lay generated cards out on a printable business-card PDF.

Example:
    python createpdf.py --pdf cards.pdf --background background.png
"""

from __future__ import annotations

import argparse
import os

from goca import ROOT
from goca.codes import GocaError
from goca.pdf import build_pdf, find_default_background


def main(argv: list[str] | None = None) -> int:
    default_input = os.path.join(ROOT, "output")
    default_pdf = os.path.join(ROOT, "cards.pdf")

    parser = argparse.ArgumentParser(
        description="Assemble pokemon.py output into a business-card PDF."
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=default_input,
        help=f"Root cards directory produced by pokemon.py (default: {default_input})",
    )
    parser.add_argument(
        "--pdf",
        "-p",
        default=default_pdf,
        help=f"Destination PDF file (default: {default_pdf})",
    )
    parser.add_argument(
        "--background",
        "-b",
        default=find_default_background(ROOT),
        help="Background image centred on each card (optional; auto-detects background.png/.jpg next to this script)",
    )

    args = parser.parse_args(argv)

    try:
        build_pdf(args.output_dir, args.pdf, args.background)
    except GocaError as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

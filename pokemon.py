#!/usr/bin/env python3
"""CLI: generate card data (message + QR) for a list of codes.

Example:
    python pokemon.py codes.csv template.txt -e "July 31st 2026"
"""

from __future__ import annotations

import argparse
import os

from goca import ROOT
from goca.codes import DEFAULT_EXPIRY, GocaError
from goca.generator import process_codes


def main(argv: list[str] | None = None) -> int:
    default_output = os.path.join(ROOT, "output")

    parser = argparse.ArgumentParser(
        description="Generate Pokemon GO redemption URLs and QR codes from a CSV of codes."
    )
    parser.add_argument("csv", help="Path to the CSV file containing redemption codes.")
    parser.add_argument(
        "template",
        nargs="?",
        default=os.path.join(ROOT, "template.txt"),
        help="Path to the message template .txt file (default: template.txt next to this script).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=default_output,
        help=f"Root output directory (default: {default_output})",
    )
    parser.add_argument(
        "--expiry",
        "-e",
        default=DEFAULT_EXPIRY,
        help=f'Expiry text substituted for ${{EXPIRY}} in the template (default: "{DEFAULT_EXPIRY}")',
    )

    args = parser.parse_args(argv)

    try:
        process_codes(args.csv, args.template, args.output, args.expiry)
    except GocaError as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

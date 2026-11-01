"""GocaTools - generate Pokemon GO redemption business cards with QR codes."""

from __future__ import annotations

import os

__version__ = "1.0.0"
__all__ = ["ROOT", "__version__"]

# Repository root (the folder holding template.txt, launch.bat, ...).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

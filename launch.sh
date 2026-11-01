#!/usr/bin/env bash
# Launch the GocaTools desktop UI (Linux / macOS).
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================================"
echo " GocaTools - Pokemon GO redemption card generator"
echo "============================================================"

# ── 1. Locate a Python 3.9+ interpreter ──────────────────────────────────────
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "[ERROR] Python 3.9 or newer was not found." >&2
    echo "        Install it from https://www.python.org/downloads/ and try again." >&2
    exit 1
fi

# ── 2. Create (or reuse) a virtual environment inside this folder ────────────
VPY=".venv/bin/python"
if [ ! -x "$VPY" ]; then
    echo "Creating a private Python environment in .venv ..."
    "$PY" -m venv .venv
fi

# ── 3. Install the two small dependencies on first run ──────────────────────
if ! "$VPY" -c 'import qrcode, reportlab' >/dev/null 2>&1; then
    echo "Installing dependencies (qrcode, pillow, reportlab) - first run only ..."
    "$VPY" -m pip install --upgrade pip >/dev/null 2>&1 || true
    "$VPY" -m pip install 'qrcode[pil]' reportlab
fi

# ── 4. Start the UI ─────────────────────────────────────────────────────────
if ! "$VPY" -c 'import tkinter' >/dev/null 2>&1; then
    echo "[ERROR] This Python installation has no tkinter, so the UI cannot start." >&2
    echo "        Debian/Ubuntu: sudo apt install python3-tk" >&2
    echo "        Fedora:        sudo dnf install python3-tkinter" >&2
    echo "        macOS:         brew install python-tk" >&2
    exit 1
fi

echo "Starting GocaTools ..."
exec "$VPY" -m goca

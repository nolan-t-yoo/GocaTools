"""Shared test fixtures: make the repository importable without installing."""

import gc
import os
import sys
import time
import tkinter as tk

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def tk_root():
    """One Tk interpreter for the whole run, skipped when no display exists."""
    widget = None
    error = None
    # Tk initialisation occasionally fails on first use in a fresh interpreter,
    # so give it a couple of tries before treating the display as unavailable.
    for _ in range(3):
        try:
            widget = tk.Tk()
            break
        except tk.TclError as exc:  # pragma: no cover - headless machines
            error = exc
            time.sleep(0.2)

    if widget is None:  # pragma: no cover - headless machines
        pytest.skip(f"tkinter display unavailable: {error}")

    widget.withdraw()
    try:
        yield widget
    finally:
        widget.destroy()


@pytest.fixture()
def clean_tk(tk_root):
    """Share the interpreter, but release this test's widgets while it is alive."""
    yield tk_root
    for child in tk_root.winfo_children():
        child.destroy()
    gc.collect()

from __future__ import annotations

import tkinter as tk


def configure_window(
    window: tk.Tk,
    title: str,
    geometry: str,
    *,
    minimum_size: tuple[int, int] = (1100, 700),
) -> None:
    """Apply the common size and visual defaults used by project plot GUIs."""
    window.title(title)
    window.geometry(geometry)
    window.minsize(*minimum_size)
    window.option_add("*Font", ("Segoe UI", 9))

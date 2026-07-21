import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

def build_guide_panel(parent: ttk.Frame, chapter_items: tuple[tuple[str, str], ...]) -> None:
    chapters = ttk.Notebook(parent); chapters.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    for title, content in chapter_items:
        frame = ttk.Frame(chapters); chapters.add(frame, text=title)
        text = ScrolledText(frame, wrap=tk.WORD, font=("TkDefaultFont", 10), padx=14, pady=12, spacing1=2, spacing3=4)
        text.pack(fill=tk.BOTH, expand=True); text.insert("1.0", content.strip()); text.configure(state=tk.DISABLED)

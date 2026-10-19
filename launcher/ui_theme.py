"""The launcher's look (20/10): charcoal panels, a deep-red glow at the top, gold headline, player cards edged
green (you) / gold (AI) / grey (empty), one big red button. Pure tkinter + Pillow (no new dependency)."""
import tkinter as tk
from tkinter import ttk

BG = "#141414"          # window
BG2 = "#1c1c1c"         # cards
BG3 = "#262626"         # fields
LINE = "#343434"
TEXT = "#ececec"
MUTED = "#9a9a9a"
GOLD = "#d9b24c"
GOLD2 = "#f0d58a"
GREEN = "#3ec46a"
RED = "#c8252c"
RED_H = "#e03a41"
AMBER = "#e0a030"
GREY = "#4a4a4a"

FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_S = ("Segoe UI", 9)
FONT_TITLE = ("Cambria", 24, "bold")
FONT_H = ("Segoe UI", 11, "bold")

# AoE 1 player colours by seat (1..8)
PLAYER_COLOURS = ["#2a63d8", "#d62b2b", "#e2c62a", "#8a5a2b", "#e8782a", "#2fa34c", "#a0a0a0", "#2bbfd0"]


def backdrop(w, h):
    """The window backdrop: charcoal with a red glow fading from the top centre (a PhotoImage)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    img = Image.new("RGB", (w, h), BG)
    glow = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(glow)
    d.ellipse((w * 0.1, -h * 0.55, w * 0.9, h * 0.35), fill=140)
    glow = glow.filter(ImageFilter.GaussianBlur(h * 0.12))
    red = Image.new("RGB", (w, h), "#5a0f14")
    img = Image.composite(red, img, glow)
    return ImageTk.PhotoImage(img)


def app_icon():
    """A small gold roundel with "D3" (the window and taskbar icon)."""
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill="#1c1c1c", outline=GOLD, width=4)
    try:
        f = ImageFont.truetype("cambriab.ttf", 30)
    except OSError:
        f = ImageFont.load_default()
    d.text((32, 33), "D3", fill=GOLD2, font=f, anchor="mm")
    return ImageTk.PhotoImage(img)


def style(root):
    """ttk widgets in the dark theme (clam as the base: it takes colours)."""
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=BG2, foreground=TEXT, font=FONT, bordercolor=LINE, lightcolor=BG2, darkcolor=BG2)
    st.configure("TCombobox", fieldbackground=BG3, background=BG3, foreground=TEXT, arrowcolor=MUTED,
                 selectbackground=BG3, selectforeground=TEXT, padding=(6, 3), insertcolor=TEXT)
    st.map("TCombobox", fieldbackground=[("readonly", BG3), ("disabled", BG2)], foreground=[("disabled", MUTED)],
           arrowcolor=[("active", GOLD)], bordercolor=[("focus", GOLD)])
    st.configure("TEntry", fieldbackground=BG3, foreground=TEXT, insertcolor=TEXT, padding=(6, 3))
    st.map("TEntry", bordercolor=[("focus", GOLD)])
    st.configure("TSpinbox", fieldbackground=BG3, foreground=TEXT, arrowcolor=MUTED, padding=(4, 2))
    st.configure("TScrollbar", background=BG3, troughcolor=BG, arrowcolor=MUTED, bordercolor=BG)
    root.option_add("*TCombobox*Listbox.background", BG3)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", GOLD)
    root.option_add("*TCombobox*Listbox.selectForeground", "#111111")
    root.option_add("*TCombobox*Listbox.font", "{Segoe UI} 10")
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    return st


class Button(tk.Label):
    """A flat button with hover / pressed / disabled looks. kind: "primary" (red), "gold", "ghost"."""

    LOOKS = {
        "primary": dict(bg=RED, fg="#ffffff", hover=RED_H, font=("Segoe UI", 12, "bold"), pad=(26, 10)),
        "gold": dict(bg=GOLD, fg="#1a1a1a", hover=GOLD2, font=FONT_B, pad=(14, 6)),
        "ghost": dict(bg=BG3, fg=TEXT, hover="#333333", font=FONT, pad=(12, 5)),
        "tiny": dict(bg=BG2, fg=MUTED, hover="#3a2222", font=FONT_B, pad=(6, 1)),
    }

    def __init__(self, parent, text, command=None, kind="ghost", **kw):
        look = self.LOOKS[kind]
        self.look, self.command, self.enabled = look, command, True
        super().__init__(parent, text=text, bg=look["bg"], fg=look["fg"], font=look["font"], cursor="hand2",
                         padx=look["pad"][0], pady=look["pad"][1], **kw)
        self.bind("<Enter>", lambda e: self.enabled and self.configure(bg=look["hover"]))
        self.bind("<Leave>", lambda e: self.enabled and self.configure(bg=look["bg"]))
        self.bind("<Button-1>", self._click)

    def _click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self.configure(bg=self.look["bg"] if on else GREY, fg=self.look["fg"] if on else "#8a8a8a",
                       cursor="hand2" if on else "arrow")


class Card(tk.Frame):
    """A panel with a thin edge (colour = state) and an optional heading."""

    def __init__(self, parent, title=None, edge=LINE, pad=12, **kw):
        super().__init__(parent, bg=BG2, highlightthickness=1, highlightbackground=edge, highlightcolor=edge,
                         padx=pad, pady=pad, **kw)
        if title:
            tk.Label(self, text=title, bg=BG2, fg=GOLD, font=FONT_H).pack(anchor="w", pady=(0, 6))

    def set_edge(self, colour):
        self.configure(highlightbackground=colour, highlightcolor=colour)


def label(parent, text, muted=False, **kw):
    return tk.Label(parent, text=text, bg=kw.pop("bg", BG2), fg=MUTED if muted else TEXT,
                    font=kw.pop("font", FONT_S if muted else FONT), **kw)


def field(parent, var, values, width=16, state="readonly", on_change=None):
    cb = ttk.Combobox(parent, textvariable=var, values=values, width=width, state=state)
    if on_change:
        cb.bind("<<ComboboxSelected>>", lambda e: on_change())
    return cb

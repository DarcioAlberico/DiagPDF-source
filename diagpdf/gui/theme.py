"""Widget styling, in a light and a dark variant."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str
    card: str
    border: str
    accent: str
    accent_hover: str
    accent_disabled: str
    fg: str
    fg_muted: str
    ok: str
    error: str


LIGHT = Palette(
    bg='#F0F4F8', card='#FFFFFF', border='#CBD5E1',
    accent='#2563EB', accent_hover='#1D4ED8', accent_disabled='#94A3B8',
    fg='#0F172A', fg_muted='#64748B', ok='#15803D', error='#B91C1C',
)

DARK = Palette(
    bg='#1E1E1E', card='#2A2A2A', border='#3F3F46',
    accent='#3B82F6', accent_hover='#60A5FA', accent_disabled='#52525B',
    fg='#E5E5E5', fg_muted='#A1A1AA', ok='#4ADE80', error='#F87171',
)

FONT_FAMILY = 'Segoe UI'


def palette_for(theme: str) -> Palette:
    return DARK if theme == 'dark' else LIGHT


def apply_theme(root, ttk, theme: str = 'light') -> Palette:
    """Style *root* for the requested theme and return its palette."""
    colours = palette_for(theme)
    style = ttk.Style(root)

    try:
        import sv_ttk  # type: ignore[import]
        sv_ttk.set_theme('dark' if theme == 'dark' else 'light')
    except ImportError:
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        root.configure(bg=colours.bg)
        style.configure('.', background=colours.bg, foreground=colours.fg, font=(FONT_FAMILY, 9))
        style.configure('TFrame', background=colours.bg)
        style.configure('TLabelframe', background=colours.bg, foreground=colours.fg)
        style.configure('TLabelframe.Label', background=colours.bg, foreground=colours.fg)
        style.configure('TLabel', background=colours.bg, foreground=colours.fg, font=(FONT_FAMILY, 9))
        style.configure('TCheckbutton', background=colours.bg, foreground=colours.fg, font=(FONT_FAMILY, 9))
        style.configure('TRadiobutton', background=colours.bg, foreground=colours.fg, font=(FONT_FAMILY, 9))
        style.configure('TEntry', fieldbackground=colours.card, foreground=colours.fg,
                        insertcolor=colours.fg, bordercolor=colours.border,
                        lightcolor=colours.border, darkcolor=colours.border)
        style.configure('TCombobox', fieldbackground=colours.card, background=colours.card,
                        foreground=colours.fg, selectbackground=colours.accent,
                        selectforeground=colours.card, bordercolor=colours.border,
                        arrowcolor=colours.fg_muted)
        style.map('TCombobox', fieldbackground=[('readonly', colours.card)])

    style.configure('SectionHdr.TLabel', foreground=colours.accent, font=(FONT_FAMILY, 8, 'bold'))
    style.configure('Accent.TButton',
                    background=colours.accent, foreground='white',
                    font=(FONT_FAMILY, 10, 'bold'), relief='flat', borderwidth=0,
                    focuscolor=colours.accent, padding=(20, 8))
    style.map('Accent.TButton',
              background=[('active', colours.accent_hover), ('disabled', colours.accent_disabled)],
              foreground=[('disabled', '#E2E8F0')])
    style.configure('Browse.TButton',
                    foreground=colours.accent, font=(FONT_FAMILY, 9), relief='flat',
                    borderwidth=1, bordercolor=colours.border, padding=(6, 3))
    style.map('Browse.TButton', background=[('active', colours.accent_hover)])
    return colours

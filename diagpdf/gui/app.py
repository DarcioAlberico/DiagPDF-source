"""The DiagPDF window."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from .. import __version__
from .. import profiles as profiles_mod
from ..fonts import FIGURINE_NAMES, FONT_NAMES
from ..i18n import LANGS, _layout_label, _next_lang, tr
from ..layouts import LAYOUTS
from ..page import PAGE_SIZE_KEYS
from ..parsers import apply_fen_policy, parse_epd, parse_fen_file, parse_pgn, read_chess_file
from ..resources import _resource
from .filetypes import (
    default_output_path,
    extension_for_label,
    normalize_output_path,
    open_filetypes,
    save_filetypes,
)
from .preview import PreviewUnavailable, render_preview_png
from .settings import (
    Settings,
    load_settings,
    save_settings,
    settings_from_opts,
    settings_to_opts,
)
from .theme import apply_theme
from .worker import Failed, Finished, GenerationJob, Progress, Stopped

POLL_MS = 60


def open_in_default_app(path: Path) -> None:
    """Open *path* with the desktop's default handler.

    Not through a shell: a path containing & or ^ used to be interpreted as a
    command by ``start``.
    """
    if sys.platform == 'win32':
        os.startfile(str(path))          # type: ignore[attr-defined]
    else:
        import subprocess
        opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
        subprocess.Popen([opener, str(path)])


def parse_positions(path: Path) -> list[dict]:
    """Read and parse an input file, or return an empty list for unknown types."""
    content = read_chess_file(path)
    suffix = path.suffix.lower()
    if suffix == '.pgn':
        return parse_pgn(content)
    if suffix == '.fen':
        return parse_fen_file(content)
    if suffix == '.epd':
        return parse_epd(content)
    return []


def run_gui() -> None:
    try:
        import tkinter as tk
        import webbrowser
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError:
        print('tkinter not available. Use command-line mode.', file=sys.stderr)
        sys.exit(1)

    settings = load_settings()
    lang = settings.lang

    root = tk.Tk()
    root.resizable(True, True)
    colours = apply_theme(root, ttk, settings.theme)

    # ── State ────────────────────────────────────────────────────────────────
    v_input = tk.StringVar(value='')
    v_output = tk.StringVar(value='')
    v_layout = tk.IntVar(value=settings.layout)
    v_font = tk.StringVar(value=settings.font)
    v_coords = tk.BooleanVar(value=settings.coords)
    v_orient = tk.StringVar(value=settings.orient)
    v_header = tk.StringVar(value=settings.header)
    v_footer = tk.StringVar(value=settings.footer)
    v_sh_hdr = tk.BooleanVar(value=settings.show_header)
    v_sh_ftr = tk.BooleanVar(value=settings.show_footer)
    v_symbol = tk.StringVar(value=settings.symbol)
    v_border = tk.StringVar(value=settings.border_style)
    v_lines_count = tk.IntVar(value=settings.lines_count)
    v_lines_mode = tk.StringVar(value=settings.lines_mode)
    v_font_size = tk.IntVar(value=settings.font_size)
    v_title_template = tk.StringVar(value=settings.title_template)
    v_lichess = tk.BooleanVar(value=settings.lichess)
    v_answers = tk.BooleanVar(value=settings.answers_section)
    v_answers_title = tk.StringVar(value=settings.answers_title)
    v_answers_cols = tk.IntVar(value=settings.answers_cols)
    v_answers_flip = tk.BooleanVar(value=settings.answers_upside_down)
    v_answers_page = tk.BooleanVar(value=settings.answers_new_page)
    v_answers_chapter = tk.BooleanVar(value=settings.answers_after_chapter)
    v_fig_font = tk.StringVar(value=settings.figurine_font)
    v_epub_css = tk.StringVar(value=settings.epub_css_path)
    v_dark = tk.BooleanVar(value=settings.theme == 'dark')
    v_page_size = tk.StringVar(value=settings.page_size)
    v_landscape = tk.BooleanVar(value=settings.landscape)
    v_cover = tk.BooleanVar(value=settings.cover)
    v_watermark = tk.StringVar(value=settings.watermark)
    v_contents = tk.BooleanVar(value=settings.contents)
    v_author = tk.StringVar(value=settings.doc_author)
    # Strings, not IntVar: typing a letter into an IntVar-backed spinbox raises
    # a raw TclError out of .get().
    v_pos_from = tk.StringVar(value='0')
    v_pos_to = tk.StringVar(value='0')
    v_renumber = tk.BooleanVar(value=True)
    v_status = tk.StringVar(value='')
    v_save_ext = tk.StringVar(value='.pdf')
    v_save_label = tk.StringVar(value='')
    v_profile = tk.StringVar(value='')

    widgets: dict[str, Any] = {}
    state = {'last_output': Path(), 'generated': False, 'total': 0, 'job': None, 'preview': None}

    def t(key: str) -> Any:
        return tr(key, lang)

    def err_title() -> str:
        return t('error').format('').strip().rstrip(':') or 'Error'

    def set_status(message: str, ok: bool = True) -> None:
        v_status.set(message)
        status_lbl.config(foreground=colours.ok if ok else colours.error)

    # ── Preview ──────────────────────────────────────────────────────────────

    def current_opts(number_offset: int = 0, doc_title: str = '') -> dict:
        return settings_to_opts(collect_settings(), number_offset=number_offset, doc_title=doc_title)

    def refresh_preview(*_) -> None:
        try:
            png = render_preview_png(current_opts(), state.get('sample'))
        except PreviewUnavailable as exc:
            preview_lbl.config(image='', text=f"{t('preview_error')}\n{exc}", compound='center')
            state['preview'] = None
            return
        except Exception as exc:                     # noqa: BLE001 - preview must never crash the app
            preview_lbl.config(image='', text=f"{t('preview_error')}\n{exc}", compound='center')
            state['preview'] = None
            return
        photo = tk.PhotoImage(data=png)
        state['preview'] = photo                     # keep a reference or Tk drops it
        preview_lbl.config(image=photo, text='')

    def schedule_preview(*_) -> None:
        if state.get('preview_job'):
            root.after_cancel(state['preview_job'])
        state['preview_job'] = root.after(150, refresh_preview)

    # ── Settings <-> widgets ─────────────────────────────────────────────────

    def collect_settings() -> Settings:
        return Settings(
            lang=lang,
            theme='dark' if v_dark.get() else 'light',
            layout=v_layout.get(),
            font=v_font.get(),
            font_size=v_font_size.get(),
            coords=v_coords.get(),
            orient=v_orient.get(),
            header=v_header.get(),
            footer=v_footer.get(),
            show_header=v_sh_hdr.get(),
            show_footer=v_sh_ftr.get(),
            symbol=v_symbol.get(),
            border_style=v_border.get(),
            lines_count=v_lines_count.get(),
            lines_mode=v_lines_mode.get(),
            title_template=v_title_template.get(),
            lichess=v_lichess.get(),
            answers_section=v_answers.get(),
            answers_title=v_answers_title.get(),
            answers_cols=v_answers_cols.get(),
            answers_upside_down=v_answers_flip.get(),
            answers_new_page=v_answers_page.get(),
            answers_after_chapter=v_answers_chapter.get(),
            figurine_font=v_fig_font.get(),
            epub_css_path=v_epub_css.get(),
            page_size=v_page_size.get(),
            landscape=v_landscape.get(),
            watermark=v_watermark.get(),
            cover=v_cover.get(),
            contents=v_contents.get(),
            doc_author=v_author.get(),
            recent_files=settings.recent_files,
        )

    def apply_settings(new: Settings) -> None:
        """Push a Settings back into the widgets - the mirror of collect_settings."""
        v_layout.set(new.layout)
        v_font.set(new.font)
        v_font_size.set(new.font_size)
        v_coords.set(new.coords)
        v_orient.set(new.orient)
        v_header.set(new.header)
        v_footer.set(new.footer)
        v_sh_hdr.set(new.show_header)
        v_sh_ftr.set(new.show_footer)
        v_symbol.set(new.symbol)
        v_border.set(new.border_style)
        v_lines_count.set(new.lines_count)
        v_lines_mode.set(new.lines_mode)
        v_title_template.set(new.title_template)
        v_lichess.set(new.lichess)
        v_answers.set(new.answers_section)
        v_answers_title.set(new.answers_title)
        v_answers_cols.set(new.answers_cols)
        v_answers_flip.set(new.answers_upside_down)
        v_answers_page.set(new.answers_new_page)
        v_answers_chapter.set(new.answers_after_chapter)
        v_fig_font.set(new.figurine_font)
        v_epub_css.set(new.epub_css_path)
        v_page_size.set(new.page_size)
        v_landscape.set(new.landscape)
        v_cover.set(new.cover)
        v_watermark.set(new.watermark)
        v_contents.set(new.contents)
        v_author.set(new.doc_author)
        layout_cb.current(new.layout)

    # ── Profiles ─────────────────────────────────────────────────────────────

    def refresh_profiles(select: str = '') -> None:
        names = sorted(profiles_mod.load_all())
        profile_cb['values'] = names
        if select and select in names:
            v_profile.set(select)
        elif v_profile.get() not in names:
            v_profile.set('')
        for key in ('profile_load', 'profile_delete'):
            widgets[key].config(state='normal' if names else 'disabled')

    def load_profile() -> None:
        name = v_profile.get().strip()
        if not name:
            set_status(t('profile_none'), ok=False)
            return
        try:
            values = profiles_mod.load(name)
        except profiles_mod.ProfileError as exc:
            set_status(str(exc), ok=False)
            refresh_profiles()
            return
        apply_settings(settings_from_opts(values, collect_settings()))
        schedule_preview()
        set_status(t('profile_loaded').format(name))

    def save_profile() -> None:
        suggested = v_profile.get().strip()
        name = simpledialog.askstring(t('profile_save'), t('profile_name'),
                                      initialvalue=suggested, parent=root)
        if name is None:
            return
        try:
            saved = profiles_mod.save(
                name, settings_to_opts(collect_settings()).changed_from_defaults())
        except profiles_mod.ProfileError as exc:
            messagebox.showerror(err_title(), str(exc), parent=root)
            return
        refresh_profiles(saved)
        set_status(t('profile_saved').format(saved))

    def delete_profile() -> None:
        name = v_profile.get().strip()
        if not name:
            set_status(t('profile_none'), ok=False)
            return
        if not messagebox.askyesno(t('profile_delete'), f'{name}?', parent=root):
            return
        try:
            profiles_mod.delete(name)
        except profiles_mod.ProfileError as exc:
            set_status(str(exc), ok=False)
        else:
            set_status(t('profile_deleted').format(name))
        refresh_profiles()

    def on_setting_change(*_) -> None:
        if state['generated']:
            state['generated'] = False
            set_status(t('ready'))
        schedule_preview()

    # ── File selection ───────────────────────────────────────────────────────

    def load_input(path: Path) -> None:
        v_input.set(str(path))
        v_output.set(str(default_output_path(path, v_save_ext.get())))
        try:
            content = read_chess_file(path)
        except Exception as exc:
            messagebox.showerror(err_title(), str(exc))
            return
        has_chapter = bool(re.search(r'^\[Chapter\s+"[^"]+"\]', content, re.MULTILINE))
        v_header.set('{chapter}' if has_chapter else path.stem)
        try:
            positions = parse_positions(path)
        except Exception:
            positions = []
        state['total'] = len(positions)
        state['sample'] = positions[0] if positions else None
        if positions:
            v_pos_from.set('1')
            v_pos_to.set(str(len(positions)))
            for spin in (spb_from, spb_to):
                spin.config(**{'from': 1, 'to': len(positions)})   # type: ignore[call-overload]
        settings.remember_file(path)
        refresh_recent_menu()
        schedule_preview()

    def browse_input() -> None:
        chosen = filedialog.askopenfilename(title=t('open_title'), filetypes=open_filetypes(lang))
        if chosen:
            load_input(Path(chosen))

    def browse_output() -> None:
        chosen = filedialog.asksaveasfilename(
            title=t('save_title'), filetypes=save_filetypes(lang), typevariable=v_save_label,
        )
        if chosen:
            extension = extension_for_label(v_save_label.get(), lang)
            v_save_ext.set(extension)
            v_output.set(str(normalize_output_path(chosen, extension)))

    def browse_epub_css() -> None:
        chosen = filedialog.askopenfilename(
            title=t('css_open_title'),
            filetypes=[('CSS', '*.css'), (t('filetype_all'), '*.*')],
        )
        if chosen:
            v_epub_css.set(chosen)

    def refresh_recent_menu() -> None:
        menu = widgets.get('recent_menu')
        if menu is None:
            return
        menu.delete(0, 'end')
        entries = settings.existing_recent_files()
        widgets['recent_btn'].config(state='normal' if entries else 'disabled')
        for item in entries:
            menu.add_command(label=Path(item).name,
                             command=lambda p=item: load_input(Path(p)))

    # ── Generation ───────────────────────────────────────────────────────────

    def read_range() -> tuple[int, int] | None:
        try:
            return int(v_pos_from.get() or 0), int(v_pos_to.get() or 0)
        except ValueError:
            messagebox.showerror(err_title(), t('err_range_value'))
            return None

    def set_busy(busy: bool) -> None:
        widgets['convert'].config(state='disabled' if busy else 'normal')
        widgets['cancel'].config(state='normal' if busy else 'disabled')
        progress.config(value=0)
        progress.grid() if busy else progress.grid_remove()

    def convert() -> None:
        in_path = Path(v_input.get().strip())
        if not in_path.exists():
            messagebox.showerror(err_title(), t('err_not_found').format(in_path))
            return
        out_text = v_output.get().strip()
        out_path = (normalize_output_path(out_text, v_save_ext.get()) if out_text
                    else default_output_path(in_path, v_save_ext.get()))

        bounds = read_range()
        if bounds is None:
            return
        pos_from, pos_to = bounds

        try:
            positions = parse_positions(in_path)
        except Exception as exc:
            messagebox.showerror(err_title(), str(exc))
            return
        if not positions:
            messagebox.showerror(err_title(), t('err_no_pos'))
            return
        positions = apply_fen_policy(positions, 'skip')
        if not positions:
            messagebox.showerror(err_title(), t('err_no_pos'))
            return

        number_offset = 0
        if pos_from > 0 or pos_to > 0:
            start = max(0, pos_from - 1) if pos_from > 0 else 0
            end = pos_to if pos_to > 0 else None
            positions = positions[start:end]
            if not positions:
                messagebox.showerror(err_title(), t('err_range'))
                return
            if not v_renumber.get():
                number_offset = start

        opts = current_opts(number_offset=number_offset, doc_title=in_path.stem)
        job = GenerationJob(positions, opts, out_path)
        state['job'] = job
        set_busy(True)
        set_status(t('working'))
        job.start()
        root.after(POLL_MS, lambda: pump(job, len(positions)))

    def pump(job: GenerationJob, count: int) -> None:
        """Drain the worker's events on the main thread."""
        finished = False
        for event in job.poll():
            if isinstance(event, Progress):
                progress.config(value=event.percent)
                set_status(f'{event.percent}%')
            elif isinstance(event, Finished):
                state['last_output'] = event.out_path
                state['generated'] = True
                widgets['open_pdf'].config(state='normal')
                set_status(t('done').format(count, event.out_path.name))
                finished = True
            elif isinstance(event, Stopped):
                set_status(t('cancelled'), ok=False)
                finished = True
            elif isinstance(event, Failed):
                messagebox.showerror(err_title(), str(event.error))
                set_status(t('error').format(event.error), ok=False)
                finished = True
        if finished:
            set_busy(False)
            state['job'] = None
            return
        root.after(POLL_MS, lambda: pump(job, count))

    def cancel() -> None:
        job = state.get('job')
        if job is not None:
            job.cancel()
            set_status(t('cancelled'), ok=False)

    def open_output() -> None:
        path = state['last_output']
        if not path.exists():
            return
        try:
            open_in_default_app(path)
        except Exception as exc:
            messagebox.showerror(err_title(), str(exc))

    # ── Language and theme ───────────────────────────────────────────────────

    def apply_lang() -> None:
        for key, widget in widgets.items():
            if key in ('recent_menu',):
                continue
            try:
                widget.config(text=t(key))
            except Exception:
                pass
        layout_cb['values'] = [_layout_label(i, lang) for i in range(len(LAYOUTS))]
        layout_cb.current(v_layout.get())
        credits_prefix.config(text=t('credits_by'))
        credits_middle.config(text=t('credits_mod'))
        set_status(t('ready'))

    def toggle_lang() -> None:
        nonlocal lang
        lang = _next_lang(lang)
        apply_lang()

    def toggle_theme() -> None:
        nonlocal colours
        colours = apply_theme(root, ttk, 'dark' if v_dark.get() else 'light')
        set_status(t('ready'))

    # ══ Layout ═══════════════════════════════════════════════════════════════
    root.title(f'DiagPDF {__version__}')
    icon = _resource('icon.ico')
    if icon.exists():
        try:
            root.iconbitmap(str(icon))
        except Exception:
            pass
    root.configure(padx=16, pady=12)

    bottom = ttk.Frame(root)
    bottom.pack(side='bottom', fill='x')
    status_lbl = ttk.Label(bottom, textvariable=v_status, font=('Segoe UI', 8))
    status_lbl.pack(side='bottom', pady=(6, 0))

    credits = ttk.Frame(bottom)
    credits.pack(side='bottom', pady=(2, 0))
    credits_prefix = ttk.Label(credits, text=t('credits_by'))
    credits_prefix.pack(side='left')
    lbl_author = ttk.Label(credits, text='Ildar Aslyamov', foreground=colours.accent, cursor='hand2')
    lbl_author.pack(side='left')
    credits_middle = ttk.Label(credits, text=t('credits_mod'))
    credits_middle.pack(side='left')
    lbl_maintainer = ttk.Label(credits, text='Darcio Alberico', foreground=colours.accent, cursor='hand2')
    lbl_maintainer.pack(side='left')
    lbl_author.bind('<Button-1>', lambda _: webbrowser.open_new_tab('https://github.com/aslyamov/DiagPDF'))
    lbl_maintainer.bind('<Button-1>', lambda _: webbrowser.open_new_tab('https://github.com/DarcioAlberico'))

    buttons = ttk.Frame(bottom)
    buttons.pack(side='bottom')
    widgets['convert'] = ttk.Button(buttons, command=convert, style='Accent.TButton', state='disabled')
    widgets['convert'].pack(side='left', ipadx=8, ipady=2)
    widgets['cancel'] = ttk.Button(buttons, command=cancel, state='disabled')
    widgets['cancel'].pack(side='left', padx=(8, 0), ipadx=8, ipady=2)
    widgets['open_pdf'] = ttk.Button(buttons, command=open_output, state='disabled')
    widgets['open_pdf'].pack(side='left', padx=(8, 0), ipadx=8, ipady=2)

    progress = ttk.Progressbar(bottom, mode='determinate', maximum=100)
    progress.pack(side='bottom', fill='x', pady=(6, 4))
    progress.pack_forget()
    progress.grid = progress.pack           # keep set_busy simple across geometry managers
    progress.grid_remove = progress.pack_forget

    ttk.Separator(bottom, orient='horizontal').pack(side='bottom', fill='x', pady=(6, 8))

    body = ttk.Frame(root)
    body.pack(fill='both', expand=True)
    main = ttk.Frame(body)
    main.pack(side='left', fill='both', expand=True)

    side = ttk.Frame(body)
    side.pack(side='right', fill='y', padx=(14, 0))
    widgets['preview'] = ttk.Label(side, style='SectionHdr.TLabel')
    widgets['preview'].pack(anchor='w')
    preview_lbl = ttk.Label(side, anchor='center', justify='center')
    preview_lbl.pack(pady=(4, 8))

    top = ttk.Frame(main)
    top.pack(fill='x', pady=(0, 8))
    ttk.Label(top, text='DiagPDF', font=('Segoe UI', 13, 'bold'),
              foreground=colours.accent).pack(side='left')
    widgets['lang_btn'] = ttk.Button(top, command=toggle_lang, width=4)
    widgets['lang_btn'].pack(side='right')
    widgets['theme'] = ttk.Checkbutton(top, variable=v_dark, command=toggle_theme)
    widgets['theme'].pack(side='right', padx=(0, 10))

    # ── Profiles ─────────────────────────────────────────────────────────────
    prof = ttk.Frame(main)
    prof.pack(fill='x', pady=(0, 8))
    widgets['profile_lbl'] = ttk.Label(prof, anchor='w')
    widgets['profile_lbl'].pack(side='left', padx=(0, 6))
    profile_cb = ttk.Combobox(prof, textvariable=v_profile, state='readonly', width=22)
    profile_cb.pack(side='left')
    widgets['profile_load'] = ttk.Button(prof, command=load_profile)
    widgets['profile_load'].pack(side='left', padx=(6, 0))
    widgets['profile_save'] = ttk.Button(prof, command=save_profile)
    widgets['profile_save'].pack(side='left', padx=(6, 0))
    widgets['profile_delete'] = ttk.Button(prof, command=delete_profile)
    widgets['profile_delete'].pack(side='left', padx=(6, 0))

    def section(key: str) -> None:
        label = ttk.Label(main, style='SectionHdr.TLabel')
        label.pack(fill='x', pady=(4, 2))
        widgets[key] = label
        ttk.Separator(main, orient='horizontal').pack(fill='x', pady=(0, 6))

    # ── Files ────────────────────────────────────────────────────────────────
    section('section_files')
    files = ttk.Frame(main)
    files.pack(fill='x', pady=(0, 4))
    files.columnconfigure(1, weight=1)
    files.columnconfigure(0, minsize=105)

    widgets['input_file'] = ttk.Label(files, anchor='w')
    widgets['input_file'].grid(row=0, column=0, sticky='w', padx=(0, 8), pady=(0, 4))
    entry_input = ttk.Entry(files, textvariable=v_input)
    entry_input.grid(row=0, column=1, sticky='ew', padx=(0, 6), pady=(0, 4))
    ttk.Button(files, text='…', command=browse_input, style='Browse.TButton',
               width=3).grid(row=0, column=2, pady=(0, 4))
    widgets['recent_btn'] = ttk.Menubutton(files, state='disabled')
    widgets['recent_btn'].grid(row=0, column=3, padx=(4, 0), pady=(0, 4))
    widgets['recent_menu'] = tk.Menu(widgets['recent_btn'], tearoff=0)
    widgets['recent_btn'].config(menu=widgets['recent_menu'])
    widgets['recent_files'] = widgets['recent_btn']

    widgets['output_pdf'] = ttk.Label(files, anchor='w')
    widgets['output_pdf'].grid(row=1, column=0, sticky='w', padx=(0, 8))
    ttk.Entry(files, textvariable=v_output).grid(row=1, column=1, sticky='ew', padx=(0, 6))
    ttk.Button(files, text='…', command=browse_output, style='Browse.TButton',
               width=3).grid(row=1, column=2)

    widgets['pos_from_lbl'] = ttk.Label(files, anchor='w')
    widgets['pos_from_lbl'].grid(row=2, column=0, sticky='w', padx=(0, 8), pady=(4, 0))
    range_frame = ttk.Frame(files)
    range_frame.grid(row=2, column=1, sticky='w', pady=(4, 0))
    spb_from = ttk.Spinbox(range_frame, textvariable=v_pos_from, from_=0, to=9999, width=6)
    spb_from.pack(side='left', padx=(0, 6))
    widgets['pos_to_lbl'] = ttk.Label(range_frame, anchor='w')
    widgets['pos_to_lbl'].pack(side='left', padx=(0, 6))
    spb_to = ttk.Spinbox(range_frame, textvariable=v_pos_to, from_=0, to=9999, width=6)
    spb_to.pack(side='left', padx=(0, 10))
    widgets['renumber_lbl'] = ttk.Checkbutton(range_frame, variable=v_renumber)
    widgets['renumber_lbl'].pack(side='left', padx=(0, 4))

    # ── Page ─────────────────────────────────────────────────────────────────
    section('section_page')
    page = ttk.Frame(main)
    page.pack(fill='x', pady=(0, 4))
    page.columnconfigure(1, weight=1)
    page.columnconfigure(4, weight=1)

    widgets['header_text'] = ttk.Label(page, anchor='w')
    widgets['header_text'].grid(row=0, column=0, sticky='w', padx=(0, 6), pady=(0, 4))
    ttk.Entry(page, textvariable=v_header).grid(row=0, column=1, sticky='ew', padx=(0, 4), pady=(0, 4))
    widgets['show_header'] = ttk.Checkbutton(page, variable=v_sh_hdr)
    widgets['show_header'].grid(row=0, column=2, padx=(0, 16), pady=(0, 4))
    widgets['layout'] = ttk.Label(page, anchor='w')
    widgets['layout'].grid(row=0, column=3, sticky='w', padx=(0, 6), pady=(0, 4))
    layout_cb = ttk.Combobox(page, width=20, state='readonly',
                             values=[_layout_label(i, lang) for i in range(len(LAYOUTS))])
    layout_cb.current(v_layout.get())
    layout_cb.grid(row=0, column=4, sticky='ew', pady=(0, 4))
    layout_cb.bind('<<ComboboxSelected>>', lambda _: v_layout.set(layout_cb.current()))

    widgets['footer_text'] = ttk.Label(page, anchor='w')
    widgets['footer_text'].grid(row=1, column=0, sticky='w', padx=(0, 6))
    ttk.Entry(page, textvariable=v_footer).grid(row=1, column=1, sticky='ew', padx=(0, 4))
    widgets['show_footer'] = ttk.Checkbutton(page, variable=v_sh_ftr)
    widgets['show_footer'].grid(row=1, column=2, padx=(0, 16))
    widgets['font'] = ttk.Label(page, anchor='w')
    widgets['font'].grid(row=1, column=3, sticky='w', padx=(0, 6))
    ttk.Combobox(page, textvariable=v_font, width=20, state='readonly',
                 values=FONT_NAMES).grid(row=1, column=4, sticky='ew')

    widgets['font_size_lbl'] = ttk.Label(page, anchor='w')
    widgets['font_size_lbl'].grid(row=2, column=3, sticky='w', padx=(0, 6), pady=(4, 0))
    ttk.Spinbox(page, textvariable=v_font_size, from_=0, to=60,
                width=5).grid(row=2, column=4, sticky='w', pady=(4, 0))

    widgets['page_size_lbl'] = ttk.Label(page, anchor='w')
    widgets['page_size_lbl'].grid(row=2, column=0, sticky='w', padx=(0, 6), pady=(4, 0))
    sheet = ttk.Frame(page)
    sheet.grid(row=2, column=1, columnspan=2, sticky='w', pady=(4, 0))
    ttk.Combobox(sheet, textvariable=v_page_size, values=list(PAGE_SIZE_KEYS),
                 state='readonly', width=7).pack(side='left', padx=(0, 8))
    widgets['landscape'] = ttk.Checkbutton(sheet, variable=v_landscape)
    widgets['landscape'].pack(side='left')

    front = ttk.Frame(page)
    front.grid(row=3, column=0, columnspan=5, sticky='w', pady=(4, 0))
    widgets['cover'] = ttk.Checkbutton(front, variable=v_cover)
    widgets['cover'].pack(side='left', padx=(0, 12))
    widgets['contents_lbl'] = ttk.Checkbutton(front, variable=v_contents)
    widgets['contents_lbl'].pack(side='left', padx=(0, 12))
    widgets['author_lbl'] = ttk.Label(front)
    widgets['author_lbl'].pack(side='left', padx=(0, 6))
    ttk.Entry(front, textvariable=v_author, width=22).pack(side='left')

    widgets['watermark_lbl'] = ttk.Label(front)
    widgets['watermark_lbl'].pack(side='left', padx=(12, 6))
    ttk.Entry(front, textvariable=v_watermark, width=16).pack(side='left')

    # ── Diagram ──────────────────────────────────────────────────────────────
    section('section_diagram')
    diagram = ttk.Frame(main)
    diagram.pack(fill='x')
    diagram.columnconfigure(0, minsize=140)
    diagram.columnconfigure(1, weight=1)

    def radio_row(row: int, label_key: str, variable, options: list[tuple[str, str]]) -> None:
        widgets[label_key] = ttk.Label(diagram, anchor='w')
        widgets[label_key].grid(row=row, column=0, sticky='w', padx=(0, 8), pady=(0, 4))
        frame = ttk.Frame(diagram)
        frame.grid(row=row, column=1, sticky='w', pady=(0, 4))
        for value, key in options:
            button = ttk.Radiobutton(frame, variable=variable, value=value)
            button.pack(side='left', padx=(0, 6))
            widgets[key] = button

    radio_row(0, 'symbol', v_symbol,
              [('square', 'sym_square'), ('circle', 'sym_circle'), ('triangle', 'sym_triangle')])
    radio_row(1, 'border_style', v_border,
              [('simple', 'border_simple'), ('double', 'border_double'), ('none', 'border_none')])

    widgets['lines_count'] = ttk.Label(diagram, anchor='w')
    widgets['lines_count'].grid(row=2, column=0, sticky='w', padx=(0, 8), pady=(0, 2))
    lines_frame = ttk.Frame(diagram)
    lines_frame.grid(row=2, column=1, sticky='w', pady=(0, 2))
    for count in range(6):
        ttk.Radiobutton(lines_frame, text=str(count), variable=v_lines_count,
                        value=count).pack(side='left', padx=(0, 4))
    mode_frame = ttk.Frame(diagram)
    mode_frame.grid(row=3, column=1, sticky='w', pady=(0, 4))
    widgets['lines_plain'] = ttk.Radiobutton(mode_frame, variable=v_lines_mode, value='plain')
    widgets['lines_plain'].pack(side='left', padx=(0, 4))
    widgets['lines_numbered'] = ttk.Radiobutton(mode_frame, variable=v_lines_mode, value='numbered')
    widgets['lines_numbered'].pack(side='left', padx=(0, 4))

    widgets['orient'] = ttk.Label(diagram, anchor='w')
    widgets['orient'].grid(row=4, column=0, sticky='w', padx=(0, 8), pady=(0, 4))
    orient_frame = ttk.Frame(diagram)
    orient_frame.grid(row=4, column=1, sticky='w', pady=(0, 4))
    for value, key in (('auto', 'orient_auto'), ('white', 'orient_white'), ('black', 'orient_black')):
        button = ttk.Radiobutton(orient_frame, variable=v_orient, value=value)
        button.pack(side='left', padx=(0, 4))
        widgets[key] = button
    ttk.Frame(orient_frame, width=10).pack(side='left')
    widgets['coords'] = ttk.Checkbutton(orient_frame, variable=v_coords)
    widgets['coords'].pack(side='left')

    widgets['title_source'] = ttk.Label(diagram, anchor='w')
    widgets['title_source'].grid(row=5, column=0, sticky='w', padx=(0, 8), pady=(0, 4))
    template_frame = ttk.Frame(diagram)
    template_frame.grid(row=5, column=1, sticky='ew', pady=(0, 4))
    template_frame.columnconfigure(0, weight=1)
    ttk.Entry(template_frame, textvariable=v_title_template).grid(row=0, column=0, sticky='ew')
    ttk.Button(template_frame, text='?', width=2,
               command=lambda: messagebox.showinfo(t('tpl_help_title'), t('tpl_help_body'))
               ).grid(row=0, column=1, padx=(4, 0))

    widgets['lichess_link'] = ttk.Checkbutton(diagram, variable=v_lichess)
    widgets['lichess_link'].grid(row=6, column=0, columnspan=2, sticky='w', pady=(0, 4))
    widgets['answers_section'] = ttk.Checkbutton(diagram, variable=v_answers)
    widgets['answers_section'].grid(row=7, column=0, columnspan=2, sticky='w', pady=(0, 2))

    widgets['answers_title_lbl'] = ttk.Label(diagram)
    widgets['answers_title_lbl'].grid(row=8, column=0, sticky='w', pady=(0, 2))
    ttk.Entry(diagram, textvariable=v_answers_title).grid(row=8, column=1, sticky='ew', pady=(0, 2))

    widgets['answers_cols_lbl'] = ttk.Label(diagram)
    widgets['answers_cols_lbl'].grid(row=9, column=0, sticky='w', pady=(0, 2))
    answers_row = ttk.Frame(diagram)
    answers_row.grid(row=9, column=1, sticky='w', pady=(0, 2))
    ttk.Combobox(answers_row, textvariable=v_answers_cols, values=['1', '2'], state='readonly',
                 width=4).pack(side='left')
    widgets['answers_new_page'] = ttk.Checkbutton(answers_row, variable=v_answers_page)
    widgets['answers_new_page'].pack(side='left', padx=(12, 0))
    widgets['answers_upside_down'] = ttk.Checkbutton(answers_row, variable=v_answers_flip)
    widgets['answers_upside_down'].pack(side='left', padx=(12, 0))
    widgets['answers_after_chapter'] = ttk.Checkbutton(answers_row, variable=v_answers_chapter)
    widgets['answers_after_chapter'].pack(side='left', padx=(12, 0))

    widgets['figurine_font_lbl'] = ttk.Label(diagram)
    widgets['figurine_font_lbl'].grid(row=10, column=0, sticky='w', pady=(0, 2))
    ttk.Combobox(diagram, textvariable=v_fig_font, values=FIGURINE_NAMES, state='readonly',
                 width=14).grid(row=10, column=1, sticky='w', pady=(0, 2))

    # A remembered field instead of a yes/no dialog on every EPUB export.
    widgets['epub_css_lbl'] = ttk.Label(diagram)
    widgets['epub_css_lbl'].grid(row=11, column=0, sticky='w', pady=(0, 2))
    css_frame = ttk.Frame(diagram)
    css_frame.grid(row=11, column=1, sticky='ew', pady=(0, 2))
    css_frame.columnconfigure(0, weight=1)
    ttk.Entry(css_frame, textvariable=v_epub_css).grid(row=0, column=0, sticky='ew')
    ttk.Button(css_frame, text='…', width=3, style='Browse.TButton',
               command=browse_epub_css).grid(row=0, column=1, padx=(4, 0))
    widgets['epub_css_clear'] = ttk.Button(css_frame, width=7, command=lambda: v_epub_css.set(''))
    widgets['epub_css_clear'].grid(row=0, column=2, padx=(4, 0))

    # ── Wiring ───────────────────────────────────────────────────────────────
    def update_convert_state(*_) -> None:
        widgets['convert'].config(state='normal' if v_input.get().strip() else 'disabled')

    v_input.trace_add('write', update_convert_state)
    for variable in (v_layout, v_font, v_font_size, v_coords, v_orient, v_header, v_footer,
                     v_sh_hdr, v_sh_ftr, v_symbol, v_border, v_lines_count, v_lines_mode,
                     v_title_template, v_lichess, v_answers, v_answers_title, v_answers_cols,
                     v_answers_flip, v_answers_page, v_answers_chapter, v_watermark,
                     v_fig_font, v_epub_css, v_page_size, v_landscape, v_cover,
                     v_contents, v_author):
        variable.trace_add('write', on_setting_change)

    _enable_drop(root, entry_input, load_input)

    def on_close() -> None:
        job = state.get('job')
        if job is not None:
            job.cancel()
        save_settings(collect_settings())
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', on_close)

    apply_lang()
    refresh_recent_menu()
    refresh_profiles()
    refresh_preview()
    root.update_idletasks()
    width, height = root.winfo_reqwidth(), root.winfo_reqheight()
    for _ in range(len(LANGS) - 1):
        toggle_lang()
        root.update_idletasks()
        width = max(width, root.winfo_reqwidth())
        height = max(height, root.winfo_reqheight())
    toggle_lang()   # back to where we started
    root.geometry(f'{width}x{min(height, root.winfo_screenheight() - 90)}')
    root.mainloop()


def _enable_drop(root, widget, on_file) -> None:
    """Accept dropped files when tkinterdnd2 is installed; stay quiet otherwise."""
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore[import]
    except ImportError:
        return
    try:
        root.TkdndVersion = TkinterDnD._require(root)
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind('<<Drop>>', lambda event: on_file(Path(event.data.strip('{}'))))
    except Exception:
        return

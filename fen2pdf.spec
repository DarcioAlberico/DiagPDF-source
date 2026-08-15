# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for DiagPDF
# Build: pyinstaller fen2pdf.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Include sv_ttk theme files if installed
try:
    sv_ttk_datas = collect_data_files('sv_ttk')
except Exception:
    sv_ttk_datas = []

a = Analysis(
    ['fen2rtf.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        *[(str(p), 'Fonts') for p in Path('Fonts').glob('*') if p.is_file()],
        ('icon.ico',                    '.'),
    ] + sv_ttk_datas,
    # The renderers are reached through the GENERATORS table, so PyInstaller's
    # static analysis cannot see them from the entry point alone.
    hiddenimports=[
        'fontTools', 'fontTools.ttLib', 'fontTools.subset',
        'diagpdf', 'diagpdf.cli', 'diagpdf.gui', 'diagpdf.gui.app',
        'diagpdf.images', 'diagpdf.moves', 'chess',
        'diagpdf.render.pdf', 'diagpdf.render.html', 'diagpdf.render.epub',
        'diagpdf.render.docx', 'diagpdf.render.rtf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DiagPDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

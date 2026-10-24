# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
import playwright

# Path ke playwright driver (berisi browser binaries)
pw_dir = Path(playwright.__file__).parent
pw_driver_dir = pw_dir / 'driver'

# Collect semua file playwright (driver + package)
playwright_datas = []
for root, dirs, files in os.walk(str(pw_dir)):
    for f in files:
        src = os.path.join(root, f)
        rel = os.path.relpath(os.path.dirname(src), str(pw_dir.parent))
        playwright_datas.append((src, rel))

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[],
    datas=playwright_datas,
    hiddenimports=[
        'playwright',
        'playwright.async_api',
        'playwright.sync_api',
        'playwright._impl._api_types',
        'playwright._impl._browser_type',
        'playwright._impl._connection',
        'asyncio',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PIL',
        'PIL.Image',
        'rich',
        'rich.console',
        'rich.progress',
        'rich.panel',
        'rich.table',
        'rich.text',
        'threading',
        'shutil',
        'uuid',
        'io',
        'msvcrt',
        'time',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GoogleTranslateAutomator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # Tidak tampilkan CMD window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GoogleTranslateAutomator',
)

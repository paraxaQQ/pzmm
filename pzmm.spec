# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
ROOT = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'docs', 'HOW_TO_READ_ERRORS.md'), 'docs'),
        (os.path.join(ROOT, 'icon.ico'), '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        # AI providers — dynamically imported in core/ai.py
        'anthropic',
        'openai',
        # pzmm modules touched only via lazy imports (e.g. ui.backups_dialog
        # is imported inside AITab._open_history)
        'core.backups',
        'ui.backups_dialog',
        'ui.confirm_write_dialog',
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
    name='pzmm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'icon.ico'),
)

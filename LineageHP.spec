# -*- mode: python ; coding: utf-8 -*-

PYTHON_PREFIX = r'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64'

a = Analysis(
    ['lineage_death_command.py'],
    pathex=[],
    binaries=[
        (PYTHON_PREFIX + r'\python314.dll',    '.'),
        (PYTHON_PREFIX + r'\python3.dll',      '.'),
        (PYTHON_PREFIX + r'\vcruntime140.dll', '.'),
        (PYTHON_PREFIX + r'\vcruntime140_1.dll', '.'),
    ],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LineageHP',
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
)

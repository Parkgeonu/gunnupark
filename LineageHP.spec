# -*- mode: python ; coding: utf-8 -*-

PYTHON_PREFIX = r'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64'
DOWNLEVEL     = r'C:\Windows\System32\downlevel'

a = Analysis(
    ['lineage_death_command.py'],
    pathex=[],
    binaries=[
        (PYTHON_PREFIX + r'\python314.dll',    '.'),
        (PYTHON_PREFIX + r'\python3.dll',      '.'),
        (PYTHON_PREFIX + r'\vcruntime140.dll', '.'),
        (PYTHON_PREFIX + r'\vcruntime140_1.dll', '.'),
        (r'C:\Windows\System32\ucrtbase.dll',  '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-conio-l1-1-0.dll',       '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-convert-l1-1-0.dll',     '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-environment-l1-1-0.dll', '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-filesystem-l1-1-0.dll',  '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-heap-l1-1-0.dll',        '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-locale-l1-1-0.dll',      '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-math-l1-1-0.dll',        '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-multibyte-l1-1-0.dll',   '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-private-l1-1-0.dll',     '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-process-l1-1-0.dll',     '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-runtime-l1-1-0.dll',     '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-stdio-l1-1-0.dll',       '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-string-l1-1-0.dll',      '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-time-l1-1-0.dll',        '.'),
        (DOWNLEVEL + r'\api-ms-win-crt-utility-l1-1-0.dll',     '.'),
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

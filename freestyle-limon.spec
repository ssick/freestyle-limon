# -*- mode: python ; coding: utf-8 -*-
import os

# Overridable so packaging/build.sh (single-arch pyenv .venv) can request a plain
# single-arch build instead of universal2, which requires build_universal2.sh's
# separate python.org interpreter - see CLAUDE.md for why.
TARGET_ARCH = os.environ.get("FREESTYLE_LIMON_TARGET_ARCH", "universal2") or None
MIN_MACOS = os.environ.get("FREESTYLE_LIMON_MIN_MACOS", "10.13")

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static'), ('packaging/lemon-icon-base.png', 'packaging')],
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
    [],
    exclude_binaries=True,
    name='freestyle-limon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='freestyle-limon',
)

app = BUNDLE(
    coll,
    name='Freestyle Limón.app',
    icon='packaging/icon.icns',
    bundle_identifier='dev.stansick.freestyle-limon',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '0.1.0',
        'LSMinimumSystemVersion': MIN_MACOS,
    },
)

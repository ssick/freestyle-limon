# -*- mode: python ; coding: utf-8 -*-
import os

# Every release gets its own bundle identifier. macOS keys an app's identity -
# Dock tile, activation, "which window comes forward" - to CFBundleIdentifier,
# so two builds sharing one identifier are two processes competing to be the
# same app. packaging/build.sh derives these; the defaults only apply when
# PyInstaller is invoked directly.
BUNDLE_ID = os.environ.get('FL_BUNDLE_ID', 'dev.stansick.freestyle-limon')
VERSION = os.environ.get('FL_VERSION', '0.1.0')
BUILD = os.environ.get('FL_BUILD', '0')

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
    bundle_identifier=BUNDLE_ID,
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': BUILD,
        'LSMinimumSystemVersion': MIN_MACOS,
    },
)

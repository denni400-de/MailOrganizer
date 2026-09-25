# PyInstaller spec for Mail Organizer.
#
# Build with:  pyinstaller mailorganizer.spec
# (or via build_exe.bat / build_exe.sh, which set up a clean venv first)
#
# --onedir instead of --onefile: PyQt6 ships a lot of binary plugin files, and
# --onefile has to unpack all of them into a temp dir on every launch, which is
# slow and (per this project's own Windows long-path lessons) another way to
# run into deep-path/antivirus trouble. --onedir starts faster and is easier
# to diagnose if something's missing.

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['mailorganizer/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('mailorganizer/ui/styles/dark_theme.qss', 'mailorganizer/ui/styles'),
        ('mailorganizer/ui/styles/light_theme.qss', 'mailorganizer/ui/styles'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'PyQt6.sip',
        'sqlalchemy.sql.default_comparator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MailOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MailOrganizer',
)

# PyInstaller onedir spec. Qt DLLs stay as separate files (not single-file
# bundling) for faster startup, easier diagnosis, and simpler LGPL compliance
# (see docs/LICENSING.md).

from pathlib import Path

block_cipher = None

repo_root = Path(SPECPATH).parent
entry_point = str(repo_root / "src" / "genome_workbench" / "__main__.py")

a = Analysis(
    [entry_point],
    pathex=[str(repo_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    name="GenomeWorkbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
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
    name="GenomeWorkbench",
)

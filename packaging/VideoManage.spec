# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

spec_path = globals().get("SPECPATH")
if spec_path:
    project_root = Path(spec_path).resolve().parent
else:
    cwd = Path.cwd().resolve()
    project_root = cwd if (cwd / "backend" / "packaged_main.py").is_file() else cwd.parent

hiddenimports = (
    collect_submodules("app")
    + collect_submodules("onvif")
    + collect_submodules("zeep")
    + collect_submodules("passlib.handlers")
    + collect_submodules("aiosqlite")
)


a = Analysis(
    [str(project_root / "backend" / "packaged_main.py")],
    pathex=[str(project_root / "backend")],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="VideoManageBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VideoManageBackend",
)

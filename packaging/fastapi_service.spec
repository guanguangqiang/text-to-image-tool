from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve().parent

hidden_imports = (
    collect_submodules("uvicorn.lifespan")
    + collect_submodules("uvicorn.loops")
    + collect_submodules("uvicorn.protocols")
)

a = Analysis(
    [str(project_root / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FastAPI-Service",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    version=str(project_root / "packaging" / "version_info.txt"),
)

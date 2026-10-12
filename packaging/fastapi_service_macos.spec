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
    [],
    exclude_binaries=True,
    name="FastAPI-Service",
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
    a.datas,
    strip=False,
    upx=False,
    name="FastAPI-Service",
)

app = BUNDLE(
    coll,
    name="FastAPI-Service.app",
    icon=None,
    bundle_identifier="com.tangwen-tool.fastapi-service",
    info_plist={
        "CFBundleDisplayName": "FastAPI Service",
        "CFBundleName": "FastAPI Service",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
)

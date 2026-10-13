from pathlib import Path


project_root = Path(SPECPATH).resolve().parent
source_root = project_root / "src"
resources = project_root / "resources"
datas = [(str(resources), "resources")] if resources.exists() else []

a = Analysis(
    [str(source_root / "script2gif" / "main.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    name="Script2Gif",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="Script2Gif",
)

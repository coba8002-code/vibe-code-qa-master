# Build from repository root: pyinstaller --noconfirm windows/VibeQAMaster.spec
from pathlib import Path

# SPECPATH already points at the directory containing this .spec (windows/).
# Its parent is the repository root; stepping up twice broke CI packaging.
root = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(root / "windows_launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "ui" / "index.html"), "ui"), (str(root / "ui" / "workflow.js"), "ui")],
    hiddenimports=["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on", "multipart", "app.runtime"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="VibeQAMaster", console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VibeQAMaster")

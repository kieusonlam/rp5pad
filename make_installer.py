"""make_installer.py [version]: builds dist\\RP5Pad-Setup-<version>.exe from pad_version.py's version, or for tests with the one given. Python is bundled, so the person installing needs nothing.

Needs a venv with PyInstaller, one with vgamepad, and Inno Setup: set RP5PAD_BUILD_VENV, RP5PAD_PAD_VENV and RP5PAD_ISCC, or keep this machine's defaults."""
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools")
BUILD = os.environ.get("RP5PAD_BUILD_VENV", os.path.join(TOOLS, "pad-build-venv"))
PAD = os.environ.get("RP5PAD_PAD_VENV", os.path.join(TOOLS, "pad-venv"))
ISCC = os.environ.get("RP5PAD_ISCC", os.path.join(TOOLS, "innosetup", "ISCC.exe"))
VERSION_FILE = os.path.join(HERE, "pad_version.py")
with open(VERSION_FILE, encoding="utf-8") as f:
    original = f.read()
version = sys.argv[1] if len(sys.argv) > 1 else re.search(r'"([\d.]+)"', original).group(1)
site = os.path.join(PAD, "Lib", "site-packages")
work = os.path.join(HERE, "build", "pyi")
shutil.rmtree(work, ignore_errors=True)
target = os.path.join(BUILD, "Lib", "site-packages", "vgamepad")
if not os.path.isdir(target):   # copied, not installed with pip: installing it can start the driver's setup
    shutil.copytree(os.path.join(site, "vgamepad"), target)
try:
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(f'VERSION = "{version}"\n')
    subprocess.run([os.path.join(BUILD, "Scripts", "python.exe"), "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
                    "--name", "RP5Pad", "--windowed", "--onedir", "--icon", os.path.join(HERE, "assets", "app.ico"),
                    "--collect-all", "vgamepad", "--add-data", os.path.join(HERE, "assets") + ";assets",
                    "--distpath", os.path.join(work, "dist"), "--workpath", os.path.join(work, "work"), "--specpath", work,
                    os.path.join(HERE, "pad_tray.py")], check=True, cwd=HERE)
finally:
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(original)
msi = os.path.join(site, "vgamepad", "win", "vigem", "install", "x64", "ViGEmBusSetup_x64.msi")
subprocess.run([ISCC, "/Qp", f"/DVersion={version}", f"/DDriverMsi={msi}", os.path.join(HERE, "installer.iss")], check=True, cwd=HERE)
out = os.path.join(HERE, "dist", f"RP5Pad-Setup-{version}.exe")
print(out, round(os.path.getsize(out) / 1e6, 1), "MB")

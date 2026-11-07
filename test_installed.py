"""test_installed.py <setup.exe> <shot.png>: run with a Python that has Pillow. Installs per user (no admin, no driver, no firewall rule) into a temp folder, runs the exe with a bare environment, drives it with a local client, opens the tester, uninstalls. The source tray is stopped during the test and started again after."""
import ctypes
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import winreg
from ctypes import wintypes as w

from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
SETUP, SHOT = sys.argv[1], sys.argv[2]
u = ctypes.windll.user32
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
root = tempfile.mkdtemp(prefix="rp5pad-inst-")
app, state = os.path.join(root, "app"), os.path.join(root, "state")
os.makedirs(state)
with open(os.path.join(state, "pad_app.json"), "w", encoding="utf-8") as f:
    f.write('{"lan": false}')   # with WiFi on, Windows would show a firewall question on this desktop
log = os.path.expanduser(r"~\.rp5pad\tester.log")
log_before = os.path.getsize(log) if os.path.exists(log) else 0


class XS(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def xinput():
    x = XS()
    e = ctypes.windll.xinput1_4.XInputGetState(0, ctypes.byref(x))
    return (e, x.b, x.lt, x.rt, x.lx, x.ly, x.rx, x.ry)


def wait(cond, secs):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def pwsh(c):
    return subprocess.run(["pwsh", "-NoProfile", "-Command", c], capture_output=True, text=True).stdout.strip()


def run_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            return winreg.QueryValueEx(k, "RP5 Pad")[0]
    except OSError:
        return None


saved_run = run_value()
pwsh("Get-CimInstance Win32_Process -Filter \"name='pythonw.exe'\" | Where-Object CommandLine -match 'pad_tray\\.py' | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction Stop } catch {} }")
print("source tray stopped:", wait(lambda: not u.FindWindowW("RP5PadTray", None), 5))
proc = None
try:
    r = subprocess.run([SETUP, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/MERGETASKS=!desktopicon", f"/DIR={app}"], timeout=120)
    exe = os.path.join(app, "RP5Pad.exe")
    print("setup exit", r.returncode, "| exe:", os.path.exists(exe))
    print("start menu shortcut:", os.path.exists(os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\RP5 Pad.lnk")))
    env = {"SystemRoot": os.environ["SystemRoot"], "PATH": os.path.join(os.environ["SystemRoot"], "System32"), "USERPROFILE": os.environ["USERPROFILE"], "TEMP": os.environ["TEMP"], "TMP": os.environ["TMP"], "RP5PAD_STATE": os.path.join(state, "pairing.json")}
    proc = subprocess.Popen([exe, "--startup"], env=env, cwd=app)
    print("tray window:", wait(lambda: u.FindWindowW("RP5PadTray", None), 15))
    print("port 7878 open:", wait(lambda: socket.socket().connect_ex(("127.0.0.1", 7878)) == 0, 10))
    time.sleep(1.5)   # the probes above were seen as clients
    c = socket.create_connection(("127.0.0.1", 7878))
    c.settimeout(2)
    print("greeting:", c.recv(3))
    pk = struct.Struct("<2sHhhhhBBH")
    seq = [0]

    def send(btn, lx, ly, rx, ry, lt, rt, secs):
        end = time.time() + secs
        while time.time() < end:
            c.sendall(pk.pack(b"R5", btn, lx, ly, rx, ry, lt, rt, seq[0] & 0xff))
            seq[0] += 1
            time.sleep(0.03)

    send(0, 0, 0, 0, 0, 0, 0, 2.5)
    print("idle, XInput:", xinput())
    send(0x1000 | 0x200, -20000, -20000, 15000, 15000, 200, 60, 0.6)
    print("A+RB, sticks, triggers, XInput:", xinput())
    u.PostMessageW(u.FindWindowW("RP5PadTray", None), 0x111, 6, 0)
    for _ in range(40):   # keep sending: the server drops a client silent for a second
        send(0x1000 | 0x200, -20000, -20000, 15000, 15000, 200, 60, 0.2)
        if u.FindWindowW(None, "RP5 Pad tester"):
            break
    h = u.FindWindowW(None, "RP5 Pad tester")
    print("tester window:", bool(h))
    send(0x1000 | 0x200, -20000, -20000, 15000, 15000, 200, 60, 1.5)
    if h:
        u.SetForegroundWindow(h)
        send(0x1000 | 0x200, -20000, -20000, 15000, 15000, 200, 60, 1)
        rc = w.RECT()
        u.GetWindowRect(h, ctypes.byref(rc))
        ImageGrab.grab((rc.left, rc.top, rc.right, rc.bottom), all_screens=True).save(SHOT)
    c.close()
    print("pad gone after disconnect:", wait(lambda: xinput()[0] == 1167, 5))
    print("files in the app folder written at run time:", sorted(f for f in os.listdir(app) if f.endswith(".json")))
    u.PostMessageW(u.FindWindowW("RP5PadTray", None), 0x111, 4, 0)
    print("quit:", wait(lambda: proc.poll() is not None, 5))
finally:
    if proc and proc.poll() is None:
        proc.kill()
    un = os.path.join(app, "unins000.exe")
    if os.path.exists(un):
        subprocess.run([un, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=60)
        print("uninstalled, folder gone:", wait(lambda: not os.path.exists(exe), 15))
    print("start menu shortcut after:", os.path.exists(os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\RP5 Pad.lnk")))
    if saved_run and run_value() != saved_run:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            winreg.SetValueEx(k, "RP5 Pad", 0, winreg.REG_SZ, saved_run)
        print("restored the Run value")
    print("Run value same as before:", run_value() == saved_run)
    shutil.rmtree(root, ignore_errors=True)
    pwsh("explorer.exe (Join-Path ([Environment]::GetFolderPath('Desktop')) 'RP5 Pad.lnk')")
    print("source tray back:", wait(lambda: u.FindWindowW("RP5PadTray", None), 10))
    new_log = os.path.getsize(log) if os.path.exists(log) else 0
    print("tester errors:", "none" if new_log == log_before else open(log, encoding="utf-8").read()[log_before:][-800:])

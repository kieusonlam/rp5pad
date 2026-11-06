"""test_tester.py <adb serial> <out dir>: run with a Python that has Pillow. Restarts the tray, installs the app, shoots the tester window: idle, with buttons held on the RP5, with sticks and triggers sent from here; closes and reopens it."""
import ctypes
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from ctypes import wintypes as w

from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
HERE = r"D:\Games\_Dev\repos\rp5pad"
A = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", sys.argv[1]]
OUT = sys.argv[2]
PKG = "org.nx2a.rp5pad"
u = ctypes.windll.user32


def sh(c):
    subprocess.run(A + ["shell", c], capture_output=True)


def shot(name):
    h = u.FindWindowW(None, "RP5 Pad tester")
    if not h:
        print("NO TESTER WINDOW for", name)
        return
    u.SetForegroundWindow(h)
    time.sleep(0.05)
    r = w.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    ImageGrab.grab((r.left, r.top, r.right, r.bottom), all_screens=True).save(os.path.join(OUT, name + ".png"))
    print("shot", name, r.right - r.left, "x", r.bottom - r.top)


def tray():
    return u.FindWindowW("RP5PadTray", None)


restart = "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe'\" | Where-Object CommandLine -match 'pad_tray\\.py' | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction Stop } catch {} }; Start-Sleep 1; explorer.exe (Join-Path ([Environment]::GetFolderPath('Desktop')) 'RP5 Pad.lnk')"
subprocess.run(["pwsh", "-NoProfile", "-Command", restart])
time.sleep(3)
print(subprocess.run(A + ["install", "-r", os.path.join(HERE, "rp5pad.apk")], capture_output=True, text=True).stdout.strip().splitlines()[-1])
sh(f"input keyevent KEYCODE_WAKEUP; am start -n {PKG}/.PadActivity")
time.sleep(6)
print("question on the PC:", bool(u.FindWindowW("#32770", "RP5 Pad: allow this device?")))
u.PostMessageW(tray(), 0x111, 6, 0)
time.sleep(4)
shot("idle")

stop = []


def hold():
    while not stop:
        sh("input gamepad keyevent --longpress BUTTON_A & input gamepad keyevent --longpress BUTTON_R1 & input gamepad keyevent --longpress DPAD_LEFT; wait")


t = threading.Thread(target=hold)
t.start()


class XS(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


end = time.time() + 8
most = 0
while time.time() < end:   # the moment all three are held
    x = XS()
    ctypes.windll.xinput1_4.XInputGetState(0, ctypes.byref(x))
    if bin(x.b).count("1") >= 3:
        most = x.b
        break
    time.sleep(0.005)
print("held on XInput:", hex(most))
time.sleep(0.05)
shot("held")
stop.append(1)
t.join()

sh(f"am force-stop {PKG}")
time.sleep(2)
shot("waiting")
c = socket.create_connection(("127.0.0.1", 7878))
c.settimeout(1)
c.recv(3)
pk = struct.Struct("<2sHhhhhBBH")
end = time.time() + 2.5
threading.Thread(target=lambda: (time.sleep(1.5), shot("sticks"))).start()
i = 0
while time.time() < end:   # stick up-left and right-down, LT most of the way, RT a little; X and Start
    c.sendall(pk.pack(b"R5", 0x4000 | 0x10, -30000, -30000, 30000, 30000, 200, 60, i & 0xff))
    i += 1
    time.sleep(0.03)
c.close()
time.sleep(0.5)

u.PostMessageW(u.FindWindowW(None, "RP5 Pad tester"), 0x10, 0, 0)   # WM_CLOSE
time.sleep(1)
print("hidden:", not u.IsWindowVisible(u.FindWindowW(None, "RP5 Pad tester")), "| tray alive:", bool(tray()))
u.PostMessageW(tray(), 0x111, 6, 0)
time.sleep(3)
print("reopened:", bool(u.IsWindowVisible(u.FindWindowW(None, "RP5 Pad tester"))))
sh(f"am start -n {PKG}/.PadActivity")
time.sleep(5)
shot("final")
log = os.path.expanduser(r"~\.rp5pad\tester.log")
print("tester errors:", open(log, encoding="utf-8").read()[-800:] if os.path.exists(log) else "none")

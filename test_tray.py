"""test_tray.py: the startup setting on a scratch registry key (not the real Run key), the icon as a picture, the tray app's window answering. Needs the tray app running for the last part."""
import ctypes
import socket
import struct
import sys
import time
import winreg

import pad_tray

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KEY = r"Software\RP5PadTest"
pad_tray.startup_set(False, KEY)
a = pad_tray.startup_on(KEY)
pad_tray.startup_set(True, KEY)
b = pad_tray.startup_on(KEY)
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
    cmd = winreg.QueryValueEx(k, pad_tray.RUN_NAME)[0]
pad_tray.startup_set(False, KEY)
c = pad_tray.startup_on(KEY)
winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY)
print("startup off/on/off:", a, b, c, "| command:", cmd)
print("real Run key has RP5 Pad:", pad_tray.startup_on())
assert (a, b, c) == (False, True, False) and "pythonw.exe" in cmd and "--startup" in cmd

ok = ctypes.windll.user32.FindWindowW(pad_tray.CLASS, None)
print("tray window:", bool(ok))


class S(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def slots():
    return [ctypes.windll.xinput1_4.XInputGetState(i, ctypes.byref(S())) for i in range(4)].count(0)


before = slots()
try:
    c = socket.create_connection(("127.0.0.1", 7878), timeout=2)
    c.settimeout(2)
    hello = c.recv(2)
    c.sendall(struct.pack("<2sHhhhhBBH", b"R5", 0x1000, 0, 0, 0, 0, 0, 0, 1))
    time.sleep(0.7)
    during = slots()
    c.close()
    time.sleep(0.7)
    print("pads before/during/after a connection:", before, during, slots(), "| greeting", hello)
except OSError as e:
    print("no connection to the tray app:", e)

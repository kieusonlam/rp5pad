"""test_tray2.py <adb serial>: the virtual pad goes away with the RP5 and comes back; the WiFi menu command restarts the tray app on the other socket, twice (back to the setting it had)."""
import ctypes
import json
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", sys.argv[1], "shell"]
PKG = "org.nx2a.rp5pad"


class S(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def pads():
    return [ctypes.windll.xinput1_4.XInputGetState(i, ctypes.byref(S())) for i in range(4)].count(0)


def listen():
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 7878 -State Listen).LocalAddress"], capture_output=True, text=True)
    return r.stdout.strip()


print("pads while connected:", pads())
subprocess.run(ADB + [f"am force-stop {PKG}"], capture_output=True)
time.sleep(2.5)
print("pads with the app closed:", pads())
for i in range(2):
    h = ctypes.windll.user32.FindWindowW("RP5PadTray", None)
    ctypes.windll.user32.PostMessageW(h, 0x111, 2, 0)   # WM_COMMAND, ID_WIFI
    time.sleep(4)
    print("after WiFi toggle: listening on", listen(), "| config", json.load(open("pad_app.json")), "| window", bool(ctypes.windll.user32.FindWindowW("RP5PadTray", None)))
subprocess.run(ADB + [f"am start -n {PKG}/.PadActivity"], capture_output=True)
time.sleep(4)
print("pads after reopening the app:", pads())

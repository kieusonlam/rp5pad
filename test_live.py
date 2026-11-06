"""test_live.py: with pad_server.py and the app running, injects gamepad keys on the RP5 and watches XInput on this PC."""
import ctypes
import os
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", os.environ["RP5_SERIAL"], "shell"]


class S(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


seen, stop = set(), False


def poll():
    x = ctypes.windll.xinput1_4
    while not stop:
        for i in range(4):
            s = S()
            if x.XInputGetState(i, ctypes.byref(s)) == 0 and s.b:
                seen.add(s.b)
        time.sleep(0.005)


t = threading.Thread(target=poll)
t.start()
want = {"BUTTON_A": 0x1000, "BUTTON_B": 0x2000, "BUTTON_X": 0x4000, "BUTTON_Y": 0x8000, "BUTTON_L1": 0x100, "BUTTON_R1": 0x200, "BUTTON_START": 0x10, "BUTTON_SELECT": 0x20, "BUTTON_THUMBL": 0x40, "BUTTON_THUMBR": 0x80, "DPAD_UP": 1, "DPAD_LEFT": 4}
for k in want:
    subprocess.run(ADB + [f"input gamepad keyevent --longpress {k}"], capture_output=True)
    time.sleep(0.2)
time.sleep(0.3)
stop = True
t.join()
for k, v in want.items():
    print(f"{k:15} {v:#06x} {'ok' if v in seen else 'MISSING'}")
print("other values seen:", [hex(v) for v in seen - set(want.values())])

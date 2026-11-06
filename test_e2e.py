"""test_e2e.py: (1) the app on the RP5 over USB to pad_server.py --dry, with injected gamepad input; (2) the real server to XInput, with packets from here. Leaves the app closed and the screen off."""
import os
import ctypes
import socket
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", os.environ["RP5_SERIAL"]]
PY = r"D:\Games\_Dev\tools\pad-venv\Scripts\python.exe"
APP = "org.nx2a.rp5pad"


def sh(c):
    return subprocess.run(ADB + ["shell", c], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()


def part1():
    subprocess.run(ADB + ["reverse", "tcp:7878", "tcp:7878"], check=True, capture_output=True)
    p = subprocess.Popen([PY, "pad_server.py", "--dry"], stdout=subprocess.PIPE, text=True, encoding="utf-8")
    time.sleep(1)
    sh("input keyevent KEYCODE_WAKEUP")
    sh(f"am start -n {APP}/.PadActivity")
    time.sleep(3)
    print("focus:", sh("dumpsys window | grep mCurrentFocus"))
    for b in ("BUTTON_A", "BUTTON_Y", "BUTTON_START", "BUTTON_L1", "DPAD_UP"):
        sh(f"input gamepad keyevent {b}")
        time.sleep(0.3)
    sh("input joystick motionevent MOVE 0.5 0.5")
    time.sleep(0.3)
    sh(f"am force-stop {APP}; input keyevent KEYCODE_SLEEP")
    time.sleep(2)
    p.terminate()
    out = p.stdout.read().splitlines()
    btns = sorted({l.split()[1] for l in out if l.startswith("btn")})
    print("connected" if any(l.startswith("connected") for l in out) else "NOT CONNECTED", "| button states seen:", btns)
    print("non-zero stick lines:", [l for l in out if l.startswith("btn") and " L      0      0" not in l][:3])
    print("last state:", [l for l in out if l.startswith("btn")][-1:])


class S(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def xstate():
    s = S()
    return (ctypes.windll.xinput1_4.XInputGetState(0, ctypes.byref(s)), hex(s.b), s.lx, s.ly, s.rx, s.ry, s.lt, s.rt)


def part2():
    p = subprocess.Popen([PY, "pad_server.py", "--port", "7980"], stdout=subprocess.DEVNULL)
    time.sleep(2)
    c = socket.create_connection(("127.0.0.1", 7980))
    c.sendall(struct.pack("<2sHhhhhBBH", b"R5", 0x9001, -32767, -32767, 32767, 32767, 255, 128, 1))   # Android: stick up is negative
    time.sleep(0.5)
    print("XInput, pressed:", xstate(), "(want 0x9001, lx -32767, ly +32767, rx 32767, ry -32767, 255, 128)")
    c.close()
    time.sleep(0.5)
    print("XInput, released:", xstate())
    p.terminate()


if __name__ == "__main__":
    if sys.argv[1:] != ["pc"]:
        part1()
    part2()

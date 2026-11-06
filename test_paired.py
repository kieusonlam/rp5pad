"""test_paired.py <adb serial>: after pairing, reopening the app connects with no question on the PC."""
import ctypes
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
A = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", sys.argv[1], "shell"]
PKG = "org.nx2a.rp5pad"


def established():
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 7878 -State Established -ErrorAction SilentlyContinue | Measure-Object).Count"], capture_output=True, text=True)
    return r.stdout.strip() != "0"


def question():
    return bool(ctypes.windll.user32.FindWindowW("#32770", "RP5 Pad: allow this device?"))


d = json.load(open(os.path.join(os.environ["LOCALAPPDATA"], "RP5Pad", "pairing.json"), encoding="utf-8"))
print("paired:", [v["name"] for v in d["devices"].values()], "| connected:", established())
for i in range(3):
    subprocess.run(A + [f"am force-stop {PKG}"], capture_output=True)
    time.sleep(1.5)
    gone = not established()
    subprocess.run(A + [f"am start -n {PKG}/.PadActivity"], capture_output=True)
    t = time.time()
    while time.time() - t < 15 and not established():
        time.sleep(0.2)
    print(f"reopen {i + 1}: closed {gone}, connected {established()} after {time.time() - t:.1f} s, question on PC: {question()}")

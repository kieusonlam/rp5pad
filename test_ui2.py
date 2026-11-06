"""test_ui2.py <adb serial> <out png>: how long each connection choice takes to connect; a screenshot taken on the device while a button is held."""
import subprocess
import sys
import time

ADB = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", sys.argv[1]]
TAP = {"auto": "163 712", "usb": "382 712", "wifi": "600 712"}


def sh(c):
    subprocess.run(ADB + ["shell", c], capture_output=True)


def established():
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 7878 -State Established -ErrorAction SilentlyContinue | Measure-Object).Count"], capture_output=True, text=True)
    return r.stdout.strip() != "0"


def timed(a, b):
    sh(f"input tap {TAP[a]}")
    time.sleep(2)
    print(a, "connected:", established(), flush=True)
    sh(f"input tap {TAP[b]}")
    t = time.time()
    while time.time() - t < 25:
        if established():
            print(f"{a} -> {b}: connected after {time.time() - t:.1f} s", flush=True)
            return
        time.sleep(0.3)
    print(f"{a} -> {b}: NOT connected in 25 s", flush=True)


for _ in range(3):
    timed("usb", "wifi")
timed("usb", "auto")
sh("input gamepad keyevent --longpress BUTTON_A & sleep 0.15; input gamepad keyevent --longpress BUTTON_R1 & sleep 0.15; screencap -p /data/local/tmp/held.png; wait")
subprocess.run(ADB + ["pull", "/data/local/tmp/held.png", sys.argv[2]], capture_output=True)
sh("rm /data/local/tmp/held.png")
print("done")

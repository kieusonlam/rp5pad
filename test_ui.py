"""test_ui.py <adb serial> <out dir>: screenshots of each connection choice and of a held button; leaves Auto chosen."""
import os
import subprocess
import sys
import threading
import time

ADB = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", sys.argv[1]]
OUT = sys.argv[2]


def sh(c):
    subprocess.run(ADB + ["shell", c], capture_output=True)


def shot(name):
    with open(os.path.join(OUT, name + ".png"), "wb") as f:
        subprocess.run(ADB + ["exec-out", "screencap -p"], stdout=f)


TAP = {"auto": "163 712", "usb": "382 712", "wifi": "600 712"}
for m in ("usb", "wifi"):
    sh(f"input tap {TAP[m]}")
    time.sleep(3)
    shot(m)
sh(f"input tap {TAP['auto']}")
time.sleep(3)
shot("auto")
for b in ("BUTTON_A", "BUTTON_R1", "DPAD_LEFT"):
    pass
stop = []


def hold():
    while not stop:
        sh("input gamepad keyevent --longpress BUTTON_A BUTTON_R1 DPAD_LEFT")


t = threading.Thread(target=hold)
t.start()
time.sleep(1.2)
shot("held")
stop.append(1)
t.join()
print("done")

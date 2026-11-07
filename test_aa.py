"""test_aa.py <shot.png>: run with a Python that has Pillow. Draws the tester from THIS folder's sprites with a made-up pressed state and shoots it. Needs no driver or running app, and leaves a running RP5 Pad alone."""
import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes as w

from PIL import ImageGrab

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ctypes.windll.shcore.SetProcessDpiAwareness(2)
import pad_server  # noqa: E402
import pad_tester  # noqa: E402

u = ctypes.windll.user32
u.GetParent.argtypes, u.GetParent.restype = [w.HWND], w.HWND
u.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
pad_server.stats.update(ip="127.0.0.1", pps=33, rtt=None, slot=0)
fake = pad_tester.XState(0, 0x1000 | 0x200, 200, 60, -20000, 20000, 15000, -15000)
pad_tester.read_xinput = lambda slot: (0, fake)
t = pad_tester.Tester()
threading.Thread(target=t.guarded, daemon=True).start()
time.sleep(3)
h = u.GetParent(t.r.winfo_id())
u.SetForegroundWindow(h)
time.sleep(1)
print("drawn from:", pad_tester.HERE)
r = w.RECT()
u.GetWindowRect(h, ctypes.byref(r))
ImageGrab.grab((r.left, r.top, r.right, r.bottom), all_screens=True).convert("RGB").save(sys.argv[1])
print("shot", r.right - r.left, r.bottom - r.top)
os._exit(0)

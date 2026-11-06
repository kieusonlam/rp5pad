"""test_knob.py <serial>: app closed; a local client sends all-zero packets, several connections in a row. XInput must settle at zero each time (a new virtual pad can otherwise read as stuck off-centre)."""
import ctypes
import socket
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
A = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", sys.argv[1], "shell"]


class XS(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def read():
    x = XS()
    e = ctypes.windll.xinput1_4.XInputGetState(0, ctypes.byref(x))
    return e, x.lx, x.ly, x.rx, x.ry


subprocess.run(A + ["am force-stop org.nx2a.rp5pad"], capture_output=True)
time.sleep(2)
pk = struct.Struct("<2sHhhhhBBH")
bad = 0
for run in range(8):
    c = socket.create_connection(("127.0.0.1", 7878))
    c.settimeout(1)
    c.recv(3)
    seen = []
    for i in range(70):
        c.sendall(pk.pack(b"R5", 0, 0, 0, 0, 0, 0, 0, i & 0xff))
        now = read()
        if not seen or seen[-1] != now:
            seen.append(now)
        time.sleep(0.03)
    c.close()
    ok = seen[-1] == (0, 0, 0, 0, 0)
    bad += not ok
    print(run, "ok" if ok else "STUCK", seen)
    time.sleep(1)
print("stuck:", bad, "of 8")

"""test_physical.py <seconds> <out.txt>: while a person presses every button and moves both sticks and triggers on the RP5, records what XInput saw: buttons ever pressed, each axis' range, and how fast updates came."""
import ctypes
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class XS(ctypes.Structure):
    _fields_ = [("p", ctypes.c_ulong), ("b", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


NAMES = {1: "Up", 2: "Down", 4: "Left", 8: "Right", 0x10: "Start", 0x20: "Back", 0x40: "L3", 0x80: "R3", 0x100: "LB", 0x200: "RB", 0x400: "Guide", 0x1000: "A", 0x2000: "B", 0x4000: "X", 0x8000: "Y"}
get = ctypes.windll.xinput1_4.XInputGetState
end = time.time() + float(sys.argv[1])
seen, lo, hi, packets, last, slot = 0, {}, {}, 0, None, None
while time.time() < end:
    for i in ([slot] if slot is not None else range(4)):
        x = XS()
        if get(i, ctypes.byref(x)) == 0:
            slot = i
            break
    else:
        slot = None
        time.sleep(0.05)
        continue
    if x.p != last:
        last, packets = x.p, packets + 1
    seen |= x.b
    for k in ("lt", "rt", "lx", "ly", "rx", "ry"):
        v = getattr(x, k)
        lo[k], hi[k] = min(lo.get(k, v), v), max(hi.get(k, v), v)
    time.sleep(0.004)
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write(f"slot {slot}, state changes {packets}\n")
    f.write("buttons seen: " + " ".join(n for bit, n in NAMES.items() if seen & bit) + "\n")
    f.write("never seen: " + " ".join(n for bit, n in NAMES.items() if not seen & bit) + "\n")
    for k in ("lx", "ly", "rx", "ry", "lt", "rt"):
        f.write(f"{k}: {lo.get(k)} .. {hi.get(k)}\n")
print(open(sys.argv[2], encoding="utf-8").read())

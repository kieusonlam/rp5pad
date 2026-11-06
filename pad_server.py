"""pad_server.py: the RP5 as an Xbox 360 pad on this PC. Run it, open RP5 Pad on the handheld.

USB (default): listens on 127.0.0.1 only and keeps `adb reverse` set whenever the handheld is plugged in. WiFi: --lan; the app finds this PC by itself.
--dry prints what arrives instead of driving a pad (no driver needed).
"""
import argparse
import ctypes
import hashlib
import hmac
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time

if sys.stdout:   # none under pythonw
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PORT = 7878
PACKET = struct.Struct("<2sHhhhhBBH")
ADB = shutil.which("adb") or r"D:\dev\android-sdk\platform-tools\adb.exe"
report = print   # pad_app.pyw shows these in its window
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def state_path():
    # In the user's home, not AppData: Windows redirects AppData per MSIX package, so a copy started from a packaged app and one started from the Desktop would keep different lists
    return os.environ.get("RP5PAD_STATE") or os.path.join(os.path.expanduser("~"), ".rp5pad", "pairing.json")


class Pairing:
    """This PC's id and the devices allowed over WiFi, with their keys; outside the source folder."""
    def __init__(self):
        self.path = state_path()
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        self.pc_id, self.devices = d.get("pc_id") or secrets.token_hex(16), d.get("devices", {})
        if not d.get("pc_id"):
            self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"pc_id": self.pc_id, "devices": self.devices}, f, indent=1)
        for i in range(10):
            try:
                os.replace(self.path + ".tmp", self.path)
                return
            except PermissionError:   # someone has it open for a moment (Windows refuses the replace then)
                if i == 9:
                    raise
                time.sleep(0.2)

    def add(self, dev, name, key):
        self.devices[dev] = {"name": name, "key": key.hex()}
        self.save()

    def forget_all(self):
        self.devices = {}
        self.save()


def ask_console(name, ip, code):
    try:
        return input(f"{name} at {ip} wants to connect, code {code}. Allow? [y/N] ").strip().lower() == "y"
    except (EOFError, RuntimeError):
        return False


ask_pair = ask_console   # pad_tray.py asks in a dialog
COOLDOWN_S = 30
stats = {"ip": None, "pps": 0, "rtt": None, "slot": None}   # read by pad_tester.py


def read_exact(c, n):
    buf = b""
    while len(buf) < n:
        got = c.recv(n - len(buf))
        if not got:
            raise ConnectionError("closed during the handshake")
        buf += got
    return buf


def handshake(c, ip, pairing, cooldown, trust_loopback=True):
    """True when this connection may press buttons. Greeting: "R5U" (USB, adb has already authorized this PC) or "R5A" + pc id + nonce.
    Known device: "H" + id + HMAC-SHA256(key, nonce + id), answered "K", or "N" when unknown or wrong.
    New device: "P" + id + name length + name, answered "B" (recently declined), or "C" + 6-digit code shown on both sides, then "Y" + key or "D"."""
    if trust_loopback and ip == "127.0.0.1":
        c.sendall(b"R5U")
        return True
    nonce = os.urandom(16)
    c.sendall(b"R5A" + bytes.fromhex(pairing.pc_id) + nonce)
    kind, dev = read_exact(c, 1), read_exact(c, 16)
    if kind == b"H":
        mac = read_exact(c, 32)
        known = pairing.devices.get(dev.hex())
        if known and hmac.compare_digest(mac, hmac.new(bytes.fromhex(known["key"]), nonce + dev, hashlib.sha256).digest()):
            c.sendall(b"K")
            return True
        c.sendall(b"N")
        return False
    if kind != b"P":
        return False
    raw = read_exact(c, read_exact(c, 1)[0])
    name = "".join(ch for ch in raw.decode("utf-8", "replace") if ch.isprintable())[:40] or "Unknown device"
    if cooldown.get(ip, 0) > time.monotonic():
        c.sendall(b"B")
        return False
    code = f"{secrets.randbelow(10 ** 6):06d}"
    c.sendall(b"C" + code.encode())
    if not ask_pair(name, ip, code):
        cooldown[ip] = time.monotonic() + COOLDOWN_S
        c.sendall(b"D")
        return False
    key = os.urandom(32)
    pairing.add(dev.hex(), name, key)   # first: a key the PC could not store must not reach the device
    c.sendall(b"Y" + key)
    report("paired:", name, ip, flush=True)
    return True


def flip(v):   # Android: up is negative; XInput: up is positive
    return min(32767, -v)


class XState(ctypes.Structure):
    _fields_ = [("packet", ctypes.c_ulong), ("buttons", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


class Pad:
    """Exists on the PC only while the RP5 is connected: a game then sees no controller otherwise, and takes a disconnect as one."""
    def __init__(self):
        import vgamepad   # fails here when the driver is missing
        self.v, self.g = vgamepad, None

    def close(self):
        self.g = None

    def slot(self):
        """The XInput slot the driver gave this pad, once it has; None before that."""
        if self.g is None:
            return None
        try:
            from vgamepad.win import vigem_client as vc
            n = ctypes.c_ulong(0)
            return n.value if vc.vigem_target_x360_get_user_index(self.g._busp, self.g._devicep, ctypes.byref(n)) == 0x20000000 else None
        except (ImportError, AttributeError, OSError):
            return None

    def set(self, b, lx, ly, rx, ry, lt, rt):
        if self.g is None:
            self.g = self.v.VX360Gamepad()
            self.settle_until = time.perf_counter() + 5
        r = self.g.report
        r.wButtons, r.bLeftTrigger, r.bRightTrigger = b, lt, rt
        r.sThumbLX, r.sThumbLY, r.sThumbRX, r.sThumbRY = lx, flip(ly), rx, flip(ry)
        self.g.update()
        if self.settle_until:
            self.settle(r)

    def settle(self, r):
        """Measured: a new pad can read as stuck at L -3356 -1869 R -3255 -848 in XInput while the reports stay all zero, whatever arrived before Windows opened it. A changed report clears it, so for the first seconds compare and nudge."""
        if time.perf_counter() > self.settle_until:
            self.settle_until = 0
            return
        slot, x = self.slot(), XState()
        if slot is None or ctypes.windll.xinput1_4.XInputGetState(slot, ctypes.byref(x)) != 0:
            return
        if (x.lx, x.ly, x.rx, x.ry) != (r.sThumbLX, r.sThumbLY, r.sThumbRX, r.sThumbRY):
            want = r.sThumbLX
            r.sThumbLX = want + 1 if want < 32767 else want - 1
            self.g.update()
            r.sThumbLX = want
            self.g.update()


def bind_retry(s, addr):   # a port just left by a restarting copy of this may take a moment to free
    for i in range(10):
        try:
            return s.bind(addr)
        except OSError:
            if i == 9:
                raise
            time.sleep(0.5)


class Dry:
    def close(self):
        pass

    def set(self, *v):
        print("btn %04x  L %6d %6d  R %6d %6d  LT %3d RT %3d" % v, flush=True)


def adb_reverse_loop():
    """Sets adb reverse on each USB device as it appears, so plugging in after starting works too."""
    if not os.path.exists(ADB):
        report("adb not found: USB needs `adb reverse tcp:7878 tcp:7878`, or use --lan", flush=True)
        return
    done = set()
    while True:
        out = subprocess.run([ADB, "devices"], capture_output=True, text=True, creationflags=HIDDEN).stdout.splitlines()[1:]
        usb = {l.split()[0] for l in out if l.endswith("device") and ":" not in l.split()[0]}
        for d in usb - done:
            r = subprocess.run([ADB, "-s", d, "reverse", f"tcp:{PORT}", f"tcp:{PORT}"], capture_output=True, text=True, creationflags=HIDDEN)
            report(f"adb reverse on {d}:", "ok" if r.returncode == 0 else r.stderr.strip(), flush=True)
        done = usb
        time.sleep(3)


def discovery_loop(bind, port):
    """Answers the app's broadcast, so it needs no IP."""
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_retry(u, (bind, port))
    while True:
        data, addr = u.recvfrom(16)
        if data == b"RP5PAD?":
            u.sendto(b"RP5PAD!", addr)


def read_packet(c):
    buf = b""
    while len(buf) < PACKET.size:
        got = c.recv(PACKET.size - len(buf))
        if not got:
            return None
        buf += got
    return PACKET.unpack(buf)


def serve(pad, lan, port, trust_loopback=True):
    pairing, cooldown = Pairing(), {}
    s = socket.socket()
    bind_retry(s, ("0.0.0.0" if lan else "127.0.0.1", port))
    s.listen(1)
    report(f"waiting on port {port} ({'LAN' if lan else 'USB only'}); Ctrl+C to stop", flush=True)
    s.settimeout(0.5)   # so Ctrl+C works on Windows
    while True:
        try:
            c, addr = s.accept()
        except TimeoutError:
            continue
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        c.settimeout(2.0)
        allowed = False
        try:
            with c:
                allowed = handshake(c, addr[0], pairing, cooldown, trust_loopback)
                if not allowed:
                    report("refused:", addr[0], flush=True)
                    continue
                report("connected:", addr[0], flush=True)
                c.settimeout(1.0)   # the app sends at least every 100 ms
                stats.update(ip=addr[0], pps=0, rtt=None, slot=None)
                seen, since, ping_id, ping_at, ping_last = 0, time.perf_counter(), 0, 0.0, 0.0
                while True:
                    p = read_packet(c)
                    if p is None:
                        break
                    if p[0] != b"R5":
                        report("not our protocol, dropped:", addr[0], flush=True)
                        break
                    pad.set(*p[1:8])
                    if stats["slot"] is None and hasattr(pad, "slot"):
                        stats["slot"] = pad.slot()
                    now = time.perf_counter()
                    seen += 1
                    if now - since >= 1:
                        stats["pps"] = round(seen / (now - since))
                        seen, since = 0, now
                    if ping_at and p[8] >> 8 == ping_id:   # the app echoes the byte below in the high half of its sequence number
                        stats["rtt"] = (now - ping_at) * 1000
                        ping_at = 0.0
                    if (not ping_at and now - ping_last >= 0.5) or (ping_at and now - ping_at > 2):
                        ping_id = ping_id % 255 + 1
                        c.sendall(bytes([ping_id]))
                        ping_at = ping_last = now
        except OSError as e:
            report("connection lost:", repr(e), flush=True)
        if allowed:
            stats.update(ip=None, pps=0, rtt=None, slot=None)
            pad.set(0, 0, 0, 0, 0, 0, 0)   # nothing stays held
            pad.close()
            report("disconnected", flush=True)


def run(pad, lan, port, adb=True):
    if adb:
        threading.Thread(target=adb_reverse_loop, daemon=True).start()
    if lan:
        threading.Thread(target=discovery_loop, args=("0.0.0.0", port), daemon=True).start()
    serve(pad, lan, port)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--lan", action="store_true", help="accept WiFi connections (any machine on the network can then press buttons)")
    a.add_argument("--dry", action="store_true")
    a.add_argument("--port", type=int, default=PORT, help=argparse.SUPPRESS)
    o = a.parse_args()
    try:
        pad = Dry() if o.dry else Pad()
    except Exception as e:
        sys.exit(f"cannot create the virtual pad ({e}). Needs the ViGEmBus driver and `pip install vgamepad`.")
    try:
        run(pad, o.lan, o.port, not o.dry)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

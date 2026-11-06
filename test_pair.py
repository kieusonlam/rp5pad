"""test_pair.py: the pairing handshake, against pad_server.serve with loopback not trusted (as a WiFi client) and a scratch state file."""
import hashlib
import hmac
import os
import socket
import struct
import sys
import tempfile
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tmp = tempfile.mkdtemp()
os.environ["RP5PAD_STATE"] = os.path.join(tmp, "pairing.json")
import pad_server  # noqa: E402

PORT = 7983
sets, answers, asked = [], [], []


class Rec:
    def set(self, *v):
        sets.append(v)

    def close(self):
        pass


def ask(name, ip, code):
    asked.append((name, code))
    return answers.pop(0)


pad_server.ask_pair = ask
pad_server.report = lambda *a, **k: None
threading.Thread(target=pad_server.serve, args=(Rec(), False, PORT, False), daemon=True).start()
time.sleep(0.3)
PK = struct.Struct("<2sHhhhhBBH")
ID = bytes(range(16))
fails = 0


def check(what, ok):
    global fails
    fails += not ok
    print(("ok   " if ok else "FAIL ") + what)


def greet():
    c = socket.create_connection(("127.0.0.1", PORT))
    c.settimeout(3)
    g = pad_server.read_exact(c, 3 + 16 + 16)
    assert g[:3] == b"R5A", g[:3]
    return c, g[19:]


def pair(dev=ID, name=b"Retroid"):
    c, _ = greet()
    c.sendall(b"P" + dev + bytes([len(name)]) + name)
    r = c.recv(1)
    code = c.recv(6).decode() if r == b"C" else None
    if code:
        r = c.recv(1)
    key = pad_server.read_exact(c, 32) if r == b"Y" else None
    return c, r, code, key


def hello(key, dev=ID):
    c, nonce = greet()
    c.sendall(b"H" + dev + hmac.new(key, nonce + dev, hashlib.sha256).digest())
    return c, c.recv(1)


# Nothing passes before the handshake
c, _ = greet()
c.sendall(PK.pack(b"R5", 0x1000, 0, 0, 0, 0, 0, 0, 1))
time.sleep(0.3)
c.close()
time.sleep(0.2)
check("a packet instead of a handshake presses nothing", not sets and not asked)

# Declined, then the cooldown
answers.append(False)
c, r, code, key = pair()
check("declined: answered D, no key", r == b"D" and key is None and len(code) == 6 and code.isdigit())
c.close()
c, r, code, key = pair()
check("asked again at once: B, no second question", r == b"B" and len(asked) == 1)
c.close()
time.sleep(0.2)

# Allowed: only then does input count
print("(waiting out the 30 s cooldown)", flush=True)
time.sleep(30.5)
answers.append(True)
c, r, code, key = pair()
check("allowed: answered Y with a key", r == b"Y" and key is not None and len(key) == 32)
check("the question showed the device name", asked[-1][0] == "Retroid")
c.sendall(PK.pack(b"R5", 0x1000, 0, 0, 0, 0, 0, 0, 2))
time.sleep(0.3)
check("input counts after pairing", sets and sets[-1][0] == 0x1000)
c.close()
time.sleep(0.3)
check("released on disconnect", sets[-1][0] == 0)

# Later connections need the key, no question
n = len(asked)
c, r = hello(key)
check("known device with the right key: K, no question", r == b"K" and len(asked) == n)
c.sendall(PK.pack(b"R5", 0x2000, 0, 0, 0, 0, 0, 0, 3))
time.sleep(0.3)
check("its input counts", sets[-1][0] == 0x2000)
c.close()
time.sleep(0.3)
k = len(sets)
c, r = hello(b"x" * 32)
check("wrong key: N", r == b"N")
c.close()
c, r = hello(key, bytes(16))
check("right key, other device id: N", r == b"N")
c.close()
time.sleep(0.2)
check("no input from either", len(sets) == k)

# Replaying an old answer fails: the nonce differs
c1, nonce1 = greet()
sig = hmac.new(key, nonce1 + ID, hashlib.sha256).digest()
c1.close()
time.sleep(0.2)
c2, nonce2 = greet()
c2.sendall(b"H" + ID + sig)
check("a replayed answer: N", nonce1 != nonce2 and c2.recv(1) == b"N")
c2.close()

# The key is stored, outside the source; a reload still knows the device; forgetting works
p = pad_server.Pairing()
check("device stored and reloaded", ID.hex() in p.devices and p.path.startswith(tmp))
p.forget_all()
check("forget_all empties the list", not pad_server.Pairing().devices)
print("PASS" if not fails else f"FAILED {fails}")
sys.exit(1 if fails else 0)

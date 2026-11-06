"""test_protocol.py: pad_server.py --dry against packets built as PadActivity.fill() does; checks what it prints, including the release on disconnect."""
import socket
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PORT = 7979
p = subprocess.Popen([sys.executable, "pad_server.py", "--dry", "--port", str(PORT)], stdout=subprocess.PIPE, text=True)
time.sleep(1)
c = socket.create_connection(("127.0.0.1", PORT))
pk = struct.Struct("<2sHhhhhBBH")
c.sendall(pk.pack(b"R5", 0x1001, -32767, 32767, 100, -100, 255, 7, 1))
c.sendall(pk.pack(b"R5", 0, 0, 0, 0, 0, 0, 0, 2)[:8])   # split in two: a TCP stream may do this
time.sleep(0.1)
c.sendall(pk.pack(b"R5", 0, 0, 0, 0, 0, 0, 0, 2)[8:])
time.sleep(0.1)
c.close()
time.sleep(0.3)
# silence: a held button must be let go after 1 s
c = socket.create_connection(("127.0.0.1", PORT))
c.sendall(pk.pack(b"R5", 0x8000, 0, 0, 0, 0, 0, 0, 3))
time.sleep(1.5)
c.close()
time.sleep(0.2)
p.terminate()
out = p.stdout.read().splitlines()
print("\n".join(out))
want = ["btn 1001  L -32767  32767  R    100   -100  LT 255 RT   7", "btn 8000"]
ok = want[0] in out and any(l.startswith(want[1]) for l in out) and out[-2].startswith("btn 0000") and sum(l.startswith("btn 0000") for l in out) >= 3 and any("connection lost" in l for l in out)
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)

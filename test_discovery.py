"""test_discovery.py: the server's answer to the app's broadcast (on loopback, so no firewall prompt), and its greeting on connect."""
import socket
import subprocess
import sys
import threading
import time

import pad_server

threading.Thread(target=pad_server.discovery_loop, args=("127.0.0.1", 7981), daemon=True).start()
time.sleep(0.2)
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.settimeout(1)
u.sendto(b"nonsense", ("127.0.0.1", 7981))
u.sendto(b"RP5PAD?", ("127.0.0.1", 7981))
r1 = u.recvfrom(16)[0]
p = subprocess.Popen([sys.executable, "pad_server.py", "--dry", "--port", "7982"], stdout=subprocess.DEVNULL)
time.sleep(1)
c = socket.create_connection(("127.0.0.1", 7982))
c.settimeout(1)
r2 = c.recv(2)
c.close()
p.terminate()
print(r1, r2)
ok = r1 == b"RP5PAD!" and r2 == b"R5"
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)

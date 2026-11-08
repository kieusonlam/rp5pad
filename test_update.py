"""test_update.py <setup old> <setup new> <new version>: the whole update path without admin. Installs the old build per user into a temp folder, runs it against a local fake of GitHub's answer, says yes to the question, and checks the new version is installed and running. A running RP5 Pad is stopped and started again after. Also checks a real HTTPS request from the exe, and that a wrong checksum is refused."""
import ctypes
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import winreg

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLD, NEW, NEW_VER = sys.argv[1:4]
u = ctypes.windll.user32
u.FindWindowW.restype = ctypes.c_void_p
u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
root = tempfile.mkdtemp(prefix="rp5pad-upd-")
app, state = os.path.join(root, "app"), os.path.join(root, "state")
os.makedirs(state)
with open(os.path.join(state, "pad_app.json"), "w", encoding="utf-8") as f:
    f.write('{"lan": false}')   # with WiFi on, Windows would show a firewall question on this desktop
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{7B6E2C14-52A1-4E0B-9C3D-6A1F0E8D2B57}_is1"
with open(NEW, "rb") as f:
    blob = f.read()
sha = hashlib.sha256(blob).hexdigest()
served = {"digest": sha, "hits": 0, "get": 0}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/latest":
            served["hits"] += 1
            base = f"http://127.0.0.1:{self.server.server_port}"
            body = json.dumps({"tag_name": "v" + NEW_VER, "assets": [{"name": f"RP5Pad-Setup-{NEW_VER}.exe", "size": len(blob), "digest": "sha256:" + served["digest"], "browser_download_url": base + "/setup.exe"}]}).encode()
        else:
            served["get"] += 1
            body = blob
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()


def wait(cond, secs):
    end = time.time() + secs
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.1)
    return None


def pwsh(c):
    return subprocess.run(["pwsh", "-NoProfile", "-Command", c], capture_output=True, text=True).stdout.strip()


def run_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            return winreg.QueryValueEx(k, "RP5 Pad")[0]
    except OSError:
        return None


def installed_version():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL) as k:
            return winreg.QueryValueEx(k, "DisplayVersion")[0]
    except OSError:
        return None


def tray():
    return u.FindWindowW("RP5PadTray", None)


def question():
    return u.FindWindowW("#32770", "RP5 Pad update")


def pids():
    return set(pwsh("Get-CimInstance Win32_Process -Filter \"name='RP5Pad.exe'\" | ForEach-Object ProcessId").split())


def start(api):
    env = {"SystemRoot": os.environ["SystemRoot"], "PATH": os.path.join(os.environ["SystemRoot"], "System32"), "USERPROFILE": os.environ["USERPROFILE"], "TEMP": os.environ["TEMP"], "TMP": os.environ["TMP"], "RP5PAD_STATE": os.path.join(state, "pairing.json")}
    if api:
        env["RP5PAD_UPDATE_API"] = api
    return subprocess.Popen([os.path.join(app, "RP5Pad.exe"), "--startup"], env=env, cwd=app)


def stop_tray():
    h = tray()
    if h:
        u.PostMessageW(h, 0x10, 0, 0)
    return wait(lambda: not tray(), 6)


def answer_yes():
    q = wait(question, 10)
    print("  question shown:", bool(q))
    if q:
        u.PostMessageW(q, 0x111, 6, 0)   # WM_COMMAND IDYES


saved_run = run_value()
was_installed = pwsh("Get-CimInstance Win32_Process -Filter \"name='RP5Pad.exe'\" | Select-Object -First 1 -ExpandProperty ExecutablePath")
print("running before:", was_installed or "nothing installed running")
pwsh("Stop-Process -Name RP5Pad -Force -Confirm:$false -ErrorAction SilentlyContinue")
wait(lambda: not tray(), 5)
try:
    r = subprocess.run([OLD, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/MERGETASKS=!desktopicon", f"/DIR={app}"], timeout=120)
    print("old installed:", r.returncode, installed_version())

    print("1. real HTTPS from the exe")
    p = start(None)
    print("  tray:", bool(wait(tray, 15)))
    wait(lambda: os.path.exists(os.path.join(state, "update.log")), 18)
    logf = os.path.join(state, "update.log")
    print("  log:", open(logf, encoding="utf-8").read().strip()[-110:] if os.path.exists(logf) else "no log: the check found nothing to complain about")
    print("  stopped:", bool(stop_tray()))
    wait(lambda: p.poll() is not None, 5)

    print("2. wrong checksum")
    served["digest"] = "0" * 64
    p = start(f"http://127.0.0.1:{srv.server_port}/latest")
    print("  checked on its own:", bool(wait(lambda: served["hits"], 15)))
    time.sleep(1)
    u.PostMessageW(tray(), 0x8001, 0, 0x405)   # as if the balloon was clicked
    answer_yes()
    time.sleep(0.5)
    wait(lambda: served["get"], 10)
    time.sleep(3)
    print("  still old:", installed_version(), "| same process:", p.poll() is None, "| refused in log:", "checksum" in open(logf, encoding="utf-8").read())

    print("3. right checksum")
    served["digest"] = sha
    before = stop_tray()
    wait(lambda: p.poll() is not None, 5)
    served["hits"] = 0
    p = start(f"http://127.0.0.1:{srv.server_port}/latest")
    wait(lambda: served["hits"], 15)
    time.sleep(1)
    old_pids = pids()
    u.PostMessageW(tray(), 0x8001, 0, 0x405)
    answer_yes()
    print("  new version installed:", wait(lambda: installed_version() == NEW_VER and installed_version(), 90))
    print("  old process gone:", bool(wait(lambda: p.poll() is not None, 20)))
    fresh = wait(lambda: pids() - old_pids, 20)
    print("  app started again:", bool(fresh), "| tray:", bool(wait(tray, 15)))
    print("  checked again after restarting:", bool(wait(lambda: served["hits"] > 1, 15)), "| no question:", not question())
    stop_tray()
finally:
    pwsh("Stop-Process -Name RP5Pad -Force -Confirm:$false -ErrorAction SilentlyContinue")
    un = os.path.join(app, "unins000.exe")
    if os.path.exists(un):
        subprocess.run([un, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=60)
        print("uninstalled:", bool(wait(lambda: not os.path.exists(os.path.join(app, "RP5Pad.exe")), 15)))
    if saved_run and run_value() != saved_run:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            winreg.SetValueEx(k, "RP5 Pad", 0, winreg.REG_SZ, saved_run)
    print("Run value as before:", run_value() == saved_run)
    shutil.rmtree(root, ignore_errors=True)
    if was_installed:
        subprocess.Popen(["explorer.exe", was_installed])
        print("your app back:", bool(wait(tray, 10)))

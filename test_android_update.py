"""test_android_update.py build|serve <serial>: the Android update path without GitHub.

build: two test APKs (0.1.1 to install, 0.1.2 to be offered) whose updater asks http://127.0.0.1:8765 instead of GitHub, and the real 0.1.3. Versions only go up, so the device keeps its settings and pairing throughout.
serve: installs test 0.1.1, forwards the device's port 8765 to a fake GitHub on this PC through adb (no firewall rule), starts the app, and waits while a person taps Update, allows installs and confirms. Then reports what is installed."""
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, "dist", "apktest")
PORT = 8765
FAKE = f"http://127.0.0.1:{PORT}"


def build(version, test, out):
    env = dict(os.environ, RP5PAD_APK_VERSION=version, RP5PAD_APK_OUT=out)
    if test:
        app = os.path.join(T, "app-" + version)
        shutil.rmtree(app, ignore_errors=True)
        shutil.copytree(os.path.join(HERE, "app"), app)
        src = os.path.join(app, "src", "org", "nx2a", "rp5pad")

        def patch(path, old, new):
            with open(path, encoding="utf-8") as f:
                s = f.read()
            assert old in s, (path, old)
            with open(path, "w", encoding="utf-8") as f:
                f.write(s.replace(old, new))

        patch(os.path.join(src, "Updater.java"), "https://api.github.com/repos/kieusonlam/rp5pad/releases/latest", FAKE + "/latest")
        patch(os.path.join(src, "UpdateRules.java"), "https://github.com/kieusonlam/rp5pad/releases/download/", FAKE + "/download/")
        patch(os.path.join(app, "AndroidManifest.xml"), "<application ", '<application android:usesCleartextTraffic="true" ')
        env["RP5PAD_APP_DIR"] = app
    subprocess.run([sys.executable, os.path.join(HERE, "build.py")], env=env, check=True)


if sys.argv[1] == "build":
    os.makedirs(T, exist_ok=True)
    build("0.1.1", True, os.path.join(T, "test-0.1.1.apk"))
    build("0.1.2", True, os.path.join(T, "rp5pad-0.1.2.apk"))
    build("0.1.3", False, os.path.join(HERE, "rp5pad.apk"))
    sys.exit()

A = [r"D:\dev\android-sdk\platform-tools\adb.exe", "-s", sys.argv[2]]
offered = os.path.join(T, "rp5pad-0.1.2.apk")
blob = open(offered, "rb").read()
seen = []


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        seen.append(self.path)
        if self.path == "/latest":
            body = json.dumps({"tag_name": "v0.1.2", "assets": [
                {"name": "RP5Pad-Setup-0.1.2.exe", "size": 5, "digest": "sha256:" + "0" * 64, "browser_download_url": FAKE + "/download/setup.exe"},
                {"name": "rp5pad-0.1.2.apk", "size": len(blob), "digest": "sha256:" + hashlib.sha256(blob).hexdigest(), "browser_download_url": FAKE + "/download/v0.1.2/rp5pad-0.1.2.apk"}]}).encode()
        else:
            body = blob
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def version():
    out = subprocess.run(A + ["shell", "dumpsys package org.nx2a.rp5pad | grep -m1 versionName"], capture_output=True, text=True).stdout
    return out.strip().replace("versionName=", "")


srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(subprocess.run(A + ["install", "-r", os.path.join(T, "test-0.1.1.apk")], capture_output=True, text=True).stdout.strip().splitlines()[-1])
print("installed:", version())
subprocess.run(A + ["reverse", f"tcp:{PORT}", f"tcp:{PORT}"], check=True, capture_output=True)
subprocess.run(A + ["shell", "input keyevent KEYCODE_WAKEUP; am start -n org.nx2a.rp5pad/.PadActivity"], capture_output=True)
print("waiting up to 5 minutes for the update to be installed…", flush=True)
end = time.time() + 300
while time.time() < end and version() != "0.1.2":
    time.sleep(2)
print("requests:", seen)
print("installed:", version())
subprocess.run(A + ["reverse", "--remove", f"tcp:{PORT}"], capture_output=True)

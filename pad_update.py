"""pad_update.py: looks for a newer installer in the GitHub releases, downloads it and checks its SHA-256. Only the installed exe uses this, and it installs only after the person says yes.

RP5PAD_UPDATE_API points at another server, for test_update.py."""
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request

import pad_server
from pad_version import VERSION

REPO = "kieusonlam/rp5pad"
API = os.environ.get("RP5PAD_UPDATE_API") or f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOADS = f"https://github.com/{REPO}/releases/download/"
AGENT = f"RP5Pad/{VERSION}"
MAX_SIZE = 200 * 1000 * 1000


class Update:
    def __init__(self, version, url, sha256, size):
        self.version, self.url, self.sha256, self.size = version, url, sha256, size


def parse(tag):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag or "")
    return tuple(int(x) for x in m.groups()) if m else None


def read_release(data):
    """An Update from GitHub's answer, or None when it holds nothing we may install."""
    version = parse(data.get("tag_name"))
    if not version:
        return None
    for a in data.get("assets", []):
        digest = a.get("digest") or ""
        url = a.get("browser_download_url") or ""
        size = a.get("size") or 0
        if not re.fullmatch(r"RP5Pad-Setup-[\d.]+\.exe", a.get("name") or ""):
            continue
        if not digest.startswith("sha256:") or not re.fullmatch(r"[0-9a-f]{64}", digest[7:]):
            return None
        if not url.startswith(DOWNLOADS) and "RP5PAD_UPDATE_API" not in os.environ:
            return None
        if not 0 < size <= MAX_SIZE:
            return None
        return Update(".".join(str(x) for x in version), url, digest[7:], size)
    return None


def fetch(url, timeout):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/vnd.github+json"}), timeout=timeout)


def newer():
    """An Update when a newer version is out, else None. Raises when the check itself fails."""
    with fetch(API, 15) as r:
        u = read_release(json.load(r))
    return u if u and parse(u.version) > parse(VERSION) else None


def download(u):
    """The installer's path, after checking it against the digest GitHub published. Raises otherwise."""
    folder = tempfile.mkdtemp(prefix="rp5pad-update-")
    path = os.path.join(folder, f"RP5Pad-Setup-{u.version}.exe")
    h, total = hashlib.sha256(), 0
    with fetch(u.url, 30) as r, open(path, "wb") as f:
        while chunk := r.read(1 << 16):
            total += len(chunk)
            if total > MAX_SIZE:
                raise ValueError("the download is larger than expected")
            h.update(chunk)
            f.write(chunk)
    if h.hexdigest() != u.sha256:
        os.remove(path)
        raise ValueError("the download does not match its checksum")
    return path


def clean_old_downloads():
    """Installers from earlier updates. One still running holds its file, and goes next time."""
    for d in glob.glob(os.path.join(tempfile.gettempdir(), "rp5pad-update-*")):
        shutil.rmtree(d, ignore_errors=True)


def setup_args():
    """Silent means a progress window and no questions; /restart=1 has installer.iss start the app again. An install outside Program Files is per user: it must stay one, with no admin prompt."""
    programs = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or r"C:\Program Files"
    per_user = not os.path.normcase(sys.executable).startswith(os.path.normcase(programs) + os.sep)
    return "/SILENT /NORESTART /restart=1" + (" /CURRENTUSER" if per_user else "")


def log(text):
    p = os.path.join(os.path.dirname(pad_server.state_path()), "update.log")
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        mode = "w" if os.path.exists(p) and os.path.getsize(p) > 65536 else "a"
        with open(p, mode, encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {VERSION} {text}\n")
    except OSError:
        pass

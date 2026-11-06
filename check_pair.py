"""check_pair.py: the pairing file, and whether each tray process runs inside an MSIX package (where AppData and HKCU writes are redirected). Prints no keys."""
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes as w

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pad_server  # noqa: E402

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype, k.OpenProcess.argtypes = w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]
k.GetPackageFullName.argtypes = [w.HANDLE, ctypes.POINTER(w.UINT), w.LPWSTR]
k.CloseHandle.argtypes = [w.HANDLE]


def package_of(pid):
    h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return "cannot open"
    n = w.UINT(256)
    b = ctypes.create_unicode_buffer(256)
    r = k.GetPackageFullName(h, ctypes.byref(n), b)
    k.CloseHandle(h)
    return "no package" if r == 15700 else b.value if r == 0 else f"error {r}"


p = pad_server.state_path()
print("state file:", p)
try:
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    print("modified", time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p))), "| now", time.strftime("%H:%M:%S"), "| devices", [v["name"] for v in d["devices"].values()])
except (OSError, ValueError) as e:
    print("unreadable:", e)
print("this process:", package_of(os.getpid()))
cmd = "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe'\" | Where-Object CommandLine -match 'pad_tray' | ForEach-Object { $_.ProcessId }"
for pid in subprocess.run(["pwsh", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.split():
    print("tray", pid, package_of(int(pid)))

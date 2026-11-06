"""test_restart.py: after the PC app restarts, a paired device connects again with no question (the key really is on disk)."""
import ctypes
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
restart = "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe'\" | Where-Object CommandLine -match 'pad_tray\\.py' | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction Stop } catch {} }; Start-Sleep 1; explorer.exe (Join-Path ([Environment]::GetFolderPath('Desktop')) 'RP5 Pad.lnk')"
subprocess.run(["pwsh", "-NoProfile", "-Command", restart])
t, asked, up = time.time(), False, False
while time.time() - t < 20 and not up:
    time.sleep(0.5)
    asked = asked or bool(ctypes.windll.user32.FindWindowW("#32770", "RP5 Pad: allow this device?"))
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 7878 -State Established -ErrorAction SilentlyContinue | Measure-Object).Count"], capture_output=True, text=True)
    up = r.stdout.strip() != "0"
print(f"after restart: connected {up} in {time.time() - t:.1f} s, asked again: {asked}")

# RP5 Pad

Use a Retroid Pocket 5 (or another Android handheld with physical controls) as a wired or wireless Xbox 360 controller for a Windows PC. Windows and games see a normal XInput pad, which exists only while the device is connected.

![App on the device](docs/android.png)
![Tester window on the PC](docs/tester.png)

## Install

**PC** (Windows 10/11, 64-bit): run `RP5Pad-Setup-*.exe` and allow the admin prompt. It installs the app, the ViGEmBus driver if it is missing, and a firewall rule for WiFi. Python is bundled. The installer is not code-signed, so Windows SmartScreen warns first: choose *More info*, then *Run anyway*.

The app lives in the tray: left click opens the tester, right click has the settings, including Start with Windows.

To run from source instead: `py -m venv .venv`, `.venv\Scripts\python -m pip install -r requirements.txt`, `.venv\Scripts\pythonw pad_tray.py`.

**Device:** install `rp5pad-*.apk` and open it. It reads the controls only while it is in front with the screen on.

## Connecting

- **USB:** needs `adb` on the PATH and USB debugging on (it is not bundled). The PC app sets up `adb reverse` by itself.
- **WiFi:** on by default in the installed app (from source, tick *Allow WiFi connections* in the tray menu). The app finds the PC by broadcast. The first connection asks you to compare a 6-digit code on both screens and press Yes on the PC.

## Limits

- No rumble.
- Over WiFi, input packets are authenticated at connect time but not encrypted, and the pairing key travels unencrypted during pairing. Pair on a network you trust.
- The APK is signed with a throwaway debug key.

## Building

`python build.py` builds `rp5pad.apk`. It needs Android SDK build-tools 36.1.0, platform 36 and a JDK; set `ANDROID_HOME` and `JAVA_HOME`. `make_installer.py <version>` builds the PC installer (needs PyInstaller, vgamepad and Inno Setup). `make_assets.py` (needs Pillow) regenerates the logo and the tester pictures. The `test_*.py` scripts are manual checks; several drive a real device over adb and need paths adjusted.

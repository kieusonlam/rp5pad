# RP5 Pad: notes for maintenance

The Android app (`app/`) reads the handheld's controls and sends them over TCP 7878. The PC app (`pad_tray.py` + `pad_server.py`) turns them into a virtual Xbox 360 pad through ViGEmBus (`vgamepad`). The README is for users; this file is about what breaks easily.

## Map
| File | Role |
|---|---|
| `pad_server.py` | Connection, pairing, adb reverse, WiFi discovery, the virtual pad (`Pad`, `Pad.settle`) |
| `pad_tray.py` | Tray icon, menu, settings, Start with Windows, update checks |
| `pad_tester.py` | Tester window (Tk, on its own thread) |
| `pad_update.py` | PC updater: GitHub API, checks, download, runs the Setup |
| `pad_version.py` | `VERSION` (PC) and `APK_VERSION` (Android) |
| `app/src/.../PadActivity.java`, `PadView.java` | Device app and its drawing |
| `app/src/.../Updater.java`, `UpdateRules.java` | Android updater; the rules are plain Java so they can be tested on the PC |
| `installer.iss`, `make_installer.py` | Inno Setup installer (PyInstaller onedir inside) |
| `build.py` | APK build with the SDK tools, no Gradle |
| `make_assets.py` | Logo, icons and tester sprites, all drawn from code |

## Contracts that installed copies depend on
Copies already out there cannot be changed, so these must stay compatible.
- **Protocol.** The PC and the device update separately, so a new PC app must work with an old APK, and the other way round. The greeting is `R5U` (USB) or `R5A` + pc id + nonce (WiFi pairing). Packets are `struct "<2sHhhhhBBH"` (`PACKET` in pad_server.py, `fill()` in PadActivity.java). Extend the protocol only in ways the old side ignores.
- **Release asset names.** `RP5Pad-Setup-<x.y.z>.exe` and `rp5pad-<x.y.z>.apk`. Both updaters find the version in these names.
- **Download URL prefix.** `https://github.com/kieusonlam/rp5pad/releases/download/`, in `pad_update.py` and `UpdateRules.java`. Renaming or moving the repo stops updates for every installed copy.
- **Checksums.** Both updaters refuse a file unless it matches the asset's `digest` (`sha256:…`) from the GitHub API, which GitHub fills in itself.
- **Inno `AppId`** `{7B6E2C14-…}` must never change; a new id would install a second copy beside the old one.
- **Signing key.** `debug.keystore` stays local, never in git: back it up. Android only installs an update over a copy signed with the same key. A new key means every user uninstalls first and pairs again.
- **Visibility.** The repo must stay public: the updaters ask GitHub without logging in, and get a 404 if it is private.
- **User data** lives in `~\.rp5pad\` (`pairing.json`, `pad_app.json` for the installed app, `update.log`, `tester.log`). It sits in the home folder and not in AppData, because MSIX redirects AppData. Never print pairing keys.

## Versions and releases
- Bump `VERSION` whenever the PC app changes. Bump `APK_VERSION` **only** when `app/` changes; otherwise every device is asked to update for nothing. `build.py` derives versionCode = major·10000 + minor·100 + patch, and it must only go up.
- The updaters read only GitHub's *latest* release, so every release carries **both** assets. If the APK did not change, attach the previous `rp5pad-<APK_VERSION>.apk` again, the same file.
- Steps: the `release` skill (`.claude/skills/release/SKILL.md`).

## Traps
- **ViGEm stale state:** a new pad that gets all-zero reports can read in XInput as L -3356 -1869 R -3255 -848. `Pad.settle` compares XInput with the report for 5 s and nudges until they match. Keep it; `test_knob.py` checks it.
- **vgamepad in the build venv** is copied in, not pip-installed, because pip can start the driver's setup. PyInstaller needs `--collect-all vgamepad`.
- **Tk:** the tester runs on a thread inside the tray. Closing it hides the window and never destroys it, because Tk cannot start again on a new thread. Other threads never touch widgets: they set a flag (`front`) that the window's own `tick()` picks up.
- **Frozen vs source** (`FROZEN` in pad_tray.py): the installed app keeps its settings in `~\.rp5pad\pad_app.json` with WiFi on by default, and Start with Windows runs the exe. From source, the settings file sits in the folder and WiFi is off. Both use the same HKCU Run value `"RP5 Pad"`, and uninstalling deletes it.
- **Sprites:** use `alpha_composite` with supersampling (see `rrect`). `paste` with a mask makes jagged edges in Tk.
- **The Android app** reads input only while it is in front with the screen on. Opening it pauses a game on the device.
- **Installer:** the normal install needs admin, because it installs the driver msi when the `ViGEmBus` service key is missing and adds the firewall rule "RP5 Pad". `/CURRENTUSER` installs per user with no admin, which tests use. Setup closes a running copy first, and `/restart=1` starts it again.

## Testing
The `test_*.py` scripts are manual checks; each docstring says what it needs. Run the ones that match what changed.
| Changed | Run | Needs |
|---|---|---|
| Protocol, server | `test_protocol.py`, `test_pair.py`, `test_discovery.py` | Python only |
| Virtual pad | `test_knob.py <serial>` | driver |
| Update rules | `test_update_rules.py`; `javac`/`java` on `test_android/RulesTest.java` with `UpdateRules.java` | Python / JDK |
| PC updater | `test_update.py <old setup> <new setup> <ver>` | two builds (`make_installer.py <ver>` for a test version) |
| Installer, frozen app | `test_installed.py <setup> <png>` | Pillow |
| Tester drawing | `test_aa.py <png>`; with a device, `test_tester.py` | Pillow |
| Android updater | `test_android_update.py build`, then `serve <serial>` | device, a person to tap |
| Device end to end | `test_e2e.py`, `test_physical.py <secs> <out>` | device (and a person for physical) |

Only a person can check: the UAC install (driver, firewall), Android's install confirmation, and clicks on the tray balloon. Tests that start the tray stop and restart a running copy; leave the user's own running app as it was.

## Conventions
- Text users see (apps, README, release notes) is English.
- Python 3.13. Files are written as UTF-8, and build scripts take tool paths from environment variables (`ANDROID_HOME`, `JAVA_HOME`, `RP5PAD_BUILD_VENV`, `RP5PAD_PAD_VENV`, `RP5PAD_ISCC`), with this machine's paths as defaults.
- Ask before pushing, creating a release, or changing the repo's settings.
- Not done yet: rumble, encryption over WiFi, a license, code signing.

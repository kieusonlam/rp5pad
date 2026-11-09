---
name: release
description: Release a new RP5 Pad version on GitHub (PC installer and/or APK). Use when asked to release, publish or ship a version.
---

# Releasing RP5 Pad

Ask the user before the push and before creating the release.

1. **Versions** in `pad_version.py`: bump `VERSION` if anything the PC app ships changed, and bump `APK_VERSION` only if `app/` changed. Never lower either one.
2. **Build what changed:**
   - PC: `make_installer.py` (run it with the build venv's Python) → `dist\RP5Pad-Setup-<VERSION>.exe`.
   - APK: `python build.py` → `rp5pad.apk`, released under the name `rp5pad-<APK_VERSION>.apk`. The build must be signed with the local `debug.keystore`; if that file is missing, stop and tell the user rather than letting build.py create a new key.
3. **Test** the parts that changed (the table in CLAUDE.md). For the installer, at least run `test_installed.py <setup> <png>`. Say plainly what only a person can check.
4. **Commit** the source and version change (the message says what changed for users), then push `main`.
5. **Release:** `gh release create v<VERSION> --title "RP5 Pad <VERSION>" --notes-file <notes> --target main <setup.exe> <apk>`.
   - Attach **both** assets every time. If the APK did not change, download the previous release's `rp5pad-<APK_VERSION>.apk` and attach that same file.
   - The notes follow the earlier releases: **Changed** (or **New**), **Files**, **Tested**, **Not tested yet**. Write them in English and keep them short.
6. **Verify:**
   - Download both assets with `gh release download` and compare their SHA-256 with the local files.
   - Check `gh api repos/kieusonlam/rp5pad/releases/latest`: it must show the new tag, both names, and a `digest` for each.
   - Without logging in, `curl https://api.github.com/repos/kieusonlam/rp5pad/releases/latest` must return 200.
7. Tell the user: the link, the hashes matched, what was and was not tested, and that installed copies will offer the update. The PC app checks at start and daily; the device checks when the app opens.

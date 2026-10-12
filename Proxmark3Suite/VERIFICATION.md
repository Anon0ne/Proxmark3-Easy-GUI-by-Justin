# Verification record â€” October 10, 2026

## 0.5 development preview

Emulation update: **48 automated tests pass**. Tests cover slot persistence, retained replaced dumps, corruption rejection, BIN/EML/JSON formats, all four Classic sizes, access-bit warnings, command flags from installed metadata, load cancellation, mismatched read-back, rechecking memory before simulation, workflow locks, workbench simulation tracking and break-command routing.

Physical COM18 read-only checks successfully executed hf mf eview --1k and hf mf esave --1k. The 1024-byte emulator capture matched the prior card backup SHA256 e1f36e54d7e3b5226ab5b43814dbaddfefb5ab49c1762bbb04024df033738540.

The source GUI Emulation panel was also exercised against COM18: a device view matched isolated PC test slot 1, then a fresh capture was saved to isolated test slot 2 with the same hash. An initial Mini/1K default mismatch was found and fixed; the managed tab now defaults to 1K. No hardware load, RF simulation, physical card write, or flash operation was performed. Load/simulation/break behavior has automated verification only.

33 automated tests pass, including operation locking, reconnect during pending information checks, explicit workflow progress, no-card clearing without losing history, communication-failure results and harmless refusal of commands while the session is busy.

Offscreen layouts were inspected at 1280Ã—850 and 980Ã—720. A clipping issue at the smaller size was fixed with a scrollable action panel and minimum button heights. Preview card data is synthetic.

The Windows ZIP was extracted into a separate local folder. Its per-user installer was exercised with a custom local destination and without a Desktop shortcut. The installed bundled EXE passed metadata startup: exit 0, 989 commands, no serial access. This does not verify clean-machine installation, default AppData installation, or physical recovery.

The package includes the Python/Qt runtime required by the GUI. It does not bundle the external Iceman client, firmware or toolchain. The official release remains 0.3b.

## Beta 0.3b

**27 automated tests pass**, including card classification, annotated UID parsing, compact fact extraction, command validation, consent decline, information checks, saved-card persistence, UID change cancellation, recovery confirmation, timeout restoration and progress formatting. The Cards-first layout was rendered offscreen and visually inspected without overlapping controls. The beta EXE metadata-only startup smoke test checks exit 0 and 989 commands without serial access. These checks do not represent physical recovery testing.

Earlier physical checks identified a Gen 1a Fudan card and produced two matching 1024-byte authenticated backups. No successful physical autopwn recovery, card write or firmware flash is claimed. The previous 0.1b prerelease is retained.

## Completed

- Installed Python environment: Python 3.12.10, PySide6 Essentials 6.12.0, PyInstaller 6.22.3. Reduced dependency footprint after the full Qt bundle encountered temporary-space exhaustion.
- Parsed the actual local Iceman client's full command documentation: 989 commands, 3,716 options. Exact metadata fixture: `client-help.txt`.
- **15 automated checks pass**, covering command/option parsing, unsupported option preservation, injection/truncation rejection, command and firmware confirmation cancellation, disconnected execution, GUI forms, compatibility mismatch locking, corrupted settings recovery, Generic build flags, artifact hashing and normal no-card results. Final source syntax checks also passed.
- Persistent offline client transactions completed without spawning a separate client for each command.
- Physical device accessed successfully on **COM18** through `C:\rrg_other\client\proxmark3.exe`, resolved from the requested batch launcher.
- `hw version`: client, bootrom and OS reported `Iceman/master/v4.21611-636-gda509461b-suspect`; model **PM3 GENERIC**, processor **AT91SAM7S512**, internal flash **512 KB**.
- `hw status` completed. `hw ping` returned valid contents (12 ms in the first run; 10 ms in the identification run).
- Real `lf search` and `hf search` transactions completed. **No card was identified during this test.** No card decryption, key recovery or card writing was performed.
- Actual source GUI integration completed installed-client discovery, COM18 connection, diagnostics and compatibility unlocking: 989 commands; compatibility matched.
- GUI rendered and visually inspected using Windows fonts. Screenshot: `gui-preview.png` (offline preview, not a live device screenshot).
- Installer completed with Python already installed: environment/dependency checks, tests, Windows EXE build and Desktop shortcut creation. Shortcut points to `dist\Proxmark3Suite.exe`.
- Final packaged EXE passed its metadata-only smoke test: exit code 0, 989 commands, matching client revision, no serial access. Result: `exe-smoke/result.json`. A host ICU DLL incorrectly bundled during the first build caused a Qt import failure; `build_exe.py` now isolates the build PATH and the corrected archive contains no unrelated ICU files.
- Final packaged EXE also passed its explicit read-only **COM18 hardware smoke test**: exit code 0, 989 commands, successful persistent connection, hardware diagnostics and compatibility match. Result: `exe-hardware-smoke/result.json`.
- A profile-free ProxSpace prerequisite check found make, GCC and Git, but no `arm-none-eabi-gcc` on the checked PATH. The configured toolchain needs its ARM compiler before firmware compilation can succeed. ProxSpace's login profile unexpectedly reinstalled existing packages during the initial check; the check's login shells were stopped, and firmware builds now use `--noprofile --norc` to avoid that profile.

Read-only device transcript: `hardware-verification.txt`. GUI compatibility transcript: `gui-integration/result.txt`.

## Boundaries

- The firmware workflow is implemented, but downloading/building the latest RRG firmware and actual firmware flashing have **not** been exercised end to end. Device firmware was not changed. Bootloader flashing is not provided.
- Python-missing winget installation path is implemented but not tested on a machine without Python.
- The catalog describes the installed client, not a promise that all commands are supported by this board's compiled capabilities. Complex positional parameters and mutually exclusive options require review against exact help; no card secrets or unsupported defaults are invented.
- Periodic presentation detection is implemented. The test exercised one LF/HF search cycle, not extended soak testing or successful identification/decryption of a presented card.
- EXE is unsigned. No clean-machine installation or 256 KB device test was performed.

Event-log/Help update: 23 unit tests passed, including split ANSI chunks and carriage-return spinner output. Help topics are embedded in the EXE. Physical card backup: two independent authenticated 1024-byte dumps matched SHA256 e1f36e54d7e3b5226ab5b43814dbaddfefb5ab49c1762bbb04024df033738540. Magic backdoor backup failed twice; standard reads succeeded with retries. No lab writes performed.

## 0.5b packaging verification — October 12, 2026

- 48 automated tests passed. Original SVG icon rendered to seven ICO sizes (16–256 px); Qt loaded the icon and PE inspection confirmed EXE icon resources.
- Windows EXE built with PyInstaller 6.22.3 using the isolated build PATH. Metadata-only packaged startup exited 0 and discovered 989 commands from the installed target client. No serial access occurred in this release packaging check.
- Inno Setup 6.7.3 compiler downloaded from its official release; Authenticode signature validated as Pyrsys B.V. The per-user Setup.exe compiled successfully and installed on this host with exit code 0.
- Installed EXE hash matched the build. Installed startup exited 0 and discovered 989 commands. Desktop shortcut targets `%LOCALAPPDATA%\Programs\Proxmark3EasyGUI\Proxmark3Suite.exe` and uses its embedded icon. Windows uninstall registration was checked. This verifies installation on this existing development host, not on a clean machine.
- Prior read-only hardware verification remains applicable to its documented scope. No card writes, physical recovery, emulator load/RF simulation or firmware flashing were performed for this packaging release.
- Obsolete generated build directories were removed after installation verification. Private backups, card data, logs and the Marauder reference were preserved.

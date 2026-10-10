# Proxmark3 Easy GUI - by Justin · 0.1b

First public beta release of the Windows Engineering Suite workbench, built from the v0.1.0 scaffold. MarauderGUI was a visual reference only; no Marauder command/backend code is used or distributed with this repository.

## Launch

Run `run_windows.bat`, or the Desktop shortcut after installation. The defaults are `C:\rrg_other\pm3.bat`, COM18, Iceman/RRG `v4.21611-636-gda509461b`, PM3 GENERIC / Easy. The batch path is resolved to its sibling `client/proxmark3.exe`; the suite supplies the DLL/plugin environment and explicit COM port without invoking the launcher's unconditional `pause`.

For a fresh installation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1
```

The installer checks Python 3.10+, uses winget to install Python 3.12 if missing, creates a virtual environment, installs Qt Essentials and PyInstaller, runs tests, builds a windowed EXE and creates a Desktop shortcut. If winget is unavailable, it reports how to install Python. Native command failures stop installation. `-NoShortcut` skips shortcut creation. The EXE bundles Python/Qt; the Proxmark client and its runtime remain external.

Dependency versions are pinned to the verified build. `build_exe.py` isolates the DLL search PATH so unrelated developer runtimes do not contaminate the EXE. Windows 10/11 is required by the selected Qt runtime.

## Workbench

- A persistent client owns the connection. Commands are serialized; a unique upstream `rem` marker fences each response in pipe mode. Stop terminates the session and requires reconnection. It cannot undo already-sent device/card changes.
- The complete installed-client `--fulltext` help is parsed dynamically. This installation supplies 989 commands and 3,716 option definitions. The cache is for browsing only until refreshed against the selected client.
- Search names and descriptions; navigate groups or double-click a command. Controls use the documented flags, with checkboxes for switches, value fields for placeholders and dropdowns when syntax explicitly enumerates choices. Required values, complex positional syntax and combinations must be reviewed against the exact usage/examples. No keys, passwords or card-specific values are guessed. Advanced input preserves firmware syntax.
- Preview/copy the exact command; keep favorites and command history. Ctrl+K focuses search; Ctrl+Enter runs the selected command. Live output is bounded, exportable and recorded in rotating local logs.
- A conservative allowlist exempts only exact `hw version`, `hw status`, `hw ping`, `lf search` and `hf search` lines from confirmation. All other operations require an explicit review, including writes, resets, scripts and recovery commands. Multiple commands, control characters and pipe-reader overflow are blocked.
- Hardware diagnostics compare the client revision, the device OS revision and PM3 GENERIC model with the selected target. Unverified/mismatched device workflows stay locked; offline tools remain accessible. The client itself still decides whether a command is supported by the device's compiled capabilities. Catalog presence is not a guarantee of hardware capability.
- Card identification runs read-only LF/HF searches once or periodically while idle. Results are raw client evidence. Universal automatic decryption is not implemented; card technology and authorized keys determine possible reading/decryption. Recovery commands remain visible in the catalog and require manual review.

Settings use Windows QSettings. Runtime caches, firmware workspaces and logs use Qt's per-user AppLocalDataLocation. Logs/history can contain identifiers, keys and arguments; handle exported files accordingly.

## Firmware workspace

Choose `latest` or an upstream tag/branch, and select a configured ProxSpace `msys2` directory. Git must be available on PATH. Each download creates a fresh RRG checkout and records its exact commit. It builds `PLATFORM=PM3GENERIC`, `LED_ORDER=PM3EASY` for 512 KB, records SHA256 hashes, then verifies that the built client's revision matches the source commit.

The install action requires a live, recently inspected PM3 GENERIC / AT91SAM7S512 device and explicit confirmation of port, commit and image hash. Hashes are checked again. It flashes **fullimage only**, without force or bootloader unlock flags. The existing bootloader must support this procedure. Failed flashing does not switch the selected client. On a confirmed upstream success result, the suite selects the matching built client/runtime, refreshes its command metadata and reconnects to verify compatibility. Retain the original launcher and prior checkout for recovery. Do not interrupt a firmware update; the window prevents closing while a firmware operation is active.

This build profile does not support 256 KB boards or additional hardware features. ProxSpace installation, automatic bootloader updates and signed binary distribution are outside this release.

Upstream references:

- [Windows / ProxSpace installation](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/md/Installation_Instructions/Windows-Installation-Instructions.md)
- [Platform build configuration](https://github.com/RfidResearchGroup/proxmark3/blob/master/Makefile.platform.sample)
- [Compilation parameters](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/md/Use_of_Proxmark/4_Advanced-compilation-parameters.md)

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe verify_session.py
.\.venv\Scripts\python.exe verify_session.py --hardware
.\.venv\Scripts\python.exe verify_session.py --hardware --identify
.\.venv\Scripts\python.exe verify_gui_hardware.py
```

Hardware probes are opt-in and read-only. `client-help.txt` is the local client's captured metadata fixture; `hardware-verification.txt` records real read-only device access. See `VERIFICATION.md` for what was actually checked and outstanding limitations.

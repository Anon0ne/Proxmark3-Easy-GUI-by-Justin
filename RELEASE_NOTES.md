# 0.6b — Windows and Linux beta

This release adds a Card Data workspace and easier connection setup. Windows Setup/EXE and a native Linux x86_64 package are available as release assets.

## New features

- Classic Mini/1K/2K/4K sector/block inspection, decoded access permissions and invalid-access-bit warnings.
- Local hex drafts, undo, original/draft hashes, same-size dump comparison and export to a separate BIN/EML file. Original backups and saved slots are preserved.
- Inspect saved Emulation slots directly in Card Data. BIN/DUMP/EML and supported Classic JSON import.
- Standard-location Iceman client discovery and port selection assistance.
- Native Linux executable/serial-device handling and isolation from bundled Qt libraries when launching the external client.
- Prioritized Future Features list informed by community GUI research.

## Installation

Windows: run Proxmark3-Easy-GUI-0.6b-Setup.exe, or use the portable ZIP/EXE. Linux: extract the Linux x86_64 tar.gz and launch Proxmark3Suite; install.sh optionally adds a per-user application-menu launcher. A compatible external Iceman client is required on both platforms.

## Verification and limits

54 automated tests passed on Windows and Ubuntu 24.04. Packaged self-tests verified GUI startup, the icon, Card Data tab and 989-command fixture on both platforms, without serial access. Windows installed-client discovery and installer checks are recorded in VERIFICATION.md. Linux installer verification uses an isolated CI home with spaces in its path.

Earlier Windows COM18 read-only hardware results do not establish Linux hardware compatibility. No new physical card writes, successful recovery, emulator load/RF interaction or firmware flashing is claimed. Linux hardware access, other distributions/architectures and clean-machine Windows installation remain unverified. GUI firmware build/flashing currently supports Windows ProxSpace only and is disabled with an explanation on Linux. Assets are unsigned.

The data editor is local-only. Guided physical reads/writes, per-sector recovery results, NDEF editing, broader LF workflows and graph tools remain Future Features. Previous beta releases remain available.

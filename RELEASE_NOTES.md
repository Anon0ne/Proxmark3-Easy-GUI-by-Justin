# 0.5b — Windows beta

A guided card workflow now presents identification, information checks and separately confirmed recovery. The Emulation tab manages sixteen persistent PC slots and the device’s single emulator buffer, with integrity checks and explicit load/simulation approvals.

## Included

- Original NFC card icon embedded in the application, EXE, Setup installer and shortcuts.
- Per-user Windows Setup installer with Desktop/Start menu shortcuts, stable upgrade location and uninstall support. Python is bundled; the external Iceman client is required.
- Persistent client, searchable firmware-derived command forms, console, readable logs and operation locks.
- Activity bar, elapsed time, compact card facts, saved observations and top Help menu.
- Slot import/export, recovered-dump saving, read-only emulator inspection/capture, confirmed load with readback, separately confirmed simulation and stop control.
- Latest/tag firmware workspace with matching client selection and guarded flashing.

## Verification and limits

48 automated tests pass. See VERIFICATION.md for installer and packaged startup checks.
Earlier physical COM18 testing verified PM3 GENERIC / 512 KB with matching target firmware, card identification and two matching authenticated backups. Read-only device emulator viewing/capture and matching captures to PC slots were verified. No successful physical autopwn recovery, card writing, device emulator loading, RF simulation/reader interaction or firmware flashing is claimed.

The EXE and installer are unsigned. Clean-machine installation, Python-missing source setup and latest firmware compilation/flashing remain unverified. This is a beta release. Previous releases remain available on GitHub. Private captures, logs, card dumps, reference UI and build toolchain are excluded.

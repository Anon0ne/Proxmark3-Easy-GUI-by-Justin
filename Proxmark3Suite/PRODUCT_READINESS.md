# Product readiness and GUI parity

Audit: October 12, 2026. Baseline: published 0.6b plus explicitly identified unreleased source fixes. This document defines what must be completed before claiming comprehensive guided-feature coverage or comparative superiority.

## Current assessment

The app has usable identification, command access, Classic recovery consent, saved observations, local dump editing and a PC emulation library. Windows installation and Ubuntu packaging/startup have verification. That does not establish complete guided-device workflows, successful recovery for every supported card, or better performance than another GUI.

An installed-client command appearing in the workbench counts as **advanced command access**, not as an implemented guided feature. Automated tests, source implementation, packaged startup and physical verification are separate evidence levels.

| Area | Implemented | Remaining requirement |
| --- | --- | --- |
| Setup and connection | Windows/Linux packages, client discovery, serial selection, persistent session, compatibility checks | Clean-machine Windows setup, Linux physical device connection, reconnect/cable-loss soak tests and clearer permission/driver guidance |
| Firmware command coverage | Installed-client catalog, exact help, argument forms, manual preview, favorites/history | Version-change regression fixtures, capability-aware workflows and explicit handling of complex argument combinations |
| Card identification | Read-only LF/HF search, current facts, saved observations, information consent | LF identities in saved-card history and technology-specific guided inspection; no universal-decryption claim |
| Classic data tools | Mini/1K/2K/4K inspection, access permissions, drafts, undo, comparison and export | Value-block decoding, selected-block read capture with completeness metadata |
| Recovery | Classic detection, information checks, separate autopwn approval, UID recheck, timeout and dump-to-slot offer | Per-sector key/result display, dictionary selection, partial/failure reports and successful controlled hardware recovery validation |
| Physical writing/restoration | Firmware commands exposed with confirmation | Guided changed-block plan, verified backup, target/type/generation checks, separate trailer/block-zero review and byte-by-byte readback |
| Emulation | PC slot integrity, capture, inspection, confirmed load/readback, separately approved simulation and stop | Actual device load and authorized reader interaction validation; confirm stop under disconnect/failure |
| LF workflows | Search and firmware command access | Guided common-protocol reads, identity display, T5577 suitability/protection checks and separately approved verified writes/emulation |
| Type 2 / NDEF | Firmware command access | Decoded read view, capacity/protection checks, editable Text/URI records and confirmed verified writes |
| Diagnostics | Hardware version/status/ping and compatibility | Antenna measurements with evidence-based explanations, plots and sanitized diagnostic reports |
| Data preservation | Atomic slot/history/draft writes, hash checks, original-dump preservation | Single-instance/concurrent-store protection, data-folder/backup management, restore tests and privacy controls |
| UX | Guided Cards, operation locks, elapsed activity, Help, keyboard command shortcuts | End-to-end usability benchmarks, keyboard/accessibility pass and clear distinction between failure, partial result and success |

## Core completion gates

1. **Read and preserve:** a selected-block read records which blocks were read, which failed, the explicit keys used and device/client provenance. Unknown blocks never become fabricated recovered data. A backup can be reopened and compared without altering its source.
2. **Recover and explain:** every sector has a known/unknown key/result state; dictionary input is validated; failures remain visible; the same card is checked before execution. Recovery success requires evidence, not an exit status or complete file size alone.
3. **Write and verify:** a concrete preview identifies source, target and changed blocks. Backup and compatibility gates precede explicit approval. Failure or cancellation never appears as success. Physical development writes require separate approval for the actual operation.
4. **Emulate and stop:** a controlled saved dump matches device readback and is observed by an authorized test reader. Stop, disconnect and restart handling are tested; killing the host client is not treated as proof RF stopped.
5. **Install and retain:** new users can install, select a compatible client and connect without source builds. Upgrades retain settings/history/slots. Corrupt stores are preserved and concurrent app instances cannot overwrite each other's data.
6. **Report and support:** operation reports separate verified, partial and failed results and support sharing without exposing private keys/dumps by default. Errors explain the next action.

Selected reads, verified restore/writes, recovery results and reliable backup/report management are core gaps, not cosmetic wishlist items. NDEF/LF workflows and graphs are required for broader guided-feature parity; optional appearance changes and remote/mobile operation come afterward.

## How to establish that we outperform another GUI

Run the same controlled tasks on the same hardware, firmware/client pair and disposable test cards. Record completed tasks, user actions, time, errors, recovery from failure and data integrity. Review task clarity with a new user. Test competitor programs directly before making comparative claims.

Benchmark tasks: first connection; no-card search; identify and reopen saved facts; read selected blocks; collect a verified backup; inspect access permissions; compare/edit/export a dump; review partial recovery; restore and verify a disposable target; load/emulate/stop; unplug/reconnect during a read; upgrade while retaining saved data.

Pass criteria: task completion with documented evidence, zero silent data loss, no unapproved writes, accurate partial/failure reporting and supported syntax only. Lower task time or fewer actions count only when the same outcome and safeguards are achieved. No speed or reliability superiority is currently proven.

## Source hardening after 0.6b

The audit found that malformed saved-card history could be silently discarded and replaced by a later observation. The source now preserves the unreadable file, retains new observations only in the current session, explains the problem, and blocks history persistence until repair. Two regression tests cover malformed JSON and invalid record schemas. This is an unreleased source fix; the published 0.6b assets and installed Desktop EXE do not yet include it.

See [feature comparison](FEATURE_PARITY.md), [Future Features](FUTURE_FEATURES.md) and [verification record](VERIFICATION.md). Reference-project documentation was reviewed; their binaries were not benchmarked here.

## 0.7 development work

Guided selected-block reads and per-block double-read verification are now implemented in source, with partial/private reports and an all-block binary export gate. Per-sector recovery results are displayed from the actual client key-table format. These workflows have synthetic automated coverage and remain unverified on physical cards. Dictionary selection, per-sector credentials, shareable redacted reports and guarded physical writes remain core work. Published 0.6b assets are unchanged.

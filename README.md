# Proxmark3 Easy GUI - by Justin

**Current beta: 0.3b.** A Windows desktop workbench for Proxmark3 Easy using the Iceman/RRG client. The application's window is titled Proxmark3 Engineering Suite.

Cards is the starting screen: identify a card, approve information checks, then separately review Auto Recovery. Advanced commands, console, connection settings and firmware updates have dedicated tabs. See [research and controlled test-card plan](Proxmark3Suite/AUTO_RECOVERY.md).

![Command workbench preview](Proxmark3Suite/gui-preview.png)

## Start

Download `Proxmark3Suite.exe` from the GitHub release, or build from source:

```powershell
cd Proxmark3Suite
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1
```

The source installer checks Python, installs missing Python dependencies, runs tests, builds the EXE, and creates a Desktop shortcut. An existing compatible Iceman/RRG Windows client is required. Defaults: `C:\rrg_other\pm3.bat`, COM18, PM3 GENERIC / Easy and Iceman revision `v4.21611-636-gda509461b`.

## Features

- Persistent client connection and live console with rotating logs and export.
- Searchable command tree generated from the installed client's exact help: 989 commands and 3,716 options in the verified target build.
- Argument controls, exact command previews, help, examples, favorites, command history and keyboard shortcuts.
- Hardware diagnostics and firmware compatibility checks before device workflows.
- Read-only LF/HF identification, including periodic searching while idle.
- Explicit confirmation for unreviewed operations, card writes, scripts and potentially destructive commands.
- Firmware workspace supporting latest or named upstream revisions, recorded commits, Generic builds and guarded fullimage installation.

## Verified and limited

27 automated tests pass. Earlier physical COM18 checks verified PM3 GENERIC / 512 KB with matching client/OS `v4.21611-636-gda509461b-suspect`. A Gen 1a Fudan card was identified, and two authenticated 1024-byte backups matched. Backdoor reads failed twice; authenticated reads succeeded with retries. The 0.3b layout and recovery flow have automated verification; no successful physical autopwn recovery, card writing or firmware flashing is claimed.

The latest firmware build/flash workflow has not been tested end to end. It requires a configured ProxSpace toolchain with the ARM cross-compiler. The Python-missing installer path and clean-machine installation also remain untested. The EXE is unsigned. Recovery is offered for identified Classic cards with explicit consent; success depends on the card, keys and communication.

See [usage and firmware instructions](Proxmark3Suite/README.md), [verification record](Proxmark3Suite/VERIFICATION.md), and [release notes](RELEASE_NOTES.md).

The Marauder UI reference, virtual environments, diagnostic executables, raw device logs and local build artifacts are excluded from Git. Release binaries and the source archive are distributed as release assets.

Copyright Justin. A redistribution license has not yet been selected. The client-help fixture originates from Iceman/RRG Proxmark3; upstream materials retain their applicable notices and license.

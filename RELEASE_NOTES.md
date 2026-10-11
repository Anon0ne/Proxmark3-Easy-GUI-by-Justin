# 0.3b — Windows beta

The main screen now follows one card workflow: identify, collect information, then review recovery. Connection settings, the command workbench, hardware diagnostics, firmware updates and the console have dedicated tabs. Card activity details are hidden until requested.

## Included

- Persistent Windows Iceman client with firmware compatibility gates.
- Searchable firmware-native catalog and argument forms; the verified target exposes 989 commands.
- Compact current-card facts and persistent local saved-card history.
- Confirmed read-only UID and Classic information checks before a separate autopwn confirmation.
- Readable terminal progress lines, log export and top Help menu.
- Latest/tag firmware workspace with guarded flashing and matching client selection.
- Source installer checks Python, installs dependencies, runs tests, builds an EXE and creates a shortcut.

## Verification and limits

27 automated tests pass. The beta EXE startup and installed-client catalog are checked without serial access.

Earlier physical COM18 testing verified matching target firmware, PM3 GENERIC / 512 KB, a Gen 1a Fudan card and two identical 1024-byte authenticated backups. Backdoor reads failed twice; authenticated reads succeeded with retries. The revised GUI workflow has not been exercised end to end on hardware. No successful physical autopwn recovery, card writes or firmware flashing is claimed.

Latest firmware compilation/flashing, Python-missing installation and clean-machine installation remain unverified. The EXE is unsigned and requires a compatible external Iceman client. Recovery may fail or be partial; review output and saved files.

The previously published 0.1b prerelease is retained.

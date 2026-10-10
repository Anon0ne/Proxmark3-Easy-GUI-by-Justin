# 0.1b — first public beta

Public release version 0.1b identifies the Engineering Suite work developed locally as v0.2.0. This is a prerelease, with known verification gaps documented below.

## Included

- Dark Windows command workbench inspired visually by the Marauder V8 GUI.
- Persistent Iceman client backend with serialized transactions, live output, command timeout selection and interruption confirmation.
- Dynamic installed-client command/help discovery and metadata-driven parameter controls.
- Favorites, history, search, command copy/preview and log export.
- COM18 defaults, PM3 GENERIC compatibility gating and read-only hardware/card workflows.
- Latest/tag firmware source builds with commit/hash recording, matching-client selection and explicitly confirmed fullimage flashing.
- Python/dependency checks, isolated Windows EXE build and Desktop shortcut installer.
- Fix for QtCore startup failure caused by accidentally bundling an unrelated host ICU DLL.

## Validation

15 automated tests passed. Source syntax checks, installer execution with existing Python, packaged startup/catalog discovery, and packaged read-only COM18 compatibility checks passed. The physical device reports matching client/OS revision `v4.21611-636-gda509461b-suspect`, PM3 GENERIC and 512 KB flash. LF/HF searches completed without identifying a card.

## Known gaps

- Latest firmware downloading/compilation/flashing has not been verified end to end; a configured ARM cross-compiler is required.
- No successful card identification, decryption, key recovery or card writes were tested. Automatic decryption is not implemented.
- Complex positional syntax and mutually exclusive options need review against exact client help.
- Clean-machine installation, Python-missing winget installation, EXE signing and 256 KB boards are not verified.

The release EXE requires a compatible external Iceman/RRG client. It does not bundle third-party firmware or flash anything automatically.

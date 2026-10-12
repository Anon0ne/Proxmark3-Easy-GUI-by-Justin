# Future Features

Research date: October 12, 2026. This is a prioritized backlog, not a list of features shipped in the current EXE. Order reflects user benefit, existing gaps and required hardware verification; no release dates are promised.

## Implemented for 0.6b

- Card Data sector/block inspector for Classic Mini/1K/2K/4K dumps, local hex drafts, undo and export to a different file.
- Decoded access conditions, invalid-complement detection, readable-Key-B authentication handling and manufacturer-block distinction.
- Comparison of same-size dumps with changed-block indicators and original/draft hashes.
- Inspect a saved Emulation slot in Card Data without modifying its stored dump.
- Standard-location client discovery and port refresh; platform-specific Linux executable and serial-device handling.
- Windows installer and native Linux package build pipeline. See the release verification record for actual build/test outcomes.

## Next priorities

The High-priority items below are core completion work, not optional enhancements. [Product readiness](PRODUCT_READINESS.md) defines their acceptance gates and the evidence required for comparative claims.

| Priority | Feature | User benefit and release requirement |
| --- | --- | --- |
| High | Guided selected-block reads | 0.7 source implements selected blocks/ranges with one supplied key and double-read verification; physical validation and per-sector keys remain. Save completeness metadata rather than zero-filling unknown data and calling it recovered. |
| High | Recovery results by sector | 0.7 source displays reported Key A/Key B and unknown sectors after recovery; live stage interpretation and dictionary selection remain. Add dictionary selection only when supported by discovered help. Do not invent a percentage or ETA. |
| High | Guarded restore/write wizard | Inspect target type/generation, validate source/backup, show exact changed blocks, recheck identity, request explicit approval and verify readback. Trailer and manufacturer-block changes need separate review. |
| High | Backup and operation reports | Keep provenance, firmware/client version, completeness, hashes and verification results. Export a shareable report with private data redacted by default. |
| Medium | Type 2 / NDEF reader and editor | Decode Text/URI records and unknown record payloads; show capacity, lock/protection status. Begin read-only; later writes preserve unrelated TLVs and require backups and readback. |
| Medium | Guided LF workflows | Protocol-specific identity inspection and target suitability, including T5577 when detected. Keep recovery, writing and simulation separately approved. |
| Medium | Antenna diagnostics and graphs | Explain measured evidence; integrate native client plots or documented sample formats. Avoid arbitrary pass/fail thresholds. |
| Medium | Broader client discovery and setup diagnostics | User-selected search folder, USB/driver/permission troubleshooting and a tested client acquisition route with matching firmware/capability checks. Do not silently change firmware. |
| Later | Appearance and accessibility | Light/dark preferences, font scaling, persistent splitter layouts and keyboard/screen-reader validation. |
| Later | Additional platforms and remote UI | ARM/Linux distributions, native Linux firmware-build UI and optional authenticated remote operation require separate validation. |

## Reference projects and useful ideas

These are documentation/source-description comparisons. None of the reference binaries was installed or tested here, and their hardware claims have not been independently verified.

- [wh201906/Proxmark3GUI](https://github.com/wh201906/Proxmark3GUI): selected-block operations, Classic data editing and access-bit analysis motivated the Card Data work and guided-read/write backlog.
- [Phosphor](https://github.com/nikitaart2000/phosphor): staged card/target workflows, magic-generation detection, blank-content checks and recovery-stage feedback inform target validation and progress design. Our confirmation boundaries remain explicit.
- [Bambu RFID Writer](https://github.com/Dandy357/bambu-rfid-writer): NDEF decoding/editing, source/target validation, changed-page writes and structured reports are useful general-purpose ideas. Specialized material libraries and keys are outside this project's scope.
- [PM3UniversalGUI](https://github.com/burma69/PM3UniversalGUI): dynamic help navigation largely overlaps our existing command catalog; its documented parsing limitations reinforce preserving raw help and manual syntax review.
- [Phreak87/Proxmark3_GUI](https://github.com/Phreak87/Proxmark3_GUI): dynamically generated command tree, Markdown help and process state overlap existing functionality; graph-frame integration is a future investigation.
- [Gaucho-GUI](https://github.com/Proxmark/Gaucho-GUI), described by the [upstream GUI wiki](https://github.com/Proxmark/proxmark3/wiki/Windows-proxmark-client-gui): configurable task buttons are useful as curated workflows. We retain live metadata instead of relying on old static command definitions.
- [AndProx](https://github.com/AndProx/AndProx): mobile connection guidance and compatibility documentation are useful references; Android development is not a near-term Windows/Linux feature. The project documents maintenance and functionality limits.
- [proxmark3-web](https://github.com/videoman/proxmark3-web): a browser interface is an architectural reference, not a priority over the desktop workflow. Remote device access would need a separate design and approval model.
- [Proxmark3.app](https://proxmark3.app/): discovered, but the website did not expose readable content to the research tool. No feature claims or parity conclusions are based on it.

## Design rules for future builds

Use a shared Card Data view for saved dumps and read results. Add capabilities inside existing workflows where possible rather than creating competing panels. Preserve firmware-native command syntax and distinguish available client commands from board capability. Keep original backups immutable, label incomplete results, and require explicit confirmation for writes/destructive actions.

Research informs an original implementation; no reference-project code or assets were copied. Any future reuse requires checking its license and attribution requirements. Feature inspiration does not establish Linux/Windows hardware compatibility.

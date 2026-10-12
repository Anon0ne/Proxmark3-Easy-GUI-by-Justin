# GUI feature comparison — October 12, 2026

This compares documented features, not hands-on testing of the reference GUI.
The likely reference is [wh201906/Proxmark3GUI](https://github.com/wh201906/Proxmark3GUI).
[ProxSpace](https://github.com/Gator96100/ProxSpace) supplies the Windows build environment; it is a separate project.
If a different GUI is intended, its feature list must be reviewed separately.

| Reference feature | Current 0.6b coverage | Work still needed |
| --- | --- | --- |
| Serial-port selection | Registry-based port discovery and connection settings | Standard-location client discovery added; broader driver/permission troubleshooting remains |
| Raw client commands | Persistent console and dynamically discovered command workbench | Preserve these alongside guided workflows |
| Classic Mini/1K/2K/4K | Managed dump library and emulator controls | Structured sector/block view shared by physical reads and saved dumps |
| Block editing | Local draft edits, hex validation, undo and comparison | Guided physical writes remain separate |
| Read all/selected blocks | Available client commands and manual argument forms | Guided selection, explicit key inputs, per-block results and partial-read handling |
| Write all/selected blocks | Client commands with general confirmation | Exact write plan, backup validation, card identity recheck, separate trailer/block-zero approval and readback verification |
| Binary/text dumps | BIN, EML and supported MFC JSON import/export | .dump binary compatibility added and tested |
| Access-bit analysis | Human-readable permissions, complement validation and readable-Key-B handling | Hardware validation of broader generation-specific behavior |
| Magic-card support | Reported capabilities, hints and firmware commands | Generation-specific guided actions based on actual client help and detected evidence |
| LF shortcuts | Read-only LF search and all discovered LF commands | Protocol-specific read/inspect workflows; write/emulation actions only when supported and explicitly approved |
| UI customization | Existing consistent theme and resizable interface | Optional appearance preferences without adding competing task panels |

## Implementation order

1. Implemented for 0.6b — local Card Data inspector/editor: sectors, blocks, decoded access permissions, import/export, draft edits and comparison. Keep original dump files immutable. This can be tested without modifying a physical card.
2. Add guided physical reads with selected blocks, caller-supplied keys, per-block outcomes and cancellation. Never label incomplete data as a complete backup.
3. Add guarded physical writes using a concrete preview of changed blocks, explicit confirmation, current-card checks and verification. Implementing the feature does not authorize executing writes during development.
4. Add evidence-based magic-card actions and LF protocol workflows. Each action must derive syntax from the selected client's metadata and distinguish client command availability from hardware capability.
5. Refine client discovery and first-run diagnostics, then validate workflows on hardware with separately approved operations.

Use one Card Data view for saved dumps and read results rather than duplicating editors across Cards and Emulation. Keep the existing guided Cards flow, PC slot library and advanced command workbench. The full reference feature set is a development target, not a claim of current parity.

Broader GUI research and remaining priorities are in [Future Features](FUTURE_FEATURES.md).

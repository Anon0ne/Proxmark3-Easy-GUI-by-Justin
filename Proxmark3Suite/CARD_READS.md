# Guided Classic reads — 0.7 development preview

These features are in current source, not the published 0.6b assets.

1. Connect & verify and identify the intended MIFARE Classic card.
2. Open **Card Data → Read from card** and select its detected size.
3. Enter block numbers/ranges (`0-3,8,12`) or `*` for all blocks. Supply Key A or B as exactly 12 hexadecimal characters. No key is guessed or substituted.
4. Select **Review & read selected blocks** and approve the displayed UID, size, selection and read-only operation.
5. The workflow checks the UID before each read and reads every block twice. Only identical, unambiguous results are marked verified. Failed and unread blocks remain explicit. Other device workflows stay locked.
6. **Cancel remaining reads** waits for the current read/check and prevents further blocks. Disconnect/client failure interrupts the capture. The console's normal timeout still applies.
7. **Export read report…** writes a private JSON report with requested blocks, outcomes, card UID, client/device provenance and timestamps. An independently reread complete-card capture also produces a BIN file and SHA256; the written file is checked against the captured bytes. Partial captures never create a zero-filled fake dump.

The same supplied key is used for all selected sectors in this first version. Different sector keys require separate captures; a per-sector credential table is future work. A read does not establish that hidden trailer keys were recovered. Key A may be masked by the device, and readable Key B cannot authenticate that sector. Exported captures may not be suitable for restoration without recovered keys and additional validation. UID checking alone cannot distinguish two different cards sharing the same UID.

Reports contain private data. They omit the supplied credential value, but raw Console/session logs contain the executed command including its key. A shareable redacted operation-report workflow is still planned.

## Recovery results

After a guided Classic autopwn command, **Card Data → Recovery results** shows each sector's Key A and Key B as reported found or unknown. It parses the final installed-client key table and preserves unresolved sectors. The result count describes reported keys, not complete card-data recovery or a verified backup. No additional recovery command or card write is triggered by this view.

## Verification

Synthetic tests cover command metadata, selection validation, correct-block parsing, errors/ambiguous output, approval cancellation, card changes, double-read mismatch, cancellation, operation locking, partial/full export and final recovery-table parsing. Command/output formats were checked against the local target client's help and RRG source. Physical guided reads, successful recovery and these new hardware workflows have not been tested in this development preview.

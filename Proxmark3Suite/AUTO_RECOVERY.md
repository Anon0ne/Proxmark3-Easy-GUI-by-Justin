# Auto Recovery development workflow

The new card-identification option offers a consent-based recovery effort for an unambiguous MIFARE Classic / Mini result with a single UID. Unsupported families and ambiguous output do not trigger it. Repeated scans of the same card do not repeatedly prompt; an HF absence/new identity or reconnection resets the presentation state. The manual Review button can retry a declined effort.

Flow: read-only LF/HF search → classify Classic size and UID → show the exact firmware-supported autopwn command and its effects → explicit Yes/No confirmation → read-only `hf 14a reader` UID recheck → run the approved recovery command only if the UID still matches. UID equality is a continuity check, not proof that a card cannot have been replaced by another card with the same UID.

The selected client's own `hf mf autopwn` help is authoritative. For the current target it documents key checks and darkside/nested/hardnested/staticnested selection, followed by a dump attempt if all keys are found. The GUI does not independently script that attack sequence or guess unsupported flags. It derives the Classic size switch and documented default dictionary from installed metadata. Autopwn can write local key/dump files and device emulator memory; the GUI does not queue card-writing, restoration or cloning commands.

Periodic scanning stops before verification/recovery. A recovery effort uses a 30-minute timeout and restores the previous timeout afterward. Stop/disconnection cancels the pending approval. Raw output remains authoritative: command completion is not represented as successful decryption. Card-dependent failures and partial results are expected.

## Primary references consulted

- [RRG cheat sheet — MIFARE flows](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/cheatsheet.md)
- [RRG command implementation — autopwn](https://github.com/RfidResearchGroup/proxmark3/blob/master/client/src/cmdhfmf.c)
- [RRG ISO14443-A identification implementation](https://github.com/RfidResearchGroup/proxmark3/blob/master/client/src/cmdhf14a.c)
- Local target client's `--fulltext` fixture: `client-help.txt`.

Upstream master evolves. Its cheat sheet currently includes syntax that differs from this installed client, including suffix/slow options; those are not copied blindly into the GUI.

## Controlled test-card plan

1. Start with owned blank MIFARE Classic 1K cards whose keys and intended data are known. Prove detection, consent cancellation and default-key recovery/readback first. This validates the application path; it does not demonstrate recovery against hardened non-default keys.
2. Use an explicitly rewritable UID / Gen1a Classic-compatible lab card for UID experiments. Genuine NXP Classic manufacturer blocks are read-only. Check the exact generation before selecting a write command, back up first and review the full affected data before every write. Do not infer write support from the displayed Classic family alone.
3. Give lab cards distinguishable test UIDs and known content. Verify changed-card cancellation, successful readback, recovered-file handling, removal/reinsertion, timeout, interruption and reconnect behavior.
4. Test a hardened Classic EV1 and unsupported NTAG/DESFire cards as negative cases. A failed recovery is a valid result; unsupported technologies should not receive the Classic autopwn prompt.
5. Keep UID writes and sector-key/access-bit setup separate from recovery. Keep original keys/backups for each lab card; incorrect trailer settings can make sectors unusable. No test-card write has been performed by this change.

Candidate lab supplies (availability and generation should be rechecked before purchase):

- [Lab401 Classic 1K 4-byte compatible Gen1 blank](https://lab401.com/products/mifare-classic-1k-4-byte-compatible)
- [Dangerous Things test-card pack](https://dangerousthings.com/products/card-pack) for several technologies and negative tests.
- [NXP Classic EV1 1K datasheet](https://www.nxp.com/docs/en/data-sheet/MF1S50YYX_V1.pdf) for genuine-card layout and manufacturer-block restrictions.

## Verification boundary

Automated tests use synthetic reader output to check classification, exact documented commands, single confirmation, UID change cancellation, timeout restoration and prompt suppression. No successful physical card recovery or UID write has been verified. The existing public v0.1b release predates this development change.

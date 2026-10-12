# Emulation and saved slots

The Emulation tab manages **16 PC slots**, numbered 01–16. These are application storage entries, not hardware banks. The device exposes current emulator memory; loading another dump replaces that buffer. Saved PC slots survive application restarts, and a verified device association is cleared after disconnecting or commands that can alter emulator memory.

## Supported managed dumps

MIFARE Classic Mini, 1K, 2K and 4K, in BIN, EML or Iceman MFC JSON format. Other card technologies retain their firmware commands in the workbench; this slot manager does not guess their incompatible dump formats.

- Select a slot, import a dump, and give it a name.
- Slot details describe its provenance, size, hash and access-bit warnings. Slot data displays every block.
- Rename, export or clear a slot. Replacing/clearing an occupied slot asks for confirmation and retains the previous content-addressed dump file.
- Invalid sizes, incomplete JSON/EML blocks, changed hashes and corrupted indexes are rejected. Invalid access-bit complements are shown and block loading.
- A complete file with valid access bits does **not** prove successful recovery of every key or data block.

The index is stored in emulation/slots.json under the application data directory. Canonical binary dumps are stored in emulation/dumps. These files can contain keys and card data.

## Current device memory

Choose the buffer format explicitly. The default is Classic 1K; selecting a format does not detect the card size.

**Read device memory** downloads all blocks of the selected format using hf mf eview. A complete read is hashed and compared with all saved slots. The Device inspector shows the returned bytes.

**Save device memory to selected slot** uses hf mf esave, verifies the resulting file size, and asks for a slot name/replacement if required.

**Load selected slot & verify** asks permission before hf mf eload. It then downloads the buffer with hf mf esave and compares every byte by SHA256. Simulation remains blocked when read-back differs.

**Review simulation** asks permission to simulate on an authorized test reader. It reads and compares the buffer again, then runs hf mf sim with the documented card size. No reader-attack flags are added. Starting the command does not verify successful interaction with a reader.

**Stop simulation** sends the installed client's hw break. Other workflows are locked while simulation is tracked. If the client disconnects while RF simulation is running, press the physical PM3 button to stop it; killing the Windows process does not prove that RF stopped.

All generated options must exist in the selected client's discovered help. The managed workflow does not use SPIFFS, --mem, card writes or bootloader commands.

## Recovery to a slot

After autopwn, the GUI checks reported binary dump files for complete size, valid access-bit complements and matching four-byte UID when applicable. It offers to save the file to a chosen PC slot; the same action remains available in Emulation. Saving the file does not reload or simulate the device.

## Hardware distinction and sources

RRG documents a separate HF_MFCSIM standalone mode with up to 15 flash-backed slots. It requires flash memory and a dedicated firmware build. This GUI does not assume that feature is available on a Generic Easy merely because commands appear in help. Some Easy variants can have external SPI flash; capability must be verified before offering flash-backed storage.

- [RRG command documentation](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/commands.md)
- [RRG command cheat sheet](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/cheatsheet.md)
- [RRG standalone HF_MFCSIM](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/standalone/hf_mfcsim.md)
- [RRG Classic emulator implementation](https://github.com/RfidResearchGroup/proxmark3/blob/master/client/src/cmdhfmf.c)

The installed target's client-help.txt and local source verify exact eload, esave, eview, sim and hw break syntax.

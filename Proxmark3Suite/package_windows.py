"""Build a runnable Windows package from the verified bundled GUI executable."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys
from app import VERSION

root = Path(__file__).resolve().parent
exe = root/(sys.argv[1] if len(sys.argv)>1 else 'dist-0.5b')/'Proxmark3Suite.exe'
target = root.parent/f'Proxmark3-Easy-GUI-{VERSION}-Windows.zip'
readme = """Proxmark3 Engineering Suite — 0.5b beta

1. Extract the entire archive into a folder.
2. Run Proxmark3Suite.exe or Start.bat. Python is not required.
3. Connect the reader. Use Connection settings to select the existing Iceman
   pm3.bat/client executable and COM port; then Connect & verify.
4. Identify a card. Approve read-only information checks, then separately
   decide whether to attempt recovery.
5. Use Emulation to save recovered dumps into PC slots, inspect or capture
   device memory, and review loading or simulation separately.

Defaults: C:\\rrg_other\\pm3.bat, COM18, PM3 GENERIC / Easy,
Iceman v4.21611-636-gda509461b.

Optional: double-click Install.bat to install for the current user and create
a Desktop shortcut. No administrator rights needed.
The source installer is separate and requires Python to build the EXE.

This package includes GUI dependencies, but not the external Iceman client,
firmware or toolchain. Choose a compatible installed client in Settings.
The EXE is unsigned. Firmware flashing and physical recovery remain unverified
end to end. Physical emulator loading and RF simulation remain unverified.
"""
with ZipFile(target,'w',ZIP_DEFLATED) as archive:
    archive.write(exe,'Proxmark3Suite.exe')
    archive.write(root/'install_app.ps1','Install.ps1')
    archive.writestr('Install.bat','@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1"\r\npause\r\n')
    archive.writestr('Start.bat','@echo off\r\nstart "" "%~dp0Proxmark3Suite.exe"\r\n')
    archive.writestr('README.txt',readme)
    archive.writestr('SHA256SUMS.txt',sha256(exe.read_bytes()).hexdigest()+'  Proxmark3Suite.exe\n')
print(target)

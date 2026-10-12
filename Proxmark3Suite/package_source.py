"""Package source and its test fixture; exclude environment/build/reference data."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from app import VERSION
root = Path(__file__).resolve().parent
files = ['app.py','card_data.py','LINUX.md','install_linux.sh','package_linux.py','FEATURE_PARITY.md','FUTURE_FEATURES.md','tests/test_card_data.py','backend.py','catalog.py','eventlog.py','launch_support.py','recovery.py','emulation.py','firmware.py','build_exe.py','build_icon.py','installer.iss','INSTALLATION.txt','assets/app-icon.svg','assets/app-icon.png','assets/app-icon.ico','install_windows.ps1','install_app.ps1','package_windows.py',
         'run_windows.bat','requirements.txt','README.md','VERIFICATION.md','client-help.txt',
         'verify_session.py','verify_gui_hardware.py','verify_emulation_gui.py','preview_gui.py','package_source.py',
         'gui-preview.png','gui-card-preview.png','gui-emulation-preview.png','tests/test_suite.py','tests/test_eventlog.py','tests/test_emulation.py','AUTO_RECOVERY.md','EMULATION.md']
target = root.parent/f'Proxmark3-Easy-GUI-{VERSION}-source.zip'
with ZipFile(target,'w',ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root/name,'Proxmark3Suite/'+name)
    for name in ['README.md','RELEASE_NOTES.md','.gitignore']:
        archive.write(root.parent/name,name)
print(target)

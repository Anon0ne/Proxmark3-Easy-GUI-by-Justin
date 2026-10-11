"""Package source and its test fixture; exclude environment/build/reference data."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
root = Path(__file__).resolve().parent
files = ['app.py','backend.py','catalog.py','eventlog.py','recovery.py','firmware.py','build_exe.py','install_windows.ps1',
         'run_windows.bat','requirements.txt','README.md','VERIFICATION.md','client-help.txt',
         'verify_session.py','verify_gui_hardware.py','preview_gui.py','package_source.py',
         'gui-preview.png','tests/test_suite.py','tests/test_eventlog.py','AUTO_RECOVERY.md']
target = root.parent/'Proxmark3-Easy-GUI-0.3b-source.zip'
with ZipFile(target,'w',ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root/name,'Proxmark3Suite/'+name)
    for name in ['README.md','RELEASE_NOTES.md','.gitignore']:
        archive.write(root.parent/name,name)
print(target)

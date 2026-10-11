"""Build without collecting unrelated DLLs from the host's developer PATH."""
import os
from pathlib import Path
import sys
import PyInstaller.__main__

root = Path(__file__).resolve().parent
os.chdir(root)
windows = Path(os.environ.get('SystemRoot',r'C:\Windows'))
os.environ['PATH'] = os.pathsep.join(map(str,[Path(sys.executable).parent,Path(sys.base_prefix),windows/'System32',windows]))
for key in ['QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_PLATFORM']:
    os.environ.pop(key,None)
output = root / (sys.argv[1] if len(sys.argv) > 1 else 'dist')
PyInstaller.__main__.run(['--noconfirm','--clean','--onefile','--windowed','--name','Proxmark3Suite',
    '--distpath',str(output),'--workpath',str(root/'build'),'--specpath',str(root),str(root/'app.py')])

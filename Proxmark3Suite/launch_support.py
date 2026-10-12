"""Platform setup helpers with no optional Python dependencies."""
import sys
import shutil
from pathlib import Path
from glob import glob

def client_candidates():
    candidates = ([r'C:\rrg_other\pm3.bat',shutil.which('proxmark3.exe')] if sys.platform == 'win32'
                  else [shutil.which('proxmark3'),'/usr/local/bin/proxmark3','/usr/bin/proxmark3'])
    if sys.platform == 'win32':
        candidates += glob(str(Path.home()/'Downloads/ProxSpace*/pm3/proxmark3/client/proxmark3.exe'))
    return list(dict.fromkeys(str(Path(p)) for p in candidates if p and Path(p).is_file()))

def default_client():
    return next(iter(client_candidates()),r'C:\rrg_other\pm3.bat' if sys.platform == 'win32' else 'proxmark3')

def default_port():
    return 'COM18' if sys.platform == 'win32' else next(iter(serial_ports()),'/dev/ttyACM0')

def serial_ports():
    if sys.platform != 'win32':
        return sorted(set(glob('/dev/serial/by-id/*') + glob('/dev/ttyACM*') + glob('/dev/ttyUSB*')))
    try:
        import winreg
        ports = set()
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DEVICEMAP\SERIALCOMM') as key:
            index = 0
            while True:
                try:
                    _, value, _ = winreg.EnumValue(key,index)
                    if isinstance(value,str) and value.upper().startswith('COM'): ports.add(value.upper())
                    index += 1
                except OSError: break
        return sorted(ports,key=lambda port:int(port[3:]) if port[3:].isdigit() else 9999)
    except (ImportError,OSError):
        return []

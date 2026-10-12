"""Windows setup helpers with no optional Python dependencies."""

def serial_ports():
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

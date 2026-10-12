"""Explicit read-only COM18 panel verification; never load or simulate."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
from pathlib import Path
import sys
from unittest.mock import patch
from PySide6.QtCore import QTimer,QSettings
from PySide6.QtWidgets import QApplication,QInputDialog
from app import Window

if '--hardware' not in sys.argv:
    raise SystemExit('Pass --hardware to read COM18 and capture emulator memory into local test slots.')
root = Path(__file__).resolve().parent
app = QApplication(sys.argv)
data = root/'emulation-gui-smoke'
window = Window(data,QSettings(str(data/'settings.ini'),QSettings.IniFormat))
window.launcher.setText(r'C:\rrg_other\pm3.bat')
window.emulation.library.save(1,root/'lab-device-emulator-capture.bin','Earlier device snapshot')
window.emulation.library.clear(2)
window.emulation.refresh()
stage = 0
timer = QTimer(); timer.setInterval(100)
def check():
    global stage
    if stage == 0 and window.catalog_verified and window.client_version:
        stage = 1; window.connect_client()
    elif stage == 1 and window.compatible and window.session.ready and not window.queue:
        stage = 2; window.emulation.view()
    elif stage == 2 and window.session.ready and not window.emulation.pending:
        if not window.emulation.active: app.exit(1); return
        stage = 3
        window.emulation.table.setCurrentItem(window.emulation.table.topLevelItem(1))
        window.emulation.capture()
    elif stage == 3 and window.session.ready and not window.emulation.pending:
        first = window.emulation.library.slots['1']; second = window.emulation.library.slots.get('2')
        if not second or first['sha256'] != second['sha256']: app.exit(1); return
        (data/'result.json').write_text(json.dumps({'serial_access':True,'read_matching_slot':1,'captured_to_slot':2,'bytes':second['bytes'],'sha256':second['sha256'],'load_executed':False,'simulation_executed':False},indent=2),encoding='utf-8')
        timer.stop(); window.close(); app.quit()
timer.timeout.connect(check); timer.start()
QTimer.singleShot(45000,lambda: app.exit(1))
with patch.object(QInputDialog,'getText',return_value=('Read-only device snapshot',True)):
    code = app.exec()
window.close()
raise SystemExit(code)

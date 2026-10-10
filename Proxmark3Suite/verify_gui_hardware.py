"""Verify the GUI's real discovery -> connection -> compatibility flow."""
import sys
from pathlib import Path
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtWidgets import QApplication
from app import Window
root = Path(__file__).parent; data = root/'gui-integration'; data.mkdir(exist_ok=True)
app = QApplication([])
window = Window(data,QSettings(str(data/'settings.ini'),QSettings.IniFormat))
window.launcher.setText(r'C:\rrg_other\pm3.bat'); window.port.setCurrentText('COM18')
timer = QTimer(); timer.setInterval(100)
connected = False
def check():
    global connected
    if not connected and window.catalog_verified and window.client_version:
        connected = True; window.connect_client()
    if connected and window.compatible and window.session.ready and not window.queue:
        print('GUI VERIFIED:',len(window.commands),'commands; compatibility matched; COM18 diagnostics completed',flush=True)
        (data/'result.txt').write_text(window.hardware_output.toPlainText(),encoding='utf-8')
        timer.stop(); window.close(); app.quit()
timer.timeout.connect(check); timer.start()
QTimer.singleShot(35000,lambda: app.exit(1))
code = app.exec(); window.close(); sys.exit(code)

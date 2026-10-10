"""Render a repeatable GUI preview with installed-client metadata; no device IO."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from PySide6.QtCore import QSettings,Qt
from PySide6.QtWidgets import QApplication,QTreeWidgetItem
from PySide6.QtGui import QFontDatabase
from app import Window
from catalog import parse_dump
app = QApplication([]); app.setStyle('Fusion')
for font in ['segoeui.ttf','consola.ttf']:
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
root = Path(__file__).parent
data = root/'preview-data'; data.mkdir(exist_ok=True)
window = Window(data,QSettings(str(data/'settings.ini'),QSettings.IniFormat),auto_discover=False)
window.commands = parse_dump((root/'client-help.txt').read_text(encoding='utf-8-sig'))
window.catalog_verified = True; window.populate()
window.catalog_label.setText(f'{len(window.commands)} commands · installed client')
window.search.setText('hf mf rdbl')
def find(parent):
    for i in range(parent.childCount()):
        item = parent.child(i)
        if item.data(0,Qt.UserRole) == 'hf mf rdbl': return item
        found = find(item)
        if found: return found
item = find(window.tree.invisibleRootItem())
window.tree.setCurrentItem(item)
window.console.setPlainText('Offline UI preview — metadata from the locally installed Iceman/RRG client.\nConnect to COM18 to verify live hardware compatibility.')
window.show(); app.processEvents()
window.grab().save(str(root/'gui-preview.png'))
window.close()

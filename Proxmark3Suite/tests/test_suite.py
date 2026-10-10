import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog import parse_dump,build_command,needs_confirmation,validate_line
from backend import resolve_client,Session
from PySide6.QtCore import QSettings,QProcess
from PySide6.QtWidgets import QApplication,QMessageBox,QTreeWidgetItem
from app import Window,TARGET
from app import saved_list
from firmware import build_script,digest

ROOT = Path(__file__).resolve().parents[1]
app = QApplication.instance() or QApplication([])

class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = parse_dump((ROOT/'client-help.txt').read_text(encoding='utf-8-sig'))

    def test_full_client_catalog(self):
        self.assertEqual(len(self.catalog),989)
        self.assertIn('hf mf rdbl',self.catalog)
        self.assertIn('lf search',self.catalog)

    def test_exact_parameter_types(self):
        options = {o.flag:o for o in self.catalog['hf mf rdbl'].options}
        self.assertEqual(options['--blk'].value,'<dec>')
        self.assertEqual(options['--key'].value,'<hex>')
        self.assertNotIn('--sector',options)
        self.assertEqual(build_command('hf mf rdbl',[(options['--blk'],'3'),(options['--key'],'A0A1A2A3A4A5')]),'hf mf rdbl --blk "3" --key "A0A1A2A3A4A5"')

    def test_gates_are_fail_closed(self):
        for line in ['hf mf wrbl --blk 0','lf t55xx wipe','script run arbitrary','hw reset','hf mf darkside','hw version --anything']:
            self.assertTrue(needs_confirmation(line))
        self.assertFalse(needs_confirmation('hf search'))
        self.assertFalse(needs_confirmation('lf search'))

    def test_separators_and_truncation_blocked(self):
        for line in ['hf search; hf mf wrbl','hf search\nhw reset','hw version\x1b','x'*251,'']:
            with self.assertRaises(ValueError): validate_line(line)

    def test_no_metadata_does_not_invent_commands(self):
        with self.assertRaises(ValueError): parse_dump('unrecognized client output')

    def test_build_targets_generic_and_does_not_flash(self):
        script = build_script(Path(r'C:\safe path\firmware'))
        self.assertIn("cd '/c/safe path/firmware'",script)
        self.assertIn('PLATFORM=PM3GENERIC',script)
        self.assertNotIn('--flash',script)
        self.assertNotIn('PM3RDV4',script)

    def test_hash_detects_modified_artifact(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'fullimage.elf'; path.write_bytes(b'one'); first = digest(path)
            path.write_bytes(b'two'); self.assertNotEqual(first,digest(path))

    def test_corrupt_settings_recover(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            settings = QSettings(str(Path(folder)/'settings.ini'),QSettings.IniFormat)
            settings.setValue('favorites','invalid json')
            self.assertEqual(saved_list(settings,'favorites'),[])
            settings.setValue('favorites','["hf search",2]')
            self.assertEqual(saved_list(settings,'favorites'),['hf search'])
            settings.sync()

    def test_supported_launcher(self):
        if Path(r'C:\rrg_other\pm3.bat').exists():
            self.assertEqual(resolve_client(r'C:\rrg_other\pm3.bat'),r'C:\rrg_other\client\proxmark3.exe')

class UiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.window = Window(self.temp.name,QSettings(str(Path(self.temp.name)/'settings.ini'),QSettings.IniFormat),auto_discover=False)
        self.window.commands = CatalogTests.catalog if hasattr(CatalogTests,'catalog') else parse_dump((ROOT/'client-help.txt').read_text(encoding='utf-8-sig'))
        self.window.catalog_verified = True
        self.window.populate()

    def tearDown(self):
        self.window.close(); self.window.deleteLater(); app.processEvents()
        self.temp.cleanup()

    def test_compatibility_requires_device_os_and_board(self):
        self.window.client_version = 'Client: Iceman/master/'+TARGET+'-suspect'
        self.window.device_version = 'Firmware.................. PM3 GENERIC\nOS......... Iceman/master/'+TARGET+'-suspect'
        self.window.check_compatibility(); self.assertTrue(self.window.compatible)
        self.window.device_version = 'Client: '+TARGET+'\nFirmware PM3 GENERIC\nOS......... v4.1-1-g123456'
        self.window.check_compatibility(); self.assertFalse(self.window.compatible)
        self.window.device_version = 'Firmware PM3 RDV4\nOS......... '+TARGET
        self.window.check_compatibility(); self.assertFalse(self.window.compatible)

    def test_forms_generated_from_metadata(self):
        item = QTreeWidgetItem(self.window.tree,['rdbl']); item.setData(0,0x100,'hf mf rdbl')
        self.window.tree.setCurrentItem(item); self.window.select()
        self.assertEqual(len(self.window.fields),6)
        self.assertIn('hf mf rdbl',self.window.preview.text())
        self.assertIn('key, 6 hex bytes',self.window.help.toPlainText())

    def test_confirmation_cancel_does_not_send(self):
        self.window.session_path = self.window.launcher.text(); self.window.session_port = self.window.port.currentText(); self.window.session_offline = False
        self.window.compatible = True
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No), patch.object(self.window.session,'send') as send:
            self.window.dispatch('hf mf wrbl --blk 0')
            send.assert_not_called()

    def test_disconnected_session_refuses_commands(self):
        with self.assertRaises(ValueError): self.window.session.send('hw version')

    def test_firmware_cancel_never_starts_flash(self):
        client = Path(self.temp.name)/'client.exe'; image = Path(self.temp.name)/'fullimage.elf'
        client.write_bytes(b'client'); image.write_bytes(b'firmware')
        self.window.firmware.staged = {'client':str(client),'image':str(image),'client_sha256':digest(client),'image_sha256':digest(image),'commit':'a'*40}
        self.window.device_version = 'Firmware PM3 GENERIC\nuC AT91SAM7S512'
        self.window.session.ready = True; self.window.session_port = self.window.port.currentText(); self.window.session_offline = False
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No),patch.object(self.window.firmware,'run') as run:
            self.window.firmware.flash(); run.assert_not_called()
        self.assertFalse(self.window.firmware.busy)

    def test_no_card_is_a_normal_search_result(self):
        self.window.result('hf search','[!] No known/supported 13.56 MHz tags found')
        self.assertEqual(self.window.statusBar().currentMessage(),'Search completed: no supported card detected.')

if __name__ == '__main__': unittest.main()

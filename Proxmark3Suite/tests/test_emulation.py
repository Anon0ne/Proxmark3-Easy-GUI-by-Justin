import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QSettings
from app import Window,TARGET
from catalog import parse_dump
from emulation import SlotLibrary,inspect_dump,emulator_command,read_view_bytes,SIZES
from recovery import ClassicCard

ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])

def fixture(size='1k'):
    data = bytearray(SIZES[size])
    data[:16] = bytes.fromhex('12345678080804000000000000000000')
    for block in range(len(data)//16):
        if block < 128 and block%4 == 3 or block >= 128 and (block-128)%16 == 15:
            data[block*16:(block+1)*16] = bytes.fromhex('FFFFFFFFFFFFFF078069FFFFFFFFFFFF')
    return bytes(data)

class SlotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        self.dump = self.root/'card.bin'; self.dump.write_bytes(fixture())
        self.library = SlotLibrary(self.root/'library')

    def tearDown(self): self.temp.cleanup()

    def test_slots_persist_and_replacement_retains_old_dump(self):
        original = self.library.save(1,self.dump,'First')
        changed = bytearray(fixture()); changed[64] = 42; self.dump.write_bytes(changed)
        self.library.save(1,self.dump,'Second')
        reloaded = SlotLibrary(self.library.root)
        self.assertEqual(reloaded.slots['1']['name'],'Second')
        self.assertTrue(reloaded.file(original).exists())
        reloaded.clear(1); self.assertEqual(reloaded.slots,{})
        self.assertTrue(reloaded.file(original).exists())
        with self.assertRaises(ValueError): reloaded.save(17,self.dump,'Invalid')

    def test_dump_formats_and_sizes(self):
        for size in SIZES:
            self.dump.write_bytes(fixture(size))
            _,meta = inspect_dump(self.dump)
            self.assertEqual(meta['size'],size); self.assertEqual(meta['warnings'],[])
        self.dump.write_bytes(fixture())
        eml = self.root/'card.eml'; eml.write_text('\n'.join(fixture()[i:i+16].hex() for i in range(0,1024,16)))
        js = self.root/'card.json'; js.write_text(json.dumps({'FileType':'mfc v2','Card':{'UID':'12345678'},'blocks':{str(i):fixture()[i*16:(i+1)*16].hex() for i in range(64)}}))
        self.assertEqual(inspect_dump(eml)[0],fixture())
        self.assertEqual(inspect_dump(js)[0],fixture())
        self.assertEqual(inspect_dump(js)[1]['uid_source'],'JSON metadata')

    def test_incomplete_dump_and_corruption_rejected(self):
        self.dump.write_bytes(b'\xff'*192)
        with self.assertRaises(ValueError): inspect_dump(self.dump)
        self.dump.write_bytes(fixture()); record = self.library.save(1,self.dump,'Original')
        file = self.library.file(record)
        altered = bytearray(fixture()); altered[16] = 1; file.write_bytes(altered)
        with self.assertRaises(ValueError): self.library.verified(record)

    def test_invalid_access_bits_are_visible(self):
        altered = bytearray(fixture()); altered[54] = 0; self.dump.write_bytes(altered)
        self.assertTrue(inspect_dump(self.dump)[1]['warnings'])

    def test_emulator_view_requires_all_blocks(self):
        text = '\n'.join('[=] | '+str(block)+' | '+fixture()[block*16:(block+1)*16].hex(' ')+' | ....' for block in range(64))
        self.assertEqual(read_view_bytes(text,'1k'),fixture())
        with self.assertRaises(ValueError): read_view_bytes(text,'4k')

    def test_corrupt_index_preserved(self):
        self.library.path.write_text('broken json')
        reloaded = SlotLibrary(self.library.root)
        self.assertIsNotNone(reloaded.error)
        with self.assertRaises(ValueError): reloaded.save(1,self.dump,'New')
        self.assertEqual(self.library.path.read_text(),'broken json')

class EmulationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        self.window = Window(self.root,QSettings(str(self.root/'settings.ini'),QSettings.IniFormat),False)
        self.window.commands = parse_dump((ROOT/'client-help.txt').read_text(encoding='utf-8-sig'))
        self.window.catalog_verified = True; self.window.compatible = True; self.window.session.ready = True
        self.window.client_version = 'Client '+TARGET
        self.window.device_version = 'Firmware PM3 GENERIC\nOS......... '+TARGET
        self.window.session_path = self.window.launcher.text(); self.window.session_port = self.window.port.currentText(); self.window.session_offline = False
        self.panel = self.window.emulation
        self.dump = self.root/'card.bin'; self.dump.write_bytes(fixture())
        self.record = self.panel.library.save(1,self.dump,'Lab')
        self.panel.refresh()

    def tearDown(self):
        self.panel.invalidate(); self.window.session.ready = False
        self.window.close(); self.window.deleteLater(); APP.processEvents()
        self.temp.cleanup()

    def test_only_installed_flags_used(self):
        command = emulator_command(self.window.commands,'load','1k','emulation/dump.bin')
        self.assertEqual(command,'hf mf eload --1k --file "emulation/dump.bin"')
        self.assertEqual(emulator_command(self.window.commands,'simulate','4k'),'hf mf sim --4k')
        self.assertEqual(emulator_command(self.window.commands,'simulate','1k',uid='04112233445566'),'hf mf sim --1k --uid 04112233445566')
        with self.assertRaises(ValueError): emulator_command({},'load','1k','x.bin')
        with self.assertRaises(ValueError): emulator_command(self.window.commands,'simulate','8k')

    def test_load_decline_does_not_send(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No),patch.object(self.window.session,'send') as send:
            self.panel.load(); send.assert_not_called()
        self.assertIsNone(self.panel.pending)

    def test_load_requires_matching_device_readback(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(self.window.session,'send') as send:
            self.panel.load(); self.assertTrue(send.call_args.args[0].startswith('hf mf eload'))
            self.window.result(send.call_args.args[0],'[=] Done!\n')
            self.assertTrue(send.call_args.args[0].startswith('hf mf esave'))
            self.panel.pending['context']['path'].write_bytes(fixture())
            self.window.result(send.call_args.args[0],'[+] Saved 1024 bytes to binary file\n')
        self.assertEqual(self.panel.active['sha256'],self.record['sha256'])
        self.assertTrue(self.panel.buttons['simulate'].isEnabled())

    def test_mismatched_readback_blocks_simulation(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(self.window.session,'send') as send:
            self.panel.load(); self.window.result(send.call_args.args[0],'Done!\n')
            altered = bytearray(fixture()); altered[64] = 1
            self.panel.pending['context']['path'].write_bytes(altered)
            self.window.result(send.call_args.args[0],'Saved\n')
        self.assertIsNone(self.panel.active)
        self.assertIn('differs',self.panel.status.text())

    def test_simulation_checks_memory_again_and_stops(self):
        self.panel.active = dict(self.record,slot=1)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(self.window.session,'send') as send:
            self.panel.simulate()
            self.assertTrue(send.call_args.args[0].startswith('hf mf esave'))
            self.panel.pending['context']['path'].write_bytes(fixture())
            self.window.result(send.call_args.args[0],'Saved\n')
            self.assertEqual(send.call_args.args[0],'hf mf sim --1k')
            self.window.result('hf mf sim --1k','[=] Press pm3 button or send another cmd to abort simulation\n')
            self.assertTrue(self.panel.simulating)
            count = send.call_count; self.window.dispatch('hf search')
            self.assertEqual(send.call_count,count)
            self.panel.stop_simulation(); self.assertEqual(send.call_args.args[0],'hw break')
            self.window.result('hw break','')
            self.assertFalse(self.panel.simulating)

    def test_busy_card_workflow_refuses_emulator_load(self):
        self.window.pending_info = ClassicCard('12345678','1k')
        with patch.object(self.window.session,'send') as send:
            self.panel.load(); send.assert_not_called()

    def test_recovery_file_can_be_offered_without_hardware_load(self):
        self.panel.offer_recovered(f'[+] Saved 1024 bytes to binary file `{self.dump}`\n',ClassicCard('12345678','1k'))
        self.assertEqual(self.panel.recovered,self.dump)
        self.assertTrue(self.panel.save_recovered.isEnabled())
        self.assertIsNone(self.panel.active)

    def test_device_view_identifies_matching_saved_slot(self):
        text = '\n'.join('[=] | '+str(block)+' | '+fixture()[block*16:(block+1)*16].hex(' ')+' | ....' for block in range(64))
        with patch.object(self.window.session,'send') as send:
            self.panel.view(); self.window.result(send.call_args.args[0],text)
        self.assertEqual(self.panel.active['slot'],1)
        self.assertIn('matches PC slot(s): 1',self.panel.status.text())

    def test_workbench_simulation_is_tracked(self):
        self.window.result('hf mf sim --1k','[=] Press pm3 button or send another cmd to abort simulation\n')
        self.assertTrue(self.panel.simulating)
        self.assertTrue(self.window.workflow_busy())

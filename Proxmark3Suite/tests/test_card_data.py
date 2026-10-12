import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QMessageBox
from card_data import DumpDraft,CardDataPanel,access_codes,block_location,describe_permissions
from emulation import inspect_dump
from backend import resolve_client,client_environment

app = QApplication.instance() or QApplication([])

def sample(size=1024):
    data = bytearray(size)
    for block in range(size//16):
        if block==block_location(block,size//16)[2]: data[block*16+6:block*16+9] = bytes.fromhex('FF0780')
    return data

class CardDataTests(unittest.TestCase):
    def test_transport_permissions_and_key_b_authentication(self):
        data = sample()
        self.assertEqual(access_codes(data[48:64]),[0,0,0,1])
        self.assertIn('Read: A\nWrite: A',describe_permissions(data,1))
        self.assertIn('Key B is readable',describe_permissions(data,1))
        self.assertIn('Key A read: Never',describe_permissions(data,3))
        self.assertIn('Write: Never',describe_permissions(data,0))

    def test_invalid_permissions_and_large_sector_mapping(self):
        data = sample(4096)
        self.assertEqual(block_location(128,256),(32,0,143))
        self.assertEqual(block_location(255,256),(39,15,255))
        self.assertIn('Sector 39',describe_permissions(data,250))
        data[143*16+6] ^= 1
        with self.assertRaises(ValueError): describe_permissions(data,128)

    def test_access_code_bit_order_all_conditions(self):
        for code in range(8):
            c1=15 if code&4 else 0; c2=15 if code&2 else 0; c3=15 if code&1 else 0
            trailer=bytearray(16); trailer[6:9]=bytes([((~c2&15)<<4)|(~c1&15),(c1<<4)|(~c3&15),(c3<<4)|c2])
            self.assertEqual(access_codes(trailer),[code]*4)

    def test_draft_undo_export_original_preserved_and_dump_extension(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            original=Path(folder)/'original.dump'; original.write_bytes(sample())
            draft=DumpDraft(original); draft.edit(1,'AB '*16)
            self.assertEqual(draft.changed(),[1]); self.assertEqual(original.read_bytes(),sample())
            with self.assertRaises(ValueError): draft.export(original)
            output=Path(folder)/'edited.eml'; draft.export(output)
            self.assertEqual(inspect_dump(output)[0][16:32],bytes.fromhex('AB'*16))
            draft.undo(); self.assertEqual(draft.changed(),[])
            for value in ('GG'*16,'00'*15,'00'*17):
                with self.assertRaises(ValueError): draft.edit(1,value)
            with self.assertRaises(ValueError): draft.edit(999,'00'*16)

    def test_editor_selection_apply_undo_and_discard_cancel(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path=Path(folder)/'original.bin'; path.write_bytes(sample())
            panel=CardDataPanel(None); self.assertTrue(panel.load_path(path))
            panel.table.setCurrentItem(panel.table.topLevelItem(1)); panel.hex.setText('11'*16); panel.apply()
            self.assertEqual(panel.draft.changed(),[1]); self.assertIn('1 edited',panel.summary.text())
            with patch.object(QMessageBox,'question',return_value=QMessageBox.No): self.assertFalse(panel.load_path(path))
            panel.undo(); self.assertEqual(panel.draft.changed(),[])
            panel.close(); panel.deleteLater(); app.processEvents()

    def test_linux_client_resolution_and_loader_environment(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path=Path(folder)/'proxmark3'; path.write_text('test'); path.chmod(0o755)
            with patch('backend.sys.platform','linux'),patch('backend.os.access',return_value=True):
                self.assertEqual(resolve_client(path),str(path.resolve()))
                with self.assertRaises(ValueError): resolve_client(Path(folder)/'missing')
                with patch.dict(os.environ,{'LD_LIBRARY_PATH':'/bundle','LD_LIBRARY_PATH_ORIG':'/native','QT_PLUGIN_PATH':'/bundle/plugins'}):
                    env=client_environment(path)
                    self.assertEqual(env.value('LD_LIBRARY_PATH'),'/native'); self.assertFalse(env.contains('QT_PLUGIN_PATH'))

if __name__ == '__main__': unittest.main()

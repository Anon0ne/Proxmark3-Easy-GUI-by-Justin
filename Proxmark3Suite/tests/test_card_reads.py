import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QSettings
from app import Window
from catalog import parse_dump
from recovery import ClassicCard,recovery_sectors
from card_reads import selected_blocks,read_command,read_payload,export_capture

ROOT=Path(__file__).resolve().parents[1]
app=QApplication.instance() or QApplication([])

def output(block,byte='AB'): return f'[+] {block:3d} | '+(' '.join([byte]*16))+' | ................\n'

class CardReadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT)
        self.w=Window(self.temp.name,QSettings(str(Path(self.temp.name)/'settings.ini'),QSettings.IniFormat),auto_discover=False)
        self.w.commands=parse_dump((ROOT/'client-help.txt').read_text(encoding='utf-8-sig'))
        self.w.catalog_verified=self.w.compatible=self.w.session.ready=True
        self.w.session_path=self.w.launcher.text(); self.w.session_port=self.w.port.currentText(); self.w.session_offline=False
        self.w.current_uid='12345678'; self.w.recovery_card=ClassicCard('12345678','1k')
        self.r=self.w.card_data.reads; self.r.blocks.setText('1'); self.r.key.setText('FFFFFFFFFFFF')

    def tearDown(self):
        self.r.abort('Test complete'); self.w.close(); self.w.deleteLater(); app.processEvents(); self.temp.cleanup()

    def test_range_validation_and_metadata_flags(self):
        self.assertEqual(selected_blocks('0-2,2,8',64),[0,1,2,8])
        self.assertEqual(len(selected_blocks('*',256)),256)
        for value in ('3-1','0-64','1;hw reset','-1',''):
            with self.assertRaises(ValueError): selected_blocks(value,64)
        self.assertEqual(read_command(self.w.commands,1,'A','FFFFFFFFFFFF'),'hf mf rdbl --blk 1 -a --key FFFFFFFFFFFF')
        with self.assertRaises(ValueError): read_command({},1,'A','FFFFFFFFFFFF')
        with self.assertRaises(ValueError): read_command(self.w.commands,1,'A','BAD')

    def test_payload_requires_matching_block_exact_bytes_no_error(self):
        self.assertEqual(read_payload(output(1),1),bytes.fromhex('AB'*16))
        for value in (output(2),output(1)+'[-] Auth error\n',output(1)+output(1,'CD'),'[+] data: '+'AB'*16):
            self.assertIsNone(read_payload(value,1))

    def test_decline_never_sends_or_starts_capture(self):
        with patch.object(self.w,'ask_workflow',return_value=QMessageBox.No),patch.object(self.w.session,'send') as send:
            self.r.start(); send.assert_not_called(); self.assertIsNone(self.r.pending)

    def test_two_reads_and_uid_checks_required_before_verified_result(self):
        with patch.object(self.w,'ask_workflow',return_value=QMessageBox.Yes),patch.object(self.w.session,'send') as send:
            self.r.start(); self.assertTrue(self.w.workflow_busy())
            self.w.result('hf 14a reader','UID: 12 34 56 78\n')
            self.w.result('hf mf rdbl --blk 1 -a --key FFFFFFFFFFFF',output(1))
            self.assertNotIn('1',self.r.report['blocks'])
            self.w.result('hf 14a reader','UID: 12 34 56 78\n')
            self.w.result('hf mf rdbl --blk 1 -a --key FFFFFFFFFFFF',output(1))
            app.processEvents()
            self.assertTrue(self.r.report['blocks']['1']['verified']); self.assertEqual(self.r.report['status'],'completed')
            self.assertEqual([c.args[0] for c in send.call_args_list],['hf 14a reader','hf mf rdbl --blk 1 -a --key FFFFFFFFFFFF']*2)

    def test_card_change_cancels_without_block_read(self):
        with patch.object(self.w,'ask_workflow',return_value=QMessageBox.Yes),patch.object(self.w.session,'send') as send:
            self.r.start(); self.w.result('hf 14a reader','UID: 87 65 43 21\n'); app.processEvents()
            self.assertEqual(send.call_count,1); self.assertEqual(self.r.report['status'],'interrupted'); self.assertEqual(self.r.report['blocks'],{})

    def test_cancel_and_unrelated_commands_are_locked(self):
        with patch.object(self.w,'ask_workflow',return_value=QMessageBox.Yes),patch.object(self.w.session,'send') as send:
            self.r.start(); self.w.dispatch('hw status'); self.assertEqual(send.call_count,1)
            self.r.cancel(); self.w.result('hf 14a reader','UID: 12 34 56 78\n'); app.processEvents()
            self.assertEqual(self.r.report['status'],'canceled'); self.assertEqual(send.call_count,1)

    def test_differing_second_read_is_partial_not_verified(self):
        with patch.object(self.w,'ask_workflow',return_value=QMessageBox.Yes),patch.object(self.w.session,'send'):
            self.r.start()
            for command,text in [('hf 14a reader','UID: 12 34 56 78\n'),('hf mf rdbl --blk 1 -a --key FFFFFFFFFFFF',output(1)),('hf 14a reader','UID: 12 34 56 78\n'),('hf mf rdbl --blk 1 -a --key FFFFFFFFFFFF',output(1,'CD'))]: self.w.result(command,text)
            app.processEvents(); self.assertEqual(self.r.report['status'],'partial'); self.assertFalse(self.r.report['blocks']['1']['verified'])

    def test_partial_export_has_no_fabricated_binary_and_full_export_hash(self):
        report={'size':'mini','blocks':{'1':{'status':'read','verified':True,'data':'AB'*16}}}
        path=export_capture(report,self.temp.name); obj=json.loads(path.read_text())
        self.assertFalse(obj['complete_card_data']); self.assertIsNone(obj['data_file']); self.assertFalse(list(Path(self.temp.name).glob('*.bin')))
        report['blocks']={str(i):{'status':'read','verified':True,'data':'AB'*16} for i in range(20)}
        path=export_capture(report,self.temp.name); obj=json.loads(path.read_text()); self.assertTrue(obj['complete_card_data']); self.assertFalse(obj['recovered_keys_complete'])
        self.assertEqual((Path(self.temp.name)/obj['data_file']).read_bytes(),bytes.fromhex('AB'*320))

    def test_recovery_table_respects_unknown_markers_and_latest_table(self):
        header='[+] Sec | Blk | key A        |res| key B        |res\n'
        rows=recovery_sectors(header+'[+] 0 | 3 | FFFFFFFFFFFF | 1 | ------------ | 0 \n[+] 1 | 7 | A0A1A2A3A4A5 | 0 | 000000000000 | D |\n','1k')
        self.assertEqual(len(rows),16); self.assertEqual(rows[0]['A']['key'],'FFFFFFFFFFFF'); self.assertIsNone(rows[0]['B']['key'])
        self.assertIsNone(rows[1]['A']['key']); self.assertEqual(rows[1]['B']['key'],'000000000000'); self.assertIsNone(rows[15]['A']['key'])
        self.assertIsNone(recovery_sectors(header+'0 | 3 | FFFFFFFFFFFF | 1 | ------------ | 0 |\n'+header,'1k')[0]['A']['key'])

if __name__=='__main__': unittest.main()

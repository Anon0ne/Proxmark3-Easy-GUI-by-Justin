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
from recovery import ClassicCard,detect_classic,card_uid,recovery_command,card_summary

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

    def test_classic_detection_and_ambiguous_families(self):
        text = '[+] UID: 12 34 56 78\n[+] MIFARE Classic 1K\n[+] Valid ISO 14443-A tag found'
        self.assertEqual(detect_classic(text),ClassicCard('12345678','1k'))
        for suffix in ['\nMIFARE Plus','\nMIFARE Classic 4K','\nNTAG213','\nNo known/supported tags found','\nUID: AA BB CC DD']:
            self.assertIsNone(detect_classic(text+suffix))
        self.assertIsNone(detect_classic('MIFARE Classic 1K'))
        self.assertEqual(detect_classic('UID: 12 34 56 78\nMIFARE Mini 0.3K\n'),ClassicCard('12345678','mini'))

    def test_recovery_uses_only_documented_flags(self):
        self.assertEqual(recovery_command(ClassicCard('12345678','1k'),self.catalog),'hf mf autopwn --1k --file mfc_default_keys')
        with self.assertRaises(ValueError): recovery_command(ClassicCard('12345678','8k'),self.catalog)
        with self.assertRaises(ValueError): recovery_command(ClassicCard('12345678','1k'),{})

class UiTests(unittest.TestCase):
    def test_corrupt_card_history_is_preserved_after_new_observation(self):
        path = Path(self.temp.name)/'cards.json'; original = b'{broken history'
        path.write_bytes(original)
        other = Window(self.temp.name,QSettings(str(Path(self.temp.name)/'other.ini'),QSettings.IniFormat),auto_discover=False)
        try:
            self.assertIsNotNone(other.card_history_error)
            other.record_card('hf search','[+] UID: 12 34 56 78\nMIFARE Classic 1K\n')
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(other.current_uid,'12345678')
            self.assertIn('session-only',other.statusBar().currentMessage())
        finally: other.close(); other.deleteLater(); app.processEvents()

    def test_invalid_history_record_does_not_silently_remove_other_records(self):
        path = Path(self.temp.name)/'cards.json'
        original = b'{"12345678":{"observations":{}},"87654321":{"observations":[],"last_seen":5}}'
        path.write_bytes(original)
        other = Window(self.temp.name,QSettings(str(Path(self.temp.name)/'other.ini'),QSettings.IniFormat),auto_discover=False)
        try:
            self.assertIsNotNone(other.card_history_error)
            other.record_card('hf search','[+] UID: 12 34 56 78\n')
            self.assertEqual(path.read_bytes(),original)
        finally: other.close(); other.deleteLater(); app.processEvents()

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
        self.window.session.ready = True
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

    def prepare_recovery(self):
        self.window.session_path = self.window.launcher.text(); self.window.session_port = self.window.port.currentText(); self.window.session_offline = False
        self.window.compatible = True; self.window.session.ready = True
        self.window.recovery_card = ClassicCard('12345678','1k')
        self.window.info_verified_uid = '12345678'

    def test_recovery_decline_does_not_send(self):
        self.prepare_recovery()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No),patch.object(self.window.session,'send') as send:
            self.window.review_recovery(); send.assert_not_called()
        self.assertIsNone(self.window.pending_recovery)

    def test_recovery_verifies_uid_then_runs_without_second_prompt(self):
        self.prepare_recovery()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes) as confirm,patch.object(self.window.session,'send') as send:
            self.window.review_recovery(); send.assert_called_once_with('hf 14a reader')
            self.window.result('hf 14a reader','[+] UID: 12 34 56 78\n')
            self.assertEqual(send.call_args.args,('hf mf autopwn --1k --file mfc_default_keys',))
            self.assertEqual(confirm.call_count,1)
            self.assertTrue(self.window.recovery_running)
            self.assertEqual(self.window.session.command_timeout_ms,1800000)
            self.window.result('hf mf autopwn --1k --file mfc_default_keys','No keys found')
            self.assertFalse(self.window.recovery_running)
            self.assertEqual(self.window.timeout.currentIndex(),0)

    def test_recovery_cancels_when_card_changes(self):
        self.prepare_recovery()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(self.window.session,'send') as send:
            self.window.review_recovery(); self.window.result('hf 14a reader','UID: AA BB CC DD\n')
            send.assert_called_once_with('hf 14a reader')
        self.assertIsNone(self.window.pending_recovery)

    def test_repeated_detected_card_prompts_once(self):
        self.prepare_recovery()
        text = '[+] UID: 12 34 56 78\n[+] MIFARE Classic 1K\n'
        with patch.object(self.window,'review_information') as offer:
            self.window.result('hf search',text); app.processEvents()
            self.window.result('hf search',text); app.processEvents()
            self.assertEqual(offer.call_count,1)

    def test_information_checks_save_card_before_recovery(self):
        self.prepare_recovery(); self.window.info_verified_uid = None
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(self.window.session,'send') as send,patch.object(self.window,'review_recovery') as recover:
            self.window.review_information()
            send.assert_called_once_with('hf 14a reader')
            self.window.result('hf 14a reader','UID: 12 34 56 78\n')
            self.assertEqual(send.call_args.args,('hf mf info',))
            self.window.result('hf mf info','UID: 12 34 56 78\nMagic capabilities... Gen 1a\n')
            app.processEvents()
            recover.assert_called_once()
        self.assertEqual(self.window.info_verified_uid,'12345678')
        self.assertTrue((self.window.data_dir/'cards.json').exists())
        self.assertIn('Gen 1a',self.window.current_card.toPlainText())

    def test_information_checks_cancel_changed_card(self):
        self.prepare_recovery(); self.window.info_verified_uid = None
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(self.window.session,'send') as send:
            self.window.review_information()
            self.window.result('hf 14a reader','UID: AA BB CC DD\n')
            send.assert_called_once_with('hf 14a reader')
        self.assertIsNone(self.window.pending_info)
        self.assertIsNone(self.window.info_verified_uid)

    def test_search_uid_annotation_is_detected(self):
        text = 'UID: 1F 1D AB 41   ( FNUID, fixed, non-unique ID )\nMIFARE Classic 1K\n'
        self.assertEqual(detect_classic(text),ClassicCard('1F1DAB41','1k'))

    def test_card_summary_keeps_facts_without_console_noise(self):
        text = '[=] Searching for Topaz tag...\n[+] UID: 1F 1D AB 41\n[+] ATQA: 00 04\n[+] SAK: 08 [2]\n[+] MIFARE Classic 1K\n[+] Magic capabilities... Gen 1a\n[#] Static nonce....... 01200145\n[+] Static nonce... yes\n[+] Sector 1 key A... A0A1A2A3A4A5\n[+] Fudan based card\n[?] Hint: Try hf mf info\n[usb|script] pm3 --> rem SUITE_abc\n'
        summary = card_summary('1F1DAB41',{'hf search':text,'hf mf info':text})
        for fact in ['UID: 1F1DAB41','ATQA: 00 04','SAK: 08','Gen 1a','Nonce value: 01200145','Static nonce: yes','Sector 1 key A: A0A1A2A3A4A5','Fingerprint: Fudan based card']:
            self.assertIn(fact,summary)
        for noise in ['Searching','Hint:','SUITE_','[+]','[usb']: self.assertNotIn(noise,summary)
        self.assertEqual(summary.count('Magic capabilities:'),1)

    def test_pending_workflow_blocks_reconnect_without_exception(self):
        self.window.pending_info = ClassicCard('12345678','1k')
        with patch.object(self.window.session,'start') as start:
            self.window.connect_client(); start.assert_not_called()
        self.assertIsNotNone(self.window.pending_info)

    def test_pending_workflow_blocks_unrelated_commands_and_searches(self):
        self.prepare_recovery()
        self.window.pending_info = self.window.recovery_card
        self.window.queue = ['hw status']
        with patch.object(self.window.session,'send') as send:
            self.window.dispatch('hw version')
            self.window.identify(); self.window.diagnostics()
            send.assert_not_called()
        self.assertIsNotNone(self.window.pending_info)
        self.assertEqual(self.window.queue,['hw status'])

    def test_progress_tracks_stages_without_fake_percentages(self):
        self.window.set_workflow('recovering','Recovering',True)
        self.assertEqual(self.window.workflow_progress.maximum(),0)
        self.assertFalse(self.window.workflow_progress.isTextVisible())
        self.assertTrue(self.window.elapsed_timer.isActive())
        self.window.set_workflow('inspected','Information collected')
        self.assertEqual(self.window.workflow_progress.value(),2)
        self.assertEqual(self.window.workflow_progress.maximum(),4)
        self.assertFalse(self.window.elapsed_timer.isActive())

    def test_current_card_clears_after_no_card_but_history_remains(self):
        self.window.offer_auto_recovery.setChecked(False)
        self.window.result('hf search','UID: 12 34 56 78\nMIFARE Classic 1K\nMagic capabilities... Gen 1a\n')
        self.window.result('hf search','No known/supported 13.56 MHz tags found\n')
        self.assertIsNone(self.window.current_uid)
        self.assertEqual(self.window.current_card.toPlainText(),'')
        self.assertIn('12345678',self.window.card_records)

    def test_recovery_communication_failure_shows_failure_stage(self):
        self.prepare_recovery(); self.window.recovery_running = True
        self.window.result('hf mf autopwn --1k --file mfc_default_keys','No tag detected or other tag communication error')
        self.assertEqual(self.window.workflow_stage,'failed')
        self.assertFalse(self.window.recovery_running)

    def test_dispatch_busy_session_does_not_invalidate_connection(self):
        self.window.compatible = True; self.window.session.ready = False
        with patch.object(self.window.session,'send') as send:
            self.window.dispatch('hw version'); send.assert_not_called()
        self.assertTrue(self.window.compatible)

if __name__ == '__main__': unittest.main()

import unittest
from eventlog import EventLogFormatter

class EventLogTests(unittest.TestCase):
    def test_spinner_redraws_and_fences(self):
        f = EventLogFormatter()
        self.assertEqual(f.feed('[/]     \r[-] Searching for Topaz tag...\r[\\]    \r[|] Searching for ISO14443-A tag...\r\r\n[+] UID: 12345678\r\r\n[usb|script] pm3 --> rem SUITE_abc123\n[+] remark: SUITE_abc123\n'),
            'Searching for Topaz tag...\nSearching for ISO14443-A tag...\n[+] UID: 12345678\n')

    def test_split_ansi_and_line(self):
        f = EventLogFormatter()
        self.assertEqual(f.feed('\x1b[3'), '')
        self.assertEqual(f.feed('2m[+] U'), '')
        self.assertEqual(f.feed('ID: 1234\x1b[0m\r'), '[+] UID: 1234\n')
        self.assertEqual(f.feed('\r\n'), '')

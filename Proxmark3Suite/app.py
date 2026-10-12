"""Firmware-native Windows workbench, version 0.2.0."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
from datetime import datetime
from time import monotonic
from PySide6.QtCore import Qt, QProcess, QTimer, QSettings, QStandardPaths
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QTreeWidget,QTreeWidgetItem,QLineEdit,QPushButton,QPlainTextEdit,QLabel,QComboBox,
    QFormLayout,QSplitter,QMessageBox,QFileDialog,QCheckBox,QTabWidget,QScrollArea,QHeaderView,QDialog,QTextBrowser,QProgressBar,QGroupBox,QFrame,QInputDialog)
from eventlog import EventLogFormatter
from launch_support import serial_ports,client_candidates,default_client,default_port
from catalog import parse_dump, build_command, needs_confirmation, clean
from backend import Session, resolve_client, client_environment, start_external
from recovery import detect_classic,card_uid,recovery_command,card_summary,recovery_sectors

VERSION = '0.7-dev'
TARGET = 'v4.21611-636-gda509461b'
HELP_TOPICS = {
    'Getting started': '''# Getting started
Connect the Proxmark3 Easy, select its COM port, and choose the installed pm3.bat launcher.
Click **Refresh command catalog**, **Connect**, then **Verify hardware**. Review compatibility before running commands.

Use the searchable command tree to find a command. Its argument form and exact help come from your installed client.
Review the command preview before execution. Favorites and command history make repeated tasks easier.
''',
    'Card positioning and identification': '''# Card positioning and identification
Place one HF card over the HF antenna. Use **Identify LF + HF** in the Cards tab.
If identification works but a subsequent operation reports no tag, keep the card still and try a small change in distance or position.
Remove other cards and metal near the antenna. Repeated read failures should be resolved before writing.

Automatic identification runs while idle. Recovery requires a separate confirmation and pauses automatic scanning.
''',
    'Auto Recovery and lab cards': '''# Auto Recovery
For a clearly identified MIFARE Classic card, the suite can offer the installed client's **hf mf autopwn** workflow.
It checks the UID again before starting. Recovery may fail or find only some keys; command completion alone does not prove success.
Inspect the recovered key table and saved dump. Files may contain sensitive card data.

Use your own disposable lab cards. Save and verify a full backup before modifying keys or data.
Changing a UID alone does not test key recovery. A key present in the default dictionary tests dictionary lookup.
Card writes require explicit confirmation. Sector trailer changes affect access and must preserve valid access bits.

[RRG workflow documentation](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/cheatsheet.md)
''',
    'Troubleshooting and logs': '''# Troubleshooting
**Invalid serial port:** check the COM port, USB connection, and whether another client already owns the device.

**No tag / communication error:** reposition the card and repeat identification. This is not a successful recovery.

**Firmware mismatch:** verify hardware and use a matching client and firmware. Review the Firmware tab before updating.

The live console displays terminal redraws as separate lines and hides internal transaction markers.
Use the console export control to save displayed output. Session logs rotate automatically.
Exact firmware help remains available in the command workbench.
''',
    'Emulation and PC slots': '''# Emulation
The Emulation tab has 16 persistent PC slots for Classic Mini/1K/2K/4K dumps.
These slots are separate from the device's current emulator buffer.

Import and name a dump. Inspect all blocks, rename, export or clear its slot.
Read device memory to match it against saved slots, or capture it into a slot.
Choose the correct memory format; the default is Classic 1K.

Loading requires confirmation and verifies device read-back against the saved hash.
Simulation requires separate confirmation and another read-back check.
Use Stop simulation before other tasks. If the client disconnects, the physical PM3 button can stop RF simulation.

Flash-backed standalone multi-slot support requires suitable hardware and firmware.
This GUI does not assume it is available on a Generic Easy.
''',
}
STYLE = '''
QWidget {background:#0f141a;color:#e8edf2;font-family:"Segoe UI";font-size:12pt;}
QLabel#title {font-size:22pt;font-weight:600;} QLabel#muted {color:#aab8c7;}
QGroupBox {border:1px solid #2a3c4a;border-radius:10px;margin-top:14px;padding:16px;background:#131e28;}
QGroupBox::title {subcontrol-origin:margin;left:16px;padding:0 6px;color:#b6c8d7;}
QGroupBox QLabel,QGroupBox QCheckBox {background:transparent;}
QProgressBar {background:#223442;border:0;border-radius:4px;min-height:8px;max-height:8px;}
QProgressBar::chunk {background:#2dd4bf;border-radius:4px;}
QScrollBar:vertical {background:#131e28;width:10px;margin:0;}
QScrollBar::handle:vertical {background:#3c5264;min-height:28px;border-radius:4px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
QMenuBar {background:#0f141a;} QMenuBar::item:selected {background:#304a5c;}
QMenu {background:#17222e;border:1px solid #334656;} QMenu::item:selected {background:#206459;}
QLineEdit,QPlainTextEdit,QTreeWidget,QComboBox {background:#111b25;border:1px solid #334656;border-radius:6px;padding:7px;selection-background-color:#206459;}
QPushButton {background:#223442;border:1px solid #3c5264;border-radius:6px;padding:9px 15px;}
QPushButton:hover {background:#304a5c;} QPushButton:disabled {color:#82909c;background:#18222c;}
QPushButton#primary {background:#2dd4bf;color:#042f2a;font-weight:600;border:0;}
QPushButton#primary:disabled {background:#1c4948;color:#85aaa7;}
QPushButton#danger {color:#ffaaa1;border-color:#a45550;}
QTabBar::tab {padding:10px 18px;background:#17222e;border-bottom:2px solid #17222e;}
QTabBar::tab:selected {border-bottom:2px solid #2dd4bf;color:#75eedb;}
QHeaderView::section {background:#20303e;padding:7px;border:0;}
QCheckBox {spacing:8px;} QCheckBox::indicator {width:18px;height:18px;}
QToolTip {background:#223442;color:white;border:1px solid #4c6678;}
'''

def row(*widgets):
    box = QHBoxLayout()
    for widget in widgets: box.addWidget(widget)
    return box

def saved_list(settings,key):
    try:
        value = json.loads(settings.value(key,'[]'))
        return [item for item in value if isinstance(item,str)] if isinstance(value,list) else []
    except (TypeError,ValueError):
        return []

class Window(QMainWindow):
    def __init__(self, data_dir=None, settings=None, auto_discover=True):
        super().__init__()
        self.setWindowTitle(f'Proxmark3 Engineering Suite {VERSION}')
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / 'assets' / 'app-icon.ico')))
        self.resize(1280, 850)
        self.setMinimumSize(980,720)
        self.settings = settings or QSettings('Anon0ne', 'Proxmark3EngineeringSuite')
        self.data_dir = Path(data_dir or QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger('suite.'+str(self.data_dir))
        if not self.logger.handlers:
            handler = RotatingFileHandler(self.data_dir/'session.log', maxBytes=5_000_000, backupCount=4, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.commands, self.fields, self.queue = {}, [], []
        self.current = self.device_version = self.client_version = ''
        self.compatible = self.catalog_verified = False
        self.discovery_generation = 0
        self.recovery_card = None
        self.pending_recovery = None
        self.approved_recovery = None
        self.approved_emulator = None
        self.approved_card_read = None
        self.recovery_running = False
        self.recovery_timeout_index = None
        self.last_recovery_offer = None
        self.pending_info = None
        self.info_verified_uid = None
        self.current_uid = None
        self.current_observations = {}
        self.workflow_prompt = False
        self.workflow_stage = 'idle'
        self.workflow_started = None
        self.card_history_error = None
        try:
            records = json.loads((self.data_dir/'cards.json').read_text(encoding='utf-8'))
            if not isinstance(records,dict) or any(
                not isinstance(record,dict) or not isinstance(record.get('observations'),dict) or
                not isinstance(record.get('last_seen',''),str) or
                any(not isinstance(k,str) or not isinstance(v,str) for k,v in record['observations'].items())
                for record in records.values()):
                raise ValueError('Invalid saved-card history structure.')
            self.card_records = records
        except FileNotFoundError: self.card_records = {}
        except (OSError,ValueError) as error:
            self.card_records = {}; self.card_history_error = str(error)
        self.expected = self.settings.value('expected',TARGET)
        self.runtime_bin = self.settings.value('runtime_bin','')
        self.device_status = ''
        self.favorites = set(saved_list(self.settings,'favorites'))
        self.history_items = saved_list(self.settings,'history')[:50]
        self.session = Session(self)
        self.event_formatter = EventLogFormatter()
        help_menu = self.menuBar().addMenu('&Help')
        for topic in HELP_TOPICS:
            help_menu.addAction(topic, lambda checked=False, name=topic: self.show_guide(name))
        self.session.output.connect(self.console_text)
        self.session.state.connect(self.session_state)
        self.session.failed.connect(self.failure)
        self.session.completed.connect(self.result)
        self.poll = QTimer(self)
        self.poll.setInterval(6000)
        self.poll.timeout.connect(self.identify)
        base = QWidget(); self.setCentralWidget(base)
        layout = QVBoxLayout(base); layout.setContentsMargins(24,18,24,18); layout.setSpacing(12)
        title = QLabel('PROXMARK3'); title.setObjectName('title')
        header = QHBoxLayout(); header.addWidget(title); header.addStretch()
        version = QLabel('ENGINEERING SUITE  /  '+VERSION); version.setObjectName('muted'); header.addWidget(version)
        layout.addLayout(header)
        subtitle = QLabel('Connect your reader. Present a card. Follow the next step.'); subtitle.setObjectName('muted')
        layout.addWidget(subtitle)
        self.badge = QLabel('●  DISCONNECTED'); self.compat = QLabel('Compatibility: not verified')
        layout.addLayout(row(self.badge, self.compat))
        self.launcher = QLineEdit(self.settings.value('launcher',default_client()))
        self.launcher.setAccessibleName('Client launcher path')
        self.port = QComboBox(); self.port.setEditable(True); self.port.addItem(self.settings.value('port',default_port()))
        self.offline = QCheckBox('Offline tools')
        setup = QWidget(); setup_layout = QVBoxLayout(setup)
        setup_layout.addWidget(QLabel('Connection settings and command catalog'))
        setup_help = QLabel('Choose the installed Iceman client and your reader port. The EXE includes its GUI dependencies; the external Proxmark3 client is required.')
        setup_help.setWordWrap(True); setup_layout.addWidget(setup_help)
        setup_layout.addLayout(row(QLabel('Client'),self.launcher,self.button('Browse…',self.browse)))
        setup_layout.addLayout(row(QLabel('Port'),self.port,self.button('Refresh ports',self.refresh_ports),self.offline))
        setup_layout.addWidget(self.button('Find installed client & ports',self.find_setup))
        self.refresh_ports()
        self.connect_button = self.button('Connect & verify',self.connect_client,primary=True)
        self.discover_button = self.button('Refresh command catalog',self.discover)
        self.timeout = QComboBox(); self.timeout.addItems(['3 minutes','10 minutes','30 minutes']); self.timeout.setToolTip('Client command timeout. Long recovery operations may need more time.')
        self.timeout.currentIndexChanged.connect(lambda index: setattr(self.session,'command_timeout_ms',[180000,600000,1800000][index]))
        self.stop_button = self.button('Disconnect / Stop',self.stop,danger=True)
        connection = QHBoxLayout(); connection.addWidget(self.connect_button); connection.addWidget(self.stop_button); connection.addStretch()
        settings_button = self.button('Connection settings',lambda: self.tabs.setCurrentWidget(setup)); connection.addWidget(settings_button)
        layout.addLayout(connection)
        setup_layout.addLayout(row(self.discover_button,QLabel('Command timeout'),self.timeout))
        setup_layout.addStretch()
        self.tabs = QTabWidget(); layout.addWidget(self.tabs,1)
        workbench = QSplitter(); self.tabs.addTab(workbench,'Command workbench')
        left = QWidget(); lv = QVBoxLayout(left)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search commands and descriptions • Ctrl+K'); self.search.textChanged.connect(self.populate)
        self.only_favorites = QCheckBox('Favorites only'); self.only_favorites.toggled.connect(self.populate)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(['Firmware commands','Availability'])
        self.tree.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self.select); self.tree.itemDoubleClicked.connect(lambda *_: self.select())
        self.catalog_label = QLabel('No catalog loaded')
        for widget in [self.search,self.only_favorites,self.tree,self.catalog_label]: lv.addWidget(widget)
        workbench.addWidget(left)
        right = QWidget(); rv = QVBoxLayout(right)
        self.selected = QLabel('Select a firmware command')
        rv.addLayout(row(self.selected,self.button('Save / remove favorite',self.favorite)))
        self.form_widget = QWidget(); self.form = QFormLayout(self.form_widget)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.form_widget); scroll.setMinimumHeight(165); rv.addWidget(scroll,3)
        self.extra = QLineEdit(); self.extra.setPlaceholderText('Advanced / positional arguments — consult exact help'); self.extra.textChanged.connect(self.preview_command); rv.addWidget(self.extra)
        self.preview = QLineEdit(); self.preview.setReadOnly(True); self.preview.setAccessibleName('Exact command preview'); rv.addWidget(self.preview)
        self.run_button = self.button('Run selected • Ctrl+Enter',self.execute,primary=True)
        rv.addLayout(row(self.run_button,self.button('Copy command',lambda: QApplication.clipboard().setText(self.preview.text()))))
        self.help = QPlainTextEdit(); self.help.setReadOnly(True); self.help.setMinimumHeight(110); self.help.setPlaceholderText('Exact installed-client usage, options and examples.'); rv.addWidget(self.help,2)
        workbench.addWidget(right); workbench.setSizes([440,920])
        cards = QWidget(); cv = QVBoxLayout(cards); cv.setSpacing(16)
        self.workflow_steps = []
        steps = QHBoxLayout()
        for label in ['01  IDENTIFY','02  INSPECT','03  RECOVER','04  RESULTS']:
            widget = QLabel(label); self.workflow_steps.append(widget); steps.addWidget(widget)
        cv.addLayout(steps)
        self.workflow_progress = QProgressBar(); self.workflow_progress.setTextVisible(False); self.workflow_progress.setAccessibleName('Card workflow activity')
        cv.addWidget(self.workflow_progress)
        panes = QHBoxLayout(); panes.setSpacing(16); cv.addLayout(panes,1)
        about = QGroupBox('Current card'); about_layout = QVBoxLayout(about)
        self.card_identity = QLabel('No card identified'); self.card_identity.setStyleSheet('font-size:18pt;font-weight:600;background:transparent;')
        self.card_presence = QLabel('Place one card on the antenna, then identify it.'); self.card_presence.setWordWrap(True); self.card_presence.setObjectName('muted')
        about_layout.addWidget(self.card_identity); about_layout.addWidget(self.card_presence)
        action_panel = QGroupBox('Next step'); actions = QVBoxLayout(action_panel); actions.setSpacing(14)
        self.workflow_message = QLabel('Connect and verify your reader to begin.'); self.workflow_message.setWordWrap(True); actions.addWidget(self.workflow_message)
        self.workflow_elapsed = QLabel(''); self.workflow_elapsed.setObjectName('muted'); actions.addWidget(self.workflow_elapsed)
        action_scroll = QScrollArea(); action_scroll.setWidgetResizable(True); action_scroll.setFrameShape(QFrame.NoFrame)
        action_scroll.setWidget(action_panel); action_panel.setMinimumHeight(440)
        panes.addWidget(about,3); panes.addWidget(action_scroll,2)
        self.auto_detect = QCheckBox('Search while idle'); self.auto_detect.setToolTip('Identify LF and HF every six seconds while no operation is running.'); self.auto_detect.toggled.connect(self.toggle_auto)
        self.identify_button = self.button('Identify card',self.identify,primary=True)
        self.identify_button.setMinimumHeight(40)
        actions.addWidget(self.identify_button)
        actions.addWidget(self.auto_detect)
        self.current_card = QPlainTextEdit(); self.current_card.setReadOnly(True); self.current_card.setFrameStyle(0); self.current_card.setMinimumHeight(180)
        self.current_card.setPlaceholderText('About current card — detected identity and recommended checks appear here.')
        about_layout.addWidget(self.current_card,1)
        about_layout.addWidget(self.button('Saved cards…',self.show_saved_cards))
        self.offer_auto_recovery = QCheckBox('Offer card information checks')
        self.offer_auto_recovery.setToolTip('Ask about read-only information commands when a new Classic card is identified. Recovery always requires separate confirmation.')
        self.offer_auto_recovery.setChecked(True)
        self.recovery_status = QLabel('Auto Recovery: waiting for a supported card. Success is not guaranteed.')
        self.recovery_status.setWordWrap(True)
        self.recovery_button = self.button('Next recommended step',self.review_recovery,primary=True)
        self.recovery_button.setMinimumHeight(40)
        actions.addWidget(self.recovery_button)
        actions.addWidget(self.recovery_status)
        actions.addStretch()
        actions.addWidget(self.offer_auto_recovery)
        details = QCheckBox('Show card activity details')
        self.card_output = QPlainTextEdit(); self.card_output.setReadOnly(True); self.card_output.setMaximumBlockCount(3000)
        self.card_output.hide(); details.toggled.connect(self.card_output.setVisible)
        cv.addWidget(details); cv.addWidget(self.card_output)
        self.tabs.insertTab(0,cards,'Cards'); self.tabs.setCurrentWidget(cards)
        hardware = QWidget(); hv = QVBoxLayout(hardware)
        self.target_label = QLabel('Target: Iceman/RRG '+self.expected+' · PM3 GENERIC / Easy'); hv.addWidget(self.target_label)
        note = QLabel('Card workflows require matching client/device revisions and a verified generic board.'); note.setWordWrap(True); hv.addWidget(note)
        self.diagnostics_button = self.button('Verify hardware',self.diagnostics,primary=True); hv.addWidget(self.diagnostics_button)
        self.hardware_output = QPlainTextEdit(); self.hardware_output.setReadOnly(True); hv.addWidget(self.hardware_output)
        self.tabs.addTab(hardware,'Hardware & compatibility')
        from firmware import FirmwarePanel
        self.firmware = FirmwarePanel(self); self.tabs.addTab(self.firmware,'Firmware updates')
        from emulation import EmulationPanel
        self.emulation = EmulationPanel(self); self.tabs.insertTab(1,self.emulation,'Emulation')
        from card_data import CardDataPanel
        self.card_data = CardDataPanel(self); self.tabs.insertTab(2,self.card_data,'Card Data')
        self.history = QComboBox(); self.history.setEditable(True); self.history.addItems(self.history_items); self.history.setCurrentText(''); self.history.setMinimumWidth(300)
        console_page = QWidget(); console_layout = QVBoxLayout(console_page)
        self.send_button = self.button('Send',self.send_console)
        console_layout.addLayout(row(self.history,self.send_button,self.button('Export log…',self.export),self.button('Clear view',lambda: self.console.clear())))
        self.console = QPlainTextEdit(); self.console.setReadOnly(True); self.console.setMaximumBlockCount(5000); self.console.setFont(QFont('Consolas',11)); console_layout.addWidget(self.console)
        self.tabs.addTab(console_page,'Console')
        self.tabs.addTab(setup,'Settings')
        self.setStyleSheet(STYLE)
        self.elapsed_timer = QTimer(self); self.elapsed_timer.setInterval(1000); self.elapsed_timer.timeout.connect(self.update_elapsed)
        self.set_workflow('idle','Connect and verify your reader to begin.')
        QShortcut(QKeySequence('Ctrl+K'),self,activated=self.search.setFocus)
        QShortcut(QKeySequence('Ctrl+Return'),self,activated=self.execute)
        self.launcher.textEdited.connect(self.invalidate)
        self.port.currentTextChanged.connect(self.invalidate_device)
        self.offline.toggled.connect(self.invalidate_device)
        cache = self.data_dir/'catalog.txt'
        if cache.exists():
            try: self.commands = parse_dump(cache.read_text(encoding='utf-8')); self.populate()
            except (ValueError,OSError): pass
        self.update_controls()
        if auto_discover: QTimer.singleShot(0,self.discover)

    def button(self,text,callback,primary=False,danger=False):
        button = QPushButton(text); button.clicked.connect(callback)
        if primary: button.setObjectName('primary')
        if danger: button.setObjectName('danger')
        return button

    def invalidate_device(self,*_):
        self.compatible = False; self.poll.stop(); self.update_controls()

    def invalidate(self,*_):
        self.discovery_generation += 1
        self.catalog_verified = False; self.invalidate_device()

    def console_text(self,text):
        formatted = self.event_formatter.feed(text)
        self.console.moveCursor(QTextCursor.End); self.console.insertPlainText(formatted)
        if formatted: self.logger.info(formatted.rstrip())

    def show_guide(self, topic):
        dialog = QDialog(self)
        dialog.setWindowTitle(topic)
        dialog.resize(760,560)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(HELP_TOPICS[topic])
        layout.addWidget(browser)
        layout.addWidget(self.button('Close',dialog.accept))
        dialog.exec()

    def failure(self,message):
        if hasattr(self,'card_data'): self.card_data.reads.abort('Read capture interrupted: '+message)
        if hasattr(self,'emulation'):
            self.emulation.invalidate('Client failed. Device memory is unverified; if simulating, press the PM3 button to stop it.')
        self.pending_info = None; self.info_verified_uid = None
        self.finish_recovery('Auto Recovery stopped: '+message)
        self.queue.clear(); self.compatible = False; self.poll.stop(); self.auto_detect.setChecked(False)
        self.console_text('\n[ERROR] '+message+'\n'); self.statusBar().showMessage(message); self.update_controls()
        self.set_workflow('failed',message)

    def browse(self):
        path,_ = QFileDialog.getOpenFileName(self,'Select launcher / client','','Client (*.bat *.exe)' if sys.platform=='win32' else 'All files (*)')
        if path: self.launcher.setText(path); self.invalidate(); self.discover()

    def find_setup(self):
        if self.workflow_busy() or self.session.ready or self.session.active or self.firmware.busy:
            self.statusBar().showMessage('Disconnect or stop the current operation before changing settings.'); return
        self.refresh_ports()
        candidates = client_candidates()
        if not candidates:
            QMessageBox.information(self,'Client setup','No installed Iceman client found. Choose Browse to select it. The GUI does not include the external client. On Linux select the native proxmark3 executable and ensure your account can access its serial device.'); return
        chosen = candidates[0]
        if len(candidates)>1:
            chosen,accepted = QInputDialog.getItem(self,'Select installed client','Client',candidates,0,False)
            if not accepted: return
        self.launcher.setText(chosen); self.settings.setValue('launcher',chosen); self.invalidate(); self.discover()
        ports = serial_ports()
        if len(ports)==1: self.port.setCurrentText(ports[0])
        self.statusBar().showMessage('Review the port, then Connect & verify. Detected ports: '+(', '.join(ports) or 'none'))

    def run_probe(self,arguments,callback):
        try: exe = resolve_client(self.launcher.text())
        except ValueError as error: self.failure(str(error)); return
        process = QProcess(self); process.setProgram(exe); process.setArguments(arguments)
        process.setWorkingDirectory(str(self.data_dir)); process.setProcessEnvironment(client_environment(exe,self.runtime_bin)); process.setProcessChannelMode(QProcess.MergedChannels)
        timer = QTimer(process); timer.setSingleShot(True); timer.timeout.connect(process.kill)
        def done(code,status):
            timer.stop(); text = bytes(process.readAllStandardOutput()).decode('utf-8','replace')
            if code == 0 and status == QProcess.NormalExit: callback(text)
            else: self.failure('Client metadata probe failed: '+text[-1000:])
            process.deleteLater()
        process.finished.connect(done); process.errorOccurred.connect(lambda _: self.failure(process.errorString()))
        start_external(process); timer.start(30000)

    def discover(self):
        self.catalog_verified = False; self.discover_button.setEnabled(False); self.catalog_label.setText('Reading client command help…')
        self.discovery_generation += 1
        generation = self.discovery_generation
        probed_path = self.launcher.text()
        def loaded(text):
            try:
                if generation != self.discovery_generation: return
                if self.launcher.text() != probed_path: raise ValueError('Client changed during discovery. Refresh again.')
                self.commands = parse_dump(text); (self.data_dir/'catalog.txt').write_text(text,encoding='utf-8')
                self.catalog_verified = True; self.populate(); self.catalog_label.setText(f'{len(self.commands)} commands · installed client')
                self.run_probe(['--incognito','--version'],lambda text: self.version_loaded(text) if generation == self.discovery_generation and self.launcher.text() == probed_path else None)
            except (ValueError,OSError) as error: self.failure(str(error))
            self.discover_button.setEnabled(True); self.update_controls()
        self.run_probe(['--fulltext'],loaded)
        QTimer.singleShot(31000,lambda: self.discover_button.setEnabled(True))

    def version_loaded(self,text):
        self.client_version = clean(text); self.check_compatibility()
        if getattr(self,'reconnect_after_discovery',False):
            self.reconnect_after_discovery = False
            self.connect_client()

    def populate(self):
        self.tree.clear(); parents = {}; needle = self.search.text().casefold()
        for name,meta in sorted(self.commands.items()):
            if needle not in (name+' '+meta.help).casefold() or (self.only_favorites.isChecked() and name not in self.favorites): continue
            prefix = ''; parent = self.tree
            for token in name.split()[:-1]:
                prefix = (prefix+' '+token).strip()
                if prefix not in parents: parents[prefix] = QTreeWidgetItem(parent,[token.upper()])
                parent = parents[prefix]
            item = QTreeWidgetItem(parent,[('[fav] ' if name in self.favorites else '')+name.split()[-1],'Offline' if meta.offline else 'Device'])
            item.setData(0,Qt.UserRole,name); item.setToolTip(0,name)
        if needle: self.tree.expandAll()
        else: self.tree.expandToDepth(0)

    def select(self):
        item = self.tree.currentItem(); name = item.data(0,Qt.UserRole) if item else None
        if not name: return
        self.current = name; self.selected.setText(name); meta = self.commands[name]; self.help.setPlainText(meta.help)
        while self.form.rowCount(): self.form.removeRow(0)
        self.fields = []
        for option in meta.options:
            if option.choices:
                field = QComboBox(); field.addItems(['']+option.choices); field.currentTextChanged.connect(self.preview_command)
            elif option.value:
                field = QLineEdit(); field.setPlaceholderText(option.value+' — '+option.description); field.textChanged.connect(self.preview_command)
            else:
                field = QCheckBox(option.description); field.toggled.connect(self.preview_command)
            field.setToolTip(option.description); field.setAccessibleName(option.flag+' '+option.description)
            self.form.addRow(option.flag,field); self.fields.append((option,field))
        if not meta.options: self.form.addRow(QLabel('Consult exact usage below for positional syntax.'))
        self.extra.clear(); self.preview_command()

    def preview_command(self):
        try:
            values = [(o,(f.currentText() if o.choices else f.text()) if o.value else f.isChecked()) for o,f in self.fields]
            self.preview.setText(build_command(self.current,values,self.extra.text()) if self.current else '')
        except ValueError as error: self.preview.setText('Invalid arguments: '+str(error))

    def favorite(self):
        if self.current:
            if self.current in self.favorites: self.favorites.remove(self.current)
            else: self.favorites.add(self.current)
            self.settings.setValue('favorites',json.dumps(sorted(self.favorites))); self.populate()

    def connect_client(self):
        if self.session.process.state() != QProcess.NotRunning:
            self.statusBar().showMessage('Reader client is already running. Disconnect before reconnecting.'); return
        if self.workflow_busy():
            self.statusBar().showMessage('Finish or stop the current card workflow before reconnecting.'); return
        if not self.catalog_verified or not self.client_version:
            self.reconnect_after_discovery = True; self.discover(); return
        try:
            if self.firmware.busy: raise ValueError('Wait for the firmware operation to finish.')
            exe = resolve_client(self.launcher.text()); self.compatible = False; self.device_version = ''; self.queue.clear()
            self.recovery_card = None; self.last_recovery_offer = None
            self.session_path = self.launcher.text(); self.session_port = self.port.currentText(); self.session_offline = self.offline.isChecked()
            self.session.start(exe,self.session_port,self.data_dir,self.session_offline,self.runtime_bin)
            if not self.session_offline: self.queue = ['hw version','hw status']
            self.settings.setValue('launcher',self.launcher.text()); self.settings.setValue('port',self.port.currentText())
            self.set_workflow('connecting','Connecting and checking the reader firmware…',True)
        except ValueError as error: self.failure(str(error))

    def refresh_ports(self):
        selected = self.port.currentText()
        ports = serial_ports()
        self.port.blockSignals(True); self.port.clear()
        self.port.addItems(list(dict.fromkeys([selected]+ports))); self.port.setCurrentText(selected)
        self.port.blockSignals(False)
        self.port.setToolTip('Detected ports: '+(', '.join(ports) or 'none. Connect USB and refresh; a port can also be entered manually.'))

    def session_state(self,state):
        self.badge.setText('●  '+state.upper())
        if state == 'Disconnected': self.compatible = False; self.poll.stop(); self.auto_detect.setChecked(False)
        if state == 'Disconnected':
            if hasattr(self,'card_data'): self.card_data.reads.abort('Client disconnected. Capture is partial; remaining blocks were not read.')
            if hasattr(self,'emulation'):
                self.emulation.invalidate('Disconnected: device memory is unverified. Press the PM3 button if simulation was running.')
            self.pending_info = None; self.info_verified_uid = None
            self.finish_recovery('Auto Recovery stopped: client disconnected.')
            self.recovery_card = None; self.last_recovery_offer = None
            self.clear_present_card()
            if self.workflow_stage != 'failed': self.set_workflow('idle','Reader disconnected. Connect to begin.')
        self.update_controls()
        if state == 'Ready': QTimer.singleShot(0,self.next_command)

    def update_controls(self):
        ready = self.session.ready
        unlocked = not self.workflow_busy() and not self.firmware.busy
        self.run_button.setEnabled(ready and self.catalog_verified and unlocked)
        self.send_button.setEnabled(ready and self.catalog_verified and unlocked)
        self.connect_button.setEnabled(self.session.process.state() == QProcess.NotRunning and unlocked)
        # Keep the running toggle operable while the client is busy.
        self.auto_detect.setEnabled(self.compatible and unlocked)
        self.identify_button.setEnabled(ready and self.compatible and unlocked and not self.queue)
        self.diagnostics_button.setEnabled(ready and unlocked and not self.queue)
        self.recovery_button.setEnabled(ready and self.compatible and self.recovery_card is not None and unlocked and not self.queue)
        self.recovery_button.setVisible(self.recovery_card is not None)
        self.identify_button.setText('Identify another card' if self.recovery_card else 'Identify card')
        identity_style = '' if self.recovery_card else 'primary'
        if self.identify_button.objectName() != identity_style:
            self.identify_button.setObjectName(identity_style)
            self.identify_button.style().unpolish(self.identify_button); self.identify_button.style().polish(self.identify_button)
        self.recovery_status.setVisible(self.recovery_card is not None or self.workflow_stage in {'complete','failed'})
        self.recovery_button.setText('Review recovery effort' if self.recovery_card and self.info_verified_uid == self.recovery_card.uid else 'Collect card information')
        for widget in [self.launcher,self.port,self.offline,self.timeout,self.discover_button]:
            widget.setEnabled(unlocked and not self.session.active)
        self.compat.setText('Compatibility: MATCHED · PM3 GENERIC' if self.compatible else 'Compatibility: UNVERIFIED / MISMATCH · card workflows locked')
        if hasattr(self,'emulation'): self.emulation.update_controls()

    def workflow_busy(self):
        emulator = getattr(self,'emulation',None)
        reads = getattr(getattr(self,'card_data',None),'reads',None)
        return bool(self.pending_info or self.pending_recovery or self.recovery_running or self.workflow_prompt or self.workflow_stage == 'identifying' or emulator and (emulator.pending or emulator.simulating) or reads and reads.pending)

    def set_workflow(self, stage, message, busy=False):
        self.workflow_stage = stage
        self.workflow_message.setText(message)
        checkpoints = {'idle':0,'connecting':0,'identifying':0,'identified':1,'inspecting':1,'inspected':2,'verifying':2,'recovering':2,'complete':4,'failed':0}
        value = checkpoints.get(stage,0)
        self.workflow_progress.setRange(0,0 if busy else 4)
        if not busy: self.workflow_progress.setValue(value)
        for index, label in enumerate(self.workflow_steps):
            active = index == min(value,3)
            color = '#75eedb' if active or index < value else '#82909c'
            label.setStyleSheet('color:'+color+';font-weight:'+('600' if active else '400')+';padding:8px 0;')
        if busy:
            self.workflow_started = monotonic(); self.elapsed_timer.start(); self.update_elapsed()
        else:
            self.workflow_started = None; self.elapsed_timer.stop(); self.workflow_elapsed.setText('')
        self.update_controls()

    def update_elapsed(self):
        if self.workflow_started is None: return
        seconds = int(monotonic()-self.workflow_started)
        self.workflow_elapsed.setText(f'Elapsed {seconds//60:02d}:{seconds%60:02d} · waiting for client output')

    def clear_present_card(self):
        self.current_uid = None; self.current_observations = {}; self.info_verified_uid = None
        self.current_card.clear(); self.card_identity.setText('No card identified')
        self.card_presence.setText('Saved observations remain available in Saved cards.')

    def ask_workflow(self, title, text):
        self.workflow_prompt = True; self.update_controls()
        try: return QMessageBox.question(self,title,text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        finally: self.workflow_prompt = False; self.update_controls()

    def diagnostics(self):
        if self.workflow_busy(): self.statusBar().showMessage('Card workflow in progress.'); return
        if not self.session.ready: self.failure('Connect and wait for the client to become ready.'); return
        self.queue = ['hw version','hw status','hw ping']; self.next_command()

    def next_command(self):
        if self.queue and self.session.ready: self.dispatch(self.queue.pop(0),internal=True)

    def dispatch(self,line,internal=False):
        if not self.session.ready:
            self.statusBar().showMessage('Connect the reader and wait for the current operation to finish.'); return
        workflow_internal = internal and ((self.pending_info or self.pending_recovery) and line in {'hf 14a reader','hf mf info'} or self.workflow_stage == 'identifying' and line in {'lf search','hf search'})
        if self.workflow_busy() and not workflow_internal and line not in {self.approved_recovery,self.approved_emulator,self.approved_card_read}:
            self.statusBar().showMessage('Wait for the card workflow to finish, or stop it first.'); return
        try:
            if self.firmware.busy: raise ValueError('Wait for the firmware operation to finish.')
            confirm = needs_confirmation(line)
            if not internal: self.poll.stop(); self.auto_detect.setChecked(False); self.queue.clear()
            if internal and confirm: raise ValueError('Automatic workflow requested an unreviewed command.')
            if self.launcher.text() != getattr(self,'session_path','') or self.port.currentText() != getattr(self,'session_port','') or self.offline.isChecked() != getattr(self,'session_offline',False):
                raise ValueError('Connection settings changed. Disconnect and reconnect.')
            name = next((n for n in sorted(self.commands,key=len,reverse=True) if line == n or line.startswith(n+' ')),None)
            if not name or not self.catalog_verified: raise ValueError('Command is not in the verified installed-client catalog.')
            if not self.commands[name].offline and not self.compatible and line not in {'hw version','hw status','hw ping'}:
                raise ValueError('Verify matching firmware and PM3 GENERIC hardware before device commands.')
            approved = line == self.approved_recovery and line.startswith('hf mf autopwn ')
            emulator_approved = line == self.approved_emulator
            read_approved = line == self.approved_card_read and (line=='hf 14a reader' or line.startswith('hf mf rdbl '))
            self.approved_recovery = None
            self.approved_emulator = None
            self.approved_card_read = None
            if confirm and not approved and not emulator_approved and not read_approved:
                answer = QMessageBox.question(self,'Confirm command','Review the exact command:\n\n'+line+'\n\nThis command has not been classified as read-only. It may modify a card, device, or files. Execute on your authorized target?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
                if answer != QMessageBox.Yes: return
            if not emulator_approved and (line.startswith(('hf mf e','hf mfu e','hf iclass e','hf mf sim','hf mf autopwn','hw reset')) or ' --emu' in line):
                self.emulation.invalidate('Another command can change emulator memory. Read or reload the buffer before simulation.')
            if line.startswith('hf mf autopwn'): self.emulation.clear_recovery_offer()
            self.session.send(line); self.console_text('\n> '+line+'\n')
            if not internal:
                self.history_items = ([line]+[x for x in self.history_items if x != line])[:50]
                self.history.clear(); self.history.addItems(self.history_items); self.history.setCurrentText('')
                self.settings.setValue('history',json.dumps(self.history_items))
            return True
        except ValueError as error: self.failure(str(error))

    def execute(self):
        if self.current: self.dispatch(self.preview.text())

    def send_console(self): self.dispatch(self.history.currentText())

    def result(self,command,text):
        if self.card_data.reads.completed(command,text): return
        self.emulation.completed(command,text)
        if command.startswith('hw '):
            self.hardware_output.appendPlainText('\n> '+command+'\n'+EventLogFormatter().feed(text+'\n'))
            if command == 'hw version': self.device_version = text
            if command == 'hw status': self.device_status = text
            self.check_compatibility()
            if command == 'hw status' and self.compatible:
                self.set_workflow('idle','Reader ready. Place one card on the antenna and select Identify card.')
        if command in {'lf search','hf search'}: self.card_output.appendPlainText(datetime.now().strftime('%H:%M:%S')+'  '+command+'\n'+EventLogFormatter().feed(text+'\n'))
        no_card = command in {'lf search','hf search'} and re.search(r"No known/supported|Couldn't identify a chipset",text,re.I)
        if no_card:
            self.statusBar().showMessage('Search completed: no supported card detected.')
        elif re.search(r'(?im)(?:\[!\]|error|failed|not connected|unknown command)',text):
            self.statusBar().showMessage('Client reported an error; review console output.')
            if re.search(r'not connected|device disconnected',text,re.I): self.compatible = False; self.queue.clear(); self.poll.stop()
        self.update_controls()
        if command in {'hf search','auto','hf 14a reader','hf mf info'}:
            self.record_card(command,text)
        if command in {'hf search','auto'}:
            self.recovery_card = detect_classic(text)
            if self.recovery_card:
                self.set_workflow('identified','Card identified. Collect its information before reviewing recovery.')
                self.recovery_status.setText('MIFARE Classic '+self.recovery_card.size.upper()+' · UID '+self.recovery_card.uid+' · review recommended information checks')
                if self.offer_auto_recovery.isChecked() and self.recovery_card != self.last_recovery_offer:
                    self.last_recovery_offer = self.recovery_card
                    QTimer.singleShot(0,self.review_information)
            else:
                if card_uid(text):
                    self.set_workflow('identified','Card identified. This technology needs its own commands in the workbench; Classic recovery is unavailable.')
                else:
                    self.clear_present_card()
                    self.set_workflow('idle','No card identified. Reposition the card and identify again.')
                self.info_verified_uid = None
                self.last_recovery_offer = None
                self.recovery_status.setText('No unambiguous MIFARE Classic card identified. Other technologies require their own documented workflow.')
            self.update_controls()
        if command == 'hf 14a reader' and self.pending_info:
            if card_uid(text) != self.pending_info.uid:
                self.pending_info = None
                self.recovery_status.setText('Information checks canceled: card missing or UID changed.')
                self.set_workflow('failed','Card changed or is missing. Identify the intended card again.')
            else:
                self.dispatch('hf mf info',internal=True)
            return
        if command == 'hf mf info' and self.pending_info:
            card = self.pending_info; self.pending_info = None
            if card_uid(text) != card.uid or re.search(r'no tag|auth error|can.t select|failed|communication error',text,re.I):
                self.recovery_status.setText('Information checks incomplete. Reposition the card and retry before recovery.')
                self.set_workflow('failed','Information checks failed. Reposition the card and retry.')
                return
            self.info_verified_uid = card.uid
            self.recovery_status.setText('Information checks saved. Review current card details before Auto Recovery.')
            self.set_workflow('inspected','Card information collected. Review the recovery effort when ready.')
            QTimer.singleShot(0,self.review_recovery)
            return
        if command == 'hf 14a reader' and self.pending_recovery:
            card,line = self.pending_recovery
            if card_uid(text) != card.uid:
                self.finish_recovery('Auto Recovery canceled: card missing, ambiguous, or UID changed. Identify it again.')
                return
            self.pending_recovery = None
            self.approved_recovery = line
            self.recovery_running = True
            self.card_data.recovery_results.setPlainText('Recovery running for UID '+card.uid+'. Sector key results will appear after the client returns its key table.')
            self.recovery_timeout_index = self.timeout.currentIndex()
            self.timeout.setCurrentIndex(2)
            self.recovery_status.setText('Auto Recovery running · 30-minute timeout · keep the same card on the antenna')
            self.set_workflow('recovering','Recovery in progress. Keep the same card still on the antenna.',True)
            self.dispatch(line)
        elif command.startswith('hf mf autopwn') and self.recovery_running:
            card = self.recovery_card
            if card:
                sectors = recovery_sectors(text,card.size)
                found = sum(row[label]['key'] is not None for row in sectors for label in ('A','B'))
                lines = [f'UID: {card.uid} · Classic {card.size.upper()}\n{found}/{len(sectors)*2} keys explicitly reported found. This does not verify complete card data.\n']
                lines += [f'Sector {row["sector"]:02d} | A: '+(row['A']['key'] or 'unknown')+' | B: '+(row['B']['key'] or 'unknown') for row in sectors]
                self.card_data.recovery_results.setPlainText('\n'.join(lines))
            self.card_output.appendPlainText('\nAUTO RECOVERY RESULT\n'+EventLogFormatter().feed(text+'\n'))
            self.finish_recovery('Auto Recovery finished. Review the client output for recovered keys, partial results and saved dumps; completion alone is not proof of success.')
            if re.search(r'no tag|communication error|no usable key|no keys found|aborted|failed',text,re.I):
                self.set_workflow('failed','Recovery did not complete successfully. Open Console for details, reposition the card, then retry.')
            else:
                self.set_workflow('complete','Recovery command finished. Review keys and saved files in Console; completion alone does not prove a complete backup.')
                if self.emulation.offer_recovered(text,self.recovery_card):
                    QTimer.singleShot(0,self.emulation.offer_save_recovery)

    def review_recovery(self):
        if not self.session.ready or self.queue or not self.compatible or not self.catalog_verified or self.workflow_busy(): return
        card = self.recovery_card
        if not card: return
        if self.info_verified_uid != card.uid:
            self.review_information(); return
        try: line = recovery_command(card,self.commands)
        except ValueError as error:
            self.recovery_status.setText(str(error)); return
        resume_scan = self.auto_detect.isChecked()
        self.poll.stop(); self.auto_detect.setChecked(False)
        answer = self.ask_workflow('Review recovery effort','MIFARE Classic '+card.size.upper()+' · UID '+card.uid+'\n\nAttempt recovery on your own or authorized card?\n\n'+line+'\n\nThis may take many minutes, save sensitive keys/dumps and change emulator memory. It can fail or recover only some keys. No card write is queued.\n\nThe UID is checked again before starting. Keep the same card on the antenna.')
        if answer != QMessageBox.Yes:
            if resume_scan and self.compatible and self.session.ready: self.auto_detect.setChecked(True)
            return
        self.poll.stop(); self.auto_detect.setChecked(False); self.queue.clear()
        self.pending_recovery = (card,line)
        self.recovery_status.setText('Verifying the same card before recovery…')
        self.set_workflow('verifying','Checking card identity before starting recovery…',True)
        self.dispatch('hf 14a reader',internal=True)

    def record_card(self, command, text):
        uid = card_uid(text)
        if not uid: return
        if self.current_uid != uid:
            self.info_verified_uid = None; self.current_observations = {}
        self.current_uid = uid
        record = self.card_records.setdefault(uid, {'uid':uid,'observations':{}})
        record['last_seen'] = datetime.now().isoformat(timespec='seconds')
        record['observations'][command] = EventLogFormatter().feed(text+'\n')
        self.current_observations[command] = record['observations'][command]
        summary = card_summary(uid,self.current_observations)
        self.current_card.setPlainText('\n'.join(summary.splitlines()[1:]))
        self.card_identity.setText(uid)
        card = detect_classic(text)
        self.card_presence.setText('MIFARE Classic '+card.size.upper()+' · detected this session' if card else 'Card observed this session · information below')
        if self.card_history_error:
            self.statusBar().showMessage('Saved-card history cannot be read and is preserved. New observations are session-only until the history is repaired.'); return
        try:
            path = self.data_dir/'cards.json'; temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.card_records,indent=2),encoding='utf-8'); temporary.replace(path)
        except OSError as error: self.statusBar().showMessage('Could not save card history: '+str(error))

    def show_saved_cards(self):
        dialog = QDialog(self); dialog.setWindowTitle('Saved card observations'); dialog.resize(850,600)
        layout = QVBoxLayout(dialog); view = QPlainTextEdit(); view.setReadOnly(True)
        if self.card_history_error:
            warning = QLabel('The saved history could not be read and has not been overwritten. Listed observations are session-only. Preserve and repair '+str(self.data_dir/'cards.json')+' before saving new history.\n'+self.card_history_error)
            warning.setWordWrap(True); layout.addWidget(warning)
        view.setPlainText('\n\n'.join(card_summary(uid,record.get('observations',{}))+'\nLast seen: '+record.get('last_seen','') for uid,record in self.card_records.items()) or 'No saved cards yet.')
        layout.addWidget(view); layout.addWidget(self.button('Close',dialog.accept)); dialog.exec()

    def review_information(self):
        if not self.session.ready or self.queue or not self.compatible or not self.catalog_verified or self.workflow_busy(): return
        card = self.recovery_card
        if not card:
            self.recovery_status.setText('Identify a MIFARE Classic card first. Other card technologies need their own information commands.'); return
        if any(command not in self.commands for command in ['hf 14a reader','hf mf info']):
            self.recovery_status.setText('Installed client lacks the recommended information commands.'); return
        resume_scan = self.auto_detect.isChecked(); self.poll.stop(); self.auto_detect.setChecked(False)
        answer = self.ask_workflow('Collect card information','UID: '+card.uid+'\n\nRun and save these read-only checks?\n\nhf 14a reader\nhf mf info\n\nThey report identity, available keys, fingerprint, magic support and nonce properties. Some details require valid keys. Recovery requires a separate confirmation.')
        if answer != QMessageBox.Yes:
            if resume_scan and self.compatible and self.session.ready: self.auto_detect.setChecked(True)
            return
        self.info_verified_uid = None; self.pending_info = card
        self.recovery_status.setText('Collecting recommended card information…')
        self.set_workflow('inspecting','Collecting card information. Keep the card in place.',True)
        self.dispatch('hf 14a reader',internal=True)

    def finish_recovery(self,message):
        active = self.pending_recovery is not None or self.recovery_running
        self.pending_recovery = self.approved_recovery = None
        self.recovery_running = False
        if self.recovery_timeout_index is not None:
            self.timeout.setCurrentIndex(self.recovery_timeout_index)
            self.recovery_timeout_index = None
        if active:
            self.recovery_status.setText(message)
            if re.search(r'canceled|stopped',message,re.I): self.set_workflow('failed',message)
        if hasattr(self,'recovery_button'): self.update_controls()

    def check_compatibility(self):
        device_lines = [line for line in self.device_version.splitlines() if re.search(r'(?:\bOS[.:]|Firmware)',line,re.I)]
        revision = re.search(r'v\d+\.\d+-\d+-g[0-9a-f]+',self.client_version)
        board = re.search(r'PM3\s*GENERIC',self.device_version,re.I)
        self.compatible = bool(revision and revision.group() == self.expected and board and any(self.expected in line for line in device_lines))
        self.target_label.setText('Target: Iceman/RRG '+self.expected+' · PM3 GENERIC / Easy')
        self.update_controls()

    def toggle_auto(self,enabled):
        if enabled and self.compatible: self.poll.start(); self.identify()
        else: self.poll.stop()

    def identify(self):
        if self.workflow_busy(): self.statusBar().showMessage('Finish or stop the current card workflow first.'); return
        if not self.compatible: self.statusBar().showMessage('Card identification requires verified firmware compatibility.'); return
        if self.session.ready and not self.queue:
            self.set_workflow('identifying','Searching LF and HF for a card…',True)
            self.queue = ['lf search','hf search']; self.next_command()

    def stop(self):
        if self.emulation.simulating and self.session.ready:
            self.emulation.stop_simulation(); return
        if self.session.active and needs_confirmation(self.session.active) and not self.card_data.reads.pending:
            answer = QMessageBox.question(self,'Interrupt operation?','This command may modify the card or device. Interrupting it cannot undo changes already sent.\n\n'+self.session.active+'\n\nStop the client?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer != QMessageBox.Yes: return
        self.queue.clear(); self.poll.stop(); self.auto_detect.setChecked(False); self.session.stop()

    def export(self):
        path,_ = QFileDialog.getSaveFileName(self,'Export visible session log','proxmark-session.txt','Text (*.txt)')
        if path:
            try: Path(path).write_text(self.console.toPlainText(),encoding='utf-8')
            except OSError as error: self.failure(str(error))

    def closeEvent(self,event):
        if hasattr(self,'card_data') and not self.card_data.discard_allowed(): event.ignore(); return
        if hasattr(self,'emulation') and self.emulation.simulating and self.session.ready:
            self.emulation.stop_simulation()
            self.statusBar().showMessage('Stopping simulation. Close again after the break command finishes.')
            event.ignore(); return
        if self.firmware.busy:
            QMessageBox.warning(self,'Firmware operation active','Wait for the firmware operation to finish before closing.'); event.ignore(); return
        if self.session.active and needs_confirmation(self.session.active) and not self.card_data.reads.pending:
            answer = QMessageBox.question(self,'Close during operation?','Closing will interrupt '+self.session.active+'. Changes already sent cannot be undone. Close now?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer != QMessageBox.Yes: event.ignore(); return
        self.poll.stop(); self.session.stopping = True; self.session.process.kill(); self.session.process.waitForFinished(2000)
        for handler in self.logger.handlers[:]:
            handler.close(); self.logger.removeHandler(handler)
        event.accept()
        if hasattr(self,'card_data'): self.card_data.reads.abort('Window closed. Remaining blocks were not read.')

if __name__ == '__main__':
    app = QApplication(sys.argv); app.setStyle('Fusion')
    app.setOrganizationName('Anon0ne'); app.setApplicationName('Proxmark3EngineeringSuite')
    if '--self-test' in sys.argv:
        probe_dir = Path(sys.argv[sys.argv.index('--self-test')+1]); probe_dir.mkdir(parents=True,exist_ok=True)
        window = Window(probe_dir,QSettings(str(probe_dir/'settings.ini'),QSettings.IniFormat),auto_discover=False)
        window.commands = parse_dump((Path(__file__).resolve().parent/'client-help.txt').read_text(encoding='utf-8-sig'))
        window.populate(); window.show(); app.processEvents()
        result = {'commands':len(window.commands),'platform':sys.platform,'serial_access':False,'icon_loaded':not window.windowIcon().isNull(),'card_data_tab':window.tabs.indexOf(window.card_data)>=0}
        (probe_dir/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        window.close(); sys.exit(0 if all((result['commands']>0,result['icon_loaded'],result['card_data_tab'])) else 1)
    elif '--smoke-test' in sys.argv:
        # Metadata only by default. Explicit --hardware enables read-only
        # connection/compatibility diagnostics for release verification.
        smoke_dir = Path(sys.argv[sys.argv.index('--smoke-test')+1]); smoke_dir.mkdir(parents=True,exist_ok=True)
        window = Window(smoke_dir,QSettings(str(smoke_dir/'settings.ini'),QSettings.IniFormat))
        window.launcher.setText(r'C:\rrg_other\pm3.bat')
        timer = QTimer(); timer.setInterval(100)
        smoke_connected = False
        def smoke_check():
            global smoke_connected
            if window.catalog_verified and window.client_version:
                if '--hardware' in sys.argv:
                    if not smoke_connected:
                        smoke_connected = True; window.port.setCurrentText('COM18'); window.connect_client(); return
                    if not window.compatible or not window.session.ready or window.queue: return
                (smoke_dir/'result.json').write_text(json.dumps({'commands':len(window.commands),'client':window.client_version,'serial_access':smoke_connected,'compatibility':window.compatible,'hardware':window.hardware_output.toPlainText() if smoke_connected else ''},indent=2),encoding='utf-8')
                timer.stop(); window.close(); app.quit()
        timer.timeout.connect(smoke_check); timer.start()
        QTimer.singleShot(35000,lambda: app.exit(1))
    else:
        window = Window(); window.show()
    sys.exit(app.exec())

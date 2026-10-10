"""Firmware-native Windows workbench, version 0.2.0."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
from datetime import datetime
from PySide6.QtCore import Qt, QProcess, QTimer, QSettings, QStandardPaths
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QTreeWidget,QTreeWidgetItem,QLineEdit,QPushButton,QPlainTextEdit,QLabel,QComboBox,
    QFormLayout,QSplitter,QMessageBox,QFileDialog,QCheckBox,QTabWidget,QScrollArea,QHeaderView)
from catalog import parse_dump, build_command, needs_confirmation, clean
from backend import Session, resolve_client, client_environment, start_external

VERSION = '0.1b'
TARGET = 'v4.21611-636-gda509461b'
STYLE = '''
QWidget {background:#0f141a;color:#e8edf2;font-family:"Segoe UI";font-size:12pt;}
QLabel#title {font-size:22pt;font-weight:600;} QLabel#muted {color:#aab8c7;}
QLineEdit,QPlainTextEdit,QTreeWidget,QComboBox {background:#111b25;border:1px solid #334656;border-radius:6px;padding:7px;selection-background-color:#206459;}
QPushButton {background:#223442;border:1px solid #3c5264;border-radius:6px;padding:9px 15px;}
QPushButton:hover {background:#304a5c;} QPushButton:disabled {color:#82909c;background:#18222c;}
QPushButton#primary {background:#2dd4bf;color:#042f2a;font-weight:600;border:0;}
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
        self.resize(1440, 940)
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
        self.expected = self.settings.value('expected',TARGET)
        self.runtime_bin = self.settings.value('runtime_bin','')
        self.device_status = ''
        self.favorites = set(saved_list(self.settings,'favorites'))
        self.history_items = saved_list(self.settings,'history')[:50]
        self.session = Session(self)
        self.session.output.connect(self.console_text)
        self.session.state.connect(self.session_state)
        self.session.failed.connect(self.failure)
        self.session.completed.connect(self.result)
        self.poll = QTimer(self)
        self.poll.setInterval(6000)
        self.poll.timeout.connect(self.identify)
        base = QWidget(); self.setCentralWidget(base)
        layout = QVBoxLayout(base); layout.setContentsMargins(24,18,24,18); layout.setSpacing(12)
        title = QLabel('PROXMARK3  /  ENGINEERING SUITE'); title.setObjectName('title')
        layout.addWidget(title)
        subtitle = QLabel('Firmware-native tools · Proxmark3 Easy · Windows workbench'); subtitle.setObjectName('muted')
        layout.addWidget(subtitle)
        self.badge = QLabel('●  DISCONNECTED'); self.compat = QLabel('Compatibility: not verified')
        layout.addLayout(row(self.badge, self.compat))
        self.launcher = QLineEdit(self.settings.value('launcher', r'C:\rrg_other\pm3.bat'))
        self.launcher.setAccessibleName('Client launcher path')
        self.port = QComboBox(); self.port.setEditable(True); self.port.addItem(self.settings.value('port','COM18'))
        self.offline = QCheckBox('Offline tools')
        layout.addLayout(row(QLabel('Client'),self.launcher,self.button('Browse…',self.browse),QLabel('Port'),self.port,self.offline))
        self.connect_button = self.button('Connect',self.connect_client,primary=True)
        self.discover_button = self.button('Refresh command catalog',self.discover)
        self.timeout = QComboBox(); self.timeout.addItems(['3 minutes','10 minutes','30 minutes']); self.timeout.setToolTip('Client command timeout. Long recovery operations may need more time.')
        self.timeout.currentIndexChanged.connect(lambda index: setattr(self.session,'command_timeout_ms',[180000,600000,1800000][index]))
        layout.addLayout(row(self.connect_button,self.button('Disconnect / Stop',self.stop,danger=True),self.discover_button,self.button('Verify hardware',self.diagnostics),self.timeout))
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
        cards = QWidget(); cv = QVBoxLayout(cards)
        intro = QLabel('Present a card to identify its technology. Only “lf search” and “hf search” run automatically.\nIdentification does not imply successful decryption; keys and card technology determine what is possible.'); intro.setWordWrap(True); cv.addWidget(intro)
        self.auto_detect = QCheckBox('Search automatically every 6 seconds while idle'); self.auto_detect.toggled.connect(self.toggle_auto)
        cv.addLayout(row(self.button('Identify LF + HF',self.identify,primary=True),self.auto_detect))
        self.card_output = QPlainTextEdit(); self.card_output.setReadOnly(True); self.card_output.setMaximumBlockCount(3000); cv.addWidget(self.card_output)
        self.tabs.addTab(cards,'Card identification')
        hardware = QWidget(); hv = QVBoxLayout(hardware)
        self.target_label = QLabel('Target: Iceman/RRG '+self.expected+' · PM3 GENERIC / Easy'); hv.addWidget(self.target_label)
        note = QLabel('Card workflows require matching client/device revisions and a verified generic board.'); note.setWordWrap(True); hv.addWidget(note)
        self.hardware_output = QPlainTextEdit(); self.hardware_output.setReadOnly(True); hv.addWidget(self.hardware_output)
        self.tabs.addTab(hardware,'Hardware & compatibility')
        from firmware import FirmwarePanel
        self.firmware = FirmwarePanel(self); self.tabs.addTab(self.firmware,'Firmware updates')
        self.history = QComboBox(); self.history.setEditable(True); self.history.addItems(self.history_items); self.history.setCurrentText(''); self.history.setMinimumWidth(300)
        layout.addLayout(row(QLabel('LIVE CONSOLE'),self.history,self.button('Send',self.send_console),self.button('Export log…',self.export),self.button('Clear view',lambda: self.console.clear())))
        self.console = QPlainTextEdit(); self.console.setReadOnly(True); self.console.setMaximumBlockCount(5000); self.console.setFont(QFont('Consolas',11)); self.console.setMaximumHeight(135); layout.addWidget(self.console)
        self.setStyleSheet(STYLE)
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
        self.console.moveCursor(QTextCursor.End); self.console.insertPlainText(clean(text))
        self.logger.info(clean(text).rstrip())

    def failure(self,message):
        self.queue.clear(); self.compatible = False; self.poll.stop(); self.auto_detect.setChecked(False)
        self.console_text('\n[ERROR] '+message+'\n'); self.statusBar().showMessage(message); self.update_controls()

    def browse(self):
        path,_ = QFileDialog.getOpenFileName(self,'Select launcher / client','','Client (*.bat *.exe)')
        if path: self.launcher.setText(path); self.invalidate(); self.discover()

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
        try:
            if self.firmware.busy: raise ValueError('Wait for the firmware operation to finish.')
            exe = resolve_client(self.launcher.text()); self.compatible = False; self.device_version = ''; self.queue.clear()
            self.session_path = self.launcher.text(); self.session_port = self.port.currentText(); self.session_offline = self.offline.isChecked()
            self.session.start(exe,self.session_port,self.data_dir,self.session_offline,self.runtime_bin)
            if not self.session_offline: self.queue = ['hw version','hw status']
            self.settings.setValue('launcher',self.launcher.text()); self.settings.setValue('port',self.port.currentText())
        except ValueError as error: self.failure(str(error))

    def session_state(self,state):
        self.badge.setText('●  '+state.upper())
        if state == 'Disconnected': self.compatible = False; self.poll.stop(); self.auto_detect.setChecked(False)
        self.update_controls()
        if state == 'Ready': QTimer.singleShot(0,self.next_command)

    def update_controls(self):
        ready = self.session.ready
        self.run_button.setEnabled(ready and self.catalog_verified)
        self.connect_button.setEnabled(self.session.process.state() == QProcess.NotRunning)
        # Keep the running toggle operable while the client is busy.
        self.auto_detect.setEnabled(self.compatible)
        self.compat.setText('Compatibility: MATCHED · PM3 GENERIC' if self.compatible else 'Compatibility: UNVERIFIED / MISMATCH · card workflows locked')

    def diagnostics(self):
        if not self.session.ready: self.failure('Connect and wait for the client to become ready.'); return
        self.queue = ['hw version','hw status','hw ping']; self.next_command()

    def next_command(self):
        if self.queue and self.session.ready: self.dispatch(self.queue.pop(0),internal=True)

    def dispatch(self,line,internal=False):
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
            if confirm:
                answer = QMessageBox.question(self,'Confirm command','Review the exact command:\n\n'+line+'\n\nThis command has not been classified as read-only. It may modify a card, device, or files. Execute on your authorized target?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
                if answer != QMessageBox.Yes: return
            self.session.send(line); self.console_text('\n> '+line+'\n')
            if not internal:
                self.history_items = ([line]+[x for x in self.history_items if x != line])[:50]
                self.history.clear(); self.history.addItems(self.history_items); self.history.setCurrentText('')
                self.settings.setValue('history',json.dumps(self.history_items))
        except ValueError as error: self.failure(str(error))

    def execute(self):
        if self.current: self.dispatch(self.preview.text())

    def send_console(self): self.dispatch(self.history.currentText())

    def result(self,command,text):
        if command.startswith('hw '):
            self.hardware_output.appendPlainText('\n> '+command+'\n'+text)
            if command == 'hw version': self.device_version = text
            if command == 'hw status': self.device_status = text
            self.check_compatibility()
        if command in {'lf search','hf search'}: self.card_output.appendPlainText(datetime.now().strftime('%H:%M:%S')+'  '+command+'\n'+text)
        no_card = command in {'lf search','hf search'} and re.search(r"No known/supported|Couldn't identify a chipset",text,re.I)
        if no_card:
            self.statusBar().showMessage('Search completed: no supported card detected.')
        elif re.search(r'(?im)(?:\[!\]|error|failed|not connected|unknown command)',text):
            self.statusBar().showMessage('Client reported an error; review console output.')
            if re.search(r'not connected|device disconnected',text,re.I): self.compatible = False; self.queue.clear(); self.poll.stop()
        self.update_controls()

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
        if not self.compatible: self.statusBar().showMessage('Card identification requires verified firmware compatibility.'); return
        if self.session.ready and not self.queue: self.queue = ['lf search','hf search']; self.next_command()

    def stop(self):
        if self.session.active and needs_confirmation(self.session.active):
            answer = QMessageBox.question(self,'Interrupt operation?','This command may modify the card or device. Interrupting it cannot undo changes already sent.\n\n'+self.session.active+'\n\nStop the client?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer != QMessageBox.Yes: return
        self.queue.clear(); self.poll.stop(); self.auto_detect.setChecked(False); self.session.stop()

    def export(self):
        path,_ = QFileDialog.getSaveFileName(self,'Export visible session log','proxmark-session.txt','Text (*.txt)')
        if path:
            try: Path(path).write_text(self.console.toPlainText(),encoding='utf-8')
            except OSError as error: self.failure(str(error))

    def closeEvent(self,event):
        if self.firmware.busy:
            QMessageBox.warning(self,'Firmware operation active','Wait for the firmware operation to finish before closing.'); event.ignore(); return
        if self.session.active and needs_confirmation(self.session.active):
            answer = QMessageBox.question(self,'Close during operation?','Closing will interrupt '+self.session.active+'. Changes already sent cannot be undone. Close now?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer != QMessageBox.Yes: event.ignore(); return
        self.poll.stop(); self.session.stopping = True; self.session.process.kill(); self.session.process.waitForFinished(2000)
        for handler in self.logger.handlers[:]:
            handler.close(); self.logger.removeHandler(handler)
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv); app.setStyle('Fusion')
    app.setOrganizationName('Anon0ne'); app.setApplicationName('Proxmark3EngineeringSuite')
    if '--smoke-test' in sys.argv:
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
